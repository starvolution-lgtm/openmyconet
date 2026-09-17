"""Haelt die 5 Sprachbloecke in app/static/translations.json synchron.

Hintergrund: Uebersetzungen werden nicht per API gepflegt, sondern von Hand
(meist von einer KI beim Einpflegen einer Textaenderung mitgeliefert) direkt
in translations.json ergaenzt -- pro Sprache ein eigener Edit. Wird dabei eine
Sprache vergessen, faellt das zur Laufzeit nicht auf: t() in omn/i18n.py
faellt bei einem fehlenden Key stillschweigend auf die deutsche Fassung
zurueck, die Seite zeigt also einfach deutschen Text mitten in einer
englischen/franzoesischen/... Seite, ohne Fehler oder Log-Eintrag. Dieser Test
macht das stattdessen zu einem CI-Fehler, sofort beim Push.
"""
import json
from pathlib import Path

TRANSLATIONS_PATH = (
    Path(__file__).resolve().parent.parent / "app" / "static" / "translations.json"
)
LANGS = ["de", "en", "nl", "fr", "es"]


def _load():
    return json.loads(TRANSLATIONS_PATH.read_text(encoding="utf-8"))


def test_alle_sprachbloecke_vorhanden():
    tr = _load()
    for lang in LANGS:
        assert lang in tr, f"Sprachblock '{lang}' fehlt komplett in translations.json"


def test_keine_fehlenden_oder_verwaisten_keys():
    """DE ist die fuehrende Sprache -- jeder Key aus DE muss in den anderen
    vier Sprachen existieren, und keine der vier darf zusaetzliche Keys haben,
    die es in DE nicht (mehr) gibt (typisch nach einer Umbenennung/Loeschung,
    bei der nur die DE-Version angepasst wurde)."""
    tr = _load()
    de_keys = set(tr["de"].keys())
    fehler = []

    for lang in LANGS:
        if lang == "de":
            continue
        lang_keys = set(tr[lang].keys())
        fehlend = de_keys - lang_keys
        verwaist = lang_keys - de_keys
        if fehlend:
            fehler.append(f"{lang}: fehlende Keys (in DE, nicht in {lang}): {sorted(fehlend)}")
        if verwaist:
            fehler.append(f"{lang}: verwaiste Keys (in {lang}, nicht mehr in DE): {sorted(verwaist)}")

    assert not fehler, "\n" + "\n".join(fehler)


def test_keine_leeren_uebersetzungen():
    """Ein Key mit leerem String ist meist ein vergessenes Nachziehen bei
    einer neuen Sprache, kein bewusster Inhalt."""
    tr = _load()
    fehler = []
    for lang in LANGS:
        leere_keys = [k for k, v in tr[lang].items() if isinstance(v, str) and v.strip() == ""]
        if leere_keys:
            fehler.append(f"{lang}: leere Uebersetzung bei: {sorted(leere_keys)}")
    assert not fehler, "\n" + "\n".join(fehler)
