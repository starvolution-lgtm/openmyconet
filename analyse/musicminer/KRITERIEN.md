# Phase A: Datengrundlage, Vorhersage und Bewertungskriterien

Stand 05.11.2026, **vor dem ersten Training** festgehalten. Änderungen an Kriterien danach nur
mit Datum, Begründung und neuer Versionsnummer.

**Ergänzung E1 zu v2** (05.11.2026, nach A3, **vor A4** festgelegt, gilt prospektiv ab A4,
Abschnitt 9): größenabhängiger Nullmodellvergleich, drei Ergebnisstufen, Operationalisierung von
8b, Robustheitstest der Kartentopologie, Vergleichsverfahren für A4. v2 und die damit bewerteten
Ergebnisse von A1–A3 bleiben unverändert.

**Ergänzung E2** (05.11.2026, nach A4, **vor Phase B** festgelegt, gilt nur für Phase B,
Abschnitt 10): Ein-Merkmal-Struktur und Übertragung präzisiert, geprüfte Schlupflöcher,
Hauptendpunkt und Entscheidungsregel zur ESOM, Verblindung, Ansichtstest, Langzeitversuch.
Phase A bleibt unverändert bewertet.

**Kriterien v2** (05.11.2026, ebenfalls vor dem ersten Training, nach Rückmeldung Robby):
Klassifikation und explorative Entdeckung werden getrennt bewertet (8a/8b); faire
Vergleichsbedingungen und zwei Nullmodelle (7); kleine SOM und große ESOM werden getrennt
betrachtet (4); Normierung präzisiert (3).

> SIMULATION. Die Daten stammen aus dem Rechenmodell des Sandbox-Generators (`sbx-gen-1.0`,
> Szenario-Version 2, Parametergrundlage `ARBITRARY_DEMO`). Findet die ESOM darin Muster, zeigt das
> nur, dass sie Strukturen dieser Simulation unterscheidet, keine biologische Ursache.

## 1. Datengrundlage

| | |
|---|---|
| Schnappschuss | `daten/schnappschuss_staging_2026-11-05.tar`, sha256 `e9e4b139b6d17a6f2109e19ed3b658a487aeea380401acb033f98767490fbd16` |
| Quelle | Staging, `omn_staging`, Rolle `omn`, READ ONLY, Stand 2026-11-05 09:48:44 UTC, Staging-Commit `de0ed0e` |
| Umfang | 6 Szenarien, 13 Reihen (die 4 Test-Messknoten aus dem Eingangstest sind ausgeschlossen) |
| Prüfung | alle Datei-, Block- und Paket-Prüfsummen, Prüfsummenkette aller 14 Läufe, Kontrollwert 78 682 442,071 (= Prod und Staging) |
| Rohdaten | 46 217 500 bioelektrische Rohwerte, 250 Hz, je Reihe 4 Rohdatenstunden (10:00–11:00 Ortszeit am 13.01., 14.04., 14.07., 13.10.2025), je Stunde zuerst 35 s EC-Pause → 3 565 s lückenlos |
| Daneben | Minuten-/Stundenwerte aller Kanäle, Umwelt-Rohwerte, 2 190 Stimulationen, 3 Qualitätsmarkierungen, 1 Uhrenabgleich, Aufzeichnungspläne |

Reihe 13 (Datenqualität) zerfällt in 6 Segmente: Neustart im Winter (7 min Lücke, neuer Lauf) und
Uhrensprung im Sommer (90 s). Den Uhrensprung erkennt der Leser an der Zeit, die Sample-Indizes
laufen dort lückenlos weiter.

## 2. Was das Rechenmodell enthält (bekannte Struktur)

Aus `omn/sandbox/modell.py` und `generator.py`. Diese Kenntnis fließt **nicht** ins Training, sie
dient nur der Vorhersage.

- Signal = Drift (Zufallsweg je Stunde) + Tagesgang (Sinus, 15 µV × Aktivität) + weißes Rauschen
  (σ = 4 + 18 × Aktivität µV, je Stunde fest) + Spikes (Poisson, 3 + 25 × Aktivität je Stunde,
  40–200 µV, Abklingen ≈ 50 ms).
- Aktivität hängt von Standort und Jahreszeit ab (Klima-Parameter je Standort; Süd-Standorte haben
  zu denselben Kalenderdaten die Gegenjahreszeit).
- Stimulationsreihen: Stimulation um 10:15 (60 s, 0–2 s Versatz), **danach** abklingende Reaktion
  (elektrisch 35 µV, optisch 22 µV, × 0,3–1,0 Aktivität, τ = 600 s) und zusätzliche Spikes in den
  20 min danach. Versetzt: optisch 5 min später. **Während** der Stimulation selbst baut das Modell
  nichts ein (kein Stimulationsartefakt).
- Kontrollreihen haben exakt dieselbe synthetische Grundlage wie ihre Stimulationsreihe; der
  Unterschied ist genau die angenommene Reaktion.
- Datenqualität (nur Reihe 13): Sättigung im Frühling 10:30 für 120 s (+3000 µV > ADC-Grenze
  2 560 µV → abgeschnitten), Neustart und Uhrensprung (nur Lücken, kein Signalmerkmal).
- Spektrum: weiß plus Spikes; **keine** Schwingungen, keine 50-Hz-Einstreuung, keine Kontaktstörungen.

## 3. Fenster und Merkmale (Merkmalssatz v1)

- **Fenster:** 10 s, Schritt 5 s, nur innerhalb eines lückenlosen Segments (≈ 37 000 Fenster).
  Empfindlichkeitsprüfung mit 2 s (Schritt 1 s) und 60 s (Schritt 30 s).
- **Kennung je Fenster:** Lauf, Kanal, erster Sample-Index, Länge, Schritt.
- **Satz P (pegelfrei):** robuste Streuung nach Trendentfernung, Kurtosis, Zahl der Ausschläge
  > 6 × robuste Streuung, größter Ausschlag relativ zur Streuung, relative Bandleistungen
  (0–1, 1–10, 10–45, 45–55, 55–125 Hz), spektrale Flachheit, Autokorrelation (1 Sample, 50 ms),
  Anteil Werte am ADC-Rand, Anteil gleichbleibender Folgewerte.
- **Satz L (Pegel):** Mittelwert, Steigung, Abweichung des Mittels vom Median der vorangehenden
  120 s. Fehlt dieser Vorlauf im Segment, fällt das Fenster aus Satz L heraus (wird gezählt).
- Normierung: stark schiefe, positive Merkmale (Streuung, Ausschlagzahl, größter Ausschlag)
  zuerst logarithmiert (`log1p`), dann robust skaliert (Median, Quartilsabstand; ist der
  Quartilsabstand 0, die Standardabweichung), danach auf ±8 begrenzt, damit einzelne Extremwerte
  die Karte nicht beherrschen. Konstante Merkmale fallen heraus (wird protokolliert). Die
  Parameter werden mit dem Ergebnis gespeichert.
- Ausgewertet werden P allein und P + L.

## 4. Karte

- **Zwei Kartengrößen, getrennt bewertet:** kleine SOM 6 × 8 (48 Neuronen, Neuronen ≈ Gruppen) und
  ESOM 40 × 60 (2 400 Neuronen, deutlich mehr Neuronen als erwartete Gruppen, wie bei ESOM üblich).
  Aussagen über den MusicMiner-Ansatz stützen sich auf die ESOM; ein negatives Ergebnis der kleinen
  Karte gilt nicht als Widerlegung.
- Je Größe planar und toroidal (ohne Rand), je 10 Läufe mit den Seeds 0–9.
- Umsetzung: eine eigene Batch-SOM in numpy (derselbe Code für alle Varianten, deterministisch je
  Seed). MiniSom 2.3.6 kann keine toroidale Karte (geprüft) und dient als Gegenprobe der eigenen
  Umsetzung auf der planaren Karte (Quantisierungs- und Topologiefehler vergleichbar).
- U-Matrix und P-Matrix (Dichte) je Lauf.
- **Gruppenbildung (Regel v2, 05.11.2026, vor dem ersten Training auf Simulationsdaten):**
  Neuronen mit mindestens einem Fenster sind Knoten, **leere Neuronen sind Mauer** (ESOM-Prinzip:
  dort liegen keine Daten). Benachbarte getroffene Neuronen bleiben verbunden, wenn ihr
  Prototypabstand ≤ 3 × Median dieser Abstände ist. Zusammenhängende Bereiche mit ≥ 0,5 % der
  Fenster sind **Gruppen**, kleinere mit ≥ 10 Fenstern bleiben als **Inseln** eigenständig (seltene
  Ereignisse), noch kleinere gehen im Merkmalsraum in den nächstgelegenen Bereich.
  *Grund für den Wechsel von v1:* Regel v1 (75. Perzentil der U-Höhe) fand im Komponententest auf
  der toroidalen Karte bei drei klar getrennten Punktwolken nur zwei Gruppen, weil die Mauern dort
  mehr als ein Viertel der Neuronen ausmachen. Außerdem hätte ihre Mindestgröße seltene Ereignisse
  (z. B. die 25 Sättigungsfenster) weggemischt. Regel v2 findet im Test die drei Wolken auf beiden
  Topologien, ergibt auf einer einzelnen Normalverteilung genau eine Gruppe und erhält eine Insel
  aus 12 Ausreißern (`tests/test_karte.py`). Voraussetzung: deutlich mehr Fenster als Neuronen
  (hier ≈ 15 je Neuron).
- **Abgrenzung einer Gruppe:** Median über ihre Fenster von (Abstand zum nächsten getroffenen
  Prototyp einer anderen Gruppe) ÷ (Abstand zum eigenen Gewinnerneuron). Werte > 1 heißen
  abgegrenzt; maßstabsfrei, daher mit den Nullmodellen vergleichbar.

## 5. Etiketten für die nachträgliche Auswertung

Nur aus Tabellen des Schnappschusses, nie aus dem Modellwissen von Abschnitt 2:
Szenario, Reihe, Rolle (Stimulation/Kontrolle), Standort, Stichtag (Jahreszeit), Stimulationsphase
aus `stimulation` (vor, während, 0–10 min, 10–30 min, > 30 min danach; für Kontrollreihen dieselben
Uhrzeiten als „zeitgleich ohne Stimulation“), Qualitätsmarkierung (Überlappung mit
`quality_annotation`), Nähe zu Segmentgrenzen (< 10 s). Spikes stehen in keiner Tabelle; ob die
Karte sie trennt, prüft erst Phase B mit bekannter Wahrheit.

## 6. Vorhersage (vor dem Training)

| | Erwartung |
|---|---|
| H1 | Stärkste Ordnung der Karte: Rauschstärke → Gradient nach Standort/Jahreszeit, eher fließend als mit scharfen Grenzen. |
| H2 | Sättigung (≈ 23 Fenster) bildet eine klar abgesetzte Insel bzw. Ausreißer; eine einfache Schwelle (ADC-Rand) findet sie ebenso sicher → kein Mehrwert. |
| H3 | Fenster mit Spike trennen sich von Fenstern ohne (Kurtosis, größter Ausschlag). |
| H4 | Nach der Stimulation: mit Satz P kaum unterscheidbar (AUC ≈ 0,5–0,6, nur mehr Spikes); mit P + L gut (0–10 min), aber nur über die Abweichung vom Vorlauf, nicht über den absoluten Pegel (Drift). |
| H5 | Während der Stimulation: nicht unterscheidbar (kein Artefakt im Modell). |
| H6 | Neustart und Uhrensprung: im Signal unsichtbar, nur als Segmentgrenzen. |
| H7 | Spektrale Merkmale tragen außer über Spikes wenig bei (weißes Rauschen, kein 50 Hz). |
| H8 | Gruppen ohne passendes Etikett sind am ehesten Folgen der Fensterbildung (Segmentränder) oder des Kartenrands. |

**Gesamterwartung:** Phase A bestätigt die Werkzeugkette, zeigt aber wahrscheinlich **keinen**
Mehrwert der ESOM gegenüber einfachen Verfahren, weil die Simulation nur wenige, einfache
Strukturen enthält. Die eigentliche Frage nach unbekannten Strukturen beantwortet Phase B.

## 7. Bewertungsmaße

- **Kartengüte:** Quantisierungs- und Topologiefehler je Seed.
- **Stabilität:** mittlere paarweise Übereinstimmung der Gruppen (Adjusted Rand Index, ARI) über
  die 10 Seeds. Als stabil gilt eine Struktur bei ARI ≥ 0,7.
- **Übereinstimmung mit bekannter Struktur:** ARI und NMI zwischen Gruppen und Etiketten; Reinheit
  je Etikett; ROC-AUC eines Auffälligkeitswerts (Quantisierungsfehler, U-Höhe am Gewinnerneuron)
  für Sättigung und für jede Stimulationsphase.
- **Paarvergleich Stimulation/Kontrolle:** Anteil der zeitgleichen Fensterpaare, deren
  Gewinnerneuronen > 3 Karteneinheiten auseinanderliegen, je Phase. Erwartung: nur „0–10 min
  danach“ (und mit P + L) deutlich über „vor“.
- **Zwei Nullmodelle**, jeweils mit denselben Kartenparametern und Seeds trainiert:
  (N1) Spalten unabhängig zufällig vertauscht (alle Zusammenhänge zwischen Merkmalen zerstört);
  (N2) eine einzige Normalverteilung mit demselben Mittel und derselben Kovarianz wie die echten
  Merkmale (lineare Zusammenhänge bleiben, Gruppen gibt es per Konstruktion keine). Was eine Karte
  auf N2 an „Mauern“ und Gruppen zeigt, ist Eigenleistung des Verfahrens und zählt nicht als Struktur.
  Maß: Zahl der Gruppen und Inseln nach Regel v2, Abgrenzungen, U-Kontrast (90. ÷ 50. Perzentil
  der U-Höhe).
- **Vergleichsverfahren** auf denselben Merkmalen: Hauptkomponenten (2D), k-Means (k = Gruppenzahl
  der ESOM), Isolation Forest, robuste Mahalanobis-Distanz, einfache Schwellen (ADC-Rand,
  Ausschlagzahl).

### Faire Vergleichsbedingungen

- ESOM und Vergleichsverfahren bekommen **dieselben Fenster und dieselbe normierte
  Merkmalsmatrix** (eine Datei, Prüfsumme im Ergebnis).
- Fenster überlappen (10 s, Schritt 5 s) und hängen zeitlich zusammen. Wo Daten zurückgehalten
  werden (Projektionstest, Schwellen für Fehlalarme, jede Klassifikation), wird **nach
  Rohdatenstunde (Segment) gruppiert** aufgeteilt (GroupKFold, 4 Teile), zusätzlich ein Standort
  ganz zurückgehalten. Nie liegen Fenster desselben Segments in Training und Test.
- Normierungsparameter und Schwellen (z. B. 1 % Fehlalarme) werden nur auf den Trainingsteilen
  bestimmt.
- Zufallsabhängige Vergleichsverfahren (k-Means, Isolation Forest) laufen ebenfalls mit den Seeds
  0–9.

## 8. Entscheidungsregeln

Klassifikation und Entdeckung werden **getrennt** bewertet; ein Mehrwert in einer der beiden
reicht für „Mehrwert“, muss aber als solcher benannt werden.

### 8a. Klassifikation bekannter Strukturen

- **Mehrwert für eine Frage**, wenn der Median über die 10 Seeds das beste Vergleichsverfahren um
  ≥ 0,05 (AUC bzw. ARI) übertrifft **und** in ≥ 8 von 10 Seeds besser ist. Gleich gut oder
  schlechter → das einfachere Verfahren hat Vorrang.

### 8b. Explorative Entdeckung

Eine Gruppe (oder ein Übergangsbereich) gilt als **entdeckte Struktur**, wenn alle Punkte gelten:

1. **Stabil:** in ≥ 8 von 10 Seeds wiederzufinden (beste Übereinstimmung der Fenstermengen,
   Jaccard ≥ 0,5).
2. **Über den Nullmodellen:** ihre Abgrenzung (Abschnitt 4) liegt über dem 95. Perzentil der
   Abgrenzungen aller Gruppen und Inseln auf N1 und N2. Zeigen die Nullmodelle in allen Seeds nur
   eine einzige Gruppe, ist dieser Punkt durch die Existenz der Gruppe erfüllt.
   (Ab A4 ergänzt durch den größenabhängigen Vergleich in Abschnitt 9; dieser Punkt bleibt als
   globale, konservative Schwelle bestehen.)
3. **Nachprüfbar:** Beispielfenster in den Rohdaten zeigen eine benennbare gemeinsame
   Eigenschaft; die Gruppe lässt sich danach durch eine einfache Regel auf die Merkmale beschreiben.
4. **Kein Verfahrensartefakt:** nicht durch Segmentränder, Kartenrand (planar ↔ toroidal) oder
   ein einzelnes extremes Merkmal erklärt.
5. **Überträgt sich:** im Projektionstest (zurückgehaltene Segmente) landen passende Fenster in
   derselben Gruppe.

Eine auffällige U-Matrix allein reicht nicht. Eine entdeckte Struktur ist ein **ESOM-spezifischer
Mehrwert**, wenn sie die Vergleichsverfahren nicht ohne Weiteres zeigen (k-Means mit derselben
Gruppenzahl trifft sie nicht mit Jaccard ≥ 0,5, sie ist in der 2D-Hauptkomponentenansicht nicht
abgegrenzt, und Isolation Forest/Mahalanobis heben sie nicht als auffällig hervor). Zeigt ein
Vergleichsverfahren sie ebenso, ist es eine Entdeckung, aber kein Vorteil der ESOM.
- **Scheingruppen:** Jede Gruppe mit ≥ 1 % der Fenster, die zu keinem Etikett eine Reinheit
  ≥ 0,5 hat, wird mit 5 Beispielfenstern dokumentiert und ihre Ursache untersucht.
- Jedes Ergebnis wird mit Schnappschuss-Prüfsumme, Merkmalssatz, Kartenparametern und Seed
  gespeichert und als SIMULATION gekennzeichnet.

## 9. Ergänzung E1 zu v2 (prospektiv, vor A4 festgelegt, gilt für A4 und Phase B)

Festgelegt am 05.11.2026 nach dem Bericht zu A1–A3 und **bevor A4 gerechnet wurde** (Vorgaben
Robby). Die Ergebnisse von A1–A3 bleiben nach v2 bewertet und werden nicht neu eingestuft. Alle
Bezeichnungen hier betreffen nur die **Erkennung von Strukturen in Simulationsdaten**, nie
biologische Ursachen.

### 9.1 Kandidaten

- Hauptkonfiguration: ESOM 40 × 60 **toroidal**, Endradius 0,75 (wie A3), je Satz P und P + L.
  Die planare Karte dient der Prüfung 8b.4.
- Kandidaten sind alle Komponenten (Gruppen außer der größten, und Inseln) der Seed-0-Karte.
  **Wiedergefunden** in einem anderen Seed heißt: Dort gibt es eine Komponente mit Jaccard ≥ 0,5
  zu den Seed-0-Fenstern des Kandidaten.
- Berichtet werden Kandidaten, die in ≥ 5 von 10 Seeds wiedergefunden werden. Die übrigen werden
  nur gezählt.

### 9.2 Größenklassen und Vergleichsmetrik

- **Größe** eines Kandidaten = Median seiner Fensterzahl über die Seeds, in denen er wiedergefunden
  wird. **Klassen** (Fenster): G1 10–19, G2 20–39, G3 40–79, G4 80–159, G5 160–319, G6 320–639,
  G7 640–1 279, G8 1 280–2 559, G9 ≥ 2 560.
- **Kandidatenwert A** = Median seiner Abgrenzung (Abschnitt 4) über die Seeds, in denen er
  wiedergefunden wird. Ein einzelner, zufällig besonders auffälliger Lauf zählt so nicht.
- **Nullläufe** je Satz in der Hauptkonfiguration: N1 mit den Seeds 0–99 (100 Läufe), N2 mit den
  Seeds 0–24 (25 Läufe). Komponenten nach Regel v2, mit Größe und Abgrenzung.
- **Nullstatistik je Klasse:** Für jeden Nulllauf mit mindestens einer Komponente in der Klasse
  zählt das **Maximum** der Abgrenzungen in dieser Klasse. Damit ist berücksichtigt, dass eine Karte
  viele Inseln zeigt und wir alle ansehen.
- **Schwelle je Klasse** = (1 − 0,05 / K)-Quantil dieser Maxima, K = Zahl der Klassen, in denen in
  dieser Konfiguration Kandidaten geprüft werden (Bonferroni über die Klassen).
- **Zu wenig Nulldaten:** Hat eine Klasse weniger als 20 Nullkomponenten oder weniger als 20 × K
  Nullläufe mit Komponente, wird für diese Klasse **keine Signifikanz behauptet**.
- **Bestanden (größenabhängig):** A liegt über der Schwelle seiner Klasse und die Klasse hat
  genug Nulldaten.

### 9.3 Globale Schwelle (Kriterium 8b.2 aus v2, konservativer Referenzwert)

Das 95. Perzentil der Abgrenzungen **aller** Nullkomponenten (N1 und N2, alle Nullläufe der
Konfiguration); gibt es keine, ist der Punkt durch die Existenz erfüllt. Verglichen wird A.

### 9.4 Operationalisierung der übrigen Punkte von 8b (eigenständige Voraussetzungen)

- **8b.1 stabil:** in ≥ 8 von 10 Seeds wiedergefunden.
- **8b.3 nachprüfbar:** (a) Ein Entscheidungsbaum der Tiefe 2 auf den unnormierten Merkmalen
  trennt Kandidat und Rest mit F1 ≥ 0,8; die Regel wird ausgegeben. (b) Beispielfenster in den
  Rohdaten werden angesehen, die gemeinsame Eigenschaft wird im Bericht in einem Satz benannt.
- **8b.4 kein Verfahrensartefakt:** (a) weniger als die Hälfte der Fenster liegt < 10 s an einem
  Segmentrand; (b) auf der planaren Karte in ≥ 5 von 10 Seeds wiedergefunden; (c) nicht ≥ 90 %
  der Fenster liegen in demselben Merkmal an der Normierungsgrenze ±8 (Ein-Merkmal-Extremstruktur).
- **8b.5 überträgt sich:** GroupKFold (4 Teile nach Segment) × Seeds 0–9, Normierung nur aus dem
  Training. In jedem Fall mit ≥ 5 Kandidatenfenstern im Testteil: Jaccard zwischen diesen Fenstern
  und der bestpassenden Komponente der Teilkarte (nur Testfenster). Erfüllt bei ≥ 3 Fällen und
  Median ≥ 0,5.

### 9.5 Drei Ergebnisstufen

| Stufe | Bedingungen |
|---|---|
| **Bestätigt nach ursprünglichem Kriterium** | 8b.1, globale Schwelle (9.3), 8b.3, 8b.4, 8b.5 |
| **Explorativ gestützt** | 8b.1, größenabhängig bestanden (9.2), 8b.3, 8b.4, 8b.5, aber globale Schwelle nicht |
| **Unbestätigter Kandidat** | in ≥ 5 von 10 Seeds wiedergefunden, erfüllt aber keine der beiden Stufen |

### 9.6 Zeigen einfachere Verfahren die Struktur ebenfalls? (ESOM-spezifischer Mehrwert)

Dieselbe normierte Merkmalsmatrix, **ohne Vorgabe der Struktur**:

- **k-Means** mit k = Zahl der Gruppen und k = Zahl aller Komponenten der ESOM (Seed 0), Seeds 0–9:
  zeigt die Struktur, wenn in ≥ 8 von 10 Seeds ein Cluster Jaccard ≥ 0,5 erreicht.
- **HDBSCAN** (min_cluster_size = 10): ein Cluster mit Jaccard ≥ 0,5.
- **Isolation Forest** (Seeds 0–9), **robuste Mahalanobis-Distanz** (MinCovDet), **LOF** (20
  Nachbarn): zeigt die Struktur, wenn ≥ 50 % der Kandidatenfenster unter den 1 % auffälligsten
  Fenstern liegen (Isolation Forest: in ≥ 8 von 10 Seeds).
- **Hauptkomponenten 2D:** Median-Anteil von Kandidatenfenstern unter den 10 nächsten Nachbarn
  ≥ 0,5.
- Wissensbasierte Schwellen zählen hier nicht, weil sie die Struktur vorgeben.
- **ESOM-spezifischer Mehrwert:** Keines dieser Verfahren zeigt die Struktur.

### 9.7 Klassifikation bekannter Strukturen (8a) in A4

- Aufgaben: **K1** Sättigung gegen alle übrigen Fenster; **K2** „0–10 min danach“ gegen „vor“ und
  **K3** „während“ gegen „vor“, beide nur in den Stimulationsreihen. Jeweils Satz P und P + L.
- Aufteilung: GroupKFold (4 Teile nach Segment) × Seeds 0–9. Jedes Verfahren wird auf den
  Trainingsteilen angepasst (Normierung ebenfalls), bewertet die Testfenster; AUC über alle
  Testfenster eines Seeds.
- **ESOM-Wert = Quantisierungsfehler** (vorab festgelegt). Die U-Höhe wird nur zusätzlich berichtet.
- Vergleich: Isolation Forest, MinCovDet-Mahalanobis, LOF (novelty), Abstand zum nächsten
  k-Means-Zentrum (k = 8), Rekonstruktionsfehler der Hauptkomponenten (95 % Varianz).
  Wissensbasierte Schwellen werden getrennt gezeigt: K1 Anteil am ADC-Rand, K2 |Abweichung vom
  Vorlauf|.
- Entscheidung nach 8a (v2).

### 9.8 Robustheit der Kartentopologie (Endradius)

- Endradius 0,75 (Basis), 1,5 und 3,0; ESOM planar und toroidal, beide Sätze, Seeds 0–9.
- Berichtet: Quantisierungs- und Topologiefehler, Zahl der Gruppen/Inseln und für jeden
  berichteten Kandidaten der Basis, in wie vielen Seeds er wiedergefunden wird und mit welcher
  Abgrenzung.
- **Maßgeblich für die Ergebnisstufen bleibt der Basisradius 0,75** (keine Auswahl nach Ergebnis).
  Ein größerer Radius gilt als „ohne Trennungsverlust“, wenn Sättigung, Reaktion und alle
  Kandidaten ab „explorativ gestützt“ dort ebenfalls in ≥ 8 von 10 Seeds wiedergefunden werden.
  Der Topologiefehler allein entscheidet nichts.

## 10. Ergänzung E2 (prospektiv, vor Phase B festgelegt, gilt nur für Phase B)

Festgelegt am 05.11.2026 nach A4 und **bevor Phase B gerechnet wurde** (Vorgaben Robby).
Grundlagen: `PRUEFUNG_QUELLEN_HARDWARE.md`, Ablauf: `PHASE_B_VORBEREITUNG.md`. Die Ergebnisse
und Bewertungen von Phase A (v2 bzw. v2 + E1) bleiben unverändert. Wo E2 nichts sagt, gilt E1.
Alle Ergebnisse betreffen nur die Erkennung von Strukturen in **synthetischen** Signalen.

### 10.1 Ersatz für 8b.4c (Ein-Merkmal-Struktur) in Phase B

Grundlage sind die unnormierten Merkmale aller Fenster des Laufs. Zur **Merkmalsgruppe** eines
Merkmals m gehören m selbst und alle Merkmale mit |Spearman-ρ| ≥ 0,8 zu m (über alle Fenster).

- **(c1) Ein-Merkmal-Struktur:** Sie liegt vor, wenn beide Bedingungen gelten:
  (i) Eine einzelne Schwelle auf **einem** Merkmal m trennt den Kandidaten vom Rest mit
  F1 ≥ 0,90 (Entscheidungsbaum mit einem Knoten, Klassengewichte ausgeglichen).
  (ii) Ohne die **ganze Merkmalsgruppe** von m erreicht ein Baum der Tiefe 2 auf den übrigen
  Merkmalen nur F1 < 0,50.
  Eine Ein-Merkmal-Struktur besteht 8b.4 nicht. Sie wird mit ihrer Schwelle berichtet und kann
  nie als „ESOM-spezifischer Mehrwert“ gelten, weil schon eine einfache Schwelle sie findet.
- **(c2) Normierungsgrenze:** Der Kandidat muss auch mit der Normierungsgrenze ±16 statt ±8 in
  ≥ 5 von 10 Seeds wiedergefunden werden (Jaccard ≥ 0,5). Sonst besteht er 8b.4 nicht, weil
  erst das Abschneiden ihn erzeugt.
- 8b.4a (Segmentrand) und 8b.4b (planar ≥ 5 von 10) gelten unverändert.

### 10.2 Ersatz für 8b.5 (Übertragung) in Phase B

- **Gültiger Prüffall:** GroupKFold nach unabhängig erzeugter Reihe × Seeds 0–9. Ein Fall zählt
  nur, wenn **Trainings- und Testteil** je ≥ 5 Kandidatenfenster enthalten. Fälle, in denen das
  Training die Struktur nie gesehen hat, prüfen Neuheit statt Übertragung. Sie werden getrennt
  berichtet, aber nicht mitgezählt. Die Neuheit prüft B2.
- **≥ 3 gültige Fälle:** bestanden bei Median-Jaccard ≥ 0,5, sonst **nicht bestanden**.
- **< 3 gültige Fälle:** **nicht prüfbar**. Ein solcher Kandidat erreicht höchstens die Stufe
  „Unbestätigter Kandidat (Übertragung nicht prüfbar)“, nie eine der beiden oberen Stufen.
- **Aufbau der Testsignale:** Jede Struktur des Generators kommt in ≥ 4 unabhängig erzeugten
  Reihen vor, jede Reihe mit eigenem Seed. Damit ist 8b.5 für alle bekannten Strukturen
  prüfbar. Ist eine bekannte Struktur trotzdem „nicht prüfbar“, gilt das als Fehler im
  Versuchsaufbau und wird berichtet.

### 10.3 Geprüfte Schlupflöcher

| Mögliches Schlupfloch | Gegenmaßnahme |
|---|---|
| Fast gleiche Merkmale (z. B. Flachheit und Gleichheitsfolge bei Sättigung): Nach dem Entfernen von m trennt das Zwillingsmerkmal weiter, (ii) wäre nie erfüllt. | Die ganze Merkmalsgruppe (ρ ≥ 0,8) wird entfernt (10.1). |
| Eine Gruppe entsteht erst durch das Abschneiden an ±8, weil viele Fenster auf demselben Grenzwert liegen. | Zusatzprüfung c2 mit ±16, verbindlich. |
| Bäume finden bei sehr kleinen Inseln zufällig eine Regel. | Kontrolle je Lauf und Größenklasse: Für 20 zufällige Fenstermengen gleicher Größe muss ein Baum der Tiefe 2 im Median F1 < 0,3 erreichen. Sonst ist 8b.3a für diese Größe nicht aussagekräftig und wird als „nicht prüfbar“ geführt. |
| „Nicht prüfbar“ statt „nicht bestanden“ könnte schwache Kandidaten besser aussehen lassen. | „Nicht prüfbar“ sperrt beide oberen Stufen (10.2). |
| Fälle ohne Kandidat im Training werden weggelassen, die Übertragung sieht dadurch besser aus. | Gewollt, denn das sind Neuheitsfälle. Ihre Zahl und ihr Ergebnis werden getrennt berichtet. |
| Zwei Reihen mit identischem Rauschen würden eine Übertragung vortäuschen. | Eigener Seed je Reihe; Prüfsumme je Rohfenster, keine identischen Fenster zwischen Reihen. |
| Merkmale werden angepasst, nachdem man die B2-Daten gesehen hat. | `mv2` und der gesamte Auswertungscode werden vor dem Öffnen der B2-Auswahl eingefroren (Commit, 10.5). Jede spätere Änderung ist eine Protokollabweichung und wird berichtet. |
| Viele Verfahren × viele Formen × viele Kennzahlen. | Ein einziger Hauptendpunkt (10.4); alles andere sind Nebenergebnisse ohne Bestätigungsanspruch. |

### 10.4 Hauptendpunkt und Entscheidungsregel zur ESOM

**Hauptendpunkt:** B2 mit **wiederkehrenden** neuen Formen (Anteil 3 %), Merkmalssatz `mv2`,
Hardware-Modell H-ideal. Eine neue Form gilt für ein Verfahren als **gefunden**, wenn ein Cluster
bzw. eine Komponente in ≥ 8 von 10 Seeds Jaccard ≥ 0,5 zu den Fenstern der Form erreicht. Bei
Ausreißerverfahren muss die Trefferquote unter den 1 % auffälligsten Fenstern ≥ 0,5 sein.

Vergleichsverfahren: HDBSCAN (auf den Merkmalen), UMAP + HDBSCAN, Matrix-Profile (Motive im
Rohsignal), Change-Point-Erkennung, Isolation Forest, robuste Mahalanobis-Distanz. Die ESOM läuft
in zwei Formen, die getrennt berichtet werden: die eigene Umsetzung (`karte-v1`) und die
Referenzumsetzung (R-Paket `Umatrix`, `esomTrain`, mit der dort vorgesehenen Gruppierung).

Ein **weiterer Einsatz der ESOM ist gerechtfertigt**, wenn mindestens eine Bedingung gilt:

1. Die ESOM (eine der beiden Umsetzungen) findet **≥ 2 neue Formen, die keines der übrigen
   Verfahren findet**, und sie findet insgesamt nicht weniger Formen als das beste übrige
   Verfahren.
2. In B3 trennt die ESOM eine schwache Struktur noch bei einem um **≥ 3 dB** kleineren
   Signal-Rausch-Verhältnis als das beste übrige Verfahren (Median über die Seeds, in ≥ 8 von
   10 Seeds).
3. Im verblindeten Ansichtstest (10.6) markiert die Mehrheit von ≥ 3 Personen auf der U-Matrix
   **mehr Strukturen richtig** als auf der UMAP-Ansicht (mit generalisierter U-Matrix), ohne
   mehr Falschmarkierungen.
4. Im Langzeitversuch B7 (10.7) bleibt die feste ESOM-Referenzkarte nach den dort festgelegten
   Kennzahlen stabiler als die übrigen festen Verfahren.

**Ein Gleichstand reicht nicht.** Dann wird für BioComm das einfachere, verbreitete Verfahren
empfohlen. Erfüllt die ESOM nur Bedingung 3 oder 4, wird sie als **ergänzendes Ansichts- bzw.
Einordnungswerkzeug** empfohlen, nicht als Entdeckungsverfahren.

### 10.5 Verblindung der neuen Formen (B2)

1. Cody erstellt einen **Katalog von ≥ 16 möglichen neuen Formen** mit Generatorparametern und
   committet ihn (Datum, Prüfsumme). Erwünscht sind zusätzlich Formen aus der Literatur
   (`PRUEFUNG_QUELLEN_HARDWARE.md`, Abschnitt 1) sowie Formen von Robby oder Dritten. Bei jeder
   Form wird vermerkt, wer sie beigetragen hat.
2. `mv2`, Generator, Hardware-Modelle und der gesamte Auswertungscode für B2 werden
   **eingefroren und committet**.
3. **Robby** wählt **≥ 8 Formen** aus (oder lost sie mit einem nur ihm bekannten Startwert). Er
   legt die Auswahl als Datei mit einem geheimen Zusatz (Salt) ab. Committet wird **nur deren
   Prüfsumme**.
4. Erst danach wird die Auswahl geöffnet und B2 mit dem eingefrorenen Code gerechnet.
5. **Bekannte Einschränkung:** Cody entwirft sowohl die Merkmale als auch den Katalog. Echte
   Unabhängigkeit gibt es nur für Formen, die jemand anderes beisteuert. Der Bericht nennt diese
   Einschränkung ausdrücklich und weist das Ergebnis **getrennt** für Formen von Cody und für
   Formen von anderen aus.
6. **Negativkontrolle:** Immer dabei ist eine bekannte Form mit Parametern innerhalb des
   Trainingsbereichs. Sie darf nicht als neu gemeldet werden.

### 10.6 Verblindeter Ansichtstest (U-Matrix gegen UMAP)

- Die Beurteilenden kennen weder die Wahrheit noch die Auswahl der Formen. Sie bekommen dieselben
  Daten einmal als U-Matrix und einmal als UMAP-Ansicht mit generalisierter U-Matrix, in
  zufälliger Reihenfolge, und markieren auffällige Bereiche. Ausgewertet wird gegen die
  Wahrheit: richtig markierte Strukturen und Falschmarkierungen.
- **Mit ≥ 3 Personen** wird nach 10.4, Bedingung 3 bewertet. **Mit weniger als 3 Personen** wird
  das Ergebnis nur explorativ berichtet, ohne Anspruch auf einen bestätigten Vorteil.

### 10.7 Langzeitversuch B7 (feste Referenzkarte)

- Die Karte und die Vergleichsverfahren (feste UMAP-Abbildung, feste PCA, feste
  k-Means-Zentren, Isolation Forest) werden auf Zeitraum 1 angepasst und danach **nicht mehr
  verändert**. Eingeordnet werden dann drei Zeiträume: (a) unveränderte Bedingungen,
  (b) langsame Drift (Elektrodenalterung, Jahreszeit), (c) dieselbe Drift plus eine neue Form.
- **Kennzahlen:**
  - Anteil der Fenster einer bekannten Struktur, die in derselben Komponente landen wie im
    Zeitraum 1;
  - Verschiebung der Trefferverteilung (Jensen-Shannon-Abstand);
  - Fehlalarme unter reiner Drift (a, b) gegen Treffer der neuen Form (c), bei einer vorab
    festgelegten Fehlalarmquote von 1 %.
- **Stabil** heißt: In (a) und (b) bleiben ≥ 90 % der Fenster bekannter Strukturen in ihrer
  Komponente. In (c) wird die neue Form mit einer Trefferquote ≥ 0,5 gemeldet, und (b)
  überschreitet die Fehlalarmquote nicht.
