"""A4: Beispielfenster der berichteten Kandidaten in den Rohdaten (Kriterium 8b.3b).

Aufruf (nach a4_laufen): venv/Scripts/python.exe -m werkzeuge.a4_beispiele daten/<schnappschuss>.tar
Kandidat = Komponente der Seed-0-Karte (toroidal, Endradius 0,75), wie in metriken.json.
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

ZIEL = Path('ergebnisse/a4')
VORBEREITUNG = Path('ergebnisse/a3/vorbereitung.npz')
HINWEIS = 'SIMULATION (Sandbox sbx-gen-1.0) – keine Messdaten'


def kennwerte(x):
    """Einfache, lageunabhaengige Beschreibung je Fenster (nur zur Benennung im Bericht)."""
    h = x.shape[1] // 2
    sprung = np.abs(x[:, h:].mean(1) - x[:, :h].mean(1))
    d = np.abs(np.diff(x, axis=1))
    groesster_schritt = d.max(1)
    lage = d.argmax(1) / x.shape[1]
    return sprung, groesster_schritt, lage


def main():
    s = Schnappschuss(sys.argv[1])
    segs = s.segmente([int(k['id']) for k in s.kanaele('bioelectric_potential')])
    fw = F.fenster_bilden(segs, 10.0, 5.0)
    v = np.load(VORBEREITUNG, allow_pickle=False)
    zeilen_je_satz = {'P': np.arange(len(v['P'])), 'PL': np.where(~np.isnan(v['L'][:, 2]))[0]}
    m = json.loads((ZIEL / 'metriken.json').read_text(encoding='utf-8'))
    laeufe = np.load(ZIEL / 'laeufe_basis.npz')
    rate = segs[0].rate_hz
    auswahl = []
    for satz in ('P', 'PL'):
        g = laeufe[f'{satz}_torus_0.75_seed0']
        for k in m['saetze'][satz]['kandidaten']:
            fenster = zeilen_je_satz[satz][np.where(g == k['id'])[0]]
            auswahl.append((satz, k, fenster))
    fig, ax = plt.subplots(len(auswahl), 4, figsize=(16, 2.1 * len(auswahl)), squeeze=False)
    rng = np.random.default_rng(0)
    zusammenfassung = []
    for zeile, (satz, k, idx) in enumerate(auswahl):
        x = F.fenstermatrix(segs, fw, idx)
        sprung, schritt, lage = kennwerte(x)
        zusammenfassung.append({
            'satz': satz, 'id': k['id'], 'art': k['art'], 'fenster': len(idx), 'stufe': k['stufe'],
            'sprung_median_uV': round(float(np.median(sprung)), 2),
            'groesster_einzelschritt_median_uV': round(float(np.median(schritt)), 2),
            'lage_groesster_schritt_quartile': [round(float(q), 2) for q in np.quantile(lage, [0.25, 0.5, 0.75])],
            'streuung_median_uV': round(float(np.median(x.std(1))), 2)})
        for spalte, j in enumerate(rng.choice(len(idx), min(4, len(idx)), replace=False)):
            t = np.arange(x.shape[1]) / rate
            a = ax[zeile, spalte]
            a.plot(t, x[j], lw=0.4, color='#1f4e79')
            a.set_title(f'{satz} K{k["id"]} ({k["art"]}, {len(idx)} F.) – {fw.kennung(int(idx[j]))[:3]}', fontsize=7)
            a.tick_params(labelsize=6)
        ax[zeile, 0].set_ylabel('µV', fontsize=7)
    fig.suptitle(f'A4: Beispielfenster der berichteten Kandidaten (Seed 0, toroidal, Endradius 0,75), 10 s je Fenster\n{HINWEIS}')
    fig.tight_layout()
    fig.savefig(ZIEL / 'abbildungen' / 'beispiele_kandidaten.png', dpi=90)
    # Vergleich: alle Fenster (Referenz fuer die Kennwerte)
    ref = F.fenstermatrix(segs, fw, rng.choice(len(fw.segment), 3000, replace=False))
    sp, sc, _ = kennwerte(ref)
    zusammenfassung.append({'satz': 'Referenz', 'id': 'zufällige 3000 Fenster',
                            'sprung_median_uV': round(float(np.median(sp)), 2),
                            'groesster_einzelschritt_median_uV': round(float(np.median(sc)), 2),
                            'streuung_median_uV': round(float(np.median(ref.std(1))), 2)})
    (ZIEL / 'beispiele.json').write_text(json.dumps(zusammenfassung, indent=1, ensure_ascii=False), encoding='utf-8')
    for z in zusammenfassung:
        print(z)


if __name__ == '__main__':
    main()
