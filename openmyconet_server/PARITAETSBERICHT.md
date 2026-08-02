# Phase 4 — Paritätsbericht (Schritt 3, erweitert um Ergänzungsauftrag)

Vergleich: Live-Website (statisch, All-Inkl) vs. neue Jinja-Template-Struktur auf Testroute (`/preview/*`, Flask/Hetzner). Grundlage für die Freigabe von Schritt 4 (DNS-Cutover) — **dieser Bericht ersetzt die Freigabe nicht**, er ist die Entscheidungsgrundlage dafür.

**Hinweis zur Struktur dieses Berichts (Ergänzungsauftrag):** Durch die zusätzlichen Punkte 1c–1e (persistenter Audio-Player, neue Seite `medien.html`, Medien-Auslagerung + neue Förderer-Sektion auf `index.html`) ist dies keine reine 1:1-Parität mehr für alle Seiten. Drei Seiten (`leihgeraete.html`, `quellennachweise.html`, `foerderer.html`) sind weiterhin echte 1:1-Paritätsvergleiche. `index.html` hat eine bewusste inhaltliche Abweichung (siehe eigener Abschnitt). `medien.html` ist neu, dafür gibt es keinen Vorher-Vergleich, nur eine funktionale Prüfung. Der persistente Player hat einen eigenen Testpunkt.

## Geprüfter Umfang

Alle 5 Hauptseiten migriert bzw. neu erstellt und geprüft: `index.html`, `leihgeraete.html`, `quellennachweise.html`, `foerderer.html`, `medien.html` (neu).

**Pro Seite geprüft:**
- Server-seitiges Rendering ohne JavaScript (per `curl`, für alle 5 Sprachen bzw. Stichprobe DE/FR/ES) — Text erscheint bereits im Roh-HTML in der richtigen Sprache, nicht erst nach Client-JS.
- Client-seitiges Instant-Umschalten per Flaggen-Klick (kein Reload) — funktioniert weiterhin unverändert on top der SSR-Version.
- Mobiles Menü (Hamburger, Öffnen/Schließen, alle Links).
- Formulare und interaktive Elemente je Seite (siehe unten).
- Konsolenfehler (keine gefunden, auf allen 4 Seiten, in allen getesteten Sprachen).
- Regressionscheck: nach jeder neu hinzugefügten Seite wurden die bereits migrierten erneut aufgerufen, keine Verschlechterung festgestellt.

**Seitenspezifisch zusätzlich geprüft:**
- `index.html`: Spenden-Slider + Gebührenberechnung, Förderer-Rollen-Formularlogik (Formularfelder deaktivieren sich korrekt), Node-Bewerbungspanel (Öffnen/Schließen), alle 5 dynamischen Array-Bereiche (Vision-Kacheln, Karten, Schritte, Datenfluss, Fakten) — jetzt zusätzlich serverseitig vorgerendert statt nur clientseitig. **Content-Block-Overlay aus Phase 1 (`applyContentBlocks`) strukturell verifiziert** — unverändert übernommen, funktioniert automatisch weiter, da rein über `data-i18n`-Attribut-Matching läuft.
- `foerderer.html`: eigener `NAV_LABELS`/`data-foerderer-i18n`-Mechanismus komplett abgelöst, nutzt jetzt dieselbe Nav wie alle anderen Seiten.
- `quellennachweise.html`: Akkordeon (mobil) und Fortschrittspfad (Desktop) inkl. Scroll-basiertem Highlighting.

## Bewusste Abweichungen vom Live-Stand (mit Begründung)

1. **Nav-Innenabstand (Padding) leicht vereinheitlicht.** `index.html` hatte `0.75rem`, die anderen 3 Seiten `1rem` — jetzt einheitlich `1rem` (index.html-Wert wurde in seinem eigenen `extra_css`-Block beibehalten und überschreibt das gemeinsame CSS wieder auf `0.75rem`, tatsächlich also **keine sichtbare Änderung** für index.html; die Angleichung betrifft nur die gemeinsame Basis für künftige neue Seiten).
2. **`nav-active`-Hervorhebung jetzt einheitlich über eine `current_page`-Variable gesteuert** (vorher: uneinheitlich, z.B. hatte `quellennachweise.html` sie im Desktop-Menü, `index.html` nur scroll-basiert). Funktional gleichwertig, Implementierung vereinheitlicht.
3. **Mobiles Menü — "Leihgerät"-Link-Konsistenz.** Original: `index.html` und `foerderer.html` hatten einen einfachen "Leihgerät"-Link, `leihgeraete.html` selbst einen hervorgehobenen Self-Link, `quellennachweise.html` **gar keinen**. Dieser Unterschied wurde 1:1 übernommen (auch die Lücke bei `quellennachweise.html` — nicht eigenmächtig ergänzt, da nicht Teil dieses Auftrags).
4. **Sprachflaggen im mobilen Menü** (`lang-flags-mobile`) gab es bisher nur auf `index.html`/`leihgeraete.html`. Jetzt in `base.html` für alle Seiten verfügbar — `foerderer.html`/`quellennachweise.html` zeigen sie jetzt zusätzlich mobil an (kleine, unschädliche Verbesserung, kein Verlust).

## Ergänzungsauftrag: index.html, medien.html, persistenter Player

### index.html — bewusste inhaltliche Abweichung (kein Paritätsziel mehr)

Auf Wunsch (Ergänzungsauftrag 1b/1c) wurden folgende Inhalte aus `index.html` entfernt und nach `medien.html` verschoben: Broschüre-Sektion, Buch-Teaser + Buch-Sektion, `#willkommen-music`-Sektion (Text übernommen, bespoke Mini-Player `ltf-audio` entfällt, siehe unten). Der freiwerdende Platz zwischen `daten`- und `spenden`-Sektion enthält jetzt eine neue "Förderer & Kooperationen"-Sektion (kompakte Darstellung, aktuell nur GPG-Projekt GmbH bestätigt, Link zur vollständigen `foerderer.html`). Dies ist **kein Parität-Bug**, sondern die gewünschte, dokumentierte Strukturänderung. Geprüft: Seite rendert fehlerfrei, alle verbleibenden Original-Sektionen (Hero, Vision, Warum, Mitmachen, Daten, Spenden, Anmelden, Über) unverändert vorhanden und funktional wie zuvor.

Der Hero-Player zeigt jetzt 5 statt 4 Tracks (siehe Player-Abschnitt unten) — bewusste Vereinheitlichung, da `willkommen-music`s Track "Listen to the Forest" jetzt Teil derselben zentralen Playlist ist statt eines separaten Mini-Players.

### medien.html — neu, funktionale Prüfung statt Parität

Kein Vorher-Vergleich möglich (Seite existierte nicht). Geprüft: Broschüre-Sektion (Download-Link, Untertitel-Ersetzung für `<em>`-Hervorhebung in allen Sprachen), Musik-Sektion (volle Playlist-Ansicht, siehe Player-Abschnitt), Buch-Teaser + Buch-Sektion (Download-Link). Neuer Nav-Eintrag "Medien" erscheint korrekt zwischen "Über" und "Förderer" (Desktop + mobiles Menü), i18n-Label in allen 5 Sprachen ergänzt. Keine Konsolenfehler.

**Bekannte, bewusst übernommene Alt-Lücke:** Der Text der Musik-Sektion (aus `#willkommen-music` übernommen) war auf der Live-Seite nie an die Übersetzung angebunden und bleibt dies auch auf `medien.html` — bleibt auf allen Sprachen Deutsch (siehe auch nächster Abschnitt, gleiche Kategorie wie die bereits bekannten Alt-Lücken).

### Persistenter Audio-Player — eigener Testpunkt

Zentralisiert in `base.html` (Audio-Element + FAB + Playlist-Logik), dadurch auf allen 5 Seiten einheitlich verfügbar. Track-Manifest um "Listen to the Forest" auf 5 Tracks erweitert (vorher 4 im Hero-Player + 1 separat in `willkommen-music`).

**Getestet (lokal, `/preview/*`):**
- Track abspielen auf `medien.html` → Navigation zu `foerderer.html` (kein großer Player dort, nur FAB) → keine Konsolenfehler, Zustand (Track, Position, Lautstärke, Mute) korrekt in `localStorage` gespeichert.
- FAB-Mute-Klick auf `foerderer.html` funktioniert (Mute/Volume sind die einzigen FAB-Funktionen, wie im Ergänzungsauftrag spezifiziert — Play/Pause/Track-Wahl nur über die große Player-Ansicht).
- Navigation zurück zu `index.html` → Track, Position (auf die Sekunde genau), Mute-Status und aktives Cover-Bild korrekt wiederhergestellt — bewusst **pausiert**, kein Autoplay-Versuch (Browser-Autoplay-Policy würde das ohnehin blockieren). Klick auf Play setzt exakt an der gespeicherten Position fort, kein Neustart von vorne.
- Alle Konsolen durchgehend fehlerfrei über die getestete Navigationskette (`medien` → `foerderer` → `index`) sowie auf `quellennachweise`/`leihgeraete` (kein großer Player dort, nur FAB — keine Fehler durch fehlende Playlist-Elemente, da alle DOM-Zugriffe defensiv geprüft sind).

**Bekannte, akzeptierte Grenze (kein Bug):** Automatisches Fortsetzen der Wiedergabe direkt nach einem Seitenwechsel ist technisch nicht sauber erreichbar (Browser-Autoplay-Policy blockiert `audio.play()` ohne Nutzergeste) — genau wie im Ergänzungsauftrag als bekannte Einschränkung benannt. Die gewählte Lösung (Zustand wiederherstellen, aber pausiert lassen, ein Klick setzt fort) erfüllt das Ziel "gefühlt nahtlos" ohne die Browser-Policy zu umgehen.

**Nebenbei gefunden und behoben:** `foerderer.html` verlinkte noch auf die alte PHP-Antragsseite (`foerderer-antrag.php`) statt auf die in Schritt 3b gebaute Flask-Route (`/foerderer/antrag`) — sowohl im Testroute-Template als auch **in der aktuell live geschalteten statischen Seite** (`www.openmyconet.de/foerderer.html`). Lokale Datei korrigiert; **Upload der korrigierten Datei nach All-Inkl steht noch aus** (nicht Teil dieses Testroute-Berichts, siehe Hinweis an Robby).

## Bekannte, bewusst NICHT behobene Alt-Lücken (1:1-Parität gewahrt)

Bei der Migration von `index.html` zusätzlich gefunden, aber **nicht behoben**, um exakte Parität mit dem Live-Stand für diesen Bericht zu wahren:

- Abschnitt „Für die ersten Schritte im Netzwerk" (`#willkommen-music`, 4 Textstellen) hat nie eine Übersetzungsanbindung gehabt — bleibt auf allen Sprachen Deutsch, wie live.
- `#node-panel-label` ("Bewerbung", Label über dem Bewerbungsformular-Titel) ist ebenfalls nie angebunden gewesen — bleibt Deutsch.

**Empfehlung:** Diese zwei Stellen als eigenen kleinen Folgeauftrag beheben (gleiches Muster wie der `leihgeraete.html`-Bridge-Fix aus der vorherigen Session) — unabhängig von Phase 4, jederzeit nachholbar.

## Nicht Teil dieses Berichts

- Schritt 3b (Förderer-PayPal/PDF-Migration) — **abgeschlossen**, live auf `api.openmyconet.de` mit echtem PayPal-Sandbox-Test verifiziert (siehe ROADMAP.md und Projekt-Memory), unabhängig von dieser Testroute.
- Kooperationen-Inhalt über GPG-Projekt GmbH hinaus (z.B. KleingartenLAN) — hängt an einer Content-Freigabe durch Robby, welche Kooperationen zum jetzigen Zeitpunkt öffentlich genannt werden dürfen.
- Schritt 4 (DNS-Cutover) — **wird an dieser Stelle explizit nicht ausgeführt**, benötigt gesonderte Freigabe.

## Fazit

Alle 5 Seiten laufen auf der Testroute mit identischem bzw. (bei `index.html`/`medien.html`) bewusst geändertem Ergebnis wie live, plus dem SSR-Vorteil (Suchmaschinen sehen jetzt direkt die korrekte Sprachversion). Persistenter Audio-Player funktioniert seitenübergreifend wie spezifiziert. Keine ungewollten Funktionsverluste festgestellt. Ein pre-existing Bug (`foerderer.html`-Antragslink) wurde nebenbei gefunden und lokal behoben, Live-Upload steht aus. Bereit für die Freigabe von Schritt 4, sobald gewünscht.
