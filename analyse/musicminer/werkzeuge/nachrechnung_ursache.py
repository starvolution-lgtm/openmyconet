"""Nachrechnung mit pydbt: Ursachensuche für Abweichungen in R2 (NACHRECHNUNG_PYDBT.md, Abschnitt 6).

Beschreibend, keine neue Entscheidungsregel. Für jeden A4-Kandidaten und jeden R2-Lauf:
- in welcher pydbt-Komponente die meisten Kandidatenfenster liegen (Anteil),
- wie groß diese Komponente im Verhältnis zum Kandidaten ist,
- ob sie die größte Komponente ist („Rest“),
- welche anderen A4-Komponenten der Seed-0-Karte darin mit ≥ 10 % der Kandidatengröße stecken.

    venv/Scripts/python.exe -m werkzeuge.nachrechnung_ursache

Schreibt ergebnisse/nachrechnung/ursache_r2.json.
SIMULATION: Simulationsdaten, keine Messwerte.
"""
import json
from collections import Counter

import numpy as np

from werkzeuge.nachrechnung_auswerten import (
    LAEUFE,
    SAETZE,
    SEEDS,
    WURZEL,
    lauf_auswerten,
)

ZIEL = LAEUFE.parent / 'ursache_r2.json'


def main():
    a4 = json.loads((WURZEL / 'ergebnisse' / 'a4' / 'metriken.json').read_text(encoding='utf-8'))
    basis = np.load(WURZEL / 'ergebnisse' / 'a4' / 'laeufe_basis.npz')
    erg = {'simuliert': True, 'hinweis': 'SIMULATION (Sandbox-Szenarien sbx-gen-1.0), keine Messdaten',
           'schritt': 'R2', 'saetze': {}}
    for satz in SAETZE:
        x = np.load(WURZEL / 'ergebnisse' / 'a3' / f'merkmale_{satz}.npz')['x']
        g0 = basis[f'{satz}_torus_0.75_seed0']
        rest_a4 = int(np.bincount(g0).argmax())
        laeufe = [lauf_auswerten('R2', satz, s, x) for s in SEEDS]
        zeilen = []
        for kd in a4['saetze'][satz]['kandidaten']:
            idx = np.where(g0 == kd['id'])[0]
            anteil, verhaeltnis, im_rest, partner = [], [], 0, Counter()
            for lf in laeufe:
                k = lf['komp']
                dom = int(np.bincount(k[idx]).argmax())
                m = np.where(k == dom)[0]
                anteil.append(float(np.mean(k[idx] == dom)))
                verhaeltnis.append(len(m) / len(idx))
                if dom == int(np.bincount(k).argmax()):
                    im_rest += 1
                    continue
                for a, c in Counter(g0[m].tolist()).items():
                    if a != kd['id'] and c >= 0.1 * len(idx):
                        partner['Rest' if a == rest_a4 else f'K{a}'] += 1
            zeilen.append({'id': kd['id'], 'fenster': len(idx),
                           'anteil_in_haupt_komponente_median': round(float(np.median(anteil)), 3),
                           'komponente_zu_kandidat_median': round(float(np.median(verhaeltnis)), 2),
                           'laeufe_im_rest': im_rest,
                           'mitgezogen_laeufe': dict(partner.most_common())})
            z = zeilen[-1]
            print(f"{satz:<2} K{z['id']:<3} n={z['fenster']:>4}  zusammen {z['anteil_in_haupt_komponente_median']:.2f}"
                  f"  Komponente/Kandidat {z['komponente_zu_kandidat_median']:>8.2f}  im Rest {im_rest:>2}/10"
                  f"  mit: {dict(partner.most_common(4))}")
        erg['saetze'][satz] = zeilen
    ZIEL.write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
