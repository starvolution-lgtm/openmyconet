# Versuchsverlauf: Entscheidungen, Abweichungen, verworfene Ansätze, negative Ergebnisse

Dieses Protokoll fließt in den Gesamtbericht ein (auch zur fachlichen Beurteilung durch
Prof. Ultsch). Es wird fortlaufend ergänzt und nachträglich nicht geschönt. Alle Ergebnisse
beziehen sich auf **Simulationsdaten** (Phase A) bzw. **synthetische Signale** (Phase B).

## Zeitleiste

| Datum | Schritt | Commit |
|---|---|---|
| 05.11.2026 | Auftrag Robby: MusicMiner-Ansatz (Merkmale → ESOM → U-Matrix) für BioComm prüfen, Variante B (eigenständig, nur lesend) | – |
| 05.11.2026 | A0: Schnappschuss der Sandbox-Szenarien von Staging, Kriterien v1/v2 vor dem ersten Training | 05e2f67 |
| 05.11.2026 | A1–A3: Fenster, Merkmalssatz `mv1`, eigene Batch-SOM, Bericht | b5d7fd1 |
| 05.11.2026 | Ergänzung E1 (größenabhängige Nullmodelle, drei Stufen), **vor A4** | 0301a87 |
| 05.11.2026 | A4: Methodenvergleich, E1, Robustheit Endradius; Phase-B-Entwurf Fassung 1 | be3804c |
| 05.11.2026 | Prüfung Literatur + Eingangsschaltung, Ergänzung E2, Phase-B-Vorbereitung Fassung 2 | bb6ecd1 |

## Abweichungen vom Plan und ihre Gründe

1. **Kontrollwert des Schnappschusses stimmte zunächst nicht** (78 682 522,194 statt
   78 682 442,071). Ursache: Auf Staging lagen vier zusätzliche Reihen eines Test-Messknotens.
   Der Export wurde auf die Szenario-Reihen beschränkt, danach stimmte der Wert.
2. **Gruppenregel v1 verworfen, bevor echte Daten trainiert wurden.** Im Test mit drei
   künstlichen Punktwolken fand sie auf der toroidalen Karte nur zwei Gruppen und hätte seltene
   Ereignisse in große Gruppen verschmolzen. Ersetzt durch Regel v2 (leere Neuronen als Wände,
   Inseln ≥ 10 Fenster). Die Änderung ist in `KRITERIEN.md` vor dem Training dokumentiert.
3. **MiniSom nur als Gegenprobe.** Die Bibliothek kennt keine toroidale Karte. Deshalb wurde eine
   eigene Batch-SOM geschrieben. Dadurch ist die ESOM in Phase A eine **Eigenumsetzung**, nicht
   die Originalsoftware. Unterschied sichtbar in A3: MiniSom QE 1,78 / TE 0,012 gegen eigene
   1,23 / 0,114. Grund ist der kleine Endradius 0,75 der eigenen Karte.
4. **Nachträgliche Schwellenänderung verworfen.** Nach A3 hatte Cody vorgeschlagen, das
   Nullmodell-Kriterium 8b.2 für A1–A3 neu zu fassen (Entwurf „v3“). Auf Robbys Vorgabe wurde das
   zurückgenommen: A1–A3 bleiben nach v2 bewertet, die Ergänzung gilt nur prospektiv (E1).
5. **8b.4c wörtlich angewendet, obwohl zu streng.** In A4 schloss die Regel „≥ 90 % der Fenster
   an der Normierungsgrenze in irgendeinem Merkmal“ 14 von 15 Kandidaten aus. Sie wurde für A4
   nicht geändert, sondern erst für Phase B präzisiert (E2 10.1).
6. **8b.5 vermischte Übertragung und Neuheit.** Die Sättigung kam in A4 nur in einem Segment
   vor und galt deshalb als „nicht übertragbar“, obwohl das gar nicht prüfbar war. Für Phase B
   gibt es drei Ergebnisse (bestanden / nicht bestanden / nicht prüfbar, E2 10.2).

## Verworfene Ansätze

| Ansatz | Warum verworfen |
|---|---|
| Kleine SOM als Ersatz für eine ESOM | trennt gröber (A3); MusicMiner beruht auf großen, emergenten Karten |
| Gruppenregel v1 | siehe Abweichung 2 |
| Kriterium „v3“ rückwirkend für A1–A3 | siehe Abweichung 4 |
| k-Means mit k aus der ESOM als Vergleichsverfahren | bekommt einen Hinweis aus der ESOM und ist damit nicht unabhängig; in Phase B weggelassen |
| Größerer Endradius (1,5 oder 3,0) als neue Grundeinstellung | senkt den Topologiefehler, verliert aber Spike-Gruppen (1,5) bzw. Sättigung und Reaktion (3,0); der Topologiefehler allein ist kein Ziel |
| Phase-B-Entwurf Fassung 1 (nur 10-s-Fenster, Spikes 10–200 ms) | passt nicht zu den in der Literatur beschriebenen Zeitskalen extrazellulärer Pilzsignale (Minuten bis Stunden); ersetzt durch drei Zeitskalen |
| Nur ein künstliches neues Signal in B2 | Ergebnis hinge von dessen Eigenschaften ab; ersetzt durch ≥ 8 einzeln zurückgehaltene Formen |

## Negative Ergebnisse

1. **A3, H5 widerlegt:** Die vermutete „unsichtbare“ Stimulationsphase zeigte eine stabile
   Sprung-Insel. Sie stammt aber aus dem Rechenmodell (Reaktion setzt schlagartig ein), nicht aus
   einer neuen Struktur.
2. **A3, H8:** Spike-Fenster zerfallen nach der Lage des Spikes im Fenster. Das ist eine Schwäche
   des Merkmalssatzes `mv1`, keine Signaleigenschaft.
3. **A4: kein Kandidat erreicht eine der beiden oberen Stufen** (alle 15 „unbestätigt“).
4. **A4: kein Mehrwert der ESOM bei bekannten Strukturen (8a).** Bei der Sättigung sind alle
   Verfahren gleich gut. Bei „nach der Stimulation“ sind die robuste Mahalanobis-Distanz (AUC
   0,85) und eine einfache Schwelle (0,96) besser als die ESOM (0,78).
5. **A4: die Sprungstruktur ist nicht ESOM-spezifisch.** HDBSCAN findet sie ohne Vorgabe.
6. **A4: die beiden einzigen ESOM-spezifischen Inseln** sind Spike-Lage-Fragmente (siehe 2).
7. **A4: Nullmodelle liefern für große Gruppen keine Vergleichsgrundlage** (0 Komponenten ≥ 160
   Fenster), deshalb dort keine größenabhängige Signifikanz.
8. **Größenabhängige Schwelle nicht durchweg milder:** In G2 lag sie über der globalen Schwelle.

## Befunde außerhalb der Analyse (zur Weitergabe)

- **Eingangsschaltung Rev. 3.3** (aus Konstruktionsunterlagen, nicht gemessen): REF des INA333
  auf GND bei einseitiger Versorgung, einpoliger ADC-Eingang, Bezugselektrode auf GND, kein
  Anti-Aliasing, Vorwiderstände aus den Notizen fehlen in der Netzliste, Verstärkung 101 statt
  100. Details und Folgen: `PRUEFUNG_QUELLEN_HARDWARE.md`, Abschnitt 2. Bestätigung durch Richard
  steht aus.
- **Literatur:** Extrazelluläre Pilzsignale werden überwiegend von einer Arbeitsgruppe berichtet.
  Es gibt eine Artefakt-Kritik (Blatt et al. 2024). Kontrollmessungen ohne lebendes Myzel sind
  für BioComm unverzichtbar.

## Bekannte methodische Grenzen (für den Bericht)

- Phase A beruht auf einem Rechenmodell mit frei gewählten Parametern (`ARBITRARY_DEMO`);
  Phase B auf literaturgestützten, nicht hardware-validierten Synthesesignalen.
- Merkmale, Generator und Katalog der neuen Formen stammen überwiegend von derselben Stelle
  (Cody). Gegenmaßnahmen und Restrisiko: E2 10.5.
- Die ESOM-Ergebnisse von Phase A beruhen auf einer Eigenumsetzung. Phase B nimmt die
  Referenzumsetzung (R-Paket `Umatrix`) hinzu.
