# Phase A, Schritte A1–A3: Ergebnisbericht

Stand 05.11.2026 · Kriterien v2 (`KRITERIEN.md`) · Merkmalssatz `mv1` · Karte `karte-v1`
Schnappschuss sha256 `e9e4b139…0fbd16` · Rohzahlen in `metriken.json`, Abbildungen in `abbildungen/`

> **SIMULATION.** Alle Aussagen betreffen das Rechenmodell des Sandbox-Generators (`sbx-gen-1.0`),
> nicht Biologie. Ein Vergleich mit den einfacheren Verfahren (A4) steht noch aus. Eine Aussage
> über einen **Mehrwert** der ESOM ist deshalb noch nicht möglich.

## Kurzfassung

- Die Werkzeugkette funktioniert vollständig, reproduzierbar und blind: 36 920 Fenster à 10 s,
  2 Merkmalssätze, 240 Karten, 104 Projektionsläufe, Laufzeit 35 min.
- **Die ESOM findet alle eingebauten Strukturen der Simulation ohne Etiketten:** Sättigung
  (saubere Insel, 10/10 Seeds), Spikes (eigene Gruppen) und mit Satz P + L die angenommene
  Reaktion nach der Stimulation (229 Fenster, 96,5 % davon „0–10 min danach“, 10/10 Seeds).
- **Sie zeigt auch etwas, das ich nicht vorhergesagt hatte:** eine kleine, stabile Insel aus
  Fenstern mit einem **Sprung** von 9–17 µV. Die Rohdaten zeigen die Ursache: Im Rechenmodell setzt
  die Reaktion am Ende der Stimulation schlagartig mit voller Höhe ein. Das ist eine Eigenschaft der
  Simulation, keine Entdeckung über Biologie, aber ein gutes Beispiel für „Unterschiede, nach denen
  niemand gesucht hat“.
- **Nullmodell N2** (eine Normalverteilung) ergibt in allen 80 Läufen genau eine Gruppe und keine
  Insel: Das Verfahren erfindet auf strukturlosen Daten keine Gruppen.
- **Nach den strengen Kriterien (8b) gilt bisher nur wenig als bestätigte Entdeckung**, weil das
  Nullmodell N1 selbst scharf abgegrenzte Inseln erzeugt (siehe Abschnitt 4). Das ist ein Ergebnis
  über die Kriterien, das wir besprechen sollten.
- **Die große Karte (ESOM) trennt sichtbar feiner als die kleine SOM**: Sättigung, Reaktion und
  Sprungfenster bekommen auf der ESOM eigene, saubere Bereiche, auf der kleinen Karte gehen sie in
  gemischten Bereichen auf.

## 1. Was gelaufen ist

| | |
|---|---|
| Fenster | 10 s (2 500 Samples), Schritt 5 s, nur in lückenlosen Segmenten: 36 920 (Satz P + L: 35 624, weil 120 s Vorlauf nötig) |
| Merkmale | Satz P: 14 pegelfreie Merkmale; Satz P + L: zusätzlich Mittel, Steigung, Abweichung vom Vorlauf |
| Karten | klein 6 × 8 und ESOM 40 × 60, jeweils planar und toroidal, Seeds 0–9, Batch-SOM, 40 Epochen |
| Daten | echt, Nullmodell N1 (Spalten vertauscht), Nullmodell N2 (eine Normalverteilung) |
| Projektion | ESOM toroidal: 4 Teile nach Rohdatenstunde × 10 Seeds, zusätzlich je Standort zurückgehalten × 3 Seeds; Normierung nur aus dem Training |

## 2. Vorhersagen im Abgleich

| | Vorhersage | Ergebnis |
|---|---|---|
| H1 | Ordnung nach Rauschstärke, fließend | **bestätigt.** Die Karte ordnet die Fenster nach Jahreszeit/Aktivität (Januar in der Mitte, Juli außen, `etikett_stichtag_*`), ohne Mauern. Darum zeigen die Gruppen keinen Zusammenhang mit Standort oder Jahreszeit (ARI ≈ 0): Ein Verlauf ist keine Gruppe. |
| H2 | Sättigung als Insel; Schwelle genauso gut | **bestätigt (Teil 1).** 23 Fenster, 100 % rein, Abgrenzung 14,7–19,6, in 10/10 Seeds, beide Topologien. AUC über U-Höhe 1,0. Teil 2 (Schwelle) prüft A4. |
| H3 | Spike-Fenster trennen sich ab | **bestätigt.** Zwei Gruppen mit je ≈ 1,6 % der Fenster (1–2 Ausschläge, Kurtosis 6–12). |
| H4 | Reaktion: mit P kaum, mit P + L gut | **bestätigt.** P: AUC 0,53. P + L: eigene Gruppe (229 Fenster, Abweichung vom Vorlauf +16 µV), AUC 0,80. Paarvergleich mit der Kontrollreihe: 0–10 min danach liegen 85–87 % der zeitgleichen Paare > 3 Neuronen auseinander, **vor** der Stimulation 0 % (dort sind die Signale identisch, eine gute Plausibilitätsprüfung). |
| H5 | Während der Stimulation nichts zu sehen | **widerlegt, aufgeklärt.** Fenster, die das Ende der Stimulation enthalten, zeigen einen Sprung von 9–17 µV und bilden eine stabile Insel (8–10 von 10 Seeds, planar und toroidal). Ursache im Modell: Die Reaktion beginnt mit voller Höhe (`Reaktion.wert`, Exponentialabfall ab Amplitude). Es ist kein Stimulationsartefakt, sondern ein Sprung zu Beginn der angenommenen Reaktion. |
| H6 | Neustart/Uhrensprung unsichtbar | **bestätigt.** Fenster mit `TIMING_UNCERTAIN` verteilen sich über die Karte. |
| H7 | Spektralmerkmale tragen wenig bei | **bestätigt.** Alle Bandanteile und die Flachheit liegen bei den Werten für weißes Rauschen. |
| H8 | Gruppen ohne Etikett: Verfahrensartefakte | **bestätigt, mit neuer Ursache.** Die ESOM bildet viele kleine, instabile Inseln (P + L: ≈ 45 je Lauf). Die Rohdaten zeigen: Spike-Fenster zerfallen nach der **Lage des Spikes im Fenster** (Anfang/Ende), weil Trendentfernung und Hann-Fenster lageabhängig sind. Diese Inseln sind kaum reproduzierbar (0–2 von 9 Seeds) und werden von den Kriterien korrekt aussortiert. |

## 3. Stabilität und Übertragbarkeit

- **Stabilität über Seeds:** paarweiser ARI 0,94–0,99 in allen Konfigurationen. Einschränkung:
  Die große Hauptgruppe (≈ 96 % der Fenster) dominiert den ARI. Für einzelne Gruppen zählt deshalb
  das Wiederfinden je Gruppe (Jaccard ≥ 0,5), siehe `metriken.json` → `gruppen_seed0`.
- **Projektionstest** (zurückgehaltene Rohdatenstunden bzw. ganzer Standort): Die Gruppen der
  zurückgehaltenen Fenster stimmen mit der Karte auf allen Daten überein (ARI median 0,95–0,97).
  Der Quantisierungsfehler steigt nur mäßig (Faktor 1,02–1,32). Die Struktur überträgt sich also
  auf ungesehene Stunden und Standorte.

## 4. Nullmodelle und Kriterium 8b

| Konfiguration | echt: Gruppen / Inseln | N1: Gruppen / Inseln | N2 | Abgrenzung 95. Perz. N1 |
|---|---|---|---|---|
| P, ESOM toroidal | 3–4 / 10–19 | 1–3 / 16–21 | 1 / 0 | 2,36 |
| P + L, ESOM toroidal | 2–4 / 37–50 | 1–2 / 8–15 | 1 / 0 | 2,75 |
| P, klein planar | 3 / 2–3 | 1–2 / 0 | 1 / 0 | 3,58 |

**Kandidaten nach 8b (stabil ≥ 8/10 Seeds):**

| Struktur | Etikett vorhanden? | Abgrenzung | über N1? | Bewertung |
|---|---|---|---|---|
| Sättigung (23 F.) | ja (`SATURATED`) | 14,7–19,6 | ja | Klassifikation (8a), A4 vergleicht |
| Spike-Gruppe (≈ 630 F.) | **nein** | 2,94 (torus), 3,34 (planar) | ja | **erfüllt 8b.1–2, 8b.3** (Spikes in den Rohdaten sichtbar, Regel: Ausschläge ≥ 1 und hohe Kurtosis), 8b.5 erfüllt; ob ein einfaches Verfahren sie ebenso zeigt, prüft A4 |
| Reaktion (229 F., nur P + L) | ja (Phase) | 2,21–2,42 | **knapp nein** (2,25–2,75) | Klassifikation (8a), A4 vergleicht |
| Sprung am Reaktionsbeginn (12–23 F.) | **nein** | 1,23–1,55 | **nein** | stabil, nachprüfbar, beide Topologien → **Kandidat**, nach 8b.2 nicht bestätigt |

**Beobachtung zu N1:** N1 vertauscht jede Merkmalsspalte für sich und behält dabei die extremen
Einzelwerte (z. B. Sättigung, Ausschlagzahl). Daraus entstehen eigene, scharf abgegrenzte Inseln,
und deren 95. Perzentil wird zur Schwelle. Damit ist N1 für kleine, echte Inseln eine sehr hohe
Hürde. Ich ändere das Kriterium nicht nachträglich. **Zur Besprechung:** Soll für Phase B
(vor deren Lauf festgelegt) die Abgrenzung mit Inseln **gleicher Größe** im Nullmodell verglichen
werden statt mit allen Inseln?

## 5. Kleine SOM gegenüber ESOM

- **Kleine SOM (48 Neuronen):** Sie findet die Hauptgruppe und die Spike-Gruppen. Die Sättigung
  steckt in einer gemischten Insel (2,7 % Sättigung) und ist nur über den Quantisierungsfehler
  erkennbar (AUC 1,0). Die Reaktion bekommt keinen eigenen Bereich (AUC 0,79 über den Fehler).
  Die Sprungfenster sind nicht zu sehen.
- **ESOM (2 400 Neuronen):** Sättigung, Reaktion und Sprungfenster bekommen jeweils eigene, reine
  und reproduzierbare Bereiche.
- **Folgerung:** Die Auflösung der großen Karte macht seltene und kleine Strukturen sichtbar. Ob
  das ein Vorteil gegenüber einfachen Verfahren ist, zeigt erst A4. Ein negatives Ergebnis der
  kleinen Karte wäre hier tatsächlich irreführend gewesen.

## 6. Gegenprobe mit MiniSom

MiniSom (planar 40 × 60, 738 400 Schritte): Quantisierungsfehler 1,78, Topologiefehler 0,012.
Eigene Batch-SOM: 1,23 bzw. 0,114. Der Unterschied kommt vom Nachbarschaftsradius am Ende: Bei
MiniSom endet er bei etwa 3,3 Neuronen, bei der eigenen Umsetzung bei 0,75. Die eigene Karte ist
damit feiner, aber weniger glatt (11 % Topologiefehler). **Für A4 schlage ich einen
Empfindlichkeitslauf mit Endradius 2 vor**, um zu sehen, ob die Kandidaten das überstehen.

## 7. Lehren für Phase B

1. **Lageunabhängige Merkmale:** Ein Ereignis darf seine Gruppe nicht dadurch wechseln, wo es im
   Fenster liegt (H8). Möglich wären verschiebungsfeste Merkmale oder ein Abgleich überlappender
   Fenster.
2. **Jedes Detail eines Testsignals braucht eine dokumentierte Wahrheit.** Der Sprung am
   Reaktionsbeginn stand in keiner Tabelle und war nicht als Eigenschaft gedacht. Genau solche
   Nebeneffekte findet die ESOM.
3. **Die Sandbox enthält keine** Netzeinstreuung (50 Hz), Kontaktstörungen, langsamen Rampen,
   Stimulationsartefakte und keine Überlagerungen. Das sind die Hauptkandidaten für Phase B.
4. Die Inselregel erhält seltene Ereignisse (23 Fenster = 0,06 %). Das ist für den Neuheitstest in
   Phase B wichtig.

## 8. Nächster Schritt (A4)

Vergleichsverfahren auf **denselben** Merkmalsmatrizen (`merkmale_*.npz`, Prüfsummen in
`metriken.json`): Hauptkomponenten, k-Means, Isolation Forest, robuste Mahalanobis-Distanz,
einfache Schwellen. Dazu die Entscheidungsregeln 8a/8b und der Empfindlichkeitslauf (Abschnitt 6).
