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
| 14.11.2026 | Vergleichsregeln für die Nachrechnung mit pydbt (`NACHRECHNUNG_PYDBT.md`), vor jedem Lauf | 6e92179 |
| 15.11.2026 | Nachrechnung R0 (Technik, V0 übereinstimmend) | 79e49e3 |
| 15.11.2026 | Nachrechnung R1 + R2 (40 Läufe): Gesamturteil **abweichend**, Zwischenbericht `ergebnisse/nachrechnung/BERICHT.md` | e4c32fa |
| 17.11.2026 | Nachrechnung R3 (100 Nullläufe) + V4: Schwellen-Rangfolge wie A4; Bericht R0–R3 | 49f4b61 |
| 17.11.2026 | Nachrechnung R4 (unsere Karte, Endradius 1,0, 20 Läufe): Endradius erklärt die Abweichung **teilweise**, unter Vorbehalt; Bericht R0–R4 | 4f5a0a3 |
| 22.11.2026 | Nachrechnung R5 (neue pydbt-Fassung `e6a483e`, gleicher σ-Verlauf wie unsere Karte, 20 Läufe): Nachbarschaft erklärt die Abweichung **nicht** (4 von 11), unter Vorbehalt; Bericht R0–R5 | (dieser Commit) |

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
7. **Zuerst die falsche Hardware-Revision geprüft.** Die Eingangsschaltung wurde zunächst an
   Revision 3.3 (06.10.2026) beurteilt, und eine Notiz an Richard dazu war schon geschrieben
   (nicht versendet). Robby wies auf Revision 3.6 (21.10.2026) hin. Sie lag nur als ZIP vor,
   und die Suche nach dem neuesten Schaltplan hatte nur entpackte Ordner erfasst. Nach der
   Prüfung von 3.6 waren die meisten 3.3-Befunde behoben, dafür kamen zwei neue Punkte dazu
   (ADC-Messbereich, Doppelrolle des Mittenspannungspuffers). Danach reichte Robby die
   **Finalfassung von 3.6 (25.10.2026)** nach. Darin ist die Doppelrolle durch einen eigenen
   Puffer (U19) bereits behoben. Die 3.3-Notiz wurde durch eine Notiz zur Finalfassung ersetzt.
   **Lehre:** Vor jeder Hardware-Aussage den aktuellen Stand bei Robby erfragen, auch ZIP-Archive
   durchsuchen und die Revision im Text nennen.

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
9. **Nachrechnung mit pydbt (R2): abweichend.** Sättigung und die Sprung-Gruppen übertragen sich,
   die Reaktion nur in 5/10 Läufen, von 11 stabilen A4-Kandidaten nur 4. pydbt fasst die
   Spike-Lage-Fragmente zu größeren Gruppen zusammen; die feine Aufteilung aus A4 hängt also
   auch von der ESOM-Umsetzung ab. Ursache offen (Endradius σ 0,75 nicht einstellbar,
   Online- statt Batch-Training). Details `ergebnisse/nachrechnung/BERICHT.md`.
   V4 (R3): Die globale Schwelle bestehen unter pydbt wie in A4 nur Sättigung und die
   Spike-Gruppe der Fenstermitte. Diese ist mit einer Nachbargruppe verschmolzen und gilt nach der
   Zuordnung (Jaccard ≥ 0,5, nicht vorab festgelegt) als „neu bestanden“.
   R4 (Regeln 7e): Unsere Karte mit Endradius 1,0 verliert 4 der 7 betroffenen Kandidaten
   (Urteil „teilweise“, unter Vorbehalt, weil P K13 nur 7/10). Das Muster ist anders als
   bei pydbt (Reaktion und PL K28 bleiben, kaum Verschmelzungen); der Rest liegt vermutlich
   im Training, ungeprüft.
   R5 (Regeln 7f): Die neue pydbt-Fassung mit genau unserem σ-Verlauf reproduziert wieder nur
   4 der 11 stabilen Kandidaten (Urteil „nicht“, unter Vorbehalt, P K13 7/10). Die Reaktion
   ist zurück (8/10), die Fragmente der PL-Fenstermitte verschmelzen weiter. Die Ursache liegt
   im Training selbst (online statt Batch, Lernrate, Startwerte), nicht getrennt geprüft.

## Befunde außerhalb der Analyse (zur Weitergabe)

- **Eingangsschaltung Rev. 3.6, Finalfassung 25.10.** (aus Konstruktionsunterlagen, nicht
  gemessen): Die Schwächen von 3.3 (REF und Bezugselektrode auf GND, kein Ruhestrompfad,
  fehlende Vorwiderstände) sind behoben, die Mittenspannung hat einen eigenen Puffer (U19).
  Offen:
  - Der ADC-Messbereich muss zur Mittenspannung 1,65 V passen (±4,096 V statt der ±0,256 V
    aus dem Datenformat).
  - Der ADC misst einpolig gegen GND. Drift der Analogversorgung geht deshalb zur Hälfte in den
    Messwert ein (10 mV Versorgung ≈ 50 µV am Eingang). Abhilfe: differenzielle Messung gegen
    VMID.
  - Der Rückstrom der Stimulation fließt in den Bezugspunkt.
  - Es gibt kein Anti-Aliasing.
  - Die Unterlagen widersprechen sich in einigen Punkten.
  - Die Verstärkung ist 101 statt 100.

  Details: `PRUEFUNG_QUELLEN_HARDWARE.md`, Abschnitt 2. Bestätigung durch Richard steht aus.
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
