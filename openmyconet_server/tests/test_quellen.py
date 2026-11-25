"""Gemeinsames Quellenverzeichnis: Schema, Positivliste, Verknüpfungen, alte Sprungmarken."""
import json
import re
from pathlib import Path

from omn import quellen

REPO = Path(__file__).resolve().parent.parent


def test_verzeichnis_ohne_fehler():
    assert quellen.fehler() == []


def test_ids_und_kennungen_format():
    for q in quellen.quellen():
        assert re.fullmatch(r"Q\d{4}", q["id"])
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", q["kennung"])


def test_keine_internen_felder_im_rohtext():
    roh = quellen.PFAD.read_text(encoding="utf-8")
    for intern in ("pruefstufe", "vermerke", "letzte_pruefung", "beleg", "nachweis", "oeffentlich", "zugang_vorschlag",
                   "ablauf", "entwurf", "herkunft_bibliografie", "textaenderung_gegenueber_bestand", "_migration"):
        assert f'"{intern}"' not in roh, intern


def test_positivliste_greift_auch_bei_unbekanntem_feld():
    d = json.loads(quellen.PFAD.read_text(encoding="utf-8"))
    d["quellen"][0]["interne_notiz"] = "darf nicht durch"
    assert any("interne_notiz" in f for f in quellen.fehler(d))


def test_kommentare_sind_rueckwaerts_auffindbar():
    t = quellen.nach_kennung("thomas-cooper-2022")
    assert ("kommentiert", quellen.nach_kennung("blatt-2023")) in quellen.rueckbeziehungen(t["id"])


def test_alle_verwendeten_alten_sprungmarken_haben_ein_ziel():
    """Jede Sprungmarke auf die Quellenseite, die heute irgendwo im Repo steht, muss auflösbar sein."""
    texte = [(REPO / "app/static/translations.json").read_text(encoding="utf-8")]
    texte += [p.read_text(encoding="utf-8") for p in (REPO / "app/templates").rglob("*.html")]
    anker = {a for t in texte for a in re.findall(r"quellennachweise\.html#([a-z0-9-]+)", t)}
    assert anker, "keine Sprungmarken gefunden – Suchmuster prüfen"
    assert {a for a in anker if quellen.anker_aufloesen(a) is None} == set()


def test_alte_eintragsnummern_bleiben_erreichbar():
    """Die frühere Seite hatte 45 Einträge mit #ref-<nr>; die Zuordnung darf keine davon verlieren."""
    alte = {a for a in quellen.laden()["alte_anker"] if a.startswith("ref-")}
    assert len(alte) >= 45
    assert all(quellen.anker_aufloesen(a) for a in alte)
