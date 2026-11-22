# Nachrechnung von Phase A mit pydbt: Bericht R0–R5

Stand 22.11.2026 · Regeln `NACHRECHNUNG_PYDBT.md` (Abschnitte 6, 7a–7f, alle vor dem jeweiligen
Lauf festgelegt) · pydbt `4a4b33e` (0.0.125), Python 3.13.17, C-Bibliothek geladen · Merkmale
`mv1` aus A3 (sha256 je Lauf in den Lauf-Metadaten) · 140 pydbt-Läufe (R1 + R2 je 20, R3 100)
und 20 Läufe unserer Karte (R4), alle ohne Fehler. R5: 20 Läufe mit der neuen pydbt-Fassung
`e6a483e` (Zweig `features-next-release`), ebenfalls ohne Fehler. Zwischenfassung (R0–R2) vom 15.11. in der Git-Historie.

> **SIMULATION.** Grundlage sind die Sandbox-Szenarien `sbx-gen-1.0`. Es sind keine Messwerte.
> Die Ergebnisse sagen etwas über die Verfahren, nie über Biologie.

Dateien: `r0.json`, `r1_r2.json` (V1–V3), `ursache_r2.json` (Ursachensuche), `v4.json` (V4), `r4.json` (R4),
`r5_technik.json` + `r5.json` (R5),
`nulldaten.json` (Prüfsummen der Nulldaten). Gewichte und Nulldaten (`laeufe/`, `nulldaten/`)
bleiben lokal.

## 1. Ergebnis

Nach den vorab festgelegten Regeln ist das Gesamturteil **abweichend**. Es wäre es schon ohne R3
gewesen: In R2 ist die Reaktionsgruppe nur teilweise reproduziert (5/10), und von den 11 in A4
stabilen Kandidaten sind nur 4 reproduziert (36 %, verlangt sind zwei Drittel). Die Abweichung
betrifft fast nur Spike-Gruppen, die schon in A4 als Lage-Fragmente eingestuft waren. pydbt
fasst sie zu größeren Gruppen zusammen. Die Ursache ist nicht abschließend geklärt (Abschnitt 5).
Nach R4 (Abschnitt 5b) erklärt der größere Endradius von pydbt die Abweichung **teilweise**, und
das nur unter Vorbehalt. Das Muster der Verluste ist bei unserer Karte ein anderes.
Nach R5 (Abschnitt 5c, neue pydbt-Fassung mit gleichem σ-Verlauf wie unsere Karte) erklärt die
Nachbarschaft die Abweichung **nicht**: Wieder sind nur 4 der 11 stabilen Kandidaten reproduziert.
Auch das gilt unter Vorbehalt (P K13 nur 7/10). Die Ursache liegt damit im Training selbst
(online statt Batch, Lernrate, Startwerte); welcher dieser drei Punkte, bleibt offen.

**V4** (Abschnitt 6) bestätigt dagegen das Bild aus A4: Die globale Schwelle bestehen unter pydbt
nur die beiden Sättigungen und die Spike-Gruppe der Fenstermitte. Die Spike-Gruppe hat pydbt
allerdings mit einer Nachbargruppe zusammengefasst, und das führt dazu, dass V4 nach der
mechanischen Lesart als nicht erfüllt gilt.

## 2. R0 (Technik, V0)

Siehe `r0.json` und `NACHRECHNUNG_PYDBT.md` 7d: Bei gleichem Seed rechnet pydbt deterministisch,
und die Übergabe der Gewichte stimmt (Gewinnerneuronen Anteil 1,0). V0 auf Chainlink 10 × 15
ist **übereinstimmend** (ARI 1,0 bei beiden Umsetzungen).

## 3. V1 Kartengüte (nur berichtet)

| | QE P | QE PL | TE P | TE PL | Gruppen P / PL | Inseln P / PL | min je Lauf |
|---|---|---|---|---|---|---|---|
| A4 (`karte-v1`, 40 × 60, Endradius 0,75) | 1,23 | 1,70 | 0,115 | 0,118 | 3 / 3 | 15 / 46 | – |
| R1 pydbt-Standard 50 × 80, 24 Epochen | 1,10 | 1,55 | 0,186 | 0,198 | 2 / 2 | 4 / 11 | 25–31 |
| R2 angeglichen 40 × 60, 40 Epochen, r 29 → 1 | 1,18 | 1,64 | 0,222 | 0,238 | 2 / 4 | 6 / 19 | 26–37 |

(Mediane über 10 Seeds.) pydbt bildet die Daten etwas genauer ab (QE kleiner), ordnet sie aber
weniger nachbarschaftstreu an (TE fast doppelt so hoch) und ergibt deutlich weniger Inseln.

## 4. V2 und V3 (wiedergefunden von 10 Läufen, Jaccard ≥ 0,5)

| Satz | Kand. | Rohdaten (A4) | A4 | R1 | R2 | Urteil R2 |
|---|---|---|---|---|---|---|
| P | K16 | **Sättigung** | 10 | 10 | 10 | reproduziert |
| P | K13 | Sprung | 9 | 8 | 8 | reproduziert |
| P | K3 | Spike am Rand oder negativ | 10 | 0 | 2 | nicht reproduziert |
| P | K10 | Spike in der Fenstermitte | 8 | 0 | 2 | nicht reproduziert |
| P | K2 | kleiner Spike | 6 | 0 | 1 | nicht reproduziert |
| PL | K52 | **Sättigung** | 10 | 10 | 10 | reproduziert |
| PL | K13 | **Reaktion** | 10 | 8 | **5** | **teilweise** |
| PL | K2 | Sprung am Reaktionsbeginn | 10 | 10 | 10 | reproduziert |
| PL | K1 | schwächerer Sprung | 8 | 5 | 3 | nicht reproduziert |
| PL | K37 | Spike nahe Anfang/Ende | 10 | 0 | 0 | nicht reproduziert |
| PL | K28 | Spike am Fensterende | 9 | 0 | 0 | nicht reproduziert |
| PL | K46 | Spike am Fensterende | 9 | 2 | 2 | nicht reproduziert |
| PL | K6 | Spike in der Mitte | 7 | 0 | 0 | nicht reproduziert |
| PL | K40 | Spike am Fensteranfang | 6 | 1 | 2 | nicht reproduziert |
| PL | K3 | großer Spike | 5 | 0 | 0 | nicht reproduziert |

- **V2 (bekannte Strukturen) in R2: nicht erfüllt.** Beide Sättigungen 10/10, die Reaktion nur 5/10.
- **V3:** stabil in A4 (≥ 8/10) waren 11 Kandidaten, davon in R2 reproduziert 4 (P K16, P K13,
  PL K52, PL K2) = 36 %.
- **Neue Komponenten** (in ≥ 5 Läufen, keinem Kandidaten entsprechend): R1 je 2, R2 je 3.
  Ihre Einstufung folgt mit V4.
- **Reinheit** (nur berichtet, 7d): 0,70–1,00 in allen Fällen. Die Kandidatenfenster liegen also
  auch in pydbt überwiegend auf eigenen Neuronen. Sie werden nur nicht als eigene Gruppe
  abgegrenzt.

## 5. Ursachensuche (Abschnitt 6, beschreibend)

`werkzeuge/nachrechnung_ursache.py`: Wo landen die Fenster eines Kandidaten in R2?

- **Die Kandidaten zerfallen nicht.** Bei 13 von 15 liegen im Median ≥ 87 % der Fenster in einer
  einzigen pydbt-Komponente.
- **Benachbarte Spike-Gruppen verschmelzen.** Die Komponente ist 2- bis 3-mal so groß wie der
  Kandidat. Dabei werden immer dieselben Partner mitgezogen: P K3 mit K10 (7/10 Läufe), PL K28
  mit K37 (10/10), PL K6 mit K7/K8/K20, PL K46 mit K38/K43. In A4 waren das nach Lage des
  Spikes im Fenster getrennte Gruppen (H8, „Spike-Lage-Fragmente“).
- **Kleine und flache Strukturen gehen in die Hauptmasse.** Die Reaktion (PL K13) bleibt immer
  beisammen (Anteil 1,00), liegt aber in 5 von 10 Läufen ohne Mauer in der größten Komponente.
  Ebenso P K2 (7/10) und PL K1 (5/10).
- **Unverändert:** Sättigung (beide Sätze) und die Sprung-Gruppen P K13 und PL K2.

**Einordnung.** Das Muster gleicht der Robustheitsprüfung in A4 (Abschnitt 6 dort): Mit größerem
Endradius blieben Sättigung und Reaktion erhalten, aber die Spike-Gruppen verschmolzen. Bei pydbt
endet die Nachbarschaft bei σ = 1,0 (Radius 1), bei `karte-v1` bei σ = 0,75; dieser Wert lässt
sich in pydbt nicht einstellen (7a). Dazu kommen Online- statt Batch-Training und eine andere
Initialisierung. Gegen den Endradius als alleinige Ursache spricht der **höhere**
Topologiefehler (0,22 statt 0,115; ein größerer Endradius hat ihn in A4 gesenkt). **Die Ursache
ist deshalb offen.**

## 5a. V4: Nullmodelle und Schwellen (R3)

`werkzeuge/nachrechnung_v4.py`, rechnet mit `mm/kriterien.py` und den Funktionen aus A4.
Nullläufe: N1 und N2 je Seeds 0–24 (7d), dieselben Matrizen wie in A4 (`nulldaten.json`), mit
R2-Parametern. Kandidaten: Komponenten der R2-Seed-0-Karte außer der größten, in ≥ 5 von 10
Läufen wiedergefunden (9.1).

| | P | P + L |
|---|---|---|
| Nullkomponenten pydbt (50 Läufe) / je Lauf | 475 / 9,5 | 301 / 6,0 |
| Nullkomponenten A4 (125 Läufe) / je Lauf | 2 058 / 16,5 | 1 429 / 11,4 |
| **globale Schwelle pydbt** / A4 | **3,16** / 2,53 | **3,33** / 2,23 |

Auch auf Zufallsdaten bildet pydbt weniger, aber besser abgegrenzte Komponenten. Die Schwelle
liegt deshalb höher.

**Größenabhängige Schwelle (9.2): in keiner Klasse anwendbar.** Mit 50 statt 125 Nullläufen ist
die Mindestzahl (20 Läufe mit Komponente je geprüfter Klasse) nirgends erreicht. Das ist eine
Folge der Wahl in 7d, kein Ergebnis über die Kandidaten.

| Satz | R2-Kand. | Fenster | A | Läufe | F1 Baum | global | A4-Gegenstück (Jaccard) | A4 global |
|---|---|---|---|---|---|---|---|---|
| P | K1 | 23 | 298 | 10 | 1,00 | **✓** | K16 Sättigung (1,00) | ✓ |
| P | K3 | 1 360 | 3,47 | 9 | 0,95 | **✓** | keins: K10 + K3 zusammen (0,46) | (K10 ✓, K3 ✗) |
| P | K6 | 11 | 1,54 | 8 | 0,96 | ✗ | K13 Sprung (0,92) | ✗ |
| P | K5 | 20 | 1,27 | 5 | 0,85 | ✗ | keins (0,03) | – |
| P | K7 | 11 | 1,21 | 5 | 0,67 | ✗ | keins (0,05) | – |
| PL | K15 | 24 | 5,33 | 10 | 1,00 | **✓** | K52 Sättigung (1,00) | ✓ |
| PL | K2 | 26 | 1,87 | 10 | 0,90 | ✗ | K2 Sprung (0,88) | ✗ |
| PL | K16 | 230 | 1,88 | 5 | 0,97 | ✗ | K13 Reaktion (0,94) | ✗ |
| PL | K5 | 662 | 1,92 | 10 | 0,91 | ✗ | keins (0,31) | – |
| PL | K1 | 246 | 1,54 | 10 | 0,63 | ✗ | keins (0,31) | – |
| PL | K13 | 13 | 1,30 | 5 | 0,11 | ✗ | keins (0,00) | – |

**Zum Gesamturteil.** Die Regel verlangt, dass „kein Kandidat die globale Schwelle besteht, der
sie in A4 nicht bestanden hat“. Wie ein R2-Kandidat einem A4-Kandidaten zugeordnet wird, legt
die Regel nicht fest. Das Auswertungsskript nimmt Jaccard ≥ 0,5. Diese Festlegung habe ich nach
R2, aber vor dem Rechnen von V4 getroffen. Danach hat **P K3 kein Gegenstück** und gilt als
„neu bestanden“, V4 ist also **nicht erfüllt**. Inhaltlich ist P K3 die Spike-Gruppe der
Fenstermitte (A4 K10, die in A4 die globale Schwelle bestand), zusammengefasst mit der
Nachbargruppe A4 K3. Eine neue Struktur, die A4 übersehen hätte, ist das nicht. Am Gesamturteil
ändert beides nichts, denn es ist schon durch V2 und V3 „abweichend“.

**Neue Komponenten:** PL K5 und PL K1 sind die zusammengefassten Spike-Gruppen aus Abschnitt 5,
gut abgegrenzt, aber unter der Schwelle. P K5, P K7 und PL K13 sind kleine, nur in 5 von 10
Läufen gefundene Inseln. Keine davon besteht die globale Schwelle.

## 5b. R4: Ursachentest Endradius (Regeln 7e, vor dem Lauf festgelegt)

`werkzeuge/nachrechnung_r4.py`: unsere `karte-v1` wie in A4 (40 × 60 Torus, 40 Epochen), nur mit
Endradius σ = 1,0 statt 0,75. Kein pydbt. 20 Läufe, je etwa 40 s. Datei `r4.json`.

| Satz | Kandidat | Rolle (7e) | A4 | R2 pydbt | **R4** | R4 verschmolzen mit |
|---|---|---|---|---|---|---|
| P | K3 | geprüft | 10 | 2 | **9** | – |
| P | K10 | geprüft | 8 | 2 | **1** | – |
| PL | K1 | geprüft | 8 | 3 | **3** | K2 (6/10), 3× in der größten Komponente |
| PL | K13 Reaktion | geprüft | 10 | 5 | **10** | – |
| PL | K28 | geprüft | 9 | 0 | **10** | K27 (6/10) |
| PL | K37 | geprüft | 10 | 0 | **6** | – |
| PL | K46 | geprüft | 9 | 2 | **7** | K43 (5/10), K40 (3/10) |
| P | K16 Sättigung | Gegenprobe | 10 | 10 | **10** | – |
| P | K13 Sprung | Gegenprobe | 9 | 8 | **7** | K11 (8/10) |
| PL | K52 Sättigung | Gegenprobe | 10 | 10 | **10** | – |
| PL | K2 Sprung | Gegenprobe | 10 | 10 | **10** | K1 (5/10) |

(Wiedergefunden von 10 Läufen, Jaccard ≥ 0,5 mit der A4-Seed-0-Karte. „Verschmolzen mit“: andere
A4-Komponenten mit ≥ 10 % der Kandidatengröße in derselben Komponente, wie in Abschnitt 5.)

**Urteil nach 7e:** 4 der 7 geprüften Kandidaten sind verloren (P K10, PL K1, PL K37, PL K46). Der
Endradius erklärt die Abweichung damit **teilweise**. Weil in der Gegenprobe P K13 nur in 7 von 10
Läufen wiedergefunden wird, gilt das Urteil nach 7e **nur unter Vorbehalt**.

**Nur berichtet** (Mediane): QE P / PL 1,30 / 1,79, TE 0,070 / 0,071, Gruppen 3 / 2, Inseln 30 / 60.
Unsere Karte mit σ = 1,0 ist etwas ungenauer als A4 (QE höher) und noch nachbarschaftstreuer (TE
0,07 statt 0,115). Bei pydbt ist der TE dagegen auf 0,22 gestiegen.

**Beschreibend, ohne neue Regel:** Das Muster ist ein anderes als bei pydbt.
- Die beiden größten Verluste unter pydbt bleiben in R4 erhalten: die Reaktion (10/10, nie in der
  größten Komponente) und PL K28 (10/10).
- P K3 und P K10 verschmelzen in R4 nicht miteinander (unter pydbt 7/10). K3 bleibt, K10 verliert
  sich ohne einen erkennbaren Partner, zerfällt also eher. Dasselbe gilt für PL K37.
- Gleich wie unter pydbt verhalten sich nur PL K1, das mit dem Sprung K2 zusammengeht, und
  teilweise PL K46 mit K43.
- PL K46 (7/10) und P K13 (7/10) liegen knapp unter der Grenze von 8.

Der Zähler nach 7e lautet also „teilweise“. Die Läufe zeigen aber nicht, dass der größere
Endradius dieselben Verschmelzungen wie pydbt hervorruft. Zusammen mit dem gegenläufigen
Topologiefehler spricht das dafür, dass der größere Teil der Abweichung im Training liegt
(online statt Batch, Initialisierung, Lernrate). Das ist eine Deutung und kein Ergebnis nach
den Regeln.

## 5c. R5: pydbt mit angeglichener Nachbarschaft (Regeln 7f, vor dem Lauf festgelegt)

Anlass: Die Entwickler haben pydbt erweitert (Zweig `features-next-release`, Commit `e6a483e`).
Mit ihrem Vorschlag `start_radius=29, end_radius=0.5, EXPONENTIAL_SIGMA, KERNEL_WIDTH, seed=s`
läuft σ genau wie in `karte-v1` von 15 auf 0,75. Sonst wie R2: 40 × 60 Torus, 40 Epochen, Seeds
0–9, Sätze P und PL, Auswertung mit unserem Code. Etwa 37 min je Lauf.

**R5-0 Technik** (`r5_technik.json`): pydbt-eigene Trainingstests 28/28 bestanden; zweimal
`seed=0` ergibt identische Gewichte und Gewinnerneuronen; unser Code findet dieselben
Gewinnerneuronen (Anteil 1,0); σ-Verlauf gleich wie `karte-v1` (Abweichung 0, σ 15 → 0,75); V0
auf Chainlink 10 × 15: ARI-Median 1,0. Alle Läufe haben pydbt nachweislich aus dem neuen
Arbeitsordner geladen (Pfad und Commit je Lauf in den Metadaten).

| Satz | Kandidat | A4 | R2 pydbt alt | R4 unsere, σ 1,0 | **R5 pydbt neu** | R5 verschmolzen mit |
|---|---|---|---|---|---|---|
| P | K3 | 10 | 2 | 9 | **6** | K10 (5/10) |
| P | K10 | 8 | 2 | 1 | **5** | K3 (4/10) |
| P | K13 Sprung | 9 | 8 | 7 | **7** | K11 (10/10) |
| P | K16 Sättigung | 10 | 10 | 10 | **10** | – |
| PL | K1 | 8 | 3 | 3 | **7** | K2 (6/10) |
| PL | K2 Sprung | 10 | 10 | 10 | **10** | – |
| PL | K13 Reaktion | 10 | 5 | 10 | **8** | 2× in der größten Komponente |
| PL | K28 | 9 | 0 | 10 | **4** | K42 (9/10), K37 (8/10), K27 (7/10) |
| PL | K37 | 10 | 0 | 6 | **3** | K28 (6/10), K42 (6/10), K45 (5/10) |
| PL | K46 | 9 | 2 | 7 | **5** | K38 (9/10), K43 (9/10) |
| PL | K52 Sättigung | 10 | 10 | 10 | **10** | – |

(Die 11 in A4 stabilen Kandidaten. Wiedergefunden von 10 Läufen, Jaccard ≥ 0,5 mit der
A4-Seed-0-Karte. Nicht stabil in A4 und nur berichtet: P K2 5/10, PL K3 4/10, PL K6 2/10,
PL K40 2/10.)

**Urteil nach 7f:** V2 ist reproduziert (beide Sättigungen 10/10, Reaktion 8/10), aber nur
**4 der 11** stabilen Kandidaten (P K16, PL K2, PL K13, PL K52), genauso viele wie in R2. Nach
7f erklärt die Nachbarschaft die Abweichung damit **nicht**; die Ursache liegt im Training selbst
und bleibt in diesem Rahmen offen. **Gegenprobe:** P K13 wird nur in 7 von 10 Läufen
wiedergefunden (R2: 8), das Urteil gilt deshalb **unter Vorbehalt**. Am Urteil ändert der
Vorbehalt nichts: Selbst mit P K13 wären es 5 der 11 und damit weiter „nicht“.

**Nur berichtet** (Mediane): QE P / PL 1,21 / 1,67, TE 0,155 / 0,168, Gruppen 3 / 4, Inseln
10 / 30. Der Topologiefehler liegt zwischen A4 (0,115) und dem alten pydbt (0,22). Eine neue
Komponente in ≥ 5 Läufen (P, 1 299 Fenster, 5/10) trifft den nächsten A4-Kandidaten mit Jaccard
0,48, knapp unter der Grenze.

**Beschreibend, ohne neue Regel:**
- Die Reaktion ist wieder da (R2 5/10, R5 8/10). Der alte, auf 1 gerundete Endradius erklärt
  vermutlich diesen einen Verlust (Deutung).
- Die Lage-Fragmente der PL-Fenstermitte (K28, K37, K46) verschmelzen weiter, jetzt mit
  wechselnden Nachbarn (K42, K45, K38, K43). Unsere Karte hält sie bei gleichem σ getrennt.
- P K3 und P K10 gehen in etwa der Hälfte der Läufe zusammen, wie unter dem alten pydbt.
- Mit gleichem σ-Verlauf und gleicher Kernform bleibt als Unterschied nur, wie trainiert wird:
  pydbt rechnet online (Fenster für Fenster, Lernrate 0,5 → 0,1, gleichverteilte Startwerte),
  `karte-v1` im Batch. R5 kann diese drei Punkte nicht trennen.

## 6. Was das für Phase A heißt

- **Stabil über beide Umsetzungen:** Sättigung, Sprung am Reaktionsbeginn (PL K2) und Sprung in
  P (K13). Das sind die Strukturen, die in A4 auch einfachere Verfahren fanden.
- **Nicht übertragbar:** die feine Aufteilung der Spikes nach ihrer Lage im Fenster. Sie war
  schon in A4 als Schwäche des Merkmalssatzes eingestuft. Die Nachrechnung zeigt jetzt
  zusätzlich, dass sie von der ESOM-Umsetzung abhängt.
- **Reaktion:** Sie ist in pydbt als Fenstermenge vorhanden, aber nur in der Hälfte der Läufe
  durch eine Mauer abgegrenzt.
- **Schwellen:** Unter beiden Umsetzungen heben sich nur die Sättigung und die Spike-Gruppe der
  Fenstermitte deutlich von Zufallsdaten ab. Sprung und Reaktion liegen in beiden Fällen
  darunter. Die Rangfolge aus A4 bleibt also erhalten.
- Nach Abschnitt 6 wird **nicht** die Umsetzung gewählt, deren Ergebnis besser aussieht. Wie es
  weitergeht, entscheiden wir gemeinsam mit den Entwicklern.

## 7. Abweichungen von den Regeln

- **Keine `.lrn`-Dateien** (Abschnitt 3): pydbt hat die Merkmale und Nulldaten direkt als Matrix
  bekommen, nicht über exportierte `.lrn`-Dateien. Die Prüfsumme der Daten steht in jedem Lauf.
- **Zuordnung R2 → A4 für V4** (Jaccard ≥ 0,5): nicht vorab festgelegt, siehe 5a.
- **Größenabhängige Schwelle** mangels Nullläufen nicht anwendbar, siehe 5a.

## 8. Offen

- Ursache der Abweichung: Nach R4 erklärt der Endradius sie nur teilweise und unter Vorbehalt
  (5b), nach R5 die Nachbarschaft insgesamt nicht (5c). Ob Online-Training, Lernrate oder
  Startwerte den Unterschied ausmachen, ist nicht geprüft. Für die neue pydbt-Fassung gibt es
  keine Nullläufe (kein V4, R6 nur nach neuer Absprache). Weitere Läufe gibt es nur nach neuer
  Absprache.
- Rückfrage an die Entwickler (16.11. gestellt): Lässt sich in pydbt ein Endradius unter 1
  einstellen, und wie grenzen sie Inseln ab?
