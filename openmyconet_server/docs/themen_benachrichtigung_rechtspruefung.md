# Benachrichtigungen aus den Themenräumen – Unterlage zur rechtlichen Prüfung

Stand: 28.10.2026 · Maßgeblich ist die deutsche Fassung; en/nl/fr/es sind nachgezogen.
Hinweis: Zusammenstellung mit Anmerkungen, **keine Rechtsberatung**.

**Freigegeben von Robby am 28.10.2026.** Seitdem ist der Schalter `THEMEN_BENACHRICHTIGUNG` überall an;
`THEMEN_BENACHRICHTIGUNG=0` in der `.env` schaltet die Mails an Teilnehmende ab (die Admin-Mail läuft
unabhängig davon). Die Freigabe ist im `_hinweis` von `omn/rechtstexte.json` vermerkt.

## 1. Entscheidungen (Robby, 28.10.2026)

| Punkt | Entscheidung |
|---|---|
| Wer folgt | automatisch: wer eine Diskussion anlegt oder darin schreibt; zusätzlich Knopf „Folgen“ / „Nicht mehr folgen“ |
| Häufigkeit | sofort, gedrosselt: nach einer Mail die nächste erst nach dem nächsten Besuch der Diskussion |
| Inhalt | Titel der Diskussion + Anzeigename + Link, **ohne Beitragstext** |
| Abbestellen | Link in **jeder** Mail (ohne Login, Bestätigungsseite), One-Click im Mail-Programm, „Nicht mehr folgen“, Einstellung „E-Mail bei neuen Beiträgen …“ |
| Admin | jede neue Diskussion, jedes neue Gebiet, jeder neue Beitrag sofort (Moderation) |

## 2. Was gespeichert wird

Neue Tabelle `themen_abo`: Konto, Diskussion, folgt ja/nein, zuletzt angesehen, zuletzt benachrichtigt.
Dazu in `themen_teilnahme` die Einstellung „Benachrichtigungen“ (Standard an). Gelöscht mit dem Konto
oder der Diskussion. Versand über die bestehende Mail-Warteschlange (gleicher Mailserver wie alle anderen Mails).

## 3. Rechtsgrundlage (Entwurf)

Art. 6 Abs. 1 lit. b DSGVO: Die Benachrichtigung ist Teil der Nutzung der Themenräume, um die die Person
durch Anlegen, Schreiben oder „Folgen“ selbst gebeten hat; jederzeit abbestellbar. Keine Werbung, kein
Newsletter – deshalb ist keine eigene Einwilligung nötig (anders als bei Rund-Mails).

## 4. Datenschutzerklärung, Abschnitt 10 – neuer Absatz (wörtlich)

> Benachrichtigungen: Wer eine Diskussion anlegt, darin schreibt oder ihr über „Folgen“ folgt, erhält per E-Mail eine Benachrichtigung über neue Beiträge – mit dem Titel der Diskussion und dem Anzeigenamen, ohne den Text des Beitrags –, danach erst wieder nach dem nächsten Besuch der Diskussion. Dafür speichern wir, welchen Diskussionen Sie folgen und wann Sie sie zuletzt angesehen bzw. eine Benachrichtigung erhalten haben; diese Angaben werden mit Ihrem Konto oder der Diskussion gelöscht. Abbestellen können Sie jederzeit über den Link in jeder Benachrichtigung, über „Nicht mehr folgen“ oder in den Einstellungen der Themenräume. Rechtsgrundlage ist Art. 6 Abs. 1 lit. b DSGVO.

Stand der Datenschutzerklärung: 28. Oktober 2026 (alle 5 Sprachen).

## 5. Zu prüfen – meine Anmerkungen

1. **Automatisches Folgen.** Wer schreibt, folgt automatisch und bekommt Mails, ohne vorher gefragt zu werden.
   Abgefedert durch: Hinweis in den Einstellungen, Abbestell-Link in jeder Mail, Drosselung. Üblich bei Foren.
2. **Anzeigename in der Mail.** Der Anzeigename anderer Teilnehmender steht in der Mail – den sehen sie ohnehin
   in den Themenräumen. Kein Beitragstext, keine E-Mail-Adressen anderer.
3. **Nutzungsregeln** müssen nicht geändert werden (keine neue Zustimmung nötig).
4. **VVT** im Kontrollzentrum ergänzt (Zweck Benachrichtigung, Daten `themen_abo`).

## 6. Nach der Freigabe

1. ✅ Freigabe im `_hinweis` von `omn/rechtstexte.json` vermerkt (28.10.2026).
2. ✅ `THEMEN_BENACHRICHTIGUNG` Standard überall an.
3. Staging → Prod deployen.
