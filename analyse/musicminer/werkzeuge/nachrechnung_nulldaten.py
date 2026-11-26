"""Nachrechnung mit refesom, R3: Nulldaten vorab erzeugen (NACHRECHNUNG_REFESOM.md, Abschnitte 3, 5, 7d).

Läuft im Analyse-venv, damit N1/N2 mit genau dem Code und der numpy-Version aus A3/A4 entstehen
(`werkzeuge.a3_laufen._nulldaten`, gleiche Seeds), also dieselben Matrizen wie dort. Die
refesom-Umgebung hat eine andere numpy-Version und liest deshalb nur diese Dateien.

    venv/Scripts/python.exe -m werkzeuge.nachrechnung_nulldaten

Schreibt ergebnisse/nachrechnung/nulldaten/{satz}_{N1|N2}_s{seed}.npz (nur lokal) und
ergebnisse/nachrechnung/nulldaten.json (sha256 je Datei).
SIMULATION: Nulldaten aus Simulationsmerkmalen, keine Messwerte.
"""
import hashlib
import json

import numpy as np

from werkzeuge.a3_laufen import _nulldaten
from werkzeuge.nachrechnung_auswerten import LAEUFE, SAETZE, WURZEL

ZIEL = LAEUFE.parent / 'nulldaten'
SEEDS = range(25)          # R3 = N1 0–24 und N2 0–24 (7d)


def main():
    ZIEL.mkdir(parents=True, exist_ok=True)
    verzeichnis = {'simuliert': True, 'numpy': np.__version__, 'code': 'werkzeuge.a3_laufen._nulldaten',
                   'dateien': {}}
    for satz in SAETZE:
        x = np.load(WURZEL / 'ergebnisse' / 'a3' / f'merkmale_{satz}.npz')['x']
        for art in ('N1', 'N2'):
            for seed in SEEDS:
                n = np.ascontiguousarray(_nulldaten(x, art, seed), dtype=np.float64)
                name = f'{satz}_{art}_s{seed}'
                np.savez(ZIEL / f'{name}.npz', x=n)
                verzeichnis['dateien'][name] = hashlib.sha256(n.tobytes()).hexdigest()
        print(satz, 'fertig')
    (LAEUFE.parent / 'nulldaten.json').write_text(json.dumps(verzeichnis, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
