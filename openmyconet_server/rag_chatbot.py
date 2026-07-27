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

from extensions import db
from models import ChatLog

logger = logging.getLogger(__name__)

chatbot_bp = Blueprint("chatbot", __name__)

# ---------------------------------------------------------------------------
# Wissensbasis — aus translations.js extrahiert + manueller Zeitplan-Chunk
# ---------------------------------------------------------------------------

CHUNKS = [
  {"id":1,"lang":"de","title":"Vision & Warum","text":"Unter unseren Füßen liegt das älteste und weitreichendste Kommunikationsnetzwerk der Erde. Mykorrhiza-Pilze verbinden seit 400 Millionen Jahren nahezu alle Landpflanzen miteinander — sie transportieren Nährstoffe, übermitteln Warnsignale und koordinieren das Leben im Boden auf eine Weise die wir gerade erst zu verstehen beginnen. Sie senden elektrische Signale. Messbar. Reproduzierbar. Und bisher kaum entschlüsselt. OpenMycoNet stellt die einfache aber weitreichende Frage: Was passiert wenn wir aufhören, Böden nur von außen zu analysieren — und stattdessen anfangen zuzuhören was das Netzwerk selbst sendet? Das Netzwerk sendet. Wir haben gerade erst angefangen zuzuhören. Jeder BioComm-Knoten der weltweit in Betrieb geht bringt uns einen Schritt näher an das Verständnis — für alle."},
  {"id":2,"lang":"de","title":"Über das Projekt","text":"OpenMycoNet wurde von Robert Jank, unabhängigem Erfinder aus Maintal bei Frankfurt, initiiert — ohne Institutszugehörigkeit, mit dem Ziel zu verstehen was Mykorrhiza-Netzwerke elektrisch signalisieren. Das zugrundeliegende System BioComm ist durch ein Gebrauchsmuster beim DPMA geschützt. Die Software wird als portable .exe bereitgestellt. Die Messdaten gehören der Gemeinschaft. Prinzip: Proprietary Intelligence, Open Data — das KI-Modell ist geschützt, die Daten die es trainieren sind frei."},
  {"id":3,"lang":"de","title":"Mitmachen & Knoten betreiben","text":"Die Ergebnisse und Daten des Netzwerks stehen allen offen — jeder kann sie einsehen, ganz ohne eigenen Knoten und ohne Vorkenntnisse. Einen eigenen BioComm-Knoten betreiben können aktuell nur ausgewählte Knotenbetreiber über eine kuratierte Bewerbung (Formular auf der Website), da die Hardware begrenzt ist. Kriterien sind unter anderem ein geeigneter Standort mit Substrat (Wald, Garten, Kompost, Blumentopf mit Pilz- oder Mykorrhiza-Substrat), WLAN-Verfügbarkeit in der Nähe des geplanten Bridge-Standorts sowie grundlegende Handhabung von Hardware; ein fachlicher oder wissenschaftlicher Bezug ist von Vorteil, aber keine Voraussetzung. Nach Zusage: BioComm-Messgerät als Leihgerät erhalten — Pfand ca. 100 € (finale Kosten folgen), Rückgabe jederzeit möglich. BioComm-Software kostenlos herunterladen — keine Installation, kein Python nötig. Elektroden ins Substrat setzen. Der Knoten funkt seine Messdaten per LoRa an eine BioComm Bridge in der Nähe (Punkt-zu-Punkt, realistisch 1–3 km Reichweite im Wald); die Bridge verbindet sich per WLAN mit der Zentrale und überträgt die Daten automatisch im Hintergrund. Diese Funkanbindung ist Teil der aktuell in Entwicklung befindlichen Hardware-Generation und noch nicht ausgeliefert. Analyse und Anonymisierung erfolgen lokal — keine Rohdaten verlassen dein Gerät."},
  {"id":4,"lang":"de","title":"Datenschutz & Transparenz","text":"GPS-Koordinaten werden auf 10×10 km vergröbert — kein exakter Standort. Keine personenbezogenen Daten. Alle Rohdaten öffentlich zugänglich unter Creative Commons CC BY 4.0."},
  {"id":5,"lang":"de","title":"Unterstützung & Spenden","text":"OpenMycoNet ist ein unabhängiges Citizen-Science-Projekt ohne institutionelle Förderung. Serverkosten und Weiterentwicklung werden durch freiwillige Spenden finanziert. Jeder Betrag hilft. Wir für OpenMycoNet — OpenMycoNet für alle."},
  {"id":6,"lang":"de","title":"Anwendungsfelder","text":"Präzisionslandwirtschaft: Wenn wir die Signalmuster von Trockenstress, Nährstoffmangel und Schädlingsbefall kennen, können Landwirte reagieren bevor Schäden entstehen — ohne Chemie, ohne Flächenpauschalen. Waldschutz: Veränderungen in den Signalmustern könnten Trockenheit, Borkenkäferbefall oder Brandgefahr anzeigen — Wochen bevor es sichtbar wird. Bodenregeneration: Durch gezielte Frequenzstimulation lässt sich die Aktivität von Mykorrhiza-Netzwerken beeinflussen. Klimaschutz: Gesunde Mykorrhiza-Netzwerke binden nachweislich CO₂. BioComm könnte als unabhängiges Monitoring-Instrument für Boden-Carbon-Zertifikate dienen. Grundlagenforschung: Adamatzky et al. haben gezeigt dass Pilz-Spike-Trains strukturelle Ähnlichkeiten mit menschlichen Sprachen aufweisen."},
  {"id":7,"lang":"de","title":"Fakten & Zahlen","text":"400 Millionen Jahre: so lange existieren Mykorrhiza-Netzwerke auf der Erde. 90% aller Landpflanzen sind mit Mykorrhiza-Pilzen verbunden. 8 Messkanäle erfasst BioComm gleichzeitig, bis zu 10.000 Hz. Ca. 100 € Pfandgebühr für ein BioComm-Leihgerät (finale Kosten folgen)."},
  {"id":8,"lang":"de","title":"Hardware-Verfügbarkeit & Zeitplan","text":"Die ersten BioComm-Prototypen befinden sich aktuell in der PCB-Fertigungsphase. Die Platinen werden produziert, anschließend folgen Aufbau und Validierung der ersten Knoten in 3D-gedruckten IP65-Gehäusen. Ein konkretes Datum für die erste Verfügbarkeit kann noch nicht genannt werden. Das Leihgerät-Modell ist geplant mit einem Pfand von ca. 100 € — finale Kosten folgen. Interessenten können sich bereits jetzt auf der Website registrieren, um frühzeitig benachrichtigt zu werden."},
  {"id":9,"lang":"en","title":"Vision & Why","text":"Beneath our feet lies the oldest and most extensive communication network on Earth. Mycorrhizal fungi have connected almost all land plants for 400 million years — transporting nutrients, transmitting warning signals, and coordinating life in the soil in ways we are only beginning to understand. They send electrical signals. Measurable. Reproducible. And barely deciphered so far. OpenMycoNet asks: what happens when we stop analysing soil only from the outside and start listening to what the network itself is sending? The network is transmitting. We have only just begun to listen."},
  {"id":10,"lang":"en","title":"About the Project","text":"OpenMycoNet was initiated by Robert Jank, independent inventor from Maintal near Frankfurt — without institutional affiliation, with the goal of understanding what mycorrhizal networks signal electrically. The underlying BioComm system is protected by a utility model registered with the DPMA. The software is provided as a portable .exe. The measurement data belongs to the community. Principle: Proprietary Intelligence, Open Data — the AI model is protected, the data that trains it is free."},
  {"id":11,"lang":"en","title":"Join & operate a node","text":"The network's results and data are open to everyone — anyone can view them, no prior knowledge and no node of your own required. Operating your own BioComm node is currently only possible for a curated selection of node operators via an application (form on the website), since hardware is limited. Criteria include a suitable location with substrate (forest, garden, compost, or a pot with fungal/mycorrhizal substrate), Wi-Fi availability near the planned bridge location, and basic hardware handling; a professional or scientific background is a plus but not a requirement. Once accepted: receive a BioComm measuring device on loan — deposit approx. €100 (final costs to follow), return at any time. Download the BioComm software for free — no installation, no Python required. Insert electrodes into the substrate. The node transmits its measurement data via LoRa to a nearby BioComm Bridge (point-to-point, realistically 1–3 km range in forest terrain); the bridge connects to the central server via Wi-Fi and uploads the data automatically in the background. This radio link is part of the hardware generation currently in development and not yet shipped. Analysis and anonymisation happen locally — no raw data ever leaves your device."},
  {"id":12,"lang":"en","title":"Privacy & Transparency","text":"GPS coordinates are coarsened to 10×10 km — no exact location. No personal data. All raw data publicly accessible under Creative Commons CC BY 4.0."},
  {"id":13,"lang":"en","title":"Support & Donations","text":"OpenMycoNet is an independent citizen science project without institutional funding. Server costs and further development are financed by voluntary donations. Every contribution helps. We support OpenMycoNet — OpenMycoNet supports everyone."},
  {"id":14,"lang":"en","title":"Applications","text":"Precision agriculture: farmers can respond before damage occurs — without chemicals, without blanket treatments. Forest protection: changes in signal patterns could indicate drought, bark beetle infestation or fire risk — weeks before it becomes visible. Soil regeneration: targeted frequency stimulation can influence mycorrhizal network activity. Climate protection: healthy mycorrhizal networks demonstrably sequester CO₂. Fundamental research: Adamatzky et al. have shown that fungal spike trains have structural similarities to human languages."},
  {"id":15,"lang":"en","title":"Facts & Numbers","text":"400 million years: mycorrhizal networks have existed on Earth. 90% of all land plants are connected to mycorrhizal fungi. 8 channels recorded simultaneously by BioComm, up to 10,000 Hz. Approx. €100 deposit for a BioComm loan device (final costs to follow)."},
  {"id":16,"lang":"en","title":"Hardware availability & timeline","text":"The first BioComm prototypes are currently in the PCB manufacturing phase. The boards are being produced, followed by assembly and validation of the first nodes in 3D-printed IP65 enclosures. A specific availability date cannot be given yet. The loan device model is planned with a deposit of approx. €100 — final costs to follow. Interested parties can already register on the website to be notified early."},
  {"id":17,"lang":"nl","title":"Visie & Waarom","text":"Onder onze voeten ligt het oudste communicatienetwerk van de aarde. Mycorrhizaschimmels verbinden al 400 miljoen jaar vrijwel alle landplanten. Ze zenden elektrische signalen. Meetbaar. Reproduceerbaar. OpenMycoNet vraagt: wat gebeurt er als we ophouden bodems alleen van buitenaf te analyseren? Het netwerk zendt. We zijn er nog maar net mee begonnen te luisteren."},
  {"id":18,"lang":"nl","title":"Over het project","text":"OpenMycoNet werd geïnitieerd door Robert Jank, onafhankelijk uitvinder uit Maintal bij Frankfurt. Het BioComm-systeem is beschermd door een gebruiksmodel bij het DPMA. De software wordt aangeboden als draagbare .exe. De meetgegevens zijn eigendom van de gemeenschap. Principe: Proprietary Intelligence, Open Data."},
  {"id":19,"lang":"nl","title":"Meedoen & knooppunt beheren","text":"De resultaten en gegevens van het netwerk zijn voor iedereen toegankelijk — je kunt ze bekijken zonder eigen node en zonder voorkennis. Een eigen BioComm-node beheren kan momenteel alleen via een gecureerde selectie van node-beheerders (sollicitatieformulier op de website), omdat de hardware beperkt is. Criteria zijn onder andere een geschikte locatie met substraat (bos, tuin, compost of bloempot met schimmel-/mycorrhiza-substraat), wifi-beschikbaarheid in de buurt van de geplande bridge-locatie en basiskennis van hardware; een vakinhoudelijke of wetenschappelijke achtergrond is een pré maar geen vereiste. Na toezegging: BioComm-meetapparaat als leentoestel — borg ca. €100 (definitieve kosten volgen). Gratis software downloaden, geen installatie nodig. Elektroden in het substraat plaatsen. De node zendt zijn meetgegevens via LoRa naar een nabijgelegen BioComm Bridge (punt-tot-punt, realistisch 1–3 km bereik in bosgebied); de bridge verbindt via wifi met de centrale server en verzendt de gegevens automatisch. Deze radioverbinding maakt deel uit van de hardwaregeneratie die momenteel in ontwikkeling is en nog niet is uitgeleverd."},
  {"id":20,"lang":"nl","title":"Privacy & Transparantie","text":"GPS-coördinaten worden vergroot naar 10×10 km — geen exacte locatie. Geen persoonsgegevens. Alle ruwe data openbaar toegankelijk onder Creative Commons CC BY 4.0."},
  {"id":21,"lang":"nl","title":"Ondersteuning & Donaties","text":"OpenMycoNet is een onafhankelijk citizen science-project zonder institutionele financiering. Serverkosten worden gefinancierd door vrijwillige donaties. Elk bedrag helpt."},
  {"id":22,"lang":"nl","title":"Toepassingen","text":"Precisielandbouw: reageren voordat schade ontstaat. Bosbescherming: signaalveranderingen kunnen droogte of plaagaantasting signaleren weken voordat het zichtbaar wordt. Bodemregeneratie via frequentiestimulatie. Klimaatbescherming: mycorrhizanetwerken binden CO₂. Fundamenteel onderzoek naar schimmelsignalen."},
  {"id":23,"lang":"nl","title":"Feiten & Cijfers","text":"400 miljoen jaar oud. 90% van alle landplanten verbonden met mycorrhizaschimmels. 8 kanalen tegelijk, tot 10.000 Hz. Borg ca. €100 (definitief te bevestigen)."},
  {"id":24,"lang":"nl","title":"Hardware-beschikbaarheid & tijdlijn","text":"De eerste BioComm-prototypes bevinden zich in de PCB-fabricagefase. Een concrete beschikbaarheidsdatum kan nog niet worden gegeven. Geïnteresseerden kunnen zich nu al registreren om tijdig geïnformeerd te worden."},
  {"id":25,"lang":"fr","title":"Vision & Pourquoi","text":"Sous nos pieds se trouve le réseau de communication le plus ancien de la Terre. Les champignons mycorhiziens relient presque toutes les plantes terrestres depuis 400 millions d'années. Ils émettent des signaux électriques. Mesurables. Reproductibles. Le réseau émet. Nous venons tout juste de commencer à écouter."},
  {"id":26,"lang":"fr","title":"À propos du projet","text":"OpenMycoNet a été initié par Robert Jank, inventeur indépendant de Maintal près de Francfort. Le système BioComm est protégé par un modèle d'utilité déposé auprès du DPMA. Principe: Proprietary Intelligence, Open Data — le modèle d'IA est protégé, les données qui l'entraînent sont libres."},
  {"id":27,"lang":"fr","title":"Participer & exploiter un nœud","text":"Les résultats et données du réseau sont accessibles à tous — vous pouvez les consulter sans nœud propre et sans connaissances préalables. Exploiter son propre nœud BioComm n'est actuellement possible que pour une sélection restreinte d'exploitants via une candidature (formulaire sur le site), le matériel étant limité. Les critères incluent un emplacement adapté avec substrat (forêt, jardin, compost ou pot avec substrat fongique/mycorhizien), la disponibilité du Wi-Fi à proximité de l'emplacement prévu pour le pont, et une manipulation de base du matériel ; un profil professionnel ou scientifique est un plus mais pas une condition. Une fois accepté : recevoir le matériel BioComm en prêt — caution env. 100 € (coût final à confirmer). Télécharger le logiciel gratuitement, sans installation. Placer les électrodes dans le substrat. Le nœud transmet ses données de mesure via LoRa à un pont BioComm à proximité (point à point, portée réaliste de 1 à 3 km en forêt) ; le pont se connecte au serveur central via Wi-Fi et transmet les données automatiquement. Cette liaison radio fait partie de la génération de matériel actuellement en développement et pas encore livrée."},
  {"id":28,"lang":"fr","title":"Confidentialité & Transparence","text":"Les coordonnées GPS sont arrondies à 10×10 km — aucune localisation précise. Aucune donnée personnelle. Toutes les données brutes accessibles publiquement sous CC BY 4.0."},
  {"id":29,"lang":"fr","title":"Soutien & Dons","text":"OpenMycoNet est un projet de science citoyenne indépendant sans financement institutionnel. Les coûts de serveur sont financés par des dons volontaires. Chaque contribution compte."},
  {"id":30,"lang":"fr","title":"Applications","text":"Agriculture de précision: réagir avant les dégâts, sans produits chimiques. Protection des forêts: des changements de signaux peuvent indiquer sécheresse ou infestation des semaines à l'avance. Régénération des sols par stimulation fréquentielle. Protection du climat: les réseaux mycorhiziens séquestrent du CO₂. Recherche fondamentale sur les signaux fongiques."},
  {"id":31,"lang":"fr","title":"Faits & Chiffres","text":"400 millions d'années d'existence. 90% des plantes terrestres connectées. 8 canaux simultanés jusqu'à 10 000 Hz. Caution env. 100 € (coût final à confirmer)."},
  {"id":32,"lang":"fr","title":"Disponibilité matérielle & calendrier","text":"Les premiers prototypes BioComm sont en phase de fabrication. Une date de disponibilité précise ne peut pas encore être donnée. Les personnes intéressées peuvent déjà s'inscrire sur le site web pour être informées rapidement."},
  {"id":33,"lang":"es","title":"Visión & Por qué","text":"Bajo nuestros pies se encuentra la red de comunicación más antigua de la Tierra. Los hongos micorrícicos llevan 400 millones de años conectando las plantas terrestres. Emiten señales eléctricas. Medibles. Reproducibles. La red transmite. Apenas hemos empezado a escuchar."},
  {"id":34,"lang":"es","title":"Sobre el proyecto","text":"OpenMycoNet fue iniciado por Robert Jank, inventor independiente de Maintal. El sistema BioComm está protegido por un modelo de utilidad registrado en la DPMA. Principio: Proprietary Intelligence, Open Data — el modelo de IA está protegido, los datos que lo entrenan son libres."},
  {"id":35,"lang":"es","title":"Participar & operar un nodo","text":"Los resultados y datos de la red están abiertos a todos — puedes consultarlos sin nodo propio y sin conocimientos previos. Operar tu propio nodo BioComm actualmente solo es posible para una selección curada de operadores mediante una solicitud (formulario en el sitio web), ya que el hardware es limitado. Los criterios incluyen una ubicación adecuada con sustrato (bosque, jardín, compost o maceta con sustrato fúngico/micorrícico), disponibilidad de Wi-Fi cerca de la ubicación prevista del puente, y manejo básico de hardware; un perfil profesional o científico es una ventaja pero no un requisito. Una vez aceptado: recibir el equipo BioComm en préstamo — depósito aprox. 100 € (costes finales por confirmar). Descargar el software gratis, sin instalación. Colocar los electrodos en el sustrato. El nodo transmite sus datos de medición mediante LoRa a un puente BioComm cercano (punto a punto, alcance realista de 1 a 3 km en bosque); el puente se conecta al servidor central por Wi-Fi y transmite los datos automáticamente. Este enlace de radio forma parte de la generación de hardware actualmente en desarrollo y aún no distribuida."},
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
