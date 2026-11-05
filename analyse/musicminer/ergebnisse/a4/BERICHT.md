# A4: Methodenvergleich, größenabhängiger Nullmodellvergleich, Robustheit des Endradius

Stand 05.11.2026 · Kriterien **v2 + Ergänzung E1** (`KRITERIEN.md`, Abschnitt 9; festgelegt in
Commit 0301a87 vor diesem Lauf) · Schnappschuss sha256 `e9e4b139…0fbd16` · Merkmalssatz `mv1`
· Karte `karte-v1`, 40 × 60, 40 Epochen · Seeds 0–9, Nullläufe N1 0–99, N2 0–24 · Laufzeit 82 min.

> **SIMULATION.** Alle Ergebnisse beziehen sich auf die Sandbox-Szenarien `sbx-gen-1.0`. Es sind
> keine Messwerte. Die Ergebnisstufen sagen nur etwas über die **Erkennung von Strukturen in
> Simulationsdaten**, nie über biologische Ursachen. A1–A3 bleiben nach v2 bewertet und wurden
> nicht neu eingestuft.

Dateien: `metriken.json` (alle Zahlen), `beispiele.json` + `abbildungen/beispiele_kandidaten.png`
(Rohdaten, 8b.3b), `abbildungen/pca_kandidaten_*.png`, `abbildungen/robustheit_*.png`.
Werkzeuge: `werkzeuge/a4_laufen.py`, `werkzeuge/a4_beispiele.py`.

## 1. Kurzfassung

1. **Kein Kandidat erreicht „Bestätigt nach ursprünglichem Kriterium“ oder „Explorativ gestützt“.**
   Alle 15 berichteten Kandidaten (5 in P, 10 in P + L) sind **unbestätigte Kandidaten**.
2. **Die Sprungstruktur finden auch einfachere Verfahren, ohne dass man sie ihnen vorgibt.**
   HDBSCAN bildet für die Sprung-Insel (P + L) einen eigenen Cluster. k-Means findet sie, wenn
   k so groß ist wie die Zahl aller ESOM-Komponenten, und in der 2D-Hauptkomponentenansicht
   liegt sie abgegrenzt. Der Sprung ist also eine echte Struktur in den Merkmalen, aber **kein
   Vorteil der ESOM**.
3. **Klassifikation bekannter Strukturen (8a): kein Mehrwert der ESOM.** Bei der Sättigung sind
   alle Verfahren nahezu perfekt. Bei „nach der Stimulation“ ist die robuste Mahalanobis-Distanz
   besser als die ESOM, und eine einfache wissensbasierte Schwelle ist am besten.
4. **Robustheit:** Mit Endradius 1,5 sinkt der Topologiefehler um 70 %. Sättigung und Reaktion
   bleiben dabei erhalten, die Spike-Gruppen verschwinden aber. Endradius 3,0 verliert auch die
   Sättigung. Ein größerer Radius ist also kein reiner Gewinn.
5. **Nur zwei Kandidaten wären ESOM-spezifisch** (kein einfacheres Verfahren zeigt sie). Beide
   sind in den Rohdaten **Spike-Lage-Fragmente**: Der Spike liegt am Fensteranfang bzw. am
   Fensterende. Sie sind schlecht nachprüfbar (F1 0,34 bzw. 0,54) und gehen auf die bekannte
   Lageabhängigkeit der Merkmale (H8) zurück, nicht auf eine neue Signalform.

## 2. Nullmodelle und Schwellen

| | P | P + L |
|---|---|---|
| Nullkomponenten (N1 + N2, 125 Läufe) | 2 058 | 1 429 |
| globale Schwelle (95. Perzentil, 9.3) | 2,53 | 2,23 |
| geprüfte Klassen (K) | G1, G2, G6 (K = 3, Quantil 0,983) | G1, G2, G3, G5 (K = 4, Quantil 0,9875) |
| Schwelle G1 (10–19) | 1,91 (593 Komp., 100 Läufe) | 1,61 (366 Komp., 97 Läufe) |
| Schwelle G2 (20–39) | 3,07 (993 Komp., 100 Läufe) | 2,39 |
| Schwelle G3 (40–79) | – | 2,06 |
| G5 / G6 | **0 Nullkomponenten → keine Signifikanz behauptet** | ebenso |

Die Nullmodelle bilden nur kleine Inseln. Für große Gruppen (≥ 160 Fenster) gibt es deshalb
keine Vergleichsgrundlage, und nach E1 wird dort keine größenabhängige Signifikanz behauptet.
Die größenabhängige Schwelle ist nur in **G1** deutlich niedriger als die globale (1,91 statt
2,53 bzw. 1,61 statt 2,23). In G2 liegt sie darüber (P: 3,07) oder etwa gleich (P + L: 2,39). Der
Grund: E1 nimmt das Maximum je Lauf und korrigiert über die Klassen, und die Nullmodelle bilden
gerade in G2 viele gut abgegrenzte Inseln.

## 3. Kandidaten und Ergebnisstufen (Hauptkonfiguration: toroidal, Endradius 0,75)

Spalten: n = Median der Fensterzahl · A = Median der Abgrenzung · Seeds = wiedergefunden von 10
(toroidal / planar) · F1 = Baum Tiefe 2 · Ü = Übertragung (Median Jaccard, Fälle).
Prüfpunkte: **S** stabil 8b.1, **G** global 9.3, **K** größenabhängig 9.2, **N** nachprüfbar
8b.3a, **A** kein Verfahrensartefakt 8b.4, **Ü** überträgt sich 8b.5.

### Satz P (nur Signalform)

| Kand. | Rohdaten (8b.3b) | n | A | Seeds | F1 | Ü | S G K N A Ü | zeigen auch |
|---|---|---|---|---|---|---|---|---|
| K16 | **Sättigung**: flach auf 2 560 µV | 23 | 13,3 | 10/10 | 1,00 | 0,00 (10) | ✓ ✓ ✓ ✓ ✗ ✗ | k-Means (k alle), HDBSCAN, PCA-2D |
| K13 | **Sprung** 10–40 µV im Fenster (Median 16,7 µV), 83 % „während“ | 17 | 1,82 | 9/10 | 0,92 | 0,70 (10) | ✓ ✗ ✗ ✓ ✗ ✓ | Mahalanobis, PCA-2D |
| K10 | ein Spike **in der Fenstermitte** | 631 | 3,02 | 8/6 | 0,92 | 0,78 (40) | ✓ ✓ – ✓ ✗ ✓ | Isolation Forest, Mahalanobis, PCA-2D |
| K3 | ein Spike am Rand oder negativ | 549 | 2,15 | 10/6 | 0,83 | 0,82 (40) | ✓ ✗ – ✓ ✗ ✓ | PCA-2D |
| K2 | kleiner Spike, sonst Rauschen | 28 | 1,41 | 6/6 | 0,68 | 0,59 (40) | ✗ ✗ ✗ ✗ ✓ ✓ | PCA-2D |

„–“ = keine Signifikanz behauptet (zu wenig Nulldaten). 16 weitere Komponenten wurden in weniger
als 5 Seeds wiedergefunden und werden nur gezählt.

### Satz P + L (Signalform + Lage gegenüber dem Vorlauf)

| Kand. | Rohdaten (8b.3b) | n | A | Seeds | F1 | Ü | S G K N A Ü | zeigen auch |
|---|---|---|---|---|---|---|---|---|
| K52 | **Sättigung** (ein Fenster mit dem Übergang) | 24 | 4,49 | 10/10 | 1,00 | 0,15 (10) | ✓ ✓ ✓ ✓ ✗ ✗ | k-Means (k alle), HDBSCAN, Mahalanobis, PCA-2D |
| K13 | **Reaktion**: Niveau gegenüber dem Vorlauf verschoben, im Fenster kein Sprung; 96,5 % „0–10 min danach“ | 225 | 1,94 | 10/10 | 0,95 | 0,93 (40) | ✓ ✗ – ✓ ✗ ✓ | k-Means (k alle), HDBSCAN, PCA-2D |
| K2 | **Sprung** am Reaktionsbeginn (Median 9,7 µV), 96 % „während“ | 17 | 1,49 | 10/10 | 0,84 | 0,83 (30) | ✓ ✗ ✗ ✓ ✗ ✓ | **k-Means (k alle), HDBSCAN**, PCA-2D |
| K1 | **schwächerer Sprung**/Anstieg (Median 9,3 µV), 100 % „während“ | 15 | 1,43 | 8/9 | 0,80 | – (0) | ✓ ✗ ✗ ✓ ✗ ✗ | LOF, PCA-2D |
| K28 | Spike **am Fensterende** | 74 | 1,35 | 9/10 | 0,28 | 0,59 (30) | ✓ ✗ ✗ ✗ ✗ ✓ | k-Means (k alle) |
| K37 | Spike nahe Anfang/Ende (Lage-Quartile 0,07–0,19) | 70 | 1,28 | 10/10 | 0,34 | 0,51 (40) | ✓ ✗ ✗ ✗ ✗ ✓ | k-Means (k alle) |
| K46 | Spike **am Fensterende**, auch negativ | 59 | 1,27 | 9/7 | 0,54 | 0,53 (30) | ✓ ✗ ✗ ✗ ✗ ✓ | **keines** |
| K40 | Spike **am Fensteranfang** | 67 | 1,27 | 6/1 | 0,28 | 0,41 (40) | ✗ ✗ ✗ ✗ ✗ ✗ | **keines** |
| K6 | ein Spike in der Mitte, auch negativ | 291 | 1,54 | 7/5 | 0,78 | 0,49 (40) | ✗ ✗ – ✗ ✗ ✗ | Isolation Forest, Mahalanobis, PCA-2D |
| K3 | großer Spike, teils doppelt | 22 | 1,24 | 5/4 | 0,52 | 0,37 (20) | ✗ ✗ ✗ ✗ ✗ ✗ | Isolation Forest, Mahalanobis, PCA-2D |

42 weitere Komponenten wurden in weniger als 5 Seeds wiedergefunden.

### Woran die Stufen scheitern

- **Sprung-Inseln (P K13, PL K2, PL K1):** Sie sind stabil, nachprüfbar und übertragen sich
  (PL K2: Jaccard 0,83). Ihre Abgrenzung liegt aber **unter der größenabhängigen Schwelle**
  (1,82 < 1,91 bzw. 1,49 < 1,61) und unter der globalen Schwelle. Damit bleiben sie
  **unbestätigte Kandidaten**, wie nach A3.
- **Reaktionsgruppe (PL K13):** Sie ist stabil, nachprüfbar und überträgt sich am besten von
  allen (0,93). Ihre Abgrenzung liegt unter der globalen Schwelle, und für G5 gibt es keine
  Nulldaten. Außerdem wird sie fast nur durch ein Merkmal getragen (`abw_vorlauf` an der
  Normierungsgrenze, 8b.4c). Ergebnis: **unbestätigter Kandidat**, wie nach A3.
- **Sättigung (P K16, PL K52):** Sie besteht beide Schwellen. Sie scheitert an zwei Punkten:
  (1) **8b.5**, weil die Sättigung nur in **einem** Segment vorkommt. Liegt dieses Segment im
  Testteil, hat die Teilkarte nie eine Sättigung gesehen, und eine Übertragung ist hier gar
  nicht prüfbar. (2) **8b.4c**, weil sie an mehreren Merkmalen gleichzeitig an der
  Normierungsgrenze liegt.
- **Spike-Gruppe P K10** (in A3 die Gruppe, die das N1-Kriterium bestand): Sie besteht die globale
  Schwelle, ist stabil, nachprüfbar und überträgt sich. Sie scheitert **nur an 8b.4**: Sie ist
  auf der planaren Karte nur in 6/10 Seeds wiederzufinden (das reicht für 8b.4b), aber
  ≥ 90 % ihrer Fenster liegen bei `kurtosis` an der Normierungsgrenze (8b.4c).

### Hinweis zur Prüfung 8b.4c (nicht rückwirkend angewendet)

8b.4c wurde wörtlich umgesetzt: ≥ 90 % der Fenster eines Kandidaten liegen bei **irgendeinem**
Merkmal an der Normierungsgrenze ±8. Das trifft 14 von 15 Kandidaten. Der Grund: Die robuste
Skalierung schiebt seltene Strukturen (Spikes → Kurtosis, Reaktion → Abweichung vom Vorlauf)
fast immer an die Grenze. Die Prüfung soll eigentlich „durch ein einzelnes extremes Merkmal
erklärt“ abfangen. In dieser Form fängt sie auch Strukturen ab, die zusätzlich durch weitere
Merkmale beschrieben werden.

**Die Stufen oben bleiben so, wie sie nach der festgelegten Regel herauskommen.** Rein zur
Einordnung: Ohne 8b.4c würde sich nur bei **P K10** (Spike in der Fenstermitte) etwas ändern.
Diese Gruppe wäre dann „Bestätigt nach ursprünglichem Kriterium“, ein Ergebnis, das auch
Isolation Forest und Mahalanobis liefern. Die Sprung-Inseln und die Reaktionsgruppe blieben
unbestätigt, weil ihnen die Abgrenzung über den Nullmodellen fehlt. Ob 8b.4c für Phase B
präzisiert wird (z. B. „der Kandidat ist durch eine Schwelle auf genau einem Merkmal
vollständig beschrieben“, F1 ≥ 0,95 mit einem einzigen Baumknoten), ist vor B zu entscheiden.

## 4. Kann ein einfacheres Verfahren die Sprungstruktur entdecken, ohne Vorgabe?

**Ja.** Alle Verfahren arbeiten auf derselben normierten Merkmalsmatrix, ohne Etiketten und ohne
Hinweis auf Sprünge:

| Sprung-Insel | HDBSCAN | k-Means (k = Gruppen) | k-Means (k = alle Komponenten) | Isolation Forest | Mahalanobis | LOF | PCA-2D |
|---|---|---|---|---|---|---|---|
| PL K2 (17 F.) | **ja** | nein | **ja** (≥ 8/10 Seeds) | nein | nein | nein | **ja** |
| P K13 (17 F.) | nein | nein | nein (Jaccard 0,44) | nein (38 %) | **ja** (50 % im obersten 1 %) | nein | **ja** |
| PL K1 (15 F.) | nein | nein | nein | nein | nein | **ja** (50 %) | **ja** |

- **HDBSCAN** ist das stärkste Argument. Es bekommt weder eine Clusterzahl noch eine Struktur
  vorgegeben und bildet für die Sprungfenster (mit Lagemerkmalen) einen eigenen Cluster.
- Bei k-Means mit „k = alle Komponenten“ stammt die Zahl k von der ESOM. Das ist ein Hinweis auf
  die Zahl der Cluster, aber keiner auf die Struktur.
- In der 2D-Hauptkomponentenansicht sind die Sprungfenster Nachbarn untereinander
  (`pca_kandidaten_*.png`). Ein Mensch, der diese Ansicht ansieht, hätte sie ebenfalls bemerken
  können.
- Ohne Lagemerkmale (Satz P) findet nur die robuste Mahalanobis-Distanz die Sprung-Insel, und
  zwar als Ausreißer, nicht als eigene Gruppe.

Fazit: Die Sprungstruktur war in A3 eine echte, nachprüfbare Entdeckung (sie hat einen
Modell-Effekt aufgedeckt). Sie ist aber **keine Stärke, die nur die ESOM hat**.

## 5. Klassifikation bekannter Strukturen (8a)

AUC, Median über 10 Seeds, GroupKFold (4 Teile nach Segment), ESOM-Wert = Quantisierungsfehler.

| Aufgabe | Satz | ESOM QE | (ESOM U) | Isol. Forest | Mahalanobis | LOF | k-Means-Abstand | PCA-Rekonstr. | wissensbasiert | Entscheidung |
|---|---|---|---|---|---|---|---|---|---|---|
| K1 Sättigung | P | 1,00 | (0,90) | 0,98 | 0,99 | 1,00 | 1,00 | 1,00 | 1,00 | gleich gut → einfacheres Verfahren |
| K1 Sättigung | PL | 1,00 | (0,83) | 0,98 | 0,99 | 1,00 | 1,00 | 1,00 | 1,00 | gleich gut → einfacheres Verfahren |
| K2 0–10 min danach vs. vor | P | 0,53 | (0,55) | 0,54 | 0,54 | 0,49 | 0,53 | 0,54 | – | kein Verfahren trennt |
| K2 0–10 min danach vs. vor | PL | 0,78 | (0,83) | 0,72 | **0,85** | 0,61 | 0,76 | 0,56 | **0,96** | Mahalanobis besser; Schwelle am besten |
| K3 während vs. vor | P | 0,58 | (0,57) | 0,57 | 0,57 | 0,56 | 0,57 | 0,55 | – | kein Verfahren trennt |
| K3 während vs. vor | PL | 0,64 | (0,63) | 0,61 | 0,64 | 0,55 | 0,62 | 0,58 | – | gleich (ESOM in 2/10 Seeds besser) |

In keiner Aufgabe erreicht die ESOM die Bedingung von 8a (≥ 0,05 besser und in ≥ 8 von 10 Seeds).
Ohne Lagemerkmale ist die Reaktion für kein Verfahren zu sehen (AUC ≈ 0,53). Das bestätigt A3:
Sie unterscheidet sich im Modell vor allem im Niveau, nicht in der Form.

Hinweis: LOF meldet „Duplicate values“. Die Ursache sind die völlig gleichen Sättigungsfenster.
Bei K1 bleibt LOF trotzdem bei AUC 1,00, auf das Ergebnis hat die Warnung also keinen Einfluss.

## 6. Robustheit der Kartentopologie (Endradius, 9.8)

| Satz | Topologie | Endradius | QE | TE | Gruppen (Median) | Inseln (Median) | Sättigung | Reaktion (PL K13) | Spike-Gruppen | Sprung (P K13 / PL K2 / PL K1) |
|---|---|---|---|---|---|---|---|---|---|---|
| P | torus | **0,75** | 1,23 | 0,115 | 3 | 15 | 10 | – | 10 / 8 | 9 / – / – |
| P | torus | 1,5 | 1,42 | 0,034 | 3 | 51 | 10 | – | **0 / 0** | 5 |
| P | torus | 3,0 | 1,65 | 0,012 | 2 | 44 | **0** | – | 0 / 10 | 5 |
| PL | torus | **0,75** | 1,70 | 0,118 | 3 | 46 | 10 | 10 | (K6: 7) | – / 10 / 8 |
| PL | torus | 1,5 | 1,93 | 0,036 | 2 | 66 | 10 | 10 | 1 | – / 9 / 1 |
| PL | torus | 3,0 | 2,21 | 0,012 | 2 | 50 | **0** | **0** | 10 | – / 4 / 2 |

(planar ähnlich, Einzelwerte in `metriken.json`; Werte = wiedergefunden von 10 Seeds.)

- **Der Topologiefehler geht deutlich zurück:** 0,115 → 0,034 → 0,012. Der Quantisierungsfehler
  steigt dabei um 15 % bzw. 34 %, die Karte bildet die Daten also gröber ab.
- **Endradius 1,5 gilt nach 9.8 als „ohne Trennungsverlust“:** Sättigung und Reaktion bleiben in
  10/10 Seeds erhalten, und es gibt keinen Kandidaten ab „explorativ gestützt“, der fehlen könnte.
  Trotzdem gehen dabei die Spike-Gruppen verloren, und die Sprung-Insel wird schwächer (P: 5/10,
  PL K1: 1/10). Feine Strukturen verschmelzen.
- **Endradius 3,0 verliert die Sättigung** (0/10) und in P + L auch die Reaktion. Das ist zu glatt.
- Die Zahl der Inseln steigt bei größerem Radius, weil sich die Prototypen gleichmäßiger
  verteilen und dadurch mehr kleine, leere Wände entstehen. Das sind keine neuen Strukturen,
  denn keine dieser Inseln besteht in ≥ 5 Seeds.
- **Fazit:** Der kleine Endradius 0,75 erzeugt einen hohen Topologiefehler, trennt aber feiner.
  Ein mittlerer Radius (1,5) wäre für die Darstellung ein vernünftiger Kompromiss. Für die
  Entdeckung kleiner Strukturen kostet er Auflösung. Maßgeblich für die Stufen bleibt, wie
  festgelegt, 0,75.

## 7. Gesamteinordnung nach A4

| Frage aus dem Arbeitsauftrag | Antwort (nur Simulationsdaten) |
|---|---|
| Trennt die ESOM bekannte Strukturen besser? | **Nein.** Sie ist gleich gut (Sättigung) oder schlechter als Mahalanobis bzw. eine einfache Schwelle (Reaktion). |
| Findet die ESOM unbekannte Strukturen, die andere übersehen? | **In A4 nicht.** Alles Stabile und Nachprüfbare zeigt mindestens ein einfacheres Verfahren. Die beiden ESOM-spezifischen Inseln sind Spike-Lage-Fragmente. |
| Ist die Karte als Ansicht nützlich? | **Ja, als Übersicht.** Sie stellt Sättigung, Spikes, Sprung und Reaktion gleichzeitig mit ihrer Nachbarschaft dar. Diesen Nutzen bewertet A4 nicht als statistischen Vorteil. |
| Wo liegt die eigentliche Schwäche? | Bei den **Merkmalen** (`mv1`): Die Lage eines Spikes im Fenster erzeugt Scheinunterschiede, und die Normierungsgrenze ±8 wird von seltenen Strukturen fast immer erreicht. |

Für Phase B folgt daraus (Vorbereitung in `../../PHASE_B_VORBEREITUNG.md`): Zuerst den
lageneutralen Merkmalssatz `mv2` mit dem Verschiebungstest prüfen. Die Neuheitsfrage (B2) wird
dann der eigentliche Test, ob die ESOM gegenüber HDBSCAN, Isolation Forest und Mahalanobis
etwas Eigenes leistet. Vor B zu entscheiden sind: die Präzisierung von 8b.4c, und ob die
Übertragungsprüfung 8b.5 bei Strukturen aus nur einem Segment als „nicht prüfbar“ statt als
„nicht erfüllt“ gilt.
