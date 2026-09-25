"""Paketformat v1 (omn/eingang/format_v1.py) ohne Datenbank.

Der Testvektor docs/dateneingang_format_v1_testvektor.omb und die Hashes unten
sind die Referenz fuer die Node-Firmware (C, ESP32-S3): Wer sie aendert, aendert
das Format. Beschreibung: docs/dateneingang_format_v1.md.
"""
import dataclasses
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from omn.eingang import format_v0, format_v1, formate
from omn.eingang.format_v0 import PaketUnlesbar

TESTVEKTOR = Path(__file__).resolve().parent.parent / 'docs' / 'dateneingang_format_v1_testvektor.omb'
T0 = datetime(2025, 3, 3, 8, 0, tzinfo=timezone.utc)
GENESIS_HEX = 'db5e9c79b06998afac13d64545c7eae91e31a8ede5e6e8db961b50613918a55f'
META_HEX = '6d2a3e5f3bba635671952df8c41ad715af589438be1e8414e45c3fe8193b7c26'
PAYLOAD_HEX = '2f5f425969297ab70704d591e7cb687e0e0f6259621ddceae615be96185eca57'
BATCH_HEX = 'a70865a07c019a664d85caf1203925fd5d196207ba26fa892a66287a09881972'


def _testpaket():
    bio = format_v1.block_bauen('U8/AIN0', 'bioelectric_potential', 0, 8, T0, (256, 1), 'int16le', 'none',
                                struct.pack('<8h', 0, 100, -100, 32767, -32768, 1, -1, 42))
    tmp = format_v1.block_bauen('DS18B20', 'soil_temperature', 0, 1, T0, (1, 600), 'float32le', 'none',
                                struct.pack('<f', 12.5))
    g = format_v1.genesis_berechnen('OMN-NODE-TEST', 'b1-00c0ffee')
    return format_v1.paket_bauen('OMN-NODE-TEST', 'b1-00c0ffee', 1, 'MIXED', T0, T0 + timedelta(minutes=10), g,
                                 (bio, tmp))


def test_testvektor_ist_stabil():
    p = _testpaket()
    roh = format_v1.paket_schreiben(p)
    assert roh == TESTVEKTOR.read_bytes(), 'Testvektor weicht ab: das Format hat sich geaendert'
    assert len(roh) == 314
    assert p.genesis().hex() == GENESIS_HEX
    assert p.meta_hash_ist().hex() == META_HEX
    assert p.payload_hash.hex() == PAYLOAD_HEX
    assert p.batch_hash.hex() == BATCH_HEX


def test_lesen_schreiben_rundlauf():
    roh = TESTVEKTOR.read_bytes()
    p = format_v1.paket_lesen(roh)
    assert p == _testpaket()
    assert format_v1.paket_schreiben(p) == roh
    assert p.batch_hash_ist() == p.batch_hash and p.payload_hash_ist() == p.payload_hash
    assert p.format == 'omn-batch-v1' and p.zeitquelle == 'RTC'
    bio, tmp = p.bloecke
    assert (bio.rate_zaehler, bio.rate_nenner, bio.rate_hz) == (256, 1, 256.0)
    assert (tmp.rate_zaehler, tmp.rate_nenner) == (1, 600)                 # exakt, kein Rundungsfehler


def test_weiche_zwischen_den_formaten():
    assert formate.paket_lesen(TESTVEKTOR.read_bytes()).format == 'omn-batch-v1'
    v0 = format_v0.paket_bauen('G', 'L', 1, 'RAW', T0, T0 + timedelta(seconds=1), format_v0.GENESIS, [
        format_v0.Block('E', 'bioelectric_potential', 0, 1, T0, 1.0, 'int16le', 'none', b'\x00\x00')])
    gelesen = formate.paket_lesen(format_v0.paket_schreiben(v0))
    assert gelesen.format == 'omn-batch-v0' and gelesen.genesis() == format_v0.GENESIS
    assert formate.paket_lesen(formate.paket_schreiben(gelesen)) == gelesen


@pytest.mark.parametrize('aenderung', [
    lambda b: dataclasses.replace(b, zeitanker=b.zeitanker + timedelta(microseconds=1)),
    lambda b: dataclasses.replace(b, erster_index=b.erster_index + 1),
    lambda b: dataclasses.replace(b, rate_zaehler=250, rate_hz=250.0),
    lambda b: dataclasses.replace(b, eingang='U14/AIN0'),
    lambda b: dataclasses.replace(b, geraete_qualitaet=b'\x01'),
])
def test_blockangaben_sind_durch_den_batch_hash_gedeckt(aenderung):
    """Die Luecke aus v0: Zeitanker, Index, Rate, Kanal und Geraetequalitaet
    liessen sich aendern, ohne dass eine Pruefsumme bricht. In v1 nicht mehr."""
    p = _testpaket()
    faelschung = dataclasses.replace(p, bloecke=(aenderung(p.bloecke[0]), p.bloecke[1]))
    assert faelschung.payload_hash_ist() == p.payload_hash          # Messwerte unveraendert ...
    assert faelschung.batch_hash_ist() != p.batch_hash              # ... trotzdem faellt es auf


def test_kopfangaben_sind_gedeckt():
    p = _testpaket()
    for feld, wert in (('messzeitraum_bis', p.messzeitraum_bis + timedelta(seconds=1)), ('lauf', 'b2-00c0ffee'),
                       ('geraet', 'OMN-NODE-ANDERS'), ('zeitquelle', 'GNSS'), ('flags', 1), ('inhalt', 'RAW')):
        assert dataclasses.replace(p, **{feld: wert}).batch_hash_ist() != p.batch_hash, feld


def test_genesis_gehoert_zu_geraet_und_lauf():
    g = format_v1.genesis_berechnen
    assert len({g('A', 'b1'), g('A', 'b2'), g('B', 'b1'), g('Ab', '1')}) == 4    # auch keine Verschiebung A|b1
    assert g('A', 'b1') != format_v0.GENESIS


def test_signatur_im_anhang():
    p = dataclasses.replace(_testpaket(), signatur_art='HMAC_SHA256', signatur=b'\x07' * 32)
    q = format_v1.paket_lesen(format_v1.paket_schreiben(p))
    assert (q.signatur_art, q.signatur) == ('HMAC_SHA256', b'\x07' * 32)
    assert q.batch_hash_ist() == p.batch_hash                        # die Signatur ist nicht Teil des Hashes


def test_ereignisse_werden_gelesen_und_sind_gedeckt():
    p = _testpaket()
    e = format_v1.Ereignis('STIMULATION', T0 + timedelta(minutes=5), b'\x01\x02')
    mit = format_v1.paket_bauen(p.geraet, p.lauf, 1, 'MIXED', p.messzeitraum_von, p.messzeitraum_bis,
                                p.vorgaenger_hash, p.bloecke, ereignisse=[e])
    q = format_v1.paket_lesen(format_v1.paket_schreiben(mit))
    assert q.ereignisse == (e,) and q.batch_hash_ist() == q.batch_hash
    assert mit.batch_hash != p.batch_hash


@pytest.mark.parametrize('kaputt, meldung', [
    (lambda r: r[:-1], 'endet mitten'),
    (lambda r: r + b'\x00', 'nach dem Paketende'),
    (lambda r: b'OMNX' + r[4:], 'OMNB'),
    (lambda r: r[:4] + b'\x02' + r[5:], 'Formatversion'),
    (lambda r: r[:5] + b'\x09' + r[6:], 'inhalt'),
    (lambda r: r[:-3] + b'\x01\x10\x00', 'Signatur'),
])
def test_formfehler_werden_erkannt(kaputt, meldung):
    with pytest.raises(PaketUnlesbar, match=meldung):
        format_v1.paket_lesen(kaputt(TESTVEKTOR.read_bytes()))


def test_zeit_ohne_zeitzone_wird_nicht_geschrieben():
    with pytest.raises(ValueError, match='Zeitzone'):
        format_v1.zeit_us(datetime(2025, 1, 1))
