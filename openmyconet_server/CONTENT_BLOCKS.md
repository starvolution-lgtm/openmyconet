# Content-Anschluss (ContentBlock ↔ Frontend)

## Umgesetzt (Phase 1, index.html)

- **Namensraum-Konvention:** `schluessel` = `<seite>_<key>`, z.B. `index_hero_sub`. Kein Schema-Change nötig — reine String-Konvention, verhindert Kollisionen zwischen Seiten mit gleichnamigen Keys (z.B. `btn_contact` auf mehreren Seiten).
- **Bulk-Endpoint:** `GET /api/v1/content?seite=<seite>&sprache=<lang>` (app.py) — liefert alle Blöcke mit `schluessel LIKE '<seite>_%'` als `{schluessel: inhalt}`-Dict. Der bestehende Einzel-Key-Endpoint (`/api/v1/content/<schluessel>`) bleibt unverändert bestehen.
- **Seed:** `seed_content_index.py` — einmalig, idempotent, überträgt die bisher in `translations.js` hart kodierten 52 Textstellen (alle `data-i18n`/`data-i18n-html`-Keys aus index.html, 5 Sprachen = 260 Zeilen) als Startwerte in `ContentBlock`. Danach sind sie über `/admin/inhalte` editierbar.
- **Frontend (index.html):** neue Funktion `applyContentBlocks(lang)`, aufgerufen direkt nach `applyTranslations(lang)` — sowohl im initialen `DOMContentLoaded`-Handler als auch in `setLang()`. Sie fetcht den Bulk-Endpoint und überschreibt dieselben `[data-i18n]`/`[data-i18n-html]`-Elemente mit dem DB-Inhalt.
  - **Fallback-Prinzip:** `applyTranslations()` rendert immer zuerst aus dem statischen `TRANSLATIONS`-Objekt (kein Netzwerk nötig, kein Layout-Flackern). Der API-Fetch überlagert das nur bei Erfolg; schlägt er fehl (API down, CORS, offline), bleibt der statische Text stehen — stiller Catch, kein Fehler für den Besucher sichtbar. Die Website bleibt also auch bei Backend-Ausfall voll funktionsfähig.
  - Getestet lokal: Bulk-Endpoint liefert korrekt 52 Keys zurück, DOM-Überlagerung funktioniert für `data-i18n` (textContent) und `data-i18n-html` (innerHTML, inkl. `<em>`-Tags in den `h2_*`-Keys), Fallback bei blockiertem/fehlgeschlagenem Fetch funktioniert ohne JS-Fehler.

## Vorgehen für die übrigen 3 Seiten (foerderer.html, quellennachweise.html, leihgeraete.html)

Gleiches Muster, kein neuer Code nötig — nur pro Seite:

1. Die verwendeten `data-i18n`/`data-i18n-html`-Keys der Seite auflisten (analog zur 52er-Liste für index.html).
2. Ein Seed-Skript `seed_content_<seite>.py` nach dem Muster von `seed_content_index.py` schreiben (Werte aus der jeweiligen Übersetzungsquelle — bei `foerderer.html` Achtung: eigenes `NAV_LABELS`/`data-foerderer-i18n`-System statt `translations.js`, siehe Website-Memo).
3. In der jeweiligen HTML-Datei `applyContentBlocks('<seite>')` nach der bestehenden Übersetzungsfunktion einhängen (Funktion selbst muss nicht dupliziert werden, falls die Seiten sie sich teilen könnten — aktuell hat aber jede Seite ihr eigenes embedded `<script>`, siehe Website-Memo zu fehlendem Shared-Template).
4. Bulk-Endpoint ist bereits generisch (`?seite=<seite>`) — keine Backend-Änderung nötig.

Reihenfolge nach Textumfang: index.html (✓ erledigt) → quellennachweise.html (sehr textlastig) → foerderer.html → leihgeraete.html.

## Variante B (SSR über Flask) — dokumentierte Option, nicht umgesetzt

**Idee:** Statt client-seitigem Fetch + DOM-Ersetzung würde Flask die Seiten serverseitig rendern (Jinja-Templates statt statischer HTML-Dateien auf dem All-Inkl-Webspace), Content-Blocks und Übersetzungen direkt beim Request einsetzen.

**Vorteil gegenüber Variante A:** Löst das bestehende hreflang/Duplicate-Content-Problem strukturell — Suchmaschinen-Crawler bekämen den tatsächlich richtigen Inhalt pro Sprache direkt in der Server-Antwort statt eines clientseitig nachträglich veränderten DOM. Aktuell (Variante A) sieht ein Crawler, der kein JS ausführt, nur die deutsche Default-Version.

**Nachteile / Aufwand:**
- Kompletter Hosting-Wechsel: die 4 statischen Seiten liegen auf All-Inkl (PHP-Webspace), das Flask-Backend läuft separat auf dem Hetzner-VPS (`api.openmyconet.de`) — SSR würde bedeuten, dass die öffentliche Website selbst vom Flask-Server ausgeliefert wird, nicht mehr von All-Inkl. Das ist ein Infrastruktur-Umzug, kein Feature-Zusatz.
- Alle 4 Seiten müssten von statischem HTML in Jinja-Templates überführt werden (aktuell: pro Seite komplett eigenständiges, unabhängig dupliziertes `<style>`/`<script>` ohne Shared-Template — siehe Website-Memo).
- DNS/Domain-Routing müsste angepasst werden (`www.openmyconet.de` zeigt aktuell auf All-Inkl, nicht auf den Hetzner-VPS).
- Deutlich größerer Umbau als der jetzige, risikoarme Fetch-Ansatz.

**Empfehlung:** Nur angehen, wenn das hreflang/Duplicate-Content-Problem in der Google Search Console tatsächlich zum echten SEO-Problem wird (aktuell nur ein bekanntes, nicht akutes Risiko). Variante A + saubere `hreflang`/`canonical`-Tags (bereits teilweise vorhanden, siehe Website-Memo zum canonical-Fix vom 2026-07-23) deckt einen Großteil des Risikos ohne den Infrastruktur-Umzug ab.
