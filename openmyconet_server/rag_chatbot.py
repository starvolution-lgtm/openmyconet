"""
rag_chatbot.py — OpenMycoNet RAG-Chatbot
Einbinden in app.py: from rag_chatbot import chatbot_bp; app.register_blueprint(chatbot_bp)
Benötigt: ANTHROPIC_API_KEY in Umgebungsvariable oder .env
"""

import os
import re
import json
import logging
from flask import Blueprint, request, jsonify
import anthropic

logger = logging.getLogger(__name__)

chatbot_bp = Blueprint("chatbot", __name__)

# ---------------------------------------------------------------------------
# Wissensbasis — aus translations.js extrahiert + manueller Zeitplan-Chunk
# ---------------------------------------------------------------------------

CHUNKS = [
  {"id":1,"lang":"de","title":"Vision & Warum","text":"Unter unseren Füßen liegt das älteste und weitreichendste Kommunikationsnetzwerk der Erde. Mykorrhiza-Pilze verbinden seit 400 Millionen Jahren nahezu alle Landpflanzen miteinander — sie transportieren Nährstoffe, übermitteln Warnsignale und koordinieren das Leben im Boden auf eine Weise die wir gerade erst zu verstehen beginnen. Sie senden elektrische Signale. Messbar. Reproduzierbar. Und bisher kaum entschlüsselt. OpenMycoNet stellt die einfache aber weitreichende Frage: Was passiert wenn wir aufhören, Böden nur von außen zu analysieren — und stattdessen anfangen zuzuhören was das Netzwerk selbst sendet? Das Netzwerk sendet. Wir haben gerade erst angefangen zuzuhören. Jeder BioComm-Knoten der weltweit in Betrieb geht bringt uns einen Schritt näher an das Verständnis — für alle."},
  {"id":2,"lang":"de","title":"Über das Projekt","text":"OpenMycoNet wurde von Robert Jank, unabhängigem Erfinder aus Maintal bei Frankfurt, initiiert — ohne Institutszugehörigkeit, mit dem Ziel zu verstehen was Mykorrhiza-Netzwerke elektrisch signalisieren. Das zugrundeliegende System BioComm ist durch ein Gebrauchsmuster beim DPMA geschützt. Die Software wird als portable .exe bereitgestellt. Die Messdaten gehören der Gemeinschaft. Prinzip: Proprietary Intelligence, Open Data — das KI-Modell ist geschützt, die Daten die es trainieren sind frei."},
  {"id":3,"lang":"de","title":"Mitmachen & Knoten betreiben","text":"Hardware leihen: BioComm-Messgerät als Leihgerät erhalten — Pfand ca. 100 € (finale Kosten folgen). Rückgabe jederzeit möglich. BioComm herunterladen: Die BioComm-Software kostenlos herunterladen — keine Installation, kein Python nötig. Elektroden setzen: Nadeln in Boden, Blumentopf oder Kompost mit Pilz- oder Mykorrhiza-Substrat. Messen & teilen: BioComm verbindet automatisch und lädt die Daten hoch. Analyse und Anonymisierung erfolgen lokal auf deinem Gerät — keine Rohdaten verlassen deinen PC."},
  {"id":4,"lang":"de","title":"Datenschutz & Transparenz","text":"GPS-Koordinaten werden auf 10×10 km vergröbert — kein exakter Standort. Keine personenbezogenen Daten. Alle Rohdaten öffentlich zugänglich unter Creative Commons CC BY 4.0."},
  {"id":5,"lang":"de","title":"Unterstützung & Spenden","text":"OpenMycoNet ist ein unabhängiges Citizen-Science-Projekt ohne institutionelle Förderung. Serverkosten und Weiterentwicklung werden durch freiwillige Spenden finanziert. Jeder Betrag hilft. Wir für OpenMycoNet — OpenMycoNet für alle."},
  {"id":6,"lang":"de","title":"Anwendungsfelder","text":"Präzisionslandwirtschaft: Wenn wir die Signalmuster von Trockenstress, Nährstoffmangel und Schädlingsbefall kennen, können Landwirte reagieren bevor Schäden entstehen — ohne Chemie, ohne Flächenpauschalen. Waldschutz: Veränderungen in den Signalmustern könnten Trockenheit, Borkenkäferbefall oder Brandgefahr anzeigen — Wochen bevor es sichtbar wird. Bodenregeneration: Durch gezielte Frequenzstimulation lässt sich die Aktivität von Mykorrhiza-Netzwerken beeinflussen. Klimaschutz: Gesunde Mykorrhiza-Netzwerke binden nachweislich CO₂. BioComm könnte als unabhängiges Monitoring-Instrument für Boden-Carbon-Zertifikate dienen. Grundlagenforschung: Adamatzky et al. haben gezeigt dass Pilz-Spike-Trains strukturelle Ähnlichkeiten mit menschlichen Sprachen aufweisen."},
  {"id":7,"lang":"de","title":"Fakten & Zahlen","text":"400 Millionen Jahre: so lange existieren Mykorrhiza-Netzwerke auf der Erde. 90% aller Landpflanzen sind mit Mykorrhiza-Pilzen verbunden. 8 Messkanäle erfasst BioComm gleichzeitig, bis zu 10.000 Hz. Ca. 100 € Pfandgebühr für ein BioComm-Leihgerät (finale Kosten folgen)."},
  {"id":8,"lang":"de","title":"Hardware-Verfügbarkeit & Zeitplan","text":"Die ersten BioComm-Prototypen befinden sich aktuell in der PCB-Fertigungsphase. Die Platinen werden produziert, anschließend folgen Aufbau und Validierung der ersten Knoten in 3D-gedruckten IP65-Gehäusen. Ein konkretes Datum für die erste Verfügbarkeit kann noch nicht genannt werden. Das Leihgerät-Modell ist geplant mit einem Pfand von ca. 100 € — finale Kosten folgen. Interessenten können sich bereits jetzt auf der Website registrieren, um frühzeitig benachrichtigt zu werden."},
  {"id":9,"lang":"en","title":"Vision & Why","text":"Beneath our feet lies the oldest and most extensive communication network on Earth. Mycorrhizal fungi have connected almost all land plants for 400 million years — transporting nutrients, transmitting warning signals, and coordinating life in the soil in ways we are only beginning to understand. They send electrical signals. Measurable. Reproducible. And barely deciphered so far. OpenMycoNet asks: what happens when we stop analysing soil only from the outside and start listening to what the network itself is sending? The network is transmitting. We have only just begun to listen."},
  {"id":10,"lang":"en","title":"About the Project","text":"OpenMycoNet was initiated by Robert Jank, independent inventor from Maintal near Frankfurt — without institutional affiliation, with the goal of understanding what mycorrhizal networks signal electrically. The underlying BioComm system is protected by a utility model registered with the DPMA. The software is provided as a portable .exe. The measurement data belongs to the community. Principle: Proprietary Intelligence, Open Data — the AI model is protected, the data that trains it is free."},
  {"id":11,"lang":"en","title":"Join & operate a node","text":"Borrow hardware: Receive a BioComm measuring device on loan — deposit approx. €100 (final costs to follow). Return at any time. Download BioComm software for free — no installation, no Python required. Place electrodes into soil, plant pot or compost with fungal or mycorrhizal substrate. BioComm connects automatically and uploads the data. Analysis and anonymisation are performed locally on your device — no raw data ever leaves your PC."},
  {"id":12,"lang":"en","title":"Privacy & Transparency","text":"GPS coordinates are coarsened to 10×10 km — no exact location. No personal data. All raw data publicly accessible under Creative Commons CC BY 4.0."},
  {"id":13,"lang":"en","title":"Support & Donations","text":"OpenMycoNet is an independent citizen science project without institutional funding. Server costs and further development are financed by voluntary donations. Every contribution helps. We support OpenMycoNet — OpenMycoNet supports everyone."},
  {"id":14,"lang":"en","title":"Applications","text":"Precision agriculture: farmers can respond before damage occurs — without chemicals, without blanket treatments. Forest protection: changes in signal patterns could indicate drought, bark beetle infestation or fire risk — weeks before it becomes visible. Soil regeneration: targeted frequency stimulation can influence mycorrhizal network activity. Climate protection: healthy mycorrhizal networks demonstrably sequester CO₂. Fundamental research: Adamatzky et al. have shown that fungal spike trains have structural similarities to human languages."},
  {"id":15,"lang":"en","title":"Facts & Numbers","text":"400 million years: mycorrhizal networks have existed on Earth. 90% of all land plants are connected to mycorrhizal fungi. 8 channels recorded simultaneously by BioComm, up to 10,000 Hz. Approx. €100 deposit for a BioComm loan device (final costs to follow)."},
  {"id":16,"lang":"en","title":"Hardware availability & timeline","text":"The first BioComm prototypes are currently in the PCB manufacturing phase. The boards are being produced, followed by assembly and validation of the first nodes in 3D-printed IP65 enclosures. A specific availability date cannot be given yet. The loan device model is planned with a deposit of approx. €100 — final costs to follow. Interested parties can already register on the website to be notified early."},
  {"id":17,"lang":"nl","title":"Visie & Waarom","text":"Onder onze voeten ligt het oudste communicatienetwerk van de aarde. Mycorrhizaschimmels verbinden al 400 miljoen jaar vrijwel alle landplanten. Ze zenden elektrische signalen. Meetbaar. Reproduceerbaar. OpenMycoNet vraagt: wat gebeurt er als we ophouden bodems alleen van buitenaf te analyseren? Het netwerk zendt. We zijn er nog maar net mee begonnen te luisteren."},
  {"id":18,"lang":"nl","title":"Over het project","text":"OpenMycoNet werd geïnitieerd door Robert Jank, onafhankelijk uitvinder uit Maintal bij Frankfurt. Het BioComm-systeem is beschermd door een gebruiksmodel bij het DPMA. De software wordt aangeboden als draagbare .exe. De meetgegevens zijn eigendom van de gemeenschap. Principe: Proprietary Intelligence, Open Data."},
  {"id":19,"lang":"nl","title":"Meedoen & knooppunt beheren","text":"Hardware lenen: BioComm-meetapparaat als leentoestel — borg ca. €100 (definitieve kosten volgen). BioComm downloaden: gratis, geen installatie nodig. Elektroden plaatsen in bodem of bloempot met schimmelsubstraat. BioComm maakt automatisch verbinding — geen ruwe data verlaat je pc."},
  {"id":20,"lang":"nl","title":"Privacy & Transparantie","text":"GPS-coördinaten worden vergroot naar 10×10 km — geen exacte locatie. Geen persoonsgegevens. Alle ruwe data openbaar toegankelijk onder Creative Commons CC BY 4.0."},
  {"id":21,"lang":"nl","title":"Ondersteuning & Donaties","text":"OpenMycoNet is een onafhankelijk citizen science-project zonder institutionele financiering. Serverkosten worden gefinancierd door vrijwillige donaties. Elk bedrag helpt."},
  {"id":22,"lang":"nl","title":"Toepassingen","text":"Precisielandbouw: reageren voordat schade ontstaat. Bosbescherming: signaalveranderingen kunnen droogte of plaagaantasting signaleren weken voordat het zichtbaar wordt. Bodemregeneratie via frequentiestimulatie. Klimaatbescherming: mycorrhizanetwerken binden CO₂. Fundamenteel onderzoek naar schimmelsignalen."},
  {"id":23,"lang":"nl","title":"Feiten & Cijfers","text":"400 miljoen jaar oud. 90% van alle landplanten verbonden met mycorrhizaschimmels. 8 kanalen tegelijk, tot 10.000 Hz. Borg ca. €100 (definitief te bevestigen)."},
  {"id":24,"lang":"nl","title":"Hardware-beschikbaarheid & tijdlijn","text":"De eerste BioComm-prototypes bevinden zich in de PCB-fabricagefase. Een concrete beschikbaarheidsdatum kan nog niet worden gegeven. Geïnteresseerden kunnen zich nu al registreren om tijdig geïnformeerd te worden."},
  {"id":25,"lang":"fr","title":"Vision & Pourquoi","text":"Sous nos pieds se trouve le réseau de communication le plus ancien de la Terre. Les champignons mycorhiziens relient presque toutes les plantes terrestres depuis 400 millions d'années. Ils émettent des signaux électriques. Mesurables. Reproductibles. Le réseau émet. Nous venons tout juste de commencer à écouter."},
  {"id":26,"lang":"fr","title":"À propos du projet","text":"OpenMycoNet a été initié par Robert Jank, inventeur indépendant de Maintal près de Francfort. Le système BioComm est protégé par un modèle d'utilité déposé auprès du DPMA. Principe: Proprietary Intelligence, Open Data — le modèle d'IA est protégé, les données qui l'entraînent sont libres."},
  {"id":27,"lang":"fr","title":"Participer & exploiter un nœud","text":"Emprunter le matériel BioComm en prêt — caution env. 100 €. Télécharger BioComm gratuitement, sans installation. Placer les électrodes dans le sol ou le pot. BioComm se connecte automatiquement — aucune donnée brute ne quitte votre PC."},
  {"id":28,"lang":"fr","title":"Confidentialité & Transparence","text":"Les coordonnées GPS sont arrondies à 10×10 km — aucune localisation précise. Aucune donnée personnelle. Toutes les données brutes accessibles publiquement sous CC BY 4.0."},
  {"id":29,"lang":"fr","title":"Soutien & Dons","text":"OpenMycoNet est un projet de science citoyenne indépendant sans financement institutionnel. Les coûts de serveur sont financés par des dons volontaires. Chaque contribution compte."},
  {"id":30,"lang":"fr","title":"Applications","text":"Agriculture de précision: réagir avant les dégâts, sans produits chimiques. Protection des forêts: des changements de signaux peuvent indiquer sécheresse ou infestation des semaines à l'avance. Régénération des sols par stimulation fréquentielle. Protection du climat: les réseaux mycorhiziens séquestrent du CO₂. Recherche fondamentale sur les signaux fongiques."},
  {"id":31,"lang":"fr","title":"Faits & Chiffres","text":"400 millions d'années d'existence. 90% des plantes terrestres connectées. 8 canaux simultanés jusqu'à 10 000 Hz. Caution env. 100 € (coût final à confirmer)."},
  {"id":32,"lang":"fr","title":"Disponibilité matérielle & calendrier","text":"Les premiers prototypes BioComm sont en phase de fabrication. Une date de disponibilité précise ne peut pas encore être donnée. Les personnes intéressées peuvent déjà s'inscrire sur le site web pour être informées rapidement."},
  {"id":33,"lang":"es","title":"Visión & Por qué","text":"Bajo nuestros pies se encuentra la red de comunicación más antigua de la Tierra. Los hongos micorrícicos llevan 400 millones de años conectando las plantas terrestres. Emiten señales eléctricas. Medibles. Reproducibles. La red transmite. Apenas hemos empezado a escuchar."},
  {"id":34,"lang":"es","title":"Sobre el proyecto","text":"OpenMycoNet fue iniciado por Robert Jank, inventor independiente de Maintal. El sistema BioComm está protegido por un modelo de utilidad registrado en la DPMA. Principio: Proprietary Intelligence, Open Data — el modelo de IA está protegido, los datos que lo entrenan son libres."},
  {"id":35,"lang":"es","title":"Participar & operar un nodo","text":"Tomar hardware BioComm en préstamo — depósito aprox. 100 €. Descargar BioComm gratis, sin instalación. Colocar electrodos en tierra o maceta con sustrato micorrícico. BioComm se conecta automáticamente — ningún dato bruto abandona tu PC."},
  {"id":36,"lang":"es","title":"Privacidad & Transparencia","text":"Las coordenadas GPS se redondean a 10×10 km — sin ubicación exacta. Sin datos personales. Todos los datos brutos accesibles públicamente bajo CC BY 4.0."},
  {"id":37,"lang":"es","title":"Apoyo & Donaciones","text":"OpenMycoNet es un proyecto de ciencia ciudadana independiente sin financiación institucional. Los costes de servidor se financian con donaciones voluntarias. Cada aportación cuenta."},
  {"id":38,"lang":"es","title":"Aplicaciones","text":"Agricultura de precisión: reaccionar antes de los daños, sin químicos. Protección forestal: cambios en señales pueden indicar sequía o infestación semanas antes. Regeneración del suelo por estimulación frecuencial. Protección del clima: las redes micorrícicas secuestran CO₂. Investigación fundamental sobre señales fúngicas."},
  {"id":39,"lang":"es","title":"Hechos & Cifras","text":"400 millones de años de existencia. 90% de las plantas terrestres conectadas. 8 canales simultáneos hasta 10.000 Hz. Depósito aprox. €100 (costes definitivos por confirmar)."},
  {"id":40,"lang":"es","title":"Disponibilidad de hardware & calendario","text":"Los primeros prototipos BioComm están en fase de fabricación de PCB. Aún no se puede dar una fecha concreta de disponibilidad. Los interesados ya pueden registrarse en el sitio web para ser notificados con anticipación."},
]

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
    # EN
    "available": ["hardware", "timeline", "available", "device", "node", "when", "delivery"],
    "join": ["join", "node", "hardware", "step", "electrode", "operate", "participate"],
    "privacy": ["privacy", "gps", "data", "personal", "anonymous"],
    "donate": ["donate", "support", "fund", "financ"],
    "application": ["application", "agriculture", "forest", "climate", "research", "use"],
    # NL/FR/ES — grundlegend
    "beschikbaar": ["hardware", "tijdlijn", "knooppunt"],
    "disponible": ["hardware", "calendrier", "nœud", "nodo"],
}

def expand_keywords(words: list[str]) -> list[str]:
    expanded = list(words)
    for w in words:
        for key, syns in SYNONYMS.items():
            if w in key or key in w:
                expanded.extend(syns)
    return expanded

def find_chunks(query: str, lang: str, top_k: int = 3) -> list[dict]:
    """Gibt die relevantesten Chunks für Sprache und Query zurück."""
    words = [w for w in query.lower().split() if len(w) > 3]
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

    message = (data.get("message") or "").strip()
    history = data.get("history") or []

    if not message:
        return jsonify({"error": "Kein Text übermittelt"}), 400

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
        {"role": m["role"], "content": m["content"]}
        for m in history[-10:]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    clean_history.append({"role": "user", "content": message})

    # Anthropic-API-Call
    try:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=system,
            messages=clean_history,
        )
        answer = response.content[0].text
    except KeyError:
        logger.error("ANTHROPIC_API_KEY nicht gesetzt")
        return jsonify({"error": "API-Key fehlt (ANTHROPIC_API_KEY nicht konfiguriert)"}), 500
    except anthropic.APIError as e:
        logger.error("Anthropic API-Fehler: %s", e)
        return jsonify({"error": f"API-Fehler: {e}"}), 502

    return jsonify({
        "answer": answer,
        "chunks_used": chunk_titles,
        "lang": lang,
    })
