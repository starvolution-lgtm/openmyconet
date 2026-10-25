# Fachlicher Austausch – Unterlage zur rechtlichen Prüfung (Phase 1)

Stand: 25.10.2026 · Code-Stand `2603039` (Staging) · Prod noch **nicht** deployt
Maßgeblich ist die deutsche Fassung. Die Übersetzungen (en/nl/fr/es) folgen erst, wenn der deutsche
Text freigegeben ist, angepasst wird nur dort, wo sich etwas ändert.

Hinweis: Das ist eine Zusammenstellung mit meinen Anmerkungen, **keine Rechtsberatung**. Die
Punkte unter „Zu prüfen“ sind Stellen, die ich bei einer Durchsicht besonders ansehen würde.

---

## 1. Was verarbeitet wird (Kurzüberblick)

| Phase | Daten | Wer sieht sie | Rechtsgrundlage (Entwurf) |
|---|---|---|---|
| Vorbereitung durch Robby | Name, E-Mail, Institution (optional), Sprache, Anrede, Titel, Themenüberblick, persönlicher Einleitungssatz | Team; Titel/Themenüberblick später auch die Person | Art. 6 Abs. 1 lit. f |
| Vorbereitung, nur intern | LinkedIn-Profil-Link, Datum Gesprächsbeginn, eigene Zusammenfassung der Vorgeschichte | nur Team | Art. 6 Abs. 1 lit. f |
| Einladung | Hash des Einladungslinks, Zeitpunkte | – | Art. 6 Abs. 1 lit. f |
| Annahme | Hash des Bestätigungscodes, Fehlversuche, Zeitpunkt der Annahme; Konto (Name, E-Mail, Sprache) | Team | Art. 6 Abs. 1 lit. b |
| Austausch | Aufgaben, Kommentare, Dateien (max. 5 MB), Zeitpunkte, Benachrichtigungsmails | Person + Team | Art. 6 Abs. 1 lit. b |

Keine neuen Auftragsverarbeiter: Server Hetzner, Mailversand ALL-INKL (beide mit AVV). Keine
KI/Anthropic in Phase 1. Kein Newsletter, keine Rolle, keine Zahlung.

## 2. Fristen (so umgesetzt in `omn/aufbewahrung.py`, täglicher Lauf)

| | Regel | Wirkung |
|---|---|---|
| F1 | Einladung nicht angenommen | 2 Jahre nach der (letzten) Einladung (wie Kontaktaufnahme, Abschnitt 8): alles gelöscht, inkl. Dateien |
| F1a | Nur vorbereitet, nie verschickt | 1 Monat nach dem Anlegen: alles gelöscht; nach 3 Wochen Erinnerungsmail an den Admin |
| F2 | 12 Monate ohne Aktivität | nur Markierung „Prüfen“ im Admin, **keine** Sperre/Löschung |
| F3 | LinkedIn-Link, Gesprächsbeginn, Vorgeschichte | 24 Monate nach der letzten Aktivität geleert |
| F4 | Austausch beendet oder gesperrt | 6 Monate nach dem Statuswechsel: alles gelöscht, inkl. Dateien |
| F5 | Löschwunsch | sofort (Admin-Knopf), optional mit Konto |
| Sperre | „berechtigter Aufbewahrungsgrund“ | setzt F1–F4 bis zu einem Datum aus, nur mit Grund, im Audit-Log |
| Backups | tägliche verschlüsselte Sicherung | Gelöschtes verschwindet mit dem regulären Ablauf der Sicherungen (steht schon in Abschnitt 16) |

## 3. Die Texte (deutsch, wörtlich)

### 3.1 Datenschutzerklärung, neuer Abschnitt 9 „Fachlicher Austausch auf Einladung“
(in `omn/rechtstexte.json` als ENTWURF vermerkt; die bisherigen Abschnitte 9–18 sind jetzt 10–19)

> Setzen wir ein fachliches Gespräch, das zum Beispiel über LinkedIn oder per E-Mail begonnen hat, in einem geschützten Austauschbereich fort, laden wir Sie per E-Mail dazu ein. Dafür speichern wir Ihren Namen, Ihre E-Mail-Adresse, gegebenenfalls Ihre Institution, die gewünschte Sprache und Anrede, einen Titel und einen kurzen Themenüberblick sowie – nur für unser Team sichtbar – gegebenenfalls einen Link zu Ihrem öffentlichen Profil, das Datum des Gesprächsbeginns und eine eigene kurze Zusammenfassung des bisherigen Gesprächs. Fremde Texte, etwa Nachrichten aus LinkedIn, übernehmen wir nicht. Die Angaben stammen aus unserem bisherigen Kontakt mit Ihnen. Rechtsgrundlage ist Art. 6 Abs. 1 lit. f DSGVO; unser berechtigtes Interesse ist die Fortführung des fachlichen Austauschs. Die Einladung enthält diese Hinweise ebenfalls.
>
> Nehmen Sie die Einladung an, bestätigen Sie das mit einem Code, den wir an Ihre E-Mail-Adresse senden. Wir legen dann ein Konto an oder verknüpfen Ihr bestehendes Konto, ohne dessen Rolle oder Einstellungen zu ändern; Sie erhalten dadurch keinen Newsletter. Im Austauschbereich speichern wir die Aufgaben, Kommentare und Dateien, die Sie oder wir dort teilen; sie sind nur für Sie und das OpenMycoNet-Team sichtbar. Über neue Einträge informieren wir Sie per E-Mail. Rechtsgrundlage ist Art. 6 Abs. 1 lit. b DSGVO (Nutzung des Austauschbereichs). Die Teilnahme ist kostenlos und unabhängig von jeder finanziellen Unterstützung.
>
> Speicherdauer: Nehmen Sie eine Einladung nicht an, löschen wir die Angaben 6 Monate nach der (letzten) Einladung; nur vorbereitete, nie verschickte Einladungen 6 Monate nach dem Anlegen. Profil-Link, Gesprächsbeginn und Zusammenfassung löschen wir 24 Monate nach der letzten Aktivität im Austausch. Einen beendeten oder gesperrten Austauschbereich löschen wir samt aller Inhalte und Dateien 6 Monate danach. In Einzelfällen, etwa bei gesetzlichen Nachweispflichten, können wir die Löschung befristet aussetzen. Sie können jederzeit widersprechen oder die Löschung verlangen (kontakt@openmyconet.de); wir löschen dann sofort, unabhängig von diesen Fristen.

### 3.2 Einladungsmail (förmlich) – Datenschutzhinweis
> Datenschutz: Für diese Einladung haben wir Ihren Namen, Ihre E-Mail-Adresse und gegebenenfalls Ihre Institution gespeichert, außerdem eine eigene kurze Notiz zu unserem bisherigen Gespräch (z. B. über LinkedIn oder E-Mail). Rechtsgrundlage ist unser berechtigtes Interesse an der Fortführung des Gesprächs (Art. 6 Abs. 1 lit. f DSGVO). Wenn Sie die Einladung nicht annehmen, löschen wir diese Angaben spätestens nach 6 Monaten. Sie können jederzeit widersprechen oder die Löschung verlangen: kontakt@openmyconet.de. Einzelheiten, Verantwortlicher und Ihre Rechte: [Link auf Abschnitt 9]

Weitere Sätze der Mail: „Der Austausch ist unabhängig von jeder finanziellen Unterstützung. Es gibt
keine Erwartung und keine Gegenleistung. Die Teilnahme ist kostenlos und unverbindlich.“ · „Der Link
ist 14 Tage gültig. Nach dem Öffnen bestätigen Sie die Annahme mit einem Code, den wir an diese
Adresse senden.“ · „Wenn Sie nicht teilnehmen möchten, müssen Sie nichts tun.“

### 3.3 Annahmeseite (vor dem Klick auf „Einladung annehmen“)
> Datenschutz: Mit der Annahme legen wir für Sie ein Konto bei OpenMycoNet an bzw. verknüpfen Ihr bestehendes Konto. Gespeichert werden Name, E-Mail-Adresse und die Inhalte, die Sie im Austausch teilen; sie sind nur für Sie und das OpenMycoNet-Team sichtbar. Rechtsgrundlage ist die Nutzung des Austauschbereichs (Art. 6 Abs. 1 lit. b DSGVO). Sie erhalten keinen Newsletter. Einzelheiten und Ihre Rechte: [Datenschutzerklärung]

---

## 4. Zu prüfen – meine Anmerkungen

1. **Frist für die Information nach Art. 14 Abs. 3 lit. a (ein Monat).** Die Information steht in
   der Einladungsmail, also bei der ersten Mitteilung (lit. b) – das passt, solange die Einladung
   zeitnah verschickt wird. Ein nur *vorbereiteter* Eintrag kann aber bis zu 6 Monate liegen
   (F1a), ohne dass die Person informiert wurde. Zu entscheiden: Ist das in Ordnung (z. B. weil
   Robby ohnehin binnen Tagen einlädt), oder soll F1a auf **1 Monat** verkürzt werden bzw. der Admin
   ab einem Monat einen Hinweis „noch nicht eingeladen“ bekommen?
2. **Kategorien in der Einladungsmail vollständig?** Die Mail nennt Name, E-Mail, Institution und
   „eine eigene kurze Notiz“. Abschnitt 9 nennt zusätzlich Profil-Link, Datum des Gesprächsbeginns,
   Sprache/Anrede und Titel/Themenüberblick. Art. 14 Abs. 1 lit. d verlangt die Kategorien – reicht
   der Verweis auf Abschnitt 9 (gestaffelte Information), oder sollen Profil-Link und Gesprächsbeginn
   in der Mail ausdrücklich genannt werden? (Textänderung, schnell gemacht.)
3. **Verantwortlicher in der Mail.** Die Mail nennt den Verantwortlichen nicht selbst, sondern
   verlinkt Abschnitt 9 („Einzelheiten, Verantwortlicher und Ihre Rechte“). Ob für Art. 14 Abs. 1
   lit. a der Link genügt oder Name + Anschrift (wie in Abschnitt 1) in die Mail gehören, bitte
   entscheiden. Der Absender ist ohnehin kontakt@openmyconet.de.
4. **Widerspruchsrecht hervorgehoben?** Art. 21 Abs. 4 verlangt, auf das Widerspruchsrecht
   spätestens bei der ersten Kommunikation „in einer verständlichen und von anderen Informationen
   getrennten Form“ hinzuweisen. Heute steht es innerhalb des Datenschutz-Absatzes. Möglich: ein
   eigener, abgesetzter Satz in der Mail („Sie können der Speicherung jederzeit widersprechen …“).
5. **Art. 6 Abs. 1 lit. b nach der Annahme.** lit. b setzt ein Vertrags- bzw. Nutzungsverhältnis
   voraus. Es gibt (noch) keine ausdrücklichen Nutzungsbedingungen für den Austausch; die Person
   nimmt die Einladung aktiv an. Zu prüfen, ob das als Nutzungsverhältnis reicht oder ob für die
   Zeit nach der Annahme ebenfalls lit. f genannt werden sollte (oder kurze Nutzungsbedingungen).
6. **Interessenabwägung dokumentieren.** Für lit. f (Vorbereitung, interne Notizen, LinkedIn-Link)
   wäre eine kurze schriftliche Abwägung im Kontrollzentrum sinnvoll (Zweck, Erforderlichkeit,
   vernünftige Erwartung der Person nach einem eigenen LinkedIn-/Mail-Gespräch, Schutzmaßnahmen:
   nur Team sichtbar, keine fremden Texte, 24-Monats-Frist).
7. **Verzeichnis von Verarbeitungstätigkeiten (Art. 30)**, falls geführt: neue Tätigkeit
   „Fachlicher Austausch auf Einladung“ ergänzen.
8. **Löschsperre** („berechtigter Aufbewahrungsgrund“): Formulierung in Abschnitt 9 („In
   Einzelfällen, etwa bei gesetzlichen Nachweispflichten …“) – passt das zu Art. 17 Abs. 3 / Art. 18,
   und sollen weitere Beispiele genannt werden?
9. **Abgrenzung zu Abschnitt 8 (Kontaktaufnahme durch OpenMycoNet).** Wird ein Kontakt zuerst über
   das MCC angeschrieben und später eingeladen, gelten beide Abschnitte mit eigenen Fristen
   (2 Jahre bzw. F1–F4). Ist das so gewollt und verständlich?
10. **Übersetzungen.** Nach der Freigabe passe ich en/nl/fr/es an etwaige Änderungen an; sie sind
    als Übersetzung zur Information gekennzeichnet (Hinweis auf den Rechtstext-Seiten).

## 5. Was nach der Freigabe passiert

1. Änderungen aus Abschnitt 4 einarbeiten (Texte in 5 Sprachen, ggf. Frist F1a).
2. ENTWURF-Vermerk in `omn/rechtstexte.json` entfernen, `stand` setzen.
3. Commit + Push → GitHub grün → Staging → Prod-Deploy (durch Robby).
4. Erste echte Einladung; Robby prüft die angekommene Mail einmal selbst.

---

## 6. Entscheidungen von Robby (25.10.2026) und Umsetzung

| Punkt | Entscheidung | Umsetzung |
|---|---|---|
| 4.1 | F1a auf **1 Monat** verkürzen, vorher Mail an den Admin | Frist 30 Tage; einmalige Admin-Mail nach 21 Tagen (Spalte `vorbereitet_erinnert_am`, Migration `a0d6f3552d84`) |
| 4.2 | Einladungsmail nennt zusätzlich den **Gesprächsbeginn** (Profil-Link nur in Abschnitt 9) | Mailtext in 5 Sprachen |
| 4.3 | Verweis auf Abschnitt 9 reicht | unverändert |
| 4.4 | Widerspruchsrecht als **eigener Satz** in der Mail | eigener Absatz vor dem Datenschutzhinweis (5 Sprachen) |
| 4.5 | lit. b reicht bei aktiver Annahme | unverändert |
| 4.6 | Interessenabwägung schriftlich | Entwurf im Kontrollzentrum (`03_Website_Backend/Interessenabwaegung_Austausch.md`) |
| 4.7 | VVT-Eintrag „Fachlicher Austausch auf Einladung“ | Entwurf im Kontrollzentrum (`03_Website_Backend/VVT_Fachlicher_Austausch.md`) |
| 4.8 | keine weiteren Beispiele zur Löschsperre | unverändert |
| 4.9 | **eine** Frist für Kontaktaufnahme und Einladung: 2 Jahre | F1 = 2 Jahre nach der letzten Einladung; Abschnitt 9 und Mail entsprechend |
| 4.10 | Übersetzungen nachziehen | erledigt (en/nl/fr/es) |

**Freigegeben von Robby am 25.10.2026** (geänderte Texte). ENTWURF-Vermerk entfernt; nächster Schritt: Staging → Prod-Deploy.
