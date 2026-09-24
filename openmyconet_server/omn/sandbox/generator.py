"""Schreibt die Sandbox-Szenarien in das Schema `sandbox` (nur PostgreSQL).

- Laeuft als Web-Rolle omn (darf in sandbox.* lesen/einfuegen). Exakte
  Koordinaten schreibt eine eigene Verbindung als omn_geo, das Zuruecksetzen
  (TRUNCATE) eine als omn_owner -- Passwoerter jeweils aus ~/.pgpass, wie bei
  der Migration 3f1b2c4d5e6a. Laeuft der Generator als Superuser (CI), alles
  ueber dieselbe Verbindung.
- Ein Szenario = eine Transaktion. Existiert (key, version) schon, wird es
  uebersprungen (sandbox.* ist wie live.* unveraenderlich; Neuaufbau nur ueber
  zuruecksetzen()).
- Nie `live`: alle Anweisungen nennen `sandbox.` ausdruecklich, und die
  CHECK-Constraints erzwingen das Praefix SBX- nur in sandbox.
"""
import hashlib
import json
import math
import random
import struct
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from psycopg.types.range import Range

from omn.sandbox.modell import SAETTIGUNG_UV, Abdeckung, Bio, Reaktion, Umwelt
from omn.sandbox.szenarien import (
    EC_DAUER_S, EC_EINSCHWING_S, GAIN, GENERATOR_VERSION, JAHR, LSB_UV, MODELL_VERSION, RATE_HZ,
    ROH_STUNDE_LOKAL, STANDORTE, STICHWOCHEN, STIM_DAUER_MS, STIM_MINUTE, STIM_STUNDE, SZENARIEN,
    SZENARIO_VERSION, VERSATZ_MS)

try:                                    # Python >= 3.14 (Server)
    from compression import zstd as _zstd

    def _komprimieren(b):
        return _zstd.compress(b, level=3), 'zstd-3'
except ImportError:                     # Python < 3.14 (z. B. lokale Alt-venv)
    import zlib

    def _komprimieren(b):
        return zlib.compress(b, 6), 'zlib-6'

GENESIS = b'\x00' * 32                  # vorlaeufiger Genesis-Wert der Hash-Kette (C4 offen)
QBIT = {'OUT_OF_RANGE': 1, 'SATURATED': 2, 'SENSOR_ERROR': 4, 'TIMING_UNCERTAIN': 8, 'INTERPOLATED': 16}

# Umwelt-/SYSTEM-Kanaele: (Groesse, Rolle, Einheit, Intervall s, Hardwarekanal, Rauschen)
UMWELT_KANAELE = (
    ('soil_temperature', 'ENVIRONMENTAL', 'Cel', 600, 'DS18B20 Bodentemperatur', 0.03),
    ('soil_moisture', 'ENVIRONMENTAL', '%', 600, 'U14/AIN0 Bodenfeuchte', 0.15),
    ('electrical_conductivity', 'ENVIRONMENTAL', 'mS/cm', 3600, 'EC-Messschaltung (U8/AIN0 umgeschaltet)', 0.004),
    ('air_temperature', 'ENVIRONMENTAL', 'Cel', 600, 'SCD41', 0.05),
    ('relative_humidity', 'ENVIRONMENTAL', '%', 600, 'SCD41', 0.4),
    ('co2', 'ENVIRONMENTAL', '[ppm]', 600, 'SCD41', 4.0),
    ('battery_voltage', 'SYSTEM', 'V', 600, 'MAX17048', 0.002),
    ('battery_state_of_charge', 'SYSTEM', '%', 600, 'MAX17048', 0.05),
)


def _sha(b):
    return hashlib.sha256(b).digest()


# ---------------------------------------------------------------------------
# Verbindungen je Rolle
# ---------------------------------------------------------------------------
def _rollen_info(conn):
    return conn.execute(sa.text(
        "SELECT current_user, (SELECT rolsuper FROM pg_roles WHERE rolname = current_user),"
        " array(SELECT rolname FROM pg_roles WHERE rolname IN ('omn_owner', 'omn_geo'))")).one()


def _rollen_engine(engine, rolle):
    """Engine, die als `rolle` verbindet -- oder None, wenn die aktuelle
    Verbindung das schon darf (Superuser, dieselbe Rolle oder Rolle fehlt)."""
    with engine.connect() as c:
        nutzer, ist_super, vorhanden = _rollen_info(c)
    if ist_super or nutzer == rolle or rolle not in vorhanden:
        return None
    u = engine.url
    return sa.create_engine(sa.engine.URL.create(
        drivername=u.drivername, username=rolle, password=None,
        host=u.host, port=u.port, database=u.database, query=u.query))


def zuruecksetzen(engine):
    """Leert alle generierten Sandbox-Daten (Stammdaten bleiben). Nur sandbox!"""
    sql = ('TRUNCATE sandbox.sandbox_scenario, sandbox.site, sandbox.device, sandbox.probe,'
           ' sandbox_private.site_location_private RESTART IDENTITY CASCADE')
    owner = _rollen_engine(engine, 'omn_owner')
    ziel = owner or engine
    try:
        with ziel.begin() as c:
            c.execute(sa.text(sql))
    finally:
        if owner is not None:
            owner.dispose()


# ---------------------------------------------------------------------------
# Hilfen fuer Zeit
# ---------------------------------------------------------------------------
@dataclass
class Zeitraum:
    start_tag: date = date(JAHR, 1, 1)
    tage: int = 365


def _lokal_utc(tz, tag, stunde=0, minute=0, sekunde=0):
    return datetime(tag.year, tag.month, tag.day, stunde, minute, sekunde, tzinfo=ZoneInfo(tz)).astimezone(timezone.utc)


@dataclass
class Run:
    key: str
    von: float                  # s ab Reihenstart
    bis: float
    ende_grund: str = 'PLANNED_END'
    reset: str = None
    id: int = None
    mc: dict = field(default_factory=dict)     # (groesse, 'RAW'|'DERIVED') -> id
    plan_id: int = None
    skip_von: float = None                      # Uhr-Vorwaertssprung (Messzeit)
    skip_s: float = 0.0

    def slot_s(self, t):
        """Abtastplatz-Zeit seit Run-Start (ohne uebersprungene Messzeit)."""
        d = t - self.von
        if self.skip_von is not None and t >= self.skip_von + self.skip_s:
            d -= self.skip_s
        return d


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------
class Generator:
    def __init__(self, engine, zeitraum=None, log=print):
        self.engine = engine
        self.z = zeitraum or Zeitraum()
        self.log = log
        self.stats = {}

    # -- Einstieg -------------------------------------------------------------
    def alle(self, nur=None):
        if self.engine.dialect.name != 'postgresql':
            raise RuntimeError('Der Sandbox-Generator braucht PostgreSQL (Schema sandbox).')
        self._standorte()
        for sz in SZENARIEN:
            if nur and sz.key not in nur:
                continue
            with self.engine.connect() as c:
                da = c.execute(sa.text('SELECT 1 FROM sandbox.sandbox_scenario WHERE scenario_key = :k AND scenario_version = :v'),
                               {'k': sz.key, 'v': SZENARIO_VERSION}).first()
            if da:
                self.log(f'{sz.key} v{SZENARIO_VERSION}: schon vorhanden -- uebersprungen')
                continue
            roh = self.engine.raw_connection()
            try:
                pg = roh.driver_connection
                self._szenario(pg, sz)
                pg.commit()
            except Exception:
                roh.driver_connection.rollback()
                raise
            finally:
                roh.close()
            self.log(f'{sz.key} v{SZENARIO_VERSION}: angelegt {self.stats.get(sz.key)}')
        return self.stats

    # -- Standorte (gemeinsam, get-or-create) ---------------------------------
    def _standorte(self):
        geo = _rollen_engine(self.engine, 'omn_geo')
        try:
            with self.engine.begin() as c:
                for s in STANDORTE.values():
                    sid = c.execute(sa.text('SELECT id FROM sandbox.site WHERE site_code = :c'), {'c': s.code}).scalar()
                    if sid is None:
                        sid = c.execute(sa.text(
                            "INSERT INTO sandbox.site (site_code, grid_system, grid_cell_id, elevation_m_rounded)"
                            " VALUES (:c, 'MGRS_10KM', :g, :h) RETURNING id"),
                            {'c': s.code, 'g': s.mgrs_10km, 'h': int(round(s.hoehe_m, -2))}).scalar()
                        c.execute(sa.text('INSERT INTO sandbox.site_timezone (site_id, iana_tz, valid_from) VALUES (:s, :tz, :v)'),
                                  {'s': sid, 'tz': s.iana_tz, 'v': datetime(JAHR - 1, 1, 1, tzinfo=timezone.utc)})
                    bridge = f'SBX-BRIDGE-{s.code[4:]}'
                    if not c.execute(sa.text('SELECT 1 FROM sandbox.device WHERE device_serial = :d'), {'d': bridge}).first():
                        c.execute(sa.text("INSERT INTO sandbox.device (device_serial, device_role, note) VALUES (:d, 'BRIDGE', 'synthetisch')"),
                                  {'d': bridge})
            with (geo or self.engine).begin() as c:
                for s in STANDORTE.values():
                    c.execute(sa.text(
                        "INSERT INTO sandbox_private.site_location_private (site_id, latitude, longitude, elevation_m, source)"
                        " SELECT id, :lat, :lon, :h, 'synthetisch (Sandbox-Generator)' FROM sandbox.site WHERE site_code = :c"
                        " ON CONFLICT (site_id) DO NOTHING"),
                        {'lat': s.breite, 'lon': s.laenge, 'h': s.hoehe_m, 'c': s.code})
        finally:
            if geo is not None:
                geo.dispose()

    # -- ein Szenario -----------------------------------------------------------
    def _szenario(self, pg, sz):
        st = self.stats.setdefault(sz.key, {'reihen': 0, 'bloecke': 0, 'aggregate': 0, 'stimulationen': 0, 'samples_roh': 0})
        cur = pg.cursor()
        reihen_ids = []
        for idx, reihe in enumerate(sz.reihen):
            sid = self._reihe(cur, sz, reihe, idx, st)
            reihen_ids.append((sid, reihe.rolle))
        cur.execute(
            "INSERT INTO sandbox.sandbox_scenario (scenario_key, scenario_version, generator_version,"
            " model_assumption_version, label, short_description, model_assumption_note, parameter_basis,"
            " stimulus_parameter_source, response_assumption, synthetic_year, is_public)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,'ARBITRARY_DEMO',%s,%s,%s,true) RETURNING id",
            (sz.key, SZENARIO_VERSION, GENERATOR_VERSION, MODELL_VERSION, sz.label, sz.kurz, sz.annahme,
             sz.stim_parameterquelle, sz.reaktionsannahme,
             Range(datetime(JAHR, 1, 1, tzinfo=timezone.utc), datetime(JAHR + 1, 1, 1, tzinfo=timezone.utc), '[)')))
        scen_id = cur.fetchone()[0]
        for sid, rolle in reihen_ids:
            cur.execute('INSERT INTO sandbox.sandbox_scenario_series VALUES (%s, %s, %s)', (scen_id, sid, rolle))

    # -- eine Reihe -------------------------------------------------------------
    def _reihe(self, cur, sz, reihe, idx, st):
        s = STANDORTE[reihe.standort]
        tz = s.iana_tz
        start = _lokal_utc(tz, self.z.start_tag)
        ende = _lokal_utc(tz, self.z.start_tag + timedelta(days=self.z.tage))
        dauer = (ende - start).total_seconds()
        stunden = math.ceil(dauer / 3600)
        sek = lambda tag, h=0, m=0, s_=0: (_lokal_utc(tz, tag, h, m, s_) - start).total_seconds()
        im_zeitraum = lambda t: 0 <= t < dauer
        seed = sz.seed + (idx if sz.key == 'baseline' else 0)   # Kontroll- und Stim.-Reihe teilen die Grundlage

        # --- Stoerungen (nur Datenqualitaets-Szenario) ---
        runs = [Run('boot-1', 0.0, dauer)]
        luecken, stoer_uv, anno = [], [], []
        clock = None
        if sz.datenqualitaet:
            w, fr, so, _he = (date(JAHR, m, d) for m, d in STICHWOCHEN)
            t_reset = sek(w, ROH_STUNDE_LOKAL, 20)
            if im_zeitraum(t_reset):             # Winter-Rohstunde: Watchdog-Neustart, 7 min Luecke
                runs = [Run('boot-1', 0.0, t_reset, 'RESTART', 'WATCHDOG_HW'), Run('boot-2', t_reset + 420, dauer)]
            luecken.append((sek(date(JAHR, 2, 10)), sek(date(JAHR, 2, 12))))      # 2 Tage fehlen (SD defekt)
            t_sat = sek(fr, ROH_STUNDE_LOKAL, 30)                                  # Fruehling: Saettigung
            stoer_uv.append((t_sat, t_sat + 120, 3000.0))
            anno.append(('bio', 'SATURATED', 'ALGORITHM', t_sat, t_sat + 120))
            t_clk = sek(so, ROH_STUNDE_LOKAL, 40)                                  # Sommer: Uhr springt 90 s vor
            if im_zeitraum(t_clk):
                clock = t_clk
                for r in runs:
                    if r.von <= t_clk < r.bis:
                        r.skip_von, r.skip_s = t_clk, 90.0
                luecken.append((t_clk, t_clk + 90))
                anno.append(('bio', 'TIMING_UNCERTAIN', 'INGESTION', sek(date(JAHR, 7, 10)), t_clk))
            anno.append(('soil_moisture', 'SENSOR_ERROR', 'ALGORITHM', sek(date(JAHR, 9, 1)), sek(date(JAHR, 9, 4))))
        runs = [r for r in runs if r.bis > r.von]

        # --- Aufzeichnungs-Abdeckung (Messzeit) ---
        roh_iv = [(r.von, r.bis) for r in runs]
        for a, b in sorted(luecken):
            neu = []
            for x, y in roh_iv:
                if b <= x or a >= y:
                    neu.append((x, y))
                else:
                    if x < a:
                        neu.append((x, a))
                    if b < y:
                        neu.append((b, y))
            roh_iv = neu
        abd = Abdeckung(roh_iv)
        # erwartet laut Plan: jeder Plan sieht Aufzeichnung bis zum Reihenende vor
        # (ein Absturz ist ungeplant) -> die Neustart-Luecke zaehlt als fehlend
        plan_abd = Abdeckung([(runs[0].von, dauer)])

        # --- Stammdaten der Reihe ---
        code = f'SBX-NODE-{reihe.kuerzel}-V{SZENARIO_VERSION}'
        cur.execute("INSERT INTO sandbox.device (device_serial, device_role, note) VALUES (%s,'NODE','synthetisch') RETURNING id", (code,))
        dev = cur.fetchone()[0]
        cur.execute("INSERT INTO sandbox.device_configuration (device_id, hardware_revision, firmware_version, config_version, settings)"
                    " VALUES (%s,'COMBO_NODE 3.2 (synthetisch)','sbx-fw-1','sbx-cfg-1',%s) RETURNING id",
                    (dev, json.dumps({'bio_rate_hz': RATE_HZ, 'ec_intervall_s': 3600, 'ec_dauer_s': EC_DAUER_S,
                                      'ec_einschwing_s_platzhalter': EC_EINSCHWING_S, 'gain_dip': GAIN})))
        cfg = cur.fetchone()[0]
        cur.execute("INSERT INTO sandbox.probe (probe_serial, probe_kind, note) VALUES (%s,'EXTERNAL_BIOCOMM','synthetisch') RETURNING id",
                    (f'SBX-PRB-{reihe.kuerzel}-V{SZENARIO_VERSION}',))
        prb = cur.fetchone()[0]
        akt = {}
        for typ, ausgang, sonde in (('ELECTRICAL', 'DAC_OUT', None), ('OPTICAL', 'LED_PWM1', prb)):
            cur.execute('INSERT INTO sandbox.actuator_channel (device_configuration_id, probe_id, actuator_type, output_label)'
                        ' VALUES (%s,%s,%s,%s) RETURNING id', (cfg, sonde, typ, ausgang))
            akt[typ] = cur.fetchone()[0]
        hw = {}
        cur.execute('INSERT INTO sandbox.hardware_channel (device_id, probe_id, input_label) VALUES (%s,%s,%s) RETURNING id',
                    (dev, prb, 'U8/AIN0 über INA333'))
        hw['bio'] = cur.fetchone()[0]
        for _q, _, _, _, label, _ in UMWELT_KANAELE:
            if label not in hw:
                cur.execute('INSERT INTO sandbox.hardware_channel (device_id, input_label) VALUES (%s,%s) RETURNING id', (dev, label))
                hw[label] = cur.fetchone()[0]
        cur.execute('INSERT INTO sandbox.series (series_code, site_id, substrate_code, title, study_period, context)'
                    ' SELECT %s, id, %s, %s, %s, %s FROM sandbox.site WHERE site_code = %s RETURNING id',
                    (f'SBX-{sz.key}-{reihe.kuerzel}-V{SZENARIO_VERSION}', s.substrat,
                     f'{sz.label} – {"Kontrollreihe" if reihe.rolle == "CONTROL" else "Reihe"} {s.code}',
                     Range(start, ende, '[)'), f'Sandbox-Szenario {sz.key} v{SZENARIO_VERSION} ({GENERATOR_VERSION})', s.code))
        serie = cur.fetchone()[0]

        # --- Runs, Kanaele, Plaene ---
        for r in runs:
            cur.execute('INSERT INTO sandbox.acquisition_run (series_id, device_id, device_configuration_id, node_run_key,'
                        ' started_at, ended_at, end_reason, reset_cause) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id',
                        (serie, dev, cfg, r.key, start + timedelta(seconds=r.von), start + timedelta(seconds=r.bis),
                         r.ende_grund, r.reset))
            r.id = cur.fetchone()[0]
            cur.execute('INSERT INTO sandbox.probe_assignment (acquisition_run_id, probe_id, is_external_biocomm) VALUES (%s,%s,true)',
                        (r.id, prb))
            kanaele = [('bio', 'PRIMARY', 'bioelectric_potential', '{count}', hw['bio'], RATE_HZ, 'RTC_SQW')]
            kanaele += [(q, rolle, q, einheit, hw[label], 1 / iv, 'SOFTWARE_TIMER') for q, rolle, einheit, iv, label, _ in UMWELT_KANAELE]
            for key, rolle, groesse, einheit, hwid, rate, takt in kanaele:
                gain = (GAIN, 'MANUAL') if key == 'bio' else (None, None)
                # ADC-Kalibrierung am Kanal (Provenienz): Umrechnung Counts -> uV am
                # Eingang = count * lsb_uv / gain. Das Dashboard liest sie von hier.
                kalib = {'adc': 'ADS1115', 'pga_v': 0.256, 'lsb_uv': LSB_UV, 'ziel_einheit': 'uV'} if key == 'bio' else {}
                cur.execute('INSERT INTO sandbox.measurement_channel (acquisition_run_id, device_id, hardware_channel_id,'
                            ' channel_role, quantity_code, unit_code, data_kind, sample_rate_hz, sample_clock_source, gain,'
                            " gain_source, calibration) VALUES (%s,%s,%s,%s,%s,%s,'RAW',%s,%s,%s,%s,%s) RETURNING id",
                            (r.id, dev, hwid, rolle, groesse, einheit, rate, takt, *gain, json.dumps(kalib)))
                r.mc[(key, 'RAW')] = cur.fetchone()[0]
                cur.execute('INSERT INTO sandbox.measurement_channel (acquisition_run_id, device_id, hardware_channel_id,'
                            ' channel_role, quantity_code, unit_code, data_kind, processing_origin, processing_version)'
                            " VALUES (%s,%s,%s,%s,%s,%s,'DERIVED','BACKEND',%s) RETURNING id",
                            (r.id, dev, hwid, rolle, groesse, 'uV' if key == 'bio' else einheit, GENERATOR_VERSION))
                r.mc[(key, 'DERIVED')] = cur.fetchone()[0]
                cur.execute('INSERT INTO sandbox.derived_channel_source VALUES (%s,%s)', (r.mc[(key, 'DERIVED')], r.mc[(key, 'RAW')]))
            cur.execute('INSERT INTO sandbox.recording_plan (acquisition_run_id, plan_version, valid_from, note)'
                        ' VALUES (%s,1,%s,%s) RETURNING id', (r.id, start + timedelta(seconds=r.von), f'{GENERATOR_VERSION}'))
            r.plan_id = cur.fetchone()[0]
            cur.execute("INSERT INTO sandbox.recording_plan_channel (recording_plan_id, acquisition_run_id, measurement_channel_id,"
                        " requirement, planned_sample_rate_hz) VALUES (%s,%s,%s,'REQUIRED',%s)",
                        (r.plan_id, r.id, r.mc[('bio', 'RAW')], RATE_HZ))
            with cur.copy('COPY sandbox.recording_plan_interval (recording_plan_id, acquisition_run_id, interval_kind,'
                          ' measurement_channel_id, pause_reason, period) FROM STDIN') as cp:
                # Aufzeichnung geplant bis Reihenende (ein Absturz ist ungeplant);
                # die EC-Pausen dieses Plans nur, solange der Run laeuft
                cp.write_row((r.plan_id, r.id, 'RECORDING', None, None,
                              Range(start + timedelta(seconds=r.von), start + timedelta(seconds=dauer), '[)')))
                h = math.ceil(r.von / 3600)
                while h * 3600 < r.bis:
                    t0 = start + timedelta(hours=h)
                    cp.write_row((r.plan_id, r.id, 'PAUSE', r.mc[('bio', 'RAW')], 'EC_MEASUREMENT',
                                  Range(t0, t0 + timedelta(seconds=EC_DAUER_S), '[)')))
                    cp.write_row((r.plan_id, r.id, 'PAUSE', r.mc[('bio', 'RAW')], 'EC_SETTLING',
                                  Range(t0 + timedelta(seconds=EC_DAUER_S), t0 + timedelta(seconds=EC_DAUER_S + EC_EINSCHWING_S), '[)')))
                    h += 1

        def run_bei(t):
            for r in runs:
                if r.von <= t < r.bis:
                    return r
            return None

        # --- Modelle ---
        umwelt = Umwelt(s, seed, start, stunden)
        stichtage = [date(JAHR, m, d) for m, d in STICHWOCHEN]
        roh_stunden = [sek(t, ROH_STUNDE_LOKAL) for t in stichtage if im_zeitraum(sek(t, ROH_STUNDE_LOKAL))]
        reaktionen, stim_zeilen = [], []
        if reihe.stimulation != 'KEINE':
            reaktionen, stim_zeilen = self._stimulationsplan(sz, reihe, umwelt, start, sek, runs, akt, cfg, stichtage, st)
        bio = Bio(umwelt, seed, stunden, reaktionen, stoer_uv)

        # --- Clock-Sync + Qualitaetsannotationen ---
        clock_id = None
        if clock is not None:
            r = run_bei(clock)
            cur.execute("INSERT INTO sandbox.clock_sync_event (device_id, acquisition_run_id, reference_source, reference_time,"
                        " device_time, correction_mode, applied_at) VALUES (%s,%s,'BRIDGE',%s,%s,'STEP_FORWARD',%s) RETURNING id",
                        (dev, r.id, start + timedelta(seconds=clock + 90), start + timedelta(seconds=clock),
                         start + timedelta(seconds=clock)))
            clock_id = cur.fetchone()[0]

        # --- Umwelt/SYSTEM: Samples, Bloecke, Stundenwerte ---
        rng_u = random.Random(seed * 31 + 5)
        batches = {r.id: [] for r in runs}      # run -> [(ende_s, content, bloecke)]
        agg = []                                  # derived_aggregate-Zeilen
        feuchte_fehler = [(a, b) for k, c, _, a, b in anno if k == 'soil_moisture']
        tage_n = self.z.tage
        for q, _, _, iv, _, rausch in UMWELT_KANAELE:
            versatz = 15 if q == 'electrical_conductivity' else 0
            proben = []                           # (t, wert)
            t = versatz
            while t < dauer:
                if abd.enthaelt(t):
                    w = umwelt.wert(q, t) + rng_u.gauss(0, rausch)
                    if q == 'soil_moisture' and any(a <= t < b for a, b in feuchte_fehler):
                        w = 63.5                  # haengender Sensor (SENSOR_ERROR)
                    proben.append((t, w))
                t += iv
            # Stundenwerte
            je_stunde = {}
            for t, w in proben:
                je_stunde.setdefault(int(t // 3600), []).append(w)
            for h, ws in je_stunde.items():
                r = run_bei(h * 3600 + versatz) or run_bei(h * 3600 + 3599)
                if r is None:
                    continue
                maske = self._maske(anno, q, h * 3600, h * 3600 + 3600)
                agg.append((r.mc[(q, 'DERIVED')], '1h', start + timedelta(hours=h), max(1, 3600 // iv), len(ws),
                            min(ws), max(ws), sum(ws) / len(ws), maske))
            # Tagesbloecke je Run, zusammenhaengende Abtastplaetze
            for tag_i in range(tage_n + 1):
                t0, t1 = sek(self.z.start_tag + timedelta(days=tag_i)), sek(self.z.start_tag + timedelta(days=tag_i + 1))
                teil = [(t, w) for t, w in proben if t0 <= t < t1]
                if not teil:
                    continue
                block = [teil[0]]
                for (t, w) in teil[1:]:
                    r_alt, r_neu = run_bei(block[-1][0]), run_bei(t)
                    if r_alt is r_neu and abs(r_neu.slot_s(t) - r_neu.slot_s(block[-1][0]) - iv) < 1e-6:
                        block.append((t, w))
                    else:
                        self._umwelt_block(batches, run_bei(block[0][0]), q, iv, block, t1, versatz)
                        block = [(t, w)]
                self._umwelt_block(batches, run_bei(block[0][0]), q, iv, block, t1, versatz)

        # --- Bio: Rohdatenstunden ---
        roh_min, roh_std = {}, {}
        for h0 in roh_stunden:
            for teil_a, teil_b in Abdeckung.ohne_ec(abd.schnitt(h0, h0 + 3600)):
                m = math.floor(teil_a / 60)
                while m * 60 < teil_b:
                    a, b = max(teil_a, m * 60), min(teil_b, (m + 1) * 60)
                    if b - a >= 1 / RATE_HZ:
                        r = run_bei(a)
                        counts = bio.roh(a, b)
                        self._bio_block(batches, r, a, b, counts, anno, st)
                        uv = [c * LSB_UV / GAIN for c in counts]
                        roh_min.setdefault(m, []).extend(uv)
                        roh_std.setdefault(int(h0 // 3600), []).extend(uv)
                    m += 1

        # --- Bio: Aggregate ---
        stichwochen_min = set()
        for tag in stichtage:
            t0 = sek(tag)
            if im_zeitraum(t0) or im_zeitraum(t0 + 7 * 86400 - 1):
                stichwochen_min.update(range(int(t0 // 60), int((t0 + 7 * 86400) // 60)))
        for h in range(stunden):
            a, b = h * 3600, min((h + 1) * 3600, dauer)
            r = run_bei(a) or run_bei(b - 1)
            if r is None:
                continue
            erwartet = int(sum(y - x for x, y in Abdeckung.ohne_ec(plan_abd.schnitt(a, b))) * RATE_HZ)
            if h in roh_std:
                ws = roh_std[h]
                werte = (len(ws), min(ws), max(ws), sum(ws) / len(ws))
            else:
                werte = bio.aggregat(Abdeckung.ohne_ec(abd.schnitt(a, b)), 4.8)
            if werte:
                agg.append((r.mc[('bio', 'DERIVED')], '1h', start + timedelta(seconds=a), erwartet, werte[0],
                            werte[1], werte[2], werte[3], self._maske(anno, 'bio', a, b)))
        for m in sorted(stichwochen_min):
            a, b = m * 60, (m + 1) * 60
            if not (0 <= a < dauer):
                continue
            r = run_bei(a)
            if r is None:
                continue
            erwartet = int(sum(y - x for x, y in Abdeckung.ohne_ec(plan_abd.schnitt(a, b))) * RATE_HZ)
            if m in roh_min:
                ws = roh_min[m]
                werte = (len(ws), min(ws), max(ws), sum(ws) / len(ws))
            else:
                werte = bio.aggregat(Abdeckung.ohne_ec(abd.schnitt(a, b)), 4.0)
            if werte:
                agg.append((r.mc[('bio', 'DERIVED')], '1min', start + timedelta(seconds=a), erwartet, werte[0],
                            werte[1], werte[2], werte[3], self._maske(anno, 'bio', a, b)))

        # --- Schreiben: Batches (eine Kette je Run), Bloecke, Anlieferungen ---
        rng_d = random.Random(seed * 17 + 3)
        bridge = f'SBX-BRIDGE-{s.code[4:]}'
        cur.execute('SELECT id FROM sandbox.device WHERE device_serial = %s', (bridge,))
        bridge_id = cur.fetchone()[0]
        for r in runs:
            # Telemetrie: ein Paket je Run und Tag mit allen Umwelt-/SYSTEM-Bloecken
            gruppiert = {}
            for ende_s, inhalt, bloecke in batches[r.id]:
                schluessel = (ende_s, inhalt) if inhalt == 'TELEMETRY' else (ende_s, inhalt, id(bloecke))
                gruppiert.setdefault(schluessel, (ende_s, inhalt, []))[2].extend(bloecke)
            liste = sorted(gruppiert.values(), key=lambda x: (x[0], x[1]))
            if not liste:
                continue
            batch_zeilen, block_zeilen, prev = [], [], GENESIS
            for seq, (ende_s, inhalt, bloecke) in enumerate(liste, start=1):
                payload_hash = _sha(b''.join(bl['payload'] for bl in bloecke))
                bhash = _sha(prev + payload_hash + seq.to_bytes(8, 'big'))
                von = min(bl['t0'] for bl in bloecke)
                batch_zeilen.append((r.id, seq, inhalt, Range(start + timedelta(seconds=von), start + timedelta(seconds=ende_s), '[)'),
                                     payload_hash, prev, bhash, f'{GENERATOR_VERSION}/{inhalt.lower()}', 'SAMPLE_BLOCKS',
                                     sum(len(bl['payload']) for bl in bloecke), 'CANONICAL', 'LINKED', 'SINGLE_CANDIDATE'))
                for bl in bloecke:
                    block_zeilen.append((seq, bl))
                prev = bhash
            with cur.copy('COPY sandbox.origin_batch (acquisition_run_id, batch_sequence_no, batch_content, measured_period,'
                          ' payload_hash, previous_batch_hash, batch_hash, payload_format, payload_location, payload_size_bytes,'
                          ' batch_status, chain_state, status_basis) FROM STDIN') as cp:
                for z in batch_zeilen:
                    cp.write_row(z)
            cur.execute('SELECT batch_sequence_no, id, upper(measured_period), batch_content FROM sandbox.origin_batch'
                        ' WHERE acquisition_run_id = %s', (r.id,))
            ids = {seq: (bid, ende, inhalt) for seq, bid, ende, inhalt in cur.fetchall()}
            with cur.copy('COPY sandbox.sample_block (acquisition_run_id, measurement_channel_id, origin_batch_id,'
                          ' first_sample_index, sample_count, time_anchor, sample_rate_hz, value_encoding, compression,'
                          ' payload_location, payload_inline, payload_hash) FROM STDIN') as cp:
                for seq, bl in block_zeilen:
                    cp.write_row((r.id, bl['mc'], ids[seq][0], bl['idx'], bl['n'], start + timedelta(seconds=bl['t0']),
                                  bl['rate'], bl['enc'], bl['komp'], 'INLINE', bl['payload'], _sha(bl['payload'])))
            st['bloecke'] += len(block_zeilen)
            with cur.copy('COPY sandbox.batch_delivery (origin_batch_id, transport_code, bridge_device_id, bridge_role,'
                          ' received_at, delivery_status, status_reason) FROM STDIN') as cp:
                for bid, ende, inhalt in ids.values():
                    sd = ende + timedelta(days=3)
                    if inhalt == 'TELEMETRY' and not (sz.datenqualitaet and rng_d.random() < 0.06):
                        cp.write_row((bid, 'LORA', bridge_id, 'BRIDGE', ende + timedelta(seconds=20), 'ACCEPTED', None))
                        cp.write_row((bid, 'SD_IMPORT', None, None, sd, 'DUPLICATE', 'schon per LoRa angeliefert'))
                    else:
                        cp.write_row((bid, 'SD_IMPORT', None, None, sd, 'ACCEPTED',
                                      'LoRa-Paket verloren, per SD nachgeliefert' if inhalt == 'TELEMETRY' else None))

        # --- Stimulationen (nach den Plaenen, EC-Ausschluss-Trigger greift) ---
        if stim_zeilen:
            self._stimulationen_schreiben(cur, stim_zeilen, start)

        # --- Qualitaetsannotationen ---
        for kanal, code_q, herkunft, a, b in anno:
            if b <= 0 or a >= dauer:
                continue
            a, b = max(a, 0), min(b, dauer)
            r = run_bei(a) or run_bei(b - 1)
            if r is None:
                continue
            idx_bereich = None
            if code_q == 'SATURATED':
                idx_bereich = Range(round(r.slot_s(a) * RATE_HZ), round(r.slot_s(b) * RATE_HZ), '[)')
            cur.execute('INSERT INTO sandbox.quality_annotation (measurement_channel_id, sample_index_range, time_range,'
                        ' quality_code, origin, processing_version, clock_sync_event_id, note)'
                        ' VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                        (r.mc[(kanal, 'RAW')], idx_bereich, Range(start + timedelta(seconds=a), start + timedelta(seconds=b), '[)'),
                         code_q, herkunft, GENERATOR_VERSION if herkunft == 'ALGORITHM' else None,
                         clock_id if code_q == 'TIMING_UNCERTAIN' else None, 'Sandbox: absichtlich eingebaute Störung'))

        # --- Aggregate ---
        with cur.copy('COPY sandbox.derived_aggregate (measurement_channel_id, resolution, bucket_start, samples_expected,'
                      ' samples_recorded, value_min, value_max, value_mean, quality_mask) FROM STDIN') as cp:
            for z in agg:
                cp.write_row(z)
        st['aggregate'] += len(agg)
        st['reihen'] += 1
        return serie

    # -- Hilfen -------------------------------------------------------------------
    @staticmethod
    def _maske(anno, kanal, a, b):
        m = 0
        for k, code_q, _, x, y in anno:
            if k == kanal and x < b and y > a:
                m |= QBIT[code_q]
        return m

    @staticmethod
    def _umwelt_block(batches, r, q, iv, block, tag_ende, versatz):
        payload = b''.join(struct.pack('<f', w) for _, w in block)
        batches[r.id].append((tag_ende if tag_ende <= r.bis else r.bis, 'TELEMETRY', [{
            'mc': r.mc[(q, 'RAW')], 'idx': round((r.slot_s(block[0][0]) - versatz) / iv), 'n': len(block),
            't0': block[0][0], 'rate': 1 / iv, 'enc': 'float32le', 'komp': 'none', 'payload': payload}]))

    @staticmethod
    def _bio_block(batches, r, a, b, counts, anno, st):
        payload, komp = _komprimieren(struct.pack(f'<{len(counts)}h', *counts))
        batches[r.id].append((b, 'RAW', [{
            'mc': r.mc[('bio', 'RAW')], 'idx': round(r.slot_s(a) * RATE_HZ), 'n': len(counts),
            't0': a, 'rate': RATE_HZ, 'enc': 'int16le', 'komp': komp, 'payload': payload}]))
        st['samples_roh'] += len(counts)

    def _stimulationsplan(self, sz, reihe, umwelt, start, sek, runs, akt, cfg, stichtage, st):
        rng = random.Random(sz.seed + 7)
        arten = {'ELEKTRISCH': (('ELECTRICAL', 0),), 'OPTISCH': (('OPTICAL', 0),),
                 'SYNCHRON': (('ELECTRICAL', 0), ('OPTICAL', 0)),
                 'VERSETZT': (('ELECTRICAL', 0), ('OPTICAL', VERSATZ_MS))}[reihe.stimulation]
        grund_uv = {'ELECTRICAL': 35.0, 'OPTICAL': 22.0}
        reaktionen, zeilen = [], []
        for tag_i in range(self.z.tage):
            tag = self.z.start_tag + timedelta(days=tag_i)
            t_plan = sek(tag, STIM_STUNDE, STIM_MINUTE)
            run = next((r for r in runs if r.von <= t_plan < r.bis - 3600), None)
            if run is None:
                continue
            sequenz = []
            for typ, versatz in arten:
                t = t_plan + versatz / 1000
                wurf = rng.random()
                if tag in stichtage:
                    zustand = 'EXECUTED'           # Rohdatenstunde: sichtbar ausgefuehrt
                elif wurf < 0.02:
                    zustand = 'FAILED'
                elif wurf < 0.04:
                    zustand = 'CANCELLED'
                elif wurf < 0.05:
                    zustand = 'PARTIAL'
                else:
                    zustand = 'EXECUTED'
                jitter = rng.uniform(0, 2)
                dauer_ms = STIM_DAUER_MS if zustand == 'EXECUTED' else int(rng.uniform(10_000, 50_000))
                ist_start = t + jitter if zustand in ('EXECUTED', 'PARTIAL') else None
                if ist_start is not None:
                    anteil = dauer_ms / STIM_DAUER_MS
                    a_uv = grund_uv[typ] * (0.3 + 0.7 * umwelt.aktivitaet(t)) * anteil
                    reaktionen.append(Reaktion(ist_start + dauer_ms / 1000, a_uv, rng))
                zeilen.append({
                    'run': run.id, 'cfg': cfg, 'akt': akt[typ], 'typ': typ, 'plan': t, 'zustand': zustand,
                    'ist_start': ist_start, 'dauer_ms': dauer_ms if ist_start is not None else None,
                    'versuch': t + jitter if zustand == 'FAILED' else None,
                    'grund': {'FAILED': 'Aktor hat nicht angesprochen (synthetisch)',
                              'CANCELLED': 'vom Plan verworfen (synthetisch)',
                              'PARTIAL': 'vorzeitig beendet (synthetisch)'}.get(zustand),
                    'versatz': versatz})
                sequenz.append(zeilen[-1])
            if len(arten) > 1:
                for z in sequenz:
                    z['sequenz'] = (run.id, t_plan, reihe.stimulation)
        st['stimulationen'] += len(zeilen)
        return reaktionen, zeilen

    def _stimulationen_schreiben(self, cur, zeilen, start):
        ts = lambda s: None if s is None else start + timedelta(seconds=s)
        with cur.copy('COPY sandbox.stimulation (acquisition_run_id, device_configuration_id, actuator_channel_id,'
                      ' actuator_type, trigger_source, planned_start, execution_state, actual_start, actual_duration_ms,'
                      ' attempted_at, state_reason, state_changed_at) FROM STDIN') as cp:
            for z in zeilen:
                ende = z['ist_start'] + z['dauer_ms'] / 1000 if z['ist_start'] is not None else z['versuch'] or z['plan']
                cp.write_row((z['run'], z['cfg'], z['akt'], z['typ'], 'SCHEDULED', ts(z['plan']), z['zustand'],
                              ts(z['ist_start']), z['dauer_ms'], ts(z['versuch']), z['grund'], ts(ende)))
        runs = sorted({z['run'] for z in zeilen})
        cur.execute('SELECT id, acquisition_run_id, actuator_type, planned_start FROM sandbox.stimulation'
                    ' WHERE acquisition_run_id = ANY(%s)', (runs,))
        ids = {(run, typ, plan): sid for sid, run, typ, plan in cur.fetchall()}
        with cur.copy('COPY sandbox.stimulation_param_electrical (stimulation_id, waveform, amplitude, amplitude_unit,'
                      ' frequency_hz, duration_ms) FROM STDIN') as cp:
            for z in zeilen:
                if z['typ'] == 'ELECTRICAL':
                    cp.write_row((ids[(z['run'], z['typ'], ts(z['plan']))], 'BIPHASIC_SQUARE', 0.5, 'V', 1.0, STIM_DAUER_MS))
        with cur.copy('COPY sandbox.stimulation_param_optical (stimulation_id, wavelength_nm, pattern, intensity,'
                      ' intensity_unit, frequency_hz, duty_cycle, duration_ms) FROM STDIN') as cp:
            for z in zeilen:
                if z['typ'] == 'OPTICAL':
                    cp.write_row((ids[(z['run'], z['typ'], ts(z['plan']))], 470, 'PULSE', 50, '%', 1.0, 0.5, STIM_DAUER_MS))
        sequenzen = {}
        for z in zeilen:
            if 'sequenz' in z:
                sequenzen.setdefault(z['sequenz'], []).append(z)
        for (run, t_plan, art), mitglieder in sequenzen.items():
            cur.execute('INSERT INTO sandbox.stimulation_sequence (acquisition_run_id, label, experiment_definition, planned_start)'
                        ' VALUES (%s,%s,%s,%s) RETURNING id',
                        (run, 'Elektrisch + optisch, ' + ('synchron' if art == 'SYNCHRON' else 'versetzt'),
                         json.dumps({'art': art, 'versatz_ms': [m['versatz'] for m in mitglieder]}), ts(t_plan)))
            seq_id = cur.fetchone()[0]
            for m in mitglieder:
                cur.execute('INSERT INTO sandbox.stimulation_sequence_member VALUES (%s,%s,%s,%s)',
                            (seq_id, ids[(m['run'], m['typ'], ts(m['plan']))], run, m['versatz']))


__all__ = ['SAETTIGUNG_UV', 'Generator', 'Zeitraum', 'zuruecksetzen']
