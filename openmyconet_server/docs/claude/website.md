# Öffentliche Website: Frontend-Audit, llms.txt, Songtexte, Rechtstexte, Startseite

> Ausgelagert aus `openmyconet_server/CLAUDE.md` am 14.10.2026 (wörtlich übernommen).
> Vor Änderungen in diesem Bereich lesen; neue Erkenntnisse hier eintragen, nicht in CLAUDE.md.

### Frontend-Audit (`frontend-audit`-Job)
Startet die App per gunicorn gegen eine leere SQLite (`db.create_all()`, kein
Seed — die SSR-Seiten rendern ohne Daten) und prüft die 14 öffentlichen
`site/*.html`-Seiten mit **Lighthouse CI** (`lighthouserc.json`: performance,
accessibility, best-practices, seo) + **axe-core via pa11y-ci** (`.pa11yci.json`,
WCAG2AA). Der Job serviert die App mit `OMN_ASSET_BASE=/` → Lighthouse/pa11y
prüfen die **Repo**-CSS/JS, nicht die schon deployten. Reports als CI-Artifact
`frontend-audit`. **Lighthouse ist der harte Gate:** `accessibility` ≥ 0.95,
`best-practices` ≥ 0.90 (`/medien` = 96: der CI-Lauf hat die serververwalteten
mp3s nicht, der Player loggt einen 404), `seo` ≥ 0.98 (Ist-Score-Ratsche, Stand
2026-09 — bei stabiler Verbesserung hochziehen), `performance` nur `warn`
(Headless-CI-Score zu verrauscht). Der **axe/pa11y-Schritt blockiert ebenfalls**
(WCAG2AA über alle URLs = 0 Verstöße). Nur `color-contrast` ist in `.pa11yci.json`
per `ignore` aus (axe kann Kontrast über Hintergrundbildern/Verläufen nicht
berechnen → ~225 Falsch-Positive; den echten Kontrast prüft Lighthouse).
`audio-caption` ist **harter Gate** (seit den Songtexten, s. u.). Lokal:
Dev-Server mit `OMN_ASSET_BASE=/ SECRET_KEY=x python wsgi.py` starten, dann
`npx @lhci/cli autorun` bzw. `npx pa11y-ci`.

### Textfassung für KI-Assistenten (`/llms.txt`, seit 28.09.2026)
`omn/llms.py` erzeugt `/llms.txt` (Kurzbeschreibung, Einordnung „kein
Wirkungsnachweis“, Seitenliste DE+EN), `/llms-full.txt` (alle Texte Deutsch) und
`/llms-full-en.txt` (beide mit YAML-Frontmatter, `stand` = Dateidatum von `translations.json` = Commit-Zeit des Deploys) — zur Laufzeit aus `translations.json`, Themengruppen aus
`omn/wissensbasis.py` (gemeinsam mit `build_rag_index.py`, also dieselben wie beim
Chatbot). Header `X-Robots-Tag: noindex` + canonical auf die Startseite, Links immer
auf www. Neue öffentliche Seite → in `SEITEN_GRUPPEN` (und ggf. `GRUPPEN_SEITE`) nachtragen.
`/llms.txt` hat einen Block „Projekt-Eckdaten“ (`ECKDATEN`, nur Text-Keys, nichts frei
formuliert) plus Angaben aus dem **Impressum** (`app/static/impressum.html`, nur deutsch,
zur Laufzeit geparst: Anbieter ohne Straße/Telefon, E-Mail, Schutzrechte, Lizenz der
Messdaten CC BY 4.0). Impressum umgebaut → `test_impressum_angaben` schlägt an.
Tests `tests/test_llms.py` (prüfen auch, dass alle Keys und Seiten existieren).

### Songtexte / Musik-Player (WCAG 1.2.1)
Der Player (`<audio id="omn-audio">` in `site/base.html`, Track-Manifest
`OMN_TRACKS`, 6 Suno-Songs; seit 15.10.2026 „When the Data Flows“; Cover 1024 px WebP
+ 64-px-`-mini`) hat eine WebVTT-Songtextspur je Track
(`app/static/lyrics/*.vtt`, git-getrackt, klein). `<track kind="captions">` wird
von `loadTrack()` pro Track umgeschaltet und speist die Follow-along-Zeile
(`#omn-now-line`, `cuechange`, nur im grossen Player, `aria-hidden`). Die
barrierefreie Volltext-Fassung steht als `<details>`-Liste unter dem Player auf
`/medien.html` (`#songtexte`, i18n-Keys `musik_texte_label`/`musik_texte_hint`;
die Texte selbst bleiben englisches Original). `mimetypes.add_type('text/vtt',
'.vtt')` in `omn/__init__.py` sichert den MIME-Typ (Flask serviert die `.vtt`,
nicht nginx). Die Liedlängen stehen fest in `OMN_TRACKS` (`dauer`, Sekunden, seit 29.09.2026 — vorher wurden dafür beim Aufruf alle MP3s angeladen); neues Lied → `dauer` mitpflegen. Neue/korrigierte Zeilen: `.srt` → `.vtt` (`WEBVTT`-Header, `,`→`.`
im Zeitstempel) + den `<details>`-Block auf `medien.html` nachziehen.

## Impressum + Datenschutz, Sprachwahl (seit 28.09.2026)
`/impressum.html` und `/datenschutz.html` sind SSR-Seiten (`site/rechtstext.html`, Routen
in `omn/site_live.py`), Texte in **`omn/rechtstexte.json`** fünfsprachig (bewusst nicht in
`translations.json`), geladen über `omn/rechtstexte.py`. **Rechtlich maßgeblich ist `de`**
(von Robby freigegeben 28.09.2026, Entwurf + Begründungen im Kontrollzentrum
`03_Website_Backend/Rechtstexte_Entwurf_2026-09.md`); en/nl/fr/es tragen oben den
Hinweis „nur zur Information“. Änderung am deutschen Text → Übersetzungen + `stand`
nachziehen; die Datenschutzerklärung nennt die Löschfristen (s. u.), Hosting (Hetzner
Helsinki), Mail (ALL-INKL), Chatbot (Anthropic, SCC; TIA im Kontrollzentrum) — bei
Änderungen daran den Text mitziehen. `fakten` (Name, Anschrift, Telefon, E-Mail) liest
auch `omn/llms.py`. Sprachwechsel auf diesen Seiten per Neuladen (`setLang` im Template).
**Sprachwahl einheitlich:** Flaggen-Klick (`omnSetLang` in `site/base.html`) schreibt
Cookie `omn_lang` **und** localStorage, `getLang()` liest Cookie vor localStorage; das
Datenlabor hat dieselben Flaggen (SVGs einmal in `omn/i18n.py` `FLAGGEN`). Footer per
`t()` (`footer_*`). Tests `tests/test_rechtstexte.py`.

## Startseite: Status-Badge + Mini-Dashboard (seit 29.09.2026)
Kein „aktiver Knoten“ mehr (die „1“ stand fest im HTML): Badge `status_badge_1..3`
(„Datenplattform steht · Hardware in Entwicklung · erste Messstandorte gesucht“, der letzte
Teil öffnet die Knoten-Bewerbung). Statt der Netzwerk-Animation ein **Mini-Dashboard mit
simulierten Daten**: Zeitraffer eines Tages (60 s) aus dem Sandbox-Szenario `baseline`
(nie Stimulation/Vergleich), Bio als Minutenmittel, Bodentemperatur/-feuchte stündlich.
Daten = **`app/static/startseite_vorschau.json`** (vorberechnet, keine DB-Abfrage pro
Aufruf; `is_simulated: true`, Szenario-/Generator-/Modellversion) aus `flask sandbox-vorschau
[--tag 2025-07-15 --standort SBX-DE-01]` (`omn/sandbox/vorschau.py`, nur PG mit Sandbox —
lokal mit der Testdatenbank auf Port 55432, der Generator ist deterministisch = Prod-Werte).
**Neue Szenario-/Generatorversion → Datei neu erzeugen**, `test_startseite_vorschau.py`
schlägt sonst an. Zeichnen: `app/static/startseite-vorschau.js` (SVG, keine Bibliothek, keine
style-Attribute), Wasserzeichen `vorschau_wasserzeichen` steht **im SVG, in jedem der drei
Felder**, Zeit = simulierte
Uhrzeit, `prefers-reduced-motion` → statischer Tag, läuft nur sichtbar (IntersectionObserver).
Badge: Punkt gold (grün las sich als „online“); eine Zeile je Aussage bei ≤ 900 px und immer
für FR/ES (`html:lang(...)`, `<html lang>` folgt dem Sprachumschalter), sonst hing ein „·“ am Zeilenende.
**Prototyp-Knoten:** `Knoten.prototyp` (Migration `2b6f1c9e7a30`, alle Zeilen des alten
Messwegs = TRUE); `/api/v1/status` zählt nur `prototyp=False`, `/api/v1/messung` ist als
Prototyp-Schnittstelle markiert; echtes Messnetz = BioComm-Dateneingang.
