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


@nur_pg
def test_api_liefert_die_gewaehlte_sprache(labor):
    antwort = labor.get(API + '/szenarien?lang=en')
    assert antwort.status_code == 200, antwort.get_data(as_text=True)[:2000]
    j = antwort.get_json()
    nach_key = {s['key']: s for s in j['szenarien']}
    assert nach_key['optisch']['label'] == 'Optical stimulation'
    assert all(s['hinweis'].startswith('SIMULATION – calculated') for s in j['szenarien'])
    assert j['kanaele']['soil_temperature']['name'] == 'Soil temperature'
    r = next(x for x in _codes(labor).values() if x['mit_stimulation'])
    fr = labor.get(API + f"/reihe?reihe={r['id']}&kanal=soil_temperature&lang=fr"
                   "&von=2025-01-12T23:00:00Z&bis=2025-01-13T23:00:00Z").get_json()
    assert fr['name'] == 'Température du sol'
    unbekannt = labor.get(API + '/szenarien?lang=xx').get_json()
    assert {s['key']: s for s in unbekannt['szenarien']}['optisch']['label'] == 'Optische Stimulation'


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


# ---------------------------------------------------------------------------
# Sprachen (omn/datenlabor_texte.json)
# ---------------------------------------------------------------------------
def _platzhalter(text):
    import re
    return set(re.findall(r'\{(\w+)\}', text))


def test_texte_in_allen_sprachen_vollstaendig():
    from omn.datenlabor import KANAELE, TEXTE
    from omn.i18n import LANGS
    from omn.sandbox.szenarien import SZENARIEN
    de = TEXTE['de']
    for lang in LANGS:
        t = TEXTE[lang]
        assert set(t['ui']) == set(de['ui']), lang
        for k, v in t['ui'].items():
            assert _platzhalter(v) == _platzhalter(de['ui'][k]), (lang, k)
            assert v.strip() or k == 'volle_stunde', (lang, k)
        assert set(t['kanaele']) == set(KANAELE), lang
        assert set(t['generator']) == set(de['generator']), lang
        assert t['locale'].startswith(lang), lang
        if lang == 'de':
            continue
        sz = t['szenarien']
        assert _platzhalter(sz['hinweis_simulation']) == {'generator', 'modell'}, lang
        assert set(sz['szenarien']) == {s.key for s in SZENARIEN}, lang
        for key, e in sz['szenarien'].items():
            assert e['label'] and e['kurz'] and e['zusatz'], (lang, key)


def test_szenario_texte_nur_bei_aktuellem_deutsch():
    from omn.datenlabor import szenario_texte
    from omn.sandbox.szenarien import SZENARIEN
    s = next(x for x in SZENARIEN if x.key == 'elektrisch')
    en = szenario_texte(s.key, s.label, s.kurz, s.annahme, s.stim_parameterquelle, 'en')
    assert en['label'] == 'Electrical stimulation'
    assert en['hinweis'].startswith('SIMULATION – calculated measurements') and 'sbx-gen-1.0' in en['hinweis']
    assert 'ARBITRARY_DEMO' in en['stimulationsparameter']
    # ein deutscher Text in der Datenbank weicht ab -> genau dieser bleibt Deutsch, die anderen werden uebersetzt
    alt = szenario_texte(s.key, s.label, s.kurz + ' (geaendert)', s.annahme, s.stim_parameterquelle, 'en')
    assert alt['kurz'].endswith('(geaendert)') and alt['label'] == 'Electrical stimulation'
    assert alt['hinweis'] == en['hinweis']
    alter_hinweis = szenario_texte(s.key, s.label, s.kurz, s.annahme[:-5], s.stim_parameterquelle, 'es')
    assert alter_hinweis['hinweis'] == s.annahme[:-5] and alter_hinweis['label'] == 'Estimulación eléctrica'
    assert szenario_texte(s.key, s.label, s.kurz, s.annahme, s.stim_parameterquelle, 'de')['label'] == s.label
    b = next(x for x in SZENARIEN if x.key == 'baseline')
    assert szenario_texte(b.key, b.label, b.kurz, b.annahme, None, 'fr')['stimulationsparameter'] is None


def test_seite_in_der_sprache_des_nutzers(app):
    c = app.test_client()
    nid = _nutzer(email='en@example.org')
    n = db.session.get(Nutzer, nid)
    n.sprache = 'en'
    db.session.commit()
    _einloggen(c, nid)
    html = c.get('/dashboard/datenlabor').get_data(as_text=True)
    assert '<html lang="en">' in html and 'BioComm <em>Data Lab</em>' in html
    assert 'calculated measurements, real data processing' in html and 'Log out' in html
    assert 'data-locale="en-GB"' in html and 'aria-current="true">English' in html
    # ?lang= und der Cookie der Website haben Vorrang vor der Registrierungssprache
    assert 'Labo de données' in c.get('/dashboard/datenlabor?lang=fr').get_data(as_text=True)
    assert '<html lang="fr">' in c.get('/dashboard/datenlabor').get_data(as_text=True)   # Wahl bleibt (Cookie)
    c2 = app.test_client()
    _einloggen(c2, nid)
    c2.set_cookie('omn_lang', 'nl', domain=app.config.get('SERVER_NAME') or 'localhost')
    assert '<html lang="nl">' in c2.get('/dashboard/datenlabor').get_data(as_text=True)
    # die uebrigen Dashboard-Seiten bleiben deutsch
    assert '<html lang="de">' in c.get('/dashboard/basis').get_data(as_text=True)


def test_seite_ohne_angabe_deutsch(app):
    c = app.test_client()
    _einloggen(c, _nutzer(email='de@example.org'))
    html = c.get('/dashboard/datenlabor?lang=xx').get_data(as_text=True)
    assert '<html lang="de">' in html and 'BioComm-<em>Datenlabor</em>' in html
    assert 'id="dl-texte"' in html
