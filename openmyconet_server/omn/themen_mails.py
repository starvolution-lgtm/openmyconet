"""
themen_mails.py -- Benachrichtigungen aus den Themenraeumen (Robby, 28.10.2026).

- Wer folgt: automatisch, wer eine Diskussion anlegt oder darin schreibt; zusaetzlich
  ueber "Folgen" / "Nicht mehr folgen" (Tabelle themen_abo).
- Gedrosselt: Mail beim ersten neuen Beitrag; die naechste erst, wenn die Person die
  Diskussion wieder angesehen hat (gesehen_am >= benachrichtigt_am).
- Inhalt OHNE Beitragstext: Titel der Diskussion, Anzeigename, Link (der Text bleibt in
  den Themenraeumen). Sprache = Website-Sprache der Empfaengerin, neutrale Anrede.
- Admin (ADMIN_NOTIFY_EMAIL): jede neue Diskussion, jedes neue Gebiet und jeder neue
  Beitrag von Teilnehmenden sofort (Moderation) -- unabhaengig vom Schalter.
- Schalter THEMEN_BENACHRICHTIGUNG: Mails an Teilnehmende; auf Prod bis zur rechtlichen
  Freigabe aus (Datenschutzerklaerung Abschnitt 10).
Versand ueber die Mail-Queue (omn.mailer.mailqueue_einreihen), nie im Request per SMTP.
"""
import logging
import os
from datetime import datetime, timezone

from flask import abort, current_app, render_template, request, url_for
from flask_mail import Message
from itsdangerous import BadSignature, URLSafeSerializer

from omn.extensions import db
from omn.i18n import LANGS, t
from omn.models import Nutzer, ThemenAbo

logger = logging.getLogger(__name__)


def jetzt():
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)   # SQLite liefert naiv zurueck
    return dt


def aktiv():
    return bool(current_app.config.get('THEMEN_BENACHRICHTIGUNG', False))


def _base_url():
    return os.getenv('BASE_URL', 'https://api.openmyconet.de').rstrip('/')


# --- Folgen ------------------------------------------------------------------------------

def abo_von(nutzer, diskussion):
    return ThemenAbo.query.filter_by(nutzer_id=nutzer.id, diskussion_id=diskussion.id).first()


def folgen(nutzer, diskussion):
    """Folgen (auch automatisch nach Anlegen/eigenem Beitrag) -- zaehlt als gesehen.
    Commit macht der Aufrufer."""
    abo = abo_von(nutzer, diskussion)
    if abo is None:
        abo = ThemenAbo(nutzer_id=nutzer.id, diskussion_id=diskussion.id)
        db.session.add(abo)
    abo.aktiv = True
    abo.gesehen_am = jetzt()
    return abo


def nicht_folgen(nutzer, diskussion):
    abo = abo_von(nutzer, diskussion)
    if abo is not None:
        abo.aktiv = False


def gesehen(nutzer, diskussion):
    """Beim Ansehen der Diskussion: erlaubt die naechste Benachrichtigung."""
    abo = abo_von(nutzer, diskussion)
    if abo is not None:
        abo.gesehen_am = jetzt()
        db.session.commit()


def _darf_benachrichtigt_werden(abo):
    if abo.benachrichtigt_am is None:
        return True
    return abo.gesehen_am is not None and _aware(abo.gesehen_am) >= _aware(abo.benachrichtigt_am)


# --- Folgen per Link aus der Mail beenden (ohne Login) -----------------------------------

def _signierer():
    return URLSafeSerializer(current_app.config['SECRET_KEY'], salt='themen-abo-beenden')


def abbestell_link(abo):
    return _base_url() + url_for('themen_folgen_beenden', token=_signierer().dumps(abo.id))


def folgen_beenden(token):
    """Link in jeder Benachrichtigung (Robby 28.10.2026: ohne umstaendliche Navigation).
    GET fragt nur (Mail-Scanner oeffnen Links), POST beendet das Folgen -- auch die
    One-Click-Abmeldung der Mail-Clients (List-Unsubscribe-Post). Kein Login, kein
    CSRF: der signierte Token ist die Autorisierung (wie /abmelden)."""
    try:
        abo = db.session.get(ThemenAbo, int(_signierer().loads(token)))
    except (BadSignature, ValueError, TypeError):
        abo = None
    if abo is None:
        abort(404)
    nutzer = db.session.get(Nutzer, abo.nutzer_id)
    lang = nutzer.sprache if nutzer and nutzer.sprache in LANGS else 'de'
    from omn.themen import anzeige
    titel = anzeige(abo.diskussion, 'titel', lang)['text']
    fertig = request.method == 'POST'
    if fertig:
        abo.aktiv = False
        db.session.commit()
    seite = render_template('themen_folgen_beenden.html', lang=lang, fertig=fertig, titel=titel, token=token,
                            tx=lambda k: t(k, lang).replace('{titel}', titel))
    return seite, 200, {'X-Robots-Tag': 'noindex, nofollow', 'Cache-Control': 'no-store'}


# --- Mails -------------------------------------------------------------------------------

def _mail(empfaenger, lang, betreff, titel, zeilen, knopf, link, hinweis, abbestellen=None):
    team = t('austausch_mail_team', lang)
    koerper = '\n\n'.join([*zeilen, f'{knopf}: {link}', hinweis, f'{team}\nhttps://www.openmyconet.de']) + '\n'
    if abbestellen:
        abbestell_zeile = f'{t("themen_mail_abbestellen", lang)}: {abbestellen}'
        koerper += f'\n{abbestell_zeile}\n'
        hinweis = f'{hinweis}\n\n{abbestell_zeile}'
    msg = Message(subject=betreff, recipients=[empfaenger])
    msg.body = koerper
    if abbestellen:   # RFC 8058: Mail-Clients zeigen "Abbestellen", Klick = POST auf den Link
        msg.extra_headers = {'List-Unsubscribe': f'<{abbestellen}>',
                             'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click'}
    msg.html = render_template('transaktions_email.html', mail_lang=lang, fusszeile=team, titel=titel,
                               zeilen=zeilen, cta_text=knopf, cta_url=link, hinweis=hinweis)
    return msg


def _einreihen(nachrichten):
    from omn.mailer import mailqueue_einreihen
    try:
        mailqueue_einreihen(nachrichten)
    except Exception as e:  # Benachrichtigungen duerfen nie das Schreiben eines Beitrags abbrechen
        db.session.rollback()
        logger.error('Themenraum-Benachrichtigung nicht eingereiht: %s', e)


def _admin_mail(betreff, zeilen, admin_pfad):
    empfaenger = os.getenv('ADMIN_NOTIFY_EMAIL') or os.getenv('MAIL_USERNAME')
    if not empfaenger:
        return None
    link = _base_url() + admin_pfad
    return _mail(empfaenger, 'de', f'Themenräume: {betreff}', 'Neu in den Themenräumen', zeilen,
                 'Im Admin öffnen', link, 'Moderation: ausblenden, verschieben, löschen im Admin.')


def neuer_beitrag(beitrag):
    """Nach dem Commit eines neuen Beitrags (Teilnehmende oder Team) aufrufen."""
    from omn.themen import anzeige, anzeigename, darf_themenraeume_nutzen
    d = beitrag.diskussion
    nachrichten = []
    if not beitrag.von_team:
        admin = _admin_mail(f'neuer Beitrag in „{d.titel}“',
                            [f'{anzeigename(beitrag, "de")} hat in „{d.titel}“ ({d.themengebiet.titel}) geschrieben.'],
                            f'/admin/themen/diskussion/{d.id}#b{beitrag.id}')
        if admin:
            nachrichten.append(admin)

    if aktiv() and d.sichtbar and d.themengebiet.sichtbar:
        jetzt_ = jetzt()
        for abo in ThemenAbo.query.filter_by(diskussion_id=d.id, aktiv=True).all():
            nutzer = abo.nutzer
            if nutzer is None or nutzer.id == beitrag.autor_nutzer_id:
                continue
            teilnahme = nutzer.themen_teilnahme
            if (teilnahme is None or not teilnahme.benachrichtigungen or not nutzer.email
                    or not darf_themenraeume_nutzen(nutzer) or not _darf_benachrichtigt_werden(abo)):
                continue
            lang = nutzer.sprache if nutzer.sprache in LANGS else 'de'
            titel = anzeige(d, 'titel', lang)['text']
            name = anzeigename(beitrag, lang)
            link = _base_url() + url_for('themen.diskussion', diskussion_id=d.id) + f'?lang={lang}#beitrag-{beitrag.id}'
            nachrichten.append(_mail(
                nutzer.email, lang,
                t('themen_mail_betreff', lang).replace('{titel}', titel),
                t('themen_mail_titel', lang),
                [t('themen_mail_zeile', lang).replace('{name}', name).replace('{titel}', titel)],
                t('themen_mail_knopf', lang), link, t('themen_mail_hinweis', lang),
                abbestellen=abbestell_link(abo),
            ))
            abo.benachrichtigt_am = jetzt_
        db.session.commit()
    _einreihen(nachrichten)


def neue_diskussion(d):
    from omn.themen import anzeigename
    if d.von_team:
        return
    admin = _admin_mail(f'neue Diskussion „{d.titel}“',
                        [f'{anzeigename(d, "de")} hat im Gebiet „{d.themengebiet.titel}“ die Diskussion '
                         f'„{d.titel}“ angelegt.'],
                        f'/admin/themen/diskussion/{d.id}')
    if admin:
        _einreihen([admin])


def neues_gebiet(g):
    from omn.themen import anzeigename
    if g.von_team:
        return
    admin = _admin_mail(f'neues Themengebiet „{g.titel}“',
                        [f'{anzeigename(g, "de")} hat das Themengebiet „{g.titel}“ angelegt.'],
                        f'/admin/themen/gebiet/{g.id}')
    if admin:
        _einreihen([admin])
