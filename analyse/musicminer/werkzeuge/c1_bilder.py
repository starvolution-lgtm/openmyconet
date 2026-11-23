"""C1 / Abschnitt 7: U-Matrix der Seed-0-Karte je Prüfdatei, Anteil Leerkanal-Fenster je Neuron.

    MPLBACKEND=Agg venv/Scripts/python.exe -m werkzeuge.c1_bilder

Schreibt ergebnisse/c1/f1_umatrix.png. Nur berichtet.
MESSWERTE VON BUFFI ET AL. (doi 10.17632/srkxbkh6sp.1, CC BY 4.0), nicht von OpenMycoNet.
"""
import matplotlib.pyplot as plt
import numpy as np

from mm import buffi as B
from mm.karte import BatchSOM
from werkzeuge.c1_f1 import LAEUFE, MERKMALE, ZIEL


def main():
    fig, ax = plt.subplots(2, 3, figsize=(15, 7.5), constrained_layout=True)
    for j, name in enumerate(B.PRUEFDATEIEN):
        lf = np.load(LAEUFE / f'F1_{name}_mb1_s0.npz')
        kanal = np.load(MERKMALE / f'{name}_vorher.npz')['kanal']
        k = BatchSOM(40, 60, toroidal=True, seed=0)
        k.w = lf['w']
        u = k.u_matrix().reshape(40, 60)
        treffer = np.bincount(lf['bmu'], minlength=k.k)
        leer = np.bincount(lf['bmu'], weights=np.isin(kanal, B.LEER).astype(float), minlength=k.k)
        anteil = np.where(treffer > 0, leer / np.maximum(treffer, 1), np.nan).reshape(40, 60)
        a = ax[0, j].imshow(u, cmap='terrain')
        ax[0, j].set_title(f'{name}: U-Matrix (Seed 0)')
        fig.colorbar(a, ax=ax[0, j], shrink=0.8)
        b = ax[1, j].imshow(anteil, cmap='coolwarm', vmin=0, vmax=1)
        ax[1, j].set_title('Anteil Leerkanal-Fenster (7-8, 15-16) je Neuron')
        fig.colorbar(b, ax=ax[1, j], shrink=0.8)
        for a_ in ax[:, j]:
            a_.set_xticks([])
            a_.set_yticks([])
    fig.suptitle('C1 / F1, Zeitraum „vorher“ (72 h vor der Zugabe). Messwerte von Buffi et al. 2025 '
                 '(doi 10.17632/srkxbkh6sp.1, CC BY 4.0), ausgewertet von OpenMycoNet', fontsize=10)
    fig.savefig(ZIEL / 'f1_umatrix.png', dpi=110)


if __name__ == '__main__':
    main()
