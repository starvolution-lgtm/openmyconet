"""Nachrechnung mit pydbt, R5: Auswertung nach Abschnitt 7f (NACHRECHNUNG_PYDBT.md).

Läuft im Analyse-venv (braucht pydbt NICHT). Wie R2 (V1–V3): pydbt-Gewichte und Gewinnerneuronen
aus ergebnisse/nachrechnung/laeufe/R5_*.npz in unsere Kartenklasse, Gruppen nach Regel v2,
Wiederfinden mit Jaccard ≥ 0,5 gegen die A4-Seed-0-Karte. Danach die vorab festgelegte
Entscheidung aus 7f. Verschmelzungspartner wie in `nachrechnung_ursache`.

    venv/Scripts/python.exe -m werkzeuge.nachrechnung_r5

Schreibt ergebnisse/nachrechnung/r5.json.
SIMULATION: Simulationsdaten, keine Messwerte.
"""
import json
from collections import Counter

import numpy as np

from mm.karte import BatchSOM
from werkzeuge.nachrechnung_auswerten import (
    BEKANNT,
    LAEUFE,
    SAETZE,
    SEEDS,
    WURZEL,
    bester_treffer,
    einstufen,
    jaccard,
)

ZIEL = LAEUFE.parent / 'r5.json'
GEGENPROBE = {'P': (16, 13), 'PL': (52, 2)}


def lauf(satz, seed, x):
    z = np.load(LAEUFE / f'R5_{satz}_s{seed}.npz')
    meta = json.loads(str(z['meta']))
    k = BatchSOM(40, 60, toroidal=True, seed=seed)
    k.w = z['w']
    bmu = z['bmu'].astype(int)
    gruppe, art = k.gruppen(bmu)
    return {'meta': meta, 'komp': gruppe[bmu], 'abgrenzung': k.abgrenzung(x, bmu, gruppe),
            'qe': float(k.quantisierungsfehler(x, bmu).mean()), 'te': float(k.topologiefehler(x)),
            'n_gruppen': sum(a == 'gruppe' for a in art.values()),
            'n_inseln': sum(a == 'insel' for a in art.values())}


def partner(idx, kid, g0, laeufe):
    rest_a4 = int(np.bincount(g0).argmax())
    zaehler, im_rest = Counter(), 0
    for lf in laeufe:
        k = lf['komp']
        dom = int(np.bincount(k[idx]).argmax())
        if dom == int(np.bincount(k).argmax()):
            im_rest += 1
            continue
        for a, c in Counter(g0[k == dom].tolist()).items():
            if a != kid and c >= 0.1 * len(idx):
                zaehler['Rest' if a == rest_a4 else f'K{a}'] += 1
    return dict(zaehler.most_common()), im_rest


def main():
    a4 = json.loads((WURZEL / 'ergebnisse' / 'a4' / 'metriken.json').read_text(encoding='utf-8'))
    basis = np.load(WURZEL / 'ergebnisse' / 'a4' / 'laeufe_basis.npz')
    r1r2 = json.loads((LAEUFE.parent / 'r1_r2.json').read_text(encoding='utf-8'))
    r4 = json.loads((LAEUFE.parent / 'r4.json').read_text(encoding='utf-8'))
    erg = {'simuliert': True, 'hinweis': 'SIMULATION (Sandbox-Szenarien sbx-gen-1.0), keine Messdaten',
           'regeln': 'NACHRECHNUNG_PYDBT.md, Abschnitt 7f', 'saetze': {}}
    alle, gegen_fehlt, commits, pfade = [], [], set(), set()
    for satz in SAETZE:
        x = np.load(WURZEL / 'ergebnisse' / 'a3' / f'merkmale_{satz}.npz')['x']
        g0 = basis[f'{satz}_torus_0.75_seed0']
        a4_mengen = {int(i): set(np.where(g0 == i)[0].tolist()) for i in np.unique(g0)}
        groesste_a4 = max(a4_mengen, key=lambda i: len(a4_mengen[i]))
        laeufe = [lauf(satz, s, x) for s in SEEDS]
        commits |= {lf['meta']['pydbt_commit'] for lf in laeufe}
        pfade |= {lf['meta'].get('pydbt_pfad') for lf in laeufe}
        r2 = {z['id']: z for z in r1r2['schritte']['R2'][satz]['kandidaten']}
        r4k = {z['id']: z for z in r4['saetze'][satz]['kandidaten']}
        zeilen = []
        for kd in a4['saetze'][satz]['kandidaten']:
            kid = kd['id']
            menge = a4_mengen[kid]
            idx = np.fromiter(menge, int)
            n = sum(bester_treffer(menge, lf['komp'])[0] >= 0.5 for lf in laeufe)
            p, im_rest = partner(idx, kid, g0, laeufe)
            z = {'id': kid, 'bekannt': BEKANNT[satz].get(kid), 'fenster_a4': len(menge),
                 'a4_wiedergefunden_von_10': kd['wiedergefunden_von_10'],
                 'a4_stabil_8b1': kd['wiedergefunden_von_10'] >= 8,
                 'r2': r2[kid]['wiedergefunden'], 'r4': r4k[kid]['r4_wiedergefunden'],
                 'r5': int(n), 'urteil': einstufen(n), 'r5_partner': p, 'r5_im_rest': im_rest}
            zeilen.append(z)
            alle.append(z)
            if kid in GEGENPROBE[satz] and n < 8:
                gegen_fehlt.append(f'{satz} K{kid}')
            print(f"{satz:<2} K{kid:<3} {z['bekannt'] or '':<10} A4 {z['a4_wiedergefunden_von_10']:>2}  "
                  f"R2 {z['r2']:>2}  R4 {z['r4']:>2}  R5 {n:>2}  im Rest {im_rest}  mit: {dict(Counter(p).most_common(4))}")
        neu = []
        k0 = laeufe[0]['komp']
        ids, anz = np.unique(k0, return_counts=True)
        for i in ids[ids != ids[anz.argmax()]]:
            menge = set(np.where(k0 == i)[0].tolist())
            n = sum(bester_treffer(menge, lf['komp'])[0] >= 0.5 for lf in laeufe)
            if n < 5:
                continue
            j_kand = max(jaccard(menge, a4_mengen[kd['id']]) for kd in a4['saetze'][satz]['kandidaten'])
            if j_kand < 0.5:
                j_alle = max(jaccard(menge, m) for i2, m in a4_mengen.items() if i2 != groesste_a4)
                neu.append({'fenster': len(menge), 'wiedergefunden': int(n),
                            'jaccard_bester_a4_kandidat': round(j_kand, 3),
                            'jaccard_beste_a4_komponente': round(j_alle, 3)})
        erg['saetze'][satz] = {
            'qe_median': float(np.median([lf['qe'] for lf in laeufe])),
            'te_median': float(np.median([lf['te'] for lf in laeufe])),
            'gruppen_median': float(np.median([lf['n_gruppen'] for lf in laeufe])),
            'inseln_median': float(np.median([lf['n_inseln'] for lf in laeufe])),
            'minuten_median': float(np.median([lf['meta']['sekunden'] for lf in laeufe]) / 60),
            'kandidaten': zeilen, 'neue_komponenten': neu}
        s = erg['saetze'][satz]
        print(f"{satz}: QE {s['qe_median']:.3f}, TE {s['te_median']:.3f}, Gruppen {s['gruppen_median']:.0f}, "
              f"Inseln {s['inseln_median']:.0f}, {s['minuten_median']:.1f} min/Lauf, neue Komponenten {len(neu)}")
    stabil = [z for z in alle if z['a4_stabil_8b1']]
    n_rep = sum(z['r5'] >= 8 for z in stabil)
    v2 = all(z['r5'] >= 8 for z in alle if z['bekannt'])
    if v2 and n_rep >= 8:
        urteil = 'weitgehend'
    elif n_rep >= 6:
        urteil = 'teilweise'
    else:
        urteil = 'nicht'
    erg['pydbt_commit'] = sorted(commits)
    erg['pydbt_pfad'] = sorted(p for p in pfade if p)
    erg['urteil'] = {'stabile_a4_kandidaten': len(stabil), 'davon_reproduziert': n_rep,
                     'r2_reproduziert': sum(z['r2'] >= 8 for z in stabil), 'v2_reproduziert': v2,
                     'nachbarschaft_erklaert_abweichung': urteil,
                     'gegenprobe_nicht_reproduziert': gegen_fehlt, 'unter_vorbehalt': bool(gegen_fehlt)}
    ZIEL.write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding='utf-8')
    print('Urteil 7f:', erg['urteil'], '| Commit', erg['pydbt_commit'])


if __name__ == '__main__':
    main()
