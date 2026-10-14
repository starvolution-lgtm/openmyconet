# Server-MCC /mcc

> Ausgelagert aus `openmyconet_server/CLAUDE.md` am 14.10.2026 (wörtlich übernommen).
> Vor Änderungen in diesem Bereich lesen; neue Erkenntnisse hier eintragen, nicht in CLAUDE.md.

## Server-MCC `/mcc` (seit 07.10.2026)
Die Teile des lokalen Mission Control Center (Kontrollzentrum `_App/`), die auch unterwegs
gebraucht werden, wenn der PC aus ist (Robby: z. B. mehrere Tage Krankenhaus). **Eigener
Bereich mit eigener Grundvorlage** (`app/templates/mcc/base.html`, Stil des lokalen MCC,
handytauglich, `app/static/mcc.css` + `mcc.js`, ohne Inline-Skripte/-Styles), **nicht** in
den Admin gequetscht (Robby); Einstieg „🧭 Zum MCC“ in der Admin-Kopfzeile. Paket `omn/mcc/`
(Blueprint `mcc_bp`, Präfix `/mcc`): gleicher kanonischer Host wie der Admin
(`_kanonischer_host`, www → api, sonst fehlt das Login-Cookie), CSRF, nur `superadmin`,
`X-Robots-Tag: noindex`, `Cache-Control: no-store`, **vom Service Worker nie gecacht**
(`sw.js` nimmt `/mcc` aus wie `/admin`; Kontrollzentrum-Check prüft das). Plan: Kontrollzentrum
`03_Website_Backend/Claude_Code_Auftraege/2026-10-07_Plan_MCC_mobil.md`.

**Schritt 1 Kontakte** (`omn/mcc/kontakte.py`, Tabelle `kontakt_versand`, Migration
`4c8c3b65f64f`): Versandlog der Vorstellungs-Mails (Status offen/positiv/negativ/nachfrage,
Wiedervorlage, Nachfragen, Notiz; fachliche Tage als `Date` im Ortsdatum Berlin,
`angelegt_am` tz-aware). Fällig = offen/nachfrage und Wiedervorlage ≤ heute. Seiten
`/mcc` (Kacheln), `/mcc/kontakte` (Filter, Positiv/Negativ/Nachfragen, Bearbeiten, Löschen,
CSV), `/mcc/vorlagen` (drei Felder + Sprache, Senden). **Versand per smtplib über das
Postfach robert.jank@** (eigener Login `MCC_MAIL_USERNAME`/`MCC_MAIL_PASSWORD`,
`MCC_MAIL_SENDER`, `MCC_MAIL_BCC`; Server/Port = `MAIL_SERVER`/`MAIL_PORT`), nicht über
Flask-Mail (hängt an kontakt@). Erst nach erfolgreichem Versand eingetragen;
`MAIL_SUPPRESS_SEND` (Staging) → nichts verschickt, Eintrag `versandart='unterdrueckt'`.
Vorlagen `omn/mcc/vorlagen/<name>_<de|en>.md` (Kopf `Vorlage:`/`Betreff:`, `---`, Text;
`{{TITEL}}` entfällt samt Leerzeichen; Absatz nur aus `**…**` → Zwischenüberschrift, `- ` →
Liste, URLs klickbar), Mail = `mcc/kontakt_email.html` (schlicht: Logo-Streifen, Text auf
Weiß, Fußzeile Anschrift/Telefon + Link „Hinweise zum Datenschutz“ →
`datenschutz.html#kontaktaufnahme`, Art. 14 DSGVO) + Klartext-Teil (`mailbau.py`,
`KONTAKT_KLARTEXT` — Kontaktdaten an beiden Stellen pflegen). **Vorschau**: `mcc.js` schickt
die Eingaben per fetch (Header `X-MCC-Vorschau`) in die Session, das iframe lädt per GET (keine
Namen in URLs); diese eine Antwort hat eine eigene CSP (`g.csp_override` in
`omn/public.py`: Inline-Styles ja, Skripte nein) — wird je Request zurückgesetzt.
**Erinnerung**: `flask mcc-erinnerung` per Cron 05:30 UTC (= 07:30 Sommerzeit, nur Prod,
`deploy/mcc_erinnerung.sh`, eingetragen von `install_backup_cron.sh`), Mail nur wenn etwas
fällig ist, mit Namen (Robby), über den normalen Website-Zugang an `MCC_ERINNERUNG_AN`
(Standard `MCC_MAIL_SENDER`). `flask mcc-faellig` liefert die Zahl für `deploy/mcc_lage.sh`
(`mcc_faellig=`) → Hinweis im lokalen MCC. `flask mcc-kontakte-import <versandlog.json>`
übernimmt einmalig den lokalen Versandlog. Löschfrist 2 Jahre nach `letzte_aktivitaet`
(`omn/aufbewahrung.py`), Datenschutzerklärung Abschnitt 8 „Kontaktaufnahme durch
OpenMycoNet“ (fünfsprachig, freigegeben 07.10.2026). Tests `tests/test_mcc.py`.

**Schritt 2 Statusdateien, nur lesen** (`omn/mcc/spiegel.py` + `dateien.py`): das lokale MCC
(`_App/spiegel.py`) schickt beim Start und alle 15 min — nur bei Änderungen — `00_UEBERSICHT.md`,
alle `*Status*.md` und den Versuchsplan (ohne Rechercheprofile/Rohfunde/Aufträge) als tar.gz per
SSH an `flask mcc-spiegel-empfangen` (stdin). Ablage `instance/mcc_spiegel/` (vom Deploy
ausgenommen, nicht öffentlich ausgeliefert, nicht im Backup — kommt vom PC neu), jeder Upload
ersetzt den ganzen Ordner (neu entpacken, dann tauschen; bei Fehlern bleibt der alte). Nur
`.md`, keine `..`/absoluten/versteckten Pfade, `tarfile`-Filter `data`, Größen begrenzt;
`.stand.json` = Zeitpunkt. Seiten `/mcc/status` (Kacheln aus der Übersichts-Tabelle,
Prioritäten, „seit N Tagen nicht geändert“ aus den mitgeschickten mtimes), `/mcc/datei/<pfad>`
(Markdown → HTML, `bleach`), `/mcc/offen` (dieselbe Auswertung wie `_App/app.py::offene_punkte`
— bei Änderungen dort hier nachziehen). Hinweis, wenn der Stand älter als 24 h ist. Abhaken nur
am PC (nie zwei Fassungen einer Datei). Neue Abhängigkeit `Markdown`. Tests `tests/test_mcc_spiegel.py`.

**Schritt 3 Server-Ampel** (`omn/mcc/server.py`, `/mcc/server`): das technische
Kontrollzentrum (vorher `/admin/kontrollzentrum`, leitet jetzt 301 dorthin) im MCC-Rahmen.
Die Checks + 5-Minuten-Cache bleiben in `omn/kontrollzentrum.py`; die Startseite zeigt eine
Zusammenfassung nur aus dem Cache (`ampel_kurz`, prüft nicht selbst). Knöpfe „Backup jetzt“ /
„Restore-Check jetzt“ posten an die Admin-Routen in `omn/admin/wartung.py`, die nach
`/mcc/server` zurückleiten. Admin-Menüpunkt „🚦 Kontrollzentrum“ entfällt („🧭 Zum MCC“).
Manifest `kontrollzentrum-manifest.json` (Name gleich gelassen, damit aufs Handy gelegte
Apps weiter funktionieren) startet jetzt in `/mcc`. Tests `tests/test_kontrollzentrum.py`.
