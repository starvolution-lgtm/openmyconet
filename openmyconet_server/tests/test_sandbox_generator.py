"""Sandbox-Generator (omn/sandbox/): nur PostgreSQL (Schema sandbox aus Migration
3f1b2c4d5e6a). Laeuft im CI-Job backend-postgres ueber 20 Tage (enthaelt die
Winter-Stichwoche mit Rohdatenstunde, Stimulation und Watchdog-Neustart).
"""
import os
import tempfile

import pytest
from flask_migrate import upgrade

from omn import create_app
from omn.config import TestConfig
from omn.extensions import db

PG_URL = (os.getenv('DATABASE_URL') or '').strip()
pytestmark = pytest.mark.skipif(not PG_URL, reason='Sandbox gibt es nur auf PostgreSQL')
SCHEMAS = ('sandbox', 'sandbox_private', 'live', 'live_private', 'biocomm_common')


def _leeren():
    db.drop_all()
    db.session.execute(db.text('DROP TABLE IF EXISTS alembic_version'))
    db.session.execute(db.text('DROP SCHEMA IF EXISTS ' + ', '.join(SCHEMAS) + ' CASCADE'))
    db.session.commit()


@pytest.fixture(scope='module')
def gen_app():
    class _Cfg(TestConfig):
        SQLALCHEMY_DATABASE_URI = PG_URL

    app = create_app(_Cfg, instance_path=tempfile.mkdtemp(suffix='_sbx'))
    with app.app_context():
        _leeren()
        upgrade()
        from omn.sandbox.generator import Generator, Zeitraum
        Generator(db.engine, Zeitraum(tage=20), log=lambda *_: None).alle()
    yield app
    with app.app_context():
        _leeren()
        db.session.remove()
        db.engine.dispose()


def _eins(sql, **p):
    # Transaktion sofort beenden: eine offen gehaltene Lese-Transaktion wuerde
    # das TRUNCATE von zuruecksetzen() (andere Verbindung) endlos blockieren.
    wert = db.session.execute(db.text(sql), p).scalar()
    db.session.rollback()
    return wert


def _minuten(serie_like, von, bis):
    return dict(db.session.execute(db.text(
        "SELECT a.bucket_start, a.value_mean FROM sandbox.derived_aggregate a"
        " JOIN sandbox.measurement_channel mc ON mc.id = a.measurement_channel_id"
        " JOIN sandbox.acquisition_run r ON r.id = mc.acquisition_run_id"
        " JOIN sandbox.series s ON s.id = r.series_id"
        " WHERE a.resolution = '1min' AND mc.quantity_code = 'bioelectric_potential'"
        " AND s.series_code LIKE :s AND a.bucket_start >= :v AND a.bucket_start < :b"),
        {'s': serie_like, 'v': von, 'b': bis}).all())


def _minuten_frei(serie_like, von, bis):
    werte = _minuten(serie_like, von, bis)
    db.session.rollback()
    return werte


def test_umfang_und_trennung(gen_app):
    with gen_app.app_context():
        assert _eins('SELECT count(*) FROM sandbox.sandbox_scenario WHERE is_public') == 6
        assert _eins('SELECT count(*) FROM sandbox.series') == 13
        assert _eins('SELECT count(*) FROM sandbox_private.site_location_private') == 4
        # nichts in live
        for t in ('site', 'series', 'sample_block', 'derived_aggregate', 'origin_batch'):
            assert _eins(f'SELECT count(*) FROM live.{t}') == 0
        # jede Szenario-Beschreibung sagt, dass es Simulation ist
        assert _eins("SELECT count(*) FROM sandbox.sandbox_scenario WHERE model_assumption_note NOT LIKE 'SIMULATION.%'") == 0


def test_stimulation_gegen_kontrolle(gen_app):
    """Bis zur Stimulation (13.01. 10:15 Berlin = 09:15 UTC) sind Stimulations- und
    Kontrollreihe identisch; danach ist die Differenz genau die angenommene,
    abklingende Reaktion."""
    with gen_app.app_context():
        st = _minuten_frei('SBX-elektrisch-E-ST%', '2025-01-13 09:00Z', '2025-01-13 10:00Z')
        ko = _minuten_frei('SBX-elektrisch-E-KO%', '2025-01-13 09:00Z', '2025-01-13 10:00Z')
        assert set(st) == set(ko) and len(st) >= 55
        vorher = [abs(st[t] - ko[t]) for t in st if t.minute < 15]
        nachher = {t.minute: st[t] - ko[t] for t in st if t.minute >= 16}
        assert max(vorher) < 1e-9
        assert nachher[16] > 3                       # sichtbar
        assert nachher[16] > nachher[30] > nachher[50] >= 0   # klingt ab


def test_ec_pause_und_neustart_luecke(gen_app):
    with gen_app.app_context():
        # Rohdaten beginnen stuendlich erst nach EC-Messung + Einschwingzeit
        assert _eins("SELECT min(extract(second FROM time_anchor)) FROM sandbox.sample_block sb"
                     " JOIN sandbox.measurement_channel mc ON mc.id = sb.measurement_channel_id"
                     " WHERE mc.quantity_code = 'bioelectric_potential' AND extract(minute FROM time_anchor) = 0") == 35
        # Datenqualitaet: Watchdog-Neustart 13.01. 10:20-10:27 Stockholm -> zwei Runs, Luecke ohne Werte
        assert _eins("SELECT count(*) FROM sandbox.acquisition_run r JOIN sandbox.series s ON s.id = r.series_id"
                     " WHERE s.series_code LIKE 'SBX-datenq%' AND r.reset_cause = 'WATCHDOG_HW'") == 1
        m = _minuten_frei('SBX-datenq%', '2025-01-13 09:20Z', '2025-01-13 09:27Z')
        assert m == {}                               # Luecke, keine Nullen
        erwartet, ist = db.session.execute(db.text(
            "SELECT a.samples_expected, a.samples_recorded FROM sandbox.derived_aggregate a"
            " JOIN sandbox.measurement_channel mc ON mc.id = a.measurement_channel_id"
            " JOIN sandbox.acquisition_run r ON r.id = mc.acquisition_run_id JOIN sandbox.series s ON s.id = r.series_id"
            " WHERE s.series_code LIKE 'SBX-datenq%' AND a.resolution = '1h'"
            " AND mc.quantity_code = 'bioelectric_potential' AND a.bucket_start = '2025-01-13 09:00Z'")).one()
        db.session.rollback()
        assert erwartet - ist == 420 * 250           # 7 min fehlen, als fehlend erkennbar


def test_hash_kette_und_anlieferung(gen_app):
    with gen_app.app_context():
        assert _eins(
            "SELECT count(*) FROM sandbox.origin_batch b LEFT JOIN sandbox.origin_batch v"
            " ON v.acquisition_run_id = b.acquisition_run_id AND v.batch_sequence_no = b.batch_sequence_no - 1"
            " WHERE b.previous_batch_hash IS DISTINCT FROM coalesce(v.batch_hash, decode(repeat('00', 32), 'hex'))") == 0
        # 8.1.1: jede per LoRa gelieferte Telemetrie kommt per SD noch einmal (DUPLICATE)
        assert _eins("SELECT count(*) FROM sandbox.batch_delivery WHERE transport_code = 'LORA'") == \
            _eins("SELECT count(*) FROM sandbox.batch_delivery WHERE delivery_status = 'DUPLICATE'")


def test_idempotent_und_reproduzierbar(gen_app):
    """Zweiter Lauf ueberspringt vorhandene Versionen; nach dem Zuruecksetzen
    entstehen bytegleich dieselben Rohdaten (feste Seeds)."""
    from omn.sandbox.generator import Generator, Zeitraum, zuruecksetzen
    with gen_app.app_context():
        vorher = _eins("SELECT md5(string_agg(encode(payload_hash, 'hex'), '' ORDER BY payload_hash))"
                       " FROM sandbox.sample_block")
        n = _eins('SELECT count(*) FROM sandbox.sample_block')
        Generator(db.engine, Zeitraum(tage=20), log=lambda *_: None).alle()
        assert _eins('SELECT count(*) FROM sandbox.sample_block') == n
        zuruecksetzen(db.engine)
        assert _eins('SELECT count(*) FROM sandbox.series') == 0
        assert _eins('SELECT count(*) FROM sandbox.ref_unit') > 0          # Stammdaten bleiben
        Generator(db.engine, Zeitraum(tage=20), log=lambda *_: None).alle(nur={'elektrisch', 'datenqualitaet'})
        Generator(db.engine, Zeitraum(tage=20), log=lambda *_: None).alle()
        nachher = _eins("SELECT md5(string_agg(encode(payload_hash, 'hex'), '' ORDER BY payload_hash))"
                        " FROM sandbox.sample_block")
    assert nachher == vorher
