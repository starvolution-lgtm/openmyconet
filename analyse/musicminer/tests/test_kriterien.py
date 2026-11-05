"""Tests fuer die gerechneten Regeln der Ergaenzung E1 (KRITERIEN.md, Abschnitt 9)."""
from mm.kriterien import STUFEN, klasse, schwelle_global, schwelle_klasse, stufe


def test_klassen():
    assert klasse(9) is None and klasse(10) == 0 and klasse(19) == 0 and klasse(20) == 1
    assert klasse(2559) == 7 and klasse(10 ** 6) == 8


def test_schwelle_ueber_laufmaxima_mit_bonferroni():
    # 40 Nulllaeufe mit je zwei Inseln in G2 (Abgrenzung 1.0 und 1.0 + i/100)
    laeufe = [[(25, 1.0), (30, 1.0 + i / 100)] for i in range(40)]
    s1 = schwelle_klasse(laeufe, 1, anzahl_klassen=1)
    assert s1['genug_nulldaten'] and s1['laeufe_mit_komponente'] == 40
    assert 1.36 < s1['schwelle'] < 1.39                 # 95-%-Quantil der Laufmaxima 1.00..1.39
    s2 = schwelle_klasse(laeufe, 1, anzahl_klassen=2)   # 97,5 % braucht >= 40 Laeufe -> noch genug
    assert s2['genug_nulldaten'] and s2['schwelle'] > s1['schwelle']
    s3 = schwelle_klasse(laeufe, 1, anzahl_klassen=3)   # braucht 60 Laeufe -> keine Signifikanz
    assert not s3['genug_nulldaten'] and s3['schwelle'] is None


def test_zu_wenige_nullkomponenten():
    s = schwelle_klasse([[(25, 1.0)]] * 10 + [[]] * 30, 1, 1)
    assert not s['genug_nulldaten']


def test_global_und_stufen():
    assert schwelle_global([[], []])['schwelle'] is None
    assert schwelle_global([[(5000, 2.0)], [(20, 4.0)]])['nullkomponenten'] == 2
    ok = dict(stabil=True, nachpruefbar=True, kein_artefakt=True, uebertraegt=True, wiedergefunden_5=True)
    assert stufe({**ok, 'global': True, 'groesse': False}) == STUFEN[0]
    assert stufe({**ok, 'global': False, 'groesse': True}) == STUFEN[1]
    assert stufe({**ok, 'global': False, 'groesse': False}) == STUFEN[2]
    assert stufe({**ok, 'stabil': False, 'global': True, 'groesse': True}) == STUFEN[2]
    assert stufe({**ok, 'stabil': False, 'global': True, 'groesse': True, 'wiedergefunden_5': False}) is None
