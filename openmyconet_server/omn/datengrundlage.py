"""Datengrundlage des Datenlabors: wie viele Werte TATSAECHLICH gespeichert sind.

Verbindliche Regel (Robby, 30.09.2026): Es werden nur gespeicherte Werte gezaehlt,
nie rechnerisch "vertretene" Einzelwerte. In der Simulation sind die Minuten- und
Stundenwerte direkt erzeugt, nicht aus Rohdaten verdichtet -- "Grundlage: 100
Milliarden Werte" waere deshalb falsch.

Gezaehlt wird je Schema (`sandbox` = Simulation, `live` = echte Messungen, gleiche
Struktur):
  - Rohwerte: Summe `sample_count` der `sample_block`-Zeilen kanonischer Batches
    (`origin_batch.batch_status = 'CANONICAL'`, Konfliktkandidaten zaehlen nie),
    davon bioelektrisch, Abtastrate(n) des bioelektrischen RAW-Kanals;
  - verdichtete Werte: Zeilen der Sicht `derived_aggregate_current` (juengste
    Version, ohne Grabsteine), Minuten- und Stundenwerte;
  - sandbox: nur die Messreihen der oeffentlichen Szenarien (Testknoten des
    Dateneingangs liegen auch in sandbox und zaehlen nicht mit);
  - live: alles Kanonische, zusaetzlich die Zahl der beteiligten Messknoten.

Kein Datenbankzugriff pro Seitenaufruf: `ermitteln()` schreibt das Ergebnis nach
`instance/datengrundlage_<schema>.json` (Befehl `flask datenlabor-grundlage`, auch
am Ende von `flask sandbox-generieren`); `lesen()` liest die Datei (im Prozess
zwischengespeichert, neu gelesen, wenn sich die Datei aendert). Fehlt sie, wird sie
einmal erzeugt. `kurzzahl()` formatiert Zahlen im Stil der Sprache.
"""
import json
import os
from datetime import datetime, timezone

from sqlalchemy import text

SCHEMAS = ('sandbox', 'live')
_ZWISCHENSPEICHER = {}


def _datei(instance_path, schema):
    return os.path.join(instance_path, f'datengrundlage_{schema}.json')


# Welche Laeufe zaehlen: sandbox nur die der oeffentlichen Szenarien (juengste Version
# je Szenario), live alle.
_LAEUFE = {
    'sandbox': """SELECT r.id FROM sandbox.acquisition_run r
                   WHERE r.series_id IN (SELECT ss.series_id FROM sandbox.sandbox_scenario_series ss
                     JOIN (SELECT DISTINCT ON (scenario_key) id FROM sandbox.sandbox_scenario
                            WHERE is_public ORDER BY scenario_key, scenario_version DESC) sc
                       ON sc.id = ss.scenario_id)""",
    'live': 'SELECT id FROM live.acquisition_run',
}
_ROH = """
    SELECT coalesce(sum(sb.sample_count), 0) AS roh,
           coalesce(sum(sb.sample_count) FILTER (WHERE mc.quantity_code = 'bioelectric_potential'), 0) AS bio,
           count(DISTINCT r.device_id) AS knoten
      FROM {s}.sample_block sb
      JOIN {s}.origin_batch ob ON ob.id = sb.origin_batch_id AND ob.batch_status = 'CANONICAL'
      JOIN {s}.measurement_channel mc ON mc.id = sb.measurement_channel_id
      JOIN {s}.acquisition_run r ON r.id = mc.acquisition_run_id
     WHERE r.id IN ({laeufe})"""
_RATEN = """
    SELECT DISTINCT mc.sample_rate_hz FROM {s}.measurement_channel mc
     WHERE mc.data_kind = 'RAW' AND mc.quantity_code = 'bioelectric_potential'
       AND mc.sample_rate_hz IS NOT NULL AND mc.acquisition_run_id IN ({laeufe})
     ORDER BY 1"""
# Rohdatendauer: verschiedene Stunden mit bioelektrischen Rohdaten je Reihe (Median)
_ROH_STUNDEN = """
    SELECT percentile_disc(0.5) WITHIN GROUP (ORDER BY n) FROM (
      SELECT count(DISTINCT date_trunc('hour', sb.time_anchor)) AS n
        FROM {s}.sample_block sb
        JOIN {s}.origin_batch ob ON ob.id = sb.origin_batch_id AND ob.batch_status = 'CANONICAL'
        JOIN {s}.measurement_channel mc ON mc.id = sb.measurement_channel_id
        JOIN {s}.acquisition_run r ON r.id = mc.acquisition_run_id
       WHERE mc.data_kind = 'RAW' AND mc.quantity_code = 'bioelectric_potential' AND r.id IN ({laeufe})
       GROUP BY r.series_id) je_reihe"""
_VERDICHTET = """
    SELECT a.resolution, count(*) AS n FROM {s}.derived_aggregate_current a
      JOIN {s}.measurement_channel mc ON mc.id = a.measurement_channel_id
     WHERE mc.acquisition_run_id IN ({laeufe}) GROUP BY 1"""


def _sql(schema, satz):
    """Setzt Schema und Laufauswahl ein -- beides nur aus den festen Listen oben."""
    if schema not in SCHEMAS:
        raise ValueError(f'Schema {schema!r} nicht erlaubt')
    return text(satz.replace('{laeufe}', _LAEUFE[schema]).replace('{s}', schema))


def zaehlen(engine, schema='sandbox'):
    """Zaehlt die gespeicherten Werte (nur lesend). Liefert ein dict."""
    with engine.connect() as c:
        roh = c.execute(_sql(schema, _ROH)).one()
        raten = [float(z[0]) for z in c.execute(_sql(schema, _RATEN))]
        verdichtet = {z.resolution: z.n for z in c.execute(_sql(schema, _VERDICHTET))}
        roh_stunden = c.execute(_sql(schema, _ROH_STUNDEN)).scalar() or 0
        if schema == 'sandbox':
            s = c.execute(text("""
                WITH sc AS (SELECT DISTINCT ON (scenario_key) * FROM sandbox.sandbox_scenario
                             WHERE is_public ORDER BY scenario_key, scenario_version DESC)
                SELECT count(DISTINCT sc.scenario_key) AS szenarien, count(DISTINCT ss.series_id) AS reihen,
                       count(DISTINCT se.site_id) AS standorte,
                       min(extract(year FROM lower(sc.synthetic_year)))::int AS jahr_von,
                       max(extract(year FROM upper(sc.synthetic_year) - interval '1 second'))::int AS jahr_bis
                  FROM sc JOIN sandbox.sandbox_scenario_series ss ON ss.scenario_id = sc.id
                  JOIN sandbox.series se ON se.id = ss.series_id""")).one()
            rahmen = {'szenarien': s.szenarien, 'reihen': s.reihen, 'standorte': s.standorte,
                      'jahr': str(s.jahr_von) if s.jahr_von == s.jahr_bis else f'{s.jahr_von}–{s.jahr_bis}'}
        else:
            s = c.execute(text("""
                SELECT count(DISTINCT r.series_id) AS reihen, count(DISTINCT se.site_id) AS standorte
                  FROM live.acquisition_run r JOIN live.series se ON se.id = r.series_id""")).one()
            rahmen = {'reihen': s.reihen, 'standorte': s.standorte}
    return {'schema': schema, **rahmen, 'roh': int(roh.roh), 'bio': int(roh.bio), 'raten_hz': raten,
            'knoten': int(roh.knoten), 'verdichtet': sum(verdichtet.values()),
            'verdichtet_je_aufloesung': verdichtet,
            # vier Jahreszeiten; 0 = keine Rohdaten
            'roh_stunden_je_jahreszeit': round(roh_stunden / 4) if roh_stunden else 0,
            'ermittelt': datetime.now(timezone.utc).replace(microsecond=0).isoformat()}


def ermitteln(engine, instance_path, schema='sandbox'):
    """Zaehlt und schreibt die Datei. Liefert das Ergebnis."""
    daten = zaehlen(engine, schema)
    os.makedirs(instance_path, exist_ok=True)
    ziel = _datei(instance_path, schema)
    with open(ziel + '.neu', 'w', encoding='utf-8') as f:
        json.dump(daten, f, ensure_ascii=False, indent=1)
    os.replace(ziel + '.neu', ziel)
    return daten


def lesen(engine, instance_path, schema='sandbox'):
    """Gespeicherte Datengrundlage oder None (keine PostgreSQL-Sandbox). Fehlt die
    Datei, wird sie einmal erzeugt; danach keine Datenbankabfrage mehr."""
    ziel = _datei(instance_path, schema)
    try:
        stempel = os.path.getmtime(ziel)
    except OSError:
        if engine.dialect.name != 'postgresql' or _ZWISCHENSPEICHER.get(ziel) == (None, None):
            return None
        try:
            return ermitteln(engine, instance_path, schema)
        except Exception:
            # z. B. Sandbox nicht eingerichtet: Kasten entfaellt, nicht bei jedem Aufruf neu versuchen
            _ZWISCHENSPEICHER[ziel] = (None, None)
            return None
    zwischen = _ZWISCHENSPEICHER.get(ziel)
    if zwischen and zwischen[0] == stempel:
        return zwischen[1]
    with open(ziel, encoding='utf-8') as f:
        daten = json.load(f)
    _ZWISCHENSPEICHER[ziel] = (stempel, daten)
    return daten


# ---------------------------------------------------------------------------
# Zahlen im Stil der Sprache
# ---------------------------------------------------------------------------
_TRENNER = {'de': ('.', ','), 'en': (',', '.'), 'nl': ('.', ','), 'fr': (' ', ','), 'es': ('.', ',')}
_GROSS = {   # (Millionen Einzahl, Mehrzahl), (Milliarden Einzahl, Mehrzahl)
    'de': (('Mio.', 'Mio.'), ('Mrd.', 'Mrd.')),
    'en': (('million', 'million'), ('billion', 'billion')),
    'nl': (('miljoen', 'miljoen'), ('miljard', 'miljard')),
    'fr': (('million', 'millions'), ('milliard', 'milliards')),
    'es': (('millón', 'millones'), ('mil millones', 'mil millones')),
}


def _ganzzahl(n, tausender):
    return f'{int(n):,}'.replace(',', tausender)


def kurzzahl(n, lang='de', vor_nomen=False):
    """51137050 -> '51,1 Mio.' (de) / '51.1 million' (en) / '51,1 millions' (fr);
    unter einer Million die ganze Zahl mit Tausendertrennern. `vor_nomen`: folgt direkt
    ein Hauptwort -> fr/es mit 'de' ('51,1 millions de valeurs')."""
    tausender, komma = _TRENNER.get(lang, _TRENNER['de'])
    woerter = _GROSS.get(lang, _GROSS['de'])
    n = int(n)
    if abs(n) < 1_000_000:
        return _ganzzahl(n, tausender)
    stufe, teiler = (1, 1_000_000_000) if abs(n) >= 1_000_000_000 else (0, 1_000_000)
    wert = n / teiler
    stellen = max(0, 3 - len(str(int(abs(wert)))))           # drei gueltige Ziffern
    text_ = f'{wert:.{stellen}f}'.rstrip('0').rstrip('.') if stellen else f'{wert:.0f}'
    # Mehrzahl: fr erst ab 2 ('1,55 million'), sonst alles ausser genau 1
    einzahl = float(text_) < 2 if lang == 'fr' else float(text_) == 1
    wort = woerter[stufe][0 if einzahl else 1]
    return text_.replace('.', komma) + ' ' + wort + (' de' if vor_nomen and lang in ('fr', 'es') else '')


def rate_text(raten, lang='de'):
    """Abtastrate(n) als Text, z. B. '250' oder '250–256'."""
    if not raten:
        return '–'
    werte = [_ganzzahl(r, _TRENNER.get(lang, _TRENNER['de'])[0]) if float(r).is_integer()
             else str(r).replace('.', _TRENNER.get(lang, _TRENNER['de'])[1]) for r in (min(raten), max(raten))]
    return werte[0] if werte[0] == werte[1] else f'{werte[0]}–{werte[1]}'


def platzhalter(daten, lang='de'):
    """Die Werte fuer die Textbausteine der Erklaerseite in einer Sprache."""
    if not daten:
        return {}
    werte = {'roh': kurzzahl(daten['roh'], lang, vor_nomen=True), 'bio': kurzzahl(daten['bio'], lang),
             'verdichtet': kurzzahl(daten['verdichtet'], lang, vor_nomen=True), 'rate': rate_text(daten.get('raten_hz'), lang),
             'reihen': str(daten.get('reihen', '')), 'standorte': str(daten.get('standorte', '')),
             'knoten': str(daten.get('knoten', ''))}
    if 'szenarien' in daten:
        werte.update(szenarien=str(daten['szenarien']), jahr=str(daten['jahr']))
    werte.update(seitenwerte(daten, lang))
    return werte


_STUNDEN = {'de': ('eine Stunde', '{n} Stunden'), 'en': ('one hour', '{n} hours'), 'nl': ('één uur', '{n} uur'),
            'fr': ('une heure', '{n} heures'), 'es': ('una hora', '{n} horas')}


def dauer_text(stunden, lang='de'):
    """1 -> 'eine Stunde' / 'one hour' …, sonst '2 Stunden'."""
    eins, viele = _STUNDEN.get(lang, _STUNDEN['de'])
    return eins if stunden == 1 else viele.replace('{n}', str(stunden))


def seitenwerte(daten, lang='de'):
    """Abtastrate und Rohdatendauer fuer die festen Texte der Erklaerseite (Liste,
    Punkt 6, Einladung) -- aus der Zaehlung, ohne Zaehlung (lokal, CI) aus der
    Generator-Konfiguration der Sandbox, nie fest im Text."""
    if daten and daten.get('roh') and daten.get('raten_hz') and daten.get('roh_stunden_je_jahreszeit'):
        return {'rate': rate_text(daten['raten_hz'], lang), 'roh_dauer': dauer_text(daten['roh_stunden_je_jahreszeit'], lang)}
    from omn.sandbox.szenarien import RATE_HZ
    return {'rate': rate_text([RATE_HZ], lang), 'roh_dauer': dauer_text(1, lang)}   # je Stichwoche eine Rohdatenstunde
