"""
vorschau.py -- kleine, vorberechnete Tagesdatei fuer das Mini-Dashboard der Startseite.

Liest EINEN simulierten Tag einer oeffentlichen Sandbox-Reihe aus denselben
verdichteten Werten, die auch das Datenlabor zeigt (sandbox.derived_aggregate_current),
und schreibt sie als JSON nach app/static/ (Auftrag Robby, 29.09.2026). Die Startseite
fragt dadurch nie die Datenbank ab, sie laedt nur diese Datei.

- Szenario 'baseline' (keine Stimulation, kein Vergleich Stimulation/Kontrolle)
- bioelektrisches Grundsignal in Minutenwerten, Bodentemperatur und -feuchte in
  Stundenwerten (langsame Kanaele werden nur stuendlich verdichtet)
- versioniert mit Szenario-, Generator- und Modellversion; test_startseite_vorschau.py
  schlaegt an, wenn szenarien.py eine neue Version hat und die Datei noch die alte

Neu erzeugen: flask sandbox-vorschau (nur PostgreSQL mit befuellter Sandbox).
"""
import json
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text

AUSGABE = 'app/static/startseite_vorschau.json'
KANAELE = {   # quantity_code -> (Aufloesung, Nachkommastellen)
    'bioelectric_potential': ('1min', 1),
    'soil_temperature': ('1h', 2),
    'soil_moisture': ('1h', 1),
}


def vorschau_erzeugen(session, szenario='baseline', standort='SBX-DE-01', tag=date(2025, 7, 15)):
    """dict fuer die Tagesdatei. ValueError, wenn Reihe oder Werte fehlen."""
    reihe = session.execute(text("""
        SELECT s.id, s.series_code, st.site_code, st.grid_cell_id, sc.scenario_key, sc.scenario_version,
               sc.generator_version, sc.model_assumption_version,
               (SELECT iana_tz FROM sandbox.site_timezone WHERE site_id = st.id ORDER BY valid_from DESC LIMIT 1)
          FROM sandbox.sandbox_scenario sc
          JOIN sandbox.sandbox_scenario_series ss ON ss.scenario_id = sc.id AND ss.series_role = 'PRIMARY'
          JOIN sandbox.series s ON s.id = ss.series_id
          JOIN sandbox.site st ON st.id = s.site_id
         WHERE sc.scenario_key = :sz AND sc.is_public AND st.site_code = :st
         ORDER BY sc.scenario_version DESC LIMIT 1"""), {'sz': szenario, 'st': standort}).first()
    if reihe is None:
        raise ValueError(f'keine oeffentliche Reihe fuer {szenario}/{standort}')
    tz = ZoneInfo(reihe[8] or 'UTC')
    von = datetime.combine(tag, time(0), tz)
    bis = datetime.combine(tag + timedelta(days=1), time(0), tz)

    kanaele = {}
    for kanal, (aufloesung, stellen) in KANAELE.items():
        zeilen = session.execute(text("""
            SELECT a.bucket_start, a.value_mean, a.samples_recorded, a.samples_expected
              FROM sandbox.derived_aggregate_current a
              JOIN sandbox.measurement_channel mc ON mc.id = a.measurement_channel_id
              JOIN sandbox.acquisition_run r ON r.id = mc.acquisition_run_id
             WHERE r.series_id = :s AND mc.quantity_code = :q AND mc.data_kind = 'DERIVED'
               AND a.resolution = :res AND a.bucket_start >= :von AND a.bucket_start < :bis
             ORDER BY 1"""), {'s': reihe[0], 'q': kanal, 'res': aufloesung, 'von': von, 'bis': bis}).all()
        schritt = 60 if aufloesung == '1min' else 3600
        anzahl = int((bis - von).total_seconds() // schritt)
        werte = [None] * anzahl
        erfasst = erwartet = 0
        for t, mittel, rec, exp in zeilen:
            i = int((t - von).total_seconds() // schritt)
            if 0 <= i < anzahl and mittel is not None and rec:
                werte[i] = round(float(mittel), stellen)
            erfasst += rec or 0
            erwartet += exp or 0
        if not any(v is not None for v in werte):
            raise ValueError(f'keine {aufloesung}-Werte fuer {kanal} am {tag}')
        kanaele[kanal] = {
            'aufloesung': aufloesung,
            'mittel': werte,
            # Anteil tatsaechlich aufgezeichneter Abtastwerte (z. B. stuendliche EC-Pause)
            'abdeckung': round(erfasst / erwartet, 4) if erwartet else None,
        }

    return {
        '_hinweis': 'SIMULATION: berechnete Messwerte aus dem BioComm-Sandkasten (frei gewaehlte '
                    'Demo-Annahmen), keine echte Messung. Erzeugt mit flask sandbox-vorschau.',
        'is_simulated': True,
        'szenario': reihe[4],
        'szenario_version': reihe[5],
        'generator_version': reihe[6],
        'modell_version': reihe[7],
        'reihe': reihe[1],
        'standort': reihe[2],
        'rasterzelle': reihe[3],
        'zeitzone': str(tz),
        'tag': tag.isoformat(),
        'quelle': 'sandbox.derived_aggregate_current',
        'kanaele': kanaele,
    }


def schreiben(daten, pfad=AUSGABE):
    with open(pfad, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(daten, f, ensure_ascii=False, separators=(',', ':'))
        f.write('\n')
