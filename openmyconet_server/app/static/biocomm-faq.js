/**
 * biocomm-faq.js — OpenMycoNet FAQ Overlay
 * Schwebendes FAQ-Widget, einbindbar auf allen Seiten via <script src="/biocomm-faq.js"></script>
 * Eigenstaendige Spracherkennung (unabhaengig vom Host-Seiten-Code) ueber denselben
 * localStorage-Key "omn_lang". Inhalt wird bei jedem OEffnen neu anhand der aktuellen
 * Sprache gerendert, damit ein Sprachwechsel waehrend des Seitenbesuchs erfasst wird.
 *
 * Inhaltsstand: an app/static/translations.json (Text-Redaktion) angeglichen.
 * Bei Aenderungen am Website-Text die betroffenen Antworten hier nachziehen.
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
        a: 'Ein weltweites Citizen-Science-Netzwerk, das elektrische Aktivität in Mykorrhiza- und Pilznetzwerken erfasst — zusammen mit den Umweltbedingungen am Messort. Die Aktivität ist messbar; die Frage ist, was ihre wiederkehrenden Muster bedeuten.' },
      { q: 'Wer steht hinter dem Projekt?',
        a: 'OpenMycoNet wurde von Robert Jank initiiert, einem unabhängigen Erfinder aus Maintal bei Frankfurt, ohne Institutszugehörigkeit. Die genutzte BioComm-Technologie umfasst geschützte technische Entwicklungen; Schutzrechte und Forschungsdaten bleiben strikt getrennt.' },
      { q: 'Was wird gemessen?',
        a: 'Elektrische Aktivität (Spannungsschwankungen) im Pilzmyzel und Mykorrhiza-Netzwerk, zusammen mit Umweltdaten wie Boden- und Lufttemperatur, Feuchtigkeit, elektrischer Leitfähigkeit und CO₂.' },
      { q: 'Wie und womit wird gemessen?',
        a: 'Mit dem BioComm-Messknoten — einer kompakten, eigenentwickelten Hardware auf ESP32-Basis mit 16-bit-Analog-Digital-Wandler und acht bioelektrischen Messkanälen, dazu Sensoren für Temperatur, Feuchtigkeit und Leitfähigkeit. Die Elektroden werden direkt ins Substrat (Boden, Topf, Kompost) gesteckt.' },
      { q: 'Kann BioComm auch elektrisch stimulieren?',
        a: 'Ja. BioComm ist bidirektional ausgelegt: Es kann definierte elektrische oder optische Reize gezielt ins Substrat einspeisen und anschließend messen, ob sich der Zustand verändert. Diese bidirektionale Stimulationsmethode ist eine eigene Entwicklung, geschützt durch ein erteiltes Gebrauchsmuster. Ob und wie das Myzel auf solche Reize reagiert, ist eine offene Forschungsfrage.' },
      { q: 'Wie kommunizieren die Sensor-Knoten mit der Zentrale?',
        a: 'Jeder Knoten sendet seine Messdaten per LoRa-Funk (Punkt-zu-Punkt, realistisch 1–3 km Reichweite im Wald) an eine BioComm Bridge in der Nähe. Die Bridge verbindet sich per WLAN mit der Zentrale und leitet die Daten weiter. Diese Funkanbindung ist Teil der aktuell in Entwicklung befindlichen Hardware-Generation und noch nicht ausgeliefert.' },
      { q: 'Wer kann mitmachen?',
        a: 'Die veröffentlichten Ergebnisse und offenen Datensätze des Netzwerks stehen allen offen — einen Knoten zu betreiben ist keine Voraussetzung. Einen eigenen BioComm-Knoten betreiben können aktuell nur ausgewählte Knotenbetreiber über eine kuratierte Bewerbung, da die Hardware begrenzt ist.' },
    ]},
    { cat: 'Projektstand', items: [
      { q: 'Wie weit ist das Projekt?',
        a: 'Die BioComm-Software läuft im Simulations- und Testbetrieb: Messdarstellung, Zuordnung von Umweltbedingungen, Dokumentation, Musteranalyse und kontrollierte Stimulation sind implementiert und lassen sich erproben. Die Knoten-Hardware durchläuft aktuell eine Design-Revision einschließlich LoRa-Integration; Hardware-/Software-Integration und Feldvalidierung folgen.' },
      { q: 'Kann ich schon einen Knoten bekommen?',
        a: 'Die Hardware ist noch in Entwicklung und begrenzt. Du kannst dich jetzt bewerben; bei hoher Nachfrage führen wir eine Warteliste und benachrichtigen dich per Mail, sobald ein Gerät verfügbar ist.' },
      { q: 'Gibt es schon Ergebnisse?',
        a: 'Nein. OpenMycoNet macht keine Wirkungsaussagen, bevor belastbare, wiederholt erhobene Daten vorliegen. Wir arbeiten ergebnisoffen und zeigen transparent, was gemessen wurde, was eine Analyse nahelegt und was sich daraus tatsächlich schließen lässt.' },
    ]},
    { cat: 'Teilnahme', items: [
      { q: 'Kann ich die Daten auch ohne eigenen Knoten sehen?',
        a: 'Ja — die veröffentlichten Ergebnisse und die für die Forschung vorgesehenen Datensätze stehen allen offen (CC BY 4.0), auch ohne eigenen Knoten. Ein Knoten ist nur nötig, wenn du selbst Messdaten beisteuern möchtest.' },
      { q: 'Wie kann ich Knotenbetreiber werden?',
        a: 'Über das Bewerbungsformular im Anmelde-Bereich — dort „Ja, ich bewerbe mich für einen Knoten" auswählen. Der Knotenbetrieb ist unabhängig von deiner Rolle im Netzwerk und eine zusätzliche Qualifikation nach kurzer Einführung. Vorausgesetzt werden ein geeigneter Standort mit Substrat, WLAN in der Nähe des geplanten Bridge-Standorts und grundlegende Handhabung von Hardware; ein fachlicher oder wissenschaftlicher Bezug ist von Vorteil, aber keine Voraussetzung.' },
      { q: 'Wie bekomme ich die Hardware?',
        a: 'Über das Leihprogramm gegen eine rückerstattbare Kaution (ca. 100 €, finale Kosten folgen). Da die Hardware noch in Entwicklung ist, erfolgt die Ausgabe nach Verfügbarkeit — bei hoher Nachfrage über eine Warteliste.' },
      { q: 'Welche Software brauche ich und wie bekomme ich sie?',
        a: 'Die BioComm-Software — kostenloser Download, keine Installation nötig. Sie wird nach der Registrierung bereitgestellt. Aktuell befindet sie sich im Simulations- und Testbetrieb.' },
      { q: 'Wo wird der Knoten am besten platziert?',
        a: 'Im Boden, Blumentopf oder Kompost mit Pilz- oder Mykorrhiza-Substrat. Die Elektroden werden direkt ins Substrat gesteckt, dauerhaft und wettergeschützt.' },
      { q: 'Welche Internetverbindung wird benötigt?',
        a: 'Der Knoten selbst braucht kein WLAN — er funkt seine Messdaten per LoRa an die BioComm Bridge. Die Bridge verbindet sich per WLAN mit der Zentrale und überträgt die Daten automatisch im Hintergrund. Diese Funkanbindung ist Teil der aktuell in Entwicklung befindlichen Hardware-Generation.' },
      { q: 'Was passiert, wenn keine Verbindung verfügbar ist?',
        a: 'Messungen bei fehlender Verbindung werden zwischengespeichert und automatisch übertragen, sobald wieder eine Verbindung besteht. Die genaue Ausgestaltung der Funkanbindung ist Teil der in Entwicklung befindlichen Hardware-Generation.' },
      { q: 'Was kostet die Teilnahme?',
        a: 'Die Teilnahme am Projekt ist grundsätzlich kostenlos. Nur wenn du einen Messknoten betreiben willst, fällt eine rückerstattbare Kaution von ca. 100 € an.' },
      { q: 'Welche Rollen gibt es — Mycelist, Hyphist, Sporist?',
        a: 'Mit der Registrierung wirst du Mycelist und damit Teil der OpenMycoNet-Community. Wer zusätzlich fachlich, wissenschaftlich, technisch oder strukturell kooperiert, kann Hyphist werden; wer das Projekt finanziell fördert, Sporist. Hyphist und Sporist schließen einander nicht aus. Keine dieser Rollen gibt Einfluss auf Forschungsergebnisse oder deren Interpretation.' },
    ]},
    { cat: 'Daten & Datenschutz', items: [
      { q: 'Welche Daten werden übertragen?',
        a: 'Bioelektrische Messdaten und Umweltdaten (Temperatur, Feuchtigkeit, Leitfähigkeit, CO₂) sowie eine grob gerasterte Standortinfo.' },
      { q: 'Was geschieht mit meinen Daten?',
        a: 'Für die Veröffentlichung vorgesehene Messdaten fließen zusammen mit den notwendigen, nicht personenbezogenen Kontextinformationen in den offenen Datensatz (CC BY 4.0) und dienen der Musteranalyse. Persönliche Angaben und dein genauer Standort werden nicht veröffentlicht. OpenMycoNet trennt Messdaten, persönliche Angaben und wissenschaftliche Interpretation klar voneinander.' },
      { q: 'Wie werden meine Daten geschützt?',
        a: 'GPS-Koordinaten werden auf 10×10 km vergröbert. Analyse und Anonymisierung laufen lokal auf deinem Gerät, bevor die Daten ans Netzwerk gehen — keine Rohdaten mit genauem Standort verlassen deinen PC.' },
      { q: 'Kann ich meine eigenen Messdaten sehen und herunterladen?',
        a: 'Ja — du hast jederzeit Zugriff auf deine Messdaten und kannst sie einsehen und exportieren.' },
    ]},
    { cat: 'Förderer & Kooperation', items: [
      { q: 'Kann mein Unternehmen OpenMycoNet unterstützen?',
        a: 'Ja, auf zwei Wegen: als Förderer (Sporist) mit einem frei wählbaren Jahresbeitrag ab 50 € und Eintrag auf der Fördererseite, oder als Kooperationspartner (Hyphist) mit Ressourcen wie Fachwissen, Infrastruktur, Reichweite oder technischer Unterstützung statt Geld. Beide Formen werden vor der Veröffentlichung geprüft. Details und Formulare unter openmyconet.de/foerderer.' },
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
        a: 'A global citizen science network that records electrical activity in mycorrhizal and fungal networks — together with the environmental conditions at the measurement site. The activity is measurable; the question is what its recurring patterns mean.' },
      { q: 'Who is behind the project?',
        a: 'OpenMycoNet was initiated by Robert Jank, an independent inventor from Maintal near Frankfurt, without institutional affiliation. The BioComm technology used includes protected technical developments; intellectual property and research data are kept strictly separate.' },
      { q: 'What is being measured?',
        a: 'Electrical activity (voltage fluctuations) in fungal mycelium and mycorrhizal networks, together with environmental data such as soil and air temperature, humidity, electrical conductivity and CO₂.' },
      { q: 'How and with what is it measured?',
        a: 'With the BioComm measurement node — compact, in-house-developed hardware based on ESP32 with a 16-bit analog-to-digital converter and eight bioelectrical channels, plus sensors for temperature, humidity and conductivity. The electrodes are inserted directly into the substrate (soil, pot, compost).' },
      { q: 'Can BioComm also apply electrical stimulation?',
        a: 'Yes. BioComm is designed to work in both directions: it can feed defined electrical or optical stimuli into the substrate and then measure whether the state changes. This bidirectional stimulation method is an in-house development, protected by a granted utility model. Whether and how the mycelium responds to such stimuli is an open research question.' },
      { q: 'How do the sensor nodes communicate with the central server?',
        a: 'Each node sends its measurement data via LoRa radio (point-to-point, realistically 1–3 km range in forest terrain) to a nearby BioComm Bridge. The Bridge connects to the central server via WiFi and forwards the data. This radio link is part of the hardware generation currently in development and has not yet shipped.' },
      { q: 'Who can take part?',
        a: 'The published results and open datasets of the network are open to everyone — operating a node is not a requirement. Operating your own BioComm node is currently limited to selected node operators via a curated application, since hardware is limited.' },
    ]},
    { cat: 'Project status', items: [
      { q: 'How far along is the project?',
        a: 'The BioComm software runs in simulation and test mode: signal display, assignment of environmental conditions, documentation, pattern analysis and controlled stimulation are implemented and can be tried out. The node hardware is currently undergoing a design revision including LoRa integration; hardware/software integration and field validation follow.' },
      { q: 'Can I get a node already?',
        a: 'The hardware is still in development and limited. You can apply now; if demand is high we maintain a waiting list and will notify you by email as soon as a device becomes available.' },
      { q: 'Are there results yet?',
        a: 'No. OpenMycoNet makes no claims about effects before robust, repeatedly collected data is available. We work with an open outcome and show transparently what was measured, what an analysis suggests and what can actually be concluded from it.' },
    ]},
    { cat: 'Participation', items: [
      { q: 'Can I see the data without operating my own node?',
        a: 'Yes — the published results and the datasets intended for research are open to everyone (CC BY 4.0), even without your own node. A node is only needed if you want to contribute measurement data yourself.' },
      { q: 'How can I become a node operator?',
        a: 'Via the application form in the registration area — select "Yes, I\'m applying for a node" there. Operating a node is independent of your role in the network and an additional qualification after a short introduction. A suitable location with substrate, WiFi near the planned Bridge site and basic hardware handling are required; a professional or scientific background is an advantage but not a requirement.' },
      { q: 'How do I get the hardware?',
        a: 'Through the loan programme against a refundable deposit (approx. €100, final costs to follow). Since the hardware is still in development, devices are issued as they become available — via a waiting list when demand is high.' },
      { q: 'What software do I need and how do I get it?',
        a: 'The BioComm software — free download, no installation required. It is provided after registration. It is currently in simulation and test mode.' },
      { q: 'Where is the best place to position the node?',
        a: 'In soil, a plant pot or compost with fungal or mycorrhizal substrate. The electrodes are inserted directly into the substrate, permanently and weather-protected.' },
      { q: 'What internet connection is required?',
        a: "The node itself doesn't need WiFi — it transmits its measurement data to the BioComm Bridge via LoRa. The Bridge connects to the central server via WiFi and transmits the data automatically in the background. This radio link is part of the hardware generation currently in development." },
      { q: 'What happens if no connection is available?',
        a: 'Measurements taken while there is no connection are cached and transmitted automatically once a connection is available again. The exact design of the radio link is part of the hardware generation currently in development.' },
      { q: 'What does participation cost?',
        a: 'Participating in the project is fundamentally free. Only if you want to operate a measurement node is there a refundable deposit of approx. €100.' },
      { q: 'What are the roles — Mycelist, Hyphist, Sporist?',
        a: 'By registering you become a Mycelist and thus part of the OpenMycoNet community. Anyone who additionally cooperates professionally, scientifically, technically or structurally can become a Hyphist; anyone who supports the project financially, a Sporist. Hyphist and Sporist are not mutually exclusive. None of these roles gives any influence over research results or their interpretation.' },
    ]},
    { cat: 'Data & privacy', items: [
      { q: 'What data is transmitted?',
        a: 'Bioelectrical measurement data and environmental data (temperature, humidity, conductivity, CO₂), plus coarsely gridded location information.' },
      { q: 'What happens to my data?',
        a: 'Measurement data intended for publication flows, together with the necessary non-personal context information, into the open dataset (CC BY 4.0) and is used for pattern analysis. Personal details and your exact location are not published. OpenMycoNet clearly separates measurement data, personal information and scientific interpretation.' },
      { q: 'How is my data protected?',
        a: 'GPS coordinates are coarsened to 10×10 km. Analysis and anonymisation run locally on your device before the data goes to the network — no raw data with an exact location ever leaves your PC.' },
      { q: 'Can I view and download my own measurement data?',
        a: 'Yes — you have access to your measurement data at any time and can view and export it.' },
    ]},
    { cat: 'Supporters & cooperation', items: [
      { q: 'Can my company support OpenMycoNet?',
        a: 'Yes, in two ways: as a supporter (Sporist) with a freely chosen annual contribution from €50 and an entry on the supporters page, or as a cooperation partner (Hyphist) contributing resources such as expertise, infrastructure, reach or technical support instead of money. Both forms are reviewed before publication. Details and forms at openmyconet.de/foerderer.' },
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
        a: 'Een wereldwijd citizen science-netwerk dat elektrische activiteit in mycorrhiza- en schimmelnetwerken registreert — samen met de omgevingsomstandigheden op de meetlocatie. De activiteit is meetbaar; de vraag is wat de terugkerende patronen ervan betekenen.' },
      { q: 'Wie staat er achter het project?',
        a: 'OpenMycoNet werd geïnitieerd door Robert Jank, een onafhankelijk uitvinder uit Maintal bij Frankfurt, zonder institutionele binding. De gebruikte BioComm-technologie omvat beschermde technische ontwikkelingen; beschermingsrechten en onderzoeksdata blijven strikt gescheiden.' },
      { q: 'Wat wordt er gemeten?',
        a: 'Elektrische activiteit (spanningsschommelingen) in schimmelmycelium en mycorrhizanetwerken, samen met omgevingsgegevens zoals bodem- en luchttemperatuur, vochtigheid, elektrische geleidbaarheid en CO₂.' },
      { q: 'Hoe en waarmee wordt er gemeten?',
        a: 'Met de BioComm-meetknoop — compacte, zelf ontwikkelde hardware op ESP32-basis met een 16-bit analoog-digitaalomzetter en acht bio-elektrische kanalen, plus sensoren voor temperatuur, vochtigheid en geleidbaarheid. De elektroden worden direct in het substraat (bodem, pot, compost) gestoken.' },
      { q: 'Kan BioComm ook elektrisch stimuleren?',
        a: 'Ja. BioComm werkt in beide richtingen: het kan gedefinieerde elektrische of optische prikkels in het substraat brengen en daarna meten of de toestand verandert. Deze bidirectionele stimulatiemethode is een eigen ontwikkeling, beschermd door een verleend gebruiksmodel. Of en hoe het mycelium op zulke prikkels reageert, is een open onderzoeksvraag.' },
      { q: 'Hoe communiceren de sensorknopen met de centrale?',
        a: 'Elke node stuurt zijn meetgegevens via LoRa-radio (punt-tot-punt, realistisch 1–3 km bereik in bosgebied) naar een nabijgelegen BioComm Bridge. De Bridge verbindt via wifi met de centrale server en stuurt de gegevens door. Deze radioverbinding maakt deel uit van de hardwaregeneratie die momenteel in ontwikkeling is en nog niet is uitgeleverd.' },
      { q: 'Wie kan meedoen?',
        a: 'De gepubliceerde resultaten en open datasets van het netwerk zijn voor iedereen toegankelijk — een node beheren is geen voorwaarde. Een eigen BioComm-node beheren kan momenteel alleen via geselecteerde knooppuntbeheerders na een gecureerde sollicitatie, omdat de hardware beperkt is.' },
    ]},
    { cat: 'Projectstatus', items: [
      { q: 'Hoe ver is het project?',
        a: 'De BioComm-software draait in simulatie- en testmodus: signaalweergave, koppeling van omgevingsomstandigheden, documentatie, patroonanalyse en gecontroleerde stimulatie zijn geïmplementeerd en kunnen worden uitgeprobeerd. De node-hardware ondergaat momenteel een ontwerprevisie inclusief LoRa-integratie; hardware-/software-integratie en veldvalidatie volgen.' },
      { q: 'Kan ik al een node krijgen?',
        a: 'De hardware is nog in ontwikkeling en beperkt. Je kunt je nu aanmelden; bij grote vraag hanteren we een wachtlijst en informeren we je per e-mail zodra er een apparaat beschikbaar is.' },
      { q: 'Zijn er al resultaten?',
        a: 'Nee. OpenMycoNet doet geen uitspraken over effecten voordat er robuuste, herhaaldelijk verzamelde data beschikbaar is. We werken met een open uitkomst en tonen transparant wat er is gemeten, wat een analyse suggereert en wat daaruit daadwerkelijk kan worden geconcludeerd.' },
    ]},
    { cat: 'Deelname', items: [
      { q: 'Kan ik de gegevens ook zonder eigen node zien?',
        a: 'Ja — de gepubliceerde resultaten en de datasets die voor onderzoek zijn bedoeld, zijn voor iedereen toegankelijk (CC BY 4.0), ook zonder eigen node. Een node is alleen nodig als je zelf meetgegevens wilt bijdragen.' },
      { q: 'Hoe kan ik knooppuntbeheerder worden?',
        a: 'Via het sollicitatieformulier in het aanmeldgedeelte — selecteer daar "Ja, ik solliciteer voor een node". Het beheren van een node staat los van je rol in het netwerk en is een extra kwalificatie na een korte introductie. Een geschikte locatie met substraat, wifi in de buurt van de geplande Bridge-locatie en basiskennis van hardware zijn vereist; een vakinhoudelijke of wetenschappelijke achtergrond is een pré, maar geen vereiste.' },
      { q: 'Hoe krijg ik de hardware?',
        a: 'Via het leenprogramma tegen een terugbetaalbare borg (ca. €100, definitieve kosten volgen). Omdat de hardware nog in ontwikkeling is, worden apparaten uitgegeven zodra ze beschikbaar zijn — bij grote vraag via een wachtlijst.' },
      { q: 'Welke software heb ik nodig en hoe krijg ik die?',
        a: 'De BioComm-software — gratis download, geen installatie nodig. Deze wordt na registratie beschikbaar gesteld. Momenteel bevindt hij zich in simulatie- en testmodus.' },
      { q: 'Waar plaats ik de node het beste?',
        a: 'In de bodem, een bloempot of compost met schimmel- of mycorrhizasubstraat. De elektroden worden direct in het substraat gestoken, duurzaam en weerbestendig.' },
      { q: 'Welke internetverbinding is nodig?',
        a: 'De node zelf heeft geen wifi nodig — hij zendt zijn meetgegevens via LoRa naar de BioComm Bridge. De Bridge verbindt via wifi met de centrale server en stuurt de gegevens automatisch op de achtergrond door. Deze radioverbinding maakt deel uit van de hardwaregeneratie die momenteel in ontwikkeling is.' },
      { q: 'Wat gebeurt er als er geen verbinding beschikbaar is?',
        a: 'Metingen zonder verbinding worden tijdelijk opgeslagen en automatisch verzonden zodra er weer verbinding is. De exacte uitwerking van de radioverbinding maakt deel uit van de hardwaregeneratie die in ontwikkeling is.' },
      { q: 'Wat kost deelname?',
        a: 'Deelname aan het project is in principe gratis. Alleen als je een meetknoop wilt beheren, geldt een terugbetaalbare borg van ca. €100.' },
      { q: 'Welke rollen zijn er — Mycelist, Hyphist, Sporist?',
        a: 'Met je registratie word je Mycelist en daarmee deel van de OpenMycoNet-community. Wie daarnaast vakinhoudelijk, wetenschappelijk, technisch of structureel samenwerkt, kan Hyphist worden; wie het project financieel steunt, Sporist. Hyphist en Sporist sluiten elkaar niet uit. Geen van deze rollen geeft invloed op onderzoeksresultaten of de interpretatie ervan.' },
    ]},
    { cat: 'Gegevens & privacy', items: [
      { q: 'Welke gegevens worden verzonden?',
        a: 'Bio-elektrische meetgegevens en omgevingsgegevens (temperatuur, vochtigheid, geleidbaarheid, CO₂), plus grof gerasterde locatie-informatie.' },
      { q: 'Wat gebeurt er met mijn gegevens?',
        a: 'Voor publicatie bestemde meetgegevens vloeien samen met de noodzakelijke, niet-persoonlijke contextinformatie in de open dataset (CC BY 4.0) en dienen voor patroonanalyse. Persoonlijke gegevens en je exacte locatie worden niet gepubliceerd. OpenMycoNet houdt meetdata, persoonlijke gegevens en wetenschappelijke interpretatie duidelijk gescheiden.' },
      { q: 'Hoe worden mijn gegevens beschermd?',
        a: 'GPS-coördinaten worden vergroot naar 10×10 km. Analyse en anonimisering gebeuren lokaal op je apparaat voordat de gegevens naar het netwerk gaan — geen ruwe data met exacte locatie verlaat ooit je pc.' },
      { q: 'Kan ik mijn eigen meetgegevens bekijken en downloaden?',
        a: 'Ja — je hebt altijd toegang tot je meetgegevens en kunt ze bekijken en exporteren.' },
    ]},
    { cat: 'Sponsors & samenwerking', items: [
      { q: 'Kan mijn bedrijf OpenMycoNet steunen?',
        a: 'Ja, op twee manieren: als sponsor (Sporist) met een vrij te kiezen jaarbijdrage vanaf €50 en een vermelding op de partnerspagina, of als samenwerkingspartner (Hyphist) met middelen zoals expertise, infrastructuur, bereik of technische ondersteuning in plaats van geld. Beide vormen worden vóór publicatie beoordeeld. Details en formulieren op openmyconet.de/foerderer.' },
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
        a: "Un réseau mondial de science citoyenne qui enregistre l'activité électrique dans les réseaux mycorhiziens et fongiques — ainsi que les conditions environnementales sur le site de mesure. L'activité est mesurable ; la question est ce que signifient ses motifs récurrents." },
      { q: 'Qui est derrière le projet ?',
        a: "OpenMycoNet a été initié par Robert Jank, inventeur indépendant de Maintal près de Francfort, sans appartenance institutionnelle. La technologie BioComm utilisée comprend des développements techniques protégés ; les droits de protection et les données de recherche restent strictement séparés." },
      { q: 'Que mesure-t-on ?',
        a: "L'activité électrique (variations de tension) dans le mycélium fongique et les réseaux mycorhiziens, ainsi que des données environnementales telles que la température du sol et de l'air, l'humidité, la conductivité électrique et le CO₂." },
      { q: 'Comment et avec quoi mesure-t-on ?',
        a: "Avec le nœud de mesure BioComm — un matériel compact développé en interne, basé sur ESP32, doté d'un convertisseur analogique-numérique 16 bits et de huit canaux bioélectriques, plus des capteurs de température, d'humidité et de conductivité. Les électrodes sont insérées directement dans le substrat (sol, pot, compost)." },
      { q: 'BioComm peut-il aussi appliquer une stimulation électrique ?',
        a: "Oui. BioComm est conçu pour fonctionner dans les deux sens : il peut injecter des stimuli électriques ou optiques définis dans le substrat, puis mesurer si l'état change. Cette méthode de stimulation bidirectionnelle est un développement propre, protégé par un modèle d'utilité délivré. La question de savoir si et comment le mycélium réagit à de tels stimuli reste ouverte." },
      { q: 'Comment les nœuds capteurs communiquent-ils avec le serveur central ?',
        a: "Chaque nœud envoie ses données de mesure par radio LoRa (point à point, portée réaliste de 1 à 3 km en forêt) à un BioComm Bridge à proximité. Le Bridge se connecte au serveur central via WiFi et transmet les données. Cette liaison radio fait partie de la génération de matériel actuellement en développement et n'a pas encore été livrée." },
      { q: 'Qui peut participer ?',
        a: "Les résultats publiés et les jeux de données ouverts du réseau sont accessibles à tous — exploiter un nœud n'est pas une condition. L'exploitation de son propre nœud BioComm est actuellement réservée à des exploitants sélectionnés via une candidature encadrée, le matériel étant limité." },
    ]},
    { cat: 'État du projet', items: [
      { q: 'Où en est le projet ?',
        a: "Le logiciel BioComm fonctionne en mode simulation et test : affichage des signaux, association des conditions environnementales, documentation, analyse de motifs et stimulation contrôlée sont implémentés et peuvent être essayés. Le matériel des nœuds fait actuellement l'objet d'une révision de conception, y compris l'intégration LoRa ; l'intégration matériel/logiciel et la validation sur le terrain suivront." },
      { q: 'Puis-je déjà obtenir un nœud ?',
        a: "Le matériel est encore en développement et limité. Vous pouvez postuler dès maintenant ; en cas de forte demande, nous tenons une liste d'attente et vous informons par e-mail dès qu'un appareil est disponible." },
      { q: 'Y a-t-il déjà des résultats ?',
        a: "Non. OpenMycoNet ne fait aucune affirmation sur des effets avant de disposer de données solides et collectées de manière répétée. Nous travaillons à résultat ouvert et montrons de manière transparente ce qui a été mesuré, ce qu'une analyse suggère et ce qu'on peut réellement en conclure." },
    ]},
    { cat: 'Participation', items: [
      { q: 'Puis-je voir les données sans exploiter mon propre nœud ?',
        a: "Oui — les résultats publiés et les jeux de données destinés à la recherche sont accessibles à tous (CC BY 4.0), même sans nœud personnel. Un nœud n'est nécessaire que si vous souhaitez contribuer vous-même des données de mesure." },
      { q: 'Comment devenir exploitant de nœud ?',
        a: "Via le formulaire de candidature dans l'espace d'inscription — sélectionnez-y « Oui, je candidate pour un nœud ». L'exploitation d'un nœud est indépendante de votre rôle dans le réseau et constitue une qualification supplémentaire après une brève introduction. Un emplacement adapté avec substrat, un WiFi à proximité de l'emplacement prévu pour le Bridge et une manipulation de base du matériel sont requis ; un profil professionnel ou scientifique est un atout, mais pas une condition." },
      { q: 'Comment obtenir le matériel ?',
        a: "Via le programme de prêt, moyennant une caution remboursable (environ 100 €, coûts définitifs à venir). Le matériel étant encore en développement, les appareils sont remis au fur et à mesure de leur disponibilité — via une liste d'attente en cas de forte demande." },
      { q: 'De quel logiciel ai-je besoin et comment l\'obtenir ?',
        a: "Le logiciel BioComm — téléchargement gratuit, aucune installation requise. Il est fourni après l'inscription. Il est actuellement en mode simulation et test." },
      { q: 'Où placer le nœud au mieux ?',
        a: 'Dans le sol, un pot de fleurs ou du compost contenant un substrat fongique ou mycorhizien. Les électrodes sont insérées directement dans le substrat, de manière durable et protégée des intempéries.' },
      { q: 'Quelle connexion internet est nécessaire ?',
        a: "Le nœud lui-même n'a pas besoin de WiFi — il transmet ses données de mesure au BioComm Bridge via LoRa. Le Bridge se connecte au serveur central via WiFi et transmet automatiquement les données en arrière-plan. Cette liaison radio fait partie de la génération de matériel actuellement en développement." },
      { q: "Que se passe-t-il en l'absence de connexion ?",
        a: "Les mesures effectuées sans connexion sont mises en cache et transmises automatiquement dès qu'une connexion est de nouveau disponible. La conception exacte de la liaison radio fait partie de la génération de matériel en développement." },
      { q: 'Quel est le coût de la participation ?',
        a: "La participation au projet est fondamentalement gratuite. Une caution remboursable d'environ 100 € n'est due que si vous souhaitez exploiter un nœud de mesure." },
      { q: 'Quels sont les rôles — Mycelist, Hyphist, Sporist ?',
        a: "En vous inscrivant, vous devenez Mycelist et donc membre de la communauté OpenMycoNet. Toute personne qui coopère en outre sur le plan professionnel, scientifique, technique ou structurel peut devenir Hyphist ; toute personne qui soutient le projet financièrement, Sporist. Hyphist et Sporist ne s'excluent pas. Aucun de ces rôles ne donne d'influence sur les résultats de recherche ou leur interprétation." },
    ]},
    { cat: 'Données & confidentialité', items: [
      { q: 'Quelles données sont transmises ?',
        a: "Les données de mesure bioélectriques et les données environnementales (température, humidité, conductivité, CO₂), ainsi qu'une localisation approximative sur grille." },
      { q: 'Que deviennent mes données ?',
        a: "Les données de mesure destinées à la publication sont intégrées, avec les informations de contexte non personnelles nécessaires, dans le jeu de données ouvert (CC BY 4.0) et servent à l'analyse de motifs. Les informations personnelles et votre localisation précise ne sont pas publiées. OpenMycoNet distingue clairement les données de mesure, les informations personnelles et l'interprétation scientifique." },
      { q: 'Comment mes données sont-elles protégées ?',
        a: "Les coordonnées GPS sont dégradées à 10×10 km. L'analyse et l'anonymisation s'effectuent localement sur votre appareil avant que les données ne partent vers le réseau — aucune donnée brute avec une localisation précise ne quitte jamais votre PC." },
      { q: 'Puis-je consulter et télécharger mes propres données de mesure ?',
        a: 'Oui — vous avez accès à tout moment à vos données de mesure et pouvez les consulter et les exporter.' },
    ]},
    { cat: 'Partenaires & coopération', items: [
      { q: 'Mon entreprise peut-elle soutenir OpenMycoNet ?',
        a: "Oui, de deux façons : en tant que partenaire (Sporist) avec une cotisation annuelle librement choisie à partir de 50 € et une inscription sur la page des partenaires, ou en tant que partenaire de coopération (Hyphist) apportant des ressources telles que savoir-faire, infrastructure, rayonnement ou soutien technique plutôt que de l'argent. Les deux formes sont examinées avant publication. Détails et formulaires sur openmyconet.de/foerderer." },
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
        a: 'Una red mundial de ciencia ciudadana que registra actividad eléctrica en redes micorrícicas y fúngicas — junto con las condiciones ambientales del lugar de medición. La actividad es medible; la pregunta es qué significan sus patrones recurrentes.' },
      { q: '¿Quién está detrás del proyecto?',
        a: 'OpenMycoNet fue iniciado por Robert Jank, un inventor independiente de Maintal, cerca de Fráncfort, sin afiliación institucional. La tecnología BioComm utilizada incluye desarrollos técnicos protegidos; los derechos de protección y los datos de investigación se mantienen estrictamente separados.' },
      { q: '¿Qué se mide?',
        a: 'Actividad eléctrica (fluctuaciones de voltaje) en el micelio fúngico y las redes micorrícicas, junto con datos ambientales como la temperatura del suelo y del aire, la humedad, la conductividad eléctrica y el CO₂.' },
      { q: '¿Cómo y con qué se mide?',
        a: 'Con el nodo de medición BioComm — hardware compacto desarrollado internamente, basado en ESP32, con un convertidor analógico-digital de 16 bits y ocho canales bioeléctricos, además de sensores de temperatura, humedad y conductividad. Los electrodos se insertan directamente en el sustrato (suelo, maceta, compost).' },
      { q: '¿BioComm también puede aplicar estimulación eléctrica?',
        a: 'Sí. BioComm está diseñado para funcionar en ambos sentidos: puede introducir estímulos eléctricos u ópticos definidos en el sustrato y luego medir si el estado cambia. Este método de estimulación bidireccional es un desarrollo propio, protegido por un modelo de utilidad concedido. Si el micelio responde a tales estímulos, y cómo lo hace, es una cuestión de investigación abierta.' },
      { q: '¿Cómo se comunican los nodos sensores con la central?',
        a: 'Cada nodo envía sus datos de medición por radio LoRa (punto a punto, con un alcance realista de 1 a 3 km en bosque) a un BioComm Bridge cercano. El Bridge se conecta a la central por WiFi y reenvía los datos. Este enlace de radio forma parte de la generación de hardware actualmente en desarrollo y aún no se ha distribuido.' },
      { q: '¿Quién puede participar?',
        a: 'Los resultados publicados y los conjuntos de datos abiertos de la red están abiertos a todos — operar un nodo no es un requisito. Actualmente, operar tu propio nodo BioComm solo es posible para operadores seleccionados mediante una solicitud curada, ya que el hardware es limitado.' },
    ]},
    { cat: 'Estado del proyecto', items: [
      { q: '¿En qué punto está el proyecto?',
        a: 'El software BioComm funciona en modo de simulación y prueba: la visualización de señales, la asignación de condiciones ambientales, la documentación, el análisis de patrones y la estimulación controlada están implementados y pueden probarse. El hardware de los nodos está actualmente en una revisión de diseño, incluida la integración de LoRa; la integración de hardware/software y la validación de campo vendrán después.' },
      { q: '¿Ya puedo conseguir un nodo?',
        a: 'El hardware todavía está en desarrollo y es limitado. Puedes solicitarlo ahora; si la demanda es alta, mantenemos una lista de espera y te avisamos por correo en cuanto haya un dispositivo disponible.' },
      { q: '¿Ya hay resultados?',
        a: 'No. OpenMycoNet no hace afirmaciones sobre efectos antes de disponer de datos sólidos y recopilados de forma repetida. Trabajamos con un resultado abierto y mostramos de forma transparente qué se midió, qué sugiere un análisis y qué se puede concluir realmente de ello.' },
    ]},
    { cat: 'Participación', items: [
      { q: '¿Puedo ver los datos sin tener mi propio nodo?',
        a: 'Sí — los resultados publicados y los conjuntos de datos destinados a la investigación están abiertos a todos (CC BY 4.0), incluso sin nodo propio. Un nodo solo es necesario si quieres aportar datos de medición tú mismo.' },
      { q: '¿Cómo puedo convertirme en operador de nodo?',
        a: 'A través del formulario de solicitud en el área de registro — selecciona ahí "Sí, quiero solicitar un nodo". Operar un nodo es independiente de tu rol en la red y es una cualificación adicional tras una breve introducción. Se requiere una ubicación adecuada con sustrato, WiFi cerca de la ubicación prevista del Bridge y un manejo básico del hardware; contar con un perfil profesional o científico es una ventaja, pero no un requisito.' },
      { q: '¿Cómo consigo el hardware?',
        a: 'A través del programa de préstamo, mediante un depósito reembolsable (aprox. 100 €, costes definitivos por confirmar). Como el hardware todavía está en desarrollo, los dispositivos se entregan a medida que están disponibles — mediante una lista de espera si la demanda es alta.' },
      { q: '¿Qué software necesito y cómo lo obtengo?',
        a: 'El software BioComm — descarga gratuita, sin instalación. Se proporciona tras el registro. Actualmente se encuentra en modo de simulación y prueba.' },
      { q: '¿Dónde es mejor colocar el nodo?',
        a: 'En el suelo, una maceta o compost con sustrato fúngico o micorrícico. Los electrodos se insertan directamente en el sustrato, de forma permanente y protegida de la intemperie.' },
      { q: '¿Qué conexión a internet se necesita?',
        a: 'El nodo en sí no necesita WiFi — transmite sus datos de medición al BioComm Bridge por LoRa. El Bridge se conecta a la central por WiFi y transmite los datos automáticamente en segundo plano. Este enlace de radio forma parte de la generación de hardware actualmente en desarrollo.' },
      { q: '¿Qué ocurre si no hay conexión disponible?',
        a: 'Las mediciones realizadas sin conexión se almacenan temporalmente y se transmiten automáticamente en cuanto vuelve a haber conexión. El diseño exacto del enlace de radio forma parte de la generación de hardware en desarrollo.' },
      { q: '¿Cuánto cuesta participar?',
        a: 'Participar en el proyecto es, en principio, gratuito. Solo si quieres operar un nodo de medición se aplica un depósito reembolsable de aprox. 100 €.' },
      { q: '¿Qué roles hay — Mycelist, Hyphist, Sporist?',
        a: 'Al registrarte te conviertes en Mycelist y, por tanto, en parte de la comunidad de OpenMycoNet. Quien además coopera profesional, científica, técnica o estructuralmente puede convertirse en Hyphist; quien apoya el proyecto económicamente, en Sporist. Hyphist y Sporist no se excluyen. Ninguno de estos roles da influencia sobre los resultados de la investigación ni sobre su interpretación.' },
    ]},
    { cat: 'Datos y privacidad', items: [
      { q: '¿Qué datos se transmiten?',
        a: 'Datos de medición bioeléctricos y datos ambientales (temperatura, humedad, conductividad, CO₂), además de información de ubicación en una cuadrícula aproximada.' },
      { q: '¿Qué ocurre con mis datos?',
        a: 'Los datos de medición destinados a la publicación se incorporan, junto con la información de contexto no personal necesaria, al conjunto de datos abierto (CC BY 4.0) y se usan para el análisis de patrones. Los datos personales y tu ubicación exacta no se publican. OpenMycoNet separa claramente los datos de medición, la información personal y la interpretación científica.' },
      { q: '¿Cómo se protegen mis datos?',
        a: 'Las coordenadas GPS se redondean a 10×10 km. El análisis y la anonimización se realizan localmente en tu dispositivo antes de que los datos se envíen a la red — ningún dato en bruto con ubicación exacta sale nunca de tu PC.' },
      { q: '¿Puedo ver y descargar mis propios datos de medición?',
        a: 'Sí — tienes acceso en todo momento a tus datos de medición y puedes consultarlos y exportarlos.' },
    ]},
    { cat: 'Patrocinadores y cooperación', items: [
      { q: '¿Puede mi empresa apoyar a OpenMycoNet?',
        a: 'Sí, de dos maneras: como patrocinador (Sporist) con una cuota anual de libre elección desde 50 € y una entrada en la página de patrocinadores, o como socio de cooperación (Hyphist) aportando recursos como conocimientos, infraestructura, alcance o apoyo técnico en lugar de dinero. Ambas formas se revisan antes de su publicación. Detalles y formularios en openmyconet.de/foerderer.' },
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
var faqCssLink = document.createElement('link');
faqCssLink.rel = 'stylesheet';
faqCssLink.href = '/biocomm-faq.css';
document.head.appendChild(faqCssLink);

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
    '<a href="#" class="faq-to-chat">' + ui.footerLink + '</a>' +
    '</div>';

  panelEl.innerHTML = headerHtml + contentHtml + footerHtml;
}

renderFaqPanel(getFaqLang());

// ── Events ───────────────────────────────────────────────────────────────
fab.addEventListener('click', function() {
  // Chat-Widget schliessen, falls offen -- beide teilen sich Bildschirmbereich
  // und z-index; nie beide gleichzeitig offen.
  var chatWidget = document.getElementById('omn-widget');
  if (chatWidget && chatWidget.classList.contains('omn-open')) {
    var chatFab = document.getElementById('omn-fab');
    if (chatFab) chatFab.click();   // sauberer Toggle-Weg (setzt isOpen zurueck)
  }
  renderFaqPanel(getFaqLang());
  overlay.classList.add('open');
  document.body.classList.add('u-no-scroll');
  setTimeout(function() {
    var s = document.getElementById('omn-faq-search');
    if (s) s.focus();
  }, 200);
});

closeBtnEl.addEventListener('click', function() {
  overlay.classList.remove('open');
  document.body.classList.remove('u-no-scroll');
});

overlay.addEventListener('click', function(e) {
  if (e.target === overlay) {
    overlay.classList.remove('open');
    document.body.classList.remove('u-no-scroll');
  }
});

// Footer-Link "Frag den Wissensvermittler" -> FAQ zu, Chat auf. Delegiert, da
// der Link bei jedem Panel-Rebuild neu erzeugt wird (statt inline onclick --
// CSP script-src ohne 'unsafe-inline').
overlay.addEventListener('click', function(e) {
  if (!e.target.closest('.faq-to-chat')) return;
  e.preventDefault();
  overlay.classList.remove('open');
  document.body.classList.remove('u-no-scroll');
  var chatFab = document.getElementById('omn-fab');
  if (chatFab) chatFab.click();
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
    cats.forEach(function(c) { c.classList.remove('faq-cat-hidden'); });
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
    c.classList.toggle('faq-cat-hidden', !visibleCats[c.getAttribute('data-cat')]);
  });
});

// ESC to close
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape' && overlay.classList.contains('open')) {
    overlay.classList.remove('open');
    document.body.classList.remove('u-no-scroll');
  }
});

})();
