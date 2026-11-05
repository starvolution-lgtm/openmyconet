"""A4: unabhaengiger Methodenvergleich + groessenabhaengiger Nullmodellvergleich + Robustheit
des Endradius, nach Kriterien v2 + Ergaenzung E1 (KRITERIEN.md, Abschnitt 9).

Aufruf (im Ordner analyse/musicminer, nach dem A3-Lauf, der die Vorbereitung erzeugt):
    venv/Scripts/python.exe -m werkzeuge.a4_laufen daten/schnappschuss_staging_2026-11-05.tar
MM_PROBE=1 -> Kurzlauf (wenige Seeds/Nulllaeufe) nach ergebnisse/a4_probe.

Alles SIMULATION. Etiketten gehen nie ins Training.
"""
import os

for _v in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '2')

import hashlib
import itertools
import json
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from sklearn.cluster import HDBSCAN, KMeans
from sklearn.covariance import MinCovDet
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import LocalOutlierFactor, NearestNeighbors
from sklearn.tree import DecisionTreeClassifier, export_text

from mm import karte as K
from mm import kriterien as KR
from mm import merkmale as M
from werkzeuge.a3_laufen import _nulldaten, merkmalssatz, vorbereiten

warnings.filterwarnings('ignore', category=FutureWarning)

ZIEL = Path('ergebnisse/a4')
VORBEREITUNG = Path('ergebnisse/a3/vorbereitung.npz')
SAETZE = ('P', 'PL')
TOPOS = {'planar': False, 'torus': True}
RADIEN = (0.75, 1.5, 3.0)
BASIS_RADIUS = 0.75
SEEDS = list(range(10))
N1_SEEDS, N2_SEEDS = list(range(100)), list(range(25))
EPOCHEN = 40
GROESSE = (40, 60)
WORKER = 4
if os.environ.get('MM_PROBE'):
    ZIEL, SEEDS, N1_SEEDS, N2_SEEDS, EPOCHEN = Path('ergebnisse/a4_probe'), [0, 1, 2], [0, 1, 2], [0], 3
STIM_SZENARIEN = ('elektrisch', 'optisch', 'elektrooptisch_synchron', 'elektrooptisch_versetzt')

_V = None


def _v():
    global _V
    if _V is None:
        _V = dict(np.load(VORBEREITUNG, allow_pickle=False))
    return _V


def _som(x, toroidal, radius, seed):
    som = K.BatchSOM(*GROESSE, toroidal=toroidal, seed=seed).trainieren(x, epochen=EPOCHEN, sigma_ende=radius)
    bmu = som.bmu(x)
    gruppe, art = som.gruppen(bmu)
    return som, bmu, gruppe, art


def _komponenten(som, x, bmu, gruppe):
    gw = gruppe[bmu]
    ab = som.abgrenzung(x, bmu, gruppe)
    return [(int((gw == g).sum()), float(ab.get(int(g), float('nan')))) for g in np.unique(gw)]


# ------------------------------------------------------------------ Worker-Jobs
def job_karte(j):
    v = _v()
    x, _, _ = merkmalssatz(v, j['satz'])
    if j['daten'] != 'echt':
        x = _nulldaten(x, j['daten'], j['seed'])
    som, bmu, gruppe, art = _som(x, TOPOS[j['topo']], j['radius'], j['seed'])
    erg = {**j, 'qe': float(som.quantisierungsfehler(x, bmu).mean()), 'te': som.topologiefehler(x),
           'n_gruppen': sum(a == 'gruppe' for a in art.values()), 'n_inseln': sum(a == 'insel' for a in art.values()),
           'komponenten': _komponenten(som, x, bmu, gruppe)}
    if j['daten'] == 'echt':
        erg['_gruppe_fenster'] = gruppe[bmu].astype(np.int32)
        erg['abgrenzung'] = som.abgrenzung(x, bmu, gruppe)
        if j['seed'] == 0:
            erg['_u'] = som.u_matrix()
    return erg


def job_teil(j):
    """GroupKFold-Teil: ESOM + Vergleichsverfahren auf Training, Bewertung der Testfenster."""
    v = _v()
    x_tr, _, par = merkmalssatz(v, j['satz'], np.array(j['train']))
    x_te, z_te, _ = merkmalssatz(v, j['satz'], np.array(j['test']), par)
    seed = j['seed']
    som, _bmu, gruppe, _ = _som(x_tr, True, BASIS_RADIUS, seed)
    bmu_te = som.bmu(x_te)
    werte = {'esom_qe': som.quantisierungsfehler(x_te, bmu_te), 'esom_u': som.u_matrix().ravel()[bmu_te]}
    werte['isolation_forest'] = -IsolationForest(random_state=seed).fit(x_tr).score_samples(x_te)
    werte['mahalanobis_mcd'] = MinCovDet(random_state=seed).fit(x_tr).mahalanobis(x_te)
    werte['lof'] = -LocalOutlierFactor(20, novelty=True).fit(x_tr).score_samples(x_te)
    km = KMeans(8, random_state=seed, n_init=1).fit(x_tr)
    werte['kmeans_abstand'] = km.transform(x_te).min(axis=1)
    pca = PCA(0.95, random_state=seed).fit(x_tr)
    werte['pca_rekonstruktion'] = np.linalg.norm(x_te - pca.inverse_transform(pca.transform(x_te)), axis=1)
    return {k: j[k] for k in ('satz', 'seed', 'teil')} | {
        '_test_zeilen': z_te, '_test_gruppe': gruppe[bmu_te].astype(np.int32),
        '_werte': {k: np.asarray(w, np.float32) for k, w in werte.items()}}


def job_entdeckung(j):
    """Vergleichsverfahren auf der vollen Matrix (wie die explorative ESOM), ohne Strukturvorgabe."""
    v = _v()
    x, _, _ = merkmalssatz(v, j['satz'])
    art = j['art']
    if art == 'kmeans':
        return {**j, '_labels': KMeans(j['k'], random_state=j['seed'], n_init=1).fit(x).labels_.astype(np.int32)}
    if art == 'hdbscan':
        return {**j, '_labels': HDBSCAN(min_cluster_size=10, copy=True).fit(x).labels_.astype(np.int32)}
    if art == 'isolation_forest':
        return {**j, '_score': -IsolationForest(random_state=j['seed']).fit(x).score_samples(x)}
    if art == 'mahalanobis_mcd':
        return {**j, '_score': MinCovDet(random_state=0).fit(x).mahalanobis(x)}
    if art == 'lof':
        return {**j, '_score': -LocalOutlierFactor(20).fit(x).negative_outlier_factor_}
    if art == 'pca2':
        return {**j, '_emb': PCA(2, random_state=0).fit_transform(x)}
    raise ValueError(art)


# ------------------------------------------------------------------ Auswertung
def _jaccard(a, b):
    return len(a & b) / len(a | b) if a or b else 0.0


def _beste(menge, labels, nur=None):
    """Beste Jaccard-Uebereinstimmung einer Fenstermenge (Positionen) mit einem Label-Cluster."""
    best = 0.0
    idx = np.fromiter(menge, int)
    for lab in np.unique(labels[idx]):
        if lab < 0:                         # HDBSCAN-Rauschen ist kein Cluster
            continue
        andere = np.where(labels == lab)[0] if nur is None else nur[labels == lab]
        best = max(best, _jaccard(menge, set(andere.tolist())))
    return best


def kandidaten(lauf0, laeufe):
    """9.1: Komponenten der Seed-0-Karte ausser der groessten Gruppe, mit Wiederfinden in den Seeds."""
    g0 = lauf0['_gruppe_fenster']
    ids, anz = np.unique(g0, return_counts=True)
    groesste = ids[anz.argmax()]
    out = []
    for gi in ids:
        if gi == groesste:
            continue
        menge = set(np.where(g0 == gi)[0].tolist())
        gefunden = [(lauf0['seed'], len(menge), lauf0['abgrenzung'].get(int(gi), float('nan')))]
        for lauf in laeufe:
            if lauf['seed'] == lauf0['seed']:
                continue
            g = lauf['_gruppe_fenster']
            best, best_g = 0.0, None
            for gj in np.unique(g[np.fromiter(menge, int)]):
                jac = _jaccard(menge, set(np.where(g == gj)[0].tolist()))
                if jac > best:
                    best, best_g = jac, gj
            if best >= 0.5:
                gefunden.append((lauf['seed'], int((g == best_g).sum()), lauf['abgrenzung'].get(int(best_g), float('nan'))))
        out.append({'id': int(gi), 'art': lauf0['art_je_gruppe'].get(int(gi), '?'), 'menge': menge,
                    'wiedergefunden': len(gefunden), 'groesse': float(np.median([g for _, g, _ in gefunden])),
                    'A': float(np.nanmedian([a for _, _, a in gefunden]))})
    return out


def wiedergefunden_in(menge, laeufe):
    n, ab = 0, []
    for lauf in laeufe:
        g = lauf['_gruppe_fenster']
        best, best_g = 0.0, None
        for gj in np.unique(g[np.fromiter(menge, int)]):
            jac = _jaccard(menge, set(np.where(g == gj)[0].tolist()))
            if jac > best:
                best, best_g = jac, gj
        if best >= 0.5:
            n += 1
            ab.append(lauf['abgrenzung'].get(int(best_g), float('nan')))
    return n, (float(np.nanmedian(ab)) if ab else None)


def _auc(y, s):
    y = np.asarray(y, bool)
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else None


def auswerten(v, ergebnisse, teile, entdeckung, zeilen_je_satz, x_je_satz):
    out = {'kriterien': KR.VERSION, 'saetze': {}}
    for satz in SAETZE:
        zeilen = zeilen_je_satz[satz]
        pos_von = {int(z): i for i, z in enumerate(zeilen)}

        def sel(topo, radius, daten, satz=satz):
            return sorted([e for e in ergebnisse if (e['satz'], e['topo'], e['radius'], e['daten'])
                           == (satz, topo, radius, daten)], key=lambda e: e['seed'])
        basis = sel('torus', BASIS_RADIUS, 'echt')
        null = [e['komponenten'] for e in sel('torus', BASIS_RADIUS, 'N1') + sel('torus', BASIS_RADIUS, 'N2')]
        null_n1 = [e['komponenten'] for e in sel('torus', BASIS_RADIUS, 'N1')]
        kand = [k for k in kandidaten(basis[0], basis) if k['wiedergefunden'] >= 5]
        klassen = sorted({KR.klasse(k['groesse']) for k in kand if KR.klasse(k['groesse']) is not None})
        anzahl_k = max(1, len(klassen))
        glob = KR.schwelle_global(null)
        roh = v['P'][zeilen] if satz == 'P' else np.hstack([v['P'], v['L']])[zeilen]
        namen = M.NAMEN_P if satz == 'P' else M.NAMEN_P + M.NAMEN_L
        x = x_je_satz[satz]
        _, _, par = merkmalssatz(v, satz)
        namen_beh = [n for n, b in zip(namen, par['behalten'], strict=True) if b]     # Spalten von x
        rand = v['e_randnah'][zeilen]
        planar = sel('planar', BASIS_RADIUS, 'echt')
        # Vergleichsverfahren (volle Matrix)
        ent = [e for e in entdeckung if e['satz'] == satz]
        emb = next(e['_emb'] for e in ent if e['art'] == 'pca2')
        nn = NearestNeighbors(n_neighbors=11).fit(emb).kneighbors(emb, return_distance=False)[:, 1:]
        k_gruppen, k_alle = basis[0]['n_gruppen'], basis[0]['n_gruppen'] + basis[0]['n_inseln']

        bericht_k = []
        for k in kand:
            idx = np.fromiter(k['menge'], int)
            y = np.zeros(len(zeilen), bool)
            y[idx] = True
            kl = KR.klasse(k['groesse'])
            groesse_test = KR.schwelle_klasse(null, kl, anzahl_k) if kl is not None else None
            besteht_groesse = bool(groesse_test and groesse_test['genug_nulldaten'] and k['A'] > groesse_test['schwelle'])
            besteht_global = glob['schwelle'] is None or k['A'] > glob['schwelle']
            baum = DecisionTreeClassifier(max_depth=2, class_weight='balanced', random_state=0).fit(roh, y)
            f1 = float(f1_score(y, baum.predict(roh)))
            extrem = [n for j, n in enumerate(namen_beh) if (np.abs(x[idx, j]) >= 8).mean() >= 0.9]
            n_planar, _ = wiedergefunden_in(k['menge'], planar)
            # 8b.5 Uebertragung
            jac = []
            for t in [t for t in teile if t['satz'] == satz]:
                test_pos = np.array([pos_von[int(z)] for z in t['_test_zeilen']])
                drin = np.isin(test_pos, idx)
                if drin.sum() >= 5:
                    menge_t = set(np.where(drin)[0].tolist())
                    jac.append(_beste(menge_t, t['_test_gruppe']))
            pruef = {'wiedergefunden_5': k['wiedergefunden'] >= 5, 'stabil': k['wiedergefunden'] >= 8,
                     'global': bool(besteht_global), 'groesse': besteht_groesse, 'nachpruefbar': f1 >= 0.8,
                     'kein_artefakt': bool(rand[idx].mean() < 0.5 and n_planar >= 5 and not extrem),
                     'uebertraegt': len(jac) >= 3 and float(np.median(jac)) >= 0.5}
            # 9.6 Vergleichsverfahren
            zeigt = {}
            for kk, name in ((k_gruppen, 'kmeans_k_gruppen'), (k_alle, 'kmeans_k_alle')):
                treffer = [_beste(k['menge'], e['_labels']) for e in ent if e['art'] == 'kmeans' and e['k'] == kk]
                zeigt[name] = {'jaccard_median': float(np.median(treffer)), 'seeds_ge_0_5': int(sum(t >= 0.5 for t in treffer)),
                               'zeigt': sum(t >= 0.5 for t in treffer) >= 0.8 * len(treffer)}
            hd = next(e['_labels'] for e in ent if e['art'] == 'hdbscan')
            j_hd = _beste(k['menge'], hd)
            zeigt['hdbscan'] = {'jaccard': j_hd, 'zeigt': j_hd >= 0.5}
            for art in ('isolation_forest', 'mahalanobis_mcd', 'lof'):
                anteile = []
                for e in [e for e in ent if e['art'] == art]:
                    grenze = np.quantile(e['_score'], 0.99)
                    anteile.append(float((e['_score'][idx] >= grenze).mean()))
                zeigt[art] = {'anteil_top1_median': float(np.median(anteile)),
                              'zeigt': sum(a >= 0.5 for a in anteile) >= (0.8 * len(anteile) if len(anteile) > 1 else 1)}
            rein = y[nn[idx]].mean(axis=1)
            zeigt['pca_2d'] = {'nachbar_reinheit_median': float(np.median(rein)), 'zeigt': float(np.median(rein)) >= 0.5}
            etik = {}
            for kat in ('szenario', 'standort', 'stichtag', 'phase', 'qualitaet'):
                w, a = np.unique(v[f'e_{kat}'][zeilen][idx], return_counts=True)
                etik[kat] = {str(w[i]): round(float(a[i] / len(idx)), 3) for i in np.argsort(-a)[:3]}
            bericht_k.append({
                'id': k['id'], 'art': k['art'], 'fenster_seed0': len(idx), 'groesse_median': k['groesse'],
                'klasse': KR.klassenname(kl) if kl is not None else '< 10', 'A_abgrenzung_median': k['A'],
                'wiedergefunden_von_10': k['wiedergefunden'], 'planar_wiedergefunden_von_10': n_planar,
                'randnah_anteil': float(rand[idx].mean()), 'extrem_merkmale': extrem,
                'baum_f1': f1, 'baum_regel': export_text(baum, feature_names=list(namen)),
                'uebertragung_jaccard_median': float(np.median(jac)) if jac else None, 'uebertragung_faelle': len(jac),
                'groessentest': groesse_test, 'pruefungen': pruef, 'stufe': KR.stufe(pruef),
                'vergleichsverfahren': zeigt, 'esom_spezifisch': not any(z['zeigt'] for z in zeigt.values()),
                'etiketten': etik, 'merkmale_median': {n: round(float(np.median(roh[idx, j])), 4) for j, n in enumerate(namen)}})

        # 8a Klassifikation
        klass = {}
        rolle, phase, sz, qual = (v[f'e_{k}'][zeilen] for k in ('rolle', 'phase', 'szenario', 'qualitaet'))
        stim = (rolle == 'PRIMARY') & np.isin(sz, STIM_SZENARIEN)
        aufgaben = {'K1_saettigung': (np.ones(len(zeilen), bool), qual == 'SATURATED'),
                    'K2_nach_0_10_vs_vor': (stim & np.isin(phase, ['vor', 'nach_0_10']), phase == 'nach_0_10'),
                    'K3_waehrend_vs_vor': (stim & np.isin(phase, ['vor', 'waehrend']), phase == 'waehrend')}
        wissen = {'K1_saettigung': roh[:, namen.index('adc_rand')]}
        if 'abw_vorlauf' in namen:
            wissen['K2_nach_0_10_vs_vor'] = np.abs(roh[:, namen.index('abw_vorlauf')])
        for aufgabe, (maske, ziel) in aufgaben.items():
            je_verfahren = {}
            for seed in SEEDS:
                ts = [t for t in teile if t['satz'] == satz and t['seed'] == seed]
                pos = np.concatenate([[pos_von[int(z)] for z in t['_test_zeilen']] for t in ts]).astype(int)
                for verf in ts[0]['_werte']:
                    s = np.concatenate([t['_werte'][verf] for t in ts])
                    m = maske[pos]
                    je_verfahren.setdefault(verf, []).append(_auc(ziel[pos][m], s[m]))
            res = {verf: {'auc_median': float(np.median([a for a in w if a is not None])) if any(a is not None for a in w) else None,
                          'auc_je_seed': w} for verf, w in je_verfahren.items()}
            if aufgabe in wissen:
                m = maske
                res['wissensbasiert'] = {'auc_median': _auc(ziel[m], wissen[aufgabe][m])}
            unbeaufs = [k for k in res if k not in ('esom_qe', 'esom_u', 'wissensbasiert') and res[k]['auc_median'] is not None]
            if res['esom_qe']['auc_median'] is not None and unbeaufs:
                bester = max(unbeaufs, key=lambda k: res[k]['auc_median'])
                besser = sum(a is not None and b is not None and a > b for a, b in
                             zip(res['esom_qe']['auc_je_seed'], res[bester]['auc_je_seed'], strict=True))
                res['entscheidung_8a'] = {
                    'bestes_unbeaufsichtigtes': bester,
                    'differenz_median': res['esom_qe']['auc_median'] - res[bester]['auc_median'],
                    'esom_besser_in_seeds': int(besser),
                    'mehrwert': bool(res['esom_qe']['auc_median'] - res[bester]['auc_median'] >= 0.05 and besser >= 8),
                    'gegen_wissensbasiert': (res['esom_qe']['auc_median'] - res['wissensbasiert']['auc_median'])
                    if 'wissensbasiert' in res else None}
            res['positive'] = int(ziel[maske].sum())
            klass[aufgabe] = res

        # 9.8 Robustheit
        robust = {}
        bezug = {k['id']: k['menge'] for k in kand}
        for topo, radius in itertools.product(TOPOS, RADIEN):
            l_ = sel(topo, radius, 'echt')
            robust[f'{topo}|{radius}'] = {
                'qe_median': float(np.median([e['qe'] for e in l_])), 'te_median': float(np.median([e['te'] for e in l_])),
                'gruppen': [e['n_gruppen'] for e in l_], 'inseln': [e['n_inseln'] for e in l_],
                'kandidaten': {str(i): dict(zip(('wiedergefunden_von_10', 'A_median'), wiedergefunden_in(m, l_), strict=True))
                               for i, m in bezug.items()}}
        out['saetze'][satz] = {
            'zeilen': len(zeilen), 'nulllaeufe': {'N1': len(null_n1), 'N2': len(null) - len(null_n1)},
            'nullkomponenten_gesamt': sum(len(n) for n in null), 'globale_schwelle': glob,
            'klassen_geprueft': [KR.klassenname(c) for c in klassen], 'kandidaten': bericht_k,
            'nicht_berichtet_unter_5_seeds': len(kandidaten(basis[0], basis)) - len(kand),
            'klassifikation_8a': klass, 'robustheit': robust}
    return out


def abbildungen(v, ergebnisse, entdeckung, auswertung, zeilen_je_satz):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    abb = ZIEL / 'abbildungen'
    abb.mkdir(parents=True, exist_ok=True)
    hinweis = 'SIMULATION (Sandbox sbx-gen-1.0) – keine Messdaten'
    for satz in SAETZE:
        a = auswertung['saetze'][satz]
        emb = next(e['_emb'] for e in entdeckung if e['satz'] == satz and e['art'] == 'pca2')
        basis0 = next(e for e in ergebnisse if (e['satz'], e['topo'], e['radius'], e['daten'], e['seed'])
                      == (satz, 'torus', BASIS_RADIUS, 'echt', 0))
        fig, ax = plt.subplots(1, 2, figsize=(14, 6))
        ax[0].scatter(emb[:, 0], emb[:, 1], s=1, c='#bbbbbb', linewidths=0)
        farben = plt.cm.tab10(np.linspace(0, 1, 10))
        for i, k in enumerate(a['kandidaten'][:10]):
            idx = np.where(basis0['_gruppe_fenster'] == k['id'])[0]
            ax[0].scatter(emb[idx, 0], emb[idx, 1], s=4, color=farben[i], label=f'K{k["id"]} ({len(idx)}, {k["stufe"] or "-"})')
        ax[0].legend(fontsize=6, markerscale=3)
        ax[0].set_title('Hauptkomponenten 2D, ESOM-Kandidaten farbig (Seed 0)', fontsize=10)
        ax[1].imshow(basis0['_u'], cmap='terrain')
        ax[1].set_title('U-Matrix ESOM toroidal, Endradius 0,75, Seed 0', fontsize=10)
        fig.suptitle(f'A4, Satz {satz}\n{hinweis}')
        fig.tight_layout()
        fig.savefig(abb / f'pca_kandidaten_{satz}.png', dpi=100)
        plt.close(fig)

        fig, ax = plt.subplots(2, 3, figsize=(15, 8))
        for zeile, topo in enumerate(TOPOS):
            for spalte, radius in enumerate(RADIEN):
                e0 = next(e for e in ergebnisse if (e['satz'], e['topo'], e['radius'], e['daten'], e['seed'])
                          == (satz, topo, radius, 'echt', 0))
                r = a['robustheit'][f'{topo}|{radius}']
                ax[zeile, spalte].imshow(e0['_u'], cmap='terrain')
                ax[zeile, spalte].set_title(f'{topo}, Endradius {radius}: TE {r["te_median"]:.3f}, QE {r["qe_median"]:.2f}',
                                            fontsize=9)
        fig.suptitle(f'Robustheit Endradius – U-Matrizen Seed 0, Satz {satz}\n{hinweis}')
        fig.tight_layout()
        fig.savefig(abb / f'robustheit_{satz}.png', dpi=100)
        plt.close(fig)


# ------------------------------------------------------------------ Ablauf
def main():
    tar = sys.argv[1]
    t0 = time.time()
    ZIEL.mkdir(parents=True, exist_ok=True)
    v = vorbereiten(tar)                        # nutzt den Cache aus A3 (Pruefsumme des Schnappschusses)
    zeilen_je_satz, x_je_satz, sha = {}, {}, {}
    for satz in SAETZE:
        x, zeilen, _ = merkmalssatz(v, satz)
        zeilen_je_satz[satz], x_je_satz[satz] = zeilen, x
        sha[satz] = hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()

    karten = [{'satz': s, 'topo': t, 'radius': r, 'daten': 'echt', 'seed': se}
              for s, t, r, se in itertools.product(SAETZE, TOPOS, RADIEN, SEEDS)]
    karten += [{'satz': s, 'topo': 'torus', 'radius': BASIS_RADIUS, 'daten': d, 'seed': se}
               for s in SAETZE for d, seeds in (('N1', N1_SEEDS), ('N2', N2_SEEDS)) for se in seeds]
    teile_jobs = []
    for satz in SAETZE:
        zeilen = zeilen_je_satz[satz]
        for teil, (tr, te) in enumerate(GroupKFold(4).split(zeilen, groups=v['f_segment'][zeilen])):
            for seed in SEEDS:
                teile_jobs.append({'satz': satz, 'seed': seed, 'teil': teil, 'train': zeilen[tr].tolist(),
                                   'test': zeilen[te].tolist()})

    with ProcessPoolExecutor(WORKER) as ex:
        ergebnisse = []
        for i, e in enumerate(ex.map(job_karte, karten)):
            ergebnisse.append(e)
            if i % 25 == 0:
                print(f'Karten {i + 1}/{len(karten)}  {time.time() - t0:.0f}s', flush=True)
        teile = []
        for i, e in enumerate(ex.map(job_teil, teile_jobs)):
            teile.append(e)
            if i % 10 == 0:
                print(f'Teile {i + 1}/{len(teile_jobs)}  {time.time() - t0:.0f}s', flush=True)
        ent_jobs = []
        for satz in SAETZE:
            b0 = next(e for e in ergebnisse if (e['satz'], e['topo'], e['radius'], e['daten'], e['seed'])
                      == (satz, 'torus', BASIS_RADIUS, 'echt', 0))
            for k in sorted({b0['n_gruppen'], b0['n_gruppen'] + b0['n_inseln']}):
                ent_jobs += [{'satz': satz, 'art': 'kmeans', 'k': k, 'seed': s} for s in SEEDS]
            ent_jobs += [{'satz': satz, 'art': 'isolation_forest', 'seed': s} for s in SEEDS]
            ent_jobs += [{'satz': satz, 'art': a, 'seed': 0} for a in ('hdbscan', 'mahalanobis_mcd', 'lof', 'pca2')]
        entdeckung = list(ex.map(job_entdeckung, ent_jobs))
        print(f'Vergleichsverfahren fertig  {time.time() - t0:.0f}s', flush=True)

    # Seed-0-Gruppenart je Komponente fuer die Kandidatenliste
    for e in ergebnisse:
        if e['daten'] == 'echt':
            e['art_je_gruppe'] = {}
    for e in ergebnisse:
        if e['daten'] == 'echt' and e['seed'] == 0:
            g = e['_gruppe_fenster']
            ids, anz = np.unique(g, return_counts=True)
            e['art_je_gruppe'] = {int(i): ('gruppe' if a >= 0.005 * len(g) else 'insel') for i, a in zip(ids, anz, strict=True)}

    auswertung = auswerten(v, ergebnisse, teile, entdeckung, zeilen_je_satz, x_je_satz)
    for e in ergebnisse:
        if e['daten'] == 'echt':
            e['abgrenzung'] = {int(k): w for k, w in e['abgrenzung'].items()}
    auswertung.update({
        'simuliert': True, 'hinweis': 'SIMULATION (Sandbox-Szenarien sbx-gen-1.0), keine Messdaten',
        'schnappschuss_sha256': str(v['sha_tar']), 'merkmalsmatrix_sha256': sha,
        'karte': {'groesse': GROESSE, 'epochen': EPOCHEN, 'radien': RADIEN, 'basis_radius': BASIS_RADIUS,
                  'version': K.VERSION}, 'seeds': SEEDS, 'n1_seeds': len(N1_SEEDS), 'n2_seeds': len(N2_SEEDS),
        'laufzeit_s': round(time.time() - t0)})
    (ZIEL / 'metriken.json').write_text(json.dumps(auswertung, indent=1, ensure_ascii=False, default=float), encoding='utf-8')
    abbildungen(v, ergebnisse, entdeckung, auswertung, zeilen_je_satz)
    np.savez_compressed(ZIEL / 'laeufe_basis.npz', **{
        f'{e["satz"]}_{e["topo"]}_{e["radius"]}_seed{e["seed"]}': e['_gruppe_fenster']
        for e in ergebnisse if e['daten'] == 'echt'})
    print('fertig', f'{time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
