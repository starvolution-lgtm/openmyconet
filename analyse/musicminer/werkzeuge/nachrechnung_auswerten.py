"""Nachrechnung mit refesom: Auswertung R1/R2 nach V1–V3 (NACHRECHNUNG_REFESOM.md, Abschnitt 6, 7d).

Läuft im Analyse-venv (braucht refesom NICHT): Die refesom-Gewichte und Gewinnerneuronen aus
ergebnisse/nachrechnung/laeufe/ werden in unsere Kartenklasse gesetzt; Gruppen (Regel v2),
Abgrenzung, Quantisierungs- und Topologiefehler rechnet UNSER Code, genau wie in Phase A.

    venv/Scripts/python.exe -m werkzeuge.nachrechnung_auswerten

Schreibt ergebnisse/nachrechnung/r1_r2.json. Fehlen Läufe, wird ausgewertet, was da ist, und
das Ergebnis als unvollständig markiert (kein Urteil).
SIMULATION: Simulationsdaten, keine Messwerte.
"""
import json
from pathlib import Path

import numpy as np

from mm.karte import BatchSOM
from werkzeuge.refesom_laden import meta_wert

WURZEL = Path(__file__).resolve().parents[1]
LAEUFE = WURZEL / 'ergebnisse' / 'nachrechnung' / 'laeufe'
ZIEL = WURZEL / 'ergebnisse' / 'nachrechnung' / 'r1_r2.json'
SCHRITTE = {'R1': (50, 80), 'R2': (40, 60)}
SAETZE = ('P', 'PL')
SEEDS = range(10)
# Bekannte Strukturen (V2), Kennungen der Seed-0-Karte aus A4
BEKANNT = {'P': {16: 'Sättigung'}, 'PL': {52: 'Sättigung', 13: 'Reaktion'}}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a or b else 0.0


def bester_treffer(menge, komp):
    """Beste Jaccard-Übereinstimmung einer Fenstermenge mit einer Komponente (Fenster → Komponente)."""
    best, best_k = 0.0, None
    for k in np.unique(komp[np.fromiter(menge, int)]):
        j = jaccard(menge, set(np.where(komp == k)[0].tolist()))
        if j > best:
            best, best_k = j, int(k)
    return best, best_k


def reinheit(menge, bmu):
    """Anteil der Kandidatenfenster, deren Gewinnerneuron überwiegend (≥ 50 %) Kandidatenfenster trägt."""
    idx = np.fromiter(menge, int)
    im_kand = np.zeros(len(bmu), bool)
    im_kand[idx] = True
    gut = 0
    for n in np.unique(bmu[idx]):
        m = bmu == n
        if im_kand[m].mean() >= 0.5:
            gut += int((m & im_kand).sum())
    return gut / len(idx)


def lauf_auswerten(schritt, satz, seed, x):
    z = np.load(LAEUFE / f'{schritt}_{satz}_s{seed}.npz')
    meta = json.loads(str(z['meta']))
    zeilen, spalten = SCHRITTE[schritt]
    k = BatchSOM(zeilen, spalten, toroidal=True, seed=seed)
    k.w = z['w']
    bmu = z['bmu'].astype(int)
    gruppe, art = k.gruppen(bmu)
    komp = gruppe[bmu]
    return {'meta': meta, 'bmu': bmu, 'komp': komp, 'abgrenzung': k.abgrenzung(x, bmu, gruppe),
            'qe': float(k.quantisierungsfehler(x, bmu).mean()), 'te': float(k.topologiefehler(x)),
            'n_gruppen': sum(a == 'gruppe' for a in art.values()),
            'n_inseln': sum(a == 'insel' for a in art.values())}


def einstufen(n):
    return 'reproduziert' if n >= 8 else 'teilweise' if n >= 5 else 'nicht reproduziert'


def main():
    a4 = json.loads((WURZEL / 'ergebnisse' / 'a4' / 'metriken.json').read_text(encoding='utf-8'))
    basis = np.load(WURZEL / 'ergebnisse' / 'a4' / 'laeufe_basis.npz')
    erg = {'simuliert': True, 'hinweis': 'SIMULATION (Sandbox-Szenarien sbx-gen-1.0), keine Messdaten',
           'regeln': 'NACHRECHNUNG_REFESOM.md, Abschnitt 6 und 7d', 'schritte': {}}
    vollstaendig = True
    for satz in SAETZE:
        x = np.load(WURZEL / 'ergebnisse' / 'a3' / f'merkmale_{satz}.npz')['x']
        g0 = basis[f'{satz}_torus_0.75_seed0']
        kandidaten = a4['saetze'][satz]['kandidaten']
        a4_mengen = {int(i): set(np.where(g0 == i)[0].tolist()) for i in np.unique(g0)}
        groesste_a4 = max(a4_mengen, key=lambda i: len(a4_mengen[i]))
        for schritt in SCHRITTE:
            vorhanden = [s for s in SEEDS if (LAEUFE / f'{schritt}_{satz}_s{s}.npz').exists()]
            if len(vorhanden) < len(SEEDS):
                vollstaendig = False
            if not vorhanden:
                continue
            laeufe = {s: lauf_auswerten(schritt, satz, s, x) for s in vorhanden}
            zeilen = []
            for kd in kandidaten:
                menge = a4_mengen[kd['id']]
                treffer = [bester_treffer(menge, laeufe[s]['komp']) for s in vorhanden]
                gefunden = [(s, kk) for s, (j, kk) in zip(vorhanden, treffer, strict=True) if j >= 0.5]
                ab = [laeufe[s]['abgrenzung'].get(kk, float('nan')) for s, kk in gefunden]
                zeilen.append({
                    'id': kd['id'], 'bekannt': BEKANNT[satz].get(kd['id']), 'a4_stufe': kd['stufe'],
                    'a4_wiedergefunden_von_10': kd['wiedergefunden_von_10'],
                    'a4_stabil_8b1': kd['wiedergefunden_von_10'] >= 8, 'fenster_a4': len(menge),
                    'wiedergefunden': len(gefunden), 'von': len(vorhanden), 'urteil': einstufen(len(gefunden)),
                    'jaccard_median': float(np.median([j for j, _ in treffer])),
                    'abgrenzung_median': float(np.nanmedian(ab)) if ab else None,
                    'a4_abgrenzung_median': kd['A_abgrenzung_median'],
                    'reinheit_median': float(np.median([reinheit(menge, laeufe[s]['bmu']) for s in vorhanden])),
                })
            # Neue Komponenten: Seed-0-Komponenten (ohne größte) in ≥ 5 Läufen, die keinem A4-Kandidaten entsprechen
            neu = []
            if 0 in laeufe:
                k0 = laeufe[0]['komp']
                ids, anz = np.unique(k0, return_counts=True)
                for i in ids[ids != ids[anz.argmax()]]:
                    menge = set(np.where(k0 == i)[0].tolist())
                    n = sum(bester_treffer(menge, laeufe[s]['komp'])[0] >= 0.5 for s in vorhanden)
                    if n < 5:
                        continue
                    j_kand = max(jaccard(menge, a4_mengen[kd['id']]) for kd in kandidaten)
                    j_alle = max(jaccard(menge, m) for i2, m in a4_mengen.items() if i2 != groesste_a4)
                    if j_kand < 0.5:
                        neu.append({'fenster': len(menge), 'wiedergefunden': int(n),
                                    'jaccard_bester_a4_kandidat': round(j_kand, 3),
                                    'jaccard_beste_a4_komponente': round(j_alle, 3)})
            erg['schritte'].setdefault(schritt, {})[satz] = {
                'laeufe': len(vorhanden), 'seeds': vorhanden,
                'qe_median': float(np.median([lf['qe'] for lf in laeufe.values()])),
                'te_median': float(np.median([lf['te'] for lf in laeufe.values()])),
                'gruppen_median': float(np.median([lf['n_gruppen'] for lf in laeufe.values()])),
                'inseln_median': float(np.median([lf['n_inseln'] for lf in laeufe.values()])),
                'sekunden_median': float(np.median([lf['meta']['sekunden'] for lf in laeufe.values()])),
                'refesom_commit': sorted({meta_wert(lf['meta'], 'refesom_commit') for lf in laeufe.values()}),
                'kandidaten': zeilen, 'neue_komponenten': neu}
    erg['vollstaendig'] = vollstaendig
    # Teilurteil aus R2 (V2, V3); V4 folgt mit R3
    r2 = erg['schritte'].get('R2', {})
    if vollstaendig and r2:
        alle = [z for satz in SAETZE for z in r2[satz]['kandidaten']]
        bekannt_ok = all(z['wiedergefunden'] >= 8 for z in alle if z['bekannt'])
        stabil = [z for z in alle if z['a4_stabil_8b1']]
        anteil = sum(z['wiedergefunden'] >= 8 for z in stabil) / len(stabil)
        erg['teilurteil_r2'] = {'v2_bekannte_reproduziert': bekannt_ok, 'stabile_a4_kandidaten': len(stabil),
                                'davon_reproduziert_anteil': round(anteil, 3),
                                'mindestens_zwei_drittel': anteil >= 2 / 3,
                                'hinweis': 'Gesamturteil erst mit V4 (R3)'}
    ZIEL.write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding='utf-8')
    for schritt, saetze in erg['schritte'].items():
        for satz, s in saetze.items():
            print(f'\n{schritt} {satz}: {s["laeufe"]} Läufe, QE {s["qe_median"]:.3f}, TE {s["te_median"]:.3f}, '
                  f'Gruppen {s["gruppen_median"]:.0f}, Inseln {s["inseln_median"]:.0f}')
            for z in s['kandidaten']:
                print(f'  K{z["id"]:<3} {z["bekannt"] or "":<10} A4 {z["a4_wiedergefunden_von_10"]:>2}/10 → '
                      f'{z["wiedergefunden"]:>2}/{z["von"]} {z["urteil"]:<18} Reinheit {z["reinheit_median"]:.2f}')
            print(f'  neue Komponenten (≥ 5 Läufe): {len(s["neue_komponenten"])}')
    print('\nvollständig:', vollstaendig, '| Teilurteil R2:', erg.get('teilurteil_r2'))


if __name__ == '__main__':
    main()
