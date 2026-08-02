/**
 * biocomm-faq.js — OpenMycoNet FAQ Overlay
 * Schwebendes FAQ-Widget, einbindbar auf allen Seiten via <script src="/biocomm-faq.js"></script>
 * Eigenstaendige Spracherkennung (unabhaengig vom Host-Seiten-Code, da index.html/
 * leihgeraete.html/quellennachweise.html "getLang()" und foerderer.html
 * "getFoerdererLang()" nutzen -- beide lesen aber denselben localStorage-Key
 * "omn_lang"). Inhalt wird bei jedem OEffnen neu anhand der aktuellen Sprache
 * gerendert, damit ein Sprachwechsel waehrend des Seitenbesuchs erfasst wird.
 */
(function() {
'use strict';

var LANGS = ['de','en','nl','fr','es'];

function getFaqLang() {
  var p = new URLSearchParams(window.location.search).get('lang');
  if (p && LANGS.indexOf(p) !== -1) return p;
  var stored = localStorage.getItem('omn_lang');
  if (stored && LANGS.indexOf(stored) !== -1) return stored;
  var bl = (navigator.language || 'de').split('-')[0].toLowerCase();
  return LANGS.indexOf(bl) !== -1 ? bl : 'de';
}

// ── FAQ-Daten (5 Sprachen) ─────────────────────────────────────────────────
var FAQ_BY_LANG = {
  de: [
    { cat: 'Über OpenMycoNet', items: [
      { q: 'Was ist OpenMycoNet?',
        a: 'Ein weltweites Citizen-Science-Netzwerk, das bioelektrische Signale in Mykorrhiza- und Pilznetzwerken misst. Ziel ist es zu verstehen, was das unterirdische Netzwerk uns mitteilt.' },
      { q: 'Was wird überhaupt gemessen?',
        a: 'Bioelektrische Signale (Spannungsschwankungen) im Pilzmyzel und Mykorrhiza-Netzwerk, zusammen mit Umweltdaten wie Bodentemperatur, Feuchtigkeit und CO₂.' },
      { q: 'Wie wird gemessen?',
        a: 'Über Elektroden, die im Substrat (Boden, Topf, Kompost) platziert werden. Der BioComm-Knoten erfasst die Signale mit hoher Auflösung und überträgt sie automatisch.' },
      { q: 'Womit wird gemessen?',
        a: 'Mit dem BioComm-Messknoten — einer kompakten, eigenentwickelten Hardware auf ESP32-Basis mit 16-bit-ADC, Sensoren für Temperatur, Feuchtigkeit und CO₂.' },
      { q: 'Wie kommunizieren die Sensor-Knoten mit der Zentrale?',
        a: 'Jeder Knoten sendet seine Messdaten per LoRa-Funk (Punkt-zu-Punkt, realistisch 1–3 km Reichweite im Wald) an eine BioComm Bridge in der Nähe. Die Bridge verbindet sich per WLAN mit der Zentrale und leitet die Daten weiter. Diese Funkanbindung ist Teil der aktuell in Entwicklung befindlichen Hardware-Generation und noch nicht ausgeliefert.' },
      { q: 'Wer kann mitmachen?',
        a: 'Die Ergebnisse und Daten des Netzwerks stehen allen offen — jeder kann sie einsehen, keine Vorkenntnisse nötig. Einen eigenen BioComm-Knoten betreiben können aktuell nur ausgewählte Knotenbetreiber über eine kuratierte Bewerbung, da die Hardware begrenzt ist.' },
    ]},
    { cat: 'Teilnahme', items: [
      { q: 'Kann ich die Daten auch ohne eigenen Knoten sehen?',
        a: 'Ja — alle Messdaten und Erkenntnisse aus dem Netzwerk sind offen zugänglich (CC BY 4.0), auch ohne eigenen Knoten. Ein Knoten ist nur nötig, wenn du selbst aktiv Daten beisteuern möchtest.' },
      { q: 'Wie kann ich Knotenbetreiber werden?',
        a: 'Über das Bewerbungsformular im Anmelde-Bereich — dort „Ja, ich bewerbe mich für einen Knoten" auswählen. Die Auswahl ist kuratiert: geeigneter Standort, WLAN in der Nähe des geplanten Bridge-Standorts und grundlegende Handhabung von Hardware werden vorausgesetzt, ein fachlicher oder wissenschaftlicher Bezug ist von Vorteil, aber keine Voraussetzung.' },
      { q: 'Wie bekomme ich die Hardware?',
        a: 'Über das Leihprogramm — gegen eine rückerstattbare Kaution (ca. 100 €) wird der BioComm-Knoten per Post zugeschickt, vorinstalliert und einsatzbereit.' },
      { q: 'Welche Software benötige ich?',
        a: 'Die BioComm-Software — sie läuft als portable .exe ohne Installation. Einfach starten, WLAN-Daten für die Bridge eingeben, fertig.' },
      { q: 'Wie erhalte ich die Software?',
        a: 'Als Download nach der Registrierung auf openmyconet.de.' },
      { q: 'Wo wird der Node am besten platziert?',
        a: 'Im Boden, Blumentopf oder Kompost mit Pilz- oder Mykorrhiza-Substrat. Die Elektroden werden direkt ins Substrat gesteckt.' },
      { q: 'Welche Internetverbindung wird benötigt?',
        a: 'Der Knoten selbst braucht kein WLAN — er funkt seine Messdaten per LoRa an die BioComm Bridge. Die Bridge verbindet sich per WLAN mit der Zentrale und überträgt die Daten automatisch im Hintergrund. Diese Funkanbindung ist Teil der aktuell in Entwicklung befindlichen Hardware-Generation.' },
      { q: 'Was passiert, wenn kein Internet verfügbar ist?',
        a: 'Die Daten werden lokal auf der microSD-Karte zwischengespeichert und bei nächster Verbindung automatisch übertragen.' },
      { q: 'Was kostet die Teilnahme?',
        a: 'Die Teilnahme am Projekt ist grundsätzlich kostenlos. Nur wenn du einen Messknoten betreiben willst fällt eine rückerstattbare Kaution in Höhe von ca. 100 € an.' },
    ]},
    { cat: 'Daten', items: [
      { q: 'Welche Daten werden übertragen?',
        a: 'Bioelektrische Messdaten und Umweltdaten (Temperatur, Feuchtigkeit, CO₂) sowie eine grobe Standortinfo.' },
      { q: 'Was geschieht mit meinen Daten?',
        a: 'Sie fließen anonymisiert in den offenen Datensatz ein (CC BY 4.0) und dienen der KI-gestützten Mustererkennung. Alle Daten sind frei zugänglich.' },
      { q: 'Wie werden meine Daten geschützt?',
        a: 'GPS-Koordinaten werden auf 10×10 km vergröbert. Die Anonymisierung erfolgt lokal auf deinem Gerät — keine Rohdaten mit genauem Standort verlassen deinen PC.' },
      { q: 'Kann ich meine eigenen Messdaten sehen und herunterladen?',
        a: 'Ja — du hast jederzeit Zugriff auf deine Messdaten und kannst sie einsehen und exportieren.' },
    ]},
    { cat: 'Sonstiges', items: [
      { q: 'Kann OpenMycoNet Gedanken lesen oder mit Pilzen kommunizieren?',
        a: 'Nein. OpenMycoNet misst elektrische Signalaktivität biologischer Netzwerke und untersucht Muster sowie Reaktionen auf Umweltbedingungen. Ziel ist es nicht, „Gedanken zu lesen", sondern biologische Prozesse besser zu verstehen.' },
      { q: 'Warum macht ihr das überhaupt?',
        a: 'Böden gehören zu den am wenigsten verstandenen Ökosystemen der Erde. Mit OpenMycoNet möchten wir gemeinsam mit Bürgerinnen und Bürgern dazu beitragen, biologische Aktivität sichtbar zu machen und langfristig besser zu verstehen.' },
    ]},
  ],
  en: [
    { cat: 'About OpenMycoNet', items: [
      { q: 'What is OpenMycoNet?',
        a: 'A global citizen science network that measures bioelectrical signals in mycorrhizal and fungal networks. The goal is to understand what the underground network is telling us.' },
      { q: 'What exactly is being measured?',
        a: 'Bioelectrical signals (voltage fluctuations) in fungal mycelium and mycorrhizal networks, together with environmental data such as soil temperature, humidity and CO₂.' },
      { q: 'How is it measured?',
        a: 'Via electrodes placed in the substrate (soil, pot, compost). The BioComm node captures the signals at high resolution and transmits them automatically.' },
      { q: 'What is used to measure it?',
        a: 'The BioComm measurement node — compact, in-house-developed hardware based on ESP32 with a 16-bit ADC and sensors for temperature, humidity and CO₂.' },
      { q: 'How do the sensor nodes communicate with the central server?',
        a: "Each node sends its measurement data via LoRa radio (point-to-point, realistically 1–3 km range in forest terrain) to a nearby BioComm Bridge. The Bridge connects to the central server via WiFi and forwards the data. This radio link is part of the hardware generation currently in development and has not yet shipped." },
      { q: 'Who can take part?',
        a: 'The network\'s results and data are open to everyone — anyone can view them, no prior knowledge required. Operating your own BioComm node is currently limited to selected node operators via a curated application, since hardware is limited.' },
    ]},
    { cat: 'Participation', items: [
      { q: 'Can I see the data without operating my own node?',
        a: 'Yes — all measurement data and findings from the network are openly accessible (CC BY 4.0), even without your own node. A node is only needed if you want to actively contribute data yourself.' },
      { q: 'How can I become a node operator?',
        a: 'Via the application form in the registration area — select "Yes, I\'m applying for a node" there. Selection is curated: a suitable location, WiFi near the planned Bridge site, and basic hardware handling are required; a professional or scientific background is an advantage but not a requirement.' },
      { q: 'How do I get the hardware?',
        a: 'Through the loan programme — against a refundable deposit (approx. €100), the BioComm node is shipped by post, pre-installed and ready to use.' },
      { q: 'What software do I need?',
        a: 'The BioComm software — it runs as a portable .exe with no installation required. Just start it, enter the Bridge\'s WiFi details, done.' },
      { q: 'How do I get the software?',
        a: 'As a download after registering on openmyconet.de.' },
      { q: 'Where is the best place to position the node?',
        a: 'In soil, a plant pot or compost with fungal or mycorrhizal substrate. The electrodes are inserted directly into the substrate.' },
      { q: 'What internet connection is required?',
        a: "The node itself doesn't need WiFi — it transmits its measurement data to the BioComm Bridge via LoRa. The Bridge connects to the central server via WiFi and transmits the data automatically in the background. This radio link is part of the hardware generation currently in development." },
      { q: 'What happens if no internet is available?',
        a: 'Data is cached locally on the microSD card and transmitted automatically once a connection is available again.' },
      { q: 'What does participation cost?',
        a: 'Participating in the project is fundamentally free. Only if you want to operate a measurement node is there a refundable deposit of approx. €100.' },
    ]},
    { cat: 'Data', items: [
      { q: 'What data is transmitted?',
        a: 'Bioelectrical measurement data and environmental data (temperature, humidity, CO₂), plus coarse location information.' },
      { q: 'What happens to my data?',
        a: 'It flows anonymised into the open dataset (CC BY 4.0) and is used for AI-assisted pattern recognition. All data is freely accessible.' },
      { q: 'How is my data protected?',
        a: 'GPS coordinates are coarsened to 10×10 km. Anonymisation happens locally on your device — no raw data with an exact location ever leaves your PC.' },
      { q: 'Can I view and download my own measurement data?',
        a: 'Yes — you have access to your measurement data at any time and can view and export it.' },
    ]},
    { cat: 'Other', items: [
      { q: 'Can OpenMycoNet read minds or communicate with fungi?',
        a: 'No. OpenMycoNet measures electrical signal activity in biological networks and studies patterns and responses to environmental conditions. The goal is not to "read minds" but to better understand biological processes.' },
      { q: 'Why are you doing this at all?',
        a: 'Soils are among the least understood ecosystems on Earth. With OpenMycoNet, we want to work together with citizens to make biological activity visible and understand it better in the long term.' },
    ]},
  ],
  nl: [
    { cat: 'Over OpenMycoNet', items: [
      { q: 'Wat is OpenMycoNet?',
        a: 'Een wereldwijd citizen science-netwerk dat bio-elektrische signalen in mycorrhiza- en schimmelnetwerken meet. Het doel is te begrijpen wat het ondergrondse netwerk ons vertelt.' },
      { q: 'Wat wordt er precies gemeten?',
        a: 'Bio-elektrische signalen (spanningsschommelingen) in schimmelmycelium en mycorrhizanetwerken, samen met omgevingsgegevens zoals bodemtemperatuur, vochtigheid en CO₂.' },
      { q: 'Hoe wordt er gemeten?',
        a: 'Via elektroden die in het substraat (bodem, pot, compost) worden geplaatst. De BioComm-node registreert de signalen met hoge resolutie en verzendt ze automatisch.' },
      { q: 'Waarmee wordt er gemeten?',
        a: 'Met de BioComm-meetknoop — compacte, zelf ontwikkelde hardware op ESP32-basis met 16-bit ADC, sensoren voor temperatuur, vochtigheid en CO₂.' },
      { q: 'Hoe communiceren de sensorknopen met de centrale?',
        a: 'Elke node stuurt zijn meetgegevens via LoRa-radio (punt-tot-punt, realistisch 1–3 km bereik in bosgebied) naar een nabijgelegen BioComm Bridge. De Bridge verbindt via wifi met de centrale server en stuurt de gegevens door. Deze radioverbinding maakt deel uit van de hardwaregeneratie die momenteel in ontwikkeling is en nog niet is uitgeleverd.' },
      { q: 'Wie kan meedoen?',
        a: 'De resultaten en gegevens van het netwerk zijn voor iedereen toegankelijk — iedereen kan ze bekijken, geen voorkennis nodig. Een eigen BioComm-node beheren kan momenteel alleen via geselecteerde knooppuntbeheerders na een gecureerde sollicitatie, omdat de hardware beperkt is.' },
    ]},
    { cat: 'Deelname', items: [
      { q: 'Kan ik de gegevens ook zonder eigen node zien?',
        a: 'Ja — alle meetgegevens en inzichten uit het netwerk zijn open toegankelijk (CC BY 4.0), ook zonder eigen node. Een node is alleen nodig als je zelf actief gegevens wilt bijdragen.' },
      { q: 'Hoe kan ik knooppuntbeheerder worden?',
        a: 'Via het sollicitatieformulier in het aanmeldgedeelte — selecteer daar "Ja, ik solliciteer voor een node". De selectie is gecureerd: een geschikte locatie, wifi in de buurt van de geplande Bridge-locatie en basiskennis van hardware zijn vereist; een vakinhoudelijke of wetenschappelijke achtergrond is een pré, maar geen vereiste.' },
      { q: 'Hoe krijg ik de hardware?',
        a: 'Via het leenprogramma — tegen een terugbetaalbare borg (ca. €100) wordt de BioComm-node per post toegestuurd, voorgeïnstalleerd en gebruiksklaar.' },
      { q: 'Welke software heb ik nodig?',
        a: 'De BioComm-software — deze draait als draagbare .exe zonder installatie. Gewoon starten, wifi-gegevens voor de Bridge invoeren, klaar.' },
      { q: 'Hoe krijg ik de software?',
        a: 'Als download na registratie op openmyconet.de.' },
      { q: 'Waar plaats ik de node het beste?',
        a: 'In de bodem, een bloempot of compost met schimmel- of mycorrhizasubstraat. De elektroden worden direct in het substraat gestoken.' },
      { q: 'Welke internetverbinding is nodig?',
        a: 'De node zelf heeft geen wifi nodig — hij zendt zijn meetgegevens via LoRa naar de BioComm Bridge. De Bridge verbindt via wifi met de centrale server en stuurt de gegevens automatisch op de achtergrond door. Deze radioverbinding maakt deel uit van de hardwaregeneratie die momenteel in ontwikkeling is.' },
      { q: 'Wat gebeurt er als er geen internet beschikbaar is?',
        a: 'Gegevens worden lokaal op de microSD-kaart opgeslagen en automatisch verzonden zodra er weer verbinding is.' },
      { q: 'Wat kost deelname?',
        a: 'Deelname aan het project is in principe gratis. Alleen als je een meetknoop wilt beheren, geldt een terugbetaalbare borg van ca. €100.' },
    ]},
    { cat: 'Gegevens', items: [
      { q: 'Welke gegevens worden verzonden?',
        a: 'Bio-elektrische meetgegevens en omgevingsgegevens (temperatuur, vochtigheid, CO₂), plus een globale locatie-indicatie.' },
      { q: 'Wat gebeurt er met mijn gegevens?',
        a: 'Ze vloeien geanonimiseerd in de open dataset (CC BY 4.0) en dienen voor AI-ondersteunde patroonherkenning. Alle gegevens zijn vrij toegankelijk.' },
      { q: 'Hoe worden mijn gegevens beschermd?',
        a: 'GPS-coördinaten worden vergroot naar 10×10 km. Anonimisering gebeurt lokaal op je apparaat — geen ruwe data met exacte locatie verlaat ooit je pc.' },
      { q: 'Kan ik mijn eigen meetgegevens bekijken en downloaden?',
        a: 'Ja — je hebt altijd toegang tot je meetgegevens en kunt ze bekijken en exporteren.' },
    ]},
    { cat: 'Overig', items: [
      { q: 'Kan OpenMycoNet gedachten lezen of met schimmels communiceren?',
        a: 'Nee. OpenMycoNet meet elektrische signaalactiviteit van biologische netwerken en onderzoekt patronen en reacties op omgevingsomstandigheden. Het doel is niet om "gedachten te lezen", maar om biologische processen beter te begrijpen.' },
      { q: 'Waarom doen jullie dit eigenlijk?',
        a: 'Bodems behoren tot de minst begrepen ecosystemen op aarde. Met OpenMycoNet willen we samen met burgers bijdragen aan het zichtbaar maken en op lange termijn beter begrijpen van biologische activiteit.' },
    ]},
  ],
  fr: [
    { cat: "À propos d'OpenMycoNet", items: [
      { q: "Qu'est-ce qu'OpenMycoNet ?",
        a: "Un réseau mondial de science citoyenne qui mesure les signaux bioélectriques dans les réseaux mycorhiziens et fongiques. L'objectif est de comprendre ce que le réseau souterrain nous communique." },
      { q: 'Que mesure-t-on exactement ?',
        a: "Les signaux bioélectriques (variations de tension) dans le mycélium fongique et les réseaux mycorhiziens, ainsi que des données environnementales telles que la température du sol, l'humidité et le CO₂." },
      { q: 'Comment mesure-t-on ?',
        a: 'Via des électrodes placées dans le substrat (sol, pot, compost). Le nœud BioComm capte les signaux à haute résolution et les transmet automatiquement.' },
      { q: 'Avec quoi mesure-t-on ?',
        a: "Avec le nœud de mesure BioComm — un matériel compact développé en interne, basé sur ESP32, doté d'un CAN 16 bits et de capteurs de température, d'humidité et de CO₂." },
      { q: 'Comment les nœuds capteurs communiquent-ils avec le serveur central ?',
        a: "Chaque nœud envoie ses données de mesure par radio LoRa (point à point, portée réaliste de 1 à 3 km en forêt) à un BioComm Bridge à proximité. Le Bridge se connecte au serveur central via WiFi et transmet les données. Cette liaison radio fait partie de la génération de matériel actuellement en développement et n'a pas encore été livrée." },
      { q: 'Qui peut participer ?',
        a: "Les résultats et données du réseau sont ouverts à tous — chacun peut les consulter, aucune connaissance préalable n'est requise. L'exploitation de son propre nœud BioComm est actuellement réservée à des exploitants de nœuds sélectionnés via une candidature encadrée, le matériel étant limité." },
    ]},
    { cat: 'Participation', items: [
      { q: 'Puis-je voir les données sans exploiter mon propre nœud ?',
        a: "Oui — toutes les données de mesure et les résultats du réseau sont librement accessibles (CC BY 4.0), même sans nœud personnel. Un nœud n'est nécessaire que si vous souhaitez contribuer activement des données vous-même." },
      { q: 'Comment devenir exploitant de nœud ?',
        a: "Via le formulaire de candidature dans l'espace d'inscription — sélectionnez-y « Oui, je candidate pour un nœud ». La sélection est encadrée : un emplacement adapté, un WiFi à proximité de l'emplacement prévu pour le Bridge et une manipulation de base du matériel sont requis ; un profil professionnel ou scientifique est un atout, mais pas une condition." },
      { q: 'Comment obtenir le matériel ?',
        a: 'Via le programme de prêt — moyennant une caution remboursable (environ 100 €), le nœud BioComm est envoyé par courrier, préinstallé et prêt à l\'emploi.' },
      { q: "De quel logiciel ai-je besoin ?",
        a: "Le logiciel BioComm — il fonctionne comme un .exe portable, sans installation. Il suffit de le lancer, de saisir les identifiants WiFi du Bridge, et c'est prêt." },
      { q: 'Comment obtenir le logiciel ?',
        a: 'En téléchargement après inscription sur openmyconet.de.' },
      { q: 'Où placer le nœud au mieux ?',
        a: 'Dans le sol, un pot de fleurs ou du compost contenant un substrat fongique ou mycorhizien. Les électrodes sont insérées directement dans le substrat.' },
      { q: 'Quelle connexion internet est nécessaire ?',
        a: "Le nœud lui-même n'a pas besoin de WiFi — il transmet ses données de mesure au BioComm Bridge via LoRa. Le Bridge se connecte au serveur central via WiFi et transmet automatiquement les données en arrière-plan. Cette liaison radio fait partie de la génération de matériel actuellement en développement." },
      { q: "Que se passe-t-il en l'absence d'internet ?",
        a: "Les données sont mises en cache localement sur la carte microSD et transmises automatiquement dès qu'une connexion est de nouveau disponible." },
      { q: 'Quel est le coût de la participation ?',
        a: "La participation au projet est fondamentalement gratuite. Une caution remboursable d'environ 100 € n'est due que si vous souhaitez exploiter un nœud de mesure." },
    ]},
    { cat: 'Données', items: [
      { q: 'Quelles données sont transmises ?',
        a: 'Les données de mesure bioélectriques et les données environnementales (température, humidité, CO₂), ainsi qu\'une localisation approximative.' },
      { q: 'Que deviennent mes données ?',
        a: "Elles sont intégrées de manière anonymisée dans le jeu de données ouvert (CC BY 4.0) et servent à la reconnaissance de motifs assistée par IA. Toutes les données sont librement accessibles." },
      { q: 'Comment mes données sont-elles protégées ?',
        a: "Les coordonnées GPS sont dégradées à 10×10 km. L'anonymisation s'effectue localement sur votre appareil — aucune donnée brute avec une localisation précise ne quitte jamais votre PC." },
      { q: 'Puis-je consulter et télécharger mes propres données de mesure ?',
        a: 'Oui — vous avez accès à tout moment à vos données de mesure et pouvez les consulter et les exporter.' },
    ]},
    { cat: 'Divers', items: [
      { q: 'OpenMycoNet peut-il lire les pensées ou communiquer avec les champignons ?',
        a: "Non. OpenMycoNet mesure l'activité des signaux électriques de réseaux biologiques et étudie les motifs ainsi que les réactions aux conditions environnementales. L'objectif n'est pas de « lire les pensées », mais de mieux comprendre les processus biologiques." },
      { q: 'Pourquoi faites-vous cela au juste ?',
        a: "Les sols comptent parmi les écosystèmes les moins compris de la planète. Avec OpenMycoNet, nous souhaitons contribuer, avec les citoyens, à rendre visible l'activité biologique et à mieux la comprendre sur le long terme." },
    ]},
  ],
  es: [
    { cat: 'Sobre OpenMycoNet', items: [
      { q: '¿Qué es OpenMycoNet?',
        a: 'Una red mundial de ciencia ciudadana que mide señales bioeléctricas en redes micorrícicas y fúngicas. El objetivo es comprender qué nos comunica la red subterránea.' },
      { q: '¿Qué se mide exactamente?',
        a: 'Señales bioeléctricas (fluctuaciones de voltaje) en el micelio fúngico y las redes micorrícicas, junto con datos ambientales como la temperatura del suelo, la humedad y el CO₂.' },
      { q: '¿Cómo se mide?',
        a: 'Mediante electrodos colocados en el sustrato (suelo, maceta, compost). El nodo BioComm capta las señales con alta resolución y las transmite automáticamente.' },
      { q: '¿Con qué se mide?',
        a: 'Con el nodo de medición BioComm — hardware compacto desarrollado internamente, basado en ESP32, con un ADC de 16 bits y sensores de temperatura, humedad y CO₂.' },
      { q: '¿Cómo se comunican los nodos sensores con la central?',
        a: 'Cada nodo envía sus datos de medición por radio LoRa (punto a punto, con un alcance realista de 1 a 3 km en bosque) a un BioComm Bridge cercano. El Bridge se conecta a la central por WiFi y reenvía los datos. Este enlace de radio forma parte de la generación de hardware actualmente en desarrollo y aún no se ha distribuido.' },
      { q: '¿Quién puede participar?',
        a: 'Los resultados y datos de la red están abiertos a todos — cualquiera puede consultarlos, sin necesidad de conocimientos previos. Actualmente, operar tu propio nodo BioComm solo es posible para operadores de nodo seleccionados mediante una solicitud curada, ya que el hardware es limitado.' },
    ]},
    { cat: 'Participación', items: [
      { q: '¿Puedo ver los datos sin tener mi propio nodo?',
        a: 'Sí — todos los datos de medición y los hallazgos de la red son de acceso abierto (CC BY 4.0), incluso sin nodo propio. Un nodo solo es necesario si quieres contribuir activamente con datos tú mismo.' },
      { q: '¿Cómo puedo convertirme en operador de nodo?',
        a: 'A través del formulario de solicitud en el área de registro — selecciona ahí "Sí, quiero solicitar un nodo". La selección es curada: se requiere una ubicación adecuada, WiFi cerca de la ubicación prevista del Bridge y un manejo básico del hardware; contar con un perfil profesional o científico es una ventaja, pero no un requisito.' },
      { q: '¿Cómo consigo el hardware?',
        a: 'A través del programa de préstamo — mediante un depósito reembolsable (aprox. 100 €), el nodo BioComm se envía por correo, preinstalado y listo para usar.' },
      { q: '¿Qué software necesito?',
        a: 'El software BioComm — funciona como un .exe portátil sin instalación. Solo hay que iniciarlo, introducir los datos WiFi del Bridge, y listo.' },
      { q: '¿Cómo obtengo el software?',
        a: 'Como descarga tras registrarte en openmyconet.de.' },
      { q: '¿Dónde es mejor colocar el nodo?',
        a: 'En el suelo, una maceta o compost con sustrato fúngico o micorrícico. Los electrodos se insertan directamente en el sustrato.' },
      { q: '¿Qué conexión a internet se necesita?',
        a: 'El nodo en sí no necesita WiFi — transmite sus datos de medición al BioComm Bridge por LoRa. El Bridge se conecta a la central por WiFi y transmite los datos automáticamente en segundo plano. Este enlace de radio forma parte de la generación de hardware actualmente en desarrollo.' },
      { q: '¿Qué ocurre si no hay internet disponible?',
        a: 'Los datos se almacenan localmente en la tarjeta microSD y se transmiten automáticamente en cuanto vuelve a haber conexión.' },
      { q: '¿Cuánto cuesta participar?',
        a: 'Participar en el proyecto es, en principio, gratuito. Solo si quieres operar un nodo de medición se aplica un depósito reembolsable de aprox. 100 €.' },
    ]},
    { cat: 'Datos', items: [
      { q: '¿Qué datos se transmiten?',
        a: 'Datos de medición bioeléctricos y datos ambientales (temperatura, humedad, CO₂), además de información aproximada de ubicación.' },
      { q: '¿Qué ocurre con mis datos?',
        a: 'Se incorporan de forma anonimizada al conjunto de datos abierto (CC BY 4.0) y se usan para el reconocimiento de patrones asistido por IA. Todos los datos son de libre acceso.' },
      { q: '¿Cómo se protegen mis datos?',
        a: 'Las coordenadas GPS se redondean a 10×10 km. La anonimización se realiza localmente en tu dispositivo — ningún dato en bruto con ubicación exacta sale nunca de tu PC.' },
      { q: '¿Puedo ver y descargar mis propios datos de medición?',
        a: 'Sí — tienes acceso en todo momento a tus datos de medición y puedes consultarlos y exportarlos.' },
    ]},
    { cat: 'Otros', items: [
      { q: '¿Puede OpenMycoNet leer la mente o comunicarse con los hongos?',
        a: 'No. OpenMycoNet mide la actividad de señales eléctricas de redes biológicas y estudia patrones y respuestas a las condiciones ambientales. El objetivo no es "leer la mente", sino comprender mejor los procesos biológicos.' },
      { q: '¿Por qué hacéis esto?',
        a: 'Los suelos se encuentran entre los ecosistemas menos comprendidos de la Tierra. Con OpenMycoNet queremos contribuir, junto con la ciudadanía, a hacer visible la actividad biológica y comprenderla mejor a largo plazo.' },
    ]},
  ],
};

// ── UI-Strings (5 Sprachen) ────────────────────────────────────────────────
var UI_BY_LANG = {
  de: { title: 'Häufige <em>Fragen</em>', subtitle: 'Alles was du über OpenMycoNet wissen musst — von der Idee bis zur Messung.', placeholder: 'Frage suchen...', close: 'Schließen', footerText: 'Weitere Fragen? ', footerLink: 'Frag den Chatbot' },
  en: { title: 'Frequently Asked <em>Questions</em>', subtitle: 'Everything you need to know about OpenMycoNet — from the idea to the measurement.', placeholder: 'Search questions...', close: 'Close', footerText: 'More questions? ', footerLink: 'Ask the chatbot' },
  nl: { title: 'Veelgestelde <em>Vragen</em>', subtitle: 'Alles wat je moet weten over OpenMycoNet — van het idee tot de meting.', placeholder: 'Vraag zoeken...', close: 'Sluiten', footerText: 'Nog vragen? ', footerLink: 'Vraag het de chatbot' },
  fr: { title: 'Questions <em>Fréquentes</em>', subtitle: "Tout ce que vous devez savoir sur OpenMycoNet — de l'idée à la mesure.", placeholder: 'Rechercher une question...', close: 'Fermer', footerText: "D'autres questions ? ", footerLink: 'Demandez au chatbot' },
  es: { title: 'Preguntas <em>Frecuentes</em>', subtitle: 'Todo lo que necesitas saber sobre OpenMycoNet — desde la idea hasta la medición.', placeholder: 'Buscar pregunta...', close: 'Cerrar', footerText: '¿Más preguntas? ', footerLink: 'Pregunta al chatbot' },
};

// ── Styles ───────────────────────────────────────────────────────────────
var css = document.createElement('style');
css.textContent = '\
#omn-faq-fab {\
  position: fixed; bottom: 150px; right: 16px; z-index: 9998;\
  width: 48px; height: 48px; border-radius: 50%;\
  background: #013020; border: 1.5px solid #0a6040;\
  cursor: pointer; display: flex; align-items: center; justify-content: center;\
  box-shadow: 0 4px 20px rgba(110,232,126,0.12), 0 2px 8px rgba(0,0,0,0.5);\
  transition: border-color 0.3s, box-shadow 0.3s;\
  animation: faq-pulse 2.5s ease-in-out infinite;\
}\
#omn-faq-fab:hover {\
  border-color: #d4a030;\
  box-shadow: 0 4px 28px rgba(212,160,48,0.25), 0 2px 8px rgba(0,0,0,0.5);\
  animation: none;\
}\
@keyframes faq-pulse {\
  0%   { border-color: #0a6040; box-shadow: 0 0 0 0 rgba(212,160,48,0); }\
  50%  { border-color: #d4a030; box-shadow: 0 0 0 3px rgba(212,160,48,0.15); }\
  100% { border-color: #0a6040; box-shadow: 0 0 0 0 rgba(212,160,48,0); }\
}\
#omn-faq-fab svg { width: 24px; height: 24px; }\
\
#omn-faq-overlay {\
  display: none; position: fixed; bottom: 206px; right: 16px; z-index: 9998;\
  width: 370px; max-width: calc(100vw - 32px);\
  max-height: calc(100vh - 300px);\
  background: #024530; border: 1px solid #0a6040;\
  box-shadow: 0 8px 40px rgba(0,0,0,0.6), 0 0 20px rgba(10,96,64,0.15);\
  flex-direction: column; align-items: stretch;\
  overflow-y: auto; padding: 0;\
}\
#omn-faq-overlay.open { display: flex; }\
\
#omn-faq-panel {\
  width: 100%;\
  padding: 3rem 1.5rem 2rem;\
  margin: 0 auto;\
}\
\
#omn-faq-close {\
  position: absolute; top: 0.8rem; right: 1rem;\
  background: none; border: none; color: #e8f5e0;\
  font-size: 1.6rem; cursor: pointer; z-index: 1;\
  line-height: 1; opacity: 0.7; transition: opacity 0.2s;\
}\
#omn-faq-close:hover { opacity: 1; }\
\
.faq-header {\
  text-align: center; margin-bottom: 2.5rem;\
}\
.faq-header h2 {\
  font-family: "Playfair Display", Georgia, serif;\
  font-size: 2rem; font-weight: 400; color: #ffffff;\
  margin-bottom: 0.5rem; line-height: 1.2;\
}\
.faq-header h2 em { font-style: italic; color: #6ee87e; }\
.faq-header p {\
  font-family: "Lora", Georgia, serif;\
  font-size: 0.95rem; color: #a0c8a0; line-height: 1.7;\
}\
\
.faq-search {\
  width: 100%; padding: 0.75rem 1rem;\
  background: rgba(0,0,0,0.28); border: 1px solid #0a6040;\
  color: #e8f5e0; font-family: "Lora", Georgia, serif; font-size: 1rem;\
  outline: none; margin-bottom: 2rem; transition: border-color 0.2s;\
}\
.faq-search:focus { border-color: #6ee87e; }\
.faq-search::placeholder { color: #5a8a6a; }\
\
.faq-cat {\
  font-family: "Lora", Georgia, serif;\
  font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase;\
  color: #d4a030; margin-bottom: 1rem; margin-top: 2rem;\
  display: flex; align-items: center; gap: 10px;\
}\
.faq-cat::before {\
  content: ""; display: inline-block;\
  width: 20px; height: 1px; background: #d4a030;\
}\
\
.faq-item {\
  border: 1px solid #0a6040; margin-bottom: 4px;\
  background: rgba(0,0,0,0.22); transition: border-color 0.2s;\
}\
.faq-item.open { border-color: #0a7050; }\
.faq-item.hidden { display: none; }\
\
.faq-q {\
  display: flex; align-items: center; gap: 12px;\
  padding: 0.85rem 1rem; cursor: pointer; user-select: none;\
  font-family: "Lora", Georgia, serif; font-size: 0.95rem;\
  color: #e8f5e0; line-height: 1.5;\
}\
.faq-q:hover { color: #6ee87e; }\
.faq-item.open .faq-q { color: #6ee87e; }\
\
.faq-chevron {\
  margin-left: auto; font-size: 0.8rem; color: #5a8a6a;\
  transition: transform 0.25s; flex-shrink: 0;\
}\
.faq-item.open .faq-chevron { transform: rotate(180deg); color: #6ee87e; }\
\
.faq-a {\
  display: none; margin: 0 1rem 1rem 1rem; padding: 0.85rem 1rem;\
  background: #ffffff; border-radius: 3px;\
  font-family: "Lora", Georgia, serif; font-size: 0.9rem;\
  color: #1a1a1a; line-height: 1.75;\
}\
.faq-item.open .faq-a { display: block; }\
\
.faq-num {\
  font-family: "Lora", Georgia, serif;\
  font-size: 0.7rem; color: #5a8a6a;\
  min-width: 22px; text-align: right; flex-shrink: 0;\
}\
\
.faq-footer {\
  margin-top: 2.5rem; padding-top: 1.5rem;\
  border-top: 1px solid #0a6040;\
  text-align: center;\
  font-family: "Lora", Georgia, serif;\
  font-size: 0.85rem; color: #a0c8a0;\
}\
.faq-footer a { color: #6ee87e; text-decoration: none; }\
.faq-footer a:hover { text-decoration: underline; }\
\
@media (max-width: 600px) {\
  #omn-faq-panel { padding: 4rem 1.25rem 3rem; }\
  #omn-faq-fab { bottom: 80px; right: 12px; width: 44px; height: 44px; }\
  .faq-header h2 { font-size: 1.5rem; }\
}';
document.head.appendChild(css);

// ── FAB Button ───────────────────────────────────────────────────────────
var fab = document.createElement('div');
fab.id = 'omn-faq-fab';
fab.title = 'FAQ';
fab.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="#d4a030" stroke-width="1.8" xmlns="http://www.w3.org/2000/svg">' +
  '<circle cx="12" cy="12" r="10"/>' +
  '<path d="M9 9c0-1.66 1.34-3 3-3s3 1.34 3 3c0 1.3-.84 2.4-2 2.82V13"/>' +
  '<circle cx="12" cy="16.5" r="0.8" fill="#d4a030" stroke="none"/>' +
  '</svg>';
document.body.appendChild(fab);

// ── Overlay (persistentes Skelett; Panel-Inhalt wird bei jedem OEffnen neu gerendert) ──
var overlay = document.createElement('div');
overlay.id = 'omn-faq-overlay';
overlay.innerHTML = '<button id="omn-faq-close" aria-label="Close">✕</button><div id="omn-faq-panel"></div>';
document.body.appendChild(overlay);

var panelEl = document.getElementById('omn-faq-panel');
var closeBtnEl = document.getElementById('omn-faq-close');

function renderFaqPanel(lang) {
  var ui = UI_BY_LANG[lang] || UI_BY_LANG.de;
  var faq = FAQ_BY_LANG[lang] || FAQ_BY_LANG.de;
  closeBtnEl.setAttribute('aria-label', ui.close);

  var headerHtml = '<div class="faq-header">' +
    '<h2>' + ui.title + '</h2>' +
    '<p>' + ui.subtitle + '</p>' +
    '</div>' +
    '<input type="text" class="faq-search" id="omn-faq-search" placeholder="' + ui.placeholder + '">';

  var contentHtml = '';
  var num = 1;
  faq.forEach(function(cat) {
    contentHtml += '<div class="faq-cat" data-cat="' + cat.cat + '">' + cat.cat + '</div>';
    cat.items.forEach(function(item) {
      contentHtml += '<div class="faq-item" data-q="' + item.q.toLowerCase() + '" data-a="' + item.a.toLowerCase() + '">' +
        '<div class="faq-q"><span class="faq-num">' + num + '.</span> ' + item.q + '<span class="faq-chevron">▾</span></div>' +
        '<div class="faq-a">' + item.a + '</div>' +
        '</div>';
      num++;
    });
  });

  var footerHtml = '<div class="faq-footer">' + ui.footerText +
    '<a href="javascript:void(0)" onclick="document.getElementById(\'omn-faq-overlay\').classList.remove(\'open\'); document.getElementById(\'omn-fab\').click();">' + ui.footerLink + '</a>' +
    '</div>';

  panelEl.innerHTML = headerHtml + contentHtml + footerHtml;
}

renderFaqPanel(getFaqLang());

// ── Events ───────────────────────────────────────────────────────────────
fab.addEventListener('click', function() {
  renderFaqPanel(getFaqLang());
  overlay.classList.add('open');
  document.body.style.overflow = 'hidden';
  setTimeout(function() {
    var s = document.getElementById('omn-faq-search');
    if (s) s.focus();
  }, 200);
});

closeBtnEl.addEventListener('click', function() {
  overlay.classList.remove('open');
  document.body.style.overflow = '';
});

overlay.addEventListener('click', function(e) {
  if (e.target === overlay) {
    overlay.classList.remove('open');
    document.body.style.overflow = '';
  }
});

// Akkordeon (delegiert auf overlay, funktioniert unabhaengig vom Panel-Rebuild)
overlay.addEventListener('click', function(e) {
  var q = e.target.closest('.faq-q');
  if (!q) return;
  var item = q.parentElement;
  var wasOpen = item.classList.contains('open');
  overlay.querySelectorAll('.faq-item').forEach(function(i) { i.classList.remove('open'); });
  if (!wasOpen) item.classList.add('open');
});

// Suche (delegiert, da #omn-faq-search bei jedem OEffnen neu erzeugt wird)
overlay.addEventListener('input', function(e) {
  if (e.target.id !== 'omn-faq-search') return;
  var term = e.target.value.toLowerCase().trim();
  var items = overlay.querySelectorAll('.faq-item');
  var cats = overlay.querySelectorAll('.faq-cat');

  if (!term) {
    items.forEach(function(i) { i.classList.remove('hidden'); });
    cats.forEach(function(c) { c.style.display = ''; });
    return;
  }

  var visibleCats = {};
  items.forEach(function(i) {
    var qText = i.getAttribute('data-q') || '';
    var aText = i.getAttribute('data-a') || '';
    if (qText.indexOf(term) !== -1 || aText.indexOf(term) !== -1) {
      i.classList.remove('hidden');
      var prev = i.previousElementSibling;
      while (prev && !prev.classList.contains('faq-cat')) prev = prev.previousElementSibling;
      if (prev) visibleCats[prev.getAttribute('data-cat')] = true;
    } else {
      i.classList.add('hidden');
      i.classList.remove('open');
    }
  });

  cats.forEach(function(c) {
    c.style.display = visibleCats[c.getAttribute('data-cat')] ? '' : 'none';
  });
});

// ESC to close
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape' && overlay.classList.contains('open')) {
    overlay.classList.remove('open');
    document.body.style.overflow = '';
  }
});

})();
