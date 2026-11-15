# Nachrechnung von Phase A mit pydbt: Zwischenbericht R0–R2

Stand 15.11.2026 · Regeln `NACHRECHNUNG_PYDBT.md` (Abschnitte 6, 7a–7d, alle vor dem jeweiligen
Lauf festgelegt) · pydbt `4a4b33e` (0.0.125), Python 3.13.17, C-Bibliothek geladen · Merkmale
`mv1` aus A3 (sha256 je Lauf in den Lauf-Metadaten) · 40 Läufe, alle ohne Fehler.
**R3 (Nullmodelle, V4) ist noch nicht gerechnet.**

> **SIMULATION.** Grundlage sind die Sandbox-Szenarien `sbx-gen-1.0`. Es sind keine Messwerte.
> Die Ergebnisse sagen etwas über die Verfahren, nie über Biologie.

Dateien: `r0.json`, `r1_r2.json` (V1–V3), `ursache_r2.json` (Ursachensuche). Die Gewichte der
Läufe (`laeufe/*.npz`) bleiben lokal.

## 1. Ergebnis in einem Satz

Nach den vorab festgelegten Regeln ist das Gesamturteil **abweichend**, und zwar schon vor R3:
In R2 ist die Reaktionsgruppe nur teilweise reproduziert (5/10), und von den 11 in A4 stabilen
Kandidaten sind nur 4 reproduziert (36 %, verlangt sind zwei Drittel). Die Abweichung betrifft
fast nur Spike-Gruppen, die schon in A4 als Lage-Fragmente eingestuft waren. pydbt fasst sie zu
größeren Gruppen zusammen. Die Ursache dafür ist offen (Abschnitt 5).

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

## 6. Was das für Phase A heißt (vorläufig)

- **Stabil über beide Umsetzungen:** Sättigung, Sprung am Reaktionsbeginn (PL K2) und Sprung in
  P (K13). Das sind die Strukturen, die in A4 auch einfachere Verfahren fanden.
- **Nicht übertragbar:** die feine Aufteilung der Spikes nach ihrer Lage im Fenster. Sie war
  schon in A4 als Schwäche des Merkmalssatzes eingestuft. Die Nachrechnung zeigt jetzt
  zusätzlich, dass sie von der ESOM-Umsetzung abhängt.
- **Reaktion:** Sie ist in pydbt als Fenstermenge vorhanden, aber nur in der Hälfte der Läufe
  durch eine Mauer abgegrenzt.
- Nach Abschnitt 6 wird **nicht** die Umsetzung gewählt, deren Ergebnis besser aussieht. Wie es
  weitergeht, entscheiden wir gemeinsam mit den Entwicklern.

## 7. Offen

- R3 (N1/N2 je Seeds 0–24 mit R2-Parametern, ≈ 15–18 h) und damit V4. Am Urteil „abweichend“
  ändert V4 nichts mehr. V4 zeigt aber, ob einer der Kandidaten oder eine neue Komponente unter
  pydbt die Schwellen bestehen würde.
- Rückfrage an die Entwickler: Lässt sich ein Endradius unter 1 (σ < 1) einstellen? Damit wäre
  ein gezielter Lauf zur Ursache möglich. Dieser Lauf wäre ein neuer Schritt und würde vorher
  festgelegt.
