"""Gerechnete Entscheidungsregeln: Ergaenzung E1 zu Kriterien v2 (KRITERIEN.md, Abschnitt 9).

Gilt prospektiv ab A4. A1-A3 bleiben nach v2 bewertet.
"""
import numpy as np

VERSION = 'v2+E1'
KLASSEN = ((10, 19), (20, 39), (40, 79), (80, 159), (160, 319), (320, 639), (640, 1279), (1280, 2559),
           (2560, None))
MIN_NULLKOMPONENTEN = 20
STUFEN = ('Bestätigt nach ursprünglichem Kriterium', 'Explorativ gestützt', 'Unbestätigter Kandidat')


def klasse(groesse):
    """Index der Groessenklasse (0 = G1) oder None unter 10 Fenstern."""
    for i, (lo, hi) in enumerate(KLASSEN):
        if groesse >= lo and (hi is None or groesse <= hi):
            return i
    return None


def klassenname(i):
    lo, hi = KLASSEN[i]
    return f'G{i + 1} ({lo}–{hi})' if hi else f'G{i + 1} (≥ {lo})'


def schwelle_klasse(nulllaeufe, k, anzahl_klassen):
    """9.2: Schwelle fuer Klasse k aus den Nulllaeufen.

    nulllaeufe: Liste je Nulllauf, darin Liste (groesse, abgrenzung) seiner Komponenten.
    anzahl_klassen: K (Klassen, in denen Kandidaten geprueft werden)."""
    maxima, anzahl = [], 0
    for lauf in nulllaeufe:
        werte = [a for g, a in lauf if klasse(g) == k and a == a]
        anzahl += len(werte)
        if werte:
            maxima.append(max(werte))
    q = 1 - 0.05 / anzahl_klassen
    genug = anzahl >= MIN_NULLKOMPONENTEN and len(maxima) >= 20 * anzahl_klassen
    return {'klasse': klassenname(k), 'nullkomponenten': anzahl, 'laeufe_mit_komponente': len(maxima),
            'quantil': round(q, 4), 'genug_nulldaten': bool(genug),
            'schwelle': float(np.quantile(maxima, q)) if genug else None}


def schwelle_global(nulllaeufe):
    """9.3 (= v2 8b.2): 95. Perzentil aller Nullkomponenten; None = keine vorhanden."""
    werte = [a for lauf in nulllaeufe for _, a in lauf if a == a]
    return {'nullkomponenten': len(werte), 'schwelle': float(np.percentile(werte, 95)) if werte else None}


def stufe(p):
    """9.5: Ergebnisstufe aus den Einzelpruefungen (dict mit bool-Werten).

    Schluessel: stabil (8b.1), global (9.3), groesse (9.2), nachpruefbar (8b.3),
    kein_artefakt (8b.4), uebertraegt (8b.5), wiedergefunden_5 (>= 5 von 10 Seeds)."""
    basis = p['stabil'] and p['nachpruefbar'] and p['kein_artefakt'] and p['uebertraegt']
    if basis and p['global']:
        return STUFEN[0]
    if basis and p['groesse']:
        return STUFEN[1]
    if p['wiedergefunden_5']:
        return STUFEN[2]
    return None
