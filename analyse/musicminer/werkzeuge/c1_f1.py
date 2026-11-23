"""C1 / F1: Findet ein Verfahren die zwei Kanäle ohne Pilz? (FREMDDATEN_BUFFI.md, Abschnitte 5 + 6)

    venv/Scripts/python.exe -m werkzeuge.c1_f1 vorlauf     # C1-0: Cycloheximid, Seed 0, zählt nicht
    venv/Scripts/python.exe -m werkzeuge.c1_f1 pruefung    # drei Prüfdateien, Seeds 0-9, alle Verfahren

Nur der Zeitraum „vorher“ wird gelesen. Merkmale und Läufe bleiben lokal (ergebnisse/c1/merkmale,
ergebnisse/c1/laeufe), ins Git gehen nur f1_vorlauf.json bzw. f1.json.
MESSWERTE VON BUFFI ET AL. (doi 10.17632/srkxbkh6sp.1, CC BY 4.0), nicht von OpenMycoNet.
"""
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations

import numpy as np
from sklearn.cluster import HDBSCAN, KMeans

from mm import buffi as B
from mm.karte import BatchSOM

ZIEL = B.WURZEL / 'ergebnisse' / 'c1'
MERKMALE = ZIEL / 'merkmale'
LAEUFE = ZIEL / 'laeufe'
SEEDS = range(10)
HINWEIS = 'MESSWERTE VON BUFFI ET AL. (Mendeley Data, doi 10.17632/srkxbkh6sp.1, CC BY 4.0), nicht von OpenMycoNet'


def vorbereiten(name):
    """Prüfsumme, Zugabelücke, Fenster + Merkmale „vorher“ (zwischengespeichert)."""
    MERKMALE.mkdir(parents=True, exist_ok=True)
    cache = MERKMALE / f'{name}_vorher.npz'
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        return {k: z[k] for k in z.files} | {'info': json.loads(str(z['info']))}
    s = B.sha256(B.DATEN / f'{name}.hdf5')
    if s != B.SHA256[name]:
        sys.exit(f'{name}: Prüfsumme falsch ({s}), Datei wird nicht genutzt')
    d = B.lesen(name)
    a, b, kand = B.zugabe(d)
    info = {'datei': name, 'sha256': s, 'rate': d['rate'], 'start_unix': d['start'], 'kanaele': d['kanaele'],
            'werte': int(d['x'].shape[1]), 'nan_abschnitte': B.nan_abschnitte(d['x']),
            'zugabe_kandidaten': kand}
    if a is None:
        sys.exit(f'{name}: keine eindeutige Zugabelücke ({kand}), Datei wird nicht ausgewertet')
    zr = B.zeitraeume(d, a, b)
    info |= {'zugabe': [a, b], 'zugabe_h': a / d['rate'] / 3600, 'vorher': list(zr['vorher'])}
    m, ml, kanal, st, verw = B.fenster_merkmale(d, zr['vorher'])
    info['fenster'] = len(m)
    info['fenster_verworfen_nan'] = verw
    np.savez_compressed(cache, m=m, ml=ml, kanal=kanal, start=st, info=json.dumps(info))
    return {'m': m, 'ml': ml, 'kanal': kanal, 'start': st, 'info': info}


def paare(kanaele):
    return list(combinations(sorted(kanaele), 2))


def j_paare(lab, kanal, kanaele):
    """J(P) für alle 28 Paare: größter Jaccard zwischen Fenstern von P und einem Cluster (lab >= 0)."""
    ks = sorted(kanaele)
    ids = np.unique(lab[lab >= 0])
    c = np.array([[np.sum((lab == i) & (kanal == k)) for k in ks] for i in ids], dtype=float)
    groesse = np.array([np.sum(lab == i) for i in ids], dtype=float)
    n_k = np.array([np.sum(kanal == k) for k in ks], dtype=float)
    out = {}
    for a, b in paare(ks):
        ia, ib = ks.index(a), ks.index(b)
        inter = c[:, ia] + c[:, ib]
        out[f'{a}-{b}'] = float(np.max(inter / (groesse + n_k[ia] + n_k[ib] - inter))) if len(ids) else 0.0
    return out


def bewerten(j_median):
    wahr = f'{B.LEER[0]}-{B.LEER[1]}'
    werte = sorted(j_median.values(), reverse=True)
    jw = j_median[wahr]
    rang = 1 + sum(v > jw for v in werte)
    einzig_bestes = rang == 1 and sum(v == jw for v in werte) == 1
    bestes = max(j_median, key=j_median.get)
    return {'j_wahres_paar': jw, 'rang_unter_28': rang, 'bestes_paar': bestes, 'j_bestes': j_median[bestes],
            'gefunden': bool(einzig_bestes and jw >= 0.5)}


def esom_lauf(arg):
    name, satz, seed = arg
    z = np.load(MERKMALE / f'{name}_vorher.npz')
    x, kanal = (z['x'], z['kanal']) if satz == 'mb1' else (z['ml_x'], z['ml_kanal'])
    t0 = time.time()
    k = BatchSOM(40, 60, toroidal=True, seed=seed).trainieren(x, epochen=40, sigma_ende=0.75)
    bmu = k.bmu(x)
    gruppe, art = k.gruppen(bmu)
    komp = gruppe[bmu]
    LAEUFE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(LAEUFE / f'F1_{name}_{satz}_s{seed}.npz', w=k.w, bmu=bmu, komp=komp)
    return {'datei': name, 'satz': satz, 'seed': seed, 'j': j_paare(komp, kanal, B.PILZ + B.LEER),
            'qe': float(k.quantisierungsfehler(x, bmu).mean()), 'te': float(k.topologiefehler(x)),
            'n_gruppen': sum(a == 'gruppe' for a in art.values()),
            'n_inseln': sum(a == 'insel' for a in art.values()),
            'n_komponenten': len(art), 'sekunden': time.time() - t0}


def matrizen(name):
    """Normierte Matrizen mb1 und mb1-L (ohne Fenster ohne Vorlauf) in den Zwischenspeicher."""
    v = vorbereiten(name)
    x, namen = B.normieren(v['m'], B.NAMEN)
    ok = np.isfinite(v['ml']).all(axis=1)
    xl, namen_l = B.normieren(np.column_stack([v['m'][ok], v['ml'][ok]]), B.NAMEN + B.NAMEN_L)
    roh = np.load(MERKMALE / f'{name}_vorher.npz')
    np.savez_compressed(MERKMALE / f'{name}_vorher.npz', **{k: roh[k] for k in roh.files},
                        x=x, ml_x=xl, ml_kanal=v['kanal'][ok])
    v['info'] |= {'merkmale_behalten': namen, 'merkmale_l_behalten': namen_l,
                  'fenster_l': int(ok.sum()), 'fenster_je_kanal': {int(k): int(np.sum(v['kanal'] == k))
                                                                   for k in v['info']['kanaele']}}
    return x, v


def einfache_verfahren(name, x, v, k_esom):
    kanal = v['kanal']
    alle = B.PILZ + B.LEER
    out = {}
    for k in sorted({2, k_esom}):
        js = [j_paare(KMeans(k, n_init=1, random_state=s).fit_predict(x), kanal, alle) for s in SEEDS]
        out[f'kmeans_k{k}'] = bewerten({p: float(np.median([j[p] for j in js])) for p in js[0]})
    lab = HDBSCAN(min_cluster_size=50).fit_predict(x)
    out['hdbscan'] = bewerten(j_paare(lab, kanal, alle)) | {'cluster': int(lab.max() + 1),
                                                            'rauschen_anteil': float(np.mean(lab < 0))}
    streu = {int(k): float(np.median(v['m'][kanal == k, 0])) for k in alle}
    leiseste = sorted(streu, key=streu.get)[:2]
    out['kanalkriterium'] = {'median_streuung_uV': streu, 'zwei_leiseste': sorted(leiseste),
                             'gefunden': sorted(leiseste) == sorted(B.LEER)}
    return out


def zusammenfassen(laeufe, satz):
    js = [lf['j'] for lf in laeufe if lf['satz'] == satz]
    med = {p: float(np.median([j[p] for j in js])) for p in js[0]}
    ls = [lf for lf in laeufe if lf['satz'] == satz]
    return bewerten(med) | {
        'seeds': len(js), 'j_median_je_paar': med,
        'qe_median': float(np.median([lf['qe'] for lf in ls])), 'te_median': float(np.median([lf['te'] for lf in ls])),
        'gruppen_median': float(np.median([lf['n_gruppen'] for lf in ls])),
        'inseln_median': float(np.median([lf['n_inseln'] for lf in ls])),
        'minuten_median': float(np.median([lf['sekunden'] for lf in ls]) / 60)}


def main():
    modus = sys.argv[1]
    ZIEL.mkdir(parents=True, exist_ok=True)
    if modus == 'vorlauf':
        name = B.VORLAUF_DATEI
        _x, v = matrizen(name)
        lf = esom_lauf((name, 'mb1', 0))
        erg = {'hinweis': HINWEIS, 'regeln': 'FREMDDATEN_BUFFI.md, Abschnitt 5 (C1-0)',
               'kennzeichnung': 'Vorlauf, nicht blind, zählt nicht', 'info': v['info'],
               'esom_seed0': bewerten(lf['j']) | {k: lf[k] for k in ('qe', 'te', 'n_gruppen', 'n_inseln', 'sekunden')},
               'j_seed0': lf['j']}
        (ZIEL / 'f1_vorlauf.json').write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding='utf-8')
        print(json.dumps({k: erg[k] for k in ('info', 'esom_seed0')}, ensure_ascii=False, indent=1))
        return
    assert modus == 'pruefung'
    infos, x_je = {}, {}
    for name in B.PRUEFDATEIEN:
        x_je[name], v = matrizen(name)
        infos[name] = v
        print(name, 'Zugabe bei', round(v['info']['zugabe_h'], 2), 'h, Fenster', v['info']['fenster'], flush=True)
    auftraege = [(n, s_, seed) for n in B.PRUEFDATEIEN for s_ in ('mb1', 'mb1-L') for seed in SEEDS]
    with ProcessPoolExecutor(int(os.environ.get('MM_ARBEITER', '4'))) as ex:
        laeufe = []
        for lf in ex.map(esom_lauf, auftraege):
            laeufe.append(lf)
            print(f"{lf['datei']} {lf['satz']} s{lf['seed']}: {lf['sekunden']/60:.1f} min", flush=True)
    erg = {'hinweis': HINWEIS, 'regeln': 'FREMDDATEN_BUFFI.md, Abschnitte 5 und 6', 'dateien': {}}
    for name in B.PRUEFDATEIEN:
        ll = [lf for lf in laeufe if lf['datei'] == name]
        k_esom = next(lf['n_komponenten'] for lf in ll if lf['satz'] == 'mb1' and lf['seed'] == 0)
        erg['dateien'][name] = {'info': infos[name]['info'], 'esom': zusammenfassen(ll, 'mb1'),
                                'esom_mb1_L_nur_berichtet': zusammenfassen(ll, 'mb1-L'),
                                **einfache_verfahren(name, x_je[name], infos[name], k_esom)}
    verfahren = ['esom', 'kmeans_k2'] + [k for k in erg['dateien'][B.PRUEFDATEIEN[0]] if k.startswith('kmeans_k')
                                         and k != 'kmeans_k2'] + ['hdbscan', 'kanalkriterium']
    gesamt = {}
    for vf in verfahren:
        treffer = sum(erg['dateien'][n].get(vf, {}).get('gefunden', False) for n in B.PRUEFDATEIEN)
        gesamt[vf] = {'gefunden_in_dateien': treffer, 'gefunden_insgesamt': treffer >= 2}
    andere = [vf for vf in gesamt if vf != 'esom' and gesamt[vf]['gefunden_insgesamt']]
    if gesamt['esom']['gefunden_insgesamt']:
        urteil = 'bestätigt ohne Mehrwert' if andere else 'ESOM-spezifischer Mehrwert'
    else:
        urteil = 'ESOM findet sie nicht'
    erg['gesamt'] = gesamt
    erg['urteil_f1'] = urteil
    erg['kein_verfahren_findet'] = not any(g['gefunden_insgesamt'] for g in gesamt.values())
    (ZIEL / 'f1.json').write_text(json.dumps(erg, ensure_ascii=False, indent=1), encoding='utf-8')
    for name in B.PRUEFDATEIEN:
        e = erg['dateien'][name]
        print(name, {vf: (round(e[vf].get('j_wahres_paar', -1), 3), e[vf].get('rang_unter_28'), e[vf]['gefunden'])
                     for vf in verfahren if vf in e})
    print('Gesamt:', gesamt, '| Urteil F1:', urteil)


if __name__ == '__main__':
    main()
