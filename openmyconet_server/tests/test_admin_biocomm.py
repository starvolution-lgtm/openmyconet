"""BioComm-Verwaltung im Admin (/admin/biocomm), Stammdaten-Logik (omn/eingang/verwaltung.py)
und das MGRS-Rasterfeld (omn/eingang/raster.py).

Die Datenbank-Tests laufen nur mit PostgreSQL (Fixture aus test_dateneingang).
"""
import re

import pytest
import sqlalchemy as sa
from test_dateneingang import PG_URL, _eins, _knoten, ein_app  # noqa: F401  (Fixture)

from omn.eingang.raster import mgrs_10km
from omn.extensions import db

nur_pg = pytest.mark.skipif(not PG_URL, reason='BioComm gibt es nur auf PostgreSQL')
URL = '/admin/biocomm'


# ---------------------------------------------------------------------------
# Rasterfeld (ohne Datenbank)
# ---------------------------------------------------------------------------
def test_rasterfeld_wie_die_gepruefen_sandbox_standorte():
    from omn.sandbox.szenarien import STANDORTE
    for s in STANDORTE.values():                    # damals mit mgrs + pyproj gegengeprueft
        assert mgrs_10km(s.breite, s.laenge) == s.mgrs_10km, s.code


@pytest.mark.parametrize('breite, laenge, erwartet', [
    (38.8895, -77.0353, '18SUJ20'),                 # Washington Monument (18SUJ 23393 06500)
    (60.0, 5.5, '32VLM'),                           # Suedwestnorwegen: Sonderzone 32 statt 31 (Rechtswert ~305 km)
    (78.2, 15.6, '33XWG'),                          # Spitzbergen: Sonderzone 33
])
def test_rasterfeld_referenzpunkte_und_sonderzonen(breite, laenge, erwartet):
    assert mgrs_10km(breite, laenge).startswith(erwartet)


@pytest.mark.parametrize('breite, laenge', [(85, 0), (-81, 0), (10, 190)])
def test_rasterfeld_ausserhalb(breite, laenge):
    with pytest.raises(ValueError):
        mgrs_10km(breite, laenge)


# ---------------------------------------------------------------------------
# Zugang (alle Engines)
# ---------------------------------------------------------------------------
def test_nur_superadmin(app, client, editor):
    assert client.get(URL).status_code == 302                      # nicht angemeldet -> Login
    with client.session_transaction() as s:
        s['admin_logged_in'], s['admin_role'] = True, 'editor'
    assert client.get(URL).status_code == 403


def test_ohne_postgresql_hinweis(app, client):
    if app.extensions['sqlalchemy'].engines[None].dialect.name == 'postgresql':
        pytest.skip('nur ohne PostgreSQL')
    with client.session_transaction() as s:
        s['admin_logged_in'], s['admin_role'] = True, 'superadmin'
    r = client.get(URL)
    assert r.status_code == 200 and 'nur auf PostgreSQL' in r.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Masken (PostgreSQL)
# ---------------------------------------------------------------------------
def _admin(app):
    c = app.test_client()
    with c.session_transaction() as s:
        s['admin_logged_in'], s['admin_role'], s['admin_username'] = True, 'superadmin', 'robby'
    return c


def _post(c, **daten):
    daten.setdefault('schema', 'sandbox')
    return c.post(URL, data=daten, follow_redirects=True)


@nur_pg
def test_ablauf_standort_bis_einsatz(ein_app):  # noqa: F811
    with ein_app.app_context():
        c = _admin(ein_app)
        r = _post(c, aktion='standort', code='SBX-ADMIN-01', breite='50,64', laenge='9.05', zeitzone='Europe/Berlin',
                  hoehe='404')
        assert 'Rasterfeld 32UNB00' in r.get_data(as_text=True)
        assert _eins("SELECT grid_cell_id || ' ' || elevation_m_rounded FROM sandbox.site WHERE site_code = 'SBX-ADMIN-01'") \
            == '32UNB00 400'
        assert _eins("SELECT iana_tz FROM sandbox.site_timezone z JOIN sandbox.site s ON s.id = z.site_id"
                     " WHERE s.site_code = 'SBX-ADMIN-01'") == 'Europe/Berlin'
        # die Koordinaten stehen nirgends
        assert _eins("SELECT count(*) FROM sandbox_private.site_location_private p JOIN sandbox.site s ON s.id = p.site_id"
                     " WHERE s.site_code = 'SBX-ADMIN-01'") == 0

        _post(c, aktion='reihe', code='SBX-ADMIN-REIHE', titel='Admin-Test', standort='SBX-ADMIN-01', substrat='SOIL',
              von='2026-10-01', bis='', kontext='Beet 3')
        assert _eins("SELECT title FROM sandbox.series WHERE series_code = 'SBX-ADMIN-REIHE'") == 'Admin-Test'

        _post(c, aktion='geraet', seriennummer='SBX-NODE-ADMIN-01', rolle='NODE', notiz='Test')
        r = _post(c, aktion='einsatz', geraet='SBX-NODE-ADMIN-01', reihe='SBX-ADMIN-REIHE', ab='2026-10-01T08:00')
        assert 'misst jetzt für SBX-ADMIN-REIHE' in r.get_data(as_text=True)
        # Ortszeit 08:00 in Berlin (Sommerzeit) = 06:00 UTC
        assert str(_eins("SELECT valid_from AT TIME ZONE 'UTC' FROM sandbox.device_deployment e"
                         " JOIN sandbox.device d ON d.id = e.device_id WHERE d.device_serial = 'SBX-NODE-ADMIN-01'")) \
            == '2026-10-01 06:00:00'
        seite = c.get(URL + '?schema=sandbox').get_data(as_text=True)
        assert 'SBX-ADMIN-REIHE seit 01.10.2026' in seite


@nur_pg
def test_fehler_werden_angezeigt_statt_absturz(ein_app):  # noqa: F811
    with ein_app.app_context():
        c = _admin(ein_app)
        for daten, text in (
                (dict(aktion='standort', schema='live', code='SBX-FALSCH', breite='50', laenge='9', zeitzone='Europe/Berlin'),
                 'darf nicht mit SBX- beginnen'),
                (dict(aktion='standort', code='SBX-X', breite='abc', laenge='9', zeitzone='Europe/Berlin'), 'Koordinaten'),
                (dict(aktion='standort', code='SBX-Y', breite='50', laenge='9', zeitzone='Mars/Olympus'), 'Zeitzone'),
                (dict(aktion='reihe', code='SBX-R', titel='x', standort='SBX-GIBTSNICHT', substrat='SOIL'), 'unbekannt'),
                (dict(aktion='geraet', seriennummer='OHNE-SBX', rolle='NODE'), 'muss mit SBX- beginnen'),
                (dict(aktion='konflikt', batch='1', grund=''), 'Begründung'),
                (dict(aktion='unsinn'), 'Unbekannte Aktion')):
            r = _post(c, **daten)
            assert r.status_code == 200 and text in r.get_data(as_text=True), text


@nur_pg
def test_zugangsschluessel_nur_einmal_sichtbar(ein_app):  # noqa: F811
    with ein_app.app_context():
        c = _admin(ein_app)
        _post(c, aktion='geraet', seriennummer='SBX-BRIDGE-ADMIN', rolle='BRIDGE')
        r = _post(c, aktion='zugang', geraet='SBX-BRIDGE-ADMIN', bezeichnung='Garten')
        html = r.get_data(as_text=True)
        schluessel = re.search(r'<code>(omnb_[^<]+)</code>', html).group(1)
        with c.session_transaction() as s:
            assert schluessel not in str(dict(s))                 # nicht in der Session / im Flash
        nachher = c.get(URL + '?schema=sandbox').get_data(as_text=True)
        assert schluessel not in nachher and 'Garten' in nachher
        nr = _eins("SELECT k.id FROM sandbox.device_credential k JOIN sandbox.device d ON d.id = k.device_id"
                   " WHERE d.device_serial = 'SBX-BRIDGE-ADMIN'")
        _post(c, aktion='zugang_widerrufen', geraet='SBX-BRIDGE-ADMIN', nr=str(nr))
        assert _eins('SELECT revoked_at IS NOT NULL FROM sandbox.device_credential WHERE id = :i', i=nr) is True


@nur_pg
def test_signaturschluessel_registrieren_und_widerrufen(ein_app):  # noqa: F811
    from omn.eingang import signatur
    with ein_app.app_context():
        c = _admin(ein_app)
        _post(c, aktion='geraet', seriennummer='SBX-NODE-ADMIN-SIG', rolle='NODE')
        pub = signatur.oeffentlicher_schluessel(signatur.seed_aus_efuse(b'admin-test' * 4)).hex()
        r = _post(c, aktion='signatur', geraet='SBX-NODE-ADMIN-SIG', public_key=pub, bezeichnung='Platine 1')
        assert 'registriert' in r.get_data(as_text=True) and pub[:16] in r.get_data(as_text=True)
        nr = _eins('SELECT id FROM sandbox.device_signing_key WHERE public_key = decode(:p, \'hex\')', p=pub)
        _post(c, aktion='signatur_widerrufen', geraet='SBX-NODE-ADMIN-SIG', nr=str(nr))
        assert _eins('SELECT revoked_at IS NOT NULL FROM sandbox.device_signing_key WHERE id = :i', i=nr) is True


@nur_pg
def test_konflikt_per_maske_aufloesen(ein_app):  # noqa: F811
    from omn.eingang.einlesen import einliefern
    from omn.eingang.formate import paket_schreiben
    with ein_app.app_context():
        k = _knoten('ADMIN-KONFLIKT')
        p1, _ = k.pakete(2)
        einliefern(db.engine, paket_schreiben(p1))
        einliefern(db.engine, paket_schreiben(k.pakete(2)[1]))
        zweiter = einliefern(db.engine, paket_schreiben(k.paket(2, p1.batch_hash, variante=1))).batch_id
        c = _admin(ein_app)
        assert f'Batch {zweiter}' in c.get(URL + '?schema=sandbox').get_data(as_text=True)
        r = _post(c, aktion='konflikt', batch=str(zweiter), grund='Kandidat von der SD-Karte')
        assert 'Konflikt aufgelöst' in r.get_data(as_text=True)
        assert _eins('SELECT batch_status FROM sandbox.origin_batch WHERE id = :i', i=zweiter) == 'CANONICAL'
        assert _eins('SELECT performed_by FROM sandbox.candidate_resolution_log WHERE origin_batch_id = :i ORDER BY id DESC LIMIT 1',
                     i=zweiter) == 'robby'


@nur_pg
def test_befehle_standort_und_reihe(ein_app):  # noqa: F811
    with ein_app.app_context():
        runner = ein_app.test_cli_runner()
        r = runner.invoke(args=['biocomm-standort', 'SBX-CLI-01', '--breite', '-34.83', '--laenge', '-56.05',
                                '--zeitzone', 'America/Montevideo', '--schema', 'sandbox'])
        assert r.exit_code == 0 and '21HWB84' in r.output and 'nicht gespeichert' in r.output
        r = runner.invoke(args=['biocomm-reihe', 'SBX-CLI-REIHE', '--standort', 'SBX-CLI-01', '--substrat', 'COMPOST',
                                '--titel', 'CLI-Test', '--schema', 'sandbox'])
        assert r.exit_code == 0, r.output
        doppelt = runner.invoke(args=['biocomm-reihe', 'SBX-CLI-REIHE', '--standort', 'SBX-CLI-01', '--substrat',
                                      'COMPOST', '--titel', 'x', '--schema', 'sandbox'])
        assert doppelt.exit_code != 0 and 'gibt es schon' in doppelt.output
        with db.engine.connect() as con:
            assert con.execute(sa.text("SELECT substrate_code FROM sandbox.series WHERE series_code = 'SBX-CLI-REIHE'")
                               ).scalar() == 'COMPOST'
