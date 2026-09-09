"""Flask-CLI-Kommandos (`flask <name>`, FLASK_APP=wsgi).

Aktuell nur `mail-queue-drain` -- der Cron-Aufhaenger fuer die Rund-Mail-Queue
(deploy/mailqueue_drain.sh laeuft das jede Minute mit flock).
"""
import click
from flask import current_app


def register_cli(app):
    @app.cli.command('mail-queue-drain')
    @click.option('--limit', default=200, show_default=True,
                  help='Hoechstzahl Zeilen pro Lauf.')
    @click.option('--still/--laut', default=True,
                  help='--still (Default): nur ausgeben, wenn wirklich versendet wurde '
                       '(fuer den Minuten-Cron). --laut: immer.')
    def mail_queue_drain(limit, still):
        """Sendet offene Rund-Mails aus der MailQueue."""
        from omn.mailer import mailqueue_drain

        gesendet = mailqueue_drain(current_app._get_current_object(), limit=limit)
        if gesendet or not still:
            click.echo(f'{gesendet} gesendet')
