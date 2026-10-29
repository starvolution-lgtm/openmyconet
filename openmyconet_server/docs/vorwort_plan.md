# Persönliches Vorwort des Initiators – Umsetzungsplan

Stand: 29.10.2026 · Entwurf von Cody, Entscheidungen V1–V5 von Robby eingearbeitet · noch nichts gebaut

## 1. Ziel

Jede Person, die in den wissenschaftlichen Austausch aufgenommen wird (fachlicher Austausch auf Einladung
und Themenräume), liest vorher Robbys persönliches Vorwort „Ein paar persönliche Worte“ – ganzseitig, nicht
zusammengeklappt – und bestätigt die **Kenntnisnahme**. Keine Zustimmung zur Haltung, kein Teil der
Nutzungsregeln oder des Datenschutzes („Einladung zur Zusammenarbeit, kein Glaubensbekenntnis“).
Danach ist das Vorwort jederzeit über einen festen Link wieder lesbar.

**Zusätzlich öffentlich** (Robby 29.10.2026): dieselbe Seite, dieselben fünf Sprachfassungen, mit Porträt,
erreichbar über den Footer-Link **„Über den Initiator“** auf www.openmyconet.de – dort ohne Haken und ohne
Kenntnisnahme. Ein öffentlicher Aufruf zählt **nie** als Kenntnisnahme.

## 2. Der Text

- **Maßgeblich ist die deutsche Fassung**, wörtlich wie von Robby am 29.10.2026 geschickt, mit dem
  ergänzten Wort „… und welchen Beitrag *er* geleistet hat“ (V1).
- **Übersetzungen en / nl / fr / es:** von Cody möglichst wörtlich und schlicht übersetzt (nicht
  „verschönert“), **Robby prüft sie** (V2). Keine automatische Übersetzung beim Aufruf.
  Unter jeder Übersetzung: „Übersetzung – Original (Deutsch) anzeigen“ (aufklappbar).
- Gespeichert im Repo als `omn/vorwort.json` (Fassung, Text je Sprache, Unterschrift) – wie die Rechtstexte,
  also nur über Git/Deploy änderbar, nicht im Admin.

## 3. Kenntnisnahme

- **Kein Haken** (Robby 29.10.2026: „man muss doch eh auf weiter klicken“): ein Knopf **„Gelesen – weiter“**,
  darüber der Satz, dass keine Zustimmung zu einer Haltung gefordert ist, nur die Kenntnisnahme. Der Klick
  ist die Kenntnisnahme.
- Gespeichert je Konto: **Fassung und Zeitpunkt** (neue kleine Tabelle `vorwort_kenntnis`, eine Zeile je
  Konto, timestamptz). Unabhängig von Austausch und Themenräumen, damit es pro Person nur einmal nötig ist.
- **Neue Fassung** (`VORWORT_FASSUNG` erhöhen) nur bei *wesentlicher* inhaltlicher Änderung → alle sehen das
  Vorwort beim nächsten Besuch einmal neu. Tippfehler/Übersetzungskorrekturen ohne neue Fassung.

## 4. Wo es im Ablauf erscheint

Eine Prüfung „Vorwort in der aktuellen Fassung zur Kenntnis genommen?“ an genau den Eingängen in den
wissenschaftlichen Austausch – fehlt sie, kommt erst die Vorwort-Seite, danach geht es zum ursprünglichen Ziel:

| Eingang | Ablauf |
|---|---|
| Einladung annehmen | Einladungslink → Bestätigungscode → **Vorwort** → Start-Themenraum bzw. Austausch |
| Themenräume (`/themen…`) | **Vorwort** → (beim ersten Mal) Anzeigename + Nutzungsregeln → Themenraum |
| Fachlicher Austausch (`/austausch`) | **Vorwort** → Austausch |
| Login als Fachkontakt | Ziel nach dem Login → dort greift die Prüfung |

- **Bereits Aufgenommene** (Robby, Lazare, …) sehen es einmalig beim nächsten Besuch – ihre Aufnahme wird
  nicht infrage gestellt.
- **Nicht betroffen:** reine Messknoten-/Kooperationsbereiche, Datenlabor, Admin, MCC.
- Reihenfolge Vorwort **vor** den Nutzungsregeln: erst der Mensch, dann die Regeln.

## 5. Eine Seite, zwei Zugänge

- **Eine** Seite `/ueber-den-initiator` (Website-Layout, Sprache wie die übrige Website, `?lang=…`),
  ein Text aus `omn/vorwort.json`, ein Porträt. Keine getrennte öffentliche Textversion.
- **Öffentlich:** Footer-Link **„Über den Initiator“** auf allen Website-Seiten (5 Sprachen). Nur Text +
  Porträt + Unterschrift, kein Haken. Neue öffentliche Seite → Eintrag in `omn/llms.py` (`SEITEN_GRUPPEN`)
  und in die Listen des Frontend-Audits (Projektregel).
- **Im Austauschbereich:** Link **„Ein paar persönliche Worte“** (V4) in den Themenräumen (Leiste oben) und im
  fachlichen Austausch; führt auf dieselbe Seite.
- **Kenntnisnahme nur im Ablauf:** Die Eingangs-Prüfung (Abschnitt 4) leitet auf dieselbe Seite mit dem
  Zusatz „Kenntnisnahme“ weiter. Nur dann – angemeldet, berechtigt und noch nicht bestätigt – erscheinen
  Haken und „Weiter“; gespeichert wird ausschließlich beim Absenden dieses Formulars (POST, CSRF), nie durch
  bloßes Aufrufen. Wer schon bestätigt hat, sieht unten klein „Zur Kenntnis genommen am …“.
- Gestaltung: ruhige Lesebreite, Porträt klein und rund neben der Unterschrift (V5).

## 6. Admin

- Auf der Detailseite eines Austauschs: „Vorwort zur Kenntnis genommen: Fassung … am …“ bzw. „noch nicht“.
- Keine Erinnerungs-Mails (die Seite erscheint ohnehin beim nächsten Besuch).

## 7. Datenschutz (kleine Ergänzung, zur Freigabe)

Die öffentliche Seite verarbeitet keine Daten der Besucher (nur Robbys eigene Angaben + Foto, seine
Entscheidung). Für die Kenntnisnahme:

Gespeichert werden nur Fassung und Zeitpunkt der Kenntnisnahme. Dafür je ein Halbsatz in Abschnitt 9
(fachlicher Austausch) und 10 (Themenräume), sinngemäß: „…sowie Zeitpunkt und Fassung, zu der Sie das
persönliche Vorwort des Initiators zur Kenntnis genommen haben“ (Rechtsgrundlage wie die übrige Nutzung,
Art. 6 Abs. 1 lit. b; gelöscht mit dem Konto). 5 Sprachen, als ENTWURF bis zu Robbys Freigabe; bis dahin
Schalter `VORWORT_AKTIV` auf Prod aus (wie bei Übersetzung und Benachrichtigungen).

## 8. Tests

Vorwort erscheint vor Austausch/Themenräumen und nach der Einladung, nur einmal je Fassung, neue Fassung →
erneut; Haken Pflicht; Weiterleitung zum ursprünglichen Ziel (nur interne Ziele); Schalter aus → keine
Prüfung; Seite ohne Login nicht erreichbar; Admin-Anzeige; alle 5 Sprachen vorhanden.

## 9. Entscheidungen (Robby, 29.10.2026)

- **V1:** fehlendes „er“ ergänzen – ja.
- **V2:** Robby prüft die Übersetzungen.
- **V3:** zusätzlich öffentlich, Footer-Link „Über den Initiator“, dieselbe Seite und Sprachfassungen,
  ohne Kenntnisnahme; öffentlicher Aufruf zählt nie als Kenntnisnahme.
- **V4:** Link im Austauschbereich „Ein paar persönliche Worte“.
- **V5:** Porträt (Robbys Foto, verkleinert als WebP ins Git, Alt-Text „Robert Jank“); kein Alter.

## 10. Reihenfolge

1. ✅ Robby: V1–V5 entschieden (29.10.2026).
2. Cody: Übersetzungen → Robby prüft.
3. Cody: Umsetzung (Schalter auf Prod aus), Vorher-/Nachher-Bilder, Datenschutz-Halbsatz als Entwurf.
4. Robby: Freigabe → Schalter an, Deploy.
