"""Beispielfenster ausgewaehlter Gruppen/Inseln (Seed 0) in den Rohdaten (Kriterium 8b.3).

Aufruf: venv/Scripts/python.exe -m werkzeuge.a3_beispiele daten/<schnappschuss>.tar
"""
import json
import sys
from pathlib import Path

import matplotlib
import numpy as np

from mm import fenster as F
from mm.schnappschuss import Schnappschuss

matplotlib.use('Agg')
import matplotlib.pyplot as plt

ZIEL = Path('ergebnisse/a3')
HINWEIS = 'SIMULATION (Sandbox sbx-gen-1.0) – keine Messdaten'


def main():
    s = Schnappschuss(sys.argv[1])
    segs = s.segmente([int(k['id']) for k in s.kanaele('bioelectric_potential')])
    fw = F.fenster_bilden(segs, 10.0, 5.0)
    m = json.loads((ZIEL / 'metriken.json').read_text(encoding='utf-8'))
    rate = segs[0].rate_hz
    auswahl = []
    for konf in ('P|esom|torus', 'PL|esom|torus', 'PL|esom|planar', 'P|esom|planar'):
        satz, groesse, topo = konf.split('|')
        laeufe = np.load(ZIEL / f'laeufe_{satz}_{groesse}_{topo}.npz')
        zeilen, g = laeufe['zeilen'], laeufe['gruppe_seed0']
        for prof in m['konfigurationen'][konf]['gruppen_seed0']:
            if prof['wiedergefunden_seeds'] >= 8 and prof['fenster'] < 5000:
                auswahl.append((konf, prof, zeilen[g == prof['gruppe']]))
    fig, ax = plt.subplots(len(auswahl), 4, figsize=(16, 2.3 * len(auswahl)), squeeze=False)
    rng = np.random.default_rng(0)
    for zeile, (konf, prof, idx) in enumerate(auswahl):
        beispiele = rng.choice(idx, min(4, len(idx)), replace=False)
        for spalte, i in enumerate(beispiele):
            x = F.fenstermatrix(segs, fw, [i])[0]
            t = np.arange(len(x)) / rate
            a = ax[zeile, spalte]
            a.plot(t, x, lw=0.4, color='#1f4e79')
            a.set_title(f'{konf} G{prof["gruppe"]} ({prof["art"]}, {prof["fenster"]} F.) – Fenster {fw.kennung(i)[:3]}',
                        fontsize=7)
            a.tick_params(labelsize=6)
        ax[zeile, 0].set_ylabel('µV', fontsize=7)
    fig.suptitle(f'Beispielfenster stabiler Gruppen/Inseln (≥ 8 von 9 Seeds wiedergefunden), 10 s je Fenster\n{HINWEIS}')
    fig.tight_layout()
    fig.savefig(ZIEL / 'abbildungen' / 'beispiele_stabile_gruppen.png', dpi=95)
    for konf, prof, idx in auswahl:
        x = F.fenstermatrix(segs, fw, idx)
        h = x.shape[1] // 2
        sprung = np.median(np.abs(x[:, h:].mean(1) - x[:, :h].mean(1)))
        print(konf, prof['gruppe'], prof['art'], len(idx), 'Median |Mittel 2. Haelfte - 1. Haelfte| =', round(float(sprung), 2),
              'uV, phase', prof['phase'])


if __name__ == '__main__':
    main()
