"""Hintergrund-Versand fuer Rund-Mails (Newsletter, News-Benachrichtigung).

Die Nachrichten werden im Request gebaut (dort funktioniert
`url_for(..., _external=True)` ueber den Host-Header), der langsame Teil --
die SMTP-Runden -- laeuft danach in einem Daemon-Thread mit EINER
wiederverwendeten Verbindung. Der Request kehrt sofort zurueck.

Bewusst KEINE echte Queue: bei einem gunicorn-Neustart mitten im Versand geht
der Rest des Batches verloren. Bei der aktuellen Nutzerzahl ist ein Batch im
Sekundenbereich -- akzeptabel. TODO: DB-Queue oder Redis, wenn die Nutzerzahl
in die Tausende geht (dann kommt Redis ohnehin mit anderen Themen).
"""
import threading

from flask import current_app

from omn.extensions import mail


def _sende(app, nachrichten):
    with app.app_context():
        ok = 0
        try:
            with mail.connect() as conn:
                for msg in nachrichten:
                    try:
                        conn.send(msg)
                        ok += 1
                    except Exception:
                        app.logger.exception('Rund-Mail an %s fehlgeschlagen', msg.recipients)
        except Exception:
            app.logger.exception('Rund-Mail-Batch: SMTP-Verbindung fehlgeschlagen')
        app.logger.info('Rund-Mail-Batch fertig: %d/%d gesendet', ok, len(nachrichten))


def versende_im_hintergrund(nachrichten):
    """`nachrichten`: fertige Liste[flask_mail.Message]. Startet den Versand im
    Hintergrund und kehrt sofort zurueck. Unter TESTING synchron (damit
    `mail.record_messages()` deterministisch bleibt)."""
    nachrichten = list(nachrichten)
    if not nachrichten:
        return
    app = current_app._get_current_object()
    if app.config.get('TESTING'):
        _sende(app, nachrichten)
        return
    threading.Thread(
        target=_sende, args=(app, nachrichten), name='mail-batch', daemon=True
    ).start()
