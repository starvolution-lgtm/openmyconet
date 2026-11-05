# Phase A: Datengrundlage, Vorhersage und Bewertungskriterien

Stand 05.11.2026, **vor dem ersten Training** festgehalten. Änderungen an Kriterien danach nur
mit Datum, Begründung und neuer Versionsnummer.

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
