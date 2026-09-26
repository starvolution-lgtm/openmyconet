# Empfangsweg für Bridges (BioComm-Dateneingang)

**Festgelegt am 26.09.2026** (Robby, Claude). Code: `omn/eingang/empfang.py`. Die Bridge-Firmware
schreibt Claude nach diesem Vertrag.

Eine Bridge empfängt Pakete der Messknoten per LoRa oder BLE, setzt sie wieder zusammen und
reicht sie **unverändert** an den Server weiter, ein Paket je Anfrage. Das Paketformat steht in
[dateneingang_format_v1.md](dateneingang_format_v1.md).

## Anfrage

```
POST https://api.openmyconet.de/api/v2/biocomm/paket
Authorization:   Bearer <Zugangsschlüssel der Bridge>
Content-Type:    application/octet-stream
Content-Length:  <Größe des Pakets>
X-OMN-Transport: LORA | BLE | USB
X-OMN-Empfangen: <Mikrosekunden seit 1970 UTC>    (optional)
X-OMN-Referenz:  <Text, höchstens 200 Zeichen>    (optional, z. B. LoRa-Rahmenzähler)

<Paket, Byte für Byte wie vom Node>
```

- **HTTPS ist Pflicht.** Die Bridge prüft das Zertifikat (Let's Encrypt, Wurzel ISRG Root X1).
- **Zugangsschlüssel:** Jede Bridge hat ihren eigenen Schlüssel (`omnb_…`, 256 Bit Zufall).
  Er wird angelegt mit `flask biocomm-schluessel <SERIENNUMMER>` und dabei **einmal** angezeigt.
  Der Server speichert nur den SHA-256-Fingerabdruck. Mit `--liste` sieht man Stand und letzte
  Nutzung, mit `--widerrufen NR` sperrt man einen Schlüssel. Die Bridge muss vorher registriert
  sein: `flask biocomm-geraet <SERIENNUMMER> --rolle BRIDGE`.
- **X-OMN-Empfangen:** Zeitpunkt, zu dem die Bridge das Paket empfangen hat. Er darf höchstens
  400 Tage zurück und höchstens 10 Minuten in der Zukunft liegen. Fehlt die Angabe, gilt die
  Ankunftszeit am Server. Die Messzeit steht ohnehin im Paket selbst.
- **SD-Import** läuft nie über eine Bridge. Die microSD sitzt am Node, deren Dateien liest
  `flask biocomm-einlesen` ein.
- Der Schlüssel bestimmt auch das Zielschema: Schlüssel aus `live` schreiben nach `live`,
  Schlüssel aus `sandbox` nach `sandbox` (zum Testen auf Staging).

## Antwort (JSON)

```json
{"status": "ACCEPTED", "grund": null, "anlieferung": 123, "batch": 456, "kette": "LINKED"}
```

| HTTP | Bedeutung | Was die Bridge tut |
|---|---|---|
| **200** | endgültige Antwort; `status` ist ACCEPTED, DUPLICATE, SCHON_EINGELESEN, WARTET, CONFLICT oder REJECTED | Paket aus der Warteschlange löschen (bei REJECTED `grund` protokollieren) |
| 400 / 411 | Kopfzeilen fehlerhaft | nicht unverändert wiederholen, Fehler melden |
| 401 | Schlüssel fehlt, ist unbekannt oder widerrufen | nicht wiederholen, Schlüssel prüfen |
| 403 | Gerät ist keine Bridge | nicht wiederholen |
| 413 | Paket größer als 4 MiB | nicht wiederholen |
| 429 | zu viele Fehlversuche von dieser Adresse (20 je Stunde, danach Sperre für den Rest der Stunde) | später erneut, mit wachsendem Abstand |
| 5xx | Serverfehler | später erneut, mit wachsendem Abstand |

**Doppelt senden schadet nie.** Geht eine Antwort verloren, schickt die Bridge das Paket einfach
noch einmal und bekommt `SCHON_EINGELESEN`. Kommt dasselbe Paket über einen anderen Weg (BLE
statt LoRa, andere Bridge), wird es als `DUPLICATE` erkannt. Pakete, deren Messlauf der
Server noch nicht kennt (LAUF_START fehlt noch), bekommen `WARTET` und werden später
automatisch verarbeitet. Auch das ist endgültig für die Bridge.

## Sicherheit und Grenzen

- Der Bridge-Schlüssel belegt nur, dass die **Bridge** echt ist. Dass ein Paket wirklich vom
  angegebenen **Node** stammt, belegt erst dessen Signatur im Anhang des Pakets (HMAC-SHA256
  mit dem eFuse-Schlüssel des ESP32-S3). Sie wird gelesen, aber **noch nicht geprüft**. Das
  gehört zur Geräte-Authentifizierung der Nodes, einem eigenen nächsten Schritt.
- Kein CSRF-Schutz (kein Browser-Formular), dafür der Schlüssel. Die Sperre nach
  Fehlversuchen zählt je Absender-IP.
- nginx lässt bis 6 MB je Anfrage durch, der Server nimmt höchstens 4 MiB je Paket an.
