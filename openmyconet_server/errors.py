"""
errors.py — zentrales Error-Handling.

Vorher: gunicorn laeuft ohne Terminal/Logdatei (stdout/stderr gehen ins Leere),
kein globaler errorhandler -- ein unbehandelter 500 auf Prod war fuer niemanden
sichtbar ausser durch Zufall. Kein Sentry/GlitchTip (weitere Infra, DSGVO-Frage
bei externem Hosting), stattdessen die pragmatische Variante:

  1. Logdatei (instance/logs/app.log, rotierend) -- faengt auch die
     bestehenden logger.error(...)-Aufrufe in den Blueprints ein.
  2. Jede unbehandelte Exception landet als Zeile in Fehlerprotokoll
     (Admin-Ansicht /admin/fehler).
  3. Ratenbegrenzte Mail an ADMIN_NOTIFY_EMAIL/MAIL_USERNAME (max. 1 pro
     Fehlerort und Stunde -- verhindert eine Mail-Flut bei einem Dauerfehler).

Einbinden in app.py: from errors import init_errors; init_errors(app)
"""
import logging
import os
import traceback as tb_module
from logging.handlers import RotatingFileHandler

from flask import render_template, request
from flask_mail import Message
from werkzeug.exceptions import HTTPException

from extensions import db, mail
from spam_schutz import ip_erlaubt

logger = logging.getLogger(__name__)


def _logging_einrichten(app):
    logdir = os.path.join(app.instance_path, 'logs')
    os.makedirs(logdir, exist_ok=True)
    handler = RotatingFileHandler(
        os.path.join(logdir, 'app.log'), maxBytes=2_000_000, backupCount=5, encoding='utf-8'
    )
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    handler.setLevel(logging.INFO)
    # An den Root-Logger, damit auch logger.error(...) aus foerderer.py,
    # kollaboration.py, dashboard.py etc. hier ankommt, nicht nur app.logger.
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def _fehler_mail(eintrag):
    admin_email = os.getenv('ADMIN_NOTIFY_EMAIL') or os.getenv('MAIL_USERNAME')
    if not admin_email:
        return
    # ip_erlaubt() ist generisch (Schluessel + Fenster) -- hier zweckentfremdet:
    # ein "Fehlerort" (Typ+Pfad) statt einer IP begrenzt die Mailrate auf
    # max. 1/Stunde je Fehlerort, egal wie oft er in der Zeit auftritt.
    fehlerort = f'{eintrag.fehlertyp}:{eintrag.pfad}'
    if not ip_erlaubt(fehlerort, 'fehler_mail', limit=1, window=3600):
        return
    try:
        msg = Message(
            subject=f'OpenMycoNet — Fehler: {eintrag.fehlertyp} auf {eintrag.pfad}',
            recipients=[admin_email],
        )
        msg.body = (
            f'{eintrag.methode} {eintrag.pfad}\nIP: {eintrag.ip}\n\n'
            f'{eintrag.nachricht}\n\n{eintrag.traceback}'
        )
        mail.send(msg)
    except Exception:
        logger.exception('Fehler-Benachrichtigungsmail konnte nicht gesendet werden')


def _unbehandelte_exception(e):
    """Top-level (statt verschachtelt in init_errors), damit Tests sie direkt
    aufrufen koennen -- Flask ruft registrierte errorhandler unter TESTING=True
    standardmaessig nicht auf (PROPAGATE_EXCEPTIONS), siehe test_errors.py."""
    if isinstance(e, HTTPException):
        return e  # 404/403/400/... unveraendert durchreichen -- kein "Fehler"

    from models import Fehlerprotokoll  # spaeter Import: keine Zirkularitaet beim App-Start

    traceback_text = tb_module.format_exc()
    logger.error('Unbehandelte Exception bei %s %s:\n%s', request.method, request.path, traceback_text)

    try:
        db.session.rollback()  # Session steckt evtl. durch den Fehler in einem kaputten Zustand
        eintrag = Fehlerprotokoll(
            pfad=request.path[:300],
            methode=request.method,
            ip=request.remote_addr,
            fehlertyp=type(e).__name__,
            nachricht=str(e)[:2000],
            traceback=traceback_text,
        )
        db.session.add(eintrag)
        db.session.commit()
        _fehler_mail(eintrag)
    except Exception:
        logger.exception('Fehlerprotokollierung selbst fehlgeschlagen')

    return render_template('fehler_500.html'), 500


def init_errors(app):
    _logging_einrichten(app)
    app.errorhandler(Exception)(_unbehandelte_exception)
