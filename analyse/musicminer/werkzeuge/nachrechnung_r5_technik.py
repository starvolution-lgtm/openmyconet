"""Nachrechnung mit refesom, R5-0 Technik-Check (NACHRECHNUNG_REFESOM.md, Abschnitt 7f).

Läuft in der refesom-Umgebung, mit refesom aus dem Arbeitsordner des neuen Zweigs:

    PYTHONPATH="<refesom_next>;." MPLBACKEND=Agg <openmyconet_extern>/venv_refesom/Scripts/python.exe \
        -m werkzeuge.nachrechnung_r5_technik <refesom_next>

Prüft: geladener refesom-Pfad + Commit, Determinismus mit `seed`, Übergabe der Gewinnerneuronen,
σ-Verlauf gegen `karte-v1`, V0 auf Chainlink 10 × 15 mit den neuen Optionen (nur berichtet, aber
Haltepunkt bei ARI < 0,9). Schreibt ergebnisse/nachrechnung/r5_technik.json. Kein refesom-Code
wird hierher kopiert, nur importiert.
"""
import contextlib
import io
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score

from mm.karte import BatchSOM

WURZEL = Path(__file__).resolve().parents[1]
ZIEL = WURZEL / 'ergebnisse' / 'nachrechnung' / 'r5_technik.json'
SEEDS = range(10)


def sigma_karte_v1(z, s, epochen, sigma_ende):
    """σ je Epoche wie in mm.karte.BatchSOM.trainieren (sigma_start = max(2, max(z, s)/4))."""
    st = max(2.0, max(z, s) / 4)
    return [st * (sigma_ende / st) ** (e / max(1, epochen - 1)) for e in range(epochen)]


def main():
    klon = Path(sys.argv[1]).resolve()
    from werkzeuge.refesom_laden import modul
    refesom = modul()
    read_cls_file = modul('data_io.cls_file_reader').read_cls_file
    read_lrn_file = modul('data_io.lrn_file_reader').read_lrn_file
    T = modul('umatrix.training')

    geladen = Path(refesom.__file__).resolve()
    if klon not in geladen.parents:
        sys.exit(f'Falsches refesom geladen: {geladen} (erwartet unter {klon})')
    with contextlib.redirect_stdout(io.StringIO()) as puffer:
        T.init_native_lib()
    c_bib = 'Using C library' in puffer.getvalue()
    commit = subprocess.run(['git', '-C', str(klon), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, check=True).stdout.strip()

    def lauf(x, seed, zeilen, spalten, start, ende):
        p = T.EsomTrainingParams.build(rows=zeilen, cols=spalten, epochs=40, start_radius=start, end_radius=ende,
                                       neighborhood_cooling=T.CoolingMethod.EXPONENTIAL_SIGMA,
                                       neighborhood_cutoff=T.NeighborhoodCutoff.KERNEL_WIDTH, seed=seed)
        with contextlib.redirect_stdout(io.StringIO()) as aus:
            _umx, bm, wts = T.esom_train(x, list(range(1, len(x) + 1)), p)
        bmu = np.array([(b.bm_row_coord - 1) * spalten + (b.bm_col_coord - 1) for b in bm.best_matches])
        radien = [float(r) for r in re.findall(r'radius=([0-9.]+)', aus.getvalue())]
        return np.asarray(wts.weights, dtype=np.float64), bmu, radien

    lrn_pfad = klon / 'tests' / 'test_data' / 'Chainlink.lrn'
    lrn = read_lrn_file(str(lrn_pfad))
    cl = read_cls_file(str(klon / 'tests' / 'test_data' / 'Chainlink.cls'), encoding='latin-1')
    je_key = dict(zip(cl.keys, cl.cls, strict=True))
    x = np.asarray(lrn.data, dtype=np.float64)
    cls = np.array([je_key[k] for k in lrn.keys])

    # 2. Determinismus + Übergabe
    w1, b1, r1 = lauf(x, 0, 10, 15, 6.5, 0.5)
    w2, b2, _ = lauf(x, 0, 10, 15, 6.5, 0.5)
    k = BatchSOM(10, 15, toroidal=True, seed=0)
    k.w = w1
    det = {'gewichte_gleich': bool(np.array_equal(w1, w2)), 'bmu_gleich': bool(np.array_equal(b1, b2)),
           'bmu_wie_refesom': float(np.mean(k.bmu(x) == b1))}

    # 3. σ-Verlauf: exakt über refesoms Funktion, zusätzlich gegen die (auf 2 Stellen gerundete) Ausgabe
    sig = {}
    for name, (z, s, start, ende) in {'40x60': (40, 60, 29, 0.5), '10x15': (10, 15, 6.5, 0.5)}.items():
        eigen = sigma_karte_v1(z, s, 40, 0.75)
        fremd = [T.gauss_kernel_stddev(T.cool_down_exponential_sigma(start, ende, 40, e)) for e in range(40)]
        sig[name] = {'max_abweichung_exakt': float(np.max(np.abs(np.subtract(eigen, fremd)))),
                     'sigma_start_ende': [fremd[0], fremd[-1]]}
    gedruckt = [(r + 1) / 2 for r in r1]
    sig['10x15']['max_abweichung_ausgabe_gerundet'] = float(
        np.max(np.abs(np.subtract(sigma_karte_v1(10, 15, 40, 0.75), gedruckt)))) if len(gedruckt) == 40 else None
    sigma_ok = all(v['max_abweichung_exakt'] < 1e-9 for v in sig.values())

    # 4. V0 Chainlink 10 x 15 (nur berichtet, Haltepunkt bei ARI < 0,9)
    ari = []
    for s in SEEDS:
        w, b, _ = lauf(x, s, 10, 15, 6.5, 0.5)
        kk = BatchSOM(10, 15, toroidal=True, seed=s)
        kk.w = w
        g, _ = kk.gruppen(b)
        ari.append(float(adjusted_rand_score(cls, g[b])))
    v0_median = float(np.median(ari))

    technik_ok = det['gewichte_gleich'] and det['bmu_gleich'] and det['bmu_wie_refesom'] == 1.0 and sigma_ok
    erg = {'schritt': 'R5-0', 'regeln': 'NACHRECHNUNG_REFESOM.md, Abschnitt 7f', 'refesom_commit': commit,
           'refesom_geladen_aus': str(geladen.parent), 'c_bibliothek_geladen': c_bib,
           'python': platform.python_version(), 'numpy': np.__version__,
           'determinismus': det, 'sigma_verlauf': sig, 'sigma_ok': sigma_ok,
           'v0_chainlink_10x15': {'ari': ari, 'median': v0_median, 'halt': v0_median < 0.9},
           'technik_ok': bool(technik_ok), 'r5_freigegeben': bool(technik_ok and v0_median >= 0.9)}
    ZIEL.write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in erg.items() if k != 'v0_chainlink_10x15'}, ensure_ascii=False, indent=1))
    print('V0 Chainlink ARI Median', round(v0_median, 3), '| R5 darf laufen:', erg['r5_freigegeben'])


if __name__ == '__main__':
    main()
