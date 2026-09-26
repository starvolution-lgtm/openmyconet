"""Signaturen der Messknoten (omn/eingang/signatur.py, Schema v5).

Die Datenbank-Tests laufen nur mit PostgreSQL (Fixture aus test_dateneingang).
"""
import dataclasses
import hashlib

import sqlalchemy as sa
from test_dateneingang import PG_URL, _eins, _lauf, _vorbereiten, ein_app  # noqa: F401  (Fixture)

import pytest
from omn.eingang import signatur
from omn.extensions import db

nur_pg = pytest.mark.skipif(not PG_URL, reason='Dateneingang gibt es nur auf PostgreSQL')
SEED = signatur.seed_aus_efuse(signatur.TEST_EFUSE_SCHLUESSEL)
SEED_2 = signatur.seed_aus_efuse(hashlib.sha256(b'OMN-TEST-EFUSE-2').digest())


def _seed(name):
    """Eigener Schluessel je Test-Knoten (ein oeffentlicher Schluessel ist nur einmal registrierbar)."""
    return signatur.seed_aus_efuse(hashlib.sha256(name.encode()).digest())


def _ein(paket, **kw):
    from omn.eingang.einlesen import einliefern
    from omn.eingang.formate import paket_schreiben
    return einliefern(db.engine, paket_schreiben(paket), **kw)


# ---------------------------------------------------------------------------
# ohne Datenbank
# ---------------------------------------------------------------------------
def test_signatur_ist_nicht_teil_der_hashes():
    from datetime import datetime, timezone

    from omn.eingang import format_v1
    from omn.eingang.testknoten import TestKnoten
    k = TestKnoten('SBX-NODE-SIG', 'boot-1', None, datetime(2025, 3, 3, 8, tzinfo=timezone.utc), 10, 60, format='v1')
    p = k.pakete(1)[0]
    s = signatur.signieren(p, SEED)
    assert s.batch_hash == p.batch_hash and s.batch_hash_ist() == p.batch_hash
    assert s.signatur_art == 'ED25519' and len(s.signatur) == 64
    wieder = format_v1.paket_lesen(format_v1.paket_schreiben(s))
    assert wieder.signatur == s.signatur
    pub = signatur.oeffentlicher_schluessel(SEED)
    assert signatur.gueltig(pub, wieder)
    assert not signatur.gueltig(signatur.oeffentlicher_schluessel(SEED_2), wieder)
    # ein veraendertes Paket (anderer batch_hash) passt nicht mehr zur Signatur
    anders = dataclasses.replace(wieder, messzeitraum_bis=wieder.messzeitraum_bis.replace(second=1))
    assert not signatur.gueltig(pub, anders)


def test_seed_ableitung_wie_in_der_firmware():
    """HMAC-SHA256(eFuse, 'OMN-ED25519-SEED-v1') -- feste Werte fuer den Firmware-Test."""
    assert signatur.TEST_EFUSE_SCHLUESSEL.hex() == hashlib.sha256(b'OMN-TEST-EFUSE-v1').hexdigest()
    assert len(SEED) == 32 and SEED != signatur.TEST_EFUSE_SCHLUESSEL
    assert signatur.oeffentlicher_schluessel(SEED) == signatur.oeffentlicher_schluessel(SEED)


# ---------------------------------------------------------------------------
# Eingang (sandbox): Schluessel registriert -> nur noch signiert
# ---------------------------------------------------------------------------
@nur_pg
def test_signierte_pakete_werden_angenommen_und_gespeichert(ein_app):  # noqa: F811
    with ein_app.app_context():
        seed = _seed('SIG-OK')
        k = _vorbereiten('SIG-OK', signatur_seed=seed)
        p = k.pakete(3)
        e = _ein(p[0])
        assert e.status == 'ACCEPTED' and e.lauf_angelegt
        assert {_ein(x).status for x in p[1:]} == {'ACCEPTED'}
        zeilen = db.session.execute(sa.text(
            'SELECT ob.signature_algorithm, ob.signature, k.public_key FROM sandbox.origin_batch ob'
            ' JOIN sandbox.device_signing_key k ON k.id = ob.signing_key_id WHERE ob.acquisition_run_id = :r'
            ' ORDER BY ob.batch_sequence_no'), {'r': e.lauf_id}).all()
        assert [(a, bytes(s)) for a, s, _ in zeilen] == [('ED25519', x.signatur) for x in p]
        assert {bytes(z.public_key) for z in zeilen} == {signatur.oeffentlicher_schluessel(seed)}


@nur_pg
def test_unsigniert_oder_falsch_signiert_wird_abgelehnt(ein_app):  # noqa: F811
    from omn.eingang import format_v1
    with ein_app.app_context():
        k = _vorbereiten('SIG-FALSCH', signatur_seed=_seed('SIG-FALSCH'))
        ohne = dataclasses.replace(k, signatur_seed=None)
        fremd = dataclasses.replace(k, signatur_seed=_seed('SIG-FALSCH-fremd'))

        # ohne Signatur: auch LAUF_START legt keinen Lauf an, nichts wartet
        e = _ein(ohne.pakete(1)[0])
        assert e.status == 'REJECTED' and 'Signatur fehlt' in e.grund and _lauf(k) is None
        e = _ein(ohne.pakete(3)[2])
        assert e.status == 'REJECTED' and 'Signatur fehlt' in e.grund
        assert _eins('SELECT count(*) FROM sandbox.delivery_waiting WHERE device_serial = :g', g=k.geraet) == 0

        e = _ein(fremd.pakete(1)[0])
        assert e.status == 'REJECTED' and e.grund == 'Signatur ungueltig' and _lauf(k) is None

        p = k.pakete(2)
        kaputt = bytearray(p[1].signatur)
        kaputt[0] ^= 1
        assert _ein(p[0]).status == 'ACCEPTED'
        e = _ein(dataclasses.replace(p[1], signatur=bytes(kaputt)))
        assert e.status == 'REJECTED' and e.grund == 'Signatur ungueltig'

        hmac_art = dataclasses.replace(p[1], signatur_art='HMAC_SHA256', signatur=bytes(32))
        e = _ein(hmac_art, transport='USB')
        assert e.status == 'REJECTED' and 'nur Ed25519' in e.grund
        assert _ein(p[1]).status == 'ACCEPTED'                  # das echte Paket kommt danach durch
        assert format_v1.SIGNATUR_CODES['ED25519'] == 2


@nur_pg
def test_ohne_schluessel_in_sandbox_unsigniert_erlaubt(ein_app):  # noqa: F811
    with ein_app.app_context():
        k = _vorbereiten('SIG-OHNE')
        assert _ein(k.pakete(1)[0]).status == 'ACCEPTED'
        mit = dataclasses.replace(k, signatur_seed=_seed('SIG-OHNE'))   # signiert, kein Schluessel registriert
        e = _ein(mit.pakete(2)[1])
        assert e.status == 'REJECTED' and 'kein gueltiger Signaturschluessel' in e.grund


@nur_pg
def test_widerruf_gilt_auch_fuer_wartende_pakete(ein_app):  # noqa: F811
    """Signaturen gehoeren nicht zu den Hashes: dasselbe Paket, mit dem neuen
    Schluessel signiert, setzt die Kette fort. Ein mit dem widerrufenen
    Schluessel signiertes wartendes Paket wird bei der Verarbeitung abgelehnt."""
    with ein_app.app_context():
        runner = ein_app.test_cli_runner()
        k = _vorbereiten('SIG-WIDERRUF', signatur_seed=_seed('SIG-WIDERRUF'))
        alt = k.pakete(3)
        assert _ein(alt[2]).status == 'WARTET'
        nr = _eins('SELECT k.id FROM sandbox.device_signing_key k JOIN sandbox.device d ON d.id = k.device_id'
                   ' WHERE d.device_serial = :g', g=k.geraet)
        r = runner.invoke(args=['biocomm-knotenschluessel', k.geraet, '--widerrufen', str(nr), '--schema', 'sandbox'])
        assert r.exit_code == 0 and 'widerrufen' in r.output
        assert _ein(alt[0]).status == 'REJECTED'                 # alter Schluessel gilt nicht mehr

        seed2 = _seed('SIG-WIDERRUF-2')
        pub2 = signatur.oeffentlicher_schluessel(seed2).hex()
        r = runner.invoke(args=['biocomm-knotenschluessel', k.geraet, '--ed25519', pub2, '--schema', 'sandbox',
                                '--bezeichnung', 'neue Platine'])
        assert r.exit_code == 0, r.output
        neu = dataclasses.replace(k, signatur_seed=seed2).pakete(3)
        e = _ein(neu[0], transport='USB')
        assert e.status == 'ACCEPTED' and e.lauf_angelegt
        assert [(n.status, n.grund) for n in e.nachverarbeitet] == [('REJECTED', 'Signatur ungueltig')]
        assert {_ein(x).status for x in neu[1:]} == {'ACCEPTED'}

        liste = runner.invoke(args=['biocomm-knotenschluessel', k.geraet, '--liste', '--schema', 'sandbox'])
        assert 'widerrufen' in liste.output and 'neue Platine' in liste.output and '3 signierte Pakete' in liste.output


@nur_pg
def test_knotenschluessel_befehl_prueft_eingaben(ein_app):  # noqa: F811
    with ein_app.app_context():
        runner = ein_app.test_cli_runner()
        k = _vorbereiten('SIG-CLI')
        ok = signatur.oeffentlicher_schluessel(_seed('SIG-CLI')).hex()
        for falsch, text in (('zz', 'Hex'), ('ab' * 31, '32 Byte'), (ok, 'unbekannt')):
            ziel = 'SBX-NODE-GIBTSNICHT' if text == 'unbekannt' else k.geraet
            r = runner.invoke(args=['biocomm-knotenschluessel', ziel, '--ed25519', falsch, '--schema', 'sandbox'])
            assert r.exit_code != 0 and text in r.output, r.output
        assert runner.invoke(args=['biocomm-knotenschluessel', k.geraet, '--ed25519', ok,
                                   '--schema', 'sandbox']).exit_code == 0
        doppelt = runner.invoke(args=['biocomm-knotenschluessel', k.geraet, '--ed25519', ok, '--schema', 'sandbox'])
        assert doppelt.exit_code != 0 and 'schon registriert' in doppelt.output
        assert runner.invoke(args=['biocomm-knotenschluessel', k.geraet, '--schema', 'sandbox']).exit_code != 0


# ---------------------------------------------------------------------------
# Schema live: Signatur Pflicht
# ---------------------------------------------------------------------------
@nur_pg
def test_live_verlangt_signatur(ein_app):  # noqa: F811
    with ein_app.app_context():
        runner = ein_app.test_cli_runner()
        # sandbox-Knoten nur als Paketquelle; in live traegt er eine live-taugliche Seriennummer
        k = dataclasses.replace(_vorbereiten('SIG-LIVE'), geraet='OMN-NODE-TEST-SIG-LIVE')
        seed = _seed('SIG-LIVE')
        assert runner.invoke(args=['biocomm-geraet', k.geraet, '--schema', 'live']).exit_code == 0
        e = _ein(k.pakete(1)[0], schema='live')
        assert e.status == 'REJECTED' and 'im Schema live Pflicht' in e.grund

        signiert = dataclasses.replace(k, signatur_seed=seed).pakete(1)[0]
        e = _ein(signiert, schema='live', transport='USB')
        assert e.status == 'REJECTED' and 'kein gueltiger Signaturschluessel' in e.grund

        r = runner.invoke(args=['biocomm-knotenschluessel', k.geraet, '--ed25519',
                                signatur.oeffentlicher_schluessel(seed).hex(), '--schema', 'live'])
        assert r.exit_code == 0, r.output
        e = _ein(signiert, schema='live', transport_ref='neu.omb')
        assert e.status == 'WARTET' and 'Einsatz' in e.grund       # Signatur ok; Messreihe fehlt noch


@nur_pg
def test_rechte_der_web_rolle(ein_app):  # noqa: F811
    """omn darf Schluessel anlegen und widerrufen, aber keinen Schluessel aendern oder loeschen."""
    with ein_app.app_context():
        k = _vorbereiten('SIG-ROLLE', signatur_seed=_seed('SIG-ROLLE'))
        with db.engine.connect() as c:
            c.execute(sa.text('SET ROLE omn'))
            nr = c.execute(sa.text('SELECT k.id FROM sandbox.device_signing_key k JOIN sandbox.device d'
                                   ' ON d.id = k.device_id WHERE d.device_serial = :g'), {'g': k.geraet}).scalar()
            c.execute(sa.text('UPDATE sandbox.device_signing_key SET revoked_at = now() WHERE id = :i'), {'i': nr})
            for verboten in ("UPDATE sandbox.device_signing_key SET public_key = '\\x00' WHERE id = :i",
                             'DELETE FROM sandbox.device_signing_key WHERE id = :i'):
                with pytest.raises(sa.exc.DBAPIError), c.begin_nested():
                    c.execute(sa.text(verboten), {'i': nr})
            c.rollback()
