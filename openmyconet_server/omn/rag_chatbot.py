"""
rag_chatbot.py — OpenMycoNet RAG-Chatbot
Einbinden in app.py: from rag_chatbot import chatbot_bp; app.register_blueprint(chatbot_bp)
Benötigt: ANTHROPIC_API_KEY in Umgebungsvariable oder .env
"""

import os
import re
import json
import logging
from pathlib import Path
from flask import Blueprint, request, jsonify
import anthropic

from omn import ki, wissensbasis
from omn.extensions import db
from omn.models import ChatLog
from omn.spam_schutz import ip_erlaubt

logger = logging.getLogger(__name__)

# Rate-Limit fuer /api/chat: der Endpunkt loest pro Aufruf einen kostenpflichtigen
# Anthropic-API-Call aus und ist bewusst ohne Login erreichbar -- ohne Limit kann
# ein Skript beliebig viele Anfragen absetzen (API-Rechnung). 20 Anfragen pro
# Stunde und IP reichen fuer eine echte Unterhaltung locker aus.
MAX_NACHRICHT_ZEICHEN = 2000
CHAT_LIMIT = 20
CHAT_WINDOW = 3600

chatbot_bp = Blueprint("chatbot", __name__)

# ---------------------------------------------------------------------------
# Wissensbasis
#
# Primärquelle: rag_chunks.json — von build_rag_index.py aus der echten
# translations.json + der News-Tabelle generiert. Nach Textänderungen an der
# Website `python build_rag_index.py` laufen lassen und die Datei mit
# deployen (siehe Skript-Doku).
#
# Fällt die Datei weg oder ist sie defekt, bündelt der Bot die Texte direkt aus
# translations.json (gleiche Logik wie build_rag_index.py, nur ohne News).
# Bis 25.11.2026 stand hier eine eingefrorene Alt-Liste mit überholten Aussagen.
# ---------------------------------------------------------------------------

# rag_chunks.json liegt im Repo-Root (build_rag_index.py schreibt es dorthin),
# omn/rag_chatbot.py eine Ebene tiefer.
_CHUNKS_FILE = Path(__file__).resolve().parent.parent / "rag_chunks.json"
_TRANSLATIONS_FILE = Path(__file__).resolve().parent.parent / "app" / "static" / "translations.json"


def _fallback_chunks() -> list[dict]:
    """Notfall-Wissen: aktuelle Website-Texte, live aus translations.json gebündelt."""
    try:
        return wissensbasis.chunks(json.loads(_TRANSLATIONS_FILE.read_text(encoding="utf-8")))
    except Exception as e:
        logger.error("Notfall-Wissen aus %s nicht ladbar (%s)", _TRANSLATIONS_FILE.name, e)
        return []


def _load_chunks() -> list[dict]:
    """rag_chunks.json laden; bei Fehler auf die Texte aus translations.json zurückfallen."""
    try:
        data = json.loads(_CHUNKS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            logger.info("RAG-Wissensbasis: %d Chunks aus %s", len(data), _CHUNKS_FILE.name)
            return data
        logger.warning("%s ist leer/ungültig — nutze translations.json", _CHUNKS_FILE.name)
    except FileNotFoundError:
        logger.warning("%s fehlt — nutze translations.json (ohne News)", _CHUNKS_FILE.name)
    except Exception as e:
        logger.error("%s konnte nicht geladen werden (%s) — nutze translations.json", _CHUNKS_FILE.name, e)
    return _fallback_chunks()


CHUNKS = _load_chunks()

# ---------------------------------------------------------------------------
# Spracherkennung
# ---------------------------------------------------------------------------

LANG_PATTERNS = {
    "de": re.compile(r"\b(ist|sind|was|wie|wann|kann|ich|das|die|der|ein|und|für|bitte|gibt|werden|haben|welche|knoten|gerät|mitmachen|verfügbar|zeitplan|spenden|datenschutz|pilz|mykorrhiza)\b"),
    "en": re.compile(r"\b(is|are|what|when|how|can|the|and|for|does|will|have|which|node|device|join|available|timeline|donate|privacy|fungal|mycorrhiza)\b"),
    "nl": re.compile(r"\b(is|zijn|wat|hoe|wanneer|kan|het|de|en|voor|heeft|welke|knooppunt|meedoen|beschikbaar|doneren)\b"),
    "fr": re.compile(r"\b(est|sont|quoi|comment|quand|peut|le|la|les|et|pour|avez|quel|nœud|disponible|donner|champignon)\b"),
    "es": re.compile(r"\b(es|son|qué|cómo|cuándo|puede|el|la|los|y|para|tiene|cuál|nodo|disponible|donar|hongo)\b"),
}

def detect_language(text: str) -> str:
    """Erkennt Sprache anhand von Schlüsselwörtern; Fallback: de."""
    t = text.lower()
    scores = {lang: len(pat.findall(t)) for lang, pat in LANG_PATTERNS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "de"


# ---------------------------------------------------------------------------
# Chunk-Retrieval (keyword-basiert)
# ---------------------------------------------------------------------------

SYNONYMS = {
    # DE
    "verfügbar": ["hardware", "zeitplan", "verfügbar", "gerät", "knoten", "wann", "lieferung", "pcb", "prototyp"],
    "gerät":     ["hardware", "zeitplan", "verfügbar", "gerät", "knoten", "lieferung", "pcb", "prototyp"],
    "mitmachen": ["mitmachen", "knoten", "hardware", "schritt", "elektrode", "betreiben", "teilnehmen"],
    "datenschutz": ["datenschutz", "gps", "daten", "privat", "anonym"],
    "spenden": ["spenden", "unterstütz", "förder", "finanzier"],
    "anwendung": ["anwendung", "landwirtschaft", "wald", "klima", "forschung", "einsatz"],
    "förderer": ["förderer", "kooperation", "sponsor", "unterstütz", "beitrag", "jahresbeitrag", "partner", "logo", "kategorie", "paypal", "gegenleistung", "firma", "unternehmen"],
    "kooperation": ["förderer", "kooperation", "sponsor", "unterstütz", "beitrag", "jahresbeitrag", "partner", "logo", "kategorie", "paypal", "gegenleistung", "firma", "unternehmen"],
    "methodik": ["methodik", "feldforschung", "labor", "mycelist", "hyphist", "sporist", "knotenbetreiber", "sorgfalt", "unabhängig", "wissenschaftlich", "arbeiten"],
    "feldforschung": ["methodik", "feldforschung", "labor", "mycelist", "hyphist", "sporist", "knotenbetreiber", "sorgfalt", "unabhängig", "wissenschaftlich"],
    "mycelist": ["methodik", "mycelist", "hyphist", "sporist", "mitglied", "rolle", "knotenbetreiber"],
    "gegründet": ["gegründet", "initiiert", "robert jank", "erfinder", "maintal", "unabhängig"],
    "gründer": ["gegründet", "initiiert", "robert jank", "erfinder", "maintal", "team", "founder"],
    "erfinder": ["erfinder", "inventor", "robert jank", "initiiert", "gebrauchsmuster", "dpma", "maintal"],
    "founded": ["founded", "initiated", "robert jank", "inventor", "maintal", "independent"],
    "founder": ["founded", "initiated", "robert jank", "inventor", "maintal", "team"],
    # DE+EN zusammengefuehrt: dieselben Keys standen frueher doppelt im Dict
    # (einmal im DE-, einmal im EN-Block) -- der zweite Eintrag ueberschrieb den
    # ersten stillschweigend, sodass DE-Anfragen die EN-Synonyme bekamen und
    # umgekehrt Synonyme verloren gingen. expand_keywords() ist ohnehin
    # sprachunabhaengig (iteriert alle Keys), daher hier bewusst die Vereinigung.
    "software": ["software", "simulation", "testbetrieb", "test", "closed loop", "implementiert", "implemented", "biocomm", "live-monitor", "monitor", "entwicklungsstatus", "development status"],
    "hardware": ["hardware", "biocomm", "esp32", "lora", "bridge", "knoten", "node", "sonde", "probe", "gehäuse", "enclosure", "überarbeitung", "revision", "prototyp", "prototype", "entwicklungsstatus", "development status"],
    "biocomm": ["biocomm", "messung", "stimulation", "plattform", "software", "hardware", "kanäle", "elektrode"],
    "stimulation": ["stimulation", "reiz", "stimulus", "elektrisch", "electrical", "optisch", "optical", "bidirektional", "bidirectional", "amplitude", "frequenz", "frequency"],
    "entwicklungsstand": ["entwicklungsstand", "entwicklungsstatus", "status", "überarbeitung", "geplant", "vorbereitung", "abgeschlossen", "fertigung", "implementiert", "ausstehend"],
    "entwicklung": ["entwicklung", "entwicklungsstatus", "status", "überarbeitung", "geplant", "vorbereitung", "abgeschlossen"],
    "leihgerät": ["leihgerät", "leihprogramm", "pfand", "kaution", "rückgabe", "edition", "gehäuse"],
    "kosten": ["kosten", "pfand", "kaution", "beitrag", "gebühr", "preis", "euro"],
    "pfand": ["pfand", "kaution", "leihgerät", "leihprogramm", "rückgabe"],
    "messen": ["messung", "kanäle", "bioelektrisch", "elektrode", "adc", "stimulation", "sonde"],
    "musik": ["musik", "song", "broschüre", "buch", "roman", "medien", "ki-generiert"],
    # EN
    "available": ["hardware", "timeline", "available", "device", "node", "when", "delivery"],
    "join": ["join", "node", "hardware", "step", "electrode", "operate", "participate"],
    "privacy": ["privacy", "gps", "data", "personal", "anonymous"],
    "donate": ["donate", "support", "fund", "financ"],
    "application": ["application", "agriculture", "forest", "climate", "research", "use"],
    "supporter": ["supporter", "cooperation", "sponsor", "support", "contribution", "partner", "logo", "category", "paypal", "company"],
    "cooperation": ["supporter", "cooperation", "sponsor", "support", "contribution", "partner", "logo", "category", "paypal", "company"],
    "methodology": ["methodology", "fieldwork", "laboratory", "mycelist", "hyphist", "sporist", "node operator", "rigor", "independent", "scientific"],
    "fieldwork": ["methodology", "fieldwork", "laboratory", "mycelist", "hyphist", "sporist", "node operator", "rigor", "independent"],
    # "software"/"hardware"/"stimulation": siehe zusammengefuehrte Eintraege im DE-Block oben.
    "development": ["development", "status", "revision", "planned", "preparation", "complete", "pending", "implemented"],
    "deposit": ["deposit", "loan", "return", "borrow", "edition"],
    "cost": ["cost", "deposit", "loan", "contribution", "fee", "price", "euro"],
    "measure": ["measure", "measurement", "channels", "bioelectric", "electrode", "adc", "stimulation", "probe"],
    "music": ["music", "song", "brochure", "book", "novel", "media", "ai-generated"],
    # NL/FR/ES — grundlegend
    "beschikbaar": ["hardware", "tijdlijn", "knooppunt"],
    "disponible": ["hardware", "calendrier", "nœud", "nodo"],
    "sponsor": ["sponsor", "samenwerking", "partenaire", "coopération", "patrocinador", "cooperación", "beitrag", "cotisation", "cuota"],
    "samenwerking": ["sponsor", "samenwerking", "partenaire", "coopération", "patrocinador", "cooperación"],
    "partenaire": ["sponsor", "samenwerking", "partenaire", "coopération", "patrocinador", "cooperación"],
    "patrocinador": ["sponsor", "samenwerking", "partenaire", "coopération", "patrocinador", "cooperación"],
    "methodiek": ["methodiek", "veldonderzoek", "mycelist", "hyphist", "sporist", "onafhankelijk"],
    "méthodologie": ["méthodologie", "terrain", "mycelist", "hyphist", "sporist", "indépendan"],
    "metodología": ["metodología", "campo", "mycelist", "hyphist", "sporist", "independien"],
    # Mykorrhiza/Kohlenstoff: "mycorrhiza" (lat./engl. Schreibweise mit c) matcht
    # sonst nicht die deutschen Chunks (durchgängig "mykorrhiza" mit y) -- ohne
    # dieses Synonym landet z.B. "Studien zu Mycorrhiza und CO2" nicht im
    # richtigen Chunk. "co2" selbst ist zu kurz fuer die Wortfilterung
    # (len > 3) und wird vor expand_keywords per _normalize_query() auf
    # "kohlenstoff" abgebildet -- der Synonym-Eintrag deckt daher zusaetzlich
    # den direkten cross-lingualen Fall ab (z.B. "carbon" in einer sonst
    # deutschen Anfrage).
    "mycorrhiza": ["mycorrhiza", "mykorrhiza"],
    "kohlenstoff": ["kohlenstoff", "carbon", "koolstof", "carbone", "carbono"],
}

# Kurzabkuerzungen, die als eigenstaendiges Wort nie die Mindestlaenge fuer
# die Wortfilterung in find_chunks() erreichen (len > 3) und daher vor der
# Tokenisierung textuell aufgeloest werden muessen, statt ueber SYNONYMS.
_ABBREV_RE = re.compile(r"\bco2\b|\bco₂\b")


def _normalize_query(text: str) -> str:
    return _ABBREV_RE.sub("kohlenstoff", text)

def expand_keywords(words: list[str]) -> list[str]:
    expanded = list(words)
    for w in words:
        for key, syns in SYNONYMS.items():
            # Nur "key in w" (Query-Wort ist eine Erweiterung/Flexion des Keys,
            # z.B. "verfügbarkeit" enthält "verfügbar") -- NICHT umgekehrt
            # "w in key". Die umgekehrte Richtung liess kurze, generische
            # Woerter matchen, die rein zufaellig als Textfragment in einem
            # laengeren, thematisch unverwandten Key stecken -- z.B. "daten"
            # in "datenschutz" (jede Frage zu Messdaten loeste dadurch den
            # Datenschutz/GPS/anonym-Synonymblock aus) oder "operation" in
            # "kooperation". Dokumentierte Ranking-Schwaeche, siehe
            # Website_Status.md.
            if key in w:
                expanded.extend(syns)
    # Duplikate entfernen: mehrere Query-Woerter koennen denselben Synonym-
    # Eintrag treffen (z.B. "förderer" + "kooperation" liefern identische
    # Listen) -- ohne Dedupe wuerden solche Treffer im Score doppelt zaehlen
    # und die Rangfolge zusaetzlich verzerren.
    return list(dict.fromkeys(expanded))

def find_chunks(query: str, lang: str, top_k: int = 3) -> list[dict]:
    """Gibt die relevantesten Chunks für Sprache und Query zurück."""
    words = [w for w in _normalize_query(query.lower()).split() if len(w) > 3]
    expanded = expand_keywords(words)

    lang_chunks = [c for c in CHUNKS if c["lang"] == lang]

    scored = []
    for c in lang_chunks:
        haystack = (c["text"] + " " + c["title"]).lower()
        score = sum(1 for w in expanded if w in haystack)
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    best = [c for s, c in scored if s > 0][:top_k]
    return best if best else [c for _, c in scored[:2]]


# ---------------------------------------------------------------------------
# System-Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPTS = {
    "de": "Du bist der offizielle Assistent von OpenMycoNet. Beantworte Fragen ausschließlich auf Basis des folgenden Kontexts. Sei ehrlich wenn etwas noch nicht bekannt ist oder noch in Entwicklung ist. Erfinde keine Informationen. Antworte auf Deutsch.\n\nKontext:\n\n{context}",
    "en": "You are the official OpenMycoNet assistant. Answer questions only based on the context below. Be honest if something is unknown or still in development. Do not invent information. Answer in English.\n\nContext:\n\n{context}",
    "nl": "Je bent de officiële OpenMycoNet-assistent. Beantwoord vragen uitsluitend op basis van de onderstaande context. Wees eerlijk als iets nog niet bekend is. Verzin geen informatie. Antwoord in het Nederlands.\n\nContext:\n\n{context}",
    "fr": "Tu es l'assistant officiel d'OpenMycoNet. Réponds aux questions uniquement sur la base du contexte ci-dessous. Sois honnête si quelque chose est inconnu. N'invente pas d'informations. Réponds en français.\n\nContexte:\n\n{context}",
    "es": "Eres el asistente oficial de OpenMycoNet. Responde preguntas únicamente basándote en el contexto siguiente. Sé honesto si algo es desconocido. No inventes información. Responde en español.\n\nContexto:\n\n{context}",
}


# ---------------------------------------------------------------------------
# Flask-Endpunkt
# ---------------------------------------------------------------------------

@chatbot_bp.route("/api/chat", methods=["POST"])
def chat():
    """
    Erwartet JSON:
        { "message": "...", "history": [ {"role": "user"|"assistant", "content": "..."}, ... ] }
    Gibt zurück:
        { "answer": "...", "chunks_used": ["Titel 1", ...], "lang": "de" }
    """
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Ungültiges JSON"}), 400
    if not isinstance(data, dict):
        return jsonify({"error": "Ungültiges JSON"}), 400

    message = data.get("message")
    message = message.strip() if isinstance(message, str) else ""
    history = data.get("history")
    if not isinstance(history, list):
        history = []

    if not message:
        return jsonify({"error": "Kein Text übermittelt"}), 400
    # Jeder Aufruf kostet API-Geld: ohne Grenzen koennte ein Request mit mehreren
    # MB Text (bis MAX_CONTENT_LENGTH) ein Vielfaches eines normalen Aufrufs kosten.
    if len(message) > MAX_NACHRICHT_ZEICHEN:
        return jsonify({"error": f"Nachricht zu lang (höchstens {MAX_NACHRICHT_ZEICHEN} Zeichen)."}), 400

    if not ip_erlaubt(request.remote_addr, "chat", limit=CHAT_LIMIT, window=CHAT_WINDOW):
        return jsonify({"error": "Zu viele Anfragen — bitte in einer Stunde erneut versuchen."}), 429

    # Sprache erkennen
    lang = detect_language(message)

    # Chunks suchen
    chunks = find_chunks(message, lang)
    context = "\n\n".join(f"[{c['title']}]\n{c['text']}" for c in chunks)
    chunk_titles = [c["title"] for c in chunks]

    # System-Prompt aufbauen
    system = SYSTEM_PROMPTS.get(lang, SYSTEM_PROMPTS["de"]).format(context=context)

    # Gesprächsverlauf bereinigen (max. 10 Turns, nur user/assistant)
    clean_history = [
        {"role": m["role"], "content": m["content"][:MAX_NACHRICHT_ZEICHEN]}
        for m in history[-10:]
        if isinstance(m, dict) and m.get("role") in ("user", "assistant")
        and isinstance(m.get("content"), str) and m["content"]
    ]
    clean_history.append({"role": "user", "content": message})

    # Anthropic-API-Call
    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = client.messages.create(
            model=ki.MODELL,
            max_tokens=1300,   # Sonnet-5-Tokenizer zaehlt ~30 % mehr Tokens als 4.6 (vorher 1000)
            thinking=ki.DENKEN_AUS,
            system=system,
            messages=clean_history,
        )
        answer = ki.antwort_text(response)
    except KeyError:
        logger.error("ANTHROPIC_API_KEY nicht gesetzt")
        return jsonify({"error": "API-Key fehlt (ANTHROPIC_API_KEY nicht konfiguriert)"}), 500
    except (anthropic.APIError, ki.KeineAntwort) as e:
        # Details nur ins Log, nicht an den Besucher (koennen Konto-/Modelldaten enthalten).
        logger.error("Anthropic API-Fehler: %s", e)
        return jsonify({"error": "Der Assistent ist gerade nicht erreichbar — bitte später erneut versuchen."}), 502

    try:
        db.session.add(ChatLog(
            message=message,
            answer=answer,
            lang=lang,
            chunks_used=", ".join(chunk_titles),
        ))
        db.session.commit()
    except Exception as e:
        logger.error("Chat-Log konnte nicht gespeichert werden: %s", e)
        db.session.rollback()

    return jsonify({
        "answer": answer,
        "chunks_used": chunk_titles,
        "lang": lang,
    })
