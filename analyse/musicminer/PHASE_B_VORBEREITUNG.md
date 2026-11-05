# Phase B: Vorbereitung (Entwurf, noch nicht gerechnet)

Stand 05.11.2026. Phase B wird separat vorbereitet. Kriterien und Signalkatalog werden **vor**
dem ersten B-Lauf verbindlich festgelegt (eigener Abschnitt in `KRITERIEN.md`). Es gelten
v2 + Ergänzung E1 (Abschnitt 9), soweit dort nichts Abweichendes beschlossen wird.

> SYNTHETISCH. Alle Testsignale in Phase B dienen ausschließlich der technischen und
> methodischen Prüfung. Sie werden nur als Dateien erzeugt, nie in eine BioComm-Datenbank
> geschrieben, nie mit Messdaten vermischt und nie als biologische Trainingsgrundlage verwendet.

## 1. Was aus Phase A mitgenommen wird

### 1.1 Lageabhängigkeit der Merkmale (A3, H8)

Spike-Fenster zerfielen nach der **Lage des Spikes im Fenster**. Ursache: lineare
Trendentfernung und Hann-Fenster gewichten Anfang und Ende anders als die Mitte.

Vorschlag für Merkmalssatz `mv2` (wird vor B festgelegt):
- Trendentfernung robust und lageneutral (gleitender Median statt Geradenanpassung über das
  ganze Fenster).
- Ereignismerkmale aus einer Spitzenerkennung (Zahl, Höhe, Breite der Ereignisse), unabhängig
  davon, wo sie liegen.
- Spektrum über mehrere überlappende Teilfenster gemittelt (Welch), statt eines Hann-Fensters
  über 10 s.
- **Verschiebungstest als Pflichttest:** Dasselbe Ereignis an 20 Positionen im Fenster muss
  Merkmale innerhalb einer vorab festgelegten Toleranz ergeben. `mv1` dient als Vergleich.

### 1.2 Abruptes Einsetzen der simulierten Reaktion (A3, H5)

Die Sprung-Insel geht auf eine Modelleigenschaft zurück: Die angenommene Reaktion setzt am Ende
der Stimulation schlagartig mit voller Höhe ein (`omn/sandbox/modell.py`, `Reaktion.wert`).

In Phase B gezielt untersuchen:
- Reaktion mit veränderlicher **Anstiegszeit** (0 s, 1 s, 10 s, 60 s) und gleicher Höhe: Ab
  welcher Anstiegszeit verschwindet die eigene Insel? Unterscheidet die ESOM „Sprung“ und
  „langsamer Anstieg“ noch als Übergang?
- Dasselbe mit kleiner werdender Höhe (Signal-Rausch-Verhältnis).
- **Keine Änderung am Sandbox-Generator ohne gesonderte Freigabe.** Eine Anpassung des
  öffentlichen Rechenmodells wäre eine neue Szenario-Version mit Folgen für Datenlabor,
  Datengrundlage und Startseiten-Vorschau.

### 1.3 Realistischere Stimulationsartefakte

Die Sandbox enthält **kein** Stimulationsartefakt. Für Phase B sind getrennt erzeugbare,
dokumentierte Artefaktmodelle vorgesehen. Alle Parameter gelten zunächst als frei gewählt
(`ARBITRARY_DEMO`), bis Referenzmessungen an der BioComm-Hardware vorliegen:
- **elektrisch:** Einkopplung des Stimulationspulses (Rechteck mit Flanken), Übersteuerung des
  Verstärkers bis zur ADC-Sättigung, danach exponentielle Erholung (Zeitkonstante des
  Eingangs, z. B. 0,1–10 s);
- **optisch:** kleiner Sprung bzw. kurze Spitzen beim Ein- und Ausschalten der LED
  (photoelektrischer Effekt, Einstreuung des Treibers);
- **Vibration:** Mikrofonie, also eine Schwingung mit der Anregungsfrequenz und abklingendem
  Nachschwingen.
Jedes Artefakt bekommt eine Wahrheitsmarkierung je Sample.

## 2. Signalkatalog (Vorschlag)

| Baustein | Parameter (Bereich, vorläufig) | Wahrheit |
|---|---|---|
| Hintergrund | weißes und farbiges Rauschen (1/f), σ 4–22 µV | Rauschart, σ |
| langsame Schwingung | 0,005–1 Hz, 2–50 µV | Frequenz, Amplitude |
| Impulse/Spikes | 20–300 µV, Abklingen 10–200 ms, Poisson-Rate | Zeitpunkte |
| Sprünge | 5–100 µV | Zeitpunkt, Höhe |
| Drift/Rampe | 0,01–5 µV/s | Steigung |
| Netzeinstreuung | 50 Hz ± 0,2 Hz, Oberwellen, 1–200 µV | Frequenz, Amplitude |
| Kontaktstörung | Grundlinien-Sprünge + mehr Rauschen + Wandern unter 1 Hz | Zeitraum |
| Sättigung | Abschneiden an der ADC-Grenze | Samples |
| Stimulationsartefakte | siehe 1.3 | Zeitraum, Art |
| Überlagerungen | Kombinationen aus 2–3 Bausteinen | alle Einzelwahrheiten |
| **neuartige Formen** (im Training nie enthalten) | z. B. Frequenz-Chirp, Sägezahn-Burst, 7-Hz-Burst | Zeitraum, Art |

**Hinweis zur Abtastrate:** Bei 250 Hz liegt die Nyquist-Grenze bei 125 Hz. Oberwellen über
125 Hz falten sich zurück (150 Hz → 100 Hz, 200 Hz → 50 Hz). Der Generator muss das
Eingangsfilter des ADS1115 nachbilden oder die Faltung ausdrücklich erzeugen, sonst sind die
Testsignale unrealistisch sauber.

## 3. Geplante Versuche

| | Frage |
|---|---|
| B1 | Werden bekannte Artefaktklassen unterschieden (8a), mit `mv1` und `mv2`? |
| B2 | **Neuheit:** Training ohne eine Signalform, dann zeigen. Fällt sie als neue Insel oder Ausreißer auf, bei vorab festgelegter Fehlalarmquote (z. B. 1 %)? Vergleich mit denselben Verfahren wie in A4. |
| B3 | **Störgrad-Reihe:** Ab welchem Signal-Rausch-Verhältnis ist eine schwache Struktur nicht mehr unterscheidbar? Kurve je Verfahren. |
| B4 | **Überlagerungen:** Bleiben Einzelstrukturen trennbar, wenn 2–3 Störquellen zusammenkommen? |
| B5 | **Anstiegszeit der Reaktion** (Abschnitt 1.2). |
| B6 | **Verschiebungstest** `mv1` gegen `mv2` (Abschnitt 1.1). |

Alle Versuche: Seeds 0–9, Aufteilung nach zusammenhängenden Signalabschnitten (nie überlappende
Fenster in Training und Test), Nullmodelle wie in E1, drei Ergebnisstufen wie in E1 9.5.

## 4. Offen, vor Phase B zu entscheiden

1. Parameterbereiche des Signalkatalogs: plausibel genug, oder vorher fachlich gegenprüfen
   (Hardware/Elektrode)?
2. Ob die Stimulationsartefakte später durch **Referenzmessungen an der BioComm-Platine**
   ersetzt werden (dann gehört ein Messplan dazu).
3. Wie die Ergebnisse von A4 den Umfang von Phase B beeinflussen (z. B. falls die ESOM in A4
   gegenüber einfacheren Verfahren nichts zeigt, ob B dann trotzdem in voller Breite läuft).
