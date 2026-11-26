"""Nachrechnung mit refesom: V4 aus R2 + R3 (NACHRECHNUNG_REFESOM.md, Abschnitt 6, V4 und Gesamturteil).

Läuft im Analyse-venv. Rechnet genau wie A4 (`werkzeuge.a4_laufen`, `mm.kriterien`), nur mit den
refesom-Läufen: Schwellen nach E1 (9.2 größenabhängig, 9.3 global) aus den R3-Nullläufen, Kandidaten
aus R2 (9.1: Komponenten der Seed-0-Karte außer der größten, in ≥ 5 von 10 Läufen), dazu 8b.1
(stabil) und 8b.3a (Baum Tiefe 2). 8b.4b und 8b.5 werden nicht wiederholt; ein Kandidat kann hier
höchstens „würde Schwellen bestehen“ heißen.

Für das Gesamturteil: Besteht ein R2-Kandidat die globale Schwelle, der sie in A4 nicht bestanden
hat? Zuordnung zu A4 über Jaccard ≥ 0,5 mit den A4-Kandidaten (Seed-0-Karte); ohne Gegenstück
gilt ein Kandidat als „in A4 nicht bestanden“.

    venv/Scripts/python.exe -m werkzeuge.nachrechnung_v4

Schreibt ergebnisse/nachrechnung/v4.json.
SIMULATION: Simulationsdaten, keine Messwerte.
"""
import json

import numpy as np
from sklearn.metrics import f1_score
from sklearn.tree import DecisionTreeClassifier

from mm import kriterien as KR
from mm.karte import BatchSOM
from werkzeuge.a3_laufen import merkmalssatz
from werkzeuge.a4_laufen import VORBEREITUNG, _jaccard, kandidaten
from werkzeuge.nachrechnung_auswerten import LAEUFE, SAETZE, WURZEL

ZIEL = LAEUFE.parent / 'v4.json'
NULLDATEN = LAEUFE.parent / 'nulldaten'
NULL_SEEDS = range(25)


def lauf(datei, x, seed):
    """refesom-Gewichte in unsere Karte, Gruppen + Abgrenzung mit unserem Code (wie A4, job_karte)."""
    z = np.load(datei)
    k = BatchSOM(40, 60, toroidal=True, seed=seed)
    k.w = z['w']
    bmu = z['bmu'].astype(int)
    gruppe, art = k.gruppen(bmu)
    gw = gruppe[bmu]
    ab = k.abgrenzung(x, bmu, gruppe)
    return {'seed': seed, '_gruppe_fenster': gw, 'abgrenzung': ab, 'art_je_gruppe': art,
            'komponenten': [(int((gw == g).sum()), float(ab.get(int(g), float('nan')))) for g in np.unique(gw)]}


def main():
    a4 = json.loads((WURZEL / 'ergebnisse' / 'a4' / 'metriken.json').read_text(encoding='utf-8'))
    basis = np.load(WURZEL / 'ergebnisse' / 'a4' / 'laeufe_basis.npz')
    v = dict(np.load(WURZEL / VORBEREITUNG, allow_pickle=False))
    erg = {'simuliert': True, 'hinweis': 'SIMULATION (Sandbox-Szenarien sbx-gen-1.0), keine Messdaten',
           'kriterien': KR.VERSION, 'regeln': 'NACHRECHNUNG_REFESOM.md, Abschnitt 6 (V4)', 'saetze': {}}
    neu_global = []
    for satz in SAETZE:
        x, zeilen, _ = merkmalssatz(v, satz)
        assert np.array_equal(x, np.load(WURZEL / 'ergebnisse' / 'a3' / f'merkmale_{satz}.npz')['x'])
        roh = v['P'][zeilen] if satz == 'P' else np.hstack([v['P'], v['L']])[zeilen]
        echt = [lauf(LAEUFE / f'R2_{satz}_s{s}.npz', x, s) for s in range(10)]
        null = []
        for art in ('N1', 'N2'):
            for s in NULL_SEEDS:
                xn = np.load(NULLDATEN / f'{satz}_{art}_s{s}.npz')['x']
                null.append(lauf(LAEUFE / f'R3_{satz}_{art}_s{s}.npz', xn, s)['komponenten'])
        kand = [k for k in kandidaten(echt[0], echt) if k['wiedergefunden'] >= 5]
        klassen = sorted({KR.klasse(k['groesse']) for k in kand if KR.klasse(k['groesse']) is not None})
        anzahl_k = max(1, len(klassen))
        glob = KR.schwelle_global(null)
        # A4-Kandidaten (Seed-0-Karte) mit ihrem Ergebnis der globalen Schwelle
        g0 = basis[f'{satz}_torus_0.75_seed0']
        a4_kand = {kd['id']: (set(np.where(g0 == kd['id'])[0].tolist()), kd['pruefungen']['global'])
                   for kd in a4['saetze'][satz]['kandidaten']}
        zeilen_k = []
        for k in kand:
            idx = np.fromiter(k['menge'], int)
            y = np.zeros(len(x), bool)
            y[idx] = True
            kl = KR.klasse(k['groesse'])
            gt = KR.schwelle_klasse(null, kl, anzahl_k) if kl is not None else None
            besteht_groesse = bool(gt and gt['genug_nulldaten'] and k['A'] > gt['schwelle'])
            besteht_global = glob['schwelle'] is None or k['A'] > glob['schwelle']
            baum = DecisionTreeClassifier(max_depth=2, class_weight='balanced', random_state=0).fit(roh, y)
            f1 = float(f1_score(y, baum.predict(roh)))
            j_best, a4_id = max(((_jaccard(k['menge'], m), i) for i, (m, _) in a4_kand.items()), default=(0.0, None))
            a4_global = a4_kand[a4_id][1] if j_best >= 0.5 else False
            pruef = {'stabil': k['wiedergefunden'] >= 8, 'global': bool(besteht_global),
                     'groesse': besteht_groesse, 'nachpruefbar': f1 >= 0.8}
            z = {'id': k['id'], 'art': k['art'], 'fenster_seed0': len(idx), 'groesse_median': k['groesse'],
                 'klasse': KR.klassenname(kl) if kl is not None else '< 10', 'A_abgrenzung_median': k['A'],
                 'wiedergefunden_von_10': k['wiedergefunden'], 'baum_f1': round(f1, 3),
                 'groessentest': gt, 'pruefungen': pruef,
                 'wuerde_schwellen_bestehen': pruef['stabil'] and pruef['nachpruefbar']
                 and (pruef['global'] or pruef['groesse']),
                 'a4_gegenstueck': f'K{a4_id}' if j_best >= 0.5 else None, 'a4_jaccard': round(j_best, 3),
                 'a4_global_bestanden': bool(a4_global)}
            zeilen_k.append(z)
            if besteht_global and not a4_global:
                neu_global.append(f'{satz} K{k["id"]}')
            print(f"{satz:<2} K{z['id']:<3} n={z['fenster_seed0']:>5} A {z['A_abgrenzung_median']:5.2f} "
                  f"{z['wiedergefunden_von_10']:>2}/10 F1 {f1:.2f} G {'✓' if besteht_global else '✗'} "
                  f"K {'✓' if besteht_groesse else '✗'}  A4: {z['a4_gegenstueck']} (J {j_best:.2f}, "
                  f"global {'✓' if a4_global else '✗'})")
        a4s = a4['saetze'][satz]
        erg['saetze'][satz] = {
            'nulllaeufe': len(null), 'nullkomponenten_gesamt': sum(len(n) for n in null),
            'globale_schwelle': glob, 'a4_globale_schwelle': a4s['globale_schwelle'],
            'a4_nullkomponenten_gesamt': a4s['nullkomponenten_gesamt'],
            'klassen_geprueft': [KR.klassenname(c) for c in klassen],
            'kandidaten_r2': zeilen_k,
            'nicht_berichtet_unter_5_seeds': len(kandidaten(echt[0], echt)) - len(kand)}
        print(f"{satz}: globale Schwelle refesom {glob['schwelle']:.2f} ({glob['nullkomponenten']} Nullkomponenten), "
              f"A4 {a4s['globale_schwelle']['schwelle']:.2f}")
    erg['v4'] = {'kandidaten_global_neu_bestanden': neu_global, 'v4_erfuellt': not neu_global}
    ZIEL.write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding='utf-8')
    print('V4 (kein neuer Kandidat über der globalen Schwelle):', not neu_global, neu_global)


if __name__ == '__main__':
    main()
