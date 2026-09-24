"""Flask-CLI-Kommandos (`flask <name>`, FLASK_APP=wsgi).

- `mail-queue-drain` -- der Cron-Aufhaenger fuer die Rund-Mail-Queue
  (deploy/mailqueue_drain.sh laeuft das jede Minute mit flock).
- `sandbox-generieren` -- fuellt das Schema sandbox mit den synthetischen
  BioComm-Szenarien (omn/sandbox/). Nur PostgreSQL; versioniert, reproduzierbar.
"""
import time

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

    @app.cli.command('sandbox-generieren')
    @click.option('--nur', multiple=True, help='Nur diese Szenario-Keys (mehrfach moeglich).')
    @click.option('--zuruecksetzen', is_flag=True,
                  help='Vorher ALLE generierten Sandbox-Daten leeren (Stammdaten bleiben). Nur sandbox, nie live.')
    @click.option('--tage', type=int, default=None, help='Nur fuer Tests: verkuerzter Zeitraum ab 1. Januar.')
    def sandbox_generieren(nur, zuruecksetzen, tage):
        """Erzeugt die BioComm-Sandbox-Szenarien (bestehende Versionen werden uebersprungen)."""
        from omn.extensions import db
        from omn.sandbox.generator import Generator, Zeitraum
        from omn.sandbox.generator import zuruecksetzen as leeren
        from omn.sandbox.szenarien import SZENARIO_KEYS

        unbekannt = set(nur) - set(SZENARIO_KEYS)
        if unbekannt:
            raise click.BadParameter(f'unbekannt: {sorted(unbekannt)}; moeglich: {", ".join(SZENARIO_KEYS)}')
        if zuruecksetzen:
            leeren(db.engine)
            click.echo('Sandbox-Daten geleert.')
        t0 = time.time()
        Generator(db.engine, Zeitraum(tage=tage) if tage else None, log=click.echo).alle(nur=set(nur) or None)
        click.echo(f'Fertig in {time.time() - t0:.0f} s.')
