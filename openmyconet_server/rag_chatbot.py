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

from extensions import db
from models import ChatLog

logger = logging.getLogger(__name__)

chatbot_bp = Blueprint("chatbot", __name__)

# ---------------------------------------------------------------------------
# Wissensbasis
#
# Primärquelle: rag_chunks.json — von build_rag_index.py aus der echten
# translations.json + der News-Tabelle generiert. Nach Textänderungen an der
# Website `python build_rag_index.py` laufen lassen und die Datei mit
# deployen (siehe Skript-Doku).
#
# Fällt die Datei weg oder ist sie defekt, greift die unten eingebettete
# _FALLBACK_CHUNKS-Liste (eingefrorener Alt-Stand, hält den Bot notdürftig
# lauffähig, ist aber veraltet).
# ---------------------------------------------------------------------------

_CHUNKS_FILE = Path(__file__).with_name("rag_chunks.json")

_FALLBACK_CHUNKS = [
  {"id":1,"lang":"de","title":"Vision & Warum","text":"Unter unseren Füßen liegt das älteste und weitreichendste Kommunikationsnetzwerk der Erde. Mykorrhiza-Pilze verbinden seit 400 Millionen Jahren nahezu alle Landpflanzen miteinander — sie transportieren Nährstoffe, übermitteln Warnsignale und koordinieren das Leben im Boden auf eine Weise die wir gerade erst zu verstehen beginnen. Sie senden elektrische Signale. Messbar. Reproduzierbar. Und bisher kaum entschlüsselt. OpenMycoNet stellt die einfache aber weitreichende Frage: Was passiert wenn wir aufhören, Böden nur von außen zu analysieren — und stattdessen anfangen zuzuhören was das Netzwerk selbst sendet? Das Netzwerk sendet. Wir haben gerade erst angefangen zuzuhören. Jeder BioComm-Knoten der weltweit in Betrieb geht bringt uns einen Schritt näher an das Verständnis — für alle."},
  {"id":2,"lang":"de","title":"Über das Projekt","text":"OpenMycoNet wurde von Robert Jank, unabhängigem Erfinder aus Maintal bei Frankfurt, initiiert — ohne Institutszugehörigkeit, mit dem Ziel zu verstehen was Mykorrhiza-Netzwerke elektrisch signalisieren. Das zugrundeliegende System BioComm ist durch ein Gebrauchsmuster beim DPMA geschützt. Die Software wird als portable .exe bereitgestellt. Die Messdaten gehören der Gemeinschaft. Prinzip: Proprietary Intelligence, Open Data — das KI-Modell ist geschützt, die Daten die es trainieren sind frei."},
  {"id":3,"lang":"de","title":"Mitmachen & Knoten betreiben","text":"Die Ergebnisse und Daten des Netzwerks stehen allen offen — jeder kann sie einsehen, ganz ohne eigenen Knoten und ohne Vorkenntnisse. Einen eigenen BioComm-Knoten betreiben können aktuell nur ausgewählte Knotenbetreiber über eine kuratierte Bewerbung (Formular auf der Website), da die Hardware begrenzt ist. Kriterien sind unter anderem ein geeigneter Standort mit Substrat (Wald, Garten, Kompost, Blumentopf mit Pilz- oder Mykorrhiza-Substrat), WLAN-Verfügbarkeit in der Nähe des geplanten Bridge-Standorts sowie grundlegende Handhabung von Hardware; ein fachlicher oder wissenschaftlicher Bezug ist von Vorteil, aber keine Voraussetzung. Nach Zusage: BioComm-Messgerät als Leihgerät erhalten — Pfand ca. 100 € (finale Kosten folgen), Rückgabe jederzeit möglich. BioComm-Software kostenlos herunterladen — keine Installation, kein Python nötig. Elektroden ins Substrat setzen. Der Knoten funkt seine Messdaten per LoRa an eine BioComm Bridge in der Nähe (Punkt-zu-Punkt, realistisch 1–3 km Reichweite im Wald); die Bridge verbindet sich per WLAN mit der Zentrale und überträgt die Daten automatisch im Hintergrund. Diese Funkanbindung ist Teil der aktuell in Entwicklung befindlichen Hardware-Generation und noch nicht ausgeliefert. Personenbezogene Daten und dein genauer Standort werden nicht veröffentlicht — deine für die Forschung vorgesehenen Messdaten werden zusammen mit den notwendigen, nicht personenbezogenen Kontextinformationen offen bereitgestellt."},
  {"id":4,"lang":"de","title":"Datenschutz & Transparenz","text":"GPS-Koordinaten werden auf 10×10 km vergröbert — kein exakter Standort. Persönliche Daten und genaue Betreiberstandorte werden nicht veröffentlicht. Für die Forschung vorgesehene Messdaten werden zusammen mit den notwendigen, nicht personenbezogenen Kontextinformationen unter Creative Commons CC BY 4.0 offen bereitgestellt."},
  {"id":5,"lang":"de","title":"Unterstützung & Spenden","text":"OpenMycoNet ist ein unabhängiges Citizen-Science-Projekt ohne institutionelle Förderung. Serverkosten und Weiterentwicklung werden durch freiwillige Spenden finanziert. Jeder Betrag hilft. Wir für OpenMycoNet — OpenMycoNet für alle."},
  {"id":6,"lang":"de","title":"Anwendungsfelder","text":"Präzisionslandwirtschaft: Wenn wir die Signalmuster von Trockenstress, Nährstoffmangel und Schädlingsbefall kennen, können Landwirte reagieren bevor Schäden entstehen — ohne Chemie, ohne Flächenpauschalen. Waldschutz: Veränderungen in den Signalmustern könnten Trockenheit, Borkenkäferbefall oder Brandgefahr anzeigen — Wochen bevor es sichtbar wird. Bodenregeneration: Durch gezielte Frequenzstimulation lässt sich die Aktivität von Mykorrhiza-Netzwerken beeinflussen. Klimaschutz: Gesunde Mykorrhiza-Netzwerke binden nachweislich CO₂. BioComm könnte als unabhängiges Monitoring-Instrument für Boden-Carbon-Zertifikate dienen. Grundlagenforschung: Adamatzky et al. haben gezeigt dass Pilz-Spike-Trains strukturelle Ähnlichkeiten mit menschlichen Sprachen aufweisen."},
  {"id":7,"lang":"de","title":"Fakten & Zahlen","text":"400 Millionen Jahre: so lange existieren Mykorrhiza-Netzwerke auf der Erde. ~70% der Gefäßpflanzenarten gehen Verbindungen mit arbuskulären Mykorrhizapilzen ein. BioComm erfasst 8 bioelektrische Messkanäle gleichzeitig und bietet eine programmierbare Stimulationsausgabe von bis zu 10 kHz. Ca. 100 € Pfandgebühr für ein BioComm-Leihgerät (finale Kosten folgen)."},
  {"id":8,"lang":"de","title":"Hardware-Verfügbarkeit & Zeitplan","text":"Die ersten BioComm-Prototypen befinden sich aktuell in der PCB-Fertigungsphase. Die Platinen werden produziert, anschließend folgen Aufbau und Validierung der ersten Knoten in 3D-gedruckten IP65-Gehäusen. Ein konkretes Datum für die erste Verfügbarkeit kann noch nicht genannt werden. Das Leihgerät-Modell ist geplant mit einem Pfand von ca. 100 € — finale Kosten folgen. Interessenten können sich bereits jetzt auf der Website registrieren, um frühzeitig benachrichtigt zu werden."},
  {"id":9,"lang":"en","title":"Vision & Why","text":"Beneath our feet lies the oldest and most extensive communication network on Earth. Mycorrhizal fungi have connected almost all land plants for 400 million years — transporting nutrients, transmitting warning signals, and coordinating life in the soil in ways we are only beginning to understand. They send electrical signals. Measurable. Reproducible. And barely deciphered so far. OpenMycoNet asks: what happens when we stop analysing soil only from the outside and start listening to what the network itself is sending? The network is transmitting. We have only just begun to listen."},
  {"id":10,"lang":"en","title":"About the Project","text":"OpenMycoNet was initiated by Robert Jank, independent inventor from Maintal near Frankfurt — without institutional affiliation, with the goal of understanding what mycorrhizal networks signal electrically. The underlying BioComm system is protected by a utility model registered with the DPMA. The software is provided as a portable .exe. The measurement data belongs to the community. Principle: Proprietary Intelligence, Open Data — the AI model is protected, the data that trains it is free."},
  {"id":11,"lang":"en","title":"Join & operate a node","text":"The network's results and data are open to everyone — anyone can view them, no prior knowledge and no node of your own required. Operating your own BioComm node is currently only possible for a curated selection of node operators via an application (form on the website), since hardware is limited. Criteria include a suitable location with substrate (forest, garden, compost, or a pot with fungal/mycorrhizal substrate), Wi-Fi availability near the planned bridge location, and basic hardware handling; a professional or scientific background is a plus but not a requirement. Once accepted: receive a BioComm measuring device on loan — deposit approx. €100 (final costs to follow), return at any time. Download the BioComm software for free — no installation, no Python required. Insert electrodes into the substrate. The node transmits its measurement data via LoRa to a nearby BioComm Bridge (point-to-point, realistically 1–3 km range in forest terrain); the bridge connects to the central server via Wi-Fi and uploads the data automatically in the background. This radio link is part of the hardware generation currently in development and not yet shipped. Personal data and your exact location are never published — your measurement data intended for research is made openly available together with the necessary, non-personal context information."},
  {"id":12,"lang":"en","title":"Privacy & Transparency","text":"GPS coordinates are coarsened to 10×10 km — no exact location. Personal data and precise operator locations are never published. Measurement data intended for research is made openly available under Creative Commons CC BY 4.0, together with the necessary, non-personal context information."},
  {"id":13,"lang":"en","title":"Support & Donations","text":"OpenMycoNet is an independent citizen science project without institutional funding. Server costs and further development are financed by voluntary donations. Every contribution helps. We support OpenMycoNet — OpenMycoNet supports everyone."},
  {"id":14,"lang":"en","title":"Applications","text":"Precision agriculture: farmers can respond before damage occurs — without chemicals, without blanket treatments. Forest protection: changes in signal patterns could indicate drought, bark beetle infestation or fire risk — weeks before it becomes visible. Soil regeneration: targeted frequency stimulation can influence mycorrhizal network activity. Climate protection: healthy mycorrhizal networks demonstrably sequester CO₂. Fundamental research: Adamatzky et al. have shown that fungal spike trains have structural similarities to human languages."},
  {"id":15,"lang":"en","title":"Facts & Numbers","text":"400 million years: mycorrhizal networks have existed on Earth. ~70% of vascular plant species form associations with arbuscular mycorrhizal fungi. BioComm records 8 bioelectrical channels simultaneously and offers a programmable stimulation output of up to 10 kHz. Approx. €100 deposit for a BioComm loan device (final costs to follow)."},
  {"id":16,"lang":"en","title":"Hardware availability & timeline","text":"The first BioComm prototypes are currently in the PCB manufacturing phase. The boards are being produced, followed by assembly and validation of the first nodes in 3D-printed IP65 enclosures. A specific availability date cannot be given yet. The loan device model is planned with a deposit of approx. €100 — final costs to follow. Interested parties can already register on the website to be notified early."},
  {"id":17,"lang":"nl","title":"Visie & Waarom","text":"Onder onze voeten ligt het oudste communicatienetwerk van de aarde. Mycorrhizaschimmels verbinden al 400 miljoen jaar vrijwel alle landplanten. Ze zenden elektrische signalen. Meetbaar. Reproduceerbaar. OpenMycoNet vraagt: wat gebeurt er als we ophouden bodems alleen van buitenaf te analyseren? Het netwerk zendt. We zijn er nog maar net mee begonnen te luisteren."},
  {"id":18,"lang":"nl","title":"Over het project","text":"OpenMycoNet werd geïnitieerd door Robert Jank, onafhankelijk uitvinder uit Maintal bij Frankfurt. Het BioComm-systeem is beschermd door een gebruiksmodel bij het DPMA. De software wordt aangeboden als draagbare .exe. De meetgegevens zijn eigendom van de gemeenschap. Principe: Proprietary Intelligence, Open Data."},
  {"id":19,"lang":"nl","title":"Meedoen & knooppunt beheren","text":"De resultaten en gegevens van het netwerk zijn voor iedereen toegankelijk — je kunt ze bekijken zonder eigen node en zonder voorkennis. Een eigen BioComm-node beheren kan momenteel alleen via een gecureerde selectie van node-beheerders (sollicitatieformulier op de website), omdat de hardware beperkt is. Criteria zijn onder andere een geschikte locatie met substraat (bos, tuin, compost of bloempot met schimmel-/mycorrhiza-substraat), wifi-beschikbaarheid in de buurt van de geplande bridge-locatie en basiskennis van hardware; een vakinhoudelijke of wetenschappelijke achtergrond is een pré maar geen vereiste. Na toezegging: BioComm-meetapparaat als leentoestel — borg ca. €100 (definitieve kosten volgen). Gratis software downloaden, geen installatie nodig. Elektroden in het substraat plaatsen. De node zendt zijn meetgegevens via LoRa naar een nabijgelegen BioComm Bridge (punt-tot-punt, realistisch 1–3 km bereik in bosgebied); de bridge verbindt via wifi met de centrale server en verzendt de gegevens automatisch. Deze radioverbinding maakt deel uit van de hardwaregeneratie die momenteel in ontwikkeling is en nog niet is uitgeleverd."},
  {"id":20,"lang":"nl","title":"Privacy & Transparantie","text":"GPS-coördinaten worden vergroot naar 10×10 km — geen exacte locatie. Persoonlijke gegevens en exacte locaties van beheerders worden nooit gepubliceerd. Voor onderzoek bestemde meetgegevens worden samen met de noodzakelijke, niet-persoonlijke contextinformatie openbaar beschikbaar gesteld onder Creative Commons CC BY 4.0."},
  {"id":21,"lang":"nl","title":"Ondersteuning & Donaties","text":"OpenMycoNet is een onafhankelijk citizen science-project zonder institutionele financiering. Serverkosten worden gefinancierd door vrijwillige donaties. Elk bedrag helpt."},
  {"id":22,"lang":"nl","title":"Toepassingen","text":"Precisielandbouw: reageren voordat schade ontstaat. Bosbescherming: signaalveranderingen kunnen droogte of plaagaantasting signaleren weken voordat het zichtbaar wordt. Bodemregeneratie via frequentiestimulatie. Klimaatbescherming: mycorrhizanetwerken binden CO₂. Fundamenteel onderzoek naar schimmelsignalen."},
  {"id":23,"lang":"nl","title":"Feiten & Cijfers","text":"400 miljoen jaar oud. ~70% van de vaatplantensoorten gaat een associatie aan met arbusculaire mycorrhizaschimmels. BioComm meet 8 bio-elektrische kanalen tegelijk en biedt een programmeerbare stimulatie-output tot 10 kHz. Borg ca. €100 (definitief te bevestigen)."},
  {"id":24,"lang":"nl","title":"Hardware-beschikbaarheid & tijdlijn","text":"De eerste BioComm-prototypes bevinden zich in de PCB-fabricagefase. Een concrete beschikbaarheidsdatum kan nog niet worden gegeven. Geïnteresseerden kunnen zich nu al registreren om tijdig geïnformeerd te worden."},
  {"id":25,"lang":"fr","title":"Vision & Pourquoi","text":"Sous nos pieds se trouve le réseau de communication le plus ancien de la Terre. Les champignons mycorhiziens relient presque toutes les plantes terrestres depuis 400 millions d'années. Ils émettent des signaux électriques. Mesurables. Reproductibles. Le réseau émet. Nous venons tout juste de commencer à écouter."},
  {"id":26,"lang":"fr","title":"À propos du projet","text":"OpenMycoNet a été initié par Robert Jank, inventeur indépendant de Maintal près de Francfort. Le système BioComm est protégé par un modèle d'utilité déposé auprès du DPMA. Principe: Proprietary Intelligence, Open Data — le modèle d'IA est protégé, les données qui l'entraînent sont libres."},
  {"id":27,"lang":"fr","title":"Participer & exploiter un nœud","text":"Les résultats et données du réseau sont accessibles à tous — vous pouvez les consulter sans nœud propre et sans connaissances préalables. Exploiter son propre nœud BioComm n'est actuellement possible que pour une sélection restreinte d'exploitants via une candidature (formulaire sur le site), le matériel étant limité. Les critères incluent un emplacement adapté avec substrat (forêt, jardin, compost ou pot avec substrat fongique/mycorhizien), la disponibilité du Wi-Fi à proximité de l'emplacement prévu pour le pont, et une manipulation de base du matériel ; un profil professionnel ou scientifique est un plus mais pas une condition. Une fois accepté : recevoir le matériel BioComm en prêt — caution env. 100 € (coût final à confirmer). Télécharger le logiciel gratuitement, sans installation. Placer les électrodes dans le substrat. Le nœud transmet ses données de mesure via LoRa à un pont BioComm à proximité (point à point, portée réaliste de 1 à 3 km en forêt) ; le pont se connecte au serveur central via Wi-Fi et transmet les données automatiquement. Cette liaison radio fait partie de la génération de matériel actuellement en développement et pas encore livrée."},
  {"id":28,"lang":"fr","title":"Confidentialité & Transparence","text":"Les coordonnées GPS sont arrondies à 10×10 km — aucune localisation précise. Les données personnelles et les emplacements exacts des exploitants ne sont jamais publiés. Les données de mesure destinées à la recherche sont mises à disposition librement, avec les informations de contexte non personnelles nécessaires, sous licence Creative Commons CC BY 4.0."},
  {"id":29,"lang":"fr","title":"Soutien & Dons","text":"OpenMycoNet est un projet de science citoyenne indépendant sans financement institutionnel. Les coûts de serveur sont financés par des dons volontaires. Chaque contribution compte."},
  {"id":30,"lang":"fr","title":"Applications","text":"Agriculture de précision: réagir avant les dégâts, sans produits chimiques. Protection des forêts: des changements de signaux peuvent indiquer sécheresse ou infestation des semaines à l'avance. Régénération des sols par stimulation fréquentielle. Protection du climat: les réseaux mycorhiziens séquestrent du CO₂. Recherche fondamentale sur les signaux fongiques."},
  {"id":31,"lang":"fr","title":"Faits & Chiffres","text":"400 millions d'années d'existence. ~70 % des espèces de plantes vasculaires forment des associations avec des champignons mycorhiziens à arbuscules. BioComm enregistre 8 canaux bioélectriques simultanément et offre une sortie de stimulation programmable jusqu'à 10 kHz. Caution env. 100 € (coût final à confirmer)."},
  {"id":32,"lang":"fr","title":"Disponibilité matérielle & calendrier","text":"Les premiers prototypes BioComm sont en phase de fabrication. Une date de disponibilité précise ne peut pas encore être donnée. Les personnes intéressées peuvent déjà s'inscrire sur le site web pour être informées rapidement."},
  {"id":33,"lang":"es","title":"Visión & Por qué","text":"Bajo nuestros pies se encuentra la red de comunicación más antigua de la Tierra. Los hongos micorrícicos llevan 400 millones de años conectando las plantas terrestres. Emiten señales eléctricas. Medibles. Reproducibles. La red transmite. Apenas hemos empezado a escuchar."},
  {"id":34,"lang":"es","title":"Sobre el proyecto","text":"OpenMycoNet fue iniciado por Robert Jank, inventor independiente de Maintal. El sistema BioComm está protegido por un modelo de utilidad registrado en la DPMA. Principio: Proprietary Intelligence, Open Data — el modelo de IA está protegido, los datos que lo entrenan son libres."},
  {"id":35,"lang":"es","title":"Participar & operar un nodo","text":"Los resultados y datos de la red están abiertos a todos — puedes consultarlos sin nodo propio y sin conocimientos previos. Operar tu propio nodo BioComm actualmente solo es posible para una selección curada de operadores mediante una solicitud (formulario en el sitio web), ya que el hardware es limitado. Los criterios incluyen una ubicación adecuada con sustrato (bosque, jardín, compost o maceta con sustrato fúngico/micorrícico), disponibilidad de Wi-Fi cerca de la ubicación prevista del puente, y manejo básico de hardware; un perfil profesional o científico es una ventaja pero no un requisito. Una vez aceptado: recibir el equipo BioComm en préstamo — depósito aprox. 100 € (costes finales por confirmar). Descargar el software gratis, sin instalación. Colocar los electrodos en el sustrato. El nodo transmite sus datos de medición mediante LoRa a un puente BioComm cercano (punto a punto, alcance realista de 1 a 3 km en bosque); el puente se conecta al servidor central por Wi-Fi y transmite los datos automáticamente. Este enlace de radio forma parte de la generación de hardware actualmente en desarrollo y aún no distribuida."},
  {"id":36,"lang":"es","title":"Privacidad & Transparencia","text":"Las coordenadas GPS se redondean a 10×10 km — sin ubicación exacta. Los datos personales y las ubicaciones exactas de los operadores nunca se publican. Los datos de medición destinados a la investigación se ponen a disposición abierta, junto con la información de contexto no personal necesaria, bajo Creative Commons CC BY 4.0."},
  {"id":37,"lang":"es","title":"Apoyo & Donaciones","text":"OpenMycoNet es un proyecto de ciencia ciudadana independiente sin financiación institucional. Los costes de servidor se financian con donaciones voluntarias. Cada aportación cuenta."},
  {"id":38,"lang":"es","title":"Aplicaciones","text":"Agricultura de precisión: reaccionar antes de los daños, sin químicos. Protección forestal: cambios en señales pueden indicar sequía o infestación semanas antes. Regeneración del suelo por estimulación frecuencial. Protección del clima: las redes micorrícicas secuestran CO₂. Investigación fundamental sobre señales fúngicas."},
  {"id":39,"lang":"es","title":"Hechos & Cifras","text":"400 millones de años de existencia. ~70% de las especies de plantas vasculares forman asociaciones con hongos micorrícicos arbusculares. BioComm registra 8 canales bioeléctricos simultáneamente y ofrece una salida de estimulación programable de hasta 10 kHz. Depósito aprox. €100 (costes definitivos por confirmar)."},
  {"id":40,"lang":"es","title":"Disponibilidad de hardware & calendario","text":"Los primeros prototipos BioComm están en fase de fabricación de PCB. Aún no se puede dar una fecha concreta de disponibilidad. Los interesados ya pueden registrarse en el sitio web para ser notificados con anticipación."},
  {"id":41,"lang":"de","title":"Förderer & Kooperationen","text":"Es gibt zwei Wege, OpenMycoNet als Unternehmen oder Organisation zu unterstützen. Als Förderer zahlt man einen frei wählbaren Jahresbeitrag ab 50 € und erscheint dafür mit Logo, Name, Kurzbeschreibung und Website-Link sichtbar auf der Fördererseite. Die Zahlung erfolgt nach einer Vorschau per PayPal oder Banküberweisung; vor der Veröffentlichung prüft OpenMycoNet, ob die Förderung thematisch passt — das dauert in der Regel höchstens 48 Stunden. Eine Rechnung wird automatisch per E-Mail bereitgestellt. Als Kooperationspartner beteiligt man sich ohne Geld — stattdessen auf Basis von Ressourcen wie Reichweite, Fachwissen, Infrastruktur oder technischer Unterstützung. Auch Kooperationsanfragen werden von OpenMycoNet persönlich geprüft, bevor der Eintrag veröffentlicht wird. Beide Formen sind auf der Fördererseite gleichberechtigt sichtbar, ohne optische Höherstufung der einen gegenüber der anderen. Bewerben kann man sich unter openmyconet.de/foerderer.html über die dortigen Formulare für 'Förderer werden' bzw. 'Kooperation anfragen'."},
  {"id":42,"lang":"de","title":"Förderer-Kategorien","text":"Förderer und Kooperationspartner ordnen sich bei der Bewerbung einer Kategorie zu, u.a. Pilzzucht & Mykologie, Landwirtschaft & Gartenbau, Forstwirtschaft & Waldschutz, Wissenschaft & Forschung, Bildung & Medien, Nachhaltige Produkte, Technologie & Software, Citizen Science & Bürgerforschung, Behörden & Institutionen, Schulen & Ausbildungsstätten sowie Sonstiges. Diese Kategorien stehen sowohl gewerblichen Förderern als auch Kooperationspartnern offen."},
  {"id":43,"lang":"en","title":"Supporters & Cooperations","text":"There are two ways for companies and organisations to support OpenMycoNet. As a supporter you pay a freely chosen annual contribution from €50 and in return appear with logo, name, short description and website link on the supporters page. Payment is made after a preview, via PayPal or bank transfer; before publishing, OpenMycoNet checks whether the funding fits OpenMycoNet's focus — this usually takes no more than 48 hours. An invoice is provided automatically by email. As a cooperation partner you contribute without money — instead based on resources such as reach, expertise, infrastructure or technical support. Cooperation requests are also reviewed personally by OpenMycoNet before publishing. Both forms are shown on the supporters page on equal footing, with no visual upgrade of one over the other. You can apply at openmyconet.de/foerderer.html via the 'Become a supporter' and 'Request cooperation' forms."},
  {"id":44,"lang":"en","title":"Supporter categories","text":"Supporters and cooperation partners choose a category when applying, including Mushroom cultivation & mycology, Agriculture & horticulture, Forestry & forest protection, Science & research, Education & media, Sustainable products, Technology & software, Citizen science, Authorities & institutions, Schools & training centres, and Other. These categories are open to both commercial supporters and cooperation partners."},
  {"id":45,"lang":"nl","title":"Sponsors & samenwerkingen","text":"Er zijn twee manieren waarop bedrijven en organisaties OpenMycoNet kunnen steunen. Als partner betaalt u een vrij te kiezen jaarbijdrage vanaf €50 en verschijnt u daarvoor met logo, naam, korte beschrijving en websitelink op de partnerspagina. De betaling verloopt na een voorbeeld via PayPal of bankoverschrijving; voordat de vermelding wordt gepubliceerd, controleert OpenMycoNet of de financiering inhoudelijk past — dit duurt doorgaans maximaal 48 uur. De factuur ontvangt u automatisch per e-mail. Als samenwerkingspartner draagt u bij zonder geld — in plaats daarvan op basis van middelen zoals bereik, expertise, infrastructuur of technische ondersteuning. Ook samenwerkingsaanvragen worden door OpenMycoNet persoonlijk beoordeeld voordat ze worden gepubliceerd. Beide vormen worden gelijkwaardig getoond op de partnerspagina. Aanmelden kan via openmyconet.de/foerderer.html met de formulieren 'Partner worden' en 'Samenwerking aanvragen'."},
  {"id":46,"lang":"nl","title":"Sponsorcategorieën","text":"Sponsors en samenwerkingspartners kiezen bij hun aanvraag een categorie, o.a. Paddenstoelenteelt & mycologie, Landbouw & tuinbouw, Bosbouw & bosbescherming, Wetenschap & onderzoek, Onderwijs & media, Duurzame producten, Technologie & software, Citizen science, Overheden & instellingen, Scholen & opleidingscentra en Overig. Deze categorieën staan open voor zowel sponsors als samenwerkingspartners."},
  {"id":47,"lang":"fr","title":"Partenaires & coopérations","text":"Il existe deux façons pour les entreprises et organisations de soutenir OpenMycoNet. En tant que partenaire, vous versez une cotisation annuelle librement choisie à partir de 50 € et apparaissez en retour avec logo, nom, courte description et lien vers votre site sur la page des partenaires. Le paiement s'effectue après un aperçu, par PayPal ou virement bancaire ; avant la publication, OpenMycoNet vérifie que le financement correspond thématiquement — cela prend généralement au maximum 48 heures. Une facture est fournie automatiquement par e-mail. En tant que partenaire de coopération, vous contribuez sans argent — sur la base de ressources telles que le rayonnement, le savoir-faire, l'infrastructure ou le soutien technique. Les demandes de coopération sont elles aussi examinées personnellement par OpenMycoNet avant publication. Les deux formes sont présentées à égalité sur la page des partenaires, sans mise en avant visuelle de l'une par rapport à l'autre. On peut postuler sur openmyconet.de/foerderer.html via les formulaires 'Devenir partenaire' et 'Demander une coopération'."},
  {"id":48,"lang":"fr","title":"Catégories de partenaires","text":"Les partenaires et partenaires de coopération choisissent une catégorie lors de leur candidature, notamment Culture de champignons & mycologie, Agriculture & horticulture, Sylviculture & protection des forêts, Science & recherche, Éducation & médias, Produits durables, Technologie & logiciels, Science citoyenne, Autorités & institutions, Écoles & centres de formation, et Autre. Ces catégories sont ouvertes aussi bien aux partenaires commerciaux qu'aux partenaires de coopération."},
  {"id":49,"lang":"es","title":"Patrocinadores & cooperaciones","text":"Existen dos formas de que empresas y organizaciones apoyen a OpenMycoNet. Como patrocinador, se paga una cuota anual de libre elección desde 50 € y a cambio se aparece con logotipo, nombre, breve descripción y enlace al sitio web en la página de patrocinadores. El pago se realiza tras ver una vista previa, mediante PayPal o transferencia bancaria; antes de la publicación, OpenMycoNet comprueba si la financiación encaja temáticamente — esto suele tardar como máximo 48 horas. La factura se proporciona automáticamente por correo electrónico. Como socio de cooperación, se contribuye sin dinero — en base a recursos como alcance, conocimientos, infraestructura o apoyo técnico. Las solicitudes de cooperación también son revisadas personalmente por OpenMycoNet antes de publicarse. Ambas formas se muestran en igualdad de condiciones en la página de patrocinadores, sin destacar visualmente una sobre la otra. Puede solicitarse en openmyconet.de/foerderer.html mediante los formularios 'Convertirse en patrocinador' y 'Solicitar cooperación'."},
  {"id":50,"lang":"es","title":"Categorías de patrocinadores","text":"Los patrocinadores y socios de cooperación eligen una categoría al solicitar, entre ellas Cultivo de setas & micología, Agricultura & horticultura, Silvicultura & protección forestal, Ciencia & investigación, Educación & medios, Productos sostenibles, Tecnología & software, Ciencia ciudadana, Autoridades & instituciones, Escuelas & centros de formación, y Otros. Estas categorías están abiertas tanto a patrocinadores comerciales como a socios de cooperación."},
  {"id":51,"lang":"de","title":"Wie wir arbeiten — Methodik","text":"OpenMycoNet setzt bewusst auf Feldforschung als Ergänzung zur Laborforschung: Laborstudien (z. B. die elektrophysiologischen Arbeiten von Andrew Adamatzky) schließen Störgrößen wie schwankende Bodenfeuchte oder Temperaturgradienten bewusst aus, um Grundmechanismen isoliert nachzuweisen — das macht sie methodisch wertvoll, begrenzt zugleich aber ihre Aussagekraft für reale, störungsbehaftete Ökosystem-Bedingungen. Lehmann und Rillig (2025) benennen eine deutliche Lücke in der CMN-Forschung (Common Mycorrhizal Networks), insbesondere bei Feldstudien und Daten auf Ökosystemebene. OpenMycoNet unterscheidet drei Mitgliedschaftsrollen — Mycelist (Mitglied, Basis des Projekts), Hyphist (Kooperationspartner) und Sporist (Förderer) — von der davon unabhängigen Knotenbetreiber-Qualifikation: Jede der drei Rollen kann nach kurzem Einführungstraining und nachgewiesener Sorgfalt Sensorik betreiben, unabhängig davon wie viel jemand einzahlt. Wissenschaftliche Sorgfalt bedeutet: erst Messdaten, dann Wirkungsaussagen, ergebnisoffenes Arbeiten, öffentliche Aussagen zu neuen Entwicklungen erst nach Klärung des Schutzstatus, systematische Dokumentation der Rahmenbedingungen durch Knotenbetreiber. In dieser frühen Phase verfolgt OpenMycoNet bewusst einen unabhängigen Entwicklungsweg, um zunächst Plattform und Datenbasis aufzubauen, bevor über institutionelle Kooperationen entschieden wird — behält dabei die Kontrolle über geistiges Eigentum, ersetzt aber nicht die Notwendigkeit methodischer Strenge: der Austausch mit unabhängigen Fachwissenschaftlern ist fester Bestandteil der Arbeit."},
  {"id":52,"lang":"en","title":"How We Work — Methodology","text":"OpenMycoNet deliberately relies on field research as a complement to laboratory research: lab studies (e.g. Andrew Adamatzky's electrophysiological work) deliberately exclude disturbance variables like fluctuating soil moisture or temperature gradients to demonstrate basic mechanisms in isolation — which makes them methodically valuable, but also limits their explanatory power for real, disturbance-laden ecosystem conditions. Lehmann and Rillig (2025) identify a substantial gap in CMN research (Common Mycorrhizal Networks), particularly regarding field studies and ecosystem-level data. OpenMycoNet distinguishes three membership roles — Mycelist (member, the project's foundation), Hyphist (cooperation partner) and Sporist (supporter) — from the independent node-operator qualification: any of the three roles can operate sensors after a short introductory training and demonstrated care, regardless of how much someone contributes financially. Scientific rigor means: measurement data first, then claims about effects; working with an open outcome; public statements about new developments only once protection status is clarified; systematic documentation of conditions by node operators. During this early phase, OpenMycoNet deliberately follows an independent development path to first establish the platform and data basis before deciding on institutional collaborations — retaining control over intellectual property, but this does not replace the need for methodological rigor: exchange with independent researchers is a fixed part of the work."},
  {"id":53,"lang":"nl","title":"Hoe wij werken — Methodiek","text":"OpenMycoNet zet bewust in op veldonderzoek als aanvulling op laboratoriumonderzoek: laboratoriumstudies (bijv. het elektrofysiologische werk van Andrew Adamatzky) sluiten storingsfactoren zoals wisselende bodemvochtigheid of temperatuurgradiënten bewust uit om basismechanismen geïsoleerd aan te tonen — dat maakt ze methodisch waardevol, maar beperkt tegelijk hun zeggingskracht voor echte, storingsgevoelige ecosysteemomstandigheden. Lehmann en Rillig (2025) benoemen een duidelijk hiaat in het CMN-onderzoek (Common Mycorrhizal Networks), met name bij veldstudies en data op ecosysteemniveau. OpenMycoNet onderscheidt drie lidmaatschapsrollen — Mycelist (lid, basis van het project), Hyphist (samenwerkingspartner) en Sporist (sponsor) — van de onafhankelijke node-beheerderskwalificatie: elk van de drie rollen kan na een korte introductietraining en aantoonbare zorgvuldigheid sensoriek beheren, ongeacht hoeveel iemand financieel bijdraagt. Wetenschappelijke zorgvuldigheid betekent: eerst meetdata, dan uitspraken over effecten; werken met open uitkomst; publieke uitspraken over nieuwe ontwikkelingen pas na verduidelijking van de beschermingsstatus; systematische documentatie van omstandigheden door node-beheerders. In deze vroege fase volgt OpenMycoNet bewust een onafhankelijk ontwikkelingspad om eerst platform en databasis op te bouwen voordat over institutionele samenwerkingen wordt beslist — met behoud van controle over intellectuele eigendom, maar dat vervangt niet de noodzaak van methodische striktheid: de uitwisseling met onafhankelijke vakwetenschappers is een vast onderdeel van het werk."},
  {"id":54,"lang":"fr","title":"Comment nous travaillons — Méthodologie","text":"OpenMycoNet mise délibérément sur la recherche de terrain comme complément à la recherche en laboratoire : les études de laboratoire (par ex. les travaux électrophysiologiques d'Andrew Adamatzky) excluent délibérément des variables perturbatrices comme l'humidité du sol fluctuante ou les gradients de température afin de démontrer isolément des mécanismes de base — ce qui les rend méthodologiquement précieuses, mais limite aussi leur portée explicative pour des conditions écosystémiques réelles, sujettes à perturbation. Lehmann et Rillig (2025) identifient un écart substantiel dans la recherche sur les CMN (Common Mycorrhizal Networks), en particulier concernant les études de terrain et les données à l'échelle de l'écosystème. OpenMycoNet distingue trois rôles d'adhésion — Mycelist (membre, base du projet), Hyphist (partenaire de coopération) et Sporist (partenaire commercial) — de la qualification d'exploitant de nœud, indépendante : chacun des trois rôles peut exploiter des capteurs après une brève formation d'introduction et un soin démontré, quel que soit le montant de sa contribution financière. La rigueur scientifique signifie : d'abord les données de mesure, puis les affirmations sur les effets ; travailler à résultat ouvert ; déclarations publiques sur de nouveaux développements uniquement une fois le statut de protection clarifié ; documentation systématique des conditions par les exploitants de nœuds. Durant cette phase précoce, OpenMycoNet suit délibérément une voie de développement indépendante afin d'établir d'abord la plateforme et la base de données avant de décider des collaborations institutionnelles — tout en conservant le contrôle de la propriété intellectuelle, mais cela ne remplace pas la nécessité d'une rigueur méthodologique : l'échange avec des scientifiques indépendants fait partie intégrante du travail."},
  {"id":55,"lang":"es","title":"Cómo trabajamos — Metodología","text":"OpenMycoNet apuesta deliberadamente por la investigación de campo como complemento a la investigación de laboratorio: los estudios de laboratorio (p. ej. el trabajo electrofisiológico de Andrew Adamatzky) excluyen deliberadamente variables de perturbación como la humedad del suelo fluctuante o los gradientes de temperatura para demostrar mecanismos básicos de forma aislada — lo que los hace metodológicamente valiosos, pero también limita su capacidad explicativa para condiciones reales de ecosistema sujetas a perturbación. Lehmann y Rillig (2025) señalan una brecha sustancial en la investigación sobre CMN (Common Mycorrhizal Networks), en particular en lo relativo a estudios de campo y datos a nivel de ecosistema. OpenMycoNet distingue tres roles de membresía — Mycelist (miembro, base del proyecto), Hyphist (socio de cooperación) y Sporist (patrocinador) — de la cualificación de operador de nodo, independiente: cualquiera de los tres roles puede operar sensores tras una breve formación introductoria y un cuidado demostrado, independientemente de cuánto contribuya económicamente. El rigor científico significa: primero los datos de medición, después las afirmaciones sobre efectos; trabajar con un resultado abierto; declaraciones públicas sobre nuevos desarrollos solo una vez aclarado el estado de protección; documentación sistemática de las condiciones por parte de los operadores de nodos. En esta fase temprana, OpenMycoNet sigue deliberadamente un camino de desarrollo independiente para establecer primero la plataforma y la base de datos antes de decidir sobre colaboraciones institucionales — conservando el control sobre la propiedad intelectual, pero esto no sustituye la necesidad de rigor metodológico: el intercambio con científicos independientes es parte fija del trabajo."},
]


def _load_chunks() -> list[dict]:
    """rag_chunks.json laden; bei Fehler auf _FALLBACK_CHUNKS zurückfallen."""
    try:
        data = json.loads(_CHUNKS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list) and data:
            logger.info("RAG-Wissensbasis: %d Chunks aus %s", len(data), _CHUNKS_FILE.name)
            return data
        logger.warning("%s ist leer/ungültig — nutze _FALLBACK_CHUNKS", _CHUNKS_FILE.name)
    except FileNotFoundError:
        logger.warning("%s fehlt — nutze _FALLBACK_CHUNKS (veralteter Stand)", _CHUNKS_FILE.name)
    except Exception as e:
        logger.error("%s konnte nicht geladen werden (%s) — nutze _FALLBACK_CHUNKS", _CHUNKS_FILE.name, e)
    return _FALLBACK_CHUNKS


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
    "software": ["software", "simulation", "testbetrieb", "closed loop", "implementiert", "biocomm", "live-monitor", "entwicklungsstatus"],
    "hardware": ["hardware", "biocomm", "esp32", "lora", "bridge", "knoten", "node", "sonde", "gehäuse", "überarbeitung", "prototyp", "entwicklungsstatus"],
    "biocomm": ["biocomm", "messung", "stimulation", "plattform", "software", "hardware", "kanäle", "elektrode"],
    "stimulation": ["stimulation", "reiz", "elektrisch", "optisch", "bidirektional", "amplitude", "frequenz"],
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
    "software": ["software", "simulation", "test", "implemented", "closed loop", "biocomm", "monitor", "development status"],
    "hardware": ["hardware", "biocomm", "esp32", "lora", "bridge", "node", "probe", "enclosure", "revision", "prototype", "development status"],
    "development": ["development", "status", "revision", "planned", "preparation", "complete", "pending", "implemented"],
    "deposit": ["deposit", "loan", "return", "borrow", "edition"],
    "cost": ["cost", "deposit", "loan", "contribution", "fee", "price", "euro"],
    "measure": ["measure", "measurement", "channels", "bioelectric", "electrode", "adc", "stimulation", "probe"],
    "stimulation": ["stimulation", "stimulus", "electrical", "optical", "bidirectional", "amplitude", "frequency"],
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
}

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
