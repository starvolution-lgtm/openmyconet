# Öffnung der Themenräume für alle Registrierten – Unterlage zur Freigabe

Stand: 14.11.2026 · ENTWURF, noch nicht umgesetzt. Maßgeblich ist die deutsche Fassung; en/nl/fr/es
werden nach der Freigabe nachgezogen. Hinweis: Zusammenstellung mit Anmerkungen, **keine Rechtsberatung**.

Ziel (Robby, 14.11.2026): Die Themenräume öffnen sich für Fragen rund um gesunden Boden, Bakterien und
Bodenleben, auch für Praktiker aus Garten, Landwirtschaft und Forst. Gründe: Sichtbarkeit und Förderung
(Bodengesundheit ist ein EU-Schwerpunkt), Praxiswissen als eigener Beitrag (Citizen Science), Brücke zu
BioComm (künftige Knotenbetreiber).

## 1. Was schon umgesetzt ist (ohne rechtliche Wirkung)

- Migration `f3b7d91a2c64` (Commit `c621d4a`): Gebiet **„Bodenleben & Bodengesundheit“** (sichtbar, die
  Fachkontakte können es schon beleben) und **„Fragen aus der Praxis“** (ausgeblendet bis zur Öffnung).
  Beide auf Deutsch mit Handübersetzungen in en/nl/fr/es.

## 2. Was sich mit der Öffnung ändert

| Punkt | bisher | nach der Öffnung |
|---|---|---|
| Teilnehmerkreis (`THEMEN_KREIS`) | `fachkontakte` (aktiver Austausch) | `alle` (jedes bestätigte Konto) – Standard in `omn/config.py`, per `.env` zurückstellbar |
| Nutzungsregeln | Fassung 2026-10-26 | neue Fassung (Abschnitt 3); alle stimmen beim nächsten Besuch neu zu |
| Datenschutzerklärung Abschnitt 10 | „derzeit eingeladene Personen, künftig …“ | Abschnitt 4 |
| Gebiet „Fragen aus der Praxis“ | ausgeblendet | in `/admin/themen` einblenden |
| Hinweis ohne Zugang (`themen_kein_zugang`) | „nur auf Einladung“ | „nur mit bestätigtem Konto“ |

Unverändert: nicht öffentlich im Netz (nur angemeldete Teilnehmende lesen), keine Rolle/Förderung als
Voraussetzung, CC BY 4.0, „Wissen bleibt“, automatische Übersetzung mit Widerspruch, Benachrichtigungen.

## 3. Nutzungsregeln, neue Fassung (nur der erste Absatz ändert sich)

Bisher:
> Sachlich und respektvoll diskutieren. Keine personenbezogenen Daten Dritter, keine vertraulichen Inhalte aus Einzelgesprächen, keine Werbung. Beiträge sind für alle Teilnehmenden der Themenräume sichtbar; der Kreis der Teilnehmenden kann künftig auf alle registrierten Mitglieder erweitert werden – das wird vorher angekündigt.

Neu:
> Sachlich und respektvoll diskutieren. Keine personenbezogenen Daten Dritter, keine vertraulichen Inhalte aus Einzelgesprächen, keine Werbung. **Keine Bestimmung von Pilzen zum Verzehr und keine Ratschläge zu Gesundheit oder Behandlung; Beiträge ersetzen keine fachkundige Beratung.** Beiträge sind für alle Teilnehmenden der Themenräume sichtbar. **Teilnehmen können alle registrierten Mitglieder mit bestätigter E-Mail-Adresse.**

## 4. Datenschutzerklärung Abschnitt 10, erster Absatz (nur ein Satz ändert sich)

Bisher:
> … Teilnehmen können derzeit eingeladene Personen, künftig voraussichtlich alle registrierten Mitglieder; eine solche Erweiterung kündigen wir vorher an. …

Neu:
> … Teilnehmen können alle registrierten Mitglieder mit bestätigter E-Mail-Adresse; die Themenräume sind nicht öffentlich, Inhalte sehen nur Teilnehmende. …

Dazu: `stand` aller fünf Sprachen auf das Freigabedatum.

## 5. Interessenabwägung – Wiedervorlage (Kontrollzentrum `03_Website_Backend/Interessenabwaegung_Themenraeume.md`)

Dort ist „bei Öffnung für alle Mitglieder“ als Wiedervorlage notiert. Vorschlag für eine Ergänzung (Abschnitt 8):

> **Ergänzung Öffnung für alle Registrierten.** Der Kreis der Personen, die Beiträge nach einer Kontolöschung
> (ohne Namen) und automatisch übersetzte Texte sehen, wird größer, bleibt aber auf angemeldete Mitglieder
> mit bestätigter Adresse beschränkt; die Inhalte sind nicht öffentlich. Wer bereits Beiträge geschrieben hat,
> wird vor der Öffnung per Mail bzw. beim nächsten Besuch (neue Fassung der Nutzungsregeln) informiert und
> kann eigene Beiträge vorher entfernen. Die übrigen Schutzmaßnahmen (Abschnitte 5 und 7) gelten unverändert.
> **Ergebnis:** Die Abwägung bleibt bestehen; das Interesse an einer breiter getragenen Diskussion über
> Bodenleben überwiegt bei Beschränkung auf Mitglieder und vorheriger Information.

## 6. Entscheidungen

- **Ö1 Vorwort für alle Neuen?** Bisher sieht jede Person vor dem ersten Betreten der Themenräume einmal
  „Ein paar persönliche Worte“ (Knopf „Gelesen – weiter“). (a) so lassen – auch Praktiker lernen dich so
  kennen; (b) nur für Eingeladene. **Vorschlag: (a).**
- **Ö2 Vorher informieren?** Die 5 bisherigen Teilnehmenden schrieben unter der Zusage „wird vorher
  angekündigt“. (a) kurze persönliche Nachricht/Mail an sie, einige Tage vor der Öffnung; (b) nur die
  Rund-Mail am Tag der Öffnung. **Vorschlag: (a)** – so ist die Zusage sauber eingelöst.
- **Ö3 Markierung „beantwortet“** im Gebiet „Fragen aus der Praxis“: später, wenn dort Fragen eingehen.
- **Ö4 Standort in Handyfotos.** Praktiker werden Fotos von Boden und Pilzen anhängen (erlaubt: png/jpg/
  webp/gif, 5 MB). Handyfotos enthalten oft GPS-Koordinaten in den Metadaten (EXIF) – bei einem Hof oder
  Garten praktisch die Wohnadresse, sichtbar für alle, die die Datei herunterladen. (a) Metadaten beim
  Hochladen automatisch entfernen (Pillow ist schon installiert; betrifft auch den Austausch); (b) nur ein
  Hinweis am Formular. **Vorschlag: (a)**, vor der Öffnung umsetzen.

## 7. Ablauf der Öffnung

1. Freigabe dieser Unterlage (Abschnitte 3–6).
2. Ich setze um: Regeln (5 Sprachen, neue `REGELN_FASSUNG`), Datenschutz Abschnitt 10 + Stand, ggf. Ö4,
   `THEMEN_KREIS` Standard `alle`, Hinweistext, Tests. Erst Staging, du prüfst, dann Prod.
3. Vorab (Ö2): die bisherigen Teilnehmenden informieren.
4. Nach dem Prod-Deploy: „Fragen aus der Praxis“ in `/admin/themen` einblenden, Eröffnungsbeiträge einstellen
   (Entwürfe: `docs/themen_oeffnung_texte.md`).
5. Rund-Mail an alle Registrierten mit Einwilligung (Entwurf ebenda).
6. Interessenabwägung Abschnitt 8 unterschreiben.
