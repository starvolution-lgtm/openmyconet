"""A3: Batch-SOM (planar oder toroidal), U-Matrix, P-Matrix, Gruppenbildung nach Regel v1.

Eine Implementierung fuer alle Varianten (kleine SOM und ESOM, planar und toroidal), deterministisch
je Seed. MiniSom dient nur als Gegenprobe der planaren Karte (werkzeuge/a3_laufen.py).
"""
from collections import deque

import numpy as np

VERSION = 'karte-v1'


class BatchSOM:
    def __init__(self, zeilen, spalten, toroidal=False, seed=0):
        self.z, self.s, self.toroidal, self.seed = zeilen, spalten, toroidal, seed
        self.k = zeilen * spalten
        r, c = np.divmod(np.arange(self.k), spalten)
        dr = np.abs(r[:, None] - r[None, :])
        dc = np.abs(c[:, None] - c[None, :])
        if toroidal:
            dr, dc = np.minimum(dr, zeilen - dr), np.minimum(dc, spalten - dc)
        self.gitter2 = (dr ** 2 + dc ** 2).astype(np.float64)    # quadrierte Gitterabstaende
        self.nachbarn = self._nachbarn()
        self.w = None

    def _nachbarn(self, acht=False):
        schritte = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if acht:
            schritte += [(-1, -1), (-1, 1), (1, -1), (1, 1)]
        out = []
        for i in range(self.k):
            r, c = divmod(i, self.s)
            liste = []
            for a, b in schritte:
                rr, cc = r + a, c + b
                if self.toroidal:
                    rr, cc = rr % self.z, cc % self.s
                elif not (0 <= rr < self.z and 0 <= cc < self.s):
                    continue
                liste.append(rr * self.s + cc)
            out.append(liste)
        return out

    def parameter(self):
        return {'version': VERSION, 'zeilen': self.z, 'spalten': self.s, 'toroidal': self.toroidal,
                'seed': self.seed, **getattr(self, 'training', {})}

    # -- Training --------------------------------------------------------------
    def trainieren(self, x, epochen=40, sigma_start=None, sigma_ende=0.75):
        rng = np.random.default_rng(self.seed)
        if sigma_start is None:
            sigma_start = max(2.0, max(self.z, self.s) / 4)
        self.w = x[rng.choice(len(x), self.k, replace=len(x) < self.k)].copy()
        for e in range(epochen):
            sigma = sigma_start * (sigma_ende / sigma_start) ** (e / max(1, epochen - 1))
            bmu = self.bmu(x)
            summe = np.zeros_like(self.w)
            np.add.at(summe, bmu, x)
            anzahl = np.bincount(bmu, minlength=self.k).astype(np.float64)
            h = np.exp(-self.gitter2 / (2 * sigma * sigma))
            self.w = (h @ summe) / (h @ anzahl)[:, None]
        self.training = {'epochen': epochen, 'sigma_start': sigma_start, 'sigma_ende': sigma_ende,
                         'initialisierung': 'zufaellige Datenpunkte'}
        return self

    def _abstaende2(self, x):
        return (x * x).sum(1)[:, None] - 2 * x @ self.w.T + (self.w * self.w).sum(1)[None, :]

    def bmu(self, x, block=4096, zwei=False):
        """Gewinnerneuron(e); Abstaende in float32 (doppelt so schnell, Prototypen bleiben float64)."""
        erste, zweite = np.empty(len(x), int), np.empty(len(x), int)
        w = self.w.astype(np.float32)
        ww = (w * w).sum(1)[None, :]
        for a in range(0, len(x), block):
            xx = x[a:a + block].astype(np.float32)
            d = (xx * xx).sum(1)[:, None] - 2 * xx @ w.T + ww
            if zwei:
                p = np.argpartition(d, 1, axis=1)[:, :2]
                vorne = np.take_along_axis(d, p, 1).argsort(axis=1)
                p = np.take_along_axis(p, vorne, 1)
                erste[a:a + block], zweite[a:a + block] = p[:, 0], p[:, 1]
            else:
                erste[a:a + block] = d.argmin(axis=1)
        return (erste, zweite) if zwei else erste

    # -- Guete ------------------------------------------------------------------
    def quantisierungsfehler(self, x, bmu=None):
        bmu = self.bmu(x) if bmu is None else bmu
        return np.linalg.norm(x - self.w[bmu], axis=1)

    def topologiefehler(self, x):
        erste, zweite = self.bmu(x, zwei=True)
        acht = self._nachbarn(acht=True)
        return float(np.mean([z not in acht[e] for e, z in zip(erste, zweite, strict=True)]))

    # -- Matrizen ---------------------------------------------------------------
    def kanten(self):
        """Alle Nachbarpaare (i < j, 4er-Nachbarschaft) mit Prototypabstand."""
        paare = sorted({(min(i, j), max(i, j)) for i in range(self.k) for j in self.nachbarn[i] if i != j})
        a, b = np.array(paare).T
        return a, b, np.linalg.norm(self.w[a] - self.w[b], axis=1)

    def u_matrix(self):
        u = np.array([np.mean([np.linalg.norm(self.w[i] - self.w[j]) for j in self.nachbarn[i]])
                      for i in range(self.k)])
        return u.reshape(self.z, self.s)

    def p_matrix(self, x, radius=None, rng=None):
        if radius is None:
            rng = rng or np.random.default_rng(self.seed)
            i = rng.choice(len(x), min(3000, len(x)), replace=False)
            d = np.sqrt(np.maximum(_paar2(x[i]), 0))
            radius = float(np.percentile(d[np.triu_indices(len(i), 1)], 18))
        anzahl = np.zeros(self.k)
        for a in range(0, len(x), 4096):
            anzahl += (self._abstaende2(x[a:a + 4096]) <= radius * radius).sum(axis=0)
        return anzahl.reshape(self.z, self.s), radius

    # -- Gruppen (Regel v2, KRITERIEN.md Abschnitt 4) ---------------------------------
    def gruppen(self, bmu, faktor=3.0, mindestanteil=0.005, insel_min=10):
        """Gruppe je Neuron.

        Knoten = Neuronen mit mindestens einem Fenster; leere Neuronen sind Mauer (ESOM-Prinzip).
        Eine Kante zwischen benachbarten getroffenen Neuronen bleibt, wenn ihr Prototypabstand
        <= faktor x Median dieser Kanten ist. Zusammenhangskomponenten mit >= mindestanteil der
        Fenster sind Gruppen, kleinere mit >= insel_min Fenstern bleiben als Inseln eigenstaendig,
        noch kleinere gehen in die naechstgelegene Komponente (Prototypraum). Leere Neuronen
        bekommen fuer die Darstellung die Gruppe des naechsten getroffenen Neurons.

        Rueckgabe: (gruppe je Neuron 0..n-1, art je Gruppe 'gruppe'|'insel')."""
        treffer = np.bincount(bmu, minlength=self.k)
        a, b, d = self.kanten()
        hh = (treffer[a] > 0) & (treffer[b] > 0)
        grenze = faktor * np.median(d[hh]) if hh.any() else np.inf
        nb = [[] for _ in range(self.k)]
        for i, j in zip(a[hh & (d <= grenze)], b[hh & (d <= grenze)], strict=True):
            nb[i].append(j)
            nb[j].append(i)
        gruppe = np.full(self.k, -1)
        g = 0
        for start in np.where(treffer > 0)[0]:
            if gruppe[start] >= 0:
                continue
            q = deque([start])
            gruppe[start] = g
            while q:
                i = q.popleft()
                for j in nb[i]:
                    if gruppe[j] < 0:
                        gruppe[j] = g
                        q.append(j)
            g += 1
        # Winzlinge (< insel_min Fenster) in die naechstgelegene Komponente
        while True:
            ids = [gi for gi in np.unique(gruppe) if gi >= 0]
            groesse = {gi: treffer[gruppe == gi].sum() for gi in ids}
            winzig = [gi for gi in ids if groesse[gi] < insel_min]
            if not winzig or len(ids) == 1:
                break
            gi = min(winzig, key=lambda x: groesse[x])
            innen, aussen = gruppe == gi, (gruppe != gi) & (gruppe >= 0)
            dd = _paar2(self.w[innen], self.w[aussen])
            gruppe[innen] = gruppe[aussen][np.unravel_index(dd.argmin(), dd.shape)[1]]
        leer = gruppe < 0
        if leer.any():
            dd = _paar2(self.w[leer], self.w[~leer])
            gruppe[leer] = gruppe[~leer][dd.argmin(axis=1)]
        ids, gruppe = np.unique(gruppe, return_inverse=True)
        art = {}
        for gi in range(len(ids)):
            art[gi] = 'gruppe' if treffer[gruppe == gi].sum() >= mindestanteil * len(bmu) else 'insel'
        return gruppe, art

    def abgrenzung(self, x, bmu, gruppe):
        """Je Gruppe: Median ueber ihre Fenster von (Abstand zum naechsten getroffenen Prototyp
        einer ANDEREN Gruppe) / (Abstand zum eigenen Gewinnerneuron). > 1 = abgegrenzt."""
        treffer = np.bincount(bmu, minlength=self.k) > 0
        gw = gruppe[bmu]
        out = {}
        if len(np.unique(gruppe[treffer])) < 2:
            return out
        eigen = np.linalg.norm(x - self.w[bmu], axis=1)
        for gi in np.unique(gw):
            m = gw == gi
            andere = treffer & (gruppe != gi)
            d = np.sqrt(np.maximum(_paar2(x[m], self.w[andere]), 0)).min(axis=1)
            out[int(gi)] = float(np.median(d / np.maximum(eigen[m], 1e-9)))
        return out


def _paar2(a, b=None):
    b = a if b is None else b
    return (a * a).sum(1)[:, None] - 2 * a @ b.T + (b * b).sum(1)[None, :]


def jaccard_beste(gruppen_a, gruppen_b):
    """Je Gruppe von a die beste Jaccard-Uebereinstimmung mit einer Gruppe von b (Fenstermengen)."""
    out = {}
    for ga in np.unique(gruppen_a):
        ma = gruppen_a == ga
        best = 0.0
        for gb in np.unique(gruppen_b[ma]):
            mb = gruppen_b == gb
            best = max(best, (ma & mb).sum() / (ma | mb).sum())
        out[int(ga)] = float(best)
    return out
