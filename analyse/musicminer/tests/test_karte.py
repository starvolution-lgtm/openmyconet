"""Tests fuer mm.karte (Batch-SOM, Gruppenregel) und mm.merkmale."""
import numpy as np

from mm.karte import BatchSOM, jaccard_beste
from mm.merkmale import merkmale_p, normieren


def _drei_wolken(n=600, seed=0):
    rng = np.random.default_rng(seed)
    zentren = np.array([[0, 0, 0], [8, 0, 0], [0, 8, 0]], float)
    wahr = rng.integers(0, 3, n)
    return zentren[wahr] + rng.normal(0, 0.5, (n, 3)), wahr


def test_toroidale_abstaende():
    som = BatchSOM(4, 6, toroidal=True)
    # Neuron (0,0) und (0,5) sind auf dem Torus Nachbarn
    assert som.gitter2[0, 5] == 1 and 5 in som.nachbarn[0]
    assert BatchSOM(4, 6).gitter2[0, 5] == 25


def test_deterministisch_je_seed():
    x, _ = _drei_wolken()
    a = BatchSOM(6, 8, seed=3).trainieren(x, epochen=10).w
    b = BatchSOM(6, 8, seed=3).trainieren(x, epochen=10).w
    assert np.array_equal(a, b)


def test_findet_drei_wolken_als_gruppen():
    x, wahr = _drei_wolken()
    for toroidal in (False, True):
        som = BatchSOM(12, 16, toroidal=toroidal, seed=1).trainieren(x, epochen=30)
        bmu = som.bmu(x)
        gruppe, art = som.gruppen(bmu)
        g = gruppe[bmu]
        assert len(np.unique(g)) == 3 and set(art.values()) == {'gruppe'}
        assert min(jaccard_beste(wahr, g).values()) > 0.95
        assert som.topologiefehler(x) < 0.1
        assert min(som.abgrenzung(x, bmu, gruppe).values()) > 3    # deutlich abgegrenzt


def test_eine_normalverteilung_ergibt_eine_gruppe():
    x = np.random.default_rng(5).normal(size=(5000, 10))
    som = BatchSOM(40, 60, toroidal=True, seed=1).trainieren(x, epochen=20)
    gruppe, _ = som.gruppen(som.bmu(x))
    assert len(np.unique(gruppe)) == 1


def test_seltene_insel_bleibt_erhalten():
    rng = np.random.default_rng(2)
    x = np.vstack([rng.normal(size=(3000, 4)), rng.normal(12, 0.2, size=(12, 4))])   # 12 Ausreisser = 0,4 %
    som = BatchSOM(20, 30, seed=0).trainieren(x, epochen=25)
    bmu = som.bmu(x)
    gruppe, art = som.gruppen(bmu)
    g = gruppe[bmu]
    assert len(set(g[-12:])) == 1 and g[-1] not in set(g[:3000])
    assert art[g[-1]] == 'insel'


def test_merkmale_weisses_rauschen_und_saettigung():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 10, (4, 2500))
    zaehl = np.round(x * 100 / 7.8125)
    zaehl[3] = 32767
    x[3] = 2559.9
    p = merkmale_p(x, zaehl, 250.0)
    assert np.allclose(p[:3, 0], 10, rtol=0.1)              # robuste Streuung
    assert np.allclose(p[:3, 9], 0.56, atol=0.03)           # spektrale Flachheit weisses Rauschen
    assert p[3, 12] == 1 and p[3, 13] == 1                  # ADC-Rand, gleichbleibende Folge
    z, par = normieren(p, [f'm{i}' for i in range(p.shape[1])])
    assert np.abs(z).max() <= 8 and len(par['median']) == p.shape[1]
