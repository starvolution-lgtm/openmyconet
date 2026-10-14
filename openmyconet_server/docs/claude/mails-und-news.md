# Rund-Mails und News

> Ausgelagert aus `openmyconet_server/CLAUDE.md` am 14.10.2026 (wörtlich übernommen).
> Vor Änderungen in diesem Bereich lesen; neue Erkenntnisse hier eintragen, nicht in CLAUDE.md.

## Rund-Mails an Nutzer
Newsletter (`/admin/newsletter`) und die optionale News-Benachrichtigung
(Checkbox + Sprach-Checkboxen beim Veröffentlichen unter `/admin/news`,
`_news_nachrichten_bauen` in `omn/admin/news.py`) gehen NUR an
`Nutzer.bestaetigt == True` **und** `keine_mails == False`. **Einwilligung (seit
28.09.2026):** `keine_mails` ist nur bei ausdrücklicher Zustimmung False — Häkchen
`newsletter` auf der Startseite (`register_nutzer_core(newsletter=…)`; Bewerbung,
Förderer, Kooperation haben keins → ohne Einwilligung) oder Klick auf
`/newsletter/einwilligen/<token>` (GET fragt, POST willigt ein, setzt auch
`bestaetigt`). Nachweis in `Nutzer.newsletter_einwilligung_am`. Erneute
Registrierung mit Häkchen ohne Einwilligung → Mail mit diesem Link (Sperre 1 h über
`einwilligung_angefragt_am`), stellt selbst nichts um. Bestandsnutzer ohne Nachweis:
`flask einwilligung-anfragen [--ausfuehren]` (ohne Flag Probelauf) meldet ab und reiht
einmal die Nachfrage ein. Tests `tests/test_registrierung.py`. Die News-Mail
zusätzlich nur an die im Formular angehakten Spracheinstellungen
(`request.form.getlist('mail_sprachen')`, gefiltert gegen `LANGS`) — die
News-Sprache selbst ist dabei egal (eine englische „aktuelle Änderungen"-News
kann bewusst an alle Sprachgruppen gehen). Jede Rund-Mail trägt einen
tokengesicherten Abmelde-Link `/abmelden/<nutzer.token>` (Route in
`omn/public.py`, GET = Bestätigungsseite gegen Prefetch, POST setzt
`keine_mails`) **und** die RFC-8058-Header `List-Unsubscribe` +
`List-Unsubscribe-Post: List-Unsubscribe=One-Click`
(`_list_unsubscribe_header` in `omn/admin/news.py`) — der POST auf dieselbe Route
erledigt die One-Click-Abmeldung der Mail-Clients. Transaktionale Mails (Doppel-Opt-in, Magic-Link) ignorieren das
Flag. Die Nachrichten werden **synchron im Request gebaut** (Rendering,
`url_for(_external=True)` braucht den Host-Header) und dann per
`omn.mailer.mailqueue_einreihen` als **`MailQueue`-Zeilen** abgelegt (eine je
Empfänger). Der SMTP-Versand läuft **ausserhalb des Requests**:
`mailqueue_drain` (CLI `flask mail-queue-drain`, Cron jede Minute via
`deploy/mailqueue_drain.sh` mit `flock`, für Prod + Staging) claimt einen Batch,
öffnet EINE `mail.connect()`-Verbindung, arbeitet ihn ab. **Durable**: ein
gunicorn-Neustart mitten im Versand verliert nichts, offene Zeilen bleiben in der
DB. Fehlversuche bis `MAX_VERSUCHE` (3), dann `status='fehler'` + Journal-Log.
`'sendet'`-Zeilen älter als 15 min → zurück auf `'offen'` (Crash-Recovery).
`'gesendet'` wird 30 Tage als Audit-Spur behalten, dann im Drain gelöscht. Unter
`TESTING` drained `mailqueue_einreihen` sofort synchron. Cron-Zeile einmalig:
`bash deploy/install_backup_cron.sh` (trägt jetzt auch die beiden Drain-Zeilen
ein). Einzel-/Transaktionsmails **und der Fehler-Alert** bleiben direkt
`mail.send()` — sofort, Einzelempfänger, und der Alert darf nicht von der Queue
abhängen. Siehe `test_news_mail.py`, `test_mailer.py`, `test_mailqueue.py`.

## News-Uebersetzung (Sept. 2026)

`News.uebersetzung_gruppe` (UUID-Hex, von `news_admin()` bei jedem neuen
Artikel frisch vergeben) verknuepft die bis zu 5 Sprachversionen EINER Story
-- vorher war jede der 5 Zeilen komplett unabhaengig (eigenes Bild, eigene
Tags, kein Bezug zueinander). `omn/admin/news.py::news_uebersetzen`
(`GET/POST /admin/news/<id>/uebersetzen/<lang>`, verlinkt aus dem "🌍 Andere
Sprachversionen"-Block auf `news_edit.html`) generiert per Anthropic-API
(dieselbe wie `rag_chatbot.py`) einen Uebersetzungsentwurf (Titel/Untertitel/
Inhalt-HTML, Tags/Bild von der Quelle uebernommen) -- landet NUR im
Formular, News hat keinen eigenen Entwurfsstatus (die `veroeffentlicht`-Spalte
ist ein reiner Zeitstempel), gespeichert wird also erst nach explizitem
Klick auf "Übersetzung veröffentlichen". Fehlt der API-Key oder schlaegt der
Call fehl, zeigt das Formular stattdessen den Originaltext zum selbst
Uebersetzen (kein Absturz, kein Blockieren des Workflows). Alte, vor dieser
Funktion angelegte News-Zeilen haben `uebersetzung_gruppe = NULL` -- harmlos,
bekommen aber beim ersten Klick auf "Entwurf erzeugen" nachtraeglich eine
Gruppe zugewiesen. Tests: `tests/test_news_uebersetzen.py` (Anthropic-Call
gemockt, kein echter API-Traffic in der Suite).

**Vorschau (Sept. 2026):** Weder das Anlege- noch das Uebersetzungsformular
hatten bisher eine Vorschau -- nur "veroeffentlichen oder nicht", und das
Quill-Editor-Fenster ist fuer eine echte Beurteilung zu klein.
`omn/admin/news.py::news_vorschau` (`POST /admin/news/vorschau`) rendert
**dieselbe** `news_detail.html`/`site/base.html`-Vorlage wie ein echter
Artikel, mit den aktuell im Formular stehenden (noch UNGESPEICHERTEN) Werten
-- legt nichts in der DB an. Der "👁 Vorschau"-Button (alle drei Formulare,
Logik gemeinsam in `admin-news-editor.js`) baut dafuer client-seitig ein
verstecktes Temp-Formular, haengt das Bild-Datei-Input-Element kurz um (damit
ein noch nicht hochgeladenes Bild mit in die Vorschau kommt, ohne es doppelt
waehlen zu muessen) und schickt es per POST in ein eigenes, vorher per
`window.open('', 'omn-vorschau-fenster')` synchron in der Klick-Geste
geoeffnetes Fenster (robuster als `form.target='_blank'` allein -- das
landete im Test als GET ohne Formulardaten). Ein neu ausgewaehltes
Vorschau-Bild wird dabei zwar schon auf die Platte geschrieben (wie beim
Quill-Inline-Bild-Upload auch), aber nur referenziert, wenn spaeter tatsaechlich
gespeichert wird. Tests: `tests/test_news_vorschau.py`.

**Manuelle Reihenfolge (Sept. 2026):** Vorher ergab sich die Anzeigereihenfolge
ausschliesslich aus `veroeffentlicht` -- nicht nachtraeglich sortierbar, ohne
das Datum zu verbiegen. `News.reihenfolge` (Integer, hoeher = weiter oben) ist
bewusst ein EIGENES Feld, unabhaengig vom angezeigten Datum. `▲`/`▼` in
`news_admin.html` (Route `POST /admin/news/<id>/verschieben/<hoch|runter>`)
vertauscht den Wert mit dem direkten Nachbarn in der aktuellen Sortierung.
Neue Artikel (`news_admin()`, `news_uebersetzen()`) bekommen
`max(reihenfolge)+1` (`naechste_reihenfolge()`), landen also weiterhin oben,
wie zuvor per Datum automatisch. Alle drei Listen-Queries (Admin-Liste,
`omn/public.py::news()`, `news_sitemap()`) sortieren nach
`reihenfolge DESC, veroeffentlicht DESC` -- der zweite Schluessel ist
absichtlich noch drin: haelt Alt-Zeilen mit `reihenfolge IS NULL` (Migration
`fa5a744c1177` backfillt zwar alle bestehenden, aber z.B. Test-Fixtures/
Skripte, die News direkt ohne `reihenfolge` anlegen, fallen sonst auf eine
undefinierte DB-Reihenfolge zurueck) weiterhin in der gewohnten
Datums-Reihenfolge. Tests: `tests/test_news_reihenfolge.py`.

**Kleinere Bildfassungen (seit 29.09.2026):** `save_news_image` legt neben dem Bild
(max. 1600 px, WebP) `<name>-480/-720/-960.webp` an (`omn/bildgroessen.py`, nie größer als
das Original, GIF nie). News-Liste und Artikelkopf nutzen `news_bild(dateiname)` (Jinja-Global:
`src`, `srcset`, `width`/`height` aus dem Dateikopf) — ohne Fassungen bzw. bei fehlender Datei
einfaches `<img>`. Bestand: `cd /home/omn/app && FLASK_APP=wsgi venv/bin/python -m flask
bilder-verkleinern` (idempotent; auf Prod + Staging am 29.09.2026 gelaufen). Bilder im
Artikeltext (Quill) bleiben unverändert. **Förderer-Logos** genauso: beim Upload (`omn/foerderer.py`)
zusätzlich `<name>-logo.webp` (in 320×200 eingepasst, SVG/GIF nie), `/foerderer.html` nimmt per
`foerderer_logo()` die kleine Fassung, falls vorhanden; `bilder-verkleinern` erledigt beide Ordner.
Tests `tests/test_bildgroessen.py`.
