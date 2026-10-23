"""Audit-Log und Login-Alarm fuer Admin-Bereich und Server-MCC (seit 23.10.2026,
Sicherheitsdurchsicht Paket 2).

- protokollieren(aktion, ziel): eine Zeile in AdminAudit (wer, was, woran, IP).
  Wird NACH der eigentlichen Aenderung aufgerufen und committet selbst; ein
  Fehler beim Protokollieren blockiert die Aktion nicht (nur Log-Eintrag).
- Login-Alarm: Mail an ADMIN_NOTIFY_EMAIL/MAIL_USERNAME bei Anmeldung von einer
  IP, von der dieses Konto sich noch nicht (innerhalb der Aufbewahrungsfrist)
  angemeldet hat, und wenn eine IP wegen Fehlversuchen gesperrt wird.
- Ansicht /admin/audit (nur Superadmin).

Aktionen beginnen mit 'login' fuer alles rund um die Anmeldung -- die haben eine
kuerzere Loeschfrist (omn/aufbewahrung.py), weil dort auch IPs Fremder stehen.
"""
import logging
import os

from flask import render_template, request, session
from flask_mail import Message

from omn.admin.core import admin_bp, role_required
from omn.extensions import db, mail
from omn.models import AdminAudit

logger = logging.getLogger(__name__)


def _kurz(text, n):
    text = str(text or '')
    return text if len(text) <= n else text[:n - 1] + '…'


def protokollieren(aktion, ziel='', user=None, anonym=False):
    """Eine Audit-Zeile schreiben. user: AdminUser (beim Login, wenn die Session
    noch nicht steht); anonym=True: kein Konto (Fehlversuch mit unbekanntem
    Namen); sonst Konto aus der Session."""
    try:
        if user is not None:
            uid, name = user.id, user.username
        elif anonym:
            uid, name = None, ''
        else:
            uid, name = session.get('admin_user_id'), session.get('admin_username', '')
        db.session.add(AdminAudit(
            admin_user_id=uid, benutzername=_kurz(name, 80), aktion=_kurz(aktion, 40),
            ziel=_kurz(ziel, 200), ip=_kurz(request.remote_addr, 45),
        ))
        db.session.commit()
    except Exception:  # Protokoll darf die eigentliche Aktion nie scheitern lassen
        db.session.rollback()
        logger.exception('Audit-Eintrag konnte nicht geschrieben werden (%s)', aktion)


def ip_neu_fuer(user, ip):
    """True, wenn es fuer dieses Konto noch keine erfolgreiche Anmeldung von
    dieser IP gibt. VOR dem Protokollieren des aktuellen Logins aufrufen."""
    return not AdminAudit.query.filter_by(admin_user_id=user.id, aktion='login', ip=ip).first()


def alarm_mail(betreff, zeilen):
    """Sicherheits-Hinweis an den Admin (direkt, nicht ueber die Mail-Queue --
    die ist fuer Rund-Mails). Fehler werden nur geloggt."""
    empfaenger = os.getenv('ADMIN_NOTIFY_EMAIL') or os.getenv('MAIL_USERNAME')
    if not empfaenger:
        return
    msg = Message(subject=f'[OpenMycoNet Sicherheit] {betreff}', recipients=[empfaenger])
    msg.body = '\n'.join(zeilen) + '\n\nAudit-Log: https://api.openmyconet.de/admin/audit\n'
    msg.html = render_template('transaktions_email.html', titel=betreff, zeilen=zeilen,
                               cta_text='Audit-Log öffnen',
                               cta_url='https://api.openmyconet.de/admin/audit')
    try:
        mail.send(msg)
    except Exception as e:
        logger.error('Sicherheits-Mail konnte nicht gesendet werden (%s): %s', betreff, e)


@admin_bp.route('/admin/audit')
@role_required('superadmin')
def audit_admin():
    page = request.args.get('page', 1, type=int)
    pagination = AdminAudit.query.order_by(AdminAudit.zeitpunkt.desc(), AdminAudit.id.desc()).paginate(
        page=page, per_page=100, error_out=False
    )
    return render_template('audit_admin.html', pagination=pagination)
