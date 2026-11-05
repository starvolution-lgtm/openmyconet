"""A1-A3 komplett: Fenster, Merkmale, Karten (klein/ESOM, planar/toroidal, Seeds 0-9),
Nullmodelle N1/N2, Projektionstest (GroupKFold nach Segment, Standort zurueckgehalten),
MiniSom-Gegenprobe, Abbildungen und metriken.json.

Aufruf (im Ordner analyse/musicminer):
    venv/Scripts/python.exe -m werkzeuge.a3_laufen daten/schnappschuss_staging_2026-11-05.tar

Alles SIMULATION. Etiketten gehen nie ins Training, nur in die Auswertung.
"""
import os

for _v in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ.setdefault(_v, '2')

import hashlib
import itertools
import json
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score, roc_auc_score
from sklearn.model_selection import GroupKFold

from mm import fenster as F
from mm import karte as K
from mm import merkmale as M
from mm.schnappschuss import Schnappschuss

ZIEL = Path('ergebnisse/a3')
GROESSEN = {'klein': (6, 8), 'esom': (40, 60)}
TOPOS = {'planar': False, 'torus': True}
SEEDS = list(range(10))
LOSO_SEEDS = [0, 1, 2]
EPOCHEN = 40
SAETZE = ('P', 'PL')
KATEGORIEN = ('szenario', 'standort', 'stichtag', 'phase', 'qualitaet', 'rolle')
WORKER = 4
if os.environ.get('MM_PROBE'):        # Kurzlauf zum Pruefen des Ablaufs (gilt auch in den Workern)
    ZIEL, SEEDS, LOSO_SEEDS, EPOCHEN = Path('ergebnisse/a3_probe'), [0, 1], [0], 3


# ---------------------------------------------------------------- Vorbereitung (A1 + A2)
def vorbereiten(tar):
    datei = ZIEL / 'vorbereitung.npz'
    sha_tar = hashlib.sha256(Path(tar).read_bytes()).hexdigest()
    if datei.exists():
        v = dict(np.load(datei, allow_pickle=False))
        if str(v['sha_tar']) == sha_tar:
            return v
    s = Schnappschuss(tar)
    s.pruefen()
    segs = s.segmente([int(k['id']) for k in s.kanaele('bioelectric_potential')])
    fw = F.fenster_bilden(segs, 10.0, 5.0)
    F.etiketten_setzen(s, segs, fw)
    p, l_ = M.berechnen(segs, fw)
    v = {'sha_tar': np.array(sha_tar), 'P': p, 'L': l_, 'laenge': np.array(fw.laenge), 'schritt': np.array(fw.schritt),
         **{f'f_{k}': getattr(fw, k) for k in ('segment', 'offset', 'lauf', 'kanal', 'erster_index', 't0')},
         **{f'e_{k}': np.array([str(x) for x in fw.etiketten[k]]) for k in ('reihe', *KATEGORIEN)},
         'e_randnah': fw.etiketten['randnah']}
    ZIEL.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(datei, **v)
    return v


def merkmalssatz(v, satz, zeilen=None, parameter=None):
    """(X normiert, Zeilenindex, Parameter). zeilen=None -> alle gueltigen Zeilen des Satzes."""
    if satz == 'P':
        roh, namen, gueltig = v['P'], M.NAMEN_P, np.ones(len(v['P']), bool)
    else:
        roh, namen = np.hstack([v['P'], v['L']]), M.NAMEN_P + M.NAMEN_L
        gueltig = ~np.isnan(v['L'][:, 2])
    alle = np.where(gueltig)[0]
    zeilen = alle if zeilen is None else np.intersect1d(zeilen, alle)
    x, par = M.normieren(roh[zeilen], namen, parameter)
    return x, zeilen, par


# ---------------------------------------------------------------- Rechenjobs (Worker)
_V = None


def _v():
    global _V
    if _V is None:
        _V = dict(np.load(ZIEL / 'vorbereitung.npz', allow_pickle=False))
    return _V


def _nulldaten(x, art, seed):
    rng = np.random.default_rng(seed + (1000 if art == 'N1' else 2000))
    if art == 'N1':
        return np.column_stack([rng.permutation(x[:, j]) for j in range(x.shape[1])])
    return rng.multivariate_normal(x.mean(0), np.cov(x, rowvar=False), size=len(x))


def _karte(x, groesse, topo, seed):
    z, s = GROESSEN[groesse]
    som = K.BatchSOM(z, s, toroidal=TOPOS[topo], seed=seed).trainieren(x, epochen=EPOCHEN)
    bmu = som.bmu(x)
    gruppe, art = som.gruppen(bmu)
    return som, bmu, gruppe, art


def job_haupt(j):
    v = _v()
    x, _, _ = merkmalssatz(v, j['satz'])
    if j['daten'] != 'echt':
        x = _nulldaten(x, j['daten'], j['seed'])
    t = time.time()
    som, bmu, gruppe, art = _karte(x, j['groesse'], j['topo'], j['seed'])
    u = som.u_matrix()
    qe = som.quantisierungsfehler(x, bmu)
    erg = {**j, 'sekunden': 0.0, 'qe': float(qe.mean()), 'te': som.topologiefehler(x),
           'u_kontrast': float(np.percentile(u, 90) / np.percentile(u, 50)),
           'n_gruppen': sum(a == 'gruppe' for a in art.values()), 'n_inseln': sum(a == 'insel' for a in art.values()),
           'art': {int(k): a for k, a in art.items()}, 'abgrenzung': som.abgrenzung(x, bmu, gruppe),
           'leer_anteil': float((np.bincount(bmu, minlength=som.k) == 0).mean()), 'karte': som.parameter()}
    erg['sekunden'] = round(time.time() - t, 1)
    erg['_bmu'] = bmu.astype(np.int32)
    erg['_gruppe_fenster'] = gruppe[bmu].astype(np.int32)
    erg['_qe'] = qe.astype(np.float32)
    erg['_u_bmu'] = u.ravel()[bmu].astype(np.float32)
    if j['seed'] == 0:
        p, radius = som.p_matrix(x)
        erg['_w'], erg['_u'], erg['_p'], erg['_gruppe_neuron'] = som.w, u, p, gruppe
        erg['p_radius'] = radius
    return erg


def job_projektion(j):
    """Trainieren ohne die zurueckgehaltenen Zeilen (Normierung nur aus Training), Test projizieren."""
    v = _v()
    x_tr, _, par = merkmalssatz(v, j['satz'], np.array(j['train']))
    x_te, z_te, _ = merkmalssatz(v, j['satz'], np.array(j['test']), par)
    som, bmu, gruppe, art = _karte(x_tr, j['groesse'], j['topo'], j['seed'])
    bmu_te = som.bmu(x_te)
    return {**{k: j[k] for k in ('satz', 'groesse', 'topo', 'seed', 'art_test', 'teil')},
            'qe_train': float(som.quantisierungsfehler(x_tr, bmu).mean()),
            'qe_test': float(som.quantisierungsfehler(x_te, bmu_te).mean()),
            'n_gruppen': sum(a == 'gruppe' for a in art.values()),
            '_test_zeilen': z_te, '_test_gruppe': gruppe[bmu_te].astype(np.int32)}


def job_minisom(j):
    from minisom import MiniSom
    v = _v()
    x, _, _ = merkmalssatz(v, j['satz'])
    z, s = GROESSEN[j['groesse']]
    t = time.time()
    m = MiniSom(z, s, x.shape[1], sigma=max(z, s) / 4, learning_rate=0.5, random_seed=0)
    m.random_weights_init(x)
    m.train(x, num_iteration=20 * len(x), random_order=True)
    return {**j, 'qe': float(m.quantization_error(x)), 'te': float(m.topographic_error(x)),
            'sekunden': round(time.time() - t, 1), 'num_iteration': 20 * len(x)}


# ---------------------------------------------------------------- Auswertung
def _auc(y, score):
    y = np.asarray(y, bool)
    return float(roc_auc_score(y, score)) if 0 < y.sum() < len(y) else None


def _gitterabstand(a, b, z, s, toroidal):
    ra, ca = np.divmod(a, s)
    rb, cb = np.divmod(b, s)
    dr, dc = np.abs(ra - rb), np.abs(ca - cb)
    if toroidal:
        dr, dc = np.minimum(dr, z - dr), np.minimum(dc, s - dc)
    return np.sqrt(dr ** 2 + dc ** 2)


def etiketten_metriken(v, zeilen, e, groesse, topo):
    g = e['_gruppe_fenster']
    out = {}
    for kat in KATEGORIEN:
        lab = v[f'e_{kat}'][zeilen]
        out[f'ari_{kat}'] = float(adjusted_rand_score(lab, g))
        out[f'nmi_{kat}'] = float(normalized_mutual_info_score(lab, g))
    q = v['e_qualitaet'][zeilen]
    out['auc_saettigung_qe'] = _auc(q == 'SATURATED', e['_qe'])
    out['auc_saettigung_u'] = _auc(q == 'SATURATED', e['_u_bmu'])
    rolle, phase, sz = v['e_rolle'][zeilen], v['e_phase'][zeilen], v['e_szenario'][zeilen]
    stim = (rolle == 'PRIMARY') & np.isin(sz, ['elektrisch', 'optisch', 'elektrooptisch_synchron', 'elektrooptisch_versetzt'])
    for ph in ('waehrend', 'nach_0_10', 'nach_10_30'):
        m = stim & np.isin(phase, ['vor', ph])
        out[f'auc_{ph}_vs_vor_qe'] = _auc(phase[m] == ph, e['_qe'][m])
    # Paarvergleich: Stimulations- und Kontrollfenster zur selben Zeit im selben Szenario
    z, s = GROESSEN[groesse]
    t0 = v['f_t0'][zeilen]
    schl = {(sz[i], round(float(t0[i]), 3)): i for i in np.where(rolle == 'CONTROL')[0]}
    paare = [(i, schl[(sz[i], round(float(t0[i]), 3))]) for i in np.where(stim)[0]
             if (sz[i], round(float(t0[i]), 3)) in schl]
    if paare:
        a, b = np.array(paare).T
        d = _gitterabstand(e['_bmu'][a], e['_bmu'][b], z, s, TOPOS[topo])
        out['paar_anteil_abstand_gt3'] = {ph: float((d[phase[a] == ph] > 3).mean()) for ph in
                                          ('vor', 'waehrend', 'nach_0_10', 'nach_10_30', 'nach_30_plus')
                                          if (phase[a] == ph).any()}
        out['paar_anzahl'] = len(paare)
    return out


def gruppen_profil(v, zeilen, satz, e, seed_laeufe):
    """Seed-0-Gruppen: Groesse, Art, Abgrenzung, Wiederfinden in anderen Seeds, Etiketten, Merkmale."""
    g0 = e['_gruppe_fenster']
    roh = v['P'][zeilen] if satz == 'P' else np.hstack([v['P'], v['L']])[zeilen]
    namen = M.NAMEN_P if satz == 'P' else M.NAMEN_P + M.NAMEN_L
    andere = [K.jaccard_beste(g0, x['_gruppe_fenster']) for x in seed_laeufe if x['seed'] != 0]
    out = []
    for gi in np.unique(g0):
        m = g0 == gi
        prof = {'gruppe': int(gi), 'art': e['art'][int(gi)], 'fenster': int(m.sum()),
                'abgrenzung': e['abgrenzung'].get(int(gi)),
                'wiedergefunden_seeds': int(sum(a[int(gi)] >= 0.5 for a in andere)),
                'jaccard_median': float(np.median([a[int(gi)] for a in andere])) if andere else None,
                'randnah_anteil': float(v['e_randnah'][zeilen][m].mean())}
        for kat in KATEGORIEN:
            werte, anz = np.unique(v[f'e_{kat}'][zeilen][m], return_counts=True)
            reihenf = np.argsort(-anz)[:3]
            prof[kat] = {str(werte[i]): round(float(anz[i] / m.sum()), 3) for i in reihenf}
        prof['merkmale_median'] = {n: round(float(np.median(roh[m, j])), 4) for j, n in enumerate(namen)}
        out.append(prof)
    return sorted(out, key=lambda p: -p['fenster'])


# ---------------------------------------------------------------- Abbildungen
def abbildungen(v, ergebnisse, zeilen_je_satz):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    abb = ZIEL / 'abbildungen'
    abb.mkdir(exist_ok=True)
    hinweis = 'SIMULATION (Sandbox sbx-gen-1.0) – keine Messdaten'
    for satz, groesse, topo in itertools.product(SAETZE, GROESSEN, TOPOS):
        def lauf(daten, seed=0, satz=satz, groesse=groesse, topo=topo):
            return next(x for x in ergebnisse if (x['satz'], x['groesse'], x['topo'], x['daten'], x['seed'])
                        == (satz, groesse, topo, daten, seed))
        e = lauf('echt')
        z, s = GROESSEN[groesse]
        fig, ax = plt.subplots(2, 2, figsize=(13, 9))
        bilder = [('U-Matrix (echt, Seed 0)', e['_u']), ('P-Matrix (Dichte, echt, Seed 0)', e['_p']),
                  ('U-Matrix Nullmodell N1 (Spalten vertauscht)', lauf('N1')['_u']),
                  ('U-Matrix Nullmodell N2 (eine Normalverteilung)', lauf('N2')['_u'])]
        for a, (titel, bild) in zip(ax.ravel(), bilder, strict=True):
            im = a.imshow(bild, cmap='terrain' if 'U-' in titel else 'viridis', origin='upper')
            a.set_title(titel, fontsize=10)
            fig.colorbar(im, ax=a, shrink=0.8)
        gn = e['_gruppe_neuron'].reshape(z, s)
        ax[0, 0].contour(gn, levels=np.arange(gn.max() + 1) + 0.5, colors='k', linewidths=0.6)
        fig.suptitle(f'Satz {satz}, {groesse} {z}×{s}, {topo} – {e["n_gruppen"]} Gruppen, {e["n_inseln"]} Inseln\n{hinweis}')
        fig.tight_layout()
        fig.savefig(abb / f'karte_{satz}_{groesse}_{topo}.png', dpi=110)
        plt.close(fig)

        if groesse != 'esom':
            continue
        zeilen = zeilen_je_satz[satz]
        r, c = np.divmod(e['_bmu'], s)
        rng = np.random.default_rng(0)
        jr, jc = r + rng.uniform(-0.35, 0.35, len(r)), c + rng.uniform(-0.35, 0.35, len(c))
        for kat in ('standort', 'stichtag', 'phase', 'qualitaet', 'szenario'):
            lab = v[f'e_{kat}'][zeilen]
            klassen = sorted(set(lab))
            fig, ax = plt.subplots(2, (len(klassen) + 1) // 2, figsize=(4.2 * ((len(klassen) + 1) // 2), 6.5),
                                   squeeze=False)
            for a in ax.ravel():
                a.axis('off')
            for a, k in zip(ax.ravel(), klassen, strict=False):
                m = lab == k
                a.imshow(e['_u'], cmap='Greys', origin='upper', alpha=0.6)
                a.scatter(jc[m], jr[m], s=1.5 if m.sum() > 200 else 8, c='crimson', alpha=0.5, linewidths=0)
                a.set_title(f'{k} ({m.sum()})', fontsize=9)
            fig.suptitle(f'Treffer je {kat} – Satz {satz}, ESOM {topo}, Seed 0\n{hinweis}', fontsize=10)
            fig.tight_layout()
            fig.savefig(abb / f'etikett_{kat}_{satz}_esom_{topo}.png', dpi=100)
            plt.close(fig)


# ---------------------------------------------------------------- Ablauf
def main():
    tar = sys.argv[1]
    t_start = time.time()
    ZIEL.mkdir(parents=True, exist_ok=True)
    v = vorbereiten(tar)
    print('Fenster', len(v['P']), f'{time.time() - t_start:.0f}s', flush=True)

    zeilen_je_satz, satz_info = {}, {}
    for satz in SAETZE:
        x, zeilen, par = merkmalssatz(v, satz)
        zeilen_je_satz[satz] = zeilen
        satz_info[satz] = {'zeilen': len(zeilen), 'merkmale': int(x.shape[1]), 'normierung': par,
                           'sha256_matrix': hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()}
        np.savez_compressed(ZIEL / f'merkmale_{satz}.npz', x=x, zeilen=zeilen)

    jobs = [{'satz': sa, 'groesse': g, 'topo': t, 'daten': d, 'seed': se}
            for sa, g, t, d, se in itertools.product(SAETZE, GROESSEN, TOPOS, ('echt', 'N1', 'N2'), SEEDS)]
    jobs.sort(key=lambda j: j['groesse'] != 'esom')          # lange Jobs zuerst
    proj_jobs = []
    for satz in SAETZE:
        zeilen = zeilen_je_satz[satz]
        seg = v['f_segment'][zeilen]
        for teil, (tr, te) in enumerate(GroupKFold(4).split(zeilen, groups=seg)):
            for seed in SEEDS:
                proj_jobs.append({'satz': satz, 'groesse': 'esom', 'topo': 'torus', 'seed': seed, 'art_test': 'segmente',
                                  'teil': teil, 'train': zeilen[tr].tolist(), 'test': zeilen[te].tolist()})
        for ort in sorted(set(v['e_standort'][zeilen])):
            m = v['e_standort'][zeilen] == ort
            for seed in LOSO_SEEDS:
                proj_jobs.append({'satz': satz, 'groesse': 'esom', 'topo': 'torus', 'seed': seed, 'art_test': 'standort',
                                  'teil': ort, 'train': zeilen[~m].tolist(), 'test': zeilen[m].tolist()})

    with ProcessPoolExecutor(WORKER) as ex:
        f_mini = ex.submit(job_minisom, {'satz': 'P', 'groesse': 'esom', 'topo': 'planar'})
        ergebnisse = []
        for i, e in enumerate(ex.map(job_haupt, jobs)):
            ergebnisse.append(e)
            if i % 20 == 0:
                print(f'Hauptlaeufe {i + 1}/{len(jobs)}  {time.time() - t_start:.0f}s', flush=True)
        projektion = []
        for i, e in enumerate(ex.map(job_projektion, proj_jobs)):
            projektion.append(e)
            if i % 20 == 0:
                print(f'Projektion {i + 1}/{len(proj_jobs)}  {time.time() - t_start:.0f}s', flush=True)
        minisom_erg = f_mini.result()

    # --- Auswertung je Konfiguration
    konfig = {}
    for satz, groesse, topo in itertools.product(SAETZE, GROESSEN, TOPOS):
        def sel(daten, satz=satz, groesse=groesse, topo=topo):
            return sorted([x for x in ergebnisse if (x['satz'], x['groesse'], x['topo'], x['daten'])
                           == (satz, groesse, topo, daten)], key=lambda x: x['seed'])
        echt, n1, n2 = sel('echt'), sel('N1'), sel('N2')
        zeilen = zeilen_je_satz[satz]
        ari_paare = [adjusted_rand_score(a['_gruppe_fenster'], b['_gruppe_fenster'])
                     for a, b in itertools.combinations(echt, 2)]

        def zusammenfassung(liste):
            abgr = [w for x in liste for w in x['abgrenzung'].values()]
            return {'qe': [round(x['qe'], 4) for x in liste], 'te': [round(x['te'], 4) for x in liste],
                    'n_gruppen': [x['n_gruppen'] for x in liste], 'n_inseln': [x['n_inseln'] for x in liste],
                    'u_kontrast': [round(x['u_kontrast'], 3) for x in liste],
                    'leer_anteil': [round(x['leer_anteil'], 3) for x in liste],
                    'abgrenzung_p95': float(np.percentile(abgr, 95)) if abgr else None,
                    'abgrenzung_anzahl': len(abgr), 'sekunden': [x['sekunden'] for x in liste]}
        k = {'echt': zusammenfassung(echt), 'N1': zusammenfassung(n1), 'N2': zusammenfassung(n2),
             'stabilitaet_ari_paarweise': {'median': float(np.median(ari_paare)), 'min': float(np.min(ari_paare)),
                                           'max': float(np.max(ari_paare))},
             'etiketten_je_seed': [etiketten_metriken(v, zeilen, e, groesse, topo) for e in echt],
             'gruppen_seed0': gruppen_profil(v, zeilen, satz, echt[0], echt),
             'p_radius_seed0': echt[0].get('p_radius')}
        konfig[f'{satz}|{groesse}|{topo}'] = k
        np.savez_compressed(ZIEL / f'laeufe_{satz}_{groesse}_{topo}.npz',
                            **{f'gruppe_seed{e["seed"]}': e['_gruppe_fenster'] for e in echt},
                            **{f'bmu_seed{e["seed"]}': e['_bmu'] for e in echt},
                            w_seed0=echt[0]['_w'], u_seed0=echt[0]['_u'], p_seed0=echt[0]['_p'],
                            gruppe_neuron_seed0=echt[0]['_gruppe_neuron'], zeilen=zeilen)

    # --- Projektionstest: Gruppen der zurueckgehaltenen Fenster vs. Karte auf allen Daten (gleicher Seed)
    proj = {}
    for p in projektion:
        voll = next(x for x in ergebnisse if (x['satz'], x['groesse'], x['topo'], x['daten'], x['seed'])
                    == (p['satz'], p['groesse'], p['topo'], 'echt', p['seed']))
        pos = np.searchsorted(zeilen_je_satz[p['satz']], p['_test_zeilen'])
        ari = float(adjusted_rand_score(voll['_gruppe_fenster'][pos], p['_test_gruppe']))
        proj.setdefault(f'{p["satz"]}|{p["art_test"]}', []).append(
            {'teil': p['teil'], 'seed': p['seed'], 'ari_zur_vollen_karte': round(ari, 4),
             'qe_verhaeltnis_test_train': round(p['qe_test'] / p['qe_train'], 4), 'n_gruppen': p['n_gruppen']})

    import minisom
    import scipy
    import sklearn
    metriken = {
        'simuliert': True, 'hinweis': 'SIMULATION (Sandbox-Szenarien sbx-gen-1.0, Szenario-Version 2), keine Messdaten',
        'schnappschuss_sha256': str(v['sha_tar']), 'fenster': {'anzahl': len(v['P']), 'laenge_samples': int(v['laenge']),
                                                              'schritt_samples': int(v['schritt'])},
        'merkmalssatz': M.VERSION, 'karte': K.VERSION, 'kriterien': 'v2', 'saetze': satz_info,
        'groessen': GROESSEN, 'seeds': SEEDS, 'epochen': EPOCHEN, 'konfigurationen': konfig, 'projektion': proj,
        'minisom_gegenprobe': minisom_erg,
        'umgebung': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__,
                     'sklearn': sklearn.__version__, 'minisom': getattr(minisom, '__version__', '2.3.6')},
        'laufzeit_s': round(time.time() - t_start),
    }
    (ZIEL / 'metriken.json').write_text(json.dumps(metriken, indent=1, ensure_ascii=False, default=float), encoding='utf-8')
    abbildungen(v, ergebnisse, zeilen_je_satz)
    print('fertig', f'{time.time() - t_start:.0f}s')


if __name__ == '__main__':
    main()
