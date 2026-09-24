"""Flask-CLI-Kommandos (`flask <name>`, FLASK_APP=wsgi).

- `mail-queue-drain` -- der Cron-Aufhaenger fuer die Rund-Mail-Queue
  (deploy/mailqueue_drain.sh laeuft das jede Minute mit flock).
- `sandbox-generieren` -- fuellt das Schema sandbox mit den synthetischen
  BioComm-Szenarien (omn/sandbox/). Nur PostgreSQL; versioniert, reproduzierbar.
- `biocomm-einlesen` / `biocomm-verdichten` / `biocomm-testpakete` -- Prototyp
  des Dateneingangs fuer Messknoten-Pakete (omn/eingang/, SD-Import-Weg).
"""
import time
from collections import Counter

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

    @app.cli.command('biocomm-einlesen')
    @click.argument('pfad', type=click.Path(exists=True))
    @click.option('--schema', type=click.Choice(['sandbox', 'live']), default='sandbox', show_default=True,
                  help='Zielschema. live nur fuer echte Messdaten.')
    @click.option('--transport', type=click.Choice(['SD_IMPORT', 'LORA', 'BLE', 'USB']), default='SD_IMPORT',
                  show_default=True, help='Transportweg der Anlieferung.')
    @click.option('--bridge', default=None, help='Seriennummer der Bridge (nicht bei SD_IMPORT).')
    @click.option('--verdichten', is_flag=True, help='Danach die betroffenen Messlaeufe verdichten.')
    def biocomm_einlesen(pfad, schema, transport, bridge, verdichten):
        """Liest Datenpakete (Format v0, *.json) aus einer Datei oder einem Ordner ein."""
        from omn.eingang.einlesen import ordner_einlesen
        from omn.eingang.verdichtung import verdichten as verdichten_
        from omn.extensions import db

        try:
            ergebnisse = ordner_einlesen(db.engine, pfad, schema=schema, transport=transport, bridge=bridge)
        except ValueError as e:
            raise click.UsageError(str(e))
        zaehler = Counter(e.status for _, e in ergebnisse)
        for datei, e in ergebnisse:
            if e.status in ('REJECTED', 'CONFLICT') or e.hinweise:
                click.echo(f'{e.status:9} {datei}: {e.grund}')
        click.echo(f'{len(ergebnisse)} Dateien: ' + ', '.join(f'{k} {v}' for k, v in sorted(zaehler.items())))
        if verdichten:
            laeufe = sorted({e.lauf_id for _, e in ergebnisse if e.lauf_id and e.status == 'ACCEPTED'})
            if laeufe:
                st = verdichten_(db.engine, schema, laeufe)
                click.echo(f'Verdichtet: {st["zeilen"]} in {st["laeufe"]} Messlaeufen')
                for u in st['uebersprungen']:
                    click.echo(f'  uebersprungen: {u}')

    @app.cli.command('biocomm-verdichten')
    @click.option('--schema', type=click.Choice(['sandbox', 'live']), default='sandbox', show_default=True)
    @click.option('--lauf', 'laeufe', type=int, multiple=True, help='Nur diese acquisition_run.id (mehrfach moeglich).')
    def biocomm_verdichten(schema, laeufe):
        """Schreibt Minuten-/Stundenwerte fuer abgeschlossene Zeitraeume (nur neue Zeilen)."""
        from omn.eingang.verdichtung import verdichten as verdichten_
        from omn.extensions import db

        st = verdichten_(db.engine, schema, list(laeufe) or None)
        click.echo(f'Verdichtet: {st["zeilen"]} in {st["laeufe"]} Messlaeufen')
        for u in st['uebersprungen']:
            click.echo(f'  uebersprungen: {u}')

    @app.cli.command('biocomm-testpakete')
    @click.argument('ordner', type=click.Path(file_okay=False))
    @click.option('--name', required=True, help='Kennung des Test-Messknotens (SBX-NODE-EINGANG-<name>).')
    @click.option('--anzahl', type=int, default=10, show_default=True, help='Zahl der Pakete.')
    @click.option('--paket-sekunden', type=int, default=60, show_default=True)
    def biocomm_testpakete(ordner, name, anzahl, paket_sekunden):
        """Legt einen Test-Messknoten in sandbox an und schreibt seine Pakete als Dateien (wie eine SD-Karte)."""
        from pathlib import Path

        from omn.eingang.format_v0 import paket_schreiben
        from omn.eingang.testknoten import knoten_anlegen
        from omn.extensions import db

        ziel = Path(ordner)
        ziel.mkdir(parents=True, exist_ok=True)
        k = knoten_anlegen(db.engine, name, paket_s=paket_sekunden)
        for p in k.pakete(anzahl):
            (ziel / f'{k.lauf}_{p.sequenz:08d}.json').write_bytes(paket_schreiben(p))
        click.echo(f'{anzahl} Pakete von {k.geraet} (Lauf {k.lauf}, id {k.lauf_id}) nach {ziel}')
