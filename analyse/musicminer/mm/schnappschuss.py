"""Lesen und Pruefen eines Sandbox-Schnappschusses (werkzeuge/schnappschuss_holen.py).

Der Schnappschuss ist eine tar-Datei mit gzip-CSV je Tabelle und einer manifest.json.
Alles hier ist SIMULATION (Sandbox-Szenarien), nie Messdaten.

Pruefungen (pruefen()):
- Datei-Pruefsummen gegen das Manifest,
- je Block sha256(payload) == payload_hash,
- je Ursprungspaket payload_hash = sha256(Blockpayloads in sample_block-id-Reihenfolge),
- Pruefsummenkette je Lauf: batch_hash = sha256(vorgaenger + payload_hash + Sequenz, 8 Byte BE),
  Genesis = 32 Null-Bytes (Format v0, so rechnet der Sandbox-Generator),
- Kontrollwert (Summe value_mean der 1h-Aggregate) gegen das Manifest.

Die Umrechnung der bioelektrischen Zaehlwerte in uV ist dieselbe wie im Datenlabor
(omn/datenlabor.py, api_roh): Zaehlwert * lsb_uv / gain, Kalibrierung aus dem Kanal.
"""
import csv
import gzip
import hashlib
import io
import json
import math
import tarfile
import zlib
from base64 import b64decode
from dataclasses import dataclass
from datetime import datetime

import numpy as np

try:
    from compression import zstd as _zstd
except ImportError:  # Python < 3.14
    _zstd = None

csv.field_size_limit(1 << 30)

GENESIS_V0 = bytes(32)


def _zeit(text):
    """PostgreSQL-CSV-Zeitstempel (UTC, '+00') -> datetime (tz-aware)."""
    t = text.strip()
    if t.endswith('+00'):
        t += ':00'
    return datetime.fromisoformat(t)


def entpacken(payload, kompression):
    if kompression == 'none':
        return payload
    if kompression.startswith('zlib'):
        return zlib.decompress(payload)
    if kompression.startswith('zstd'):
        if _zstd is None:
            raise RuntimeError('zstd braucht Python 3.14')
        return _zstd.decompress(payload)
    raise ValueError(f'unbekannte Kompression {kompression}')


def dekodieren(roh, kodierung):
    if kodierung == 'int16le':
        return np.frombuffer(roh, dtype='<i2')
    if kodierung == 'float32le':
        return np.frombuffer(roh, dtype='<f4')
    raise ValueError(f'unbekannte Kodierung {kodierung}')


@dataclass
class Segment:
    """Lueckenloser Abschnitt eines Kanals (aufeinanderfolgende Sample-Indizes)."""
    kanal_id: int
    lauf_id: int
    erster_index: int
    anker: datetime          # Zeit des ersten Samples (Geraetezeit, UTC)
    rate_hz: float
    werte: np.ndarray        # physikalische Einheit (bio: uV)
    zaehlwerte: np.ndarray | None = None   # bio: rohe ADC-Zaehlwerte (fuer Saettigung)

    @property
    def dauer_s(self):
        return len(self.werte) / self.rate_hz


class Schnappschuss:
    def __init__(self, pfad):
        self.pfad = str(pfad)
        self._roh = {}
        with tarfile.open(self.pfad) as tar:
            for m in tar.getmembers():
                self._roh[m.name] = tar.extractfile(m).read()
        self.manifest = json.loads(self._roh['manifest.json'])
        self._cache = {}

    # -- Tabellen ----------------------------------------------------------
    def zeilen(self, name):
        """Iterator ueber die Zeilen einer Tabelle (dict, Werte als Text, '' = NULL)."""
        daten = gzip.decompress(self._roh[f'{name}.csv.gz'])
        return csv.DictReader(io.StringIO(daten.decode('utf-8')))

    def tabelle(self, name):
        if name not in self._cache:
            self._cache[name] = list(self.zeilen(name))
        return self._cache[name]

    # -- Pruefung ----------------------------------------------------------
    def pruefen(self):
        """Alle Pruefungen; wirft AssertionError beim ersten Fehler, sonst Kennzahlen."""
        for name, info in self.manifest['dateien'].items():
            ist = hashlib.sha256(self._roh[name]).hexdigest()
            assert ist == info['sha256'], f'{name}: Pruefsumme passt nicht zum Manifest'
            assert sum(1 for _ in self.zeilen(name[:-7])) == info['zeilen'], f'{name}: Zeilenzahl'

        bloecke_je_batch = {}
        for z in self.zeilen('sample_block'):
            payload = b64decode(z['payload'])
            assert hashlib.sha256(payload).hexdigest() == z['payload_hash'], f'Block {z["id"]}: payload_hash'
            bloecke_je_batch.setdefault(int(z['origin_batch_id']), []).append((int(z['id']), payload))

        laeufe = {}
        for b in self.tabelle('origin_batch'):
            assert b['batch_status'] == 'CANONICAL', f'Batch {b["id"]} nicht kanonisch'
            bl = sorted(bloecke_je_batch.get(int(b['id']), []))
            ph = hashlib.sha256(b''.join(p for _, p in bl)).digest()
            assert ph.hex() == b['payload_hash'], f'Batch {b["id"]}: payload_hash der Bloecke'
            laeufe.setdefault(int(b['acquisition_run_id']), []).append((int(b['batch_sequence_no']), ph, b['batch_hash']))
        for lauf, liste in laeufe.items():
            prev = GENESIS_V0
            for seq, ph, bh in sorted(liste):
                h = hashlib.sha256(prev + ph + seq.to_bytes(8, 'big')).digest()
                assert h.hex() == bh, f'Lauf {lauf}, Sequenz {seq}: Kette gebrochen'
                prev = h

        summe = math.fsum(float(z['value_mean']) for z in self.zeilen('derived_aggregate_current')
                          if z['resolution'] == '1h')
        soll = float(self.manifest['kontrollwert_1h_summe_value_mean'])
        assert abs(round(summe, 3) - soll) < 0.0015, f'Kontrollwert {summe:.3f} != {soll}'

        return {'bloecke': sum(len(v) for v in bloecke_je_batch.values()), 'batches': len(self.tabelle('origin_batch')),
                'laeufe': len(laeufe), 'kontrollwert': round(summe, 3)}

    # -- Rohsignale ----------------------------------------------------------
    def kanaele(self, groesse=None, art='RAW'):
        return [k for k in self.tabelle('measurement_channel')
                if k['data_kind'] == art and (groesse is None or k['quantity_code'] == groesse)]

    def reihe_von_lauf(self):
        return {int(r['id']): int(r['series_id']) for r in self.tabelle('acquisition_run')}

    def segmente(self, kanal_ids=None):
        """Lueckenlose Segmente je Kanal (aufeinanderfolgende Indizes, gleiche Rate werden verbunden).

        bio-Kanaele (int16) werden mit lsb_uv / gain in uV umgerechnet."""
        kanaele = {int(k['id']): k for k in self.tabelle('measurement_channel')}
        if kanal_ids is not None:
            kanal_ids = set(kanal_ids)
        offen = {}
        fertig = []
        for z in self.zeilen('sample_block'):
            kid = int(z['measurement_channel_id'])
            if kanal_ids is not None and kid not in kanal_ids:
                continue
            k = kanaele[kid]
            zw = dekodieren(entpacken(b64decode(z['payload']), z['compression']), z['value_encoding'])
            assert len(zw) == int(z['sample_count']), f'Block {z["id"]}: Laenge'
            if z['value_encoding'] == 'int16le':
                kal = json.loads(k['calibration'] or '{}')
                faktor = float(kal['lsb_uv']) / float(k['gain'])
                werte, zaehl = zw.astype(np.float64) * faktor, zw
            else:
                werte, zaehl = zw.astype(np.float64), None
            idx, rate = int(z['first_sample_index']), float(z['sample_rate_hz'])
            seg = offen.get(kid)
            anker = _zeit(z['time_anchor'])
            # verbinden nur bei lueckenlosem Index UND passender Zeit (halbe Abtastperiode Toleranz)
            if (seg is not None and seg['ende'] == idx and seg['rate'] == rate
                    and abs((anker - seg['anker']).total_seconds() - (idx - seg['start']) / rate) < 0.5 / rate):
                seg['werte'].append(werte)
                if zaehl is not None:
                    seg['zaehl'].append(zaehl)
                seg['ende'] = idx + len(zw)
                continue
            if seg is not None:
                fertig.append(seg)
            offen[kid] = {'kid': kid, 'lauf': int(k['acquisition_run_id']), 'start': idx, 'ende': idx + len(zw),
                          'anker': anker, 'rate': rate, 'werte': [werte],
                          'zaehl': [zaehl] if zaehl is not None else None}
        fertig.extend(offen.values())
        return [Segment(s['kid'], s['lauf'], s['start'], s['anker'], s['rate'], np.concatenate(s['werte']),
                        np.concatenate(s['zaehl']) if s['zaehl'] else None)
                for s in sorted(fertig, key=lambda s: (s['kid'], s['start']))]
