"""Verwaltung eingegangener Kontaktanfragen (/kontakt.html-Formular).

Antworten (seit 23.11.2026): Robby beantwortet eine Anfrage direkt hier statt im
Mailprogramm. Versand direkt per mail.send() wie alle Einzel-/Transaktionsmails
(nicht ueber die Rund-Mail-Queue), Reply-To = Projektadresse, BCC an die
Admin-Adresse (damit die Antwort auch im Postfach liegt). Die Antwort wird in
kontakt_antwort gespeichert und mit der Anfrage geloescht (6 Monate nach Eingang,
omn/aufbewahrung.py, Datenschutzerklaerung Abschnitt 'kontaktformular').
"""
import logging
import os
from datetime import timezone
from zoneinfo import ZoneInfo

from flask import flash, redirect, render_template, request, session, url_for
from flask_mail import Message

from omn.admin.audit import protokollieren
from omn.admin.core import admin_bp, role_required
from omn.extensions import db, mail
from omn.models import KontaktAntwort, Kontaktanfrage
from omn.rechtstexte import RECHTSTEXTE

logger = logging.getLogger(__name__)

KONTAKT_STATUS = ['neu', 'bearbeitet', 'erledigt']
BETREFF_MAX = 200
TEXT_MAX = 20000
ORTSZEIT = ZoneInfo('Europe/Berlin')


BETREFF_VORSCHLAG = 'Re: Ihre Kontaktanfrage an OpenMycoNet'


def ortszeit(dt):
    """Antwort-Zeitpunkt (timestamptz; SQLite liefert ihn naiv in UTC) als deutsche Ortszeit."""
    if dt is None:
        return ''
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ORTSZEIT).strftime('%d.%m.%Y %H:%M')


def _seite(nachricht=None, fehler=None, entwurf=None, status=200):
    anfragen_liste = Kontaktanfrage.query.order_by(Kontaktanfrage.erstellt_am.desc()).all()
    return render_template('kontakt_admin.html',
        anfragen_liste=anfragen_liste,
        status_optionen=KONTAKT_STATUS,
        nachricht=nachricht,
        fehler=fehler,
        entwurf=entwurf or {},
        betreff_vorschlag=BETREFF_VORSCHLAG,
        ortszeit=ortszeit,
    ), status


@admin_bp.route('/admin/kontakt', methods=['GET', 'POST'])
@role_required('superadmin')
def kontakt_admin():
    nachricht = None
    fehler = None
    if request.method == 'POST':
        anfrage_id = request.form.get('anfrage_id', type=int)
        anfrage = Kontaktanfrage.query.get(anfrage_id) if anfrage_id else None
        if not anfrage:
            fehler = 'Kontaktanfrage nicht gefunden.'
        elif request.form.get('action') == 'delete':
            nachricht = f'Kontaktanfrage #{anfrage.id} ({anfrage.name or anfrage.email}) gelöscht.'
            db.session.delete(anfrage)
            db.session.commit()
        else:
            neuer_status = request.form.get('status', '').strip()
            if neuer_status not in KONTAKT_STATUS:
                fehler = 'Ungültiger Status.'
            else:
                anfrage.status = neuer_status
                db.session.commit()
                nachricht = f'Status von Kontaktanfrage #{anfrage.id} auf "{neuer_status}" gesetzt.'
    return _seite(nachricht, fehler)


@admin_bp.route('/admin/kontakt/<int:anfrage_id>/antworten', methods=['POST'])
@role_required('superadmin')
def kontakt_antworten(anfrage_id):
    anfrage = db.session.get(Kontaktanfrage, anfrage_id)
    if not anfrage:
        return _seite(fehler='Kontaktanfrage nicht gefunden.', status=404)
    # Zeilenumbrueche im Betreff wuerden Mail-Header einschleusen
    betreff = ' '.join((request.form.get('betreff') or '').split())[:BETREFF_MAX]
    text = (request.form.get('text') or '').replace('\r\n', '\n').strip()
    entwurf = {'anfrage_id': anfrage.id, 'betreff': betreff, 'text': text}
    if not betreff or not text:
        return _seite(fehler='Bitte Betreff und Text ausfüllen.', entwurf=entwurf, status=400)
    if len(text) > TEXT_MAX:
        return _seite(fehler=f'Der Text ist zu lang (höchstens {TEXT_MAX} Zeichen).', entwurf=entwurf, status=400)

    admin_email = os.getenv('ADMIN_NOTIFY_EMAIL') or os.getenv('MAIL_USERNAME')
    msg = Message(
        subject=betreff,
        recipients=[anfrage.email],
        bcc=[admin_email] if admin_email else None,
        reply_to=RECHTSTEXTE['fakten']['mail'],
        body=text + '\n',
    )
    try:
        mail.send(msg)
    except Exception as e:
        logger.error('Antwort auf Kontaktanfrage #%s konnte nicht gesendet werden: %s', anfrage.id, e)
        return _seite(fehler='Die Antwort konnte nicht gesendet werden (Mailserver). Dein Text steht '
                             'noch im Formular, bitte später noch einmal versuchen.', entwurf=entwurf, status=502)

    db.session.add(KontaktAntwort(anfrage_id=anfrage.id, an=anfrage.email, betreff=betreff, text=text,
                                  gesendet_von=session.get('admin_username', '')[:80]))
    anfrage.status = 'bearbeitet'
    db.session.commit()
    protokollieren('kontakt_antwort', f'Kontaktanfrage #{anfrage.id}')
    flash(f'Antwort an {anfrage.email} gesendet (Kontaktanfrage #{anfrage.id}).')
    return redirect(url_for('admin.kontakt_admin') + f'#anfrage-{anfrage.id}')
