# Automatische Übersetzung der Themenräume – Unterlage zur rechtlichen Prüfung (Phase 2b)

Stand: 26.10.2026 · Maßgeblich ist die deutsche Fassung; en/nl/fr/es sind nachgezogen.
Hinweis: Zusammenstellung mit Anmerkungen, **keine Rechtsberatung**.

**Freigegeben von Robby am 26.10.2026** (Datenschutztext, Nutzungsregeln Fassung 2026-10-26, E1–E3).
Seitdem ist der Schalter `UEBERSETZUNG_AKTIV` überall standardmäßig an; `UEBERSETZUNG_AKTIV=0` in der `.env`
schaltet ab.

Die Übersetzung ist gebaut (Commits `f1a52d7`, `23b6e2d`, `85613aa`, `ef2fbb6`, `fd56240`). Vor der Freigabe war
der Schalter auf Prod aus. Solange er aus ist, geht
kein Text an Anthropic, es erscheinen weder Platzhalter noch Hinweis. Die Freigabe ist im `_hinweis` von
`omn/rechtstexte.json` vermerkt.

---

## 1. Entscheidungen (Robby, 26.10.2026)

| Punkt | Entscheidung |
|---|---|
| Anbieter | **Claude (Anthropic)**, dasselbe Modell wie Chatbot und News-Übersetzung (`claude-sonnet-5-5`) – kein neuer Vertrag |
| Kostenbremse | **100** automatische Übersetzungen je Tag (UTC); zusätzlich 300 Abrufe je Person und Stunde |
| Hinweis beim Schreiben | **Variante 2:** „Texte werden automatisch übersetzt (Anthropic) – Datenschutzerklärung“ (Link) |
| E1 Widerspruch | **Einstellung „Eigene Texte nicht automatisch übersetzen“** (umgesetzt, s. Abschnitt 5) |
| E2 Nutzungsregeln | **neuer Absatz**, Fassung `2026-10-26` – alle stimmen beim nächsten Besuch neu zu (s. Abschnitt 5) |
| E3 Kennzeichnung | **bleibt** „Automatisch übersetzt aus …“ |

## 2. Was genau passiert

| | |
|---|---|
| Was wird übersetzt | Titel + Beschreibung von Themengebieten und Diskussionen, Text von Beiträgen |
| Was **nicht** | Anzeigename, Konto, E-Mail, IP-Adresse, Anhänge/Dateien, Zeitpunkte |
| Wann | nur wenn jemand den Text in einer anderen Website-Sprache aufruft; je Fassung und Sprache genau **einmal** (danach aus der Datenbank). Bei „Originale zuerst“ erst beim Aufklappen |
| Was geht an Anthropic | eine feste Anweisung (Sprachpaar, Regeln, passende Glossarbegriffe) + der Text, klar abgegrenzt; das Modell hat keine Werkzeuge; Aufruf vom Server, Schlüssel nur dort |
| Prüfung der Antwort | verworfen, wenn Zahlen, Links, DOIs oder E-Mail-Adressen nicht mit dem Original übereinstimmen; Anzeige immer escaped (kein HTML) |
| Speicherung bei uns | Tabelle `uebersetzung`: Text, Zielsprache, Prüfsumme der Originalfassung, Anbieter, Zeitpunkt |
| Löschung | mit dem Original (Beitrag entfernen/löschen/bearbeiten, Diskussion/Gebiet löschen, Löschlauf für ausgeblendete Beiträge); Admin kann einzelne Übersetzungen löschen (Audit-Log) |
| Kennzeichnung | „Automatisch übersetzt aus: Deutsch · Original anzeigen“; Original immer in der Seite; Hinweis „Maßgeblich ist das Original. Übersetzungen können Fehler enthalten.“ |
| Kontolöschung | Beiträge bleiben ohne Namen („Wissen bleibt“), ihre Übersetzungen ebenso |

## 3. Rechtsgrundlage (Entwurf)

| Verarbeitung | Rechtsgrundlage |
|---|---|
| Übermittlung der Texte an Anthropic zur Übersetzung, Speichern der Übersetzung | Art. 6 Abs. 1 lit. f – Ergänzung der Interessenabwägung: Kontrollzentrum `03_Website_Backend/Interessenabwaegung_Themenraeume.md`, Abschnitt 7 |
| Übermittlung in die USA | Art. 46 Abs. 2 lit. c (Standardvertragsklauseln im DPA von Anthropic) – Ergänzung der TIA: `03_Website_Backend/TIA_Anthropic_Chatbot.md`, Abschnitt 7 |
| Anthropic als Auftragsverarbeiter | Art. 28 – bestehendes DPA (gilt für die gesamte API-Nutzung des Kontos) |

## 4. Datenschutzerklärung, Abschnitt „10. Wissenschaftliche Themenräume“ – Änderung (wörtlich)

**Alt (Schluss des dritten Absatzes):**
> Die Inhalte werden nicht an Dritte weitergegeben. Eine automatische Übersetzung der Beiträge findet derzeit nicht statt; sollte sie eingeführt werden, ergänzen wir diesen Abschnitt vorher.

**Neu:**
> Außer für die automatische Übersetzung (nächster Absatz) geben wir die Inhalte nicht weiter.
>
> Automatische Übersetzung: Damit Teilnehmende verschiedener Sprachen miteinander diskutieren können, werden Titel, Beschreibungen und Beiträge in den Themenräumen automatisch übersetzt, wenn jemand sie in einer anderen Sprache der Website aufruft. Dafür übermitteln wir nur den jeweiligen Text an Anthropic, ohne Anzeigenamen, E-Mail-Adresse, IP-Adresse oder andere Kennungen; Anthropic erzeugt daraus die Übersetzung. Vertragspartner, Verarbeitung in den USA, Standardvertragsklauseln und Ausschluss des Trainings sind wie beim Chatbot geregelt (Abschnitt 12). Die Übersetzung speichern wir neben dem Original und löschen sie spätestens mit ihm; ändert sich das Original, wird sie nicht mehr angezeigt. Maßgeblich ist immer das Original; Übersetzungen sind als automatisch gekennzeichnet und können Fehler enthalten. Rechtsgrundlage ist Art. 6 Abs. 1 lit. f DSGVO; unser berechtigtes Interesse und das der Teilnehmenden ist eine mehrsprachige wissenschaftliche Diskussion. Sie können jederzeit widersprechen: In den Einstellungen der Themenräume lässt sich die Übersetzung Ihrer eigenen Texte abschalten; vorhandene Übersetzungen löschen wir dann, und das gilt auch nach einer Kontolöschung weiter. Bitte schreiben Sie in den Themenräumen nichts, was nicht an diesen Dienstleister übermittelt werden soll.

Stand der Datenschutzerklärung: 26. Oktober 2026 (in allen 5 Sprachen).

## 5. Umgesetzte Entscheidungen E1–E3 (Robby, 26.10.2026)

**E1 – Widerspruch: Einstellung „Eigene Texte nicht automatisch übersetzen“.** In den Einstellungen der
Themenräume. Gilt für alle eigenen Themengebiete, Diskussionen und Beiträge; neue Texte übernehmen die
Einstellung. Beim Einschalten werden die vorhandenen automatischen Übersetzungen sofort gelöscht, danach
wird nichts mehr an Anthropic geschickt. Gespeichert **je Inhalt** (`uebersetzen`), damit der Widerspruch
auch nach einer Kontolöschung gilt, wenn die Beiträge ohne Namen stehen bleiben (Migration `b7c41e2d9a05`).
Inhalte des Teams sind davon nicht betroffen.

Text der Einstellung:
> Eigene Texte nicht automatisch übersetzen
> Gilt für alle eigenen Themengebiete, Diskussionen und Beiträge, auch nach einer Kontolöschung. Vorhandene automatische Übersetzungen werden gelöscht; Teilnehmende anderer Sprachen sehen dann nur das Original.

**E2 – Nutzungsregeln, neue Fassung `2026-10-26`.** Neuer Absatz vor dem Moderations-Absatz (alle
Teilnehmenden stimmen beim nächsten Besuch einmal neu zu):
> Texte in den Themenräumen werden automatisch in die anderen Sprachen der Website übersetzt; dafür wird nur der Text, ohne Name und E-Mail-Adresse, an Anthropic übermittelt. Maßgeblich ist das Original. In den Einstellungen lässt sich die Übersetzung der eigenen Texte jederzeit abschalten.

Hinweis: Auch die neue Regelfassung darf erst nach der Freigabe auf Prod – sonst würden dort alle einer
Übersetzung zustimmen, die noch aus ist.

**E3 – Kennzeichnung bleibt** „Automatisch übersetzt aus: … · Original anzeigen“.

## 6. Zu prüfen – meine Anmerkungen

1. **lit. f statt lit. b.** Man könnte die Übersetzung als Teil der Nutzung (lit. b) sehen. Ausgelöst wird sie aber
   durch die Lesenden, nicht durch die Verfasser, und die Themenräume funktionieren auch ohne sie. lit. f mit
   Widerspruchsmöglichkeit (E1, umgesetzt) halte ich für sauberer.
2. **Unveröffentlichte Forschung.** Für Fachkontakte ist das größere Risiko kein Personenbezug, sondern
   Vertraulichkeit (z. B. noch nicht publizierte Ergebnisse). Abgefedert durch: Nutzungsregeln (keine vertraulichen
   Inhalte), Hinweis beim Schreiben, kein Training bei Anthropic, Opt-out (E1, umgesetzt).
3. **Besondere Kategorien (Art. 9).** Nicht vorgesehen und laut Nutzungsregeln unerwünscht; fachliche Texte.
4. **Veraltete Übersetzungen.** Ändert der Admin den Titel eines Gebiets, bleiben die alten automatischen
   Übersetzungen gespeichert (werden aber nicht mehr angezeigt), bis das Gebiet gelöscht wird oder der Admin sie
   in der Liste löscht (dort als „veraltet“ markiert). Bei Beiträgen werden sie beim Bearbeiten sofort gelöscht.
   Auf Wunsch lösche ich veraltete Fassungen künftig automatisch mit – passt dann wörtlich zu „löschen sie
   spätestens mit ihm“ und wäre sparsamer.
5. **Speicherdauer bei Anthropic.** Richtet sich nach den Commercial Terms / dem DPA (wie beim Chatbot); bitte
   bei der Gelegenheit prüfen, ob sich daran seit dem 28.09.2026 etwas geändert hat.
6. **Fehlerhinweis (Commercial Terms D.3).** Erfüllt: „Übersetzungen können Fehler enthalten“ unter jeder
   Diskussion und in den Einstellungen, zusätzlich im Datenschutztext.
7. **Ausgabenlimit.** Unabhängig vom Tageslimit bitte in der Anthropic-Konsole ein monatliches Ausgabenlimit
   setzen (100 Übersetzungen/Tag ≈ 0,80 $/Tag, also höchstens rund 25 $/Monat).

## 7. Kontrollzentrum (Entwürfe zur Freigabe)

- `TIA_Anthropic_Chatbot.md` – neuer Abschnitt 7 „Ergänzung Phase 2b: Übersetzung der Themenräume“
- `Interessenabwaegung_Themenraeume.md` – neuer Abschnitt 7 mit eigener Freigabezeile
- `VVT_Themenraeume.md` – Empfänger + Drittlandübermittlung ergänzt

## 8. Nach der Freigabe

1. ✅ Freigabe im `_hinweis` von `omn/rechtstexte.json` vermerkt (26.10.2026).
2. ✅ `UEBERSETZUNG_AKTIV` Standard überall an (Prod), per `.env` abschaltbar.
3. Staging → Prod deployen; danach einmal einen Beitrag in einer anderen Sprache aufrufen und im Admin
   (`/admin/themen/uebersetzungen`) nachsehen.
