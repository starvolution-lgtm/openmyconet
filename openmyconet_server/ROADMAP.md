# OpenMycoNet — Roadmap: Content, Dashboard & Netzwerk-Explorer

## ✅ Phase 1 — Content-Anschluss (abgeschlossen 2026-07-30)

- Bulk-Endpoint `GET /api/v1/content?seite=<seite>&sprache=<lang>` + Seed für index.html (52 Textstellen × 5 Sprachen).
- `applyContentBlocks(lang)` in index.html: überlagert `data-i18n`/`data-i18n-html`-Elemente mit Admin-Inhalt, stiller Fallback auf statischen Text bei API-Ausfall.
- Details, Namensraum-Konvention und Vorgehen für die 3 übrigen Seiten (foerderer/quellennachweise/leihgeraete): [CONTENT_BLOCKS.md](CONTENT_BLOCKS.md).
- Variante B (SSR) als spätere Option dokumentiert, nicht umgesetzt.

## ✅ Phase 2 — Login-Fundament & Rollenmodell (abgeschlossen 2026-07-30)

- Magic-Link-Login für registrierte Nutzer (`dashboard.py`), eigene Session (`nutzer_*`), getrennt von `admin_*`.
- Dashboard-Kernrollen (Basis-Nutzer / Bewerber / Knotenbetreiber) — aus bestehenden Relationen abgeleitet, kein neues Status-Feld.
- `Nutzer.fachrolle` (Wissenschaftler/wiss. Mitarbeiter/Student) als reine Klassifizierung fürs spätere Forum, admin-pflegbar über `/admin`.
- Forum-Zugriffsmodell (zweistufig: Kernzugang per Fachrolle + post-spezifische Freigabe für Knotenbetreiber) dokumentiert, nicht gebaut: [ROLLENMODELL.md](ROLLENMODELL.md).
- Mykorrhiza-Hintergrundtextur (320px-Kachel, ~14 KB JPEG, Opacity 0.05–0.08) auf Startseiten-Hero und Dashboard-Login eingebunden — gezielt, nicht flächendeckend.

## ✅ Phase 4 — Template-Vereinheitlichung & SSR-Vorbereitung (Schritt 1–3b abgeschlossen, Schritt 4 offen)

- Gemeinsames Jinja-Template (`app/templates/site/base.html`) + einheitliches i18n (`translations.json`, server- und clientseitig über `t()`/Instant-Umschalten) für alle 5 Hauptseiten (`index`, `leihgeraete`, `quellennachweise`, `foerderer`, `medien` neu) — lauffähig auf Testrouten `/preview/*`, noch nicht live.
- `foerderer.html`s eigener `NAV_LABELS`-Mechanismus abgelöst — jetzt derselbe Mechanismus wie überall.
- SSR löst nebenbei das hreflang/Duplicate-Content-Thema aus Phase 1 (Variante B ist damit teilweise umgesetzt, ohne vollen Hosting-Umzug).
- Details, bewusste Abweichungen, bekannte Alt-Lücken: [PARITAETSBERICHT.md](PARITAETSBERICHT.md), Architekturentscheidungen: [project_openmyconet_phase4_ssr.md](../../.claude/projects/memory/project_openmyconet_phase4_ssr.md) *(lokale Memory-Datei, nicht Teil des Repos)*.
- **Schritt 3b (Förderer-PayPal/PDF-Migration PHP → Flask): fertig, live auf api.openmyconet.de verifiziert (2026-07-31).** Neues Model `Foerderer`/`RechnungsZaehler` (`models.py`), neuer Blueprint `foerderer.py` mit `/foerderer/antrag` (Formular + Vorschau + PayPal-Redirect), `/foerderer/ipn` (PayPal-IPN-Webhook), `/foerderer/danke`, `/foerderer/rechnung` (tokengesicherter PDF-Download). PDF-Rechnung über `fpdf2`. **Echter End-to-End-Test mit PayPal-Sandbox erfolgreich:** echte Sandbox-Zahlung → IPN validiert → Förderer-Eintrag aktiviert → PDF-Rechnung erzeugt → Bestätigungsmail beim Förderer angekommen. Deployment erfolgte minimal-invasiv (nur `foerderer_bp` zum bestehenden, noch nicht-Phase-4-migrierten Live-`app.py` hinzugefügt, Phase-4-SSR-Templates bewusst nicht mit ausgerollt), DB-Backup vor Schema-Änderung, Worker-Reload per `kill -HUP` (kein sudo nötig, da Prozesse dem `omn`-User gehören).
- **Ergänzungsauftrag (2026-07-31, in Phase 4 gebündelt):** Persistenter Audio-Player (Track/Position/Lautstärke/Mute per `localStorage` über alle 5 Seiten, zentral in `base.html`, 5-Track-Playlist inkl. "Listen to the Forest"), neue Seite `medien.html` (Broschüre, volle Playlist-Ansicht, Buch — aus `index.html` ausgelagert), neue "Förderer & Kooperationen"-Sektion auf `index.html` (aktuell nur GPG-Projekt GmbH, weitere Kooperationen warten auf Content-Freigabe durch Robby). Details siehe [PARITAETSBERICHT.md](PARITAETSBERICHT.md).
- **Nebenbei gefunden (live-relevant):** `foerderer.html` verlinkte noch auf die alte `foerderer-antrag.php` statt auf die neue Flask-Route — betrifft auch die **aktuell live geschaltete** statische Seite auf All-Inkl. Lokal korrigiert, **Upload nach All-Inkl durch Robby steht noch aus**.
- **Schritt 4 (DNS-Cutover): durchgeführt (2026-07-31).** Nach Robbys Freigabe: echte Produktivrouten eingerichtet (`site_live.py`, ersetzt die seit der Migration kaputte alte `/`-Route), alle Assets zusätzlich auf Hetzner (kein Template-Umbau nötig dank `asset()`/`live()`-Architektur), nginx-Server-Block + SSL-Zertifikat für die Hauptdomain (Let's Encrypt, automatische HTTP→HTTPS-Weiterleitung, Auto-Renewal). DNS bei All-Inkl umgestellt (Apex-A-Record + neuer dedizierter `www`-A-Record auf die Hetzner-IP, Wildcard-CNAME/MX/SPF/DMARC/DKIM bewusst unangetastet). Live verifiziert. **Offen:** Google Search Console/Sitemap-Check (SEO-Kontinuität).

## ⏳ Phase 2b — Förderer & Wissenschaftler-Ansicht (nächster Schritt)

- Wissenschaftler-Dashboard-Ansicht (nutzt bereits vorhandenes `fachrolle`-Feld).
- Förderer-Dashboard: Brücke zum separaten PHP-Datentopf (`foerderer-antrag.php`) klären — ohne Doppelpflege.

## ⏳ Phase 3 — Netzwerk-Explorer (separater Auftrag, folgt nach Phase 2b)

- Optionale interaktive Netzwerk-Visualisierung (vis.js Network, isolierte Testseite, `noindex`), nutzt dieselbe `ContentBlock`-Datenquelle.
- Mykorrhiza-Textur hier als Haupteinsatzort vorgesehen (immersiver Bereich).

## Nicht Teil der aktuellen Roadmap

- Forum-Funktionalität selbst (Threads, Beiträge, Moderation) — bewusst zurückgestellt, Architektur ist vorbereitet (siehe ROLLENMODELL.md).
- Variante B (SSR-Umzug für Content) — nur dokumentierte Option.
