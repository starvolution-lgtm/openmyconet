# Fremddaten Buffi et al. 2025: Prüfregeln (Schritt C1)

**Freigegeben am 23.11.2026 (Robby), vor jedem Lauf auf den Prüfdateien.** Danach nur noch
dokumentierte, begründete Ergänzungen, nie Änderungen nach Ansicht der Ergebnisse.

> **MESSWERTE VON BUFFI ET AL., NICHT VON OPENMYCONET.** Quelle: M. Buffi (Universität Neuchâtel),
> Mendeley Data, doi 10.17632/srkxbkh6sp.1, Lizenz CC BY 4.0. Zur Arbeit: Buffi et al.,
> *Detection of electrical signals in fungal mycelia in response to external stimuli*, iScience 28
> (10), 113484 (2025), doi 10.1016/j.isci.2025.113484. Die Rohdaten bleiben außerhalb dieses
> Repositorys (`openmyconet_extern/buffi_2025`), hier stehen nur Regeln, Code und Ergebnisse.

## 1. Zweck und Abgrenzung

Phase A und die Nachrechnung liefen nur auf Simulationsdaten. C1 prüft die ESOM/U-Matrix zum
ersten Mal an **echten, veröffentlichten Messwerten** mit bekannter Antwort: Auf jeder Platine
liegen 6 Elektrodenpaare mit Pilz (*Fusarium oxysporum*) und 2 Paare nur mit Nährlösung. Die Frage
ist ein Widerlegungsversuch: **Findet die ESOM die beiden Kanäle ohne
Pilz, ohne dass man sie ihr nennt, und kann das ein einfacheres Verfahren genauso?** (F1,
Abschnitt 6)

Die zweite Frage ist eine **blinde Vorhersage** (F2, Abschnitt 6a): Nach der Zugabe bekamen je
Platine 3 Pilzkanäle und 1 Leerkanal den Stoff, die übrigen 3 + 1 nur das Lösungsmittel. Welche,
steht nicht im Paper. Die Verfahren sagen die Aufteilung vorher, die Vorhersage wird mit Datum
veröffentlicht, und erst danach wird die wahre Zuordnung beschafft und verglichen.

Nicht Teil von C1:
- Keine Aussage über eine biologische Wirkung der Stoffe. F2 prüft nur, ob sich die Aufteilung
  aus den Daten vorhersagen lässt.
- Keine biologische Deutung über „Kanal mit Pilz unterscheidet sich von Kanal ohne Pilz“ hinaus.
  Je Stoff gibt es nur eine Platine, die Leerkanäle sind Nährlösung ohne Sporen, und die
  Artefakt-Kritik (Blatt et al. 2024) gilt auch hier.
- Keine Änderung an Phase A, an KRITERIEN v2/E1/E2, an der Nachrechnung oder an Phase B.
- Keine Änderung an Server, Datenbank, Pipeline, Schema oder Firmware.
- RefESOM wird nicht verwendet. Eine Nachrechnung mit RefESOM wäre ein eigener, späterer Schritt nach
  Absprache mit den Entwicklern.

## 2. Was vor der Festlegung schon angesehen wurde (Offenlegung)

Am 23.11.2026 wurde **nur die Datei `cycloheximide.hdf5`** geladen und gelesen: Aufbau
(8 Kanäle, 16,67 Werte/s, 10,1 Tage, NaN-Lücken bei 93,6 h und 168,4 h), Wertebereich und
Perzentile **je Kanal** über die ganze Aufnahme (also auch über die Zeit nach der Zugabe,
aber nur als Gesamtwert, nicht vorher/nachher getrennt), Spektrum und Kanalkorrelationen im Block
10–80 h (keine Linien über 0,2 Hz, schneller Anteil 1,0–1,8 µV, Kanäle unkorreliert). Dabei war
sichtbar, dass der Wertebereich je Kanal verschieden ist (z. B. 7-8 am engsten). Nach Kanälen
mit und ohne Pilz ausgewertet wurde nichts.

Deshalb gilt: **Die Cycloheximid-Datei ist nur Vorlauf** (Abschnitt 5, C1-0) und zählt für kein
Urteil. Für F2 wird auch für sie eine Vorhersage abgegeben, aber getrennt berichtet und nicht
mitgezählt. Geprüft wird auf den drei noch nicht geladenen Dateien `calcimycin.hdf5`,
`sodiumazide.hdf5` und `voriconazole.hdf5` (zusammen 744 MB; Download Teil der Freigabe).

## 3. Daten

- Je Datei 8 Datensätze `Differenziale a - b`, float32, 16,6667 Werte/s (Attribut `interval`;
  Paper: 60 ms Wandlungszeit je Kanal), Startzeit im Attribut `start`. Einheit nicht angegeben;
  alle Merkmale in C1 sind maßstabsfrei oder werden robust skaliert, die Einheit spielt keine Rolle.
- Prüfsumme (sha256) je Datei gegen die Angabe bei Mendeley; Abweichung = Datei wird nicht genutzt.
- **Kanalzuordnung (Annahme aus dem Paper):** beimpft sind die Elektroden 1, 3, 5, 9, 11, 13, also
  die Kanäle 1-2, 3-4, 5-6, 9-10, 11-12, 13-14. **Ohne Pilz: 7-8 und 15-16.** Ist die Annahme
  falsch, ist C1 ohne Aussage; das wird dann so berichtet, nicht umgedeutet.
- **Zugabezeitpunkt:** die NaN-Lücke (≥ 10 aufeinanderfolgende NaN, in allen Kanälen gleich),
  nach der noch 60–90 h Aufnahme folgen (Paper: 7 Tage Besiedlung, danach 3 Tage). Gibt es keine
  oder mehr als eine solche Lücke, wird die Datei nicht ausgewertet und das berichtet.
- **Zeiträume:** „vorher“ = die letzten 72 h vor der Zugabelücke; „nachher“ = ab 1 h nach der
  Lücke (Einschwingen nach dem Öffnen von Käfig und Inkubator) bis zum Ende, höchstens 72 h.
  F1 nutzt nur „vorher“. Die Zeit „nachher“ wird erst für F2 gelesen, nach Abschluss von F1.

### 3a. Nachtrag Zugabelücke (freigegeben von Robby am 23.11.2026, nach Laden der Prüfdateien, vor jedem Ergebnis)

**Anlass:** Die Regel oben findet in **keiner** der drei Prüfdateien eine Zugabelücke, weil die
Aufnahmen nach der Lücke nicht 3 Tage dauern, wie das Paper schreibt. Angesehen wurde dafür nur
die Lage der gemeinsamen NaN-Lücken (Werkzeug-Abbruch vor jeder Merkmalsberechnung), keine
Messwerte und kein Ergebnis:

| Datei | Dauer | gemeinsame NaN-Lücken (ohne Anfang/Ende) | danach |
|---|---|---|---|
| Calcimycin | 282,4 h | 169,1 h (456 Werte) | 113,3 h |
| Natriumazid | 289,3 h | 72,3 h (8 Werte), 172,7 h (1 157 Werte) | 216,9 h / 116,5 h |
| Voriconazol | 169,6 h | 122,9 h (799 Werte) | 46,7 h |
| Cycloheximid (Vorlauf) | 243,0 h | 93,6 h (1 357 Werte), 168,4 h (424 Werte) | 149,4 h / 74,6 h |

**Neue Regel (ersetzt den Punkt „Zugabezeitpunkt“):** Zugabelücke = die **letzte** gemeinsame
NaN-Lücke mit **≥ 100 Werten** (≈ 6 s; Käfig und Inkubator öffnen, Stoff auftragen dauert
länger), nach der noch **≥ 24 h** Aufnahme folgen. Das ergibt je Datei genau eine Lücke:
Calcimycin 169,1 h, Natriumazid 172,7 h, Voriconazol 122,9 h, Cycloheximid 168,4 h (wie im
Vorlauf). „Nachher“ bleibt ab 1 h nach der Lücke, höchstens 72 h; bei Voriconazol sind es nur
45,7 h.

**Vorbehalt, der berichtet wird:** Bei Voriconazol liegt die Lücke nach 5,1 statt nach etwa
7 Tagen. Ob das die Zugabe war, lässt sich aus den Daten nicht sicher sagen. Die Datei wird
trotzdem nach der Regel ausgewertet; ihr Ergebnis wird mit diesem Vorbehalt gekennzeichnet.

## 4. Fenster, Merkmale, Karte

- **Fenster:** 60 s (1 000 Werte), Schritt 30 s, je Kanal; Fenster mit NaN fallen heraus (gezählt).
  Je Datei etwa 8 × 8 600 ≈ 69 000 Fenster (≈ 29 je Neuron).
- **Merkmalssatz `mb1`, pegelfrei** (wie Satz P, an 16,67 Hz angepasst), je Fenster nach
  Entfernen einer Geraden: robuste Streuung (log), Kurtosis, Zahl der Ausschläge > 6 × robuste
  Streuung (log1p), größter Ausschlag relativ zur Streuung (log1p), relative Bandleistung
  0–0,1 / 0,1–0,5 / 0,5–1,5 / 1,5–4 / 4–8,33 Hz (Welch, Hann, 256 Werte), spektrale Flachheit,
  Autokorrelation bei 1 Wert und bei 1 s, Anteil gleichbleibender Folgewerte.
- **Satz `mb1-L`, mit Pegel:** zusätzlich Mittelwert, Steigung, Abweichung des Mittels vom Median
  der vorangehenden 10 min (fehlt der Vorlauf, fällt das Fenster aus diesem Satz heraus).
- Normierung wie KRITERIEN Abschnitt 3 (log/log1p, Median und Quartilsabstand, Grenze ±8),
  **je Datei über alle 8 Kanäle gemeinsam**, ohne Kenntnis der Kanalrolle.
- Ausgewertet werden `mb1` (Hauptsatz) und `mb1-L` (nur berichtet).
- **Karte:** `karte-v1` wie A4: ESOM 40 × 60 toroidal, 40 Epochen, Endradius σ 0,75, Seeds 0–9,
  Gruppen nach Regel v2 (KRITERIEN Abschnitt 4). Komponenten = alle Gruppen **einschließlich der
  größten** sowie Inseln.

## 5. Läufe in fester Reihenfolge

- **C1-0 Vorlauf (Cycloheximid, zählt nicht):** Lesen, Zugabelücke finden, Fenster und Merkmale,
  ein Lauf Seed 0. Prüft nur Technik und Laufzeit. Bricht etwas ab oder passt die Lücke nicht zu
  Abschnitt 3, wird angehalten und geklärt, bevor eine Prüfdatei gelesen wird. Das F1-Ergebnis
  auf dieser Datei wird berichtet, als „Vorlauf, nicht blind“ gekennzeichnet.
- **C1 Prüfung F1:** die drei Prüfdateien laden, Prüfsummen, dann je Datei Seeds 0–9 und alle
  Vergleichsverfahren aus Abschnitt 6, nur „vorher“. Keine Zwischenansicht der Ergebnisse vor
  Abschluss aller drei Dateien.
- **C1 Vorhersage F2:** danach „nachher“ lesen, Vorhersagen nach 6a für alle vier Dateien,
  `ergebnisse/c1/f2_vorhersage.json` schreiben, committen und pushen (Zeitstempel). **Erst
  danach** wird die wahre Zuordnung beschafft (Zusatzmaterial des Papers oder Nachfrage, die nur
  Robby schickt).
- **C1 Prüfung F2:** wahre Zuordnung eintragen (mit Quelle), Vorhersage unverändert dagegen
  halten, Urteil nach 6a.

## 6. Hauptfrage F1: Findet ein Verfahren die zwei Kanäle ohne Pilz?

**Maß je Datei.** Für jedes der 28 möglichen Kanalpaare P (aus 8 Kanälen 2 gewählt):
J(P) = größter Jaccard-Wert zwischen der Fenstermenge von P und einer Komponente bzw. einem
Cluster. Bei der ESOM und bei Verfahren mit Seeds zählt der Median von J(P) über die Seeds 0–9.

**Gefunden in einer Datei**, wenn beide Bedingungen gelten:
1. Das wahre Paar (7-8, 15-16) hat von allen 28 Paaren das **höchste** J (bei Gleichstand: nicht
   gefunden).
2. Sein J ist ≥ 0,5.

Unter der Nullannahme „die Struktur hat mit Pilz/kein Pilz nichts zu tun“ ist Bedingung 1 mit
Wahrscheinlichkeit 1/28 ≈ 0,036 erfüllt.

**Gefunden insgesamt:** in **mindestens 2 der 3** Prüfdateien (unter der Nullannahme
p ≈ 0,004).

**Verfahren, alle auf derselben normierten Merkmalsmatrix `mb1`, ohne Kanalrolle:**
- **ESOM** (`karte-v1`, Abschnitt 4).
- **k-Means** mit k = 2 und k = Zahl der Komponenten der Seed-0-ESOM, Seeds 0–9.
- **HDBSCAN** (min_cluster_size = 50; Rauschpunkte zählen zu keinem Cluster).
- **Einfaches Kanalkriterium (Referenz, kein Clustering):** Die zwei Kanäle mit dem kleinsten
  Median der robusten Streuung. Gefunden, wenn das genau das wahre Paar ist. Das entspricht dem
  Befund im Paper (Pilzkanäle zeigen mehr Leistung).

**Entscheidung (vorab):**
- **ESOM-spezifischer Mehrwert:** Die ESOM findet die Leerkanäle insgesamt, **keines** der übrigen
  Verfahren (einschließlich Kanalkriterium) tut es.
- **ESOM bestätigt den bekannten Befund, ohne Mehrwert:** Die ESOM findet sie, mindestens ein
  einfacheres Verfahren auch. Gleichstand reicht nicht (wie KRITERIEN 10.4).
- **ESOM findet sie nicht:** wird so berichtet, auch wenn ein einfacheres Verfahren sie findet.
  Findet kein Verfahren sie, ist das ein Widerspruch zum Paper, der berichtet und nicht durch neue
  Merkmale nachträglich behoben wird.

## 6a. Zweite Frage F2: Blinde Vorhersage der Aufteilung nach der Zugabe

**Mögliche Aufteilungen.** Je Platine sind 6 Pilzkanäle und 2 Leerkanäle in zwei Hälften zu je
3 Pilz + 1 Leer zu teilen: 20 Aufteilungen (ohne Seite). Mit Seite (welche Hälfte den Stoff
bekam) sind es 40.

**Gemeinsame Grundlage.** Merkmale `mb1` aus „vorher“ und „nachher“ aller 8 Kanäle, gemeinsam
normiert (ohne Kanalrolle). Für jeden Kanal c die **Änderung** Δ(c) als Vektor, je Verfahren
unten festgelegt. Ähnlichkeit zweier Kanäle = Kosinus ihrer Δ. Wert einer Aufteilung = mittlere
Ähnlichkeit innerhalb der Hälften minus mittlere Ähnlichkeit zwischen den Hälften. Vorhergesagt
wird die Aufteilung mit dem höchsten Wert. **Seite:** Die Hälfte, deren 3 Pilzkanäle im Mittel die
größere Änderung (Länge von Δ) zeigen, gilt als „Stoff“ (Annahme: das Lösungsmittel ändert
weniger als der Stoff; bei Calcimycin/DMSO ist das nach dem Paper fraglich und wird so berichtet).

**Verfahren:**
- **ESOM:** `karte-v1` wie Abschnitt 4 auf „vorher“ + „nachher“ zusammen, Seeds 0–9.
  Δ(c) = Anteil der Fenster von c je Komponente nachher minus vorher. Die Vorhersage ist die in den
  meisten Seeds gewählte Aufteilung (mit Seite). Wird sie in weniger als 5 von 10 Seeds gewählt,
  heißt sie **unsicher**; sie wird trotzdem abgegeben und gezählt.
- **Merkmalsänderung (einfach):** Δ(c) = Median je Merkmal nachher minus vorher (normierte
  Merkmale), sonst wie oben.
- **Lautstärke (einfachste Referenz):** Δ(c) = Änderung des Medians der robusten Streuung (log).
  Hälfte „Stoff“ = die 3 Pilzkanäle mit der größten |Änderung| und der Leerkanal mit der größeren
  |Änderung|.

**Festschreiben.** Je Datei und Verfahren: Aufteilung, Seite, bei der ESOM die Zahl der Seeds,
die sie gewählt haben. Datei `f2_vorhersage.json` mit sha256 der Eingangsdaten, committet und
gepusht, bevor die wahre Zuordnung bekannt ist. Danach wird an der Vorhersage nichts mehr geändert.

**Urteil (nach Eingang der wahren Zuordnung, vorab festgelegt):**
- Je Datei und Verfahren **Aufteilung richtig** (Zufall 1/20) und **mit Seite richtig**
  (Zufall 1/40).
- Ein Verfahren **sagt die Aufteilung vorher**, wenn sie in **mindestens 2 der 3** Prüfdateien
  richtig ist (Zufall ≈ 0,007; mit Seite ≈ 0,002).
- **ESOM-spezifischer Mehrwert** nur, wenn die ESOM das schafft und keines der beiden einfachen
  Verfahren. Gleichstand reicht nicht.
- Gibt es die wahre Zuordnung nicht (keine Antwort, nicht mehr bekannt), bleibt F2 **offen**; die
  Vorhersage bleibt veröffentlicht und wird nicht nachträglich gedeutet.

### 6b. Nachtrag Gleichstand (freigegeben von Robby am 23.11.2026, nach der Vorhersage, vor Kenntnis der Wahrheit)

Abschnitt 6a regelt nicht, was gilt, wenn bei der ESOM zwei Vorhersagen gleich viele Seeds
haben (eingetreten bei Natriumazid 3/3 und Voriconazol 5/5). Festgelegt: **Bei Gleichstand zählt
die ESOM-Vorhersage dieser Datei als nicht richtig** (die strengere Lesart). Alle gleichauf
liegenden Vorhersagen sind in `f2_vorhersage.json` festgeschrieben.

**Nur berichtet (nach Eingang der Zuordnung):** ob der Leerkanal mit Stoff in Δ den Pilzkanälen
mit Stoff ähnlicher ist als denen mit Lösungsmittel. Das wäre ein Hinweis auf einen
Elektroden- oder Lösungseffekt statt einer Wirkung auf den Pilz, nie ein Beweis.

## 7. Nur berichtet (keine Regel, kein Urteil)

- Kartengüte je Datei (QE, TE), Zahl der Gruppen und Inseln, Laufzeit.
- Komponenten, die in ≥ 5 von 10 Seeds wiedergefunden werden (Jaccard ≥ 0,5 zur Seed-0-Karte):
  Anteil je Kanal und Verteilung über die Tageszeit (Startzeit + Fensterlage). Eine Komponente
  aus ≥ 80 % Fenstern eines Kanals heißt **kanaltypisch**. Das ist eine Hypothese im Sinn
  „U-Matrix als Hypothesengenerator“, kein Befund.
- U-Matrix der Seed-0-Karte je Datei, Fenster nach Kanal eingefärbt (Bild für die Entwickler).
- `mb1-L` mit derselben F1-Auswertung, nur als Zahl.
- Netzreste: Bei 16,67 Hz = 50/3 Hz fallen 50 Hz und alle Oberwellen genau auf 0 Hz und sind im
  Spektrum nicht prüfbar. Das wird festgehalten (Bezug Störquellen-Katalog, eigene Abtastrate).

## 8. Was ausdrücklich zurückgestellt ist

- **Stoffwirkung im biologischen Sinn:** Auch eine richtige Vorhersage in F2 zeigt nur, dass sich
  die behandelten Kanäle anders verändern. Ob das am Pilz, an der Elektrode oder an der Lösung
  liegt, entscheidet C1 nicht (je Stoff eine Platine, ein Leerkanal je Bedingung).
- **Kontakt zu Buffi et al.** nur durch Robby, und für F2 erst nach dem Push der Vorhersage.
- Keine Desktop-Anwendung der Entwickler, keine interaktive Erkundung als Entscheidungsgrundlage.
- Keine eigenen Messwerte; Simulationsdaten aus Phase A werden nicht mit diesen Daten gemischt.

## 9. Ergebnis und Bericht

`ergebnisse/c1/BERICHT.md` und `c1.json`: Vorlauf, Prüfsummen, Zugabelücken je Datei, F1-Tabelle
(Verfahren × Datei, J des wahren Paares, Rang unter 28), Urteil nach Abschnitt 6, die Punkte aus
Abschnitt 7, Abweichungen von diesen Regeln. F2 in zwei Stufen: zuerst nur die Vorhersage
(`f2_vorhersage.json`), nach Eingang der Zuordnung der Vergleich als Nachtrag. Rohdaten, Merkmalsmatrizen und Gewichte bleiben
lokal. Quelle und Lizenz stehen in jedem Bericht. Eintrag in `VERLAUF.md`.

**Umgebung:** Analyse-venv, zusätzlich `h5py` (in `requirements.in`, `requirements.txt` neu mit
Prüfsummen erzeugen).
