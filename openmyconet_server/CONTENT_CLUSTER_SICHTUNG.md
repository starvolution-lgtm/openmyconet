# Content-Sichtung für Topic-Cluster/SEO

Status: Sichtungs- und Vorschlagsdokument, keine Umsetzung. Entscheidung über Aufbau/Reihenfolge trifft Robert.
Geprüft: index.html, leihgeraete.html, quellennachweise.html, medien.html, presse.html, foerderer.html (Templates unter `app/templates/site/`) sowie die zugehörigen deutschen Texte in `app/static/translations.json`.

---

## 1. Bestandssichtung — Textsubstanz je möglichem Cluster-Thema

### Cluster A — Mykorrhiza-Netzwerke / "Wood Wide Web" (Grundlagen + Kritik)

| Fundstelle | Inhalt |
|---|---|
| `index.html` Vision-Sektion, Key `vision_p1` | "400 Millionen Jahre alt", Nährstofftransport, Warnsignale, "sie senden elektrische Signale — messbar, reproduzierbar, kaum entschlüsselt" |
| `index.html` Vision-Sektion, Key `vision_p2`, `vision_p3` | Rhetorische Grundfrage von OpenMycoNet, Begründung für Citizen-Science-Ansatz (Datenmangel) |
| `index.html` Warum-Sektion, Key `desc_warum` | "Mykorrhiza-Pilze verbinden über 90 % aller Landpflanzen" |
| `index.html` Facts-Kacheln (`facts`) | "400M Jahre alt", "90% aller Landpflanzen" |
| `quellennachweise.html` Station 1 (`#station-1`) | Ausführlichster Abschnitt zum Thema — Simard-Grundlagenwerk, peer-reviewte Nachweise |
| `quellennachweise.html` Station Kritik (`#station-kritik`) | Explizite kritische Gegenposition zur Wood-Wide-Web-Popularisierung |

Umfang: mittel-groß, aber über zwei Seiten verteilt (kurze Absätze auf index.html, ausführliche Stationsbeschreibung + Referenzen auf quellennachweise.html).

### Cluster B — Bioelektrizität bei Pilzen / Wie BioComm misst

| Fundstelle | Inhalt |
|---|---|
| `index.html` Vision, `vision_p1` | "Sie senden elektrische Signale" (Teilsatz, s. auch Cluster A) |
| `index.html` Warum-Karten (`cards`), Karte "Echte Wissenschaft" | "Die Signale existieren nachweislich (Adamatzky et al., 2022)" |
| `index.html` Facts-Kachel | "8 Messkanäle, bis zu 10.000 Hz" (BioComm-Spezifikation) |
| `quellennachweise.html` Station 2 (`#station-2`) | Elektrische Aktivität im Myzel — drei Referenzen |
| `quellennachweise.html` Station 3 (`#station-3`) | Messbarkeit/Sensorik/KI-Mustererkennung — drei Adamatzky-Arbeiten + MIND |
| `leihgeraete.html` komplett (Specs-Tabelle, Bridge-Sektion, "System im Einsatz") | Vollständige technische Beschreibung der BioComm-Hardware (ESP32, LoRa, ADC, Sensorik, Gehäuse) |

Umfang: groß — dies ist inhaltlich die textreichste Seite außerhalb von index.html/quellennachweise.html, komplett vorhanden.

### Cluster C — Citizen-Science-Ansatz

| Fundstelle | Inhalt |
|---|---|
| `index.html` Mitmachen-Sektion, `desc_mitmachen` + `steps` | Ablauf: Hardware leihen → Software → Elektroden setzen → Messen & teilen |
| `index.html` Warum-Karten, Karte "Citizen Science" | Analogie zu SETI@home |
| `index.html` Warum-Karten, Karte "Globale Datenbasis" | Begründung für verteilte Messungen |
| `quellennachweise.html` Station CS (`#station-cs`) | Methodische Begründung: iNaturalist-Studie, FunDive-Vergleichsprojekt |

Umfang: mittel, eher knapp bei der methodischen Begründung.

### Randthema — Zukunftsvisionen / Anwendungsfälle (vision_apps)

`index.html`, sechs Kacheln unter der Vision-Sektion (Präzisionslandwirtschaft, Waldschutz, Bodenregeneration, Klimaschutz, Grundlagenforschung, "Was wir noch nicht wissen"). Sprachlich bereits vorsichtig gehalten ("könnte", "möglicherweise", "wenn das stimmt"). Kein eigenständiges Cluster-Thema, aber inhaltlich relevant für Cluster A/B als "Ausblick".

### Randthema — Populärwissenschaftlicher Kontext (Sheldrake) vs. eigener Roman

Zwei unterschiedliche Bücher, die leicht verwechselt werden können:
- `quellennachweise.html` Station "Buch" (`#station-buch`): Merlin Sheldrakes *Entangled Life* — Fremdwerk, als Einstiegslektüre empfohlen.
- `medien.html` Buch-Sektion: Robert Janks eigener Roman *Das letzte Korn* — Fiktion, kein wissenschaftlicher Beleg, hat mit den Quellennachweisen nichts zu tun.

### Nicht clusterrelevant, aber im Zuge der Sichtung erfasst

`about_p1–p3` (Projektgeschichte, Gebrauchsmuster, "Proprietary Intelligence, Open Data"), `a_node_req_*` (Bewerbungsvoraussetzungen), `foerderer.html` (Geschäftsseite) — organisatorische bzw. Produktseiten, keine Wissensvermittlung im engeren Sinn.

---

## 2. Zuordnungstabelle: Textpassage ↔ Quellennachweis

| Textpassage | Kernaussage | Zugeordnete(r) Quellennachweis(e) |
|---|---|---|
| `vision_p1` (Mykorrhiza-Grundlage, Nährstoff/Warnsignale) | Pflanzen kommunizieren über Mykorrhiza | Ref 01 (Simard TED/Buch), Ref 02 (Simard et al. 2015) |
| `vision_p1` ("sie senden elektrische Signale — messbar, reproduzierbar") | Elektrische Aktivität im Pilznetzwerk | Ref 03 (Electrical signaling in fungi), Ref 04 (The fungal grid) |
| `desc_warum` ("verbinden über 90 % aller Landpflanzen") | Verbreitungsgrad Mykorrhiza | Thematisch nahe an Ref 01/02, aber **keine der 14 Quellen belegt die 90%-Zahl explizit** |
| `facts` Kachel "400M Jahre" | Alter der Mykorrhiza-Symbiose | Thematisch nahe an Ref 01/02, **Zahl selbst nicht direkt referenziert** |
| `cards` "Echte Wissenschaft" ("Adamatzky et al., 2022") | Signale existieren nachweislich | Vermutlich Ref 05 (arXiv:2112.07236, 2021) oder Ref 06 (arXiv:2304.10675, 2023) — **Jahresangabe "2022" passt zu keiner der gelisteten Adamatzky-Arbeiten exakt** |
| `facts` Kachel "8 Messkanäle … bis 10.000 Hz" | BioComm-Hardwarespezifikation | Frequenzbereich lehnt sich an Ref 06 (100–10.000 Hz) an; Kanalzahl (8) ist eigene Hardware-Entscheidung, keine externe Quelle |
| `quellennachweise.html` Station 1 | Grundlagenforschung Netzwerkkommunikation | Ref 01, 02, 14 |
| `quellennachweise.html` Station Kritik | Kritische Einordnung | Ref 11, 12 |
| `quellennachweise.html` Station 2 | Elektrische Aktivität in Pilzen | Ref 03, 04, 13 (`q_ref08`) |
| `quellennachweise.html` Station 3 | Messbarkeit/Sensorik/KI | Ref 05, 06, 07 |
| `quellennachweise.html` Station Buch | Populärwissenschaftliche Einordnung | Ref 08 (Sheldrake) |
| `quellennachweise.html` Station CS | Methodik verteilter Laienmessung | Ref 09, 10 |
| `cards` "Citizen Science" (SETI@home-Vergleich) | Analogie zur Legitimation des Ansatzes | Keine der 14 Quellen — eigene Analogie, nicht referenziert |
| `desc_mitmachen`, `steps` (Ablaufbeschreibung) | Wie man mitmacht | Keine externe Quelle nötig (Verfahrensbeschreibung) |
| `leihgeraete.html` komplett (Specs, Bridge, System) | BioComm-Hardware im Detail | Keine externe Quelle — eigene Entwicklung (laut `about_p2` per Gebrauchsmuster beim DPMA geschützt) |
| `vision_apps` (6 Kacheln) | Zukunftsanwendungen | Nur "Grundlagenforschung"-Kachel nennt "Adamatzky et al." namentlich (Ref 05/06); die übrigen 5 sind unbelegte eigene Hypothesen |
| `about_p1–p3` | Projektgeschichte, Datenprinzip | Keine externe Quelle — Selbstauskunft |
| `medien.html` Buch-Teaser "Das letzte Korn" | Eigener Roman | Keine externe Quelle — eigenes fiktionales Werk |

---

## 3. Trennung: Sekundärquelle (belegt) vs. eigene offene Fragestellung

**(a) Durch Quelle belegbar — etablierter wissenschaftlicher Stand:**
- Mykorrhiza-Netzwerke als Informationskanal zwischen Pflanzen (Cluster A, Ref 01/02/14)
- Kritische Gegenposition zur Wood-Wide-Web-Popularisierung (Ref 11/12) — bewusst mit einbezogen, nicht verschwiegen
- Elektrische/bioelektrische Aktivität in Pilzmyzel als reproduzierbares Phänomen (Cluster B, Ref 03/04/13)
- Signalverarbeitende Eigenschaften des Myzels, Frequenzübertragung (Ref 05/06/07)
- Methodische Validität verteilter Citizen-Science-Messungen (Cluster C, Ref 09/10)

**(b) OpenMycoNets eigene, unbeantwortete Fragestellung/Hypothese — kein Beleg vorhanden oder möglich:**
- Alle sechs `vision_apps`-Kacheln (Präzisionslandwirtschaft, Waldschutz, Bodenregeneration, Klimaschutz, "Was wir noch nicht wissen") — Sprache ist bereits konjunktivisch/vorsichtig gehalten, das ist positiv zu vermerken
- Ob und wie BioComm-Messdaten die unter (a) belegten Phänomene bei OpenMycoNet-Teilnehmern tatsächlich bestätigen — dazu gibt es aktuell keine eigenen Messergebnisse auf der Website (konsistent mit "erst Messdaten, dann alles andere")
- Die konkrete BioComm-Hardware selbst (`leihgeraete.html`) ist weder aus (a) noch (b) — sie ist eigene Technik-Entwicklung, für die keine externe Quelle nötig oder sinnvoll wäre; sie sollte aber auch nicht so dargestellt werden, als sei sie durch die Forschungsquellen "bewiesen"

**Beobachtungen am Rande (nicht Teil dieses Auftrags, aber beim Sichten aufgefallen):**
1. Die Jahresangabe "Adamatzky et al., 2022" (`cards`, Karte "Echte Wissenschaft") lässt sich keiner der 14 gelisteten Quellen exakt zuordnen (die dort gelisteten Adamatzky-Arbeiten sind von 2021 und 2023). Reine Sichtbeobachtung, keine Korrektur vorgenommen.
2. Die Zahlen "400 Millionen Jahre" und "90 % aller Landpflanzen" (Facts-Kacheln, `desc_warum`) sind wissenschaftlich gängige Werte, aber in der aktuellen Quellenliste nicht mit einer konkreten Referenznummer verknüpft — bei einer späteren Cluster-Seite ließe sich das leicht nachschärfen, indem eine dediziert Zahlen-tragende Quelle ergänzt wird.

---

## 4. Strukturvorschlag (unverbindlich)

### Vorschlag: drei Pillar-Themen statt vier

Die vier vom Auftrag genannten Beispielthemen lassen sich zu **drei tragfähigen Pillar-Seiten** bündeln — "Bioelektrik bei Pilzen" und "wie BioComm misst" gehören inhaltlich so eng zusammen (Forschungsstand + eigene Technik, die darauf aufbaut), dass eine gemeinsame Seite sinnvoller wirkt als zwei dünne.

**Pillar 1 — "Mykorrhiza-Netzwerke verstehen"**
(Grundlagen + kritische Einordnung)
- Vorhandener Text: ~60 % (Kernaussagen aus `vision_p1–p3`, `desc_warum`, Station 1 + Station Kritik von quellennachweise.html)
- Neu zu schreiben: verbindende Fließtext-Struktur, ggf. Zahlen (400M Jahre/90 %) mit sauberer Quellenangabe nachschärfen
- Verlinkt auf: Ref 01, 02, 11, 12, 14 (via Anchor `#station-1` / `#station-kritik`, die es auf quellennachweise.html bereits gibt)

**Pillar 2 — "Bioelektrizität bei Pilzen & wie BioComm misst"**
(Forschungsstand + eigene Messtechnik, klar getrennt ausgewiesen)
- Vorhandener Text: ~50 % (wissenschaftlicher Teil aus `cards`, `facts`, Station 2+3; technischer Teil bereits vollständig auf `leihgeraete.html`)
- Neu zu schreiben: redaktionelle Trennung zwischen "was die Forschung zeigt" (Ref-belegt) und "was BioComm konkret tut" (eigene Entwicklung) — aktuell in den Kurz-Kacheln auf index.html vermischt dargestellt
- Verlinkt auf: Ref 03, 04, 05, 06, 07, 13 (via `#station-2` / `#station-3`) sowie intern auf `leihgeraete.html` als vertiefende technische Unterseite

**Pillar 3 — "Citizen Science bei OpenMycoNet"**
- Vorhandener Text: ~40 % (Ablauf aus `steps`/`desc_mitmachen` vorhanden, methodische Begründung dünn)
- Neu zu schreiben: methodischer Unterbau (warum verteilte Laienmessung wissenschaftlich valide ist), gestützt auf Ref 09/10
- Verlinkt auf: Ref 09, 10 (via `#station-cs`) sowie auf die Registrierungssektion `index.html#anmelden`

**Kein eigenes Cluster:**
- `vision_apps` (Zukunftsvisionen) als "Ausblick"-Abschnitt in Pillar 1 oder 2 einbinden statt eigene Seite — Inhalt ist zu dünn und zu spekulativ für eine eigenständige SEO-Seite, Gefahr der Fehlinterpretation als Ergebnis statt offene Frage
- Sheldrake-Buch als kurze Lesetipp-Box in Pillar 1, klar von `medien.html`s "Das letzte Korn" abgegrenzt

### Verlinkungsstruktur

- Pillar 1 ↔ Pillar 2: stark verbunden (gegenseitige Verlinkung sinnvoll, da Cluster B auf Cluster A aufbaut)
- Pillar 3: lockerer verbunden zu beiden (Querverweis von Pillar 3 auf Pillar 2, weil dort beschrieben wird, was gemessen wird)
- Alle drei Pillar-Seiten verlinken gezielt auf die passenden Stationen/Referenzen auf `quellennachweise.html` — die dortige Anchor-Struktur (`#station-1`, `#station-kritik`, `#station-2`, `#station-3`, `#station-buch`, `#station-cs`) ist bereits vorhanden und eignet sich direkt als Verlinkungsziel, ohne dass an `quellennachweise.html` selbst etwas geändert werden müsste
- `leihgeraete.html` bekommt eine Rückverlinkung von Pillar 2 aus — aktuell ist die Seite nur von `index.html#anmelden` aus erreichbar
- `presse.html` bewusst **nicht** in die Cluster-Struktur einbetten — sie sammelt Drittquellen-Berichterstattung, keine Wissenschaft, und trennt das bereits vorbildlich über den Disclaimer-Hinweis oben auf der Seite ("keine wissenschaftliche Validierung … Wissenschaftlich geprüfte Quellen … unter Quellennachweise")

---

## 5. Nicht Teil dieser Sichtung

Wie im Auftrag festgelegt: keine neuen Templates angelegt, keine Texte über reine Umsortierung hinaus verändert, `quellennachweise.html` selbst unangetastet gelassen. Dieses Dokument ist Entscheidungsgrundlage, keine Umsetzung.
