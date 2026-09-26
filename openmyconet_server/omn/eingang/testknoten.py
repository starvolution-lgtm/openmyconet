"""Test-Messknoten fuer den Dateneingang (nur Schema sandbox).

Es gibt noch keine echte Hardware. Dieser Knoten legt die Stammdaten eines
synthetischen Nodes an (Geraet, Konfiguration, Sonde, Hardwarekanaele, Serie,
Messlauf, RAW- und DERIVED-Kanaele, wie der Sandbox-Generator) und erzeugt
fortlaufende Datenpakete im Format v0 oder v1 (format='v1') -- so, wie ein Node sie auf SD-Karte
schreiben und per LoRa/BLE schicken wuerde. Feste Seeds -> reproduzierbar.

Selbstanmeldung (Format v1): knoten_vorbereiten() legt nur Geraet, Messreihe
und Einsatz an; das erste Paket traegt LAUF_START, der Eingang legt den
Messlauf daraus an -- wie spaeter beim echten Node.

Ausserdem: pakete_aus_datenbank() exportiert die vom Sandbox-Generator
geschriebenen Batches eines Laufs als Pakete v0 (Formatgleichheit pruefen,
SD-Import nachstellen).
"""
import math
import random
import struct
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from omn.eingang.einlesen import sql
from omn.eingang import format_v1
from omn.eingang.format_v0 import GENESIS, Block, paket_bauen

EINGANG_BIO = 'U8/AIN0 über INA333'
EINGANG_TEMP = 'DS18B20 Bodentemperatur'
TEMP_INTERVALL_S = 10
STANDORT = 'SBX-EINGANG-01'
LSB_UV, GAIN = 7.8125, 100


@dataclass
class TestKnoten:
    geraet: str
    lauf: str
    lauf_id: int
    start: datetime
    rate_hz: int
    paket_s: int
    kanaele: dict = field(default_factory=dict)     # (schluessel, RAW|DERIVED) -> measurement_channel.id
    format: str = 'v0'                              # Paketformat: 'v0' (JSON) oder 'v1' (binaer, Firmware)
    anmelden: bool = False                          # Sequenz 1 traegt LAUF_START (nur v1)
    sonde: str = None
    ec_pause: bool = False                          # LAUF_START meldet stuendlich 30 s + 5 s EC-Pause

    # -- Pakete ------------------------------------------------------------
    def paket(self, sequenz, vorgaenger_hash, variante=0):
        """Paket `sequenz` (ab 1). variante != 0 -> andere Messwerte auf demselben
        Sequenzplatz (fuer Konflikt-Tests)."""
        rng = random.Random(f'{self.geraet}/{self.lauf}/{sequenz}/{variante}')
        t0 = self.start + timedelta(seconds=(sequenz - 1) * self.paket_s)
        n_bio = self.paket_s * self.rate_hz
        counts = []
        for i in range(n_bio):
            t = (sequenz - 1) * self.paket_s + i / self.rate_hz
            counts.append(max(-32768, min(32767, round(900 * math.sin(2 * math.pi * t / 300) + rng.gauss(0, 25)))))
        n_temp = self.paket_s // TEMP_INTERVALL_S
        temp = [12.0 + 0.5 * math.sin(2 * math.pi * ((sequenz - 1) * n_temp + i) / 360) + rng.gauss(0, 0.02)
                for i in range(n_temp)]
        bio = zlib.compress(struct.pack(f'<{n_bio}h', *counts), 6)
        tmp = struct.pack(f'<{n_temp}f', *temp)
        bis = t0 + timedelta(seconds=self.paket_s)
        if self.format == 'v1':
            bloecke = (
                format_v1.block_bauen(EINGANG_BIO, 'bioelectric_potential', (sequenz - 1) * n_bio, n_bio, t0,
                                      (self.rate_hz, 1), 'int16le', 'zlib-6', bio),
                format_v1.block_bauen(EINGANG_TEMP, 'soil_temperature', (sequenz - 1) * n_temp, n_temp, t0,
                                      (1, TEMP_INTERVALL_S), 'float32le', 'none', tmp),
            )
            ereignisse = [format_v1.ereignis(self.lauf_start(), t0)] if self.anmelden and sequenz == 1 else []
            return format_v1.paket_bauen(self.geraet, self.lauf, sequenz, 'MIXED', t0, bis, vorgaenger_hash, bloecke,
                                         ereignisse=ereignisse)
        bloecke = (
            Block(EINGANG_BIO, 'bioelectric_potential', (sequenz - 1) * n_bio, n_bio, t0, float(self.rate_hz),
                  'int16le', 'zlib-6', bio),
            Block(EINGANG_TEMP, 'soil_temperature', (sequenz - 1) * n_temp, n_temp, t0, 1 / TEMP_INTERVALL_S,
                  'float32le', 'none', tmp),
        )
        return paket_bauen(self.geraet, self.lauf, sequenz, 'MIXED', t0, bis, vorgaenger_hash, bloecke)

    def lauf_start(self):
        """LAUF_START dieses Knotens (Kanaele wie knoten_anlegen)."""
        pausen = ()
        if self.ec_pause:
            pausen = (format_v1.PausenRegel(EINGANG_BIO, 'bioelectric_potential', 'EC_MEASUREMENT', 3600, 0, 30_000),
                      format_v1.PausenRegel(EINGANG_BIO, 'bioelectric_potential', 'EC_SETTLING', 3600, 30_000, 5_000))
        kal = '{"adc": "ADS1115", "lsb_uv": %s, "ziel_einheit": "uV"}' % LSB_UV
        return format_v1.LaufStart(
            'COMBO_NODE 3.2 (Test)', 'test-fw-1', 'test-cfg-1' + ('-ec' if self.ec_pause else ''), 'POWER_ON',
            self.sonde, (
                format_v1.KanalAngabe(EINGANG_BIO, 'bioelectric_potential', '{count}', 'PRIMARY', self.rate_hz, 1,
                                      'RTC_SQW', GAIN * 1000, 'MANUAL', True, kal),
                format_v1.KanalAngabe(EINGANG_TEMP, 'soil_temperature', 'Cel', 'ENVIRONMENTAL', 1, TEMP_INTERVALL_S,
                                      'SOFTWARE_TIMER')),
            pausen)

    def genesis(self):
        return format_v1.genesis_berechnen(self.geraet, self.lauf) if self.format == 'v1' else GENESIS

    def pakete(self, anzahl):
        """Die ersten `anzahl` Pakete der Kette (Sequenz 1..anzahl)."""
        liste, vorg = [], self.genesis()
        for seq in range(1, anzahl + 1):
            p = self.paket(seq, vorg)
            liste.append(p)
            vorg = p.batch_hash
        return liste


def knoten_vorbereiten(engine, name, *, start=datetime(2025, 3, 3, 8, 0, tzinfo=timezone.utc), rate_hz=250,
                       paket_s=60, lauf='boot-1', einsatz=True, ec_pause=False):
    """Nur Geraet, Messreihe und (optional) Einsatz in sandbox anlegen; den
    Messlauf legt der Eingang aus dem LAUF_START in Sequenz 1 an (Format v1).
    Liefert den TestKnoten (lauf_id None)."""
    if paket_s % TEMP_INTERVALL_S:
        raise ValueError(f'paket_s muss ein Vielfaches von {TEMP_INTERVALL_S} sein')
    geraet = f'SBX-NODE-EINGANG-{name}'
    with engine.begin() as c:
        q = lambda text, **p: c.execute(sa.text(text), p).scalar()
        site = q('SELECT id FROM sandbox.site WHERE site_code = :c', c=STANDORT)
        if site is None:
            site = q("INSERT INTO sandbox.site (site_code, grid_system, grid_cell_id) VALUES (:c, 'MGRS_10KM', '32UNB00')"
                     ' RETURNING id', c=STANDORT)
        dev = q("INSERT INTO sandbox.device (device_serial, device_role, note) VALUES (:d, 'NODE', 'Test-Messknoten')"
                ' RETURNING id', d=geraet)
        serie = q("INSERT INTO sandbox.series (series_code, site_id, substrate_code, title, study_period)"
                  " VALUES (:c, :s, 'SOIL', :t, tstzrange(:a, :e)) RETURNING id", c=f'SBX-EINGANG-{name}', s=site,
                  t=f'Test-Messknoten {name}', a=start, e=start + timedelta(days=365))
        if einsatz:
            q('INSERT INTO sandbox.device_deployment (device_id, series_id, valid_from) VALUES (:d, :s, :a) RETURNING id',
              d=dev, s=serie, a=start - timedelta(days=1))
    return TestKnoten(geraet, lauf, None, start, rate_hz, paket_s, format='v1', anmelden=True,
                      sonde=f'SBX-PRB-EINGANG-{name}', ec_pause=ec_pause)


def knoten_anlegen(engine, name, *, start=datetime(2025, 3, 3, 8, 0, tzinfo=timezone.utc), rate_hz=250,
                   paket_s=60, lauf='boot-1', ended_at=None, format='v0'):
    """Legt Stammdaten eines Test-Nodes in sandbox an und liefert den TestKnoten.
    `name` wird Teil der Seriennummer (SBX-NODE-EINGANG-<name>), muss also je
    Datenbank eindeutig sein. Laeuft mit SELECT/INSERT (Rolle omn genuegt)."""
    if paket_s % TEMP_INTERVALL_S:
        raise ValueError(f'paket_s muss ein Vielfaches von {TEMP_INTERVALL_S} sein')
    geraet = f'SBX-NODE-EINGANG-{name}'
    with engine.begin() as c:
        q = lambda text, **p: c.execute(sa.text(text), p).scalar()
        site = q('SELECT id FROM sandbox.site WHERE site_code = :c', c=STANDORT)
        if site is None:
            site = q("INSERT INTO sandbox.site (site_code, grid_system, grid_cell_id) VALUES (:c, 'MGRS_10KM', '32UNB00')"
                     ' RETURNING id', c=STANDORT)
        dev = q("INSERT INTO sandbox.device (device_serial, device_role, note) VALUES (:d, 'NODE', 'Test-Messknoten')"
                ' RETURNING id', d=geraet)
        cfg = q("INSERT INTO sandbox.device_configuration (device_id, hardware_revision, firmware_version, config_version)"
                " VALUES (:d, 'COMBO_NODE 3.2 (Test)', 'test-fw-0', 'test-cfg-0') RETURNING id", d=dev)
        prb = q("INSERT INTO sandbox.probe (probe_serial, probe_kind, note) VALUES (:p, 'EXTERNAL_BIOCOMM', 'Test')"
                ' RETURNING id', p=f'SBX-PRB-EINGANG-{name}')
        hw_bio = q('INSERT INTO sandbox.hardware_channel (device_id, probe_id, input_label) VALUES (:d, :p, :l) RETURNING id',
                   d=dev, p=prb, l=EINGANG_BIO)
        hw_temp = q('INSERT INTO sandbox.hardware_channel (device_id, input_label) VALUES (:d, :l) RETURNING id',
                    d=dev, l=EINGANG_TEMP)
        serie = q("INSERT INTO sandbox.series (series_code, site_id, substrate_code, title, study_period)"
                  " VALUES (:c, :s, 'SOIL', :t, tstzrange(:a, :e)) RETURNING id", c=f'SBX-EINGANG-{name}', s=site,
                  t=f'Test-Messknoten {name}', a=start, e=start + timedelta(days=365))
        run = q('INSERT INTO sandbox.acquisition_run (series_id, device_id, device_configuration_id, node_run_key,'
                ' started_at, ended_at, end_reason) VALUES (:s, :d, :c, :k, :a, :e, :g) RETURNING id',
                s=serie, d=dev, c=cfg, k=lauf, a=start, e=ended_at, g='PLANNED_END' if ended_at else None)
        c.execute(sa.text('INSERT INTO sandbox.probe_assignment (acquisition_run_id, probe_id, is_external_biocomm)'
                          ' VALUES (:r, :p, true)'), {'r': run, 'p': prb})
        k = TestKnoten(geraet, lauf, run, start, rate_hz, paket_s, format=format)
        for schluessel, hw, rolle, groesse, einheit, rate, takt, gain, kalib, einheit_abg in (
                ('bio', hw_bio, 'PRIMARY', 'bioelectric_potential', '{count}', rate_hz, 'RTC_SQW', GAIN,
                 '{"adc": "ADS1115", "lsb_uv": %s, "ziel_einheit": "uV"}' % LSB_UV, 'uV'),
                ('temp', hw_temp, 'ENVIRONMENTAL', 'soil_temperature', 'Cel', 1 / TEMP_INTERVALL_S, 'SOFTWARE_TIMER',
                 None, '{}', 'Cel')):
            k.kanaele[(schluessel, 'RAW')] = q(
                'INSERT INTO sandbox.measurement_channel (acquisition_run_id, device_id, hardware_channel_id,'
                ' channel_role, quantity_code, unit_code, data_kind, sample_rate_hz, sample_clock_source, gain,'
                " gain_source, calibration) VALUES (:r, :d, :h, :ro, :g, :e, 'RAW', :hz, :t, :ga, :gs, CAST(:k AS jsonb))"
                ' RETURNING id', r=run, d=dev, h=hw, ro=rolle, g=groesse, e=einheit, hz=rate, t=takt, ga=gain,
                gs='MANUAL' if gain else None, k=kalib)
            k.kanaele[(schluessel, 'DERIVED')] = q(
                'INSERT INTO sandbox.measurement_channel (acquisition_run_id, device_id, hardware_channel_id,'
                ' channel_role, quantity_code, unit_code, data_kind, processing_origin, processing_version)'
                " VALUES (:r, :d, :h, :ro, :g, :e, 'DERIVED', 'BACKEND', 'eingang-v0') RETURNING id",
                r=run, d=dev, h=hw, ro=rolle, g=groesse, e=einheit_abg)
            c.execute(sa.text('INSERT INTO sandbox.derived_channel_source VALUES (:a, :b)'),
                      {'a': k.kanaele[(schluessel, 'DERIVED')], 'b': k.kanaele[(schluessel, 'RAW')]})
    return k


def pakete_aus_datenbank(engine, lauf_id, schema='sandbox'):
    """Exportiert die Batches eines Laufs (Ablage SAMPLE_BLOCKS) als Pakete v0,
    Bloecke in Speicherreihenfolge. Fuer Batches des Sandbox-Generators."""
    s = schema
    with engine.connect() as c:
        kopf = c.execute(sql(s,
            'SELECT d.device_serial, r.node_run_key FROM {s}.acquisition_run r JOIN {s}.device d ON d.id = r.device_id'
            ' WHERE r.id = :r'), {'r': lauf_id}).one()
        batches = c.execute(sql(s,
            'SELECT id, batch_sequence_no, batch_content, lower(measured_period) AS von, upper(measured_period) AS bis,'
            ' previous_batch_hash FROM {s}.origin_batch'
            " WHERE acquisition_run_id = :r AND payload_location = 'SAMPLE_BLOCKS' ORDER BY batch_sequence_no"),
            {'r': lauf_id}).all()
        pakete = []
        for b in batches:
            bloecke = [Block(z.input_label, z.quantity_code, z.first_sample_index, z.sample_count, z.time_anchor,
                             float(z.sample_rate_hz), z.value_encoding, z.compression, bytes(z.payload_inline),
                             None if z.device_quality is None else bytes(z.device_quality))
                       for z in c.execute(sql(s,
                           'SELECT hc.input_label, mc.quantity_code, sb.* FROM {s}.sample_block sb'
                           ' JOIN {s}.measurement_channel mc ON mc.id = sb.measurement_channel_id'
                           ' JOIN {s}.hardware_channel hc ON hc.id = mc.hardware_channel_id'
                           ' WHERE sb.origin_batch_id = :b ORDER BY sb.id'), {'b': b.id})]
            pakete.append(paket_bauen(kopf.device_serial, kopf.node_run_key, b.batch_sequence_no, b.batch_content,
                                      b.von, b.bis, bytes(b.previous_batch_hash), bloecke))
    return pakete
