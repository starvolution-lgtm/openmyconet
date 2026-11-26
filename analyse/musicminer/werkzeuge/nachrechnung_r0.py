"""Nachrechnung mit pydbt, Schritt R0 (NACHRECHNUNG_PYDBT.md, Abschnitt 5 und 7c).

Läuft NICHT im Analyse-venv, sondern in der eigenen pydbt-Umgebung (Python 3.13):

    PYTHONPATH=. MPLBACKEND=Agg <openmyconet_extern>/venv_pydbt/Scripts/python.exe \
        -m werkzeuge.nachrechnung_r0 <pfad zum pydbt-Klon>

Schreibt ergebnisse/nachrechnung/r0.json. Kein pydbt-Code wird hier kopiert, nur importiert.
SIMULATION: Die Zeitmessung auf P + L verwirft die Gewichte und wertet sie nicht aus.
"""
import contextlib
import hashlib
import io
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

from mm.karte import BatchSOM

WURZEL = Path(__file__).resolve().parents[1]
ZIEL = WURZEL / 'ergebnisse' / 'nachrechnung'
SEEDS = range(10)


def sha256(pfad):
    return hashlib.sha256(Path(pfad).read_bytes()).hexdigest()


def pydbt_lauf(x, seed, **param):
    """Ein pydbt-Training; liefert (Gewichte, Gewinnerneuron-Index je Punkt, Sekunden)."""
    from pydbt.umatrix.training import EsomTrainingParams, esom_train
    np.random.seed(seed)
    p = EsomTrainingParams.build(**param)
    t = time.perf_counter()
    with contextlib.redirect_stdout(io.StringIO()):     # pydbt druckt jede Epoche
        _umx, bm, wts = esom_train(x, list(range(1, len(x) + 1)), p)
    sek = time.perf_counter() - t
    # Bestmatches beginnen in pydbt bei 1 (BM_START_AT_ONE_DEFAULT)
    bmu = np.array([(b.bm_row_coord - 1) * p.cols + (b.bm_col_coord - 1) for b in bm.best_matches])
    return np.asarray(wts.weights, dtype=np.float64), bmu, sek


def als_karte(w, zeilen, spalten, seed):
    """pydbt-Gewichte in unsere Kartenklasse setzen, damit Gruppen/Maße mit UNSEREM Code laufen."""
    k = BatchSOM(zeilen, spalten, toroidal=True, seed=seed)
    k.w = w
    return k


def auswerten(k, x, bmu, cls):
    gruppe, _art = k.gruppen(bmu)
    je_punkt = gruppe[bmu]
    eigene_bmu = k.bmu(x)
    return {
        'ari': float(adjusted_rand_score(cls, je_punkt)),
        'komponenten': len(np.unique(je_punkt)),
        'qe': float(np.mean(k.quantisierungsfehler(x, bmu))),
        'te': float(k.topologiefehler(x)),
        'bmu_wie_pydbt': float(np.mean(eigene_bmu == bmu)),
        'reinheit_neuron': reinheit(bmu, cls),
    }


def reinheit(bmu, cls):
    """Anteil der Punkte, deren Gewinnerneuron nur Punkte derselben Klasse trägt."""
    rein = 0
    for n in np.unique(bmu):
        m = bmu == n
        if len(np.unique(cls[m])) == 1:
            rein += m.sum()
    return float(rein / len(bmu))


def median(werte, schluessel):
    return float(np.median([w[schluessel] for w in werte]))


def main():
    klon = Path(sys.argv[1])
    from pydbt.data_io.cls_file_reader import read_cls_file
    from pydbt.data_io.lrn_file_reader import read_lrn_file
    from pydbt.umatrix import training

    with contextlib.redirect_stdout(io.StringIO()) as puffer:
        training.init_native_lib()
    c_bibliothek = 'Using C library' in puffer.getvalue()

    lrn_pfad = klon / 'tests' / 'test_data' / 'Chainlink.lrn'
    cls_pfad = klon / 'tests' / 'test_data' / 'Chainlink.cls'
    lrn = read_lrn_file(str(lrn_pfad))
    cl = read_cls_file(str(cls_pfad), encoding='latin-1')
    cls_je_key = dict(zip(cl.keys, cl.cls, strict=True))
    x = np.asarray(lrn.data, dtype=np.float64)
    cls = np.array([cls_je_key[k] for k in lrn.keys])

    erg = {
        'schritt': 'R0',
        'pydbt_commit': subprocess.run(['git', '-C', str(klon), 'rev-parse', 'HEAD'],
                                       capture_output=True, text=True, check=True).stdout.strip(),
        'python': platform.python_version(),
        'c_bibliothek_geladen': c_bibliothek,
        'numpy': np.__version__,
        'chainlink': {'lrn_sha256': sha256(lrn_pfad), 'cls_sha256': sha256(cls_pfad),
                      'punkte': len(x), 'klassen': sorted({int(c) for c in cls})},
    }

    # Determinismus (7c): zweimal Seed 0, 10 x 15
    r02 = {'rows': 10, 'cols': 15, 'epochs': 40, 'start_radius': 6.5, 'end_radius': 1, 'toroid': True}
    w1, b1, _ = pydbt_lauf(x, 0, **r02)
    w2, b2, _ = pydbt_lauf(x, 0, **r02)
    erg['determinismus'] = {'gewichte_gleich': bool(np.array_equal(w1, w2)),
                            'bmu_gleich': bool(np.array_equal(b1, b2))}

    # R0b, maßgeblich: toroidal 10 x 15, je 10 Seeds
    eigen, fremd, zeiten = [], [], []
    for s in SEEDS:
        k = BatchSOM(10, 15, toroidal=True, seed=s).trainieren(x, epochen=40)
        eigen.append(auswerten(k, x, k.bmu(x), cls))
        w, b, sek = pydbt_lauf(x, s, **r02)
        zeiten.append(sek)
        fremd.append(auswerten(als_karte(w, 10, 15, s), x, b, cls))
    mk, mp = median(eigen, 'ari'), median(fremd, 'ari')
    v0 = 'übereinstimmend' if (mk >= 0.9 and mp >= 0.9) or abs(mk - mp) < 0.1 else 'abweichend'
    erg['r0b'] = {'karte': '10x15 toroidal, 40 Epochen', 'karte_v1': eigen, 'pydbt': fremd,
                  'median_ari_karte_v1': mk, 'median_ari_pydbt': mp, 'v0': v0,
                  'pydbt_sekunden_median': float(np.median(zeiten))}

    # Nur berichtet: pydbt-Standard 50 x 80 / 24 Epochen
    std = []
    for s in SEEDS:
        w, b, sek = pydbt_lauf(x, s, rows=50, cols=80, epochs=24, toroid=True)
        a = auswerten(als_karte(w, 50, 80, s), x, b, cls)
        a['sekunden'] = sek
        std.append(a)
    erg['nur_berichtet_50x80'] = {'laeufe': std, 'median_ari_regel_v2': median(std, 'ari'),
                                  'median_reinheit_neuron': median(std, 'reinheit_neuron')}

    # Laufzeit: je eine Epoche auf P + L, Gewichte verworfen
    pl = np.load(WURZEL / 'ergebnisse' / 'a3' / 'merkmale_PL.npz')['x']
    zeit = {}
    for name, param, epochen in (('R1', {'rows': 50, 'cols': 80, 'start_radius': 24, 'end_radius': 24}, 24),
                                 ('R2', {'rows': 40, 'cols': 60, 'start_radius': 29, 'end_radius': 29}, 40)):
        # 2 Epochen (bei 1 Epoche teilt pydbts lineare Abkühlung durch 0), Mittel je Epoche
        _w, _b, sek = pydbt_lauf(pl, 0, epochs=2, toroid=True, **param)
        sek /= 2
        zeit[name] = {'eine_epoche_s': round(sek, 1), 'epochen': epochen,
                      'hochgerechnet_min': round(sek * epochen / 60, 1),
                      'hinweis': 'Startradius = groesste Nachbarschaft, also eher Obergrenze'}
    erg['laufzeit_PL'] = zeit

    ZIEL.mkdir(parents=True, exist_ok=True)
    (ZIEL / 'r0.json').write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in erg.items() if k not in ('r0b', 'nur_berichtet_50x80')},
                     ensure_ascii=False, indent=1))
    print('R0b V0:', v0, '| Median ARI karte-v1', round(mk, 3), '| pydbt', round(mp, 3))
    print('50x80 nur berichtet: ARI', round(erg['nur_berichtet_50x80']['median_ari_regel_v2'], 3),
          '| Reinheit', round(erg['nur_berichtet_50x80']['median_reinheit_neuron'], 3))


if __name__ == '__main__':
    main()
