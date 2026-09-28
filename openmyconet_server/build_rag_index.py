"""
build_rag_index.py -- Baut die Wissensbasis des RAG-Chatbots neu auf.

Hintergrund: Die Chunk-Liste in rag_chatbot.py war urspruenglich ein
handkuratierter Schnappschuss aus translations.js. Sie wurde von nichts
automatisch aktualisiert und ist mit dem Ausbau der Website (BioComm-Seiten,
Methodik, Mykorrhiza-Wissensseiten, Quellennachweise, Leihgeraet, Medien ...)
immer weiter veraltet.

Dieses Skript erzeugt `rag_chunks.json` aus den echten Textquellen:
  * app/static/translations.json  -- thematisch zu Chunks gebuendelt
  * News-Tabelle (falls DB erreichbar)  -- je Meldung ein eigener Chunk

rag_chatbot.py laedt `rag_chunks.json` beim Import; fehlt die Datei, faellt
es auf die eingebaute _FALLBACK_CHUNKS-Liste zurueck.

Aufruf:  venv/Scripts/python.exe build_rag_index.py
Sicher mehrfach ausfuehrbar -- schreibt die Datei jedes Mal komplett neu.
Nach Textaenderungen an translations.json bzw. neuen News erneut ausfuehren
(lokal generieren + per scp hochladen, oder direkt auf dem Server laufen
lassen, damit die News mitgezogen werden).
"""
import json
import os

from omn.wissensbasis import GROUPS, abschnitte, clean

BASE = os.path.dirname(__file__)
TRANSLATIONS_PATH = os.path.join(BASE, "app", "static", "translations.json")
OUT_PATH = os.path.join(BASE, "rag_chunks.json")

LANGS = ["de", "en", "nl", "fr", "es"]
MAX_CHARS = 4000  # pro Chunk -- haelt den zusammengesetzten Kontext handhabbar

# Themengruppen, Textbereinigung: omn/wissensbasis.py (gemeinsam mit /llms.txt).


def build_from_translations():
    with open(TRANSLATIONS_PATH, encoding="utf-8") as f:
        tr = json.load(f)

    chunks = []
    cid = 0
    for lang in LANGS:
        for slug, titel, texts in abschnitte(tr, lang):
            body = " ".join(texts)
            if len(body) > MAX_CHARS:
                body = body[:MAX_CHARS].rsplit(" ", 1)[0] + " …"
            cid += 1
            chunks.append({
                "id": cid,
                "lang": lang,
                "slug": slug,
                "title": titel,
                "text": body,
            })
    return chunks


def build_from_news(start_id):
    """News-Meldungen als eigene Chunks -- nur wenn die DB erreichbar ist."""
    try:
        from omn import create_app
        app = create_app()
        from omn.models import News
    except Exception as e:  # pragma: no cover - nur ausserhalb App-Umgebung
        print(f"  News uebersprungen (Import fehlgeschlagen: {e})")
        return []

    chunks = []
    cid = start_id
    try:
        with app.app_context():
            rows = News.query.order_by(News.veroeffentlicht.desc()).all()
            for n in rows:
                lang = (n.sprache or "de").lower()
                if lang not in LANGS:
                    lang = "de"
                body = clean(" ".join(filter(None, [n.untertitel, n.inhalt])))
                if not body:
                    continue
                if len(body) > MAX_CHARS:
                    body = body[:MAX_CHARS].rsplit(" ", 1)[0] + " …"
                datum = n.veroeffentlicht.strftime("%Y-%m-%d") if n.veroeffentlicht else ""
                cid += 1
                chunks.append({
                    "id": cid,
                    "lang": lang,
                    "slug": "news",
                    "title": f"News ({datum}): {n.titel}".strip(),
                    "text": body,
                })
    except Exception as e:  # pragma: no cover
        print(f"  News uebersprungen (DB-Fehler: {e})")
        return []
    return chunks


def main():
    print("Baue RAG-Wissensbasis ...")
    chunks = build_from_translations()
    print(f"  {len(chunks)} Chunks aus translations.json "
          f"({len(GROUPS)} Themen x {len(LANGS)} Sprachen, leere weggelassen)")

    news_chunks = build_from_news(chunks[-1]["id"] if chunks else 0)
    if news_chunks:
        print(f"  {len(news_chunks)} News-Chunks")
    chunks.extend(news_chunks)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=1)
    print(f"{len(chunks)} Chunks -> {os.path.relpath(OUT_PATH, BASE)}")


if __name__ == "__main__":
    main()
