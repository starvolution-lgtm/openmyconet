# Nachrechnung von Phase A mit einer Referenz-ESOM (pydbt): Vergleichsregeln

**Freigegeben am 14.11.2026 (Robby), vor jedem Lauf.** Offen bis vor R1 und nur an den
gekennzeichneten Stellen: pydbt-Commit, Parameterzuordnung R2, Umfang R3. Danach gelten nur
noch dokumentierte, begründete Ergänzungen, nie Änderungen nach Ansicht der Ergebnisse.

> **SIMULATION.** Grundlage sind dieselben Simulationsdaten wie in Phase A (Sandbox-Szenarien
> `sbx-gen-1.0`). Es sind keine Messwerte. Die Nachrechnung sagt etwas über die Verfahren und
> ihre Umsetzung, nie über Biologie.

## 1. Zweck und Abgrenzung

Phase A wurde mit einer eigenen Batch-SOM (`karte-v1`, `mm/karte.py`) gerechnet. Die
Nachrechnung prüft, ob die Ergebnisse an dieser eigenen Umsetzung hängen. Dafür wird die
ESOM-Bibliothek pydbt verwendet, die uns die Entwickler zur Verfügung gestellt haben.

Zwei Fragen:

1. **Umsetzung:** Verhält sich `karte-v1` auf einem Datensatz mit bekannter Lösung wie eine
   etablierte ESOM?
2. **Reproduzierbarkeit:** Finden sich die Strukturen und die Kernaussage von Phase A mit pydbt
   wieder?

**Phase A wird dadurch nicht neu bewertet.** Ihre Ergebnisstufen, Kriterien (v2, E1) und
Berichte bleiben unverändert. Abweichungen werden als Ergebnis der Nachrechnung berichtet und
untersucht, nicht in Phase A übertragen. Findet pydbt eine Struktur, die Phase A nicht hatte,
ist das eine **neue Hypothese** und kein Befund. Sie wird erst in einem eigenen, vorab
festgelegten Schritt geprüft, frühestens in Phase B.

## 2. Software und Umgebung

- pydbt wird aus dem privaten Repository in einen Ordner **außerhalb des Git** geklont.
  Fest gehalten wird ein Commit: der vollständige Commit-Hash steht vor dem ersten Lauf hier.
  Ein späterer Wechsel des Commits ist ein neuer, gekennzeichneter Lauf.
- Eigene Python-Umgebung nur für diese Nachrechnung (nicht `venv/` der Analyse, nicht der
  Server). pydbt kommt **nicht** in `requirements.txt` und nicht in die CI, solange es nicht
  veröffentlicht ist.
- Kein pydbt-Code wird in dieses (öffentliche) Repository kopiert. Ergebnisse aus pydbt
  (Zahlen, Bilder) werden erst nach Rücksprache mit den Entwicklern veröffentlicht.
- Protokolliert wird je Lauf: Commit, Python-Version, ob die C-Bibliothek geladen wurde
  („C library not found“ = reiner Python-Code), alle Parameter, Seed, Laufzeit.
- Finden wir einen Fehler in pydbt, melden wir ihn den Entwicklern. Ein eigener Patch wird nur
  mit Diff dokumentiert verwendet und der Lauf gekennzeichnet.

## 3. Daten

- **Dieselben normierten Merkmalsmatrizen wie in A3/A4:** `ergebnisse/a3/merkmale_P.npz` und
  `merkmale_PL.npz` (Schnappschuss `e9e4b139…0fbd16`, Merkmalssatz `mv1`, Normierung auf ±8).
  Sie werden unverändert als `.lrn` exportiert, der Schlüssel ist die Fensternummer.
  sha256 der `.npz` und der `.lrn` stehen im Ergebnis.
- **Nullmodelle:** N1 (Spalten vertauscht) und N2 (eine Normalverteilung) werden mit dem Code
  und den Seeds aus A4 erzeugt, also dieselben Matrizen wie dort, und ebenfalls als `.lrn`
  exportiert.
- **Referenzdatensatz mit bekannter Lösung:** `Chainlink.lrn` aus dem pydbt-Repository
  (zwei verschlungene Ringe, FCPS) mit der zugehörigen Klassendatei, falls vorhanden.

## 4. Gruppen und Maße: dieselbe Auswertung für beide Verfahren

Damit nur das **Training** verglichen wird, nicht die Auswertung, gilt:

- pydbt liefert Gewichte (`.wts`) und Gewinnerneuronen (`.bm`). Gruppen, Inseln und Abgrenzung
  werden daraus mit **unserer Gruppenregel v2** und unserem Code berechnet, Quantisierungs- und
  Topologiefehler ebenfalls mit unserem Code.
- Die U-Matrix, P-Matrix und U\*-Matrix von pydbt werden zusätzlich als Bilder gezeigt. Eine
  Inselbestimmung mit pydbt-eigenen Werkzeugen (z. B. `.imx`) wird nur ergänzend berichtet und
  geht in keine Entscheidung ein.
- **Wiedergefunden** heißt wie in E1 (9.1): Es gibt eine Komponente mit Jaccard ≥ 0,5 zu den
  Fenstern des Phase-A-Kandidaten (Seed 0 der Hauptkonfiguration von A4).

## 5. Läufe in fester Reihenfolge

| Schritt | Inhalt | Läufe |
|---|---|---|
| **R0** Technik | pydbt-eigene Tests laufen durch; das Chainlink-Beispiel aus der Anleitung läuft. Laufzeit eines Laufs auf P + L wird gemessen. | – |
| **R0b** Gegenprobe Umsetzung | `karte-v1` und pydbt auf Chainlink, je 10 Seeds, toroidal. | 2 × 10 |
| **R1** pydbt nach Empfehlung | Parameter **wie von den Entwicklern empfohlen**; liegt keine Empfehlung vor, die Werte aus ihrer Anleitung: 50 × 80, 24 Epochen, toroidal, sonst Standardwerte. Satz P und P + L. | 2 × 10 |
| **R2** pydbt angeglichen | 40 × 60, toroidal, 40 Epochen, Radius- und Lernratenverlauf so nah an `karte-v1` wie pydbt es erlaubt. Die Zuordnung der Parameter wird **nach dem Lesen des pydbt-Codes, aber vor R1** hier eingetragen. | 2 × 10 |
| **R3** Nullmodelle | pydbt mit R2-Parametern auf N1 (Seeds 0–99) und N2 (Seeds 0–24), je Satz. Ist ein Lauf in R0 länger als 3 min, werden es N1 0–24 und N2 0–24; diese Wahl wird nach R0 und vor R1 hier eingetragen. | bis 2 × 125 |

Hat pydbt keinen Seed-Parameter, werden die 10 Läufe als Wiederholungen gerechnet und das wird
vermerkt. Ist pydbt bei gleichem Seed nicht deterministisch, ebenfalls.

**R1 kommt vor R2**, damit wir pydbt nicht unbewusst auf unsere Ergebnisse hin einstellen.

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

**V4 Nullmodelle und Stufen (R3).** Mit den pydbt-Nullläufen werden die Schwellen nach E1
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
  pydbt-Bildern bleiben bis zur Rücksprache außerhalb des Git.
- Der Bericht nennt alle Läufe, auch fehlgeschlagene, und jede Abweichung von diesen Regeln.
- Eintrag in `VERLAUF.md`.

## 7a. Nachträge vor R1 (14.11.2026, nach Lesen des pydbt-Codes, vor jedem Lauf)

**pydbt-Commit:** `cdedeba40b323b98cc2e6c322b58c4f84ec081f4` (08.10.2026, Version 0.0.124),
geklont nach `Desktop/openmyconet_extern/pydbt` (außerhalb jedes Git-Repositorys von uns).

**Was pydbt anders macht als `karte-v1`** (aus `pydbt/umatrix/training.py`):

| | `karte-v1` (Phase A) | pydbt `esom_train` |
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
übrige Werte Standard. Begründung: pydbt-Radius r entspricht σ = (r + 1)/2; σ 15 (Startwert
`karte-v1`) ergibt r = 29. Das Ende lässt sich nicht angleichen: σ 0,75 hieße r = 0,5, und pydbt
würde dann nur noch das Gewinnerneuron selbst anpassen. Daher r = 1 (σ = 1, kleinster Wert mit
Nachbarschaft). Geometrische Abkühlung gibt es in pydbt nicht, daher linear. Diese Unterschiede
sind gewollt sichtbar: R2 prüft, ob Phase A vom genauen Trainingsverfahren abhängt, nicht, ob
pydbt `karte-v1` nachbaut.

**Auffälligkeiten im pydbt-Code** (nur berichtet, nichts verändert; an die Entwickler):

1. Planare Karte, U-Matrix: In `neighbors()` stehen für die Ecke unten rechts Spaltenindizes
   `rows-2`/`rows-1` statt `cols-2`/`cols-1`. Betrifft nur planare Karten; wir rechnen toroidal.
2. Planare Karte, Training: Nachbarn außerhalb der Karte werden auf den Rand geschoben (`clip`)
   statt weggelassen. Randneuronen werden dadurch je Schritt mehrfach angepasst. Nur planar.
3. `esom_train` schreibt `is_toroid=True` in die Gewichte- und Bestmatch-Daten, auch bei
   planarer Karte.
4. `pyproject.toml` nennt die MIT-Lizenz, die Datei `LICENSE` die MPL 2.0.

Da alle Läufe toroidal sind, betreffen 1–3 die Nachrechnung nicht.

## 8. Was ausdrücklich nicht dazugehört

- Keine Änderung an Phase A, an den Kriterien v2/E1/E2 oder an Phase B.
- Keine neuen Merkmale, keine neuen Daten, keine Messdaten.
- Kein UmatrixLab (geschlossene Software). Eine interaktive Erkundung ist ein eigener, späterer
  Schritt.
- Keine Änderung an Server, Datenbank, Pipeline, Schema oder Firmware.
