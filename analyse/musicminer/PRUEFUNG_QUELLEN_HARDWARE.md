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

**Grundlage:** KiCad-Projekt „OpenMyCoNet_Project_Completed_Package_V3.3“ (Kombi-Node,
Revision 3.3, Konstruktionsnotizen vom 01.–03.10.2026, Dateien vom 06.10.2026, lokal unter
`Downloads/…/COMBO NODE BOARD/COMBO_NODE/`). Ausgewertet wurden nur lesend die Netzzuordnung der
Pads in `COMBO_NODE.kicad_pcb` und die Notizen in den Schaltplänen. Dazu kommen die Datenblätter
TI INA333 (SBOS445C) und ADS1115 (SBAS444E). **Ob Revision 3.3 der Fertigungsstand ist, muss
Richard bestätigen.**

### 2.1 Was die Unterlagen zeigen

| Punkt | Befund (Rev. 3.3) | Datenblatt |
|---|---|---|
| Verstärker | INA333 (U10), Versorgung **einseitig** +3,3 V (+3.3VA / GND) | Eingangs-Gleichtaktbereich (V−) + 0,1 V bis (V+) − 0,1 V; Ausgang bis etwa 50 mV an die Versorgungsgrenzen (10 kΩ Last) |
| Verstärkung | Schalter SWITCH1 wählt R_G = 100 Ω / 1 kΩ / 10 kΩ, also **G = 1001 / 101 / 11** | G = 1 + 100 kΩ / R_G |
| REF-Anschluss | Pad 5 (REF) liegt auf **GND** | Bei einseitiger Versorgung empfiehlt das Datenblatt REF auf **halbe Versorgung**: „Zero differential input voltage demands an output voltage of mid-supply“ |
| Bezugselektrode | Koaxbuchse über 100 Ω ∥ 100 nF an **GND**, also kein Anschluss an den Verstärker. Sie legt das Substrat auf das Massepotenzial der Platine. | „VIN+ and VIN– must both be 0.1 V more than ground for linear operation“ |
| Eingänge | J4 (IN+/IN−) direkt an INA333, Klemmdioden BAV199 nach +3.3VA/GND. **Die in den Notizen genannten 1-kΩ-Vorwiderstände sind in der Netzliste nicht vorhanden.** Kein Eingangs-RC-Filter. | Pfad für den Eingangsruhestrom nötig (Abschnitt 8.2.2.5) |
| ADC | ADS1115 (U8), **AIN0 einpolig** (AIN1–3 offen), Messbereich ±0,256 V. Davor 100 Ω + 1 nF (Grenzfrequenz ≈ 1,6 MHz) und der Analogschalter TS5A3159 (Umschaltung Bio/EC). | Einpolige Messung nutzt nur Codes 0000h–7FFFh, also **0 bis +0,256 V**. Empfohlenes Anti-Aliasing-RC: Grenzfrequenz bei der Datenrate bis 10-fach darüber, hier also 250 Hz bis 2,5 kHz. |
| Rauschen | – | INA333: 50 nV/√Hz, 1 µVss (0,1–10 Hz) bei G = 100. ADS1115 bei 250 SPS und ±0,256 V: 7,81 µV eff. (18,5 µVss) am ADC, durch G = 101 geteilt also ≈ 0,08 µV am Eingang. **Das Rauschen der Elektronik ist klein gegen das Modellrauschen der Sandbox (4–22 µV).** |
| Datenrate | 250 SPS, Toleranz ±10 % | Datenblatt: Datenrate −10 % bis +10 % |
| Bandbreite INA | – | 3,5 kHz bei G = 100 |
| Stimulation | Rückleiter der Stimulationsklemme J11 liegt auf derselben **GND** wie die Bezugselektrode | – |
| EC-Messung | teilt sich den ADC-Kanal mit dem Biosignal (Analogschalter), Einschwingzeit 100–150 ms nach dem Umschalten (Notiz) | – |

### 2.2 Folgen, sofern Rev. 3.3 so gefertigt wird (von Richard zu prüfen)

1. **Negative Spannungen gehen verloren.** REF liegt auf GND, und der ADC misst einpolig. Damit
   kann nur IN+ > IN− dargestellt werden, also bei G = 101 etwa **0 bis +2,5 mV** am Eingang.
   Nahe 0 V kommt eine tote Zone dazu: Der Ausgang kommt nur bis etwa 50 mV an GND heran. Das
   entspricht rund 0,5 mV am Eingang (Datenblattwert für 10 kΩ Last; bei der hochohmigen
   ADC-Last vermutlich weniger, nicht spezifiziert). Biphasische Spikes würden halbiert.
   Die Sandbox nimmt dagegen einen **zweiseitigen** Bereich von ±2,56 mV an.
2. **Gleichtakt an der Grenze.** Die Bezugselektrode legt das Substrat auf GND. Die
   Messelektroden liegen damit nahe 0 V, der INA333 braucht aber mindestens 0,1 V über GND.
   Je nach Elektrodenpotenzial arbeitet der Verstärker außerhalb seines linearen Bereichs.
3. **Gleichspannungsanteil der Elektroden.** Der Eingang ist gleichspannungsgekoppelt. Jede
   Spannungsdifferenz zwischen den beiden Messelektroden (Elektrodenpotenziale, Polarisation)
   wird mitverstärkt. Bei G = 101 reichen etwa 2,5 mV für die Sättigung. Wie groß die
   Differenz bei Edelstahlelektroden im Substrat ist, ist unbekannt und **muss gemessen
   werden**. Die Literaturgruppe misst mit 156 mV Messbereich.
4. **Kein Anti-Aliasing.** Netzeinstreuung und Oberwellen werden nur durch das Digitalfilter
   des ADS1115 gedämpft. Dessen Verlauf ist im Datenblatt nur als Grafik angegeben (Abb. 5-21),
   die Dämpfung bei 100–150 Hz ist daraus nicht genau ablesbar. Anteile nahe der
   Modulatorfrequenz (250 kHz) werden laut Datenblatt gar nicht gedämpft.
5. **Gemeinsame Masse von Stimulation und Messung.** Elektrische Stimulation und Bezugselektrode
   teilen sich GND. Stimulationsartefakte (Klemmung über die BAV199, Erholung) sind deshalb
   wahrscheinlich. Das passt zum offenen Hardware-Punkt „Messpfad-Entkopplung“ vom 27.09.2026.
6. **Verstärkung 101 statt 100.** Im Datenformat steht „Verstärkung 100“. Der Unterschied
   beträgt 1 % in allen µV-Werten. Klein, aber beim ersten Lauf richtig eintragen.

Das sind **Befunde aus den Unterlagen, keine Messung**. Sie gehören an Richard (Hardware) und in
den Hardware-Status im Kontrollzentrum. Für die Analyse folgt: Phase B rechnet mit **zwei
Hardware-Modellen** (Abschnitt 3), damit sichtbar wird, was die Schaltung mit den Signalen macht.

## 3. Folgen für die Signalparameter in Phase B

| Thema | bisheriger Entwurf | neu (Vorschlag für E2/Phase B) |
|---|---|---|
| Zeitskalen der Fenster | nur 10 s | **drei Skalen:** 10 s (schnell), 2 min (Spikes nach Literatur), 20 min (Züge, Drift); für die langen Skalen Mittelung auf 1 Wert/s (wie in der Literatur) |
| Spike-Familien | 20–300 µV, 10–200 ms | (a) **schnell** 10–200 ms, nur als Methodentest; (b) **pilzähnlich** Dauer 30 s – 20 min, einzelne bis 2 h, Amplitude 0,03–2 mV, in Zügen (2–8 Spikes, Zugdauer 20–120 min) |
| Grundliniendrift | 0,01–5 µV/s | Wellen von **1–12 h**, 0,1–1 mV; dazu langsame Rhythmen (30 min, 24 h). Wochenperioden passen nicht in die Laufzeit der Testsignale, nur als Hinweis. |
| Hardware-Modell | ideal, ±2,56 mV | **H-ideal** (zweiseitig ±2,53 mV, G = 101) und **H-Rev3.3** (einseitig 0 bis +2,53 mV, tote Zone 0–0,5 mV, Elektroden-Gleichanteil, Sättigung, kein Anti-Aliasing); dieselben Signale durch beide Modelle |
| Netzeinstreuung | 1–200 µV | bis zur Sättigung; Faltung über ein Filtermodell, das als **Annahme** gekennzeichnet ist (sinc-Verlauf), bis das Digitalfilter nachgemessen ist |
| Elektroden-Gleichanteil | – | 0 bis ± einige mV, unbekannt → als Parameterreihe, bis zur Messung |
| Rauschen | weiß, 4–22 µV | weiß + 1/f; Elektronik vernachlässigbar (siehe 2.1), Elektrode/Umgebung unbekannt |

## 4. Was nur durch Messungen an der Hardware zu klären ist

1. Gleichspannungsdifferenz und Drift zwischen zwei Edelstahlelektroden im Substrat ohne Pilz
   (Stunden bis Tage).
2. Rauschen und Netzeinstreuung im Feld mit der echten Verkabelung (≤ 20 cm).
3. Verlauf des ADS1115-Digitalfilters (Sinus mit bekannten Frequenzen einspeisen).
4. Stimulationsartefakte: elektrisch (mit und ohne Abschwächer 1:10), LED (einschließlich der
   PWM-Frequenz), Umschaltung Bio/EC.
5. **Kontrollen ohne lebendes Myzel** (nur Substrat, abgetötetes Myzel) mit denselben Elektroden
   und Reizen.
