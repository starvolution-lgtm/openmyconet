"""Nachrechnung mit pydbt, Läufe R1 und R2 als Warteschlange (NACHRECHNUNG_PYDBT.md, 5, 7a, 7d).

Jeder Lauf (Schritt, Satz, Seed) ist ein eigener Auftrag mit eigener Ergebnisdatei. Beliebig viele
Arbeiter können gleichzeitig laufen und jederzeit dazukommen; jeder nimmt sich den nächsten
offenen Auftrag (Sperrdatei, atomar angelegt). Fertige Läufe werden übersprungen, ein Abbruch
verliert nur den gerade laufenden Auftrag. Jeder Lauf ist allein durch seinen Seed festgelegt.

Läuft in der pydbt-Umgebung (Python 3.13):

    PYTHONPATH=. MPLBACKEND=Agg <openmyconet_extern>/venv_pydbt/Scripts/python.exe \
        -m werkzeuge.nachrechnung_laeufe <pfad zum pydbt-Klon> [arbeiter-name]

MM_PROBE=1: Kurzlauf (2 Epochen, 2 000 Fenster, 1 Seed) nach ergebnisse/nachrechnung/probe/.
SIMULATION: Grundlage sind die Merkmale aus Phase A (Simulationsdaten, keine Messwerte).
"""
import contextlib
import ctypes
import hashlib
import io
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

for _v in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '1')     # ein Kern je Arbeiter

import numpy as np

WURZEL = Path(__file__).resolve().parents[1]
PROBE = os.environ.get('MM_PROBE') == '1'
ZIEL = WURZEL / 'ergebnisse' / 'nachrechnung' / ('probe' if PROBE else 'laeufe')
SPERRE_ALT_S = 4 * 3600      # Sperre eines abgestürzten Arbeiters gilt nach 4 h als verwaist

# Parameter laut Abschnitt 7a (vor R1 festgelegt); R1 vor R2 in der Warteschlange
SCHRITTE = {
    'R1': {'rows': 50, 'cols': 80, 'epochs': 24, 'toroid': True},
    'R2': {'rows': 40, 'cols': 60, 'epochs': 40, 'toroid': True, 'start_radius': 29, 'end_radius': 1},
}
SAETZE = ('P', 'PL')
SEEDS = range(1) if PROBE else range(10)


def auftraege():
    return [(s, satz, seed) for s in SCHRITTE for satz in SAETZE for seed in SEEDS]


def niedrige_prioritaet_und_wach():
    """Windows: Priorität „niedriger als normal“, Ruhezustand verhindern, solange der Prozess läuft."""
    if sys.platform != 'win32':
        return
    k32 = ctypes.windll.kernel32
    k32.SetPriorityClass(k32.GetCurrentProcess(), 0x00004000)        # BELOW_NORMAL_PRIORITY_CLASS
    k32.SetThreadExecutionState(0x80000000 | 0x00000001)             # ES_CONTINUOUS | ES_SYSTEM_REQUIRED


def sperren(pfad):
    try:
        fd = os.open(pfad, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if time.time() - pfad.stat().st_mtime > SPERRE_ALT_S:
            pfad.unlink(missing_ok=True)
            return sperren(pfad)
        return False
    os.write(fd, f'{os.getpid()} {time.strftime("%Y-%m-%d %H:%M:%S")}'.encode())
    os.close(fd)
    return True


def main():
    klon = Path(sys.argv[1])
    name = sys.argv[2] if len(sys.argv) > 2 else f'a{os.getpid()}'
    niedrige_prioritaet_und_wach()
    from pydbt.umatrix.training import EsomTrainingParams, esom_train, init_native_lib

    with contextlib.redirect_stdout(io.StringIO()) as puffer:
        init_native_lib()
    c_bib = 'Using C library' in puffer.getvalue()
    commit = subprocess.run(['git', '-C', str(klon), 'rev-parse', 'HEAD'],
                            capture_output=True, text=True, check=True).stdout.strip()
    ZIEL.mkdir(parents=True, exist_ok=True)
    daten, hashes = {}, {}
    for satz in SAETZE:
        pfad = WURZEL / 'ergebnisse' / 'a3' / f'merkmale_{satz}.npz'
        hashes[satz] = hashlib.sha256(pfad.read_bytes()).hexdigest()
        x = np.load(pfad)['x']
        daten[satz] = x[:2000] if PROBE else x

    def log(text):
        zeile = f'{time.strftime("%H:%M:%S")} [{name}] {text}'
        print(zeile, flush=True)
        with open(ZIEL / f'{name}.log', 'a', encoding='utf-8') as f:
            f.write(zeile + '\n')

    log(f'Start: pydbt {commit[:7]}, C-Bibliothek {c_bib}, Python {platform.python_version()}')
    for schritt, satz, seed in auftraege():
        kennung = f'{schritt}_{satz}_s{seed}'
        datei = ZIEL / f'{kennung}.npz'
        if datei.exists() or not sperren(ZIEL / f'{kennung}.lock'):
            continue
        try:
            param = dict(SCHRITTE[schritt])
            if PROBE:
                param['epochs'] = 2
            x = daten[satz]
            log(f'{kennung}: rechne ({len(x)} Fenster, {param})')
            np.random.seed(seed)
            t = time.perf_counter()
            with contextlib.redirect_stdout(io.StringIO()):
                umx, bm, wts = esom_train(x, list(range(1, len(x) + 1)), EsomTrainingParams.build(**param))
            sek = time.perf_counter() - t
            p = EsomTrainingParams.build(**param)
            bmu = np.array([(b.bm_row_coord - 1) * p.cols + (b.bm_col_coord - 1) for b in bm.best_matches],
                           dtype=np.int32)
            meta = {'schritt': schritt, 'satz': satz, 'seed': seed, 'parameter': repr(p),
                    'pydbt_commit': commit, 'c_bibliothek': c_bib, 'python': platform.python_version(),
                    'numpy': np.__version__, 'merkmale_sha256': hashes[satz], 'fenster': len(x),
                    'sekunden': round(sek, 1), 'arbeiter': name, 'probe': PROBE,
                    'fertig': time.strftime('%Y-%m-%d %H:%M:%S')}
            tmp = ZIEL / f'{kennung}.tmp.npz'
            np.savez_compressed(tmp, w=np.asarray(wts.weights, dtype=np.float64), bmu=bmu,
                                umx=np.asarray(umx.data, dtype=np.float64), meta=json.dumps(meta))
            os.replace(tmp, datei)
            log(f'{kennung}: fertig in {sek / 60:.1f} min')
        finally:
            (ZIEL / f'{kennung}.lock').unlink(missing_ok=True)
    offen = [a for a in auftraege() if not (ZIEL / f'{a[0]}_{a[1]}_s{a[2]}.npz').exists()]
    log(f'Ende: keine freien Aufträge mehr ({len(offen)} offen oder in Arbeit bei anderen)')


if __name__ == '__main__':
    main()
