"""Empfangsweg fuer Bridges (omn/eingang/empfang.py): POST /api/v2/biocomm/paket.

Die Datenbank-Tests laufen nur mit PostgreSQL (Fixture aus test_dateneingang).
Jeder Test nutzt eine eigene Absender-IP (X-Forwarded-For), weil die Sperre
nach Fehlversuchen je IP in Dateien im Temp-Ordner zaehlt.
"""
import random
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from test_dateneingang import PG_URL, _eins, _vorbereiten, ein_app  # noqa: F401  (Fixture)

import pytest
from omn.extensions import db

URL = '/api/v2/biocomm/paket'
nur_pg = pytest.mark.skipif(not PG_URL, reason='Dateneingang gibt es nur auf PostgreSQL')


def _ip():
    return f'203.0.{random.randint(0, 255)}.{random.randint(1, 254)}'


def _bridge(name, schema='sandbox', rolle='BRIDGE'):
    from omn.eingang.empfang import schluessel_anlegen
    serial = f'SBX-BRIDGE-{name}' if schema == 'sandbox' else f'OMN-BRIDGE-TEST-{name}'
    with db.engine.begin() as c:
        c.execute(sa.text(f"INSERT INTO {schema}.device (device_serial, device_role) VALUES (:g, :r)"),
                  {'g': serial, 'r': rolle})
    return serial, schluessel_anlegen(db.engine, schema, serial, 'Test')[1]


def _senden(client, roh, schluessel=None, ip=None, **kopf):
    h = {'X-Forwarded-For': ip or _ip(), 'Content-Type': 'application/octet-stream', 'X-OMN-Transport': 'LORA'}
    if schluessel:
        h['Authorization'] = f'Bearer {schluessel}'
    h.update({k.replace('_', '-'): v for k, v in kopf.items() if v is not None})
    for k in [k for k, v in kopf.items() if v is None]:
        h.pop(k.replace('_', '-'), None)
    return client.post(URL, data=roh, headers=h)


# ---------------------------------------------------------------------------
# ohne Datenbank-Abhaengigkeit
# ---------------------------------------------------------------------------
def test_echte_absender_ip_hinter_nginx(app):
    """ProxyFix x_for=1: remote_addr ist die IP aus X-Forwarded-For, nicht nginx (127.0.0.1)."""
    from flask import request

    @app.route('/_test_ip')
    def _test_ip():
        return request.remote_addr

    c = app.test_client()
    assert c.get('/_test_ip', headers={'X-Forwarded-For': '203.0.113.7'}).get_data(as_text=True) == '203.0.113.7'
    assert c.get('/_test_ip').get_data(as_text=True) == '127.0.0.1'


def test_ohne_postgresql_nicht_verfuegbar(app):
    if app.extensions['sqlalchemy'].engines[None].dialect.name == 'postgresql':
        pytest.skip('nur ohne PostgreSQL')
    r = app.test_client().post(URL, data=b'x')
    assert r.status_code == 503


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------
@nur_pg
def test_anmeldung_der_bridge(ein_app):  # noqa: F811
    with ein_app.app_context():
        c = ein_app.test_client()
        _bridge('ANMELDUNG')
        assert _senden(c, b'x').status_code == 401
        r = _senden(c, b'x', schluessel='omnb_falsch')
        assert r.status_code == 401 and r.get_json()['status'] == 'NICHT_ANGEMELDET'
        _, knoten_schluessel = _bridge('KEINE-BRIDGE', rolle='NODE')
        assert _senden(c, b'x', schluessel=knoten_schluessel).status_code == 403


@nur_pg
def test_sperre_nach_fehlversuchen(ein_app):  # noqa: F811
    from omn.eingang.empfang import FEHLVERSUCHE_JE_STUNDE
    with ein_app.app_context():
        c = ein_app.test_client()
        _, schluessel = _bridge('SPERRE')
        ip = _ip()
        codes = [_senden(c, b'x', schluessel='omnb_falsch', ip=ip).status_code for _ in range(FEHLVERSUCHE_JE_STUNDE)]
        assert codes == [401] * FEHLVERSUCHE_JE_STUNDE                  # 20 Fehlversuche je Stunde ...
        assert _senden(c, b'x', schluessel='omnb_falsch', ip=ip).status_code == 429      # ... dann gesperrt
        # gesperrt heisst gesperrt: auch der richtige Schluessel wird nicht mehr geprueft ...
        assert _senden(c, b'x', schluessel=schluessel, ip=ip).status_code == 429
        # ... andere Adressen sind nicht betroffen (je IP, seit ProxyFix x_for=1)
        assert _senden(c, b'x', schluessel=schluessel).status_code != 429


@nur_pg
def test_kopfzeilen_und_groesse(ein_app):  # noqa: F811
    from omn.eingang.einlesen import MAX_PAKET_BYTES
    with ein_app.app_context():
        c = ein_app.test_client()
        _, s = _bridge('KOPF')
        assert _senden(c, b'x', schluessel=s, X_OMN_Transport=None).status_code == 400
        assert _senden(c, b'x', schluessel=s, X_OMN_Transport='SD_IMPORT').status_code == 400
        assert _senden(c, b'x', schluessel=s, X_OMN_Empfangen='gestern').status_code == 400
        zukunft = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp() * 1_000_000)
        assert _senden(c, b'x', schluessel=s, X_OMN_Empfangen=str(zukunft)).status_code == 400
        assert _senden(c, b'x', schluessel=s, X_OMN_Referenz='r' * 201).status_code == 400
        assert _senden(c, b'\x00' * (MAX_PAKET_BYTES + 1), schluessel=s).status_code == 413
        # unlesbarer Inhalt ist eine endgueltige Antwort: 200 mit REJECTED
        r = _senden(c, b'kein paket', schluessel=s)
        assert r.status_code == 200 and r.get_json()['status'] == 'REJECTED'


@nur_pg
def test_pakete_ueber_die_bridge(ein_app):  # noqa: F811
    from omn.eingang.formate import paket_schreiben
    with ein_app.app_context():
        c = ein_app.test_client()
        bridge, s = _bridge('NORMAL')
        k = _vorbereiten('UEBER-BRIDGE')
        p = k.pakete(3)
        # Empfangszeit der Bridge: aktuell (die Messzeit der Testdaten liegt 2025,
        # eine Empfangszeit ueber 400 Tage in der Vergangenheit waere unplausibel)
        empfangen = (datetime.now(timezone.utc) - timedelta(minutes=5)).replace(microsecond=0)
        us = int(empfangen.timestamp() * 1_000_000)
        r2 = _senden(c, paket_schreiben(p[1]), schluessel=s, X_OMN_Referenz='lora-17', X_OMN_Empfangen=str(us))
        assert r2.status_code == 200 and r2.get_json()['status'] == 'WARTET'
        r1 = _senden(c, paket_schreiben(p[0]), schluessel=s, X_OMN_Transport='BLE')
        assert r1.get_json()['status'] == 'ACCEPTED' and r1.get_json()['kette'] == 'LINKED'
        assert _senden(c, paket_schreiben(p[2]), schluessel=s).get_json()['status'] == 'ACCEPTED'
        # dasselbe Paket nochmal (z. B. Antwort ging verloren): schadet nicht
        wieder = _senden(c, paket_schreiben(p[2]), schluessel=s)
        assert wieder.status_code == 200 and wieder.get_json()['status'] == 'SCHON_EINGELESEN'
        # Anlieferung haengt an der Bridge, mit Referenz und Empfangszeit der Bridge
        z = db.session.execute(sa.text(
            'SELECT d.transport_code, d.transport_ref, d.received_at, d.delivery_status, b.device_serial'
            ' FROM sandbox.batch_delivery d JOIN sandbox.device b ON b.id = d.bridge_device_id WHERE d.id = :a'),
            {'a': r2.get_json()['anlieferung']}).one()
        db.session.rollback()
        assert (z.transport_code, z.transport_ref, z.received_at, z.delivery_status, z.device_serial) == \
            ('LORA', 'lora-17', empfangen, 'ACCEPTED', bridge)
        assert _eins('SELECT last_used_at IS NOT NULL FROM sandbox.device_credential k JOIN sandbox.device d'
                     ' ON d.id = k.device_id WHERE d.device_serial = :g', g=bridge)


@nur_pg
def test_schluessel_bestimmt_das_schema(ein_app):  # noqa: F811
    from omn.eingang.formate import paket_schreiben
    with ein_app.app_context():
        c = ein_app.test_client()
        _, s_live = _bridge('LIVE', schema='live')
        k = _vorbereiten('NUR-SANDBOX')                   # der Node existiert nur in sandbox
        r = _senden(c, paket_schreiben(k.pakete(1)[0]), schluessel=s_live)
        assert r.status_code == 200 and r.get_json()['status'] == 'REJECTED' and 'unbekannt' in r.get_json()['grund']
        assert _eins('SELECT count(*) FROM live.batch_delivery WHERE id = :a', a=r.get_json()['anlieferung']) == 1


@nur_pg
def test_schluessel_per_befehl(ein_app):  # noqa: F811
    with ein_app.app_context():
        c = ein_app.test_client()
        runner = ein_app.test_cli_runner()
        serial = 'SBX-BRIDGE-CLI'
        assert runner.invoke(args=['biocomm-geraet', serial, '--rolle', 'BRIDGE', '--schema', 'sandbox']).exit_code == 0
        neu = runner.invoke(args=['biocomm-schluessel', serial, '--bezeichnung', 'Garten', '--schema', 'sandbox'])
        assert neu.exit_code == 0, neu.output
        schluessel = next(z.strip() for z in neu.output.splitlines() if z.strip().startswith('omnb_'))
        assert _senden(c, b'x', schluessel=schluessel).status_code == 200      # angemeldet (Inhalt unlesbar)
        # nur der Fingerabdruck liegt in der Datenbank, nie der Schluessel
        assert _eins("SELECT count(*) FROM sandbox.device_credential WHERE encode(token_hash, 'escape') LIKE '%omnb_%'") == 0
        liste = runner.invoke(args=['biocomm-schluessel', serial, '--liste', '--schema', 'sandbox'])
        assert 'aktiv' in liste.output and 'Garten' in liste.output and schluessel not in liste.output
        nr = _eins('SELECT k.id FROM sandbox.device_credential k JOIN sandbox.device d ON d.id = k.device_id'
                   ' WHERE d.device_serial = :g', g=serial)
        weg = runner.invoke(args=['biocomm-schluessel', serial, '--widerrufen', str(nr), '--schema', 'sandbox'])
        assert weg.exit_code == 0
        assert _senden(c, b'x', schluessel=schluessel).status_code == 401
