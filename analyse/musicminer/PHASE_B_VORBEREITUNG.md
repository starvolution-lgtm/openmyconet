# Phase B: Vorbereitung (Fassung 2, noch nicht gerechnet)

Stand 05.11.2026. Fassung 2 nach A4, der Abstimmung mit Robby und der Prüfung von Literatur und
Hardware (`PRUEFUNG_QUELLEN_HARDWARE.md`). Verbindliche Regeln: `KRITERIEN.md`, v2 + E1 + **E2**
(Abschnitt 10). Fassung 1 (nur 10-s-Fenster, nur ESOM gegen einfache Verfahren) ist in
`VERLAUF.md` als überholt beschrieben.

> SYNTHETISCH. Alle Testsignale in Phase B dienen ausschließlich der technischen und
> methodischen Prüfung. Sie werden nur als Dateien erzeugt, nie in eine BioComm-Datenbank
> geschrieben, nie mit Messdaten vermischt und nie als biologische Trainingsgrundlage verwendet.
> Parameter sind **literaturgestützt, aber nicht hardware-validiert**. Sie werden ersetzt, sobald
> Referenzmessungen an der BioComm-Hardware vorliegen.

## 1. Ziel

Die am besten geeignete **Kombination von Verfahren** für die explorative Analyse bioelektrischer
Signale finden, unabhängig davon, ob die ESOM darin eine zentrale, ergänzende oder gar keine
Rolle spielt. Der MusicMiner-Gedanke wird dabei nicht auf das automatische Erkennen einzelner
Cluster reduziert: Die **Kartenansicht für Menschen** (B8) und die **feste Referenzkarte** für
den Dauerbetrieb (B7) werden eigens geprüft.

## 2. Testsignale

### 2.1 Bausteine (je Baustein eine Wahrheitsmarkierung je Sample)

| Baustein | Parameter (vorläufig) | Herkunft |
|---|---|---|
| Hintergrundrauschen | weiß + 1/f, σ 2–25 µV | Annahme (Elektronik laut Datenblatt viel leiser, Elektrode unbekannt) |
| Grundliniendrift | Wellen 1–12 h, 0,1–1 mV | Literatur (Adamatzky & Gandia 2022: Median 8,3 h, 0,45 mV) |
| Langsame Rhythmen | 30 min, 24 h | Literatur (Zusammenfassung Fukasawa et al. 2024) |
| Pilzähnliche Spikes | Dauer 30 s – 20 min (einzelne bis 2 h), 0,03–2 mV, Abstand 3–40 min, in Zügen von 2–8 Spikes, Zugdauer 20–120 min | Literatur (Adamatzky 2018, 2022; Adamatzky & Gandia 2022) |
| Schnelle Spikes | 20–300 µV, Abklingen 10–200 ms | **Methodentest**, ausdrücklich nicht pilztypisch |
| Schwingungen im Hertz-Bereich | 1,5–8 Hz, Amplitude und Dauer als Parameterreihe | Literatur (Buffi et al. 2025, iScience) |
| Sprünge / Niveauwechsel | 5 µV – 1 mV, Anstiegszeit 0 / 1 / 10 / 60 s | Methodentest; B5 |
| Netzeinstreuung | 50 Hz ± 0,2 Hz + Oberwellen, 1 µV bis Sättigung | Annahme; Faltung siehe 2.3 |
| Kontaktstörung | Grundliniensprünge, mehr Rauschen, Wandern unter 1 Hz, austrocknender Kontakt (Rauschen steigt über Stunden) | Annahme |
| Sättigung | an der Grenze des jeweiligen Hardware-Modells | Hardware-Modell |

### 2.2 Stimulationsartefakte (erst getrennt, dann kombiniert)

| Artefakt | Modell |
|---|---|
| elektrisch, Einkopplung | Pulsform des Reizes, Klemmung über die Eingangsdioden bis zur Sättigung, exponentielle Erholung 0,1–10 s |
| elektrisch, **Polarisation** | langsames Abklingen über 1–30 min nach dem Reiz. **Wichtigster Verwechslungskandidat**, weil es zeitlich wie eine Reaktion aussieht. |
| optisch, LED | kleiner Sprung bzw. Spitzen beim Ein- und Ausschalten; **PWM-Frequenz** gefaltet ins Messband |
| Vibration | Schwingung mit der Anregungsfrequenz, abklingendes Nachschwingen |
| **Umschaltung Bio/EC** | Einschwingen 100–150 ms nach jedem Umschalten des gemeinsamen ADC-Kanals (laut Konstruktionsnotiz) |
| **Funk (ESP32/LoRa)** | Störimpulse im Sendetakt |
| Hantieren / Temperatur | mechanische Störungen; Drift beim Öffnen der Box |

**Verwechslungstest (Teil von B1):** jeweils nur Artefakt, nur synthetische Reaktion, beides
zusammen. Gemessen wird, wie oft ein Verfahren ein Artefakt für eine Reaktion hält.

### 2.3 Hardware-Modelle (dieselben Signale durch beide)

- **H-ideal:** zweiseitig ±2,53 mV am Eingang (G = 101, ±0,256 V), wie in der Sandbox angenommen.
- **H-Rev3.6:** so, wie die Konstruktionsunterlagen der Finalfassung von Revision 3.6 (25.10.2026) die Schaltung zeigen (zur
  Bestätigung durch Richard). Variante a, wie gezeichnet: etwa ±16 mV am Eingang (G = 101, ADC einpolig ±4,096 V),
  Auflösung 1,24 µV, ADC-Rauschen ≈ 1,2 µV am Eingang, Elektroden-Gleichanteil (Parameterreihe
  0 bis ±100 mV, Einschätzung; bei Übersteuerung Verstärkung 11 als Variante), kein Anti-Aliasing, Drift der Analogversorgung (halb, 1 : 1 im Messwert),
  Verschiebung der Mittenspannung durch Stimulationsströme, Einschwingen der Eingänge.
  Variante b, nach der am 05.11. erbetenen Änderung: differenziell gegen VMID (keine
  Versorgungsdrift), Anti-Aliasing-RC bei ≈ 720 Hz, Messbereich ±2,5 / ±10 / ±20 mV.
- Faltung über ein **angenommenes** sinc-Filter bei 250 SPS, bis der Filterverlauf gemessen
  ist. 16-Bit-Quantisierung, Datenrate mit Abweichung bis ±10 %, Lücken und Zeitunsicherheit wie
  im Datenformat (`TIMING_UNCERTAIN`).

### 2.4 Aufbau der Datensätze

- Viele unabhängig erzeugte Reihen, jede mit eigenem Seed. Jede bekannte Struktur kommt in ≥ 4
  Reihen vor (E2 10.2). Keine identischen Rohfenster zwischen Reihen (Prüfsumme).
- Laufzeit je Reihe so lang, dass die langen Skalen tragen: ≥ 48 h für Drift- und
  Spike-Züge, gemittelt auf 1 Wert/s; dazu kurze Abschnitte mit voller Rate (250 Hz) für die
  schnelle Skala.

## 3. Merkmale `mv2` (vor B2 eingefroren)

- **Drei Zeitskalen:** 10 s (volle Rate), 2 min und 20 min (aus der 1-Hz-Mittelung).
- **Form-Merkmale** (lageneutral): robuste Trendentfernung (gleitender Median), Spektrum nach
  Welch über Teilfenster, Ereignismerkmale aus einer Spitzenerkennung (Zahl, Höhe, Breite,
  Vorzeichen), unabhängig von der Lage im Fenster.
- **Niveau- und Langsam-Merkmale** getrennt davon: Mittel, Steigung und Abweichung vom Vorlauf
  auf jeder Skala. Damit entfernt die Trendentfernung der Form-Merkmale keine langsamen
  Strukturen, denn diese stecken in eigenen Merkmalen.
- `mv1` läuft in B6 zum Vergleich mit.

## 4. Verfahren

| Verfahren | Rolle |
|---|---|
| ESOM, eigene Umsetzung (`karte-v1`) | wie in Phase A |
| **ESOM, Referenzumsetzung**: R-Paket `Umatrix` (`esomTrain`, U-/P-/U*-Matrix; Lerch, Thrun, Ultsch, Lötsch) | originalgetreuere Umsetzung; Gruppierung wie dort vorgesehen |
| UMAP + HDBSCAN, Ansicht mit **generalisierter U-Matrix** (R-Paket `GeneralizedUmatrix`, Thrun & Ultsch 2020) | heutiger Standard für explorative Gruppensuche; faire Vergleichsansicht |
| HDBSCAN auf den Merkmalen | in A4 das stärkste einfache Verfahren |
| **Matrix-Profile** (Python, `stumpy`) | Motive und Abweichungen **direkt im Rohsignal**, ohne Merkmale und ohne Lageproblem |
| **Change-Point-Erkennung** (Python, `ruptures`) | Sprünge, Niveauwechsel, Drift-Brüche |
| Isolation Forest, robuste Mahalanobis-Distanz | Ausreißer |
| Wissensbasierte Schwellen | nur zur Einordnung (8a), nie für die Entdeckung |

Weggelassen: k-Means mit einem k, das von der ESOM übernommen wird (Begründung in `VERLAUF.md`).

Neue Abhängigkeiten (`umap-learn`, `stumpy`, `ruptures`; R mit `Umatrix`, `GeneralizedUmatrix`)
kommen gepinnt und mit Prüfsummen in die Analyse-Umgebung, getrennt vom Server.

### 4.1 Ergänzende Darstellungen (Vorschlag, R-Paket `DataVisualizations`)

Vorschlag vom 12.11.2026, noch nicht beschlossen. Das R-Paket `DataVisualizations` (Thrun;
<https://github.com/Mthrun/DataVisualizations>, auf CRAN; MD-Plot nach Thrun, Gehlert & Ultsch
2020, PLoS ONE, doi:10.1371/journal.pone.0238835) stammt aus demselben Umfeld wie
`Umatrix` und `GeneralizedUmatrix`. Es enthält Darstellungen für die explorative Analyse, die
die bestehenden Auswertungen ergänzen. Die Darstellungen sind **reine Ansichten**: Sie ändern
weder Merkmale noch Training noch Bewertungskriterien und dienen nur der Auswertung.

| Funktion | Einsatz bei uns | Bezug |
|---|---|---|
| `MDplot` (Verteilungen per Pareto-Dichteschätzung, PDE) | Alle Merkmale von `mv1`/`mv2` vor und nach der Transformation zeigen. Prüfen, ob die `log1p`-Auswahl (`streuung`, `ausschlaege`, `max_ausschlag`) und die Begrenzung auf ± 8 passen, und wo Merkmale mehrgipflig sind (Hinweis auf Gruppenstruktur schon vor jeder Karte) | Abschnitt 3, vor dem Einfrieren von `mv2` |
| `InspectVariable` | Einzelmerkmal genauer ansehen (Histogramm, PDE, QQ-Plot, Boxplot), wenn der MD-Plot etwas Auffälliges zeigt | Abschnitt 3 |
| `Heatmap` (Distanzmatrix, nach Gruppen sortiert), `Silhouetteplot` | Gruppen je Verfahren (ESOM, UMAP + HDBSCAN, HDBSCAN) sichtbar machen: Sind sie kompakt und nach außen abgegrenzt? Visuelles Gegenstück zur Abgrenzung A | B1, B2, B4 |
| `DensityScatter` | 2D-Ansichten (PCA, UMAP) als Dichte statt Einzelpunkte, damit kleine Inseln (z. B. ≈ 23 Sättigungsfenster) bei Tausenden Fenstern sichtbar bleiben | wie `pca_kandidaten_*.png` in A4 |
| `Pixelmatrix` | Gesamtbild der Merkmalsmatrix (Fenster × Merkmale): auffällige Blöcke, konstante Spalten | B0, Plausibilitätsprüfung |
| Shepard-Dichteplot | Wie gut erhält eine Projektion (ESOM, UMAP) die Abstände der Merkmale? Ergänzt Quantisierungs- und Topologiefehler | B8, Vergleich der Ansichten |

Bedingungen:

- **Verblindung bleibt unberührt.** Ansichten mit Etiketten (Szenario, Wahrheitsmarkierung)
  entstehen in B2 erst nach der Entblindung. Die Beurteilenden in B8 bekommen nur die dort
  festgelegten Ansichten zu sehen, keine dieser Darstellungen.
- **Übergabe Python → R** über exportierte Dateien (Merkmale, Gruppenzuordnung, Fensterkennung;
  z. B. CSV aus den `.npz`). Jede Abbildung nennt wie bisher Schnappschuss bzw. Datensatz,
  Merkmalssatz-Version und Seed.
- Das Paket kommt gepinnt in die R-Umgebung (zusammen mit `Umatrix`, `GeneralizedUmatrix`; siehe
  Abschnitt 7, Punkt 3). Stand CRAN: **Version 1.4.0**, veröffentlicht 31.10.2025, braucht
  R ≥ 3.5. Direkte Abhängigkeiten: `Rcpp`, `RcppParallel`, `ggplot2`, `sp`, `pracma`, `reshape2`.
  Das Paket wird kompiliert (C++17); für Windows gibt es fertige Binärpakete, ohne sie braucht es
  Rtools. Einige Funktionen nutzen zusätzlich optionale Pakete (Suggests), welche genau, zeigt
  erst die Einrichtung.
- **Lizenz: GPL-3** (Angabe Robby, 12.11.2026). Für die Nutzung in der Analyse ist das
  unproblematisch, der Ordner wird nicht deployt. Code aus dem Paket wird nicht in dieses Repo
  kopiert; sonst stünde dieser Teil unter GPL-3.

### 4.2 Weitere R-Pakete aus demselben Umfeld (Vorschlag)

Vorschlag vom 12.11.2026, noch nicht beschlossen. Quelle: Paketübersicht
<https://www.deepbionics.de/rpackages.html> (Thrun), durchgesehen am 12.11.2026. Die drei Pakete
stehen unter **GPL-3**, auf CRAN und GitHub. Für sie gelten dieselben Bedingungen wie in 4.1:
gepinnt, Übergabe per Datei, kein Code im Repo.

| Paket | Einsatz bei uns | Bezug |
|---|---|---|
| **`DRquality`** (Gütemaße für Projektionen) | Misst, wie gut eine 2D-Projektion die Nachbarschaften und Abstände der Merkmale erhält, gleich für ESOM und UMAP. Liefert eine **zahlenmäßige** Ergänzung zum Urteil der Beurteilenden; bisher gibt es nur Quantisierungs- und Topologiefehler, und nur für die ESOM | B8 (ergänzend, ändert E2 10.6 nicht) |
| **`FCPS`** (Fundamental Clustering Problems Suite) | Testdatensätze mit bekannter Gruppenstruktur und eine einheitliche Schnittstelle zu vielen Clusterverfahren. **Vorprüfung:** eigene ESOM (`karte-v1`) und Gruppenregel v2 auf diesen Datensätzen laufen lassen, bevor sie auf die B-Signale angewandt werden. Erweitert die Prüfungen in `tests/test_karte.py` (eine Normalverteilung → eine Gruppe; Insel aus 12 Ausreißern) | vor B1, unabhängig vom Generator |
| `AdaptGauss` (Gauß-Mischmodelle in 1D), **Option** | Schwellen aus der Verteilung herleiten statt von Hand setzen, z. B. für die wissensbasierten Schwellen (8a) oder die Spike-Erkennung. Nur zur Einordnung, nie für die Entdeckung (wie in Abschnitt 4) | B1 |

Geprüft und **nicht vorgesehen**: `DatabionicSwarm` (weiteres Projektions- und Clusterverfahren;
A4 zeigt, dass einfache Verfahren genügen), `ABCanalysis` (Merkmalsbedeutung; der
Entscheidungsbaum für F1 deckt das ab), `ProjectionBasedClustering` (überschneidet sich mit
`GeneralizedUmatrix`), `RHmm` (seit 2014 nicht mehr auf CRAN). `TSAT`, `Classifiers` und
`dbt.DataIO` stehen unter **CC BY-NC** bzw. **CC BY-NC-SA** (nur nicht-kommerziell) und werden
nicht verwendet, solange nicht geklärt ist, ob das für BioComm passt.

## 5. Versuche und Reihenfolge

| Schritt | Frage | Bemerkung |
|---|---|---|
| **B0** | Erzeugt der Generator, was die Wahrheit behauptet? (Spektren, Amplituden, Faltung, Hardware-Modelle) | nur Tests, keine Analyse |
| **B6** | Verschiebungstest `mv1` gegen `mv2`: dasselbe Ereignis an 20 Lagen im Fenster. **Erhaltungstest:** Bleiben langsame Schwingungen, Rampen und Sprünge unterscheidbar? | danach `mv2` einfrieren |
| **B1** | Unterscheidung bekannter Artefakte (8a), getrennt und kombiniert, mit Verwechslungstest | |
| **B3** | Störgrad-Reihe: ab welchem Signal-Rausch-Verhältnis ist eine schwache Struktur nicht mehr unterscheidbar? Kurve je Verfahren | Bedingung 2 in E2 10.4 |
| **B5** | Anstiegszeit einer Reaktion (0 / 1 / 10 / 60 s) und kleiner werdende Höhe | Ursache der Sprung-Insel aus A3/A4 |
| **B4** | Überlagerungen aus 2–3 Bausteinen | |
| **B2** | **Hauptendpunkt:** neue Formen, einzeln zurückgehalten, selten (0,2 %) und wiederkehrend (3 %), mit Negativkontrolle, verblindet nach E2 10.5 | zuletzt, mit eingefrorenem Code |
| **B7** | Langzeitstabilität einer festen Referenzkarte (E2 10.7) | eigener Versuch |
| **B8** | Verblindeter Ansichtstest U-Matrix gegen UMAP (E2 10.6) | ≥ 3 Personen, sonst explorativ |

Jeder Versuch läuft mit beiden Hardware-Modellen. Maßgeblich für den Hauptendpunkt ist
H-ideal; H-Rev3.6 zeigt, was die Schaltung in ihrer gezeichneten Form kosten würde.

## 6. Katalog möglicher neuer Formen für B2 (Entwurf, ≥ 16, Auswahl durch Robby)

Wird vor dem Einfrieren von `mv2` als eigene Datei mit Parametern committet. Arten von Neuheit:
neue Form (Frequenz-Chirp, Sägezahn-Burst, Doppelspike mit fester Verzögerung), neue Frequenz
(7-Hz-Burst, 0,5-Hz-Schwingung über Minuten), langsames Ereignis (Plateau über 30 min, asymmetrische
Welle), nur veränderte Häufigkeit (Spike-Zug mit doppelter Rate), feste Abfolge bekannter
Ereignisse (Spike, dann Sprung nach 2 min), schwer erkennbare Varianten (Spike mit 5-facher
Abklingzeit, Vorzeichenumkehr), Formen aus der Literatur (Zug-Muster nach Adamatzky). Dazu kommen
Beiträge von Robby oder Dritten.

## 7. Offen (vor dem ersten B-Lauf)

1. **Richard:** Befunde zur Eingangsschaltung Rev. 3.6 bestätigen oder korrigieren
   (`PRUEFUNG_QUELLEN_HARDWARE.md`, Abschnitt 2.3), vor allem den ADC-Messbereich und die
   Versorgungsdrift (differenzielle Messung gegen VMID). Davon hängt ab, wie H-Rev3.6 aussieht.
2. **Robby:** Formen beisteuern (oder Dritte fragen, z. B. Prof. Ultsch), Auswahl für B2
   verblindet treffen, Beurteilende für B8 suchen (≥ 3).
3. R in der Analyse-Umgebung einrichten und prüfen, ob die R-Pakete wie beschrieben laufen
   (`Umatrix`, `GeneralizedUmatrix`; falls 4.1 bzw. 4.2 beschlossen werden, auch
   `DataVisualizations`, `DRquality`, `FCPS` und ggf. `AdaptGauss`, alle GPL-3).
   Pinnen der R-Pakete festlegen, z. B. über eine `renv`-Sperrdatei.
4. Später, mit Hardware: Referenzmessungen nach `PRUEFUNG_QUELLEN_HARDWARE.md`, Abschnitt 4,
   und die Synthese-Parameter danach ersetzen.
