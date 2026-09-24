"""BioComm-Datenlabor (omn/datenlabor.py).

Zugang (alle Engines): nur eingeloggte UND bestaetigte Nutzer; Seite leitet
sonst auf den Login, die API antwortet 401 JSON. Auf SQLite gibt es keine
Sandbox -> leerer Zustand statt Fehler.

Daten (nur PostgreSQL): 20 generierte Tage (enthaelt die Winter-Stichwoche ab
13.01.2025 mit Minutenwerten, Rohdatenstunde 10-11 Uhr Ortszeit und der
Stimulation um 10:15 Uhr).
"""
import os
import tempfile

import pytest
from flask_migrate import upgrade

from omn import create_app
from omn.config import TestConfig
from omn.extensions import db
from omn.models import Nutzer

API = '/dashboard/datenlabor/api'
PG_URL = (os.getenv('DATABASE_URL') or '').strip()
nur_pg = pytest.mark.skipif(not PG_URL, reason='Sandbox gibt es nur auf PostgreSQL')


def _nutzer(bestaetigt=True, email='labor@example.org'):
    n = Nutzer(name='Labor', email=email, bestaetigt=bestaetigt)
    db.session.add(n)
    db.session.commit()
    return n.id


def _einloggen(client, nutzer_id):
    with client.session_transaction() as sess:
        sess['nutzer_logged_in'] = True
        sess['nutzer_id'] = nutzer_id


# ---------------------------------------------------------------------------
# Zugang + leerer Zustand (SQLite lokal, PG in der CI-Matrix)
# ---------------------------------------------------------------------------
def test_ohne_login_kein_zugang(app):
    c = app.test_client()
    r = c.get('/dashboard/datenlabor')
    assert r.status_code == 302 and '/dashboard/login' in r.headers['Location']
    for pfad in ('/szenarien', '/reihe?reihe=1&von=2025-01-01T00:00Z&bis=2025-01-02T00:00Z', '/roh?reihe=1&von=2025-01-01T00:00Z'):
        r = c.get(API + pfad)
        assert r.status_code == 401
        assert r.get_json()['is_simulated'] is True


def test_unbestaetigt_kein_zugang(app):
    c = app.test_client()
    _einloggen(c, _nutzer(bestaetigt=False))
    assert c.get('/dashboard/datenlabor').status_code == 302
    assert c.get(API + '/szenarien').status_code == 401


def test_geloeschter_nutzer_kein_zugang(app):
    c = app.test_client()
    _einloggen(c, 9999)
    assert c.get(API + '/szenarien').status_code == 401


def test_seite_und_leerer_zustand(app):
    c = app.test_client()
    _einloggen(c, _nutzer())
    r = c.get('/dashboard/datenlabor')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'SIMULATION' in html and 'datenlabor.js' in html and 'dl-breit' in html
    j = c.get(API + '/szenarien').get_json()
    assert j == {'szenarien': [], 'is_simulated': True}
    assert c.get(API + '/reihe?reihe=1').get_json()['punkte'] == []
    assert c.get(API + '/roh?reihe=1').get_json()['samples'] == []


def test_link_im_nutzer_dashboard(app):
    c = app.test_client()
    _einloggen(c, _nutzer())
    assert '/dashboard/datenlabor' in c.get('/dashboard/basis').get_data(as_text=True)


# ---------------------------------------------------------------------------
# Daten (PostgreSQL)
# ---------------------------------------------------------------------------
SCHEMAS = ('sandbox', 'sandbox_private', 'live', 'live_private', 'biocomm_common')


def _leeren():
    db.drop_all()
    db.session.execute(db.text('DROP TABLE IF EXISTS alembic_version'))
    db.session.execute(db.text('DROP SCHEMA IF EXISTS ' + ', '.join(SCHEMAS) + ' CASCADE'))
    db.session.commit()


@pytest.fixture(scope='module')
def labor():
    class _Cfg(TestConfig):
        SQLALCHEMY_DATABASE_URI = PG_URL

    app = create_app(_Cfg, instance_path=tempfile.mkdtemp(suffix='_labor'))
    with app.app_context():
        _leeren()
        upgrade()
        from omn.sandbox.generator import Generator, Zeitraum
        Generator(db.engine, Zeitraum(tage=20), log=lambda *_: None).alle()
        nid = _nutzer()
        db.session.remove()
    c = app.test_client()
    _einloggen(c, nid)
    yield c
    with app.app_context():
        _leeren()
        db.session.remove()
        db.engine.dispose()


def _reihe(labor, code):
    for sc in labor.get(API + '/szenarien').get_json()['szenarien']:
        for r in sc['reihen']:
            if r['code'] == code:
                return r
    raise AssertionError(code)


def _codes(labor):
    return {r['code']: r for sc in labor.get(API + '/szenarien').get_json()['szenarien'] for r in sc['reihen']}


@nur_pg
def test_szenarien(labor):
    j = labor.get(API + '/szenarien').get_json()
    assert j['is_simulated'] is True
    assert len(j['szenarien']) == 6
    assert all(sc['hinweis'].startswith('SIMULATION – berechnete Messwerte') for sc in j['szenarien'])
    reihen = _codes(labor)
    assert len(reihen) == 13
    nach_standort = {r['standort']: r for r in reihen.values()}
    assert nach_standort['SBX-SOUTH-01']['hemisphaere'] == 'S'
    assert nach_standort['SBX-DE-01']['hemisphaere'] == 'N'
    assert nach_standort['SBX-LOWLAT-01']['aequatornah'] is True
    assert not nach_standort['SBX-DE-01']['aequatornah']
    # keine exakten Koordinaten in der Antwort
    text = labor.get(API + '/szenarien').get_data(as_text=True)
    assert '50.64' not in text and '9.05' not in text
    stim = [r for r in reihen.values() if r['mit_stimulation']]
    assert stim and all(r['rolle'] == 'PRIMARY' for r in stim)
    de = next(r for r in reihen.values() if r['standort'] == 'SBX-DE-01' and r['mit_stimulation'])
    assert '2025-01-13T09:00:00+00:00' in de['roh_stunden']          # 10 Uhr Berlin
    assert 'bioelectric_potential' in de['kanaele'] and 'soil_temperature' in de['kanaele']


@nur_pg
def test_reihe_minutenwerte_mit_stimulation(labor):
    r = next(x for x in _codes(labor).values() if x['mit_stimulation'])
    j = labor.get(API + f"/reihe?reihe={r['id']}&von=2025-01-12T23:00:00Z&bis=2025-01-13T23:00:00Z").get_json()
    assert j['is_simulated'] is True and j['aufloesung'] == '1min' and j['einheit'] == 'µV'
    assert 1300 < len(j['punkte']) <= 1440
    for p in j['punkte'][:50]:
        assert p[1] <= p[3] <= p[2]
    ausgefuehrt = [s for s in j['stimulationen'] if s['zustand'] == 'EXECUTED']
    assert ausgefuehrt and ausgefuehrt[0]['geplant'] == 1736759700000    # 13.01.2025 10:15 Berlin
    assert 0 <= ausgefuehrt[0]['start'] - ausgefuehrt[0]['geplant'] < 10_000   # Ist-Start mit Geraeteverzug


@nur_pg
def test_reihe_aufloesungen(labor):
    r = _reihe(labor, next(iter(_codes(labor))))
    wo = labor.get(API + f"/reihe?reihe={r['id']}&von=2025-01-01T00:00:00Z&bis=2025-01-08T00:00:00Z").get_json()
    assert wo['aufloesung'] == '1h' and 150 < len(wo['punkte']) <= 168
    jahr = labor.get(API + f"/reihe?reihe={r['id']}&von=2025-01-01T00:00:00Z&bis=2026-01-01T00:00:00Z").get_json()
    assert jahr['aufloesung'] == '1d'
    assert 19 <= len(jahr['punkte']) <= 21          # nur 20 generierte Tage: der Rest ist Luecke, keine Nullen
    umwelt = labor.get(API + f"/reihe?reihe={r['id']}&kanal=soil_temperature&von=2025-01-01T00:00:00Z&bis=2025-01-02T00:00:00Z").get_json()
    assert umwelt['einheit'] == '°C' and umwelt['punkte'] and umwelt['stimulationen'] == []


@nur_pg
def test_reihe_eingaben(labor):
    r = _reihe(labor, next(iter(_codes(labor))))
    assert labor.get(API + f"/reihe?reihe={r['id']}&kanal=rm%20-rf&von=2025-01-01T00:00Z&bis=2025-01-02T00:00Z").status_code == 400
    assert labor.get(API + f"/reihe?reihe={r['id']}&von=kaputt&bis=2025-01-02T00:00Z").status_code == 400
    assert labor.get(API + f"/reihe?reihe={r['id']}&von=2025-01-02T00:00Z&bis=2025-01-01T00:00Z").status_code == 400
    assert labor.get(API + "/reihe?reihe=999999&von=2025-01-01T00:00Z&bis=2025-01-02T00:00Z").status_code == 404
    assert labor.get(API + f"/roh?reihe={r['id']}&von=2025-01-13T09:15:00Z&dauer=31").status_code == 400


@nur_pg
def test_rohdaten_kalibriert(labor):
    r = next(x for x in _codes(labor).values() if x['mit_stimulation'])
    j = labor.get(API + f"/roh?reihe={r['id']}&von=2025-01-13T09:15:00Z&dauer=10").get_json()
    assert j['is_simulated'] is True and j['einheit'] == 'µV'
    s = j['samples']
    assert len(s) in (2500, 2501)
    # Herkunft der Umrechnung kommt aus dem Messkanal, nicht aus Konstanten
    assert j['rate_hz'] == 250
    assert j['quelle']['lsb_uv'] == 7.8125 and j['quelle']['gain'] == 100 and j['quelle']['gain_quelle'] == 'MANUAL'
    idx = [x[2] for x in s]
    assert idx == sorted(idx) and idx[-1] - idx[0] == len(s) - 1
    # Umrechnung Zaehlwert * 7,8125 uV / Verstaerkung 100 -> Vielfache von 0,078125
    for x in s[:200]:
        assert abs(x[1] / 0.078125 - round(x[1] / 0.078125)) < 0.02
    # EC-Messfenster hh:00:00-00:35: planmaessige Aufzeichnungspause -> keine Samples
    pause = labor.get(API + f"/roh?reihe={r['id']}&von=2025-01-13T09:00:05Z&dauer=10").get_json()
    assert pause['samples'] == []


# ---------------------------------------------------------------------------
# Oeffentliche Erklaerseite /biocomm/datenlabor
# ---------------------------------------------------------------------------
def test_erklaerseite_oeffentlich(app):
    c = app.test_client()
    r = c.get('/biocomm/datenlabor')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Das BioComm-Datenlabor' in html
    assert 'datenlabor_vorschau.webp' in html
    assert 'index.html#anmelden' in html and 'dashboard/login' in html
    assert 'kein Wirkungsnachweis' in html
    # andere Sprache kommt serverseitig an
    assert 'The BioComm Data Lab' in c.get('/biocomm/datenlabor?lang=en').get_data(as_text=True)


def test_erklaerseite_verlinkt(app):
    c = app.test_client()
    for pfad in ('/biocomm', '/biocomm/software', '/'):
        assert 'biocomm/datenlabor' in c.get(pfad).get_data(as_text=True), pfad
    from pathlib import Path
    static = Path(app.root_path).parent / 'app' / 'static'
    assert 'biocomm/datenlabor' in (static / 'sitemap.xml').read_text(encoding='utf-8')
    assert (static / 'datenlabor_vorschau.webp').stat().st_size > 10_000
