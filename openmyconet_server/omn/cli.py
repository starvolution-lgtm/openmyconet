"""Flask-CLI-Kommandos (`flask <name>`, FLASK_APP=wsgi).

- `mail-queue-drain` -- der Cron-Aufhaenger fuer die Rund-Mail-Queue
  (deploy/mailqueue_drain.sh laeuft das jede Minute mit flock).
- `sandbox-generieren` -- fuellt das Schema sandbox mit den synthetischen
  BioComm-Szenarien (omn/sandbox/). Nur PostgreSQL; versioniert, reproduzierbar.
- `biocomm-einlesen` / `biocomm-verdichten` / `biocomm-testpakete` -- Prototyp
  des Dateneingangs fuer Messknoten-Pakete (omn/eingang/, SD-Import-Weg).
- `biocomm-konflikt` -- offene Konflikte anzeigen bzw. manuell aufloesen.
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
        """Liest Datenpakete (Format v1 *.omb, v0 *.json) aus einer Datei oder einem Ordner ein."""
        from omn.eingang.einlesen import ordner_einlesen
        from omn.eingang.verdichtung import verdichten as verdichten_
        from omn.extensions import db

        try:
            ergebnisse = ordner_einlesen(db.engine, pfad, schema=schema, transport=transport, bridge=bridge)
        except ValueError as e:
            raise click.UsageError(str(e))
        zaehler = Counter(e.status for _, e in ergebnisse)
        for datei, e in ergebnisse:
            if e.status in ('REJECTED', 'CONFLICT', 'WARTET') or e.hinweise:
                click.echo(f'{e.status:9} {datei}: {e.grund}')
            if e.lauf_angelegt:
                click.echo(f'          Messlauf {e.lauf_id} aus LAUF_START angelegt; '
                           f'{len(e.nachverarbeitet)} wartende Anlieferungen nachverarbeitet')
        click.echo(f'{len(ergebnisse)} Dateien: ' + ', '.join(f'{k} {v}' for k, v in sorted(zaehler.items())))
        if verdichten:
            alle = [e for _, e in ergebnisse] + [n for _, e in ergebnisse for n in e.nachverarbeitet]
            laeufe = sorted({e.lauf_id for e in alle if e.lauf_id and e.status == 'ACCEPTED'})
            if laeufe:
                _verdichtung_melden(verdichten_(db.engine, schema, laeufe))

    @app.cli.command('biocomm-verdichten')
    @click.option('--schema', type=click.Choice(['sandbox', 'live']), default='sandbox', show_default=True)
    @click.option('--lauf', 'laeufe', type=int, multiple=True, help='Nur diese acquisition_run.id (mehrfach moeglich).')
    @click.option('--voll', is_flag=True, help='Alle Laeufe ueber den ganzen Zeitraum pruefen (Kontrolle, Reparatur).')
    @click.option('--funkstille-stunden', type=float, default=6, show_default=True,
                  help='Ohne neues Paket so lange -> letzte angefangene Fenster eines Laufs ohne Ende abschliessen.')
    @click.option('--still/--laut', default=False,
                  help='--still (fuer den Zeitgeber): nur ausgeben, wenn etwas berechnet oder uebersprungen wurde.')
    def biocomm_verdichten(schema, laeufe, voll, funkstille_stunden, still):
        """Schreibt Minuten-/Stundenwerte fuer abgeschlossene Zeitraeume. Ohne --lauf nur Laeufe mit Aenderungen."""
        from datetime import timedelta

        from omn.eingang.verdichtung import verdichten as verdichten_
        from omn.extensions import db

        st = verdichten_(db.engine, schema, list(laeufe) or None,
                         funkstille=timedelta(hours=funkstille_stunden), voll=voll)
        if not still or any(st['zeilen'].values()) or st['uebersprungen']:
            _verdichtung_melden(st)

    @app.cli.command('biocomm-konflikt')
    @click.option('--schema', type=click.Choice(['sandbox', 'live']), default='sandbox', show_default=True)
    @click.option('--gewinner', type=int, default=None,
                  help='origin_batch.id des Kandidaten, der CANONICAL werden soll. Ohne: offene Konflikte auflisten.')
    @click.option('--von', 'bearbeitet_von', default=None, help='Wer entscheidet (Pflicht mit --gewinner).')
    @click.option('--grund', 'begruendung', default=None, help='Begruendung (Pflicht mit --gewinner).')
    @click.option('--verdichten', is_flag=True, help='Danach den Messlauf neu verdichten.')
    def biocomm_konflikt(schema, gewinner, bearbeitet_von, begruendung, verdichten):
        """Konflikte (8.1.2): auflisten oder einen Kandidaten manuell festlegen (MANUAL_REVIEW, protokolliert)."""
        from omn.eingang.einlesen import kandidat_festlegen, offene_konflikte
        from omn.eingang.verdichtung import verdichten as verdichten_
        from omn.extensions import db

        if gewinner is None:
            zeilen = offene_konflikte(db.engine, schema)
            if not zeilen:
                click.echo('Keine offenen Konflikte.')
            for z in zeilen:
                click.echo(f'Lauf {z["lauf"]} Sequenz {z["sequenz"]}: Batch {z["batch"]} (angelegt {z["angelegt"]:%Y-%m-%d %H:%M},'
                           f' {z["anlieferungen"]} Anlieferungen, Verweise von Nachfolgern: {z["nachfolger_verweise"]})')
            return
        if not bearbeitet_von or not begruendung:
            raise click.UsageError('--von und --grund sind Pflicht')
        try:
            erg = kandidat_festlegen(db.engine, gewinner, bearbeitet_von, begruendung, schema=schema)
        except ValueError as e:
            raise click.ClickException(str(e))
        click.echo(f'Batch {gewinner} ist CANONICAL (Lauf {erg["lauf_id"]}, Sequenz {erg["sequenz"]}), protokolliert.')
        if erg['weitere_aufgeloest']:
            click.echo(f'Per Kettenbeweis zusaetzlich aufgeloest: {erg["weitere_aufgeloest"]}')
        if verdichten:
            _verdichtung_melden(verdichten_(db.engine, schema, [erg['lauf_id']]))

    @app.cli.command('biocomm-testpakete')
    @click.argument('ordner', type=click.Path(file_okay=False))
    @click.option('--name', required=True, help='Kennung des Test-Messknotens (SBX-NODE-EINGANG-<name>).')
    @click.option('--anzahl', type=int, default=10, show_default=True, help='Zahl der Pakete.')
    @click.option('--paket-sekunden', type=int, default=60, show_default=True)
    @click.option('--format', 'paketformat', type=click.Choice(['v1', 'v0']), default='v1', show_default=True,
                  help='v1 = Binaerformat der Firmware (*.omb), v0 = JSON des Prototyps (*.json).')
    def biocomm_testpakete(ordner, name, anzahl, paket_sekunden, paketformat):
        """Legt einen Test-Messknoten in sandbox an und schreibt seine Pakete als Dateien (wie eine SD-Karte)."""
        from pathlib import Path

        from omn.eingang.formate import paket_schreiben
        from omn.eingang.testknoten import knoten_anlegen
        from omn.extensions import db

        ziel = Path(ordner)
        ziel.mkdir(parents=True, exist_ok=True)
        k = knoten_anlegen(db.engine, name, paket_s=paket_sekunden, format=paketformat)
        endung = 'omb' if paketformat == 'v1' else 'json'
        for p in k.pakete(anzahl):
            (ziel / f'{k.lauf}_{p.sequenz:08d}.{endung}').write_bytes(paket_schreiben(p))
        click.echo(f'{anzahl} Pakete von {k.geraet} (Lauf {k.lauf}, id {k.lauf_id}) nach {ziel}')

    @app.cli.command('biocomm-geraet')
    @click.argument('seriennummer')
    @click.option('--rolle', type=click.Choice(['NODE', 'BRIDGE']), default='NODE', show_default=True)
    @click.option('--notiz', default=None)
    @click.option('--schema', type=click.Choice(['sandbox', 'live']), default='live', show_default=True)
    def biocomm_geraet(seriennummer, rolle, notiz, schema):
        """Registriert einen Messknoten oder eine Bridge (Seriennummer wie in der Firmware)."""
        from omn.eingang.verwaltung import geraet_anlegen
        from omn.extensions import db

        try:
            geraet_anlegen(db.engine, schema, seriennummer, rolle, notiz)
        except ValueError as e:
            raise click.ClickException(str(e))
        click.echo(f'{rolle} {seriennummer} in {schema} registriert.')

    @app.cli.command('biocomm-standort')
    @click.argument('code')
    @click.option('--breite', required=True, help='Breitengrad (WGS84), z. B. 50.64 -- wird nur fuer das Rasterfeld genutzt.')
    @click.option('--laenge', required=True, help='Laengengrad (WGS84), z. B. 9.05.')
    @click.option('--zeitzone', required=True, help='IANA-Zeitzone, z. B. Europe/Berlin.')
    @click.option('--hoehe', default=None, help='Hoehe in Metern (wird auf 10 m gerundet).')
    @click.option('--schema', type=click.Choice(['sandbox', 'live']), default='live', show_default=True)
    def biocomm_standort(code, breite, laenge, zeitzone, hoehe, schema):
        """Legt einen Standort an. Gespeichert wird nur das 10-km-Rasterfeld, nicht die Koordinaten."""
        from omn.eingang.verwaltung import standort_anlegen
        from omn.extensions import db

        try:
            zelle = standort_anlegen(db.engine, schema, code, breite, laenge, zeitzone, hoehe)
        except ValueError as e:
            raise click.ClickException(str(e))
        click.echo(f'Standort {code} ({schema}) angelegt: Rasterfeld {zelle}, Zeitzone {zeitzone}.'
                   ' Die Koordinaten wurden nicht gespeichert.')

    @app.cli.command('biocomm-reihe')
    @click.argument('code')
    @click.option('--standort', 'site_code', required=True)
    @click.option('--substrat', required=True, help='SOIL, WOOD_CHIPS, COMPOST, STRAW, AQUATIC oder OTHER.')
    @click.option('--titel', required=True)
    @click.option('--kontext', default=None, help='Versuchskontext (frei).')
    @click.option('--schema', type=click.Choice(['sandbox', 'live']), default='live', show_default=True)
    def biocomm_reihe(code, site_code, substrat, titel, kontext, schema):
        """Legt eine Messreihe an einem Standort an (danach flask biocomm-einsatz)."""
        from omn.eingang.verwaltung import reihe_anlegen
        from omn.extensions import db

        try:
            reihe_anlegen(db.engine, schema, code, site_code, substrat, titel, kontext=kontext)
        except ValueError as e:
            raise click.ClickException(str(e))
        click.echo(f'Messreihe {code} ({schema}) am Standort {site_code} angelegt.')

    @app.cli.command('biocomm-einsatz')
    @click.option('--geraet', 'seriennummer', required=True, help='Seriennummer des Messknotens.')
    @click.option('--serie', 'series_code', required=True, help='series_code der Messreihe.')
    @click.option('--ab', 'ab_text', default=None,
                  help='Beginn des Einsatzes, ISO 8601 mit Zeitzone (Standard: jetzt). Ein offener frueherer'
                       ' Einsatz endet dann.')
    @click.option('--schema', type=click.Choice(['sandbox', 'live']), default='live', show_default=True)
    def biocomm_einsatz(seriennummer, series_code, ab_text, schema):
        """Ordnet einen Messknoten ab einem Zeitpunkt einer Messreihe zu; danach werden wartende Pakete verarbeitet."""
        from datetime import datetime, timezone

        from omn.eingang.verwaltung import einsatz_setzen
        from omn.extensions import db

        ab = datetime.fromisoformat(ab_text) if ab_text else datetime.now(timezone.utc)
        if ab.tzinfo is None:
            raise click.UsageError('--ab braucht eine Zeitzone, z. B. 2026-10-01T08:00:00+02:00')
        try:
            ergebnis = einsatz_setzen(db.engine, schema, seriennummer, series_code, ab)
        except ValueError as e:
            raise click.ClickException(str(e))
        click.echo(f'{seriennummer} misst ab {ab.isoformat()} fuer {series_code}.')
        _wartende_melden(ergebnis)

    @app.cli.command('biocomm-schluessel')
    @click.argument('seriennummer')
    @click.option('--bezeichnung', default=None, help='Notiz zum Schluessel, z. B. "Bridge Garten, Okt. 2026".')
    @click.option('--liste', is_flag=True, help='Schluessel des Geraets anzeigen (ohne den Schluessel selbst).')
    @click.option('--widerrufen', 'widerrufen_id', type=int, default=None, help='Schluessel mit dieser Nummer sperren.')
    @click.option('--schema', type=click.Choice(['sandbox', 'live']), default='live', show_default=True)
    def biocomm_schluessel(seriennummer, bezeichnung, liste, widerrufen_id, schema):
        """Zugangsschluessel fuer den Empfangsweg einer Bridge anlegen, anzeigen oder widerrufen."""
        from omn.eingang.empfang import schluessel_anlegen, schluessel_liste, schluessel_widerrufen
        from omn.extensions import db

        if liste:
            zeilen = schluessel_liste(db.engine, schema, seriennummer)
            if not zeilen:
                click.echo('Keine Schluessel.')
            for z in zeilen:
                stand = f'widerrufen {z.revoked_at:%Y-%m-%d %H:%M}' if z.revoked_at else 'aktiv'
                zuletzt = f'{z.last_used_at:%Y-%m-%d %H:%M}' if z.last_used_at else 'nie'
                click.echo(f'Nr. {z.id}: {stand}, angelegt {z.created_at:%Y-%m-%d %H:%M}, zuletzt genutzt {zuletzt}'
                           + (f' ({z.label})' if z.label else ''))
            return
        if widerrufen_id is not None:
            if not schluessel_widerrufen(db.engine, schema, seriennummer, widerrufen_id):
                raise click.ClickException('Schluessel nicht gefunden oder schon widerrufen')
            click.echo(f'Schluessel Nr. {widerrufen_id} von {seriennummer} ist widerrufen.')
            return
        try:
            kid, schluessel = schluessel_anlegen(db.engine, schema, seriennummer, bezeichnung)
        except ValueError as e:
            raise click.ClickException(str(e))
        click.echo(f'Neuer Schluessel Nr. {kid} fuer {seriennummer} ({schema}):')
        click.echo('')
        click.echo(f'    {schluessel}')
        click.echo('')
        click.echo('Er wird NUR JETZT angezeigt und steht nirgends auf dem Server (nur sein Fingerabdruck).')
        click.echo('In die Bridge eintragen und sicher aufbewahren; bei Verlust widerrufen und neu anlegen.')

    @app.cli.command('biocomm-lage')
    @click.option('--schema', type=click.Choice(['sandbox', 'live']), default='live', show_default=True)
    @click.option('--json', 'als_json', is_flag=True, help='Maschinenlesbar (fuer das MCC).')
    def biocomm_lage(schema, als_json):
        """Lagebericht des Datenwegs: Anlieferungen 24 h, wartend, Konflikte, letzte Verdichtung (nur lesend)."""
        import json

        from omn.eingang.lage import lage
        from omn.extensions import db

        if db.engine.dialect.name != 'postgresql':
            raise click.ClickException('BioComm gibt es nur auf PostgreSQL')
        erg = lage(db.engine, schema)
        if als_json:
            click.echo(json.dumps(erg, ensure_ascii=False))
            return
        st = ', '.join(f'{k} {v}' for k, v in sorted(erg['status_24h'].items())) or 'keine'
        click.echo(f"Schema {erg['schema']}: {erg['anlieferungen_24h']} Anlieferungen in 24 h ({st})")
        click.echo(f"  wartend {erg['wartend']} · offene Konflikte {erg['konflikte_offen']}"
                   f" · letzte Anlieferung {erg['letzte_anlieferung'] or '–'}"
                   f" · letzte Verdichtung {erg['letzte_verdichtung'] or '–'}")
        click.echo(f"  Messknoten {erg['knoten']} · Bridges {erg['bridges']} · laufende Messlaeufe"
                   f" {erg['laeufe_offen']} · Signaturschluessel {erg['signaturschluessel']}")

    @app.cli.command('dashboard-anmeldelink')
    @click.argument('email')
    @click.option('--weiter', default=None, help='Seite nach dem Login, z. B. /dashboard/datenlabor.')
    def dashboard_anmeldelink(email, weiter):
        """Einmaligen Login-Link fuers Nutzer-Dashboard ausgeben (ohne Mail).

        Fuer den Direktzugang aus dem lokalen MCC: der Aufruf braucht den
        SSH-Zugang zum Server. Nur bestaetigte Nutzer; gibt NUR den Link aus."""
        from omn.dashboard import LINK_GUELTIG_MINUTEN, anmeldelink_erzeugen
        from omn.models import Nutzer

        nutzer = Nutzer.query.filter(Nutzer.email == email.strip().lower(), Nutzer.bestaetigt.is_(True)).first()
        if nutzer is None:
            raise click.ClickException('Kein bestaetigter Nutzer mit dieser E-Mail-Adresse.')
        click.echo(anmeldelink_erzeugen(nutzer, weiter))
        click.echo(f'(einmal nutzbar, {LINK_GUELTIG_MINUTEN} Minuten gueltig)', err=True)

    @app.cli.command('biocomm-knotenschluessel')
    @click.argument('seriennummer')
    @click.option('--ed25519', 'public_key', default=None,
                  help='Oeffentlicher Schluessel des Messknotens (64 Hex-Zeichen, gibt die Firmware per USB aus).')
    @click.option('--bezeichnung', default=None, help='Notiz, z. B. "Platine 3, Okt. 2026".')
    @click.option('--liste', is_flag=True, help='Schluessel des Messknotens anzeigen.')
    @click.option('--widerrufen', 'widerrufen_id', type=int, default=None, help='Schluessel mit dieser Nummer sperren.')
    @click.option('--schema', type=click.Choice(['sandbox', 'live']), default='live', show_default=True)
    def biocomm_knotenschluessel(seriennummer, public_key, bezeichnung, liste, widerrufen_id, schema):
        """Signaturschluessel (Ed25519) eines Messknotens registrieren, anzeigen oder widerrufen."""
        from omn.eingang.signatur import schluessel_liste, schluessel_registrieren, schluessel_widerrufen
        from omn.extensions import db

        if liste:
            zeilen = schluessel_liste(db.engine, schema, seriennummer)
            if not zeilen:
                click.echo('Keine Signaturschluessel.')
            for z in zeilen:
                stand = f'widerrufen {z.revoked_at:%Y-%m-%d %H:%M}' if z.revoked_at else 'aktiv'
                click.echo(f'Nr. {z.id}: {stand}, angelegt {z.created_at:%Y-%m-%d %H:%M}, {z.pakete} signierte Pakete,'
                           f' Schluessel {bytes(z.public_key).hex()}' + (f' ({z.label})' if z.label else ''))
            return
        if widerrufen_id is not None:
            if not schluessel_widerrufen(db.engine, schema, seriennummer, widerrufen_id):
                raise click.ClickException('Schluessel nicht gefunden oder schon widerrufen')
            click.echo(f'Signaturschluessel Nr. {widerrufen_id} von {seriennummer} ist widerrufen.'
                       ' Pakete mit diesem Schluessel werden ab jetzt abgelehnt.')
            return
        if not public_key:
            raise click.UsageError('--ed25519 SCHLUESSEL, --liste oder --widerrufen NR angeben')
        try:
            nr = schluessel_registrieren(db.engine, schema, seriennummer, public_key, bezeichnung)
        except ValueError as e:
            raise click.ClickException(str(e))
        click.echo(f'Signaturschluessel Nr. {nr} fuer {seriennummer} ({schema}) registriert.'
                   ' Ab jetzt nimmt der Eingang von diesem Knoten nur noch damit signierte Pakete an.')

    @app.cli.command('biocomm-wartende')
    @click.option('--schema', type=click.Choice(['sandbox', 'live']), default='live', show_default=True)
    def biocomm_wartende(schema):
        """Zurueckgestellte Pakete (Messlauf fehlte) erneut versuchen und den Stand zeigen."""
        from omn.eingang.einlesen import wartende_erneut
        from omn.extensions import db

        _wartende_melden(wartende_erneut(db.engine, schema))


def _wartende_melden(ergebnis):
    if not ergebnis:
        click.echo('Keine wartenden Pakete.')
    for (geraet, lauf), erg in ergebnis.items():
        if isinstance(erg, str):
            click.echo(f'{geraet} / {lauf}: wartet weiter: {erg}')
        else:
            zaehler = Counter(e.status for e in erg)
            click.echo(f'{geraet} / {lauf}: ' + ', '.join(f'{k} {v}' for k, v in sorted(zaehler.items())))


def _verdichtung_melden(st):
    click.echo(f'Verdichtet: {st["zeilen"]} in {st["laeufe"]} Messlaeufen'
               f' (davon neue Versionen {st["neue_versionen"]}, Grabsteine {st["grabsteine"]})')
    for u in st['uebersprungen']:
        click.echo(f'  uebersprungen: {u}')
