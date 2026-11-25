"""Gemeinsames Quellenverzeichnis (öffentlicher Teil).

Die Daten stehen in ``omn/daten/quellen.json`` und werden aus dem internen Arbeitsbestand (nicht im Repo)
erzeugt. Dieses Modul lädt und prüft sie; es enthält keine Seitenlogik.

Grundsätze:
  * Jede Quelle hat eine unveränderliche interne ID (``Q0001``) und eine öffentliche Kennung
    (``thomas-cooper-2022``), die als Sprungmarke dient.
  * Im öffentlichen Verzeichnis stehen nur Felder aus ``FELDER_QUELLE`` (Positivliste). Interne Prüfdaten
    gibt es hier nicht.
  * Alte Sprungmarken der früheren Quellenseite (``#ref-15``, ``#station-kritik``) bleiben über
    ``alte_anker`` erreichbar.
"""
import json
from functools import lru_cache
from pathlib import Path

PFAD = Path(__file__).resolve().parent / "daten" / "quellen.json"
SPRACHEN = ("de", "en", "nl", "fr", "es")

FELDER_QUELLE = frozenset({
    "id", "kennung", "alte_kennungen", "art", "status", "version", "autoren", "jahr", "jahr_druck", "jahr_online",
    "titel", "korrekturen", "erschienen_in", "doi", "url", "pmid", "pmcid", "arxiv", "isbn", "zugang", "zugang_link",
    "themen", "forschungsfragen", "beziehungen", "schlagworte", "texte", "im_chatbot", "aufgenommen", "freigegeben",
})
FELDER_AUTOR = frozenset({"nachname", "vorname", "initialen", "organisation"})
FELDER_ERSCHIENEN = frozenset({"zeitschrift", "band", "heft", "seiten", "verlag", "server", "sendung", "angabe"})
FELDER_BEZIEHUNG = frozenset({"typ", "ziel"})
FELDER_KORREKTUR = frozenset({"doi", "art"})
FELDER_OBEN = frozenset({"_hinweis", "stand", "quellen", "seiten", "aenderungen", "alte_anker"})

ARTEN = frozenset({"primaerstudie", "review", "systematische-uebersicht", "metaanalyse", "kommentar", "meinungsbeitrag",
                   "perspective", "editorial", "preprint", "buch", "vortrag-gespraech", "journalismus", "projekt"})
STATUS = frozenset({"veroeffentlicht", "preprint", "korrigiert", "zurueckgezogen"})
ZUGANG = frozenset({"verlag_frei", "autorenfassung_frei", "nur_abstract", "frei_abrufbar", "im_handel", "ungeprueft"})
THEMEN = frozenset({"leben-im-boden", "netzwerke", "elektrische-aktivitaet", "wie-wir-forschen", "weiterlesen"})
# Farbklasse des Einordnungs-Kennzeichens auf der Quellenseite (page-quellennachweise.css: p, r, c, b, pre, pop)
BADGE_KLASSE = {"primaerstudie": "p", "review": "r", "systematische-uebersicht": "r", "metaanalyse": "r",
                "kommentar": "c", "meinungsbeitrag": "c", "perspective": "c", "editorial": "c", "preprint": "pre",
                "buch": "pop", "vortrag-gespraech": "pop", "journalismus": "pop", "projekt": "b"}
BEZIEHUNGSTYPEN = frozenset({"kommentiert", "erwidert_auf", "korrigiert", "neue_fassung_von", "nimmt_bezug_auf",
                             "thematisch_verwandt"})


@lru_cache(maxsize=1)
def laden():
    """Verzeichnis einmal laden (unveränderlich während der Laufzeit)."""
    with open(PFAD, encoding="utf-8") as f:
        return json.load(f)


def quellen():
    return laden()["quellen"]


def nach_kennung(kennung):
    return next((q for q in quellen() if q["kennung"] == kennung), None)


def nach_id(qid):
    return next((q for q in quellen() if q["id"] == qid), None)


def rueckbeziehungen(qid):
    """Beziehungen, die auf diese Quelle zeigen (z. B. Kommentare zu ihr): Liste (typ, quelle)."""
    return [(b["typ"], q) for q in quellen() for b in q.get("beziehungen", []) if b["ziel"] == qid]


# ------------------------------------------------------------------ Anzeige
def autoren_anzeige(q):
    """Nachnamen in Originalschreibweise: bis 6 Autoren alle, sonst „Erstautor et al.“."""
    namen = [a.get("nachname") or a.get("organisation") for a in q.get("autoren", [])]
    namen = [n for n in namen if n]
    if not namen:
        return ""
    if len(namen) > 6:
        return f"{namen[0]} et al."
    return namen[0] if len(namen) == 1 else ", ".join(namen[:-1]) + " & " + namen[-1]


def erschienen_anzeige(q):
    e = q.get("erschienen_in", {})
    if "angabe" in e:
        return e["angabe"]
    if "zeitschrift" in e:
        teil = e["zeitschrift"]
        if e.get("band"):
            teil += f" {e['band']}" + (f"({e['heft']})" if e.get("heft") else "")
        if e.get("seiten"):
            teil += f", {e['seiten']}"
        return teil
    return e.get("verlag") or e.get("sendung") or e.get("server") or ""


def meta_anzeige(q):
    """Bibliografische Zeile ohne Titel, z. B. „Thomas & Cooper (2022) · Plant Signaling & Behavior 17(1), 2129291 · DOI …“."""
    teile = [f"{autoren_anzeige(q)}" + (f" ({q['jahr']})" if q.get("jahr") else "")]
    if erschienen_anzeige(q):
        teile.append(erschienen_anzeige(q))
    if q.get("version"):
        teile.append(q["version"])
    if q.get("doi"):
        teile.append(f"DOI {q['doi']}")
    elif q.get("arxiv"):
        teile.append(f"arXiv:{q['arxiv']}")
    elif q.get("isbn"):
        teile.append(f"ISBN {q['isbn']}")
    return " · ".join(t for t in teile if t)


def link(q):
    if q.get("doi"):
        return f"https://doi.org/{q['doi']}"
    if q.get("arxiv"):
        return f"https://arxiv.org/abs/{q['arxiv']}"
    return q.get("url") or q.get("zugang_link")


def text(q, feld, lang):
    """Beschreibung in der gewünschten Sprache (Deutsch als Rückfall)."""
    t = q.get("texte", {}).get(feld) or {}
    return t.get(lang) or t.get("de") or ""


def chatbot_abschnitte(lang, bezeichnung):
    """Wissensabschnitte für Chatbot und /llms.txt: je Thema eine Liste von Absätzen, eine Quelle je Absatz.
    ``bezeichnung(key)`` liefert übersetzte Bezeichnungen (Publikationsart). Nur Quellen mit ``im_chatbot``."""
    ergebnis = {}
    for q in sorted(quellen(), key=lambda x: (autoren_anzeige(x).lower(), x.get("jahr") or 0)):
        if not q.get("im_chatbot"):
            continue
        absatz = f"{q['titel']} – {meta_anzeige(q)}. {bezeichnung('q_art_' + q['art'])}. {text(q, 'zeigt', lang)}"
        if q.get("texte", {}).get("heranziehen"):
            absatz += f" {bezeichnung('q_heranziehen_label')} {text(q, 'heranziehen', lang)}"
        ergebnis.setdefault(q["themen"][0], []).append(absatz)
    return ergebnis


def anker_aufloesen(anker):
    """Alte oder neue Sprungmarke -> aktuelles Ziel (Kennung oder ``thema-…``); unbekannt -> None."""
    anker = anker.lstrip("#")
    if nach_kennung(anker):
        return anker
    if anker.startswith("thema-") and anker[6:] in THEMEN:
        return anker
    return laden()["alte_anker"].get(anker)


def fehler(daten=None):
    """Prüft das Verzeichnis gegen Positivliste und erlaubte Werte. Liefert eine Liste von Fehlermeldungen."""
    d = daten or laden()
    f = []
    f += [f"unbekanntes Feld oben: {k}" for k in d if k not in FELDER_OBEN]
    ids, kennungen = set(), set()
    for q in d["quellen"]:
        k = q.get("kennung", "?")
        f += [f"{k}: unbekanntes Feld {x}" for x in q if x not in FELDER_QUELLE]
        if q["id"] in ids or k in kennungen:
            f.append(f"{k}: ID oder Kennung doppelt")
        ids.add(q["id"])
        kennungen.add(k)
        if q.get("art") not in ARTEN:
            f.append(f"{k}: Art {q.get('art')}")
        if q.get("status") not in STATUS:
            f.append(f"{k}: Status {q.get('status')}")
        if q.get("zugang") not in ZUGANG:
            f.append(f"{k}: Zugang {q.get('zugang')}")
        f += [f"{k}: Thema {t}" for t in q.get("themen", []) if t not in THEMEN]
        f += [f"{k}: Autorfeld {x}" for a in q.get("autoren", []) for x in a if x not in FELDER_AUTOR]
        f += [f"{k}: Erscheinungsfeld {x}" for x in q.get("erschienen_in", {}) if x not in FELDER_ERSCHIENEN]
        f += [f"{k}: Korrekturfeld {x}" for kk in q.get("korrekturen", []) for x in kk if x not in FELDER_KORREKTUR]
        for b in q.get("beziehungen", []):
            f += [f"{k}: Beziehungsfeld {x}" for x in b if x not in FELDER_BEZIEHUNG]
            if b.get("typ") not in BEZIEHUNGSTYPEN:
                f.append(f"{k}: Beziehungstyp {b.get('typ')}")
        texte = q.get("texte", {})
        f += [f"{k}: Textfeld {x}" for x in texte if x not in ("zeigt", "heranziehen")]
        for feld in ("zeigt", "heranziehen"):
            if feld in texte and set(texte[feld]) != set(SPRACHEN):
                f.append(f"{k}: {feld} nicht genau in den 5 Sprachen")
        if "zeigt" not in texte:
            f.append(f"{k}: Beschreibung fehlt")
    for q in d["quellen"]:
        f += [f"{q['kennung']}: Beziehungsziel {b['ziel']} fehlt" for b in q.get("beziehungen", []) if b["ziel"] not in ids]
    f += [f"Zitierliste {s}: {i} fehlt" for s, ls in d.get("seiten", {}).items() for i in ls if i not in ids]
    f += [f"alter Anker {a} -> {z} fehlt" for a, z in d.get("alte_anker", {}).items()
          if z not in kennungen and not (z.startswith("thema-") and z[6:] in THEMEN)]
    return f
