# Hardware V3.6 (fertigungsreif)

Finaler Stand der beiden Platinen **COMBO NODE** (Messknoten) und **BLE BRIDGE**,
Version 3.6 (KiCad-Projekte, Fertigungsdateien, Prüfberichte). Abgelegt am 26.10.2026.

Quelle: Paket `OpenMyCoNet_Project_Completed_Package_Finale_Ver3.6.zip`
(SHA-256 `373a08654455d4fddd7a3f6c591d7695429d6e759cf8f633c875d926a3661b07`),
unverändert entpackt. Weggelassen wurde nur der interne KiCad-Verlauf
`BLE BRIDGE BOARD/BLE BRIDGE PCB/.history/` (ein eingebettetes Git-Verzeichnis vom Juni 2026).

## Für die Bestellung

**Diese beiden BOMs verwenden**, nicht die `bom.csv` in den Unterordnern:

| Datei | Unterschied zur `bom.csv` im Paket |
|---|---|
| `COMBO_NODE_V3.6_bom_korrigiert.csv` | 100 nF (0603): Menge 20 statt 19 (C51 war nicht mitgezählt) |
| `BLEBRIDGE_V3.6_bom_korrigiert.csv` | 10 kΩ (0603): Menge 10 statt 11 (nach Wegfall des zweiten R13) |

Sonst sind die Dateien Zeile für Zeile gleich. Gegengeprüft (26.10.2026): Jede Zeile hat
so viele Bezeichner wie ihre Menge (Node 179, Bridge 99 Bauteile), BOM und
Bestückungsliste (`positions.csv`) enthalten auf beiden Platinen genau dieselben Bauteile.

Gerber und Bohrdaten: `COMBO NODE BOARD/PRODUCTION FILES/production/COMBO_NODE_3.6.zip`
und `BLE BRIDGE BOARD/PRODUCTION FILES/production/BLEBRIDGE_BOARD.zip`.

## Änderungen gegenüber dem Stand vom 23.10.2026

Laut Prüfung (Vergleich der Verdrahtung Pin für Pin, BOM, Bestückungsliste, Layout und Gerber):

- **Node, Puffer:** neuer Baustein U19 (OPA333, SOT-23-5, ca. 17 µA Ruhestrom) als
  Spannungsfolger: Eingang am Teiler R43/R44 (C34), Ausgang über R62 an den Referenzknoten,
  Abblockkondensator C51. U13B arbeitet nur noch für den EC-Empfang, die EC-Messung wird
  nicht mehr verfälscht. In der Netzliste nachvollzogen: U19 Pin 5 an 3.3VA, Pin 2 an GND,
  Pin 3 (+IN) am Teiler, Pin 1 (OUT) und Pin 4 (−IN) verbunden und an R62.
- **Bridge, R13:** nur noch ein R13 (1,18 kΩ an ILIM des BQ24075). Der zweite Widerstand
  an SYSOFF ist entfallen; er zog in der Stellung „Aus“ dauerhaft ca. 0,4 mA aus dem Akku.
  SYSOFF legt der Schalter S1 fest.
- Prüfbericht V3.6: `GUIDE/OpenMycoNet_Architectural_Evolution_Design_Verification_Report_V3.6.docx`.

## Wichtig: TH1 und der Akku

TH1 (10-kΩ-NTC) ist auf **beiden** Platinen nicht bestückt (fehlt in BOM und
Bestückungsliste, steht im Schaltplan aber noch als bestückt, in `designators.csv`
ebenfalls noch aufgeführt). TH1 liegt am TS-Pin des Ladereglers BQ24075 (U4, Pin 1),
an derselben Leitung wie **Pin 2 des Akkusteckers J2** (Belegung +BATT / NTC / GND).

Ohne TH1 misst der Laderegler die Temperatur über den Akkupack. Deshalb:

- **Akkus müssen 3-adrig sein, mit 10-kΩ-NTC (B ≈ 3435) an der mittleren Ader.**
- Ein Akku mit nur 2 Adern lässt TS offen: Der BQ24075 sieht einen Temperaturfehler und
  **lädt nicht**. Dann TH1 bzw. einen festen 10-kΩ-Widerstand doch bestücken.
- Firmware: Die Node misst keine eigene Platinentemperatur. Die Ausgänge CHG und PGOOD
  des BQ24075 hängen auf beiden Platinen nur an Pull-ups (R15/R16), **nicht am ESP32**
  (Netzliste geprüft 27.10.2026). Die Firmware sieht nur die Laderate des MAX17048
  (positiv = lädt) und meldet „lädt“ bzw. „lädt nicht“ im Protokoll. Für eine spätere
  Revision: CHG an einen freien Eingang führen.

## BQ24075: zwei LCSC-Nummern (geklärt)

Der BQ24075 (U4) hat in den beiden BOMs verschiedene LCSC-Nummern: Node `C15464`, Bridge
`C2865459`. Laut Richard (27.10.2026) beabsichtigt: Die Suffixe RGTR und RGTT unterscheiden
nur die Verpackung (Rollengröße), Footprint und Pads sind gleich. Beide Nummern sind für ihre
Platine richtig, die BOMs bleiben so.

## Pin-Merkblatt Firmware (Watchdog, Akkualarm)

`BioComm_Bridge_V3.6_Pinbelegung_Firmware.md` (Stand 27.10.2026), unverändert abgelegt.
Gegen die Netzlisten V3.6 geprüft (27.10.2026), alle Angaben stimmen
(Modul-Pin → GPIO nach Datenblatt ESP32-S3-WROOM-1):

| Signal | Node | Bridge | Netz in der Netzliste |
|---|---|---|---|
| BATT_ALERT | GPIO21 (U6-23) | GPIO47 (U6-24) | MAX17048 U5-5 (ALRT), Pull-up Node R20 / Bridge R32 (10 kΩ), Bridge zusätzlich D3 |
| WCD_SLEEP | GPIO47 (U6-24) | GPIO48 (U6-25) | TPS3851 U7-5 (SET1), Pull-down Node R55 / Bridge R27 (100 kΩ) |
| RST_WDI | GPIO4 (U6-4) | GPIO21 (U6-23) | TPS3851 U7-6 (WDI) |
| LED_ON | – | GPIO41 (U6-34) | über R23 (1 kΩ) an D7 |

Ergänzung für die **Node-Firmware**: Auch die Node hat den TPS3851H33 mit 100 nF an CWD
(C20). Ist ihr Watchdog über GPIO47 eingeschaltet, gilt dort dasselbe Zeitfenster von
rund 323 ms (GPIO4 etwa alle 300 ms umschalten oder vorher abschalten).

## Inhalt

| Ordner | Inhalt |
|---|---|
| `COMBO NODE BOARD/COMBO_NODE/` | KiCad-Projekt Node (Schaltplan-Blätter, Layout) |
| `COMBO NODE BOARD/PRODUCTION FILES/` | Gerber-Zip, BOM, Bestückungsliste, Netzliste (IPC), interaktive BOM, Kaufhinweise für Ersatzteile |
| `COMBO NODE BOARD/REPORTATION/` | Schaltplan-PDF, ERC/DRC-Ergebnisse, Unterlagen zum Watchdog TPS3851 |
| `COMBO NODE BOARD/DOCUMENTATION/` | Bilder der Lagen und Ansichten |
| `BLE BRIDGE BOARD/…` | dasselbe für die Bridge |
| `GUIDE/` | ERC/DRC-Leitfäden beider Platinen, Prüfbericht V3.6 |

Nicht Teil des Deploys: Der Server bekommt nur `openmyconet_server/`.
