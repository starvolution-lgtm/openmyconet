"""Nachrechnung mit refesom, R4: Ursachentest Endradius (NACHRECHNUNG_REFESOM.md, Abschnitt 7e).

Läuft im Analyse-venv, ohne refesom: unsere Karte `karte-v1` genau wie in A4 (40 × 60 Torus,
40 Epochen, Initialisierung aus Datenpunkten), nur mit `sigma_ende = 1,0` statt 0,75. Seeds 0–9,
Sätze P und PL. Wiederfinden der A4-Kandidaten wie in V3 (Jaccard ≥ 0,5 mit der Seed-0-Karte
aus A4). Entscheidungsregel vorab in 7e; dieses Skript wendet sie nur an.

    venv/Scripts/python.exe -m werkzeuge.nachrechnung_r4

Schreibt ergebnisse/nachrechnung/laeufe/R4_{satz}_s{seed}.npz (nur lokal) und
ergebnisse/nachrechnung/r4.json.
SIMULATION: Simulationsdaten, keine Messwerte.
"""
import os

for _v in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '2')

import json
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from mm.karte import BatchSOM
from werkzeuge.nachrechnung_auswerten import (
    LAEUFE,
    SAETZE,
    SEEDS,
    WURZEL,
    bester_treffer,
    einstufen,
)

ZIEL = LAEUFE.parent / 'r4.json'
SIGMA_ENDE = 1.0
GROESSE = (40, 60)
EPOCHEN = 40
# 7e: geprüfte Kandidaten (in A4 stabil, in R2 nicht reproduziert) und Gegenprobe (in R2 reproduziert)
GEPRUEFT = {'P': (3, 10), 'PL': (1, 13, 28, 37, 46)}
GEGENPROBE = {'P': (16, 13), 'PL': (52, 2)}


def job(auftrag):
    satz, seed = auftrag
    datei = LAEUFE / f'R4_{satz}_s{seed}.npz'
    x = np.load(WURZEL / 'ergebnisse' / 'a3' / f'merkmale_{satz}.npz')['x']
    t0 = time.time()
    if datei.exists():
        z = np.load(datei)
        k = BatchSOM(*GROESSE, toroidal=True, seed=seed)
        k.w = z['w']
    else:
        k = BatchSOM(*GROESSE, toroidal=True, seed=seed).trainieren(x, epochen=EPOCHEN, sigma_ende=SIGMA_ENDE)
    bmu = k.bmu(x)
    gruppe, art = k.gruppen(bmu)
    np.savez(datei, w=k.w, bmu=bmu)
    return {'satz': satz, 'seed': seed, 'komp': gruppe[bmu].astype(np.int32),
            'qe': float(k.quantisierungsfehler(x, bmu).mean()), 'te': float(k.topologiefehler(x)),
            'n_gruppen': sum(a == 'gruppe' for a in art.values()),
            'n_inseln': sum(a == 'insel' for a in art.values()), 'sekunden': round(time.time() - t0, 1)}


def partner(idx, kid, g0, laeufe):
    """Wie nachrechnung_ursache: A4-Komponenten, die mit ≥ 10 % der Kandidatengröße mitgezogen werden."""
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
    ursache = json.loads((LAEUFE.parent / 'ursache_r2.json').read_text(encoding='utf-8'))
    r1r2 = json.loads((LAEUFE.parent / 'r1_r2.json').read_text(encoding='utf-8'))
    LAEUFE.mkdir(parents=True, exist_ok=True)
    auftraege = [(satz, s) for satz in SAETZE for s in SEEDS]
    with ProcessPoolExecutor(4) as ex:
        ergebnisse = list(ex.map(job, auftraege))
    erg = {'simuliert': True, 'hinweis': 'SIMULATION (Sandbox-Szenarien sbx-gen-1.0), keine Messdaten',
           'regeln': 'NACHRECHNUNG_REFESOM.md, Abschnitt 7e', 'karte': 'karte-v1 (mm.karte.BatchSOM)',
           'sigma_ende': SIGMA_ENDE, 'groesse': GROESSE, 'epochen': EPOCHEN, 'saetze': {}}
    verloren, gegen_fehlt = [], []
    for satz in SAETZE:
        laeufe = [e for e in ergebnisse if e['satz'] == satz]
        g0 = basis[f'{satz}_torus_0.75_seed0']
        r2 = {z['id']: z for z in r1r2['schritte']['R2'][satz]['kandidaten']}
        urs = {z['id']: z for z in ursache['saetze'][satz]}
        zeilen = []
        for kd in a4['saetze'][satz]['kandidaten']:
            kid = kd['id']
            idx = np.where(g0 == kid)[0]
            menge = set(idx.tolist())
            n = sum(bester_treffer(menge, lf['komp'])[0] >= 0.5 for lf in laeufe)
            rolle = 'geprueft' if kid in GEPRUEFT[satz] else 'gegenprobe' if kid in GEGENPROBE[satz] else None
            p, im_rest = partner(idx, kid, g0, laeufe)
            z = {'id': kid, 'rolle': rolle, 'fenster_a4': len(idx), 'a4_wiedergefunden_von_10':
                 kd['wiedergefunden_von_10'], 'r2_refesom_wiedergefunden': r2[kid]['wiedergefunden'],
                 'r4_wiedergefunden': int(n), 'r4_urteil': einstufen(n),
                 'r4_partner': p, 'r4_im_rest': im_rest,
                 'r2_partner': urs[kid]['mitgezogen_laeufe'], 'r2_im_rest': urs[kid]['laeufe_im_rest']}
            zeilen.append(z)
            if rolle == 'geprueft' and n < 8:
                verloren.append(f'{satz} K{kid}')
            if rolle == 'gegenprobe' and n < 8:
                gegen_fehlt.append(f'{satz} K{kid}')
            print(f"{satz:<2} K{kid:<3} {rolle or '':<10} n={len(idx):>4}  A4 {kd['wiedergefunden_von_10']:>2}/10"
                  f"  R2 {r2[kid]['wiedergefunden']:>2}/10  R4 {n:>2}/10  im Rest {im_rest}"
                  f"  R4 mit: {dict(Counter(p).most_common(4))}")
        erg['saetze'][satz] = {
            'qe_median': float(np.median([lf['qe'] for lf in laeufe])),
            'te_median': float(np.median([lf['te'] for lf in laeufe])),
            'gruppen_median': float(np.median([lf['n_gruppen'] for lf in laeufe])),
            'inseln_median': float(np.median([lf['n_inseln'] for lf in laeufe])),
            'sekunden_median': float(np.median([lf['sekunden'] for lf in laeufe])),
            'kandidaten': zeilen}
        s = erg['saetze'][satz]
        print(f"{satz}: QE {s['qe_median']:.3f}, TE {s['te_median']:.3f}, Gruppen {s['gruppen_median']:.0f}, "
              f"Inseln {s['inseln_median']:.0f}")
    anzahl = len(verloren)
    urteil = 'überwiegend' if anzahl >= 5 else 'teilweise' if anzahl >= 3 else 'nicht'
    erg['urteil'] = {'verloren': verloren, 'anzahl_verloren_von_7': anzahl,
                     'endradius_erklaert_abweichung': urteil,
                     'gegenprobe_nicht_reproduziert': gegen_fehlt, 'unter_vorbehalt': bool(gegen_fehlt)}
    ZIEL.write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding='utf-8')
    print('Urteil 7e:', erg['urteil'])


if __name__ == '__main__':
    main()
