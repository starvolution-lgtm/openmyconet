# Prüfung vor Phase B: Zeitskalen der Pilzsignale und Eingangsschaltung

Stand 05.11.2026. Vor der Festlegung von E2 und der Signalparameter für Phase B geprüft
(Auftrag Robby). Die Signalparameter sollen nicht nur auf allgemeinen Annahmen beruhen.

**Wichtig vorab:** Alle Zahlen hier sind Literaturwerte oder Werte aus Konstruktionsunterlagen
und Datenblättern. Gemessen an der BioComm-Hardware ist noch nichts. Für Phase B werden sie als
**„synthetisch, literaturgestützt, nicht hardware-validiert“** gekennzeichnet.

## 1. Zeitskalen und Amplituden bioelektrischer Pilzsignale (Literatur)

### 1.1 Befunde

| Quelle | Aufnahme | Befund |
|---|---|---|
| Adamatzky & Gandia, *Fungi anaesthesia*, Sci. Rep. 12 (2022), doi 10.1038/s41598-021-04172-0, arXiv 2106.09007 | *Pleurotus ostreatus*, Myzel in Substrat; Nadelelektroden (Iridium-beschichteter Edelstahl), Abstand 1–2 cm; Logger ADC-24 (Pico), 24 Bit, Messbereich 156 mV, **1 Wert/s** gespeichert | „langsame (Stunden) unregelmäßige Wellen der Grundlinie“ und „schnelle (Minuten) Spikes“. Intakt: Spike-Amplitude Median 0,48 mV, Spike-Dauer Median **62 s**, Abstand zwischen Spikes Median 214 s; Spike-Züge im Median aus 3 Spikes, Zugdauer Median **84 min**, Abstand zwischen Zügen Median 53 min. Grundliniendrift: Dauer Median ≈ 8,3 h, Amplitude Median **0,45 mV**. Unter Chloroform deutlich kleinere Amplituden und seltenere Spikes. |
| Adamatzky, *Language of fungi derived from their electrical spiking activity*, R. Soc. Open Sci. 9, 211926 (2022), arXiv 2112.09907 | vier Arten (*Omphalotus nidiformis*, *Flammulina velutipes*, *Schizophyllum commune*, *Cordyceps militaris*), Differenzialelektroden im Substrat bzw. Fruchtkörper | Spike-Dauer artabhängig **1 bis 21 h**, Amplitude **0,03 bis 2,1 mV**, Spikes oft in Zügen. |
| Adamatzky, *On spiking behaviour of oyster fungi Pleurotus djamor*, Sci. Rep. 8 (2018) | Fruchtkörper | zwei Spike-Modi mit Periode **2,6 min** und **14 min**. Eine spätere Arbeit derselben Gruppe nennt für diese Art Amplituden von 0,5 bis 6 mV (nur aus Sekundärquelle, nicht selbst geprüft). |
| Fukasawa, Akai, Takehi, Osada, *Electrical integrity and week-long oscillation in fungal mycelia*, Sci. Rep. 14, 15601 (2024), doi 10.1038/s41598-024-66223-6 | *Pholiota brunnescens* auf Agar mit Holzköder, über **100 Tage** aufgezeichnet | gerichteter Potenzialfluss vom Köder ins übrige Myzel, nach etwa 60 Tagen Schwingungen mit etwa **einer Woche** Periode. Die Arbeit fasst die berichteten Perioden zusammen: Millisekunden bis 20–40 s (aktionspotenzialähnlich), etwa 30 min (Fruchtkörper), 20–24 h (tagesrhythmisch). |
| Olsson & Hansson, Naturwissenschaften 82, 30–31 (1995); Slayman, Long & Gradmann, BBA 426, 732–744 (1976) | **intrazelluläre** Ableitung (*Armillaria*, *Pleurotus* bzw. *Neurospora*) | aktionspotenzialähnliche Aktivität, schneller als die extrazellulären Befunde. Volltexte nicht geprüft, nur Sekundärquellen. |
| Blatt et al., *Does electrical activity in fungi function as a language?*, Fungal Ecology (2024), doi 10.1016/j.funeco.2023.101326 | Kommentar | **Kritik:** Die Spannungsschwankungen könnten nicht biologisch sein, sondern Mess- und Elektrodenartefakte (z. B. Bewegung oder Drift der Elektrodenspitze im Substrat). Nur Zusammenfassungen gelesen. |

### 1.2 Einordnung

- Die extrazellulären Befunde (wie BioComm sie messen würde) liegen bei **Minuten bis Stunden**
  (Spikes), **Stunden** (Grundliniendrift) und bis zu **Tagen bzw. einer Woche** (Rhythmen). Die
  Amplituden reichen von etwa **0,03 bis 2 mV**, in einzelnen Berichten mehr.
- Die Daten stammen überwiegend aus **einer** Arbeitsgruppe und sind kaum unabhängig repliziert.
  Es gibt eine ernst zu nehmende Artefakt-Kritik. Für BioComm folgt daraus:
  Kontrollmessungen ohne lebendes Myzel sind Pflicht, bevor irgendetwas als biologisch gilt.
- **Folge für die Analyse:** Unsere bisherigen 10-s-Fenster mit Spikes von 10–200 ms
  (Sandbox-Modell) erfassen diese Zeitskalen nicht. Die lineare Trendentfernung in `mv1` würde
  Ereignisse von Minuten bis Stunden innerhalb eines 10-s-Fensters als Trend behandeln und
  entfernen. Phase B braucht deshalb **mehrere Zeitskalen** (Abschnitt 3).
- Die schnellen Spikes (10–200 ms) bleiben als **methodischer Testbaustein** im Katalog. Sie
  werden aber nicht als pilztypisch bezeichnet.

## 2. Eingangsschaltung der BioComm-Platine (Konstruktionsunterlagen)

### 2.1 Grundlage und Fassungen

- **Maßgeblich ist die Finalfassung von Revision 3.6**
  (`OpenMyCoNet_Project_Completed_Package_Finale_Ver3.6.zip`, Konstruktionsnotizen „Revision
  3.6, Date 2026-10-25“). Robby hat sie als aktuellen Stand genannt.
- Ausgewertet wurden nur lesend die Netzzuordnung der Pads in `COMBO_NODE.kicad_pcb` und die
  Notizen in den Schaltplänen, dazu die Datenblätter TI INA333 (SBOS445C) und ADS1115
  (SBAS444E). Gemessen ist nichts. **Ob diese Fassung gefertigt wird, muss Richard bestätigen.**
- Geprüft wurden der Reihe nach drei Fassungen: zuerst versehentlich Rev. 3.3 (06.10.), dann
  Rev. 3.6 vom 21.10., schließlich die Finalfassung vom 25.10. (siehe 2.4 und `VERLAUF.md`). In
  der Eingangsschaltung unterscheidet sich die Finalfassung von der Fassung vom 21.10. nur durch
  einen eigenen Puffer für die Mittenspannung (U19).

### 2.2 Was die Unterlagen der Finalfassung zeigen

| Punkt | Befund (Rev. 3.6 final) | Datenblatt |
|---|---|---|
| Verstärker | INA333 (U10), Versorgung einseitig +3.3VA / GND | Eingangs-Gleichtaktbereich (V−) + 0,1 V bis (V+) − 0,1 V; Ausgang bis etwa 50 mV an die Versorgungsgrenzen |
| Verstärkung | R_G = 100 Ω / 1 kΩ / 10 kΩ per Schalter, also **G = 1001 / 101 / 11** | G = 1 + 100 kΩ / R_G |
| Mittenspannung VMID_REFF | Teiler R43/R44 (je 100 kΩ) + C34 100 nF; **eigener Puffer U19 (OPA333, Spannungsfolger, ohne Abschaltung)**, über R62 (22 Ω) auf VMID_REFF. Der EC-Verstärker U13B nutzt nur noch den Teiler als Bezug und ist von VMID_REFF getrennt. | REF muss niederohmig angesteuert werden; das ist erfüllt |
| REF-Anschluss | Pad 5 an **VMID_REFF (≈ 1,65 V)** | entspricht der Empfehlung für einseitige Versorgung |
| Bezugselektrode | Koaxbuchse über 100 Ω ∥ 100 nF an **VMID_REFF** | Eingänge liegen in der Mitte des Gleichtaktbereichs |
| Eingänge | J4 → **R56/R57 je 1 kΩ** → INA333; Klemmdioden BAV199; **10 MΩ (R63/R64) von jedem Eingang nach VMID_REFF** | Ruhestrompfad vorhanden. Kein Eingangs-RC-Filter. |
| Rückleiter Stimulation | J11 Pin 2 und der Abschwächer (R46) an **VMID_REFF** | – |
| ADC | ADS1115 (U8), **AIN0 einpolig gegen GND** (AIN1–3 offen); davor TS5A3159 (Bio/EC), 100 Ω + 1 nF (Grenzfrequenz ≈ 1,6 MHz) | Einpolig: 0 V bis +FSR (höchstens VDD). Empfohlenes Anti-Aliasing-RC: Grenzfrequenz bei der Datenrate bis 10-fach darüber. |
| Messbereich ADC | **nicht festgelegt** (Firmware). Der INA-Ausgang ruht bei ≈ 1,65 V. Bei ±0,256 V (so steht es im Datenformat) läge schon die Ruhelage außerhalb des Bereichs. Nutzbar sind ±2,048 V (0–2,048 V, also −16 mV bis +3,9 mV am Eingang bei G = 101) oder ±4,096 V (0–3,3 V, also etwa ±16 mV). | ADS1115 bei 250 SPS: ±2,048 V → 62,5 µV eff. (0,62 µV am Eingang), LSB 0,62 µV; ±4,096 V → 125 µV eff. (1,24 µV am Eingang), LSB 1,24 µV |
| Stromversorgung ADC | Netzliste: ADS1115 an **+3.3V** (digital). Die Notizen nennen +3.3VA. | – |
| Bauteilbezeichnungen | In einer Notiztabelle heißt U19 „LPV811DBV“, sonst, auf der Platine und in der korrigierten Stückliste (`COMBO_NODE_V3.6_bom_korrigiert.csv`) OPA333AIDBVR. Die Notizen nennen den ADS1115 U14 und den Analogschalter U15, auf der Platine sind es U8 und U9. | – |

### 2.3 Folgen, sofern die Finalfassung so gefertigt wird (von Richard zu prüfen)

**Behoben gegenüber 3.3:** REF und Bezugselektrode liegen auf der Mittenspannung, es gibt einen
Ruhestrompfad über 10 MΩ und die 1-kΩ-Vorwiderstände. **Behoben gegenüber der Fassung vom
21.10.:** Der Puffer der Mittenspannung ist nicht mehr zugleich EC-Transimpedanzverstärker.
Damit sind **zweiseitige Signale messbar**, die Eingänge liegen im linearen Bereich, und
EC-Ströme verschieben den Bezugspunkt nicht mehr.

Offen:

1. **ADC-Messbereich muss zur Mittenspannung passen.** Mit ±4,096 V (einpolig) beträgt der
   Eingangsbereich bei G = 101 etwa ±16 mV, bei 1,24 µV Auflösung und rund 1,2 µV Rauschen. Für
   Pilzsignale von 0,03–2 mV reicht das, und Elektroden-Gleichanteile bis über 10 mV passen
   hinein. Das Datenformat (`pga_v` 0,256, `lsb_uv` 7,8125) muss dann entsprechend gesetzt
   werden; die Felder dafür gibt es je Kanal schon.
2. **Versorgungsdrift geht in den Messwert ein.** Der ADC misst einpolig gegen GND, die
   Mittenspannung ist die halbe Analogversorgung. Ändert sich +3.3VA um 10 mV (Temperatur,
   Last), wandert der Messwert um 5 mV am ADC, also um rund 50 µV am Eingang (G = 101). Das
   liegt genau im Bereich der langsamen Pilzsignale (0,1–1 mV über Stunden). Abhilfe wäre
   eine **differenzielle Messung AIN0 gegen AIN1 = VMID_REFF**. Damit hebt sich die Drift auf,
   und der kleine Messbereich ±0,256 V mit 0,08 µV Auflösung wäre wieder nutzbar (dann ±2,5 mV
   am Eingang). Dafür müsste AIN1 verbunden werden.
3. **Stimulation am Bezugspunkt.** Der Rückstrom der elektrischen Stimulation fließt über R62
   (22 Ω) in den Puffer U19, also in den Bezugspunkt von Verstärker und Bezugselektrode. Schon
   1 mA ergibt 22 mV Verschiebung, am Eingang rund 0,2 mV. Stimulationsartefakte sind damit
   sicher. Eine Abtrennung des Messpfads während der Stimulation (Punkt 3 der Prüfrunde vom
   27.09.) ist nicht zu erkennen.
4. **Kein Anti-Aliasing** (unverändert, Grenzfrequenz ≈ 1,6 MHz). Netzeinstreuung und Oberwellen
   dämpft nur das Digitalfilter des ADS1115. Dessen Verlauf ist im Datenblatt nur als Grafik
   angegeben. Anteile nahe 250 kHz werden gar nicht gedämpft.
5. **Gleichspannungsanteil der Elektroden** (unverändert) wird mitverstärkt. Mit ±16 mV Bereich
   ist er weniger kritisch als in 3.3. Seine Größe muss gemessen werden.
6. **Einschwingen der Eingänge** nach dem Einschalten bzw. nach Stimulation über 10 MΩ und die
   Elektroden- und Leitungskapazität: Die Dauer ist unbekannt, die ersten Werte sind zu
   markieren. VMID selbst bleibt dank U19 ohne Abschaltung stehen.
7. **Unterlagen widersprechen sich** in Kleinigkeiten (Versorgung des ADC, Bezeichnung von U19,
   Bauteilnummern). Vor der Fertigung zu bereinigen.
8. **Verstärkung 101 statt 100** (unverändert); 1 % in allen µV-Werten.

### 2.4 Zum Vergleich: frühere Fassungen (überholt)

- **Rev. 3.3 (06.10.):** REF und Bezugselektrode auf GND, kein Ruhestrompfad, Vorwiderstände
  fehlten in der Netzliste. Damit wären nur positive Spannungen von 0 bis +2,5 mV messbar
  gewesen, mit einer toten Zone nahe 0, und der Gleichtakt hätte außerhalb des INA333-Bereichs
  gelegen.
- **Rev. 3.6 vom 21.10.:** wie die Finalfassung, aber die Mittenspannung wurde von U13B
  gepuffert, der zugleich EC-Transimpedanzverstärker war (invertierender Eingang an der
  EC-Sense-Elektrode). EC-Ströme hätten den Bezugspunkt verschoben. In der Finalfassung ist das
  durch U19 behoben.
- In allen Fassungen gleich geblieben: einpoliger ADC-Eingang, kein Anti-Aliasing,
  Verstärkung 101, Rückstrom der Stimulation am Bezugspunkt.

## 3. Folgen für die Signalparameter in Phase B

| Thema | bisheriger Entwurf | neu (Vorschlag für E2/Phase B) |
|---|---|---|
| Zeitskalen der Fenster | nur 10 s | **drei Skalen:** 10 s (schnell), 2 min (Spikes nach Literatur), 20 min (Züge, Drift); für die langen Skalen Mittelung auf 1 Wert/s (wie in der Literatur) |
| Spike-Familien | 20–300 µV, 10–200 ms | (a) **schnell** 10–200 ms, nur als Methodentest; (b) **pilzähnlich** Dauer 30 s – 20 min, einzelne bis 2 h, Amplitude 0,03–2 mV, in Zügen (2–8 Spikes, Zugdauer 20–120 min) |
| Grundliniendrift | 0,01–5 µV/s | Wellen von **1–12 h**, 0,1–1 mV; dazu langsame Rhythmen (30 min, 24 h). Wochenperioden passen nicht in die Laufzeit der Testsignale, nur als Hinweis. |
| Hardware-Modell | ideal, ±2,56 mV | **H-ideal** (zweiseitig ±2,53 mV, G = 101, wie die Sandbox) und **H-Rev3.6** (±16 mV, Auflösung 1,24 µV, ADC-Rauschen 1,2 µV am Eingang, Elektroden-Gleichanteil, Sättigung, kein Anti-Aliasing, Drift der Versorgung im Messwert, Verschiebung der Mittenspannung durch Stimulationsströme); dieselben Signale durch beide Modelle |
| Netzeinstreuung | 1–200 µV | bis zur Sättigung; Faltung über ein Filtermodell, das als **Annahme** gekennzeichnet ist (sinc-Verlauf), bis das Digitalfilter nachgemessen ist |
| Elektroden-Gleichanteil | – | 0 bis ± einige mV, unbekannt → als Parameterreihe, bis zur Messung |
| Rauschen | weiß, 4–22 µV | weiß + 1/f; Elektronik bei Rev. 3.6 ≈ 1,2 µV eff. am Eingang (ADC bei ±4,096 V, siehe 2.2), Elektrode/Umgebung unbekannt |

## 4. Was nur durch Messungen an der Hardware zu klären ist

1. Gleichspannungsdifferenz und Drift zwischen zwei Edelstahlelektroden im Substrat ohne Pilz
   (Stunden bis Tage).
2. Rauschen und Netzeinstreuung im Feld mit der echten Verkabelung (≤ 20 cm).
3. Verlauf des ADS1115-Digitalfilters (Sinus mit bekannten Frequenzen einspeisen).
4. Stimulationsartefakte: elektrisch (mit und ohne Abschwächer 1:10), LED (einschließlich der
   PWM-Frequenz), Umschaltung Bio/EC.
5. **Kontrollen ohne lebendes Myzel** (nur Substrat, abgetötetes Myzel) mit denselben Elektroden
   und Reizen.
