"""Tests fuer mm.schnappschuss mit einem kleinen, hier gebauten Schnappschuss."""
import csv
import gzip
import hashlib
import io
import json
import tarfile
import zlib
from base64 import b64encode

import numpy as np
import pytest

from mm.schnappschuss import GENESIS_V0, Schnappschuss

LSB, GAIN, RATE = 7.8125, 100, 250.0


def _csv(zeilen):
    puffer = io.StringIO()
    w = csv.DictWriter(puffer, fieldnames=list(zeilen[0]))
    w.writeheader()
    w.writerows(zeilen)
    return gzip.compress(puffer.getvalue().encode(), mtime=0)


def _bauen(pfad, manipulieren=None, zeitluecke=False):
    """Ein Lauf, ein bio-Kanal, zwei Pakete mit je einem Block (2 x 500 Samples)."""
    rng = np.random.default_rng(1)
    bloecke, batches, prev = [], [], GENESIS_V0
    for seq in (1, 2):
        zw = rng.integers(-2000, 2000, 500).astype('<i2')
        payload = zlib.compress(zw.tobytes(), 6)
        start = (seq - 1) * 500
        sek = start / RATE + (5 if zeitluecke and seq == 2 else 0)
        bloecke.append({'id': seq, 'acquisition_run_id': 1, 'measurement_channel_id': 7, 'origin_batch_id': seq,
                        'first_sample_index': start, 'sample_count': 500,
                        'time_anchor': f'2025-01-13 09:00:{sek:06.3f}+00', 'sample_rate_hz': RATE,
                        'value_encoding': 'int16le', 'compression': 'zlib-6',
                        'payload': b64encode(payload).decode(), 'payload_hash': hashlib.sha256(payload).hexdigest(),
                        'device_quality': ''})
        ph = hashlib.sha256(payload).digest()
        bh = hashlib.sha256(prev + ph + seq.to_bytes(8, 'big')).digest()
        batches.append({'id': seq, 'acquisition_run_id': 1, 'batch_sequence_no': seq, 'payload_hash': ph.hex(),
                        'batch_hash': bh.hex(), 'batch_status': 'CANONICAL'})
        prev = bh
    if manipulieren == 'kette':
        batches[1]['batch_hash'] = '00' * 32
    tabellen = {
        'sample_block': bloecke,
        'origin_batch': batches,
        'measurement_channel': [{'id': 7, 'acquisition_run_id': 1, 'quantity_code': 'bioelectric_potential',
                                 'data_kind': 'RAW', 'gain': GAIN, 'calibration': json.dumps({'lsb_uv': LSB})}],
        'acquisition_run': [{'id': 1, 'series_id': 3}],
        'derived_aggregate_current': [{'resolution': '1h', 'value_mean': 1.25}, {'resolution': '1min', 'value_mean': 9}],
    }
    dateien = {f'{n}.csv.gz': _csv(z) for n, z in tabellen.items()}
    manifest = {'kontrollwert_1h_summe_value_mean': '1.250',
                'dateien': {n: {'zeilen': len(tabellen[n[:-7]]), 'sha256': hashlib.sha256(d).hexdigest()}
                            for n, d in dateien.items()}}
    if manipulieren == 'datei':
        dateien['origin_batch.csv.gz'] = _csv(batches[:1])
    dateien['manifest.json'] = json.dumps(manifest).encode()
    with tarfile.open(pfad, 'w') as tar:
        for n, d in dateien.items():
            info = tarfile.TarInfo(n)
            info.size = len(d)
            tar.addfile(info, io.BytesIO(d))
    return pfad


def test_pruefung_und_umrechnung(tmp_path):
    s = Schnappschuss(_bauen(tmp_path / 's.tar'))
    assert s.pruefen() == {'bloecke': 2, 'batches': 2, 'laeufe': 1, 'kontrollwert': 1.25}
    (seg,) = s.segmente()
    assert len(seg.werte) == 1000 and seg.erster_index == 0
    assert np.allclose(seg.werte, seg.zaehlwerte * LSB / GAIN)


def test_zeitluecke_trennt_segmente(tmp_path):
    s = Schnappschuss(_bauen(tmp_path / 's.tar', zeitluecke=True))
    assert [len(g.werte) for g in s.segmente()] == [500, 500]


@pytest.mark.parametrize('art, meldung', [('kette', 'Kette gebrochen'), ('datei', 'Pruefsumme')])
def test_manipulation_wird_erkannt(tmp_path, art, meldung):
    s = Schnappschuss(_bauen(tmp_path / 's.tar', manipulieren=art))
    with pytest.raises(AssertionError, match=meldung):
        s.pruefen()
