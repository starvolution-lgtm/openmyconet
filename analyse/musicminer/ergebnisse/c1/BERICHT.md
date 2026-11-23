# C1: ESOM an veröffentlichten Pilzmessungen (Buffi et al. 2025), Bericht F1 + Vorhersage F2

Stand 23.11.2026 · Regeln `FREMDDATEN_BUFFI.md` (freigegeben 23.11., Nachtrag 3a freigegeben
23.11., beide vor jedem Ergebnis) · `karte-v1`, Merkmalssatz `mb1` · Commits a28832f (Regeln),
f296d28 (Nachtrag, Werkzeuge, Vorlauf).

> **MESSWERTE VON BUFFI ET AL., NICHT VON OPENMYCONET.** M. Buffi, Universität Neuchâtel,
> Mendeley Data, doi [10.17632/srkxbkh6sp.1](https://doi.org/10.17632/srkxbkh6sp.1), Lizenz
> CC BY 4.0. Arbeit: Buffi et al., iScience 28 (10), 113484 (2025), doi 10.1016/j.isci.2025.113484.
> Ausgewertet von OpenMycoNet; die Rohdaten sind nicht Teil dieses Repositorys. Die Ergebnisse sagen
> etwas über die Verfahren auf diesen Daten, nicht über Pilzbiologie.

Dateien: `f1_vorlauf.json` (C1-0), `f1.json` (F1), `f1_komponenten.json` und `f1_umatrix.png`
(Abschnitt 7, nur berichtet), `f2_vorhersage.json` (F2, Vorhersage vor Kenntnis der Zuordnung).

## 1. Ergebnis

**F1 nach den Regeln: Die ESOM findet die zwei Kanäle ohne Pilz nicht**, in keiner der drei
Prüfdateien. Gefunden hat sie nur das einfachste Verfahren, die Lautstärke (die zwei Kanäle mit
der kleinsten Streuung): in 2 von 3 Dateien genau das Paar ohne Pilz, damit „gefunden insgesamt“.
Das bestätigt den Befund des Papers (mit Pilz mehr Signal) auf einem einfachen Weg. k-Means und
HDBSCAN finden die Leerkanäle ebenfalls nicht.

**Nur berichtet, aber wichtig für die Deutung:** Die Karte selbst ordnet die Fenster der
Leerkanäle in allen drei Dateien in **zusammenhängenden Gebieten** an (Abbildung, untere Reihe),
bei Natriumazid teilweise von sichtbaren Erhebungen der U-Matrix begrenzt. Die automatische
Gruppenregel v2 (KRITERIEN Abschnitt 4) macht daraus trotzdem jedes Mal **eine** große Gruppe
(97–99 % aller Fenster) und viele kleine Inseln. Das Versagen liegt damit wahrscheinlich in der
Abgrenzung der Gruppen, nicht in der Karte. Das ist eine Beobachtung am Bild, keine Prüfung nach
Regeln, und wird nicht nachträglich zum Ergebnis.

## 2. Vorlauf C1-0 (Cycloheximid, zählt nicht)

Technik in Ordnung: Zugabelücke eindeutig bei 168,4 h, 8 × 8 639 Fenster, keine verworfen,
27 s je Kartenlauf. ESOM Seed 0: eine Gruppe, 22 Inseln, wahres Paar auf Rang 22 von 28
(J = 0,25). Nicht blind (Abschnitt 2 der Regeln).

## 3. F1: Tabelle

J = größter Jaccard-Wert zwischen den Fenstern eines Kanalpaars und einem Cluster bzw. einer
Komponente (ESOM und k-Means: Median über die Seeds 0–9). Gefunden = wahres Paar (7-8, 15-16)
allein auf Rang 1 von 28 **und** J ≥ 0,5. Bei zufälliger Lage ist ein J von etwa 0,25 zu
erwarten, weil das Paar ein Viertel aller Fenster ausmacht.

| Datei | Zugabe | ESOM J (Rang) | k-Means k=2 | k-Means k=Komponenten | HDBSCAN | Lautstärke: zwei leiseste |
|---|---|---|---|---|---|---|
| Calcimycin | 169,1 h | 0,244 (28) | 0,212 (28) | 0,163 (**1**), k = 26 | 0,243 (28), 2 Cluster | 7, 13 – nein |
| Natriumazid | 172,7 h | 0,250 (10) | 0,263 (4) | 0,158 (**1**), k = 45 | 0,259 (4), 2 Cluster | **7, 15 – ja** |
| Voriconazol* | 122,9 h | 0,247 (16) | 0,247 (11) | 0,115 (**1**), k = 51 | 0,243 (13), 4 Cluster | **7, 15 – ja** |
| **gefunden in** | | **0 von 3** | 0 von 3 | 0 von 3 | 0 von 3 | **2 von 3** |

\* Vorbehalt aus Nachtrag 3a: Die Lücke liegt nach 5,1 statt etwa 7 Tagen.

**Urteil nach Abschnitt 6: „ESOM findet sie nicht.“** Ein Widerspruch zum Paper liegt nicht vor,
weil ein Verfahren (Lautstärke) die Leerkanäle findet.

Median der Streuung je Kanal (60-s-Fenster nach Trendentfernung, in µV unter der Annahme Volt):
Leerkanäle 2,8 / 10,7 (Calcimycin), 3,3 / 4,7 (Natriumazid), 6,2 / 6,7 (Voriconazol); Pilzkanäle
8,0–17,2. Bei Calcimycin ist Leerkanal 15-16 lauter als zwei Pilzkanäle.

**Nur berichtet:**
- Kartengüte (Mediane): QE 0,81–0,87, TE 0,095–0,101; je Datei eine Gruppe und 22–49 Inseln;
  1,4–1,6 min je Lauf. Satz `mb1-L` (mit Pegel): gleiches Bild, wahres Paar auf Rang 28 / 9 / 11.
- k-Means mit vielen Clustern setzt das wahre Paar in allen drei Dateien auf Rang 1, aber mit
  J von nur 0,12–0,16: Es gibt Cluster, die überwiegend aus Leerkanal-Fenstern bestehen, aber
  jeweils nur einen kleinen Teil davon enthalten.
- Die Regel „Rang 1 **und** J ≥ 0,5“ verlangt, dass ein Verfahren die Leerkanäle als eine
  zusammenhängende Gruppe ausweist. Das leistet hier keines der Clusterverfahren.

## 4. Wiederkehrende Komponenten (Abschnitt 7, Hypothesen, kein Befund)

Komponenten der Seed-0-Karte außer der größten, in ≥ 5 von 10 Seeds wiedergefunden (`f1_komponenten.json`):

- **Calcimycin:** 8 Inseln (12–82 Fenster), bei **allen** überwiegt ein Leerkanal (7-8 oder 15-16,
  31–65 %).
- **Natriumazid:** 11 Inseln (16–107 Fenster). Zwei sind **kanaltypisch** (≥ 80 % aus einem Kanal):
  Kanal 3-4, 20 und 24 Fenster, Tageszeit etwa 2–3 Uhr UTC.
- **Voriconazol:** 14 Inseln (12–252 Fenster), eine kanaltypisch (Kanal 13-14, 36 Fenster,
  etwa 4–6 Uhr UTC).
- Die übrigen Inseln liegen überwiegend zwischen etwa 6 und 18 Uhr UTC (Neuchâtel: UTC+1).
  Ob das mit Tätigkeit im Labor zusammenhängt, lässt sich aus den Daten nicht sagen.

## 5. F2: Vorhersage (vor Kenntnis der wahren Zuordnung)

**Festgeschrieben mit diesem Commit, bevor die wahre Zuordnung beschafft wird.** Kanäle mit
ihrer ersten Elektrode benannt (1 = Kanal 1-2 usw.); 7 und 15 sind die Leerkanäle. „Stoff“ =
vorhergesagte Hälfte mit Stoff, die andere bekam nur das Lösungsmittel.

| Datei | ESOM (Seeds mit dieser Vorhersage) | Merkmalsänderung | Lautstärke |
|---|---|---|---|
| Calcimycin | Stoff 3, 9, 11, 15 (5/10) | Stoff 1, 9, 11, 15 | Stoff 3, 5, 9, 7 |
| Natriumazid | **Gleichstand** 3/10: Stoff 1, 5, 9, 15 **oder** 1, 11, 13, 7 | Stoff 3, 5, 9, 15 | Stoff 9, 11, 13, 7 |
| Voriconazol* | **Gleichstand** 5/10: Stoff 9, 11, 13, 15 **oder** 9, 11, 13, 7 | Stoff 1, 3, 11, 7 | Stoff 1, 3, 9, 7 |
| *Cycloheximid (Vorlauf, zählt nicht)* | *Stoff 1, 5, 13, 7 (9/10)* | *Stoff 1, 5, 13, 7* | *Stoff 1, 5, 13, 15* |

\* Vorbehalt Nachtrag 3a; „nachher“ nur 45,7 h.

**Was man schon jetzt sagen kann, ohne die Wahrheit zu kennen:**
- Die Vorhersagen sind **schwach**. Bei der ESOM trennt die gewählte Aufteilung sich von der
  zweitbesten meist nur um 0,001–0,04 (Kosinus-Wert), und die Seeds sind sich nur bei
  Cycloheximid einig (9/10). Bei Natriumazid und Voriconazol gibt es Gleichstände; dafür
  enthielten die Regeln keine Bestimmung (Abschnitt 6, Vorschlag Nachtrag 6b).
- Die drei Verfahren stimmen in den Prüfdateien nirgends überein.
- Nur bei **Cycloheximid** (Vorlauf) zeigen alle drei dasselbe Bild: Die Kanäle 1, 5 und 13
  werden nach der Zugabe deutlich leiser (log-Streuung −1,29 / −1,36 / −0,87, die übrigen
  Pilzkanäle −0,08 bis −0,56). Das passt zum Paper (Cycloheximid dämpft das Signal) und ist ein
  klarer Kandidat. Die Datei zählt nach den Regeln nicht, die Vorhersage steht trotzdem fest.
- Bei Calcimycin wählen 7 von 10 Seeds dieselbe Aufteilung (3, 9, 11 + 15 gegen 1, 5, 13 + 7),
  nur die Seite schwankt (5 gegen 2).

Alle Stimmen je Seed stehen in `f2_vorhersage.json`.

## 6. Abweichungen von den Regeln

- **Nachtrag 3a** (Zugabelücke), freigegeben vor jedem Ergebnis: Die ursprüngliche Regel
  (60–90 h nach der Lücke) fand in keiner Prüfdatei eine Lücke.
- **Benennung k-Means:** Im Werkzeug heißt das Verfahren je Datei nach seinem k (`kmeans_k26`,
  `kmeans_k45`, `kmeans_k51`), die Gesamtzählung in `f1.json` erfasst deshalb nur `kmeans_k26`.
  Das Ergebnis ändert sich nicht (in keiner Datei gefunden); die Tabelle oben zählt richtig.
- **Gleichstand in F2** (Natriumazid, Voriconazol): Die Regeln sagen nicht, was dann gilt. Das
  Werkzeug hat die zuerst gezählte Vorhersage als „Mehrheit“ eingetragen; alle gleichauf liegenden
  stehen zusätzlich in `f2_vorhersage.json`. Vorschlag Nachtrag 6b (noch nicht freigegeben,
  festzulegen **vor** Kenntnis der Wahrheit): Bei Gleichstand zählt die ESOM-Vorhersage dieser
  Datei als **nicht richtig**.

## 7. Was das heißt

- Auf echten Pilzmessungen trennt die ESOM mit unserer automatischen Gruppenregel Kanäle mit und
  ohne Pilz nicht. Ein einfaches Lautstärkemaß tut es in 2 von 3 Fällen. Das passt zu A4 (kein
  ESOM-Mehrwert auf Simulationsdaten).
- Die Karte zeigt die Leerkanäle aber als zusammenhängende Gebiete. Ob eine andere Abgrenzung
  der Gruppen, etwa die der Entwickler, sie trennt, ist eine offene, gezielte Frage an Boon
  Elschenbroich (Inselabgrenzung). Eine Prüfung dazu wäre ein neuer Schritt mit eigenen Regeln.
