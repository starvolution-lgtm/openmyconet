"""C1 / F2: blinde Vorhersage der Aufteilung nach der Zugabe (FREMDDATEN_BUFFI.md, Abschnitt 6a).

    venv/Scripts/python.exe -m werkzeuge.c1_f2

Läuft erst, wenn F1 abgeschlossen ist (ergebnisse/c1/f1.json). Liest „vorher“ und „nachher“ aller
vier Dateien, schreibt ergebnisse/c1/f2_vorhersage.json. Die Datei wird committet und gepusht,
BEVOR die wahre Zuordnung beschafft wird; danach wird an ihr nichts mehr geändert.
MESSWERTE VON BUFFI ET AL. (doi 10.17632/srkxbkh6sp.1, CC BY 4.0), nicht von OpenMycoNet.
"""
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations

import numpy as np

from mm import buffi as B
from mm.karte import BatchSOM
from werkzeuge.c1_f1 import HINWEIS, LAEUFE, MERKMALE, SEEDS, ZIEL

DATEIEN = B.PRUEFDATEIEN + (B.VORLAUF_DATEI,)
# Aufteilung = die 3 Pilzkanäle, die mit Leerkanal 7 in einer Hälfte liegen (20 Möglichkeiten)
AUFTEILUNGEN = [tuple(c) for c in combinations(B.PILZ, 3)]


def haelften(auft):
    a = sorted(auft) + [B.LEER[0]]
    b = sorted(set(B.PILZ) - set(auft)) + [B.LEER[1]]
    return a, b


def schluessel(auft, seite):
    a, b = haelften(auft)
    stoff, loesung = (a, b) if seite == 0 else (b, a)
    return {'stoff': stoff, 'loesungsmittel': loesung}


def vorhersage_aus_delta(delta):
    """delta: {kanal: Vektor}. Beste Aufteilung nach Kosinus-Wert, Seite nach mittlerer |Δ| der Pilzkanäle."""
    ks = list(delta)
    d = np.array([delta[k] for k in ks], dtype=float)
    nrm = np.linalg.norm(d, axis=1)
    s = (d @ d.T) / np.maximum(np.outer(nrm, nrm), 1e-12)
    pos = {k: i for i, k in enumerate(ks)}
    werte = {}
    for auft in AUFTEILUNGEN:
        a, b = haelften(auft)
        innen = [s[pos[i], pos[j]] for h in (a, b) for i, j in combinations(h, 2)]
        zwischen = [s[pos[i], pos[j]] for i in a for j in b]
        werte[auft] = float(np.mean(innen) - np.mean(zwischen))
    beste = max(werte, key=werte.get)
    a, b = haelften(beste)
    laenge = lambda h: float(np.mean([nrm[pos[k]] for k in h if k in B.PILZ]))
    seite = 0 if laenge(a) >= laenge(b) else 1
    return beste, seite, werte[beste], sorted(werte.values(), reverse=True)[1]


def vorbereiten(name):
    cache = MERKMALE / f'{name}_f2.npz'
    if cache.exists():
        z = np.load(cache)
        return {k: z[k] for k in z.files} | {'info': json.loads(str(z['info']))}
    s = B.sha256(B.DATEN / f'{name}.hdf5')
    if s != B.SHA256[name]:
        sys.exit(f'{name}: Prüfsumme falsch')
    d = B.lesen(name)
    a, b, kand = B.zugabe(d)
    if a is None:
        sys.exit(f'{name}: keine eindeutige Zugabelücke ({kand})')
    zr = B.zeitraeume(d, a, b)
    teile = {t: B.fenster_merkmale(d, zr[t]) for t in ('vorher', 'nachher')}
    m = np.vstack([teile['vorher'][0], teile['nachher'][0]])
    kanal = np.concatenate([teile['vorher'][2], teile['nachher'][2]])
    nach = np.concatenate([np.zeros(len(teile['vorher'][0]), bool), np.ones(len(teile['nachher'][0]), bool)])
    x, namen = B.normieren(m, B.NAMEN)
    info = {'datei': name, 'sha256': s, 'zugabe': [a, b], 'zugabe_h': a / d['rate'] / 3600,
            'vorher': list(zr['vorher']), 'nachher': list(zr['nachher']),
            'nachher_h': (zr['nachher'][1] - zr['nachher'][0]) / d['rate'] / 3600,
            'fenster_vorher': int((~nach).sum()), 'fenster_nachher': int(nach.sum()),
            'verworfen_nan': {t: teile[t][4] for t in teile}, 'merkmale_behalten': namen}
    np.savez_compressed(cache, x=x, m=m, kanal=kanal, nach=nach, info=json.dumps(info))
    return {'x': x, 'm': m, 'kanal': kanal, 'nach': nach, 'info': info}


def esom_lauf(arg):
    name, seed = arg
    z = np.load(MERKMALE / f'{name}_f2.npz')
    x, kanal, nach = z['x'], z['kanal'], z['nach']
    t0 = time.time()
    k = BatchSOM(40, 60, toroidal=True, seed=seed).trainieren(x, epochen=40, sigma_ende=0.75)
    bmu = k.bmu(x)
    gruppe, art = k.gruppen(bmu)
    komp = gruppe[bmu]
    np.savez_compressed(LAEUFE / f'F2_{name}_s{seed}.npz', w=k.w, bmu=bmu, komp=komp)
    n = len(art)
    delta = {}
    for c in B.PILZ + B.LEER:
        v = np.bincount(komp[(kanal == c) & ~nach], minlength=n) / max(1, np.sum((kanal == c) & ~nach))
        w = np.bincount(komp[(kanal == c) & nach], minlength=n) / max(1, np.sum((kanal == c) & nach))
        delta[c] = (w - v).tolist()
    auft, seite, wert, zweiter = vorhersage_aus_delta(delta)
    return {'datei': name, 'seed': seed, 'aufteilung': auft, 'seite': seite, 'wert': wert,
            'abstand_zum_zweiten': wert - zweiter, 'n_komponenten': n, 'sekunden': time.time() - t0}


def einfach(v):
    x, m, kanal, nach = v['x'], v['m'], v['kanal'], v['nach']
    delta = {c: (np.median(x[(kanal == c) & nach], axis=0) - np.median(x[(kanal == c) & ~nach], axis=0))
             for c in B.PILZ + B.LEER}
    auft, seite, wert, zweiter = vorhersage_aus_delta(delta)
    merkmal = {'vorhersage': schluessel(auft, seite), 'wert': wert, 'abstand_zum_zweiten': wert - zweiter}
    lst = {c: float(np.median(np.log(m[(kanal == c) & nach, 0])) - np.median(np.log(m[(kanal == c) & ~nach, 0])))
           for c in B.PILZ + B.LEER}
    pilz = sorted(B.PILZ, key=lambda c: -abs(lst[c]))[:3]
    leer = max(B.LEER, key=lambda c: abs(lst[c]))
    stoff = sorted(pilz) + [leer]
    loesung = sorted(set(B.PILZ) - set(pilz)) + [c for c in B.LEER if c != leer]
    laut = {'vorhersage': {'stoff': stoff, 'loesungsmittel': loesung}, 'delta_log_streuung': lst}
    return merkmal, laut


def main():
    if not (ZIEL / 'f1.json').exists():
        sys.exit('F1 ist noch nicht abgeschlossen (ergebnisse/c1/f1.json fehlt). Reihenfolge Abschnitt 5.')
    LAEUFE.mkdir(parents=True, exist_ok=True)
    vs = {}
    for name in DATEIEN:
        vs[name] = vorbereiten(name)
        print(name, 'nachher', round(vs[name]['info']['nachher_h'], 1), 'h, Fenster',
              vs[name]['info']['fenster_vorher'], '+', vs[name]['info']['fenster_nachher'], flush=True)
    auftraege = [(n, s) for n in DATEIEN for s in SEEDS]
    with ProcessPoolExecutor(int(os.environ.get('MM_ARBEITER', '4'))) as ex:
        laeufe = []
        for lf in ex.map(esom_lauf, auftraege):
            laeufe.append(lf)
            print(f"{lf['datei']} s{lf['seed']}: {lf['sekunden']/60:.1f} min", flush=True)
    erg = {'hinweis': HINWEIS, 'regeln': 'FREMDDATEN_BUFFI.md, Abschnitt 6a',
           'stand': 'Vorhersage vor Kenntnis der wahren Zuordnung; danach unverändert',
           'kanalzuordnung_annahme': {'pilz': list(B.PILZ), 'leer': list(B.LEER)}, 'dateien': {}}
    for name in DATEIEN:
        ll = [lf for lf in laeufe if lf['datei'] == name]
        stimmen = Counter((tuple(lf['aufteilung']), lf['seite']) for lf in ll)
        (auft, seite), n = stimmen.most_common(1)[0]
        gleichstand = sum(1 for c in stimmen.values() if c == n) > 1
        merkmal, laut = einfach(vs[name])
        erg['dateien'][name] = {
            'zaehlt': name in B.PRUEFDATEIEN, 'info': vs[name]['info'],
            'esom': {'vorhersage': schluessel(auft, seite), 'seeds_mit_dieser_vorhersage': n,
                     'unsicher': n < 5, 'gleichstand_bei_mehrheit': gleichstand,
                     'je_seed': [{'seed': lf['seed'], **schluessel(lf['aufteilung'], lf['seite']),
                                  'wert': lf['wert'], 'abstand_zum_zweiten': lf['abstand_zum_zweiten'],
                                  'n_komponenten': lf['n_komponenten']} for lf in sorted(ll, key=lambda q: q['seed'])],
                     'minuten_median': float(np.median([lf['sekunden'] for lf in ll]) / 60)},
            'merkmalsaenderung': merkmal, 'lautstaerke': laut}
    (ZIEL / 'f2_vorhersage.json').write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding='utf-8')
    for name in DATEIEN:
        e = erg['dateien'][name]
        print(name, '(zählt)' if e['zaehlt'] else '(Vorlauf)')
        for vf in ('esom', 'merkmalsaenderung', 'lautstaerke'):
            extra = f" [{e[vf]['seeds_mit_dieser_vorhersage']}/10]" if vf == 'esom' else ''
            print(f"  {vf:<18} Stoff {e[vf]['vorhersage']['stoff']}  Lösungsmittel {e[vf]['vorhersage']['loesungsmittel']}{extra}")


if __name__ == '__main__':
    main()
