"""BioComm-Datenlabor: geschuetztes Dashboard fuer die Sandbox-Szenarien.

Spezifikation v7, Abschnitt 5: nur fuer registrierte (bestaetigte) Nutzer,
serverseitige Pruefung auf ALLEN Daten-Endpunkten, durchgaengige Kennzeichnung
als Simulation (jede API-Antwort traegt is_simulated: true), fehlende Werte als
Luecke (die API liefert fuer fehlende Zeitfenster schlicht keine Punkte, nie 0).

Routen (Blueprint datenlabor_bp):
  GET /dashboard/datenlabor                  Seite (Login noetig, sonst Redirect)
  GET /dashboard/datenlabor/api/szenarien    Szenarien + Reihen + Filterdaten
  GET /dashboard/datenlabor/api/reihe        Zeitreihe eines Kanals (auto. Aufloesung)
  GET /dashboard/datenlabor/api/roh          Rohdaten-Ausschnitt (max. 30 s)
Die API antwortet ohne Login mit 401 JSON (kein Redirect auf HTML).

Liest nur `sandbox.*` -- nie `live.*`, nie `*_private` (die Web-Rolle omn hat
darauf ohnehin keine Rechte). Rohdaten nur aus kanonischen Batches
(origin_batch.batch_status = 'CANONICAL'; Konfliktkandidaten erscheinen nie),
Aggregate nur in der juengsten Version (Sicht derived_aggregate_current,
Migration biocomm_0002). Auf SQLite (lokal/CI) gibt es die Sandbox nicht:
dann leerer Zustand statt Fehler.

Sprachen (seit 26.09.2026): alle Texte in omn/datenlabor_texte.json (de, en,
nl, fr, es). Sprache der Seite: ?lang= -> Cookie der Website (Flaggen-Wahl) ->
Nutzer.sprache (Registrierung) -> de. Das Skript schickt die Sprache der Seite
als ?lang= an die API mit; diese uebersetzt Szenario-Texte, Namen der
Messgroessen und die festen Texte des Sandbox-Generators. Szenario-Texte nur,
solange der deutsche Text in der Datenbank dem in omn/sandbox/szenarien.py
entspricht -- sonst bleibt es beim deutschen Text (keine veraltete Uebersetzung).
"""
import json
import os
import struct
import zlib
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import text

from omn.extensions import db
from omn.i18n import COOKIE_NAME, LANGS
from omn.models import Nutzer

try:
    from compression import zstd as _zstd
except ImportError:          # Python < 3.14
    _zstd = None

datenlabor_bp = Blueprint('datenlabor', __name__)

MAX_ROH_S = 30
KANAELE = {    # quantity_code -> (Anzeigename, Einheit fuer die Anzeige)
    'bioelectric_potential': ('Bioelektrisches Potential', 'µV'),
    'soil_temperature': ('Bodentemperatur', '°C'),
    'soil_moisture': ('Bodenfeuchte', '%'),
    'electrical_conductivity': ('Elektrische Leitfähigkeit', 'mS/cm'),
    'air_temperature': ('Lufttemperatur', '°C'),
    'relative_humidity': ('Relative Luftfeuchte', '%'),
    'co2': ('CO₂', 'ppm'),
    'battery_voltage': ('Akkuspannung', 'V'),
    'battery_state_of_charge': ('Akku-Ladezustand', '%'),
}
QUALITAET = {1: 'OUT_OF_RANGE', 2: 'SATURATED', 4: 'SENSOR_ERROR', 8: 'TIMING_UNCERTAIN', 16: 'INTERPOLATED'}

with open(os.path.join(os.path.dirname(__file__), 'datenlabor_texte.json'), encoding='utf-8') as _f:
    TEXTE = json.load(_f)


# ---------------------------------------------------------------------------
# Sprache und Texte
# ---------------------------------------------------------------------------
def seiten_sprache(nutzer):
    """?lang= -> Cookie der Website -> Sprache aus der Registrierung -> de."""
    for kandidat in (request.args.get('lang'), request.cookies.get(COOKIE_NAME), getattr(nutzer, 'sprache', None)):
        if kandidat in LANGS:
            return kandidat
    return 'de'


def _api_sprache():
    lang = request.args.get('lang')
    return lang if lang in LANGS else 'de'


def ui_texte(lang):
    """Oberflaechentexte einer Sprache, fehlende Schluessel auf Deutsch."""
    return {**TEXTE['de']['ui'], **TEXTE.get(lang, {}).get('ui', {})}


def kanal_name(kanal, lang):
    return TEXTE.get(lang, {}).get('kanaele', {}).get(kanal) or KANAELE[kanal][0]


def generator_text(text_de, lang):
    """Feste deutsche Texte des Sandbox-Generators (Gruende, Hinweise)."""
    if not text_de:
        return text_de
    return TEXTE.get(lang, {}).get('generator', {}).get(text_de, text_de)


def szenario_texte(key, label, kurz, hinweis, stimulationsparameter, lang):
    """Uebersetzte Szenario-Texte oder die deutschen aus der Datenbank.

    Je Text einzeln: uebersetzt wird nur, wenn der deutsche Text in der
    Datenbank genau dem aktuellen in szenarien.py entspricht. Aendert sich ein
    deutscher Wortlaut, erscheint genau dieser Text wieder auf Deutsch, bis die
    Uebersetzung nachgezogen ist."""
    from omn.sandbox import szenarien as sz
    erg = {'label': label, 'kurz': kurz, 'hinweis': hinweis, 'stimulationsparameter': stimulationsparameter}
    t = TEXTE.get(lang, {}).get('szenarien')
    vorlage = next((x for x in sz.SZENARIEN if x.key == key), None)
    if lang == 'de' or not t or vorlage is None or key not in t['szenarien']:
        return erg
    e = t['szenarien'][key]
    if label == vorlage.label:
        erg['label'] = e['label']
    if kurz == vorlage.kurz:
        erg['kurz'] = e['kurz']
    if hinweis == vorlage.annahme:
        zusatz = t['reaktion_demo'] if e['zusatz'] == '$reaktion_demo' else e['zusatz']
        erg['hinweis'] = t['hinweis_simulation'].format(generator=sz.GENERATOR_VERSION,
                                                        modell=sz.MODELL_VERSION) + ' ' + zusatz
    if stimulationsparameter and stimulationsparameter == vorlage.stim_parameterquelle:
        erg['stimulationsparameter'] = t['parameter_demo']
    return erg


# ---------------------------------------------------------------------------
# Zugang
# ---------------------------------------------------------------------------
def _nutzer():
    if not session.get('nutzer_logged_in'):
        return None
    n = db.session.get(Nutzer, session.get('nutzer_id'))
    return n if n and n.bestaetigt else None


def mycelist_required(api=False):
    """Nur eingeloggte UND bestaetigte Nutzer. Anders als dashboard.login_required
    wird der Nutzer bei jedem Aufruf aus der DB geladen (geloescht/entbestaetigt
    -> kein Zugriff mehr) und die API bekommt 401 JSON statt eines Redirects."""
    def deko(f):
        @wraps(f)
        def innen(*args, **kwargs):
            nutzer = _nutzer()
            if nutzer is None:
                if api:
                    return jsonify({'fehler': 'Anmeldung erforderlich', 'is_simulated': True}), 401
                return redirect(url_for('dashboard.login'))
            return f(nutzer, *args, **kwargs)
        return innen
    return deko


def _sandbox_da():
    if db.engine.dialect.name != 'postgresql':
        return False
    return bool(db.session.execute(text("SELECT to_regclass('sandbox.sandbox_scenario') IS NOT NULL")).scalar())


def _antwort(daten, status=200):
    daten['is_simulated'] = True
    r = jsonify(daten)
    r.status_code = status
    r.headers['Cache-Control'] = 'private, no-store'
    return r


def _zeit(wert, name):
    try:
        t = datetime.fromisoformat(wert.replace('Z', '+00:00'))
    except (AttributeError, ValueError):
        raise ValueError(f'{name}: ungültiger Zeitpunkt')
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Hemisphaere aus dem OEFFENTLICHEN Rasterfeld (MGRS-Breitenband), nie aus
# den privaten Koordinaten. Baender C..M = Sued, N..X = Nord; M/N = Aequatornaehe.
# ---------------------------------------------------------------------------
def _hemisphaere(grid_cell_id):
    band = next((c for c in (grid_cell_id or '') if c.isalpha()), '')
    if not band:
        return None, False
    return ('S' if band.upper() < 'N' else 'N'), band.upper() in ('M', 'N')


# ---------------------------------------------------------------------------
# Seite
# ---------------------------------------------------------------------------
@datenlabor_bp.route('/dashboard/datenlabor')
@mycelist_required()
def seite(nutzer):
    lang = seiten_sprache(nutzer)
    return render_template('datenlabor.html', nutzer=nutzer, kanaele=KANAELE, lang=lang, T=ui_texte(lang),
                           locale=TEXTE[lang]['locale'], sprachen=LANGS)


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@datenlabor_bp.route('/dashboard/datenlabor/api/szenarien')
@mycelist_required(api=True)
def api_szenarien(nutzer):
    if not _sandbox_da():
        return _antwort({'szenarien': []})
    zeilen = db.session.execute(text("""
        WITH aktuell AS (
            SELECT DISTINCT ON (scenario_key) * FROM sandbox.sandbox_scenario
             WHERE is_public ORDER BY scenario_key, scenario_version DESC)
        SELECT sc.id, sc.scenario_key, sc.scenario_version, sc.label, sc.short_description,
               sc.model_assumption_note, sc.parameter_basis, sc.stimulus_parameter_source,
               sc.response_assumption, lower(sc.synthetic_year), upper(sc.synthetic_year),
               ss.series_role, s.id, s.series_code, s.substrate_code, sub.label, st.site_code, st.grid_cell_id,
               (SELECT iana_tz FROM sandbox.site_timezone WHERE site_id = st.id ORDER BY valid_from DESC LIMIT 1),
               lower(s.study_period), upper(s.study_period),
               EXISTS (SELECT 1 FROM sandbox.stimulation x JOIN sandbox.acquisition_run r ON r.id = x.acquisition_run_id
                        WHERE r.series_id = s.id) AS mit_stim,
               ARRAY(SELECT DISTINCT date_trunc('hour', sb.time_anchor)
                       FROM sandbox.sample_block sb
                       JOIN sandbox.origin_batch ob ON ob.id = sb.origin_batch_id AND ob.batch_status = 'CANONICAL'
                       JOIN sandbox.measurement_channel mc ON mc.id = sb.measurement_channel_id
                       JOIN sandbox.acquisition_run r ON r.id = mc.acquisition_run_id
                      WHERE r.series_id = s.id AND mc.quantity_code = 'bioelectric_potential'
                      ORDER BY 1) AS roh_stunden,
               ARRAY(SELECT DISTINCT mc.quantity_code FROM sandbox.measurement_channel mc
                       JOIN sandbox.acquisition_run r ON r.id = mc.acquisition_run_id
                      WHERE r.series_id = s.id AND mc.data_kind = 'DERIVED') AS groessen
          FROM aktuell sc
          JOIN sandbox.sandbox_scenario_series ss ON ss.scenario_id = sc.id
          JOIN sandbox.series s ON s.id = ss.series_id
          JOIN sandbox.site st ON st.id = s.site_id
          JOIN sandbox.substrate sub ON sub.code = s.substrate_code
         ORDER BY sc.id, ss.series_role DESC, s.id
    """)).all()
    lang = _api_sprache()
    szenarien = {}
    for z in zeilen:
        if z[1] not in szenarien:
            szenarien[z[1]] = {
                'key': z[1], 'version': z[2], **szenario_texte(z[1], z[3], z[4], z[5], z[7], lang),
                'parametergrundlage': z[6], 'reaktionsannahme': z[8],
                'jahr_von': z[9].isoformat(), 'jahr_bis': z[10].isoformat(), 'reihen': []}
        sc = szenarien[z[1]]
        hemi, aequator = _hemisphaere(z[17])
        sc['reihen'].append({
            'id': z[12], 'code': z[13], 'rolle': z[11], 'substrat': z[14], 'substrat_label': z[15],
            'standort': z[16], 'rasterzelle': z[17], 'zeitzone': z[18], 'hemisphaere': hemi,
            'aequatornah': aequator, 'von': z[19].isoformat(), 'bis': z[20].isoformat(),
            'mit_stimulation': z[21], 'roh_stunden': [t.isoformat() for t in z[22]],
            'kanaele': [k for k in KANAELE if k in z[23]]})
    return _antwort({'szenarien': list(szenarien.values()), 'kanaele': {k: {'name': kanal_name(k, lang), 'einheit': v[1]}
                                                                         for k, v in KANAELE.items()}})


def _reihe_pruefen(series_id):
    return db.session.execute(text("""
        SELECT s.id, (SELECT iana_tz FROM sandbox.site_timezone WHERE site_id = s.site_id ORDER BY valid_from DESC LIMIT 1)
          FROM sandbox.series s JOIN sandbox.sandbox_scenario_series ss ON ss.series_id = s.id
          JOIN sandbox.sandbox_scenario sc ON sc.id = ss.scenario_id AND sc.is_public
         WHERE s.id = :s"""), {'s': series_id}).first()


@datenlabor_bp.route('/dashboard/datenlabor/api/reihe')
@mycelist_required(api=True)
def api_reihe(nutzer):
    if not _sandbox_da():
        return _antwort({'punkte': []})
    try:
        series_id = int(request.args.get('reihe', ''))
        kanal = request.args.get('kanal', 'bioelectric_potential')
        von, bis = _zeit(request.args.get('von'), 'von'), _zeit(request.args.get('bis'), 'bis')
    except ValueError as e:
        return _antwort({'fehler': str(e) or 'Parameter ungültig'}, 400)
    if kanal not in KANAELE or not von < bis or bis - von > timedelta(days=370):
        return _antwort({'fehler': 'kanal oder Zeitraum ungültig'}, 400)
    reihe = _reihe_pruefen(series_id)
    if reihe is None:
        return _antwort({'fehler': 'unbekannte Reihe'}, 404)
    tz = reihe[1] or 'UTC'
    spanne = bis - von
    p = {'s': series_id, 'q': kanal, 'von': von, 'bis': bis, 'tz': tz}
    basis = """FROM sandbox.derived_aggregate_current a
               JOIN sandbox.measurement_channel mc ON mc.id = a.measurement_channel_id
               JOIN sandbox.acquisition_run r ON r.id = mc.acquisition_run_id
              WHERE r.series_id = :s AND mc.quantity_code = :q AND mc.data_kind = 'DERIVED'
                AND a.bucket_start >= :von AND a.bucket_start < :bis"""
    aufloesung = '1h'
    if spanne <= timedelta(hours=48):
        n_min = db.session.execute(text(f"SELECT count(*) {basis} AND a.resolution = '1min'"), p).scalar()
        if n_min:
            aufloesung = '1min'
    if spanne > timedelta(days=45):
        aufloesung = '1d'
        sql = f"""SELECT date_trunc('day', a.bucket_start, :tz) AS t, min(a.value_min), max(a.value_max),
                         sum(a.value_mean * a.samples_recorded) / sum(a.samples_recorded),
                         bit_or(a.quality_mask), sum(a.samples_recorded), sum(a.samples_expected)
                  {basis} AND a.resolution = '1h' GROUP BY 1 ORDER BY 1"""
    else:
        sql = f"""SELECT a.bucket_start, a.value_min, a.value_max, a.value_mean, a.quality_mask,
                         a.samples_recorded, a.samples_expected
                  {basis} AND a.resolution = :res ORDER BY 1"""
        p['res'] = aufloesung
    punkte = [[int(z[0].timestamp() * 1000), round(z[1], 4), round(z[2], 4), round(z[3], 4), z[4], z[5], z[6]]
              for z in db.session.execute(text(sql), p).all()]

    stim = db.session.execute(text("""
        SELECT x.actuator_type, x.execution_state, x.planned_start, x.actual_start, x.actual_duration_ms,
               x.attempted_at, x.state_reason, m.planned_offset_ms
          FROM sandbox.stimulation x JOIN sandbox.acquisition_run r ON r.id = x.acquisition_run_id
          LEFT JOIN sandbox.stimulation_sequence_member m ON m.stimulation_id = x.id
         WHERE r.series_id = :s AND x.planned_start >= :von - interval '1 hour' AND x.planned_start < :bis
         ORDER BY x.planned_start"""), p).all() if kanal == 'bioelectric_potential' else []
    qual = db.session.execute(text("""
        SELECT qa.quality_code, qa.origin, lower(qa.time_range), upper(qa.time_range), qa.note
          FROM sandbox.quality_annotation qa JOIN sandbox.measurement_channel mc ON mc.id = qa.measurement_channel_id
          JOIN sandbox.acquisition_run r ON r.id = mc.acquisition_run_id
         WHERE r.series_id = :s AND mc.quantity_code = :q AND qa.action = 'ASSERT'
           AND qa.time_range && tstzrange(:von, :bis)
           AND NOT EXISTS (SELECT 1 FROM sandbox.quality_annotation w WHERE w.supersedes_annotation_id = qa.id)"""), p).all()
    ms = lambda t: None if t is None else int(t.timestamp() * 1000)
    lang = _api_sprache()
    return _antwort({
        'reihe': series_id, 'kanal': kanal, 'name': kanal_name(kanal, lang), 'einheit': KANAELE[kanal][1],
        'aufloesung': aufloesung, 'zeitzone': tz,
        'felder': ['t_ms', 'min', 'max', 'mittel', 'qualitaet_maske', 'samples', 'samples_erwartet'],
        'punkte': punkte,
        'stimulationen': [{'typ': z[0], 'zustand': z[1], 'geplant': ms(z[2]), 'start': ms(z[3]),
                           'dauer_ms': z[4], 'versuch': ms(z[5]), 'grund': generator_text(z[6], lang),
                           'versatz_ms': z[7]} for z in stim],
        'qualitaet': [{'code': z[0], 'herkunft': z[1], 'von': ms(z[2]), 'bis': ms(z[3]),
                       'hinweis': generator_text(z[4], lang)} for z in qual],
        'qualitaet_bits': QUALITAET,
    })


def _entpacken(payload, kompression):
    if kompression == 'none':
        return payload
    if kompression.startswith('zlib'):
        return zlib.decompress(payload)
    if kompression.startswith('zstd'):
        if _zstd is None:
            raise RuntimeError('zstd auf diesem Python nicht verfügbar')
        return _zstd.decompress(payload)
    raise RuntimeError(f'unbekannte Kompression {kompression}')


@datenlabor_bp.route('/dashboard/datenlabor/api/roh')
@mycelist_required(api=True)
def api_roh(nutzer):
    if not _sandbox_da():
        return _antwort({'samples': []})
    try:
        series_id = int(request.args.get('reihe', ''))
        von = _zeit(request.args.get('von'), 'von')
        dauer = float(request.args.get('dauer', '10'))
    except ValueError as e:
        return _antwort({'fehler': str(e) or 'Parameter ungültig'}, 400)
    if not 0 < dauer <= MAX_ROH_S:
        return _antwort({'fehler': f'dauer: 0 bis {MAX_ROH_S} s'}, 400)
    if _reihe_pruefen(series_id) is None:
        return _antwort({'fehler': 'unbekannte Reihe'}, 404)
    bis = von + timedelta(seconds=dauer)
    bloecke = db.session.execute(text("""
        SELECT sb.time_anchor, sb.sample_rate_hz, sb.sample_count, sb.first_sample_index, sb.value_encoding,
               sb.compression, sb.payload_inline, mc.gain, mc.calibration, mc.gain_source
          FROM sandbox.sample_block sb
          JOIN sandbox.origin_batch ob ON ob.id = sb.origin_batch_id AND ob.batch_status = 'CANONICAL'
          JOIN sandbox.measurement_channel mc ON mc.id = sb.measurement_channel_id
          JOIN sandbox.acquisition_run r ON r.id = mc.acquisition_run_id
         WHERE r.series_id = :s AND mc.quantity_code = 'bioelectric_potential' AND mc.data_kind = 'RAW'
           AND sb.time_anchor < :bis
           AND sb.time_anchor + make_interval(secs => (sb.sample_count / sb.sample_rate_hz)::float8) > :von
         ORDER BY sb.time_anchor"""), {'s': series_id, 'von': von, 'bis': bis}).all()
    samples, quelle = [], {}
    for anker, rate, n, erster, enc, komp, payload, gain, kalib, gain_quelle in bloecke:
        if enc != 'int16le' or not kalib or 'lsb_uv' not in kalib or not gain:
            continue
        werte = struct.unpack(f'<{n}h', _entpacken(bytes(payload), komp))
        faktor = float(kalib['lsb_uv']) / float(gain)
        quelle = {'kodierung': enc, 'kompression': komp, 'adc': kalib.get('adc'),
                  'lsb_uv': float(kalib['lsb_uv']), 'gain': float(gain), 'gain_quelle': gain_quelle}
        rate = float(rate)
        a = max(0, int((von - anker).total_seconds() * rate))
        b = min(n, int((bis - anker).total_seconds() * rate) + 1)
        t0 = anker.timestamp() * 1000
        for i in range(a, b):
            samples.append([round(t0 + i * 1000 / rate, 1), round(werte[i] * faktor, 3), erster + i,
                            1 if abs(werte[i]) >= 32767 else 0])
    return _antwort({'reihe': series_id, 'einheit': 'µV', 'rate_hz': int(rate) if bloecke else None,
                     'quelle': quelle,
                     'felder': ['t_ms', 'wert', 'sample_index', 'saettigung'], 'samples': samples})
