"""Durable Warteschlange fuer Rund-Mails (Newsletter, News-Benachrichtigung).

Die Nachrichten werden im Request gebaut (dort funktioniert
`url_for(..., _external=True)` ueber den Host-Header) und dann als Zeilen in
`MailQueue` abgelegt -- eine je Empfaenger. Der Request kehrt sofort zurueck.

Der eigentliche SMTP-Versand laeuft ausserhalb des Requests: `mailqueue_drain`
(CLI `flask mail-queue-drain`, per Cron jede Minute, `deploy/mailqueue_drain.sh`
mit `flock`) claimt einen Batch, oeffnet EINE `mail.connect()`-Verbindung und
arbeitet ihn ab. Ein gunicorn-Neustart mitten im Versand verliert nichts: offene
Zeilen bleiben in der DB, der naechste Cron-Lauf macht weiter. Fehlversuche
werden bis `MAX_VERSUCHE` wiederholt, danach `status='fehler'` + Journal-Log.

Einzel-/Transaktionsmails (Magic-Link, Doppel-Opt-in, Foerderer-Benachrichtigung,
Fehler-Alert) laufen bewusst NICHT hierueber -- die sollen sofort raus, sind
Einzelempfaenger, und der Fehler-Alert darf nicht von derselben Queue abhaengen,
die evtl. gerade das Problem meldet.
"""
import json
from datetime import timedelta

from flask import current_app
from flask_mail import Message

from omn.extensions import db, mail
from omn.models import MailQueue
from omn.zeit import utcnow

MAX_VERSUCHE = 3
HAENGT_NACH = timedelta(minutes=15)   # 'sendet'-Zeilen aelter als das -> Crash, zurueck auf 'offen'
BEHALTEN = timedelta(days=30)         # gesendete Zeilen so lange als Audit-Spur behalten


def mailqueue_einreihen(nachrichten):
    """`nachrichten`: Iterable[flask_mail.Message] (Betreff, recipients, body,
    optional html + extra_headers). Legt je Empfaenger eine MailQueue-Zeile an.
    Unter TESTING wird direkt synchron gedrained, damit `mail.record_messages()`
    deterministisch bleibt. Leere Eingabe = no-op."""
    nachrichten = list(nachrichten)
    if not nachrichten:
        return
    for msg in nachrichten:
        header_json = json.dumps(msg.extra_headers) if msg.extra_headers else None
        for empfaenger in msg.recipients:
            db.session.add(MailQueue(
                empfaenger=empfaenger,
                betreff=msg.subject or '',
                body=msg.body or '',
                html=msg.html,
                header_json=header_json,
            ))
    db.session.commit()

    if current_app.config.get('TESTING'):
        mailqueue_drain(current_app._get_current_object())


def _zu_message(zeile):
    msg = Message(subject=zeile.betreff, recipients=[zeile.empfaenger])
    msg.body = zeile.body
    if zeile.html:
        msg.html = zeile.html
    if zeile.header_json:
        msg.extra_headers = json.loads(zeile.header_json)
    return msg


def _haenger_zuruecksetzen():
    """Zeilen, die ein abgestuerzter Drain im Status 'sendet' liegengelassen hat,
    wieder freigeben."""
    geloest = db.session.execute(
        db.update(MailQueue)
        .where(MailQueue.status == 'sendet', MailQueue.claim_am < utcnow() - HAENGT_NACH)
        .values(status='offen', claim_am=None)
    ).rowcount
    if geloest:
        db.session.commit()
        current_app.logger.warning('MailQueue: %d haengende Zeile(n) zurueckgesetzt', geloest)
    else:
        db.session.rollback()


def _alte_aufraeumen():
    weg = db.session.execute(
        db.delete(MailQueue)
        .where(MailQueue.status == 'gesendet', MailQueue.gesendet_am < utcnow() - BEHALTEN)
    ).rowcount
    if weg:
        db.session.commit()
    else:
        db.session.rollback()


def mailqueue_drain(app, limit=200):
    """Sendet bis zu `limit` offene Zeilen. Gibt die Zahl der erfolgreich
    gesendeten zurueck. Nicht reentrant gedacht -- der Cron serialisiert per
    flock (deploy/mailqueue_drain.sh)."""
    with app.app_context():
        _haenger_zuruecksetzen()

        offen = (MailQueue.query
                 .filter(MailQueue.status == 'offen', MailQueue.versuche < MAX_VERSUCHE)
                 .order_by(MailQueue.id)
                 .limit(limit)
                 .all())
        if not offen:
            _alte_aufraeumen()
            return 0

        ids = [z.id for z in offen]
        db.session.execute(
            db.update(MailQueue).where(MailQueue.id.in_(ids))
            .values(status='sendet', claim_am=utcnow())
        )
        db.session.commit()

        ok = 0
        try:
            with mail.connect() as conn:
                for zeile in offen:
                    try:
                        conn.send(_zu_message(zeile))
                        zeile.status = 'gesendet'
                        zeile.gesendet_am = utcnow()
                        zeile.claim_am = None
                        ok += 1
                    except Exception as fehler:  # eine kaputte Mail darf den Batch nicht stoppen
                        zeile.versuche += 1
                        zeile.letzter_fehler = str(fehler)[:500]
                        zeile.status = 'fehler' if zeile.versuche >= MAX_VERSUCHE else 'offen'
                        zeile.claim_am = None
                        app.logger.exception('MailQueue #%s an %s fehlgeschlagen (Versuch %d)',
                                             zeile.id, zeile.empfaenger, zeile.versuche)
                    db.session.commit()
        except Exception:
            # SMTP-Verbindung tot -- alle noch geclaimten Zeilen zurueckgeben.
            for zeile in offen:
                if zeile.status == 'sendet':
                    zeile.status = 'offen'
                    zeile.claim_am = None
            db.session.commit()
            app.logger.exception('MailQueue-Drain: SMTP-Verbindung fehlgeschlagen')

        _alte_aufraeumen()
        app.logger.info('MailQueue-Drain: %d/%d gesendet', ok, len(offen))
        return ok
