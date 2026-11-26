# Nachrechnung von Phase A mit einer Referenz-ESOM (RefESOM): Vergleichsregeln

**Freigegeben am 14.11.2026 (Robby), vor jedem Lauf.** Offen bis vor R1 und nur an den
gekennzeichneten Stellen: RefESOM-Commit, Parameterzuordnung R2, Umfang R3. Danach gelten nur
noch dokumentierte, begründete Ergänzungen, nie Änderungen nach Ansicht der Ergebnisse.

> **Namen (26.11.2026):** „RefESOM“ ist ein Arbeitsname für die Referenz-Umsetzung der ESOM, die uns ihre
> Entwickler privat zur Verfügung gestellt haben. Paketname, Beteiligte und ihre Software nennen wir hier
> erst mit ihrer Zustimmung. Die Werkzeuge laden das Paket über die lokale Umgebungsvariable
> `REFESOM_MODUL` (`werkzeuge/refesom_laden.py`). Die Datei hieß bis 26.11.2026 anders; ältere Commits
> verweisen auf den früheren Namen.

> **SIMULATION.** Grundlage sind dieselben Simulationsdaten wie in Phase A (Sandbox-Szenarien
> `sbx-gen-1.0`). Es sind keine Messwerte. Die Nachrechnung sagt etwas über die Verfahren und
> ihre Umsetzung, nie über Biologie.

## 1. Zweck und Abgrenzung

Phase A wurde mit einer eigenen Batch-SOM (`karte-v1`, `mm/karte.py`) gerechnet. Die
Nachrechnung prüft, ob die Ergebnisse an dieser eigenen Umsetzung hängen. Dafür wird die
ESOM-Bibliothek RefESOM verwendet, die uns die Entwickler zur Verfügung gestellt haben.

Zwei Fragen:

1. **Umsetzung:** Verhält sich `karte-v1` auf einem Datensatz mit bekannter Lösung wie eine
   etablierte ESOM?
2. **Reproduzierbarkeit:** Finden sich die Strukturen und die Kernaussage von Phase A mit RefESOM
   wieder?

**Phase A wird dadurch nicht neu bewertet.** Ihre Ergebnisstufen, Kriterien (v2, E1) und
Berichte bleiben unverändert. Abweichungen werden als Ergebnis der Nachrechnung berichtet und
untersucht, nicht in Phase A übertragen. Findet RefESOM eine Struktur, die Phase A nicht hatte,
ist das eine **neue Hypothese** und kein Befund. Sie wird erst in einem eigenen, vorab
festgelegten Schritt geprüft, frühestens in Phase B.

## 2. Software und Umgebung

- RefESOM wird aus dem privaten Repository in einen Ordner **außerhalb des Git** geklont.
  Fest gehalten wird ein Commit: der vollständige Commit-Hash steht vor dem ersten Lauf hier.
  Ein späterer Wechsel des Commits ist ein neuer, gekennzeichneter Lauf.
- Eigene Python-Umgebung nur für diese Nachrechnung (nicht `venv/` der Analyse, nicht der
  Server). RefESOM kommt **nicht** in `requirements.txt` und nicht in die CI, solange es nicht
  veröffentlicht ist.
- Kein RefESOM-Code wird in dieses (öffentliche) Repository kopiert. Ergebnisse aus RefESOM
  (Zahlen, Bilder) werden erst nach Rücksprache mit den Entwicklern veröffentlicht.
- Protokolliert wird je Lauf: Commit, Python-Version, ob die C-Bibliothek geladen wurde
  („C library not found“ = reiner Python-Code), alle Parameter, Seed, Laufzeit.
- Finden wir einen Fehler in RefESOM, melden wir ihn den Entwicklern. Ein eigener Patch wird nur
  mit Diff dokumentiert verwendet und der Lauf gekennzeichnet.

## 3. Daten

- **Dieselben normierten Merkmalsmatrizen wie in A3/A4:** `ergebnisse/a3/merkmale_P.npz` und
  `merkmale_PL.npz` (Schnappschuss `e9e4b139…0fbd16`, Merkmalssatz `mv1`, Normierung auf ±8).
  Sie werden unverändert als `.lrn` exportiert, der Schlüssel ist die Fensternummer.
  sha256 der `.npz` und der `.lrn` stehen im Ergebnis.
- **Nullmodelle:** N1 (Spalten vertauscht) und N2 (eine Normalverteilung) werden mit dem Code
  und den Seeds aus A4 erzeugt, also dieselben Matrizen wie dort, und ebenfalls als `.lrn`
  exportiert.
- **Referenzdatensatz mit bekannter Lösung:** `Chainlink.lrn` aus dem RefESOM-Repository
  (zwei verschlungene Ringe, FCPS) mit der zugehörigen Klassendatei, falls vorhanden.

## 4. Gruppen und Maße: dieselbe Auswertung für beide Verfahren

Damit nur das **Training** verglichen wird, nicht die Auswertung, gilt:

- RefESOM liefert Gewichte (`.wts`) und Gewinnerneuronen (`.bm`). Gruppen, Inseln und Abgrenzung
  werden daraus mit **unserer Gruppenregel v2** und unserem Code berechnet, Quantisierungs- und
  Topologiefehler ebenfalls mit unserem Code.
- Die U-Matrix, P-Matrix und U\*-Matrix von RefESOM werden zusätzlich als Bilder gezeigt. Eine
  Inselbestimmung mit RefESOM-eigenen Werkzeugen (z. B. `.imx`) wird nur ergänzend berichtet und
  geht in keine Entscheidung ein.
- **Wiedergefunden** heißt wie in E1 (9.1): Es gibt eine Komponente mit Jaccard ≥ 0,5 zu den
  Fenstern des Phase-A-Kandidaten (Seed 0 der Hauptkonfiguration von A4).

## 5. Läufe in fester Reihenfolge

| Schritt | Inhalt | Läufe |
|---|---|---|
| **R0** Technik | RefESOM-eigene Tests laufen durch; das Chainlink-Beispiel aus der Anleitung läuft. Laufzeit eines Laufs auf P + L wird gemessen. | – |
| **R0b** Gegenprobe Umsetzung | `karte-v1` und RefESOM auf Chainlink, je 10 Seeds, toroidal. | 2 × 10 |
| **R1** RefESOM nach Empfehlung | Parameter **wie von den Entwicklern empfohlen**; liegt keine Empfehlung vor, die Werte aus ihrer Anleitung: 50 × 80, 24 Epochen, toroidal, sonst Standardwerte. Satz P und P + L. | 2 × 10 |
| **R2** RefESOM angeglichen | 40 × 60, toroidal, 40 Epochen, Radius- und Lernratenverlauf so nah an `karte-v1` wie RefESOM es erlaubt. Die Zuordnung der Parameter wird **nach dem Lesen des RefESOM-Codes, aber vor R1** hier eingetragen. | 2 × 10 |
| **R3** Nullmodelle | RefESOM mit R2-Parametern auf N1 (Seeds 0–99) und N2 (Seeds 0–24), je Satz. Ist ein Lauf in R0 länger als 3 min, werden es N1 0–24 und N2 0–24; diese Wahl wird nach R0 und vor R1 hier eingetragen. | bis 2 × 125 |

Hat RefESOM keinen Seed-Parameter, werden die 10 Läufe als Wiederholungen gerechnet und das wird
vermerkt. Ist RefESOM bei gleichem Seed nicht deterministisch, ebenfalls.

**R1 kommt vor R2**, damit wir RefESOM nicht unbewusst auf unsere Ergebnisse hin einstellen.

## 6. Vergleichsregeln (vorab festgelegt)

**V0 Umsetzung (R0b).** ARI zwischen Gruppen und den Chainlink-Klassen, Median über 10 Seeds.
*Übereinstimmend*, wenn beide Verfahren ARI ≥ 0,9 erreichen oder der Unterschied der Mediane
< 0,1 ist. Sonst *abweichend*, und die Ursache wird vor allen weiteren Schritten gesucht.

**V1 Kartengüte (R1, R2).** Quantisierungs- und Topologiefehler je Lauf, neben den A4-Werten
(QE 1,23 / 1,70, TE 0,115 / 0,118). Nur berichtet, keine Entscheidung, weil die
Kartengröße in R1 eine andere ist.

**V2 Bekannte Strukturen (R1, R2).** Sättigung (P K16, PL K52) und Reaktionsgruppe (PL K13).
*Reproduziert*, wenn in ≥ 8 von 10 Läufen wiedergefunden.

**V3 Kandidaten aus A4 (R1, R2).** Für jeden der 15 berichteten Kandidaten: in wie vielen der
10 Läufe wiedergefunden. *Reproduziert* ≥ 8, *teilweise* 5–7, *nicht reproduziert* ≤ 4.
Zusätzlich gezählt: Komponenten in ≥ 5 Läufen, die keinem A4-Kandidaten entsprechen
(neue Hypothesen, siehe Abschnitt 1).

**V4 Nullmodelle und Stufen (R3).** Mit den RefESOM-Nullläufen werden die Schwellen nach E1
(9.2, 9.3) neu berechnet und die Kandidaten aus R2 damit eingestuft (8b.1, globale und
größenabhängige Schwelle; 8b.3a mit dem Baum Tiefe 2). Die Prüfungen 8b.4b (planare Karte) und
8b.5 (Übertragung) werden **nicht** wiederholt; ein Kandidat kann in der Nachrechnung deshalb
höchstens „würde Schwellen bestehen“ heißen, nie eine Stufe aus Phase A erreichen.

**Gesamturteil.**

- **Kernaussage von Phase A bestätigt**, wenn V0 übereinstimmt, V2 in R2 reproduziert ist,
  mindestens zwei Drittel der in A4 stabilen Kandidaten (8b.1 erfüllt) in R2 reproduziert sind
  und in V4 kein Kandidat die globale Schwelle besteht, der sie in A4 nicht bestanden hat.
- **Abweichend** in jedem anderen Fall. Jede Abweichung wird untersucht (gleiche Daten?
  Parameter? Gruppenregel? Fehler in einer der Umsetzungen?) und mit Ursache oder als „Ursache
  offen“ berichtet.
- Bei Abweichung wird **nicht** die Umsetzung gewählt, deren Ergebnis besser aussieht. Die
  Entscheidung, wie weiter verfahren wird, treffen wir gemeinsam mit den Entwicklern.

## 7. Ergebnis und Bericht

- `ergebnisse/nachrechnung/BERICHT.md` und `metriken.json`, lokal. Große Dateien und alles mit
  RefESOM-Bildern bleiben bis zur Rücksprache außerhalb des Git.
- Der Bericht nennt alle Läufe, auch fehlgeschlagene, und jede Abweichung von diesen Regeln.
- Eintrag in `VERLAUF.md`.

## 7a. Nachträge vor R1 (14.11.2026, nach Lesen des RefESOM-Codes, vor jedem Lauf)

**RefESOM-Commit:** `cdedeba40b323b98cc2e6c322b58c4f84ec081f4` (08.10.2026, Version 0.0.124),
geklont nach `Desktop/openmyconet_extern/RefESOM` (außerhalb jedes Git-Repositorys von uns).

**Was RefESOM anders macht als `karte-v1`** (aus `RefESOM/umatrix/training.py`):

| | `karte-v1` (Phase A) | RefESOM `esom_train` |
|---|---|---|
| Lernverfahren | Batch (alle Fenster je Epoche auf einmal) | online (Fenster einzeln, je Epoche zufällig gemischt) |
| Startwerte | zufällige Datenpunkte | gleichverteilt zwischen Min. und Max. jedes Merkmals |
| Nachbarschaft | Gauß, σ = Radius, ohne Abschneiden | Gauß, σ = (Radius + 1) / 2, abgeschnitten bei ⌊Radius⌋ |
| Abkühlung | geometrisch, σ 15 → 0,75 | linear (oder „lead in/lead out“), Radius 24 → 1 |
| Lernrate | keine (Batch) | linear 0,5 → 0,1 |
| Zufall | eigener Seed | globaler Zufallsgenerator von numpy, kein Seed-Parameter |

**Seeds:** Vor jedem Lauf wird `np.random.seed(s)` gesetzt (s = 0–9 bzw. Nullmodell-Seeds).
In R0 wird geprüft, ob zwei Läufe mit gleichem Seed identisch sind.

**R1 (Empfehlung):** solange keine Empfehlung der Entwickler vorliegt, `EsomTrainingParams.build(
rows=50, cols=80, epochs=24, toroid=True)` mit allen übrigen Standardwerten (Radius 24 → 1
linear, Lernrate 0,5 → 0,1 linear, Startwerte Min/Max, Rundung 4 Stellen).

**R2 (angeglichen):** `rows=40, cols=60, epochs=40, toroid=True, start_radius=29, end_radius=1`,
übrige Werte Standard. Begründung: RefESOM-Radius r entspricht σ = (r + 1)/2; σ 15 (Startwert
`karte-v1`) ergibt r = 29. Das Ende lässt sich nicht angleichen: σ 0,75 hieße r = 0,5, und RefESOM
würde dann nur noch das Gewinnerneuron selbst anpassen. Daher r = 1 (σ = 1, kleinster Wert mit
Nachbarschaft). Geometrische Abkühlung gibt es in RefESOM nicht, daher linear. Diese Unterschiede
sind gewollt sichtbar: R2 prüft, ob Phase A vom genauen Trainingsverfahren abhängt, nicht, ob
RefESOM `karte-v1` nachbaut.

**Auffälligkeiten im RefESOM-Code** (nur berichtet, nichts verändert; an die Entwickler):

1. Planare Karte, U-Matrix: In `neighbors()` stehen für die Ecke unten rechts Spaltenindizes
   `rows-2`/`rows-1` statt `cols-2`/`cols-1`. Betrifft nur planare Karten; wir rechnen toroidal.
2. Planare Karte, Training: Nachbarn außerhalb der Karte werden auf den Rand geschoben (`clip`)
   statt weggelassen. Randneuronen werden dadurch je Schritt mehrfach angepasst. Nur planar.
3. `esom_train` schreibt `is_toroid=True` in die Gewichte- und Bestmatch-Daten, auch bei
   planarer Karte.
4. `pyproject.toml` nennt die MIT-Lizenz, die Datei `LICENSE` die MPL 2.0.

Da alle Läufe toroidal sind, betreffen 1–3 die Nachrechnung nicht.

## 7b. Nachtrag vor R0 (15.11.2026, nach Antwort der Entwickler, vor jedem Lauf)

- **Neuer RefESOM-Commit:** Die Entwickler haben die Punkte 1–4 am 14.11. behoben. Maßgeblich ist
  jetzt `4a4b33e4334e4d19f75640d1687034466a0f1b44` (Version 0.0.125). Der Diff gegenüber
  `cdedeba` betrifft nur planare Karten (Nachbarschaft, Ecke der U-Matrix), die Kennzeichnung
  `is_toroid`, den `.wts`-Leser und die Lizenzangabe. Der toroidale Trainingsweg und die
  C-Bibliothek sind unverändert. Weil noch kein Lauf stattgefunden hat, gilt das nicht als
  Wechsel nach Abschnitt 2.
- **Seed:** `np.random.seed(...)` ist laut Entwicklern der vorgesehene Weg und auf derselben
  Plattform wiederholbar. R0 prüft das trotzdem.
- **R1:** Die Entwickler verweisen für Parameterempfehlungen auf den Urheber des Verfahrens. Es bleibt bei
  den Standardwerten aus 7a. Kommt eine Empfehlung vor dem Start von R1, wird sie hier
  eingetragen und als **R1b** zusätzlich gerechnet. R1 mit Standardwerten bleibt bestehen.
- **Veröffentlichung:** Die Entwickler sind einverstanden, dass wir RefESOM nennen und Bilder und
  Werte vor der Veröffentlichung der Bibliothek zeigen. Die Einschränkung aus Abschnitt 2 und
  Abschnitt 7 entfällt damit für Ergebnisse. Für den Code gilt sie weiter, bis er veröffentlicht
  ist.
- **Inseln:** Auch die Entwickler halten die automatische Inselbestimmung für offen und
  arbeiten oft manuell in der Desktop-Anwendung der Entwickler. Maßgeblich für die Nachrechnung bleibt unsere Regel v2.
  Ein Austausch dazu ist ausdrücklich erwünscht, gehört aber nicht zu diesem Schritt.

## 7c. Nachtrag während R0 (15.11.2026, vor jeder Rechnung auf Chainlink oder unseren Daten)

- **Umgebung:** Python **3.13.17** (über uv), RefESOM-Abhängigkeiten genau nach
  `RefESOM/requirements.txt` (u. a. numpy 2.3.5, scikit-learn 1.8.0), vollständige Liste in
  `openmyconet_extern/RefESOM_umgebung.txt`. Unter Python 3.14 lässt sich RefESOM nicht importieren
  (`from _ctypes import POINTER` gibt es dort nicht mehr). RefESOM wird dafür **nicht** verändert;
  Hinweis an die Entwickler.
- **RefESOM-eigene Tests:** 79 von 84 bestanden (mit `MPLBACKEND=Agg`), darunter alle 15
  Trainingstests. Die 5 übrigen vergleichen erzeugte PNG-Bilder Byte für Byte mit
  Referenzbildern (politische Karte, Delaunay/Gabriel-Darstellung). Sie betreffen nur die
  Darstellung, nicht Training, Gewinnerneuronen oder U-Matrix-Werte. Ohne `Agg` scheitert
  zusätzlich ein Test an der fehlenden Tk-Grafikausgabe der uv-Python-Installation.
- **R0b, Kartengröße:** Chainlink hat nur 1 000 Punkte. Regel v2 setzt deutlich mehr Punkte als
  Neuronen voraus (in Phase A ≈ 15 je Neuron); auf einer 50 × 80-Karte zerfiele fast alles in
  Mauern. Maßgeblich für V0 ist deshalb eine **toroidale Karte 10 × 15** (150 Neuronen, ≈ 6,7
  Punkte je Neuron), 40 Epochen:
  - `karte-v1` mit ihren Standardwerten (σ 3,75 → 0,75 geometrisch, Seeds 0–9);
  - RefESOM mit derselben Zuordnung wie R2 (r = 2σ − 1): `start_radius=6.5, end_radius=1`,
    linear, Lernrate Standard, `np.random.seed(s)` mit s = 0–9.
  Chainlink wird so verwendet, wie es in der `.lrn` steht (keine Normierung). Gruppen nach
  Regel v2 mit unseren Standardwerten.
- **Nur berichtet (keine Entscheidung):** RefESOM mit den Standardwerten 50 × 80 / 24 Epochen auf
  Chainlink, ausgewertet (a) mit Regel v2 und (b) mit einem von der Gruppenregel unabhängigen
  Maß: Anteil der Punkte, deren Gewinnerneuron nur Punkte derselben Klasse trägt.
- **Determinismus:** RefESOM zweimal mit Seed 0 auf Chainlink (10 × 15); identisch heißt gleiche
  Gewichte (nach RefESOMs Rundung auf 4 Stellen) und gleiche Gewinnerneuronen.
- **Laufzeit:** eine einzelne Epoche mit R1-Parametern auf P + L und eine mit R2-Parametern;
  die Gewichte werden verworfen und nicht ausgewertet. Hochgerechnet auf alle Epochen
  entscheidet das über den Umfang von R3 (Abschnitt 5).

## 7d. Ergebnis R0 und Folgen für R1–R3 (15.11.2026, vor R1)

Werte: `ergebnisse/nachrechnung/r0.json`, Skript `werkzeuge/nachrechnung_r0.py`.

- **Technik:** RefESOM `4a4b33e`, Python 3.13.17, C-Bibliothek geladen. Zweimal Seed 0 ergibt
  identische Gewichte und Gewinnerneuronen. Unser Code berechnet aus den RefESOM-Gewichten in
  allen Läufen genau dieselben Gewinnerneuronen wie RefESOM (Anteil 1,0), die Übergabe stimmt also.
- **V0 (Chainlink, 10 × 15 toroidal): übereinstimmend.** `karte-v1` und RefESOM trennen die beiden
  Ringe in allen 10 Seeds fehlerfrei (ARI 1,0, je genau 2 Gruppen). Quantisierungsfehler
  `karte-v1` 0,073–0,076, RefESOM 0,064–0,067; Topologiefehler 0,06–0,18 bzw. 0,02–0,14.
- **Nur berichtet, 50 × 80 auf Chainlink:** Jedes Gewinnerneuron trägt nur Punkte eines Rings
  (Reinheit 1,0): Die Karte trennt richtig. **Unsere Gruppenregel v2 zerlegt sie aber in 51–60
  Komponenten (ARI 0,04).** Bei 1 000 Punkten auf 4 000 Neuronen sind fast alle Neuronen leer
  und damit Mauer. Das bestätigt die in Abschnitt 4 von `KRITERIEN.md` genannte Voraussetzung
  von Regel v2 (deutlich mehr Punkte als Neuronen) und ist ein Ergebnis über **unsere
  Gruppenregel**, nicht über RefESOM.
- **Folge für R1 (vor R1 festgehalten):** R1 hat 50 × 80 = 4 000 Neuronen, also rund 9 Fenster je
  Neuron statt rund 15 in Phase A und R2. Ein in R1 „nicht reproduzierter“ Kandidat kann deshalb
  an der Gruppenregel liegen statt am Training. R1 wird deshalb zusätzlich mit der Reinheit
  ausgewertet: Anteil der Kandidatenfenster, deren Gewinnerneuron überwiegend
  (≥ 50 %) Kandidatenfenster trägt (nur berichtet). Das Gesamturteil stützt sich ohnehin auf R2
  (Abschnitt 6), daran ändert sich nichts.
- **Laufzeit:** eine Epoche auf P + L 89,5 s (R1) bzw. 63,3 s (R2), hochgerechnet ≈ 36 bzw.
  ≈ 42 min je Lauf (Obergrenze, gemessen mit größtem Radius). Damit greift die Regel aus
  Abschnitt 5: **R3 = N1 Seeds 0–24 und N2 Seeds 0–24.** Die Läufe sind unabhängig und werden
  zu viert parallel gerechnet (4 Prozessorkerne); jeder Lauf bleibt durch seinen Seed
  festgelegt. Geschätzt: R1 + R2 (40 Läufe) ≈ 7 h, R3 (100 Läufe) ≈ 18 h.
- **Hinweise an die Entwickler:** Python 3.14 (Import `_ctypes.POINTER`); fünf Bildvergleichs-
  Tests scheitern unter Windows; `cool_down_linear` teilt bei `epochs=1` durch 0.

## 7e. R4: Ursachentest Endradius (freigegeben von Robby am 17.11.2026, nach R3, vor jedem R4-Lauf)

**Anlass:** Die Abweichung in R2 (Bericht, Abschnitt 5). RefESOM endet bei σ = 1,0, `karte-v1`
bei σ = 0,75. R4 prüft von unserer Seite, ob allein dieser Unterschied die Abweichung erklärt.
Beschlossen von Robby am 16.11.2026.

**Lauf:** `karte-v1` unverändert (Batch-SOM, Initialisierung aus Datenpunkten, 40 × 60
toroidal, 40 Epochen, geometrische Abkühlung ab max(2, 60/4) = 15), **nur `sigma_ende = 1,0`**
statt 0,75. Seeds 0–9, Sätze P und PL, dieselben Merkmale wie A4. Kein RefESOM. Gruppen, Maße und
Wiederfinden wie in V3 (Jaccard ≥ 0,5 mit den A4-Kandidaten der Seed-0-Karte).

**Geprüfte Kandidaten:** die 7 in A4 stabilen Kandidaten, die in R2 **nicht** reproduziert
wurden: P K3, P K10, PL K1, PL K13 (Reaktion), PL K28, PL K37, PL K46. Ein Kandidat gilt in R4 als
**verloren**, wenn er in weniger als 8 von 10 Läufen wiedergefunden wird. Das ist dieselbe Grenze
wie bei „reproduziert“ in V3.

**Entscheidung (vorab):**
- **≥ 5 der 7 verloren:** Der Endradius erklärt die Abweichung **überwiegend**.
- **3–4 verloren:** Der Endradius erklärt sie **teilweise**.
- **≤ 2 verloren:** Der Endradius erklärt sie **nicht**. Die Ursache liegt dann eher im
  Training (online statt Batch, Initialisierung, Lernrate) und bleibt offen.

**Gegenprobe:** Die 4 in R2 reproduzierten Kandidaten (P K16, P K13, PL K52, PL K2) sollten auch
in R4 reproduziert sein. Fehlt einer, wird das berichtet, und das Urteil gilt nur unter Vorbehalt.

**Nur berichtet:** QE, TE, Zahl der Gruppen und Inseln. Dazu für die verlorenen Kandidaten, ob
sie mit denselben Partnern verschmelzen wie in RefESOM (`ursache_r2.json`).

**Was R4 nicht entscheidet:** welcher Endradius „richtig“ ist, und auch nichts an Phase A.
Abschnitt 8 gilt unverändert.

## 7f. R5: RefESOM mit angeglichener Nachbarschaft (freigegeben von Robby am 22.11.2026, vor jedem R5-Lauf)

**Anlass:** Antwort der Entwickler (erhalten 22.11.2026) auf den Bericht R0–R4. Sie
haben RefESOM erweitert: Radius als Gleitkommazahl (auch unter 1), exakter Radius statt abgerundet,
Seed-Parameter, Nachbarschaftsgrenze an die Kernelbreite gekoppelt (3σ), exponentielle Abkühlung
von σ. Mit ihrem Parametervorschlag stimmen σ-Verlauf und Kernform mit `karte-v1` überein. R5
prüft, ob die Abweichung aus R2 dann verschwindet. Es bleiben Online- statt Batch-Training,
Lernrate und Startwerte, und R5 kann diese drei **nicht** voneinander trennen.

**Version (Abschnitt 2: neuer, gekennzeichneter Lauf):** Zweig `features-next-release`, Commit
`e6a483eeffdaf06e849a0f04664e129833b277d9`, als eigener Arbeitsordner
`openmyconet_extern/refesom_next` (git worktree). Der Klon mit `4a4b33e` bleibt unverändert; R1–R4
gelten nur für `4a4b33e`. Der Diff gegenüber `4a4b33e` betrifft nur `RefESOM/umatrix/training.py`
und die Tests; die C-Bibliothek ist unverändert und bekommt den Radius als Gleitkommazahl.
Gleiche Umgebung `venv_refesom` (Python 3.13.17). Weil dort `4a4b33e` als bearbeitbare Installation
eingetragen ist, wird RefESOM über `PYTHONPATH` aus `refesom_next` geladen; jeder Lauf protokolliert
den tatsächlich geladenen Pfad und den Commit, und ein Lauf mit falschem Pfad ist ungültig.

**Gelesen vor der Festlegung (aus dem Code, nicht aus der Mail):**
- `EXPONENTIAL_SIGMA`: σ_e = σ_start · (σ_ende/σ_start)^(e/(E−1)) mit σ = (Radius + 1)/2. Mit
  Radius 29 → 0,5 ist das σ 15 → 0,75, also **genau** die Formel von `karte-v1`.
- `KERNEL_WIDTH`: angepasst werden alle Neuronen bis 3σ; der Gauß-Kernel selbst nutzt den exakten
  Radius. Bei σ ≥ 6,7 (3σ ≥ 20, halbe Kartenhöhe) ist das die ganze Karte. `karte-v1` schneidet
  gar nicht ab; der Unterschied liegt unter 1,1 % des Kernels.
- `seed`: eigener Zufallsgenerator (`default_rng(seed)`) für Startwerte und Reihenfolge; ersetzt
  das bisherige `np.random.seed`.
- Unverändert: Lernrate linear 0,5 → 0,1, Startwerte gleichverteilt zwischen Min. und Max.,
  Rundung auf 4 Stellen.

**R5-0 Technik (vor R5, auf Chainlink, Minuten):**
1. RefESOM-eigene Trainingstests des neuen Zweigs laufen durch.
2. Zweimal `seed=0` ergibt identische Gewichte und Gewinnerneuronen; unser Code findet aus den
   Gewichten dieselben Gewinnerneuronen (Anteil 1,0).
3. Der protokollierte Radius je Epoche, umgerechnet in σ, stimmt mit dem σ-Verlauf von `karte-v1`
   überein (größte Abweichung < 10⁻⁹).
4. Nur berichtet: V0 auf Chainlink 10 × 15 mit der Zuordnung aus 7c und den neuen Optionen
   (`start_radius=6.5, end_radius=0.5`, `EXPONENTIAL_SIGMA`, `KERNEL_WIDTH`). Trennt RefESOM die
   Ringe dann nicht mehr (ARI < 0,9), wird **vor R5 angehalten** und mit den Entwicklern geklärt.

Scheitert 1–3, wird R5 nicht gerechnet und die Ursache zuerst geklärt.

**Lauf R5:** genau der Vorschlag der Entwickler,
`EsomTrainingParams.build(rows=40, cols=60, epochs=40, start_radius=29, end_radius=0.5,
neighborhood_cooling=CoolingMethod.EXPONENTIAL_SIGMA, neighborhood_cutoff=NeighborhoodCutoff.KERNEL_WIDTH,
seed=s)`, alle übrigen Werte Standard (toroidal, Lernrate, Startwerte, Rundung). Seeds s = 0–9,
Sätze P und PL, dieselben Merkmale wie A4 (sha256 je Lauf). 20 Läufe, zu viert parallel,
geschätzt 2–4 h. Auswertung genau wie R2 (Abschnitt 4, V1–V3): Gruppen nach Regel v2 mit unserem
Code, Wiederfinden mit Jaccard ≥ 0,5 gegen die A4-Seed-0-Karte.

**Entscheidung (vorab).** Gezählt werden die 11 in A4 stabilen Kandidaten (8b.1), wie in V3 für R2:
- **Nachbarschaft erklärt die Abweichung weitgehend:** V2 reproduziert (beide Sättigungen und die
  Reaktion in ≥ 8 von 10 Läufen) **und** mindestens 8 der 11 stabilen Kandidaten reproduziert
  (zwei Drittel, wie im Gesamturteil).
- **teilweise:** nicht der erste Fall, aber mindestens 6 der 11 reproduziert (R2: 4).
- **nicht:** höchstens 5 der 11 reproduziert. Die Ursache liegt dann im Training selbst (online
  statt Batch, Lernrate, Startwerte) und bleibt in diesem Rahmen offen.

**Gegenprobe:** Die 4 in R2 reproduzierten Kandidaten (P K16, P K13, PL K52, PL K2) sollten
reproduziert bleiben. Fehlt einer, wird das berichtet, und das Urteil gilt nur unter Vorbehalt.

**Nur berichtet:** QE, TE, Zahl der Gruppen und Inseln (neben A4, R2, R4); neue Komponenten in
≥ 5 Läufen; für nicht reproduzierte Kandidaten die Verschmelzungspartner wie in `ursache_r2.json`;
Laufzeit.

**Was R5 nicht entscheidet:**
- Das Gesamturteil der Nachrechnung (Abschnitt 6) bleibt für `4a4b33e` „abweichend“. R5 ist eine
  neue Version; für sie gibt es keine Nullläufe und damit kein V4, also auch kein „bestätigt“.
  Nullläufe mit R5-Parametern (R6) nur nach neuer Absprache.
- Nichts an Phase A (Abschnitt 6, letzter Punkt, und Abschnitt 8 gelten unverändert). Fällt R5
  „besser“ aus, wird deshalb nicht diese Umsetzung gewählt.
- Ergebnisse dürfen gezeigt werden (7b), der RefESOM-Code bleibt außerhalb dieses Repositorys.

## 8. Was ausdrücklich nicht dazugehört

- Keine Änderung an Phase A, an den Kriterien v2/E1/E2 oder an Phase B.
- Keine neuen Merkmale, keine neuen Daten, keine Messdaten.
- Keine Desktop-Anwendung der Entwickler (geschlossene Software). Eine interaktive Erkundung ist ein eigener, späterer
  Schritt.
- Keine Änderung an Server, Datenbank, Pipeline, Schema oder Firmware.
