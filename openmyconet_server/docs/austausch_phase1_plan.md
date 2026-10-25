# Austauschbereich Phase 1 – Umsetzungsplan (Fachkontakte einladen)

Stand: 25.10.2026, überarbeitet mit Robbys Anmerkungen (Themenräume, Übersetzung in 5 Sprachen)
Grundlage: Auftrag „auftrag_austauschbereich_phase1_ergaenzt.md“ + Codeanalyse
Status: **Plan, noch kein Produktivcode geändert.**

**Änderungen in dieser Fassung:**
- Phase 1 unterstützt die **5 Sprachen der Website** statt nur DE/EN, und es gibt keine eigene Spracheinstellung
  für den Austausch (Abschnitte 1.2 und 4).
- **Neu: Phase 2 „Wissenschaftliche Themenräume“** mit Übersetzung der Beiträge (Abschnitt 8). Die bisherigen
  Phasen 2 und 3 des Auftrags rücken auf 3 und 4.
- **Entscheidungen vom 25.10. übernommen:** Gültigkeit und Erneuerung, Fristen F1–F5 samt Einordnung in
  `aufbewahrung.py` (Abschnitt 5), „Fachkontakt“ nur intern, Anrede „Sie“ als Standard (Abschnitt 4).
  Rechtliche Prüfung der Löschregeln ist Voraussetzung für die Produktivfreigabe. Phase 2 bleibt
  Architekturplan.
- **Identitätsprüfung (Robbys Anmerkung, 25.10.):** Der Einladungslink allein reicht nicht mehr. Beim Annehmen
  geht ein 6-stelliger Code an die eingeladene Adresse, erst dieser löst ein (Abschnitt 3). Neu ist auch die
  Regel bei Kontolöschung (Abschnitt 3, Schritt 7).

---

## 0. Kernaussage in drei Sätzen

1. Eingeladene Fachkontakte bekommen eine **eigene kleine Tabelle `austausch`**. Die Aufgaben, Kommentare,
   Anhänge und Benachrichtigungen des bestehenden Kollaborationsbereichs (`omn/kollaboration.py`) werden
   unverändert weiterverwendet. Dafür kommt nur ein dritter „Kontext“ neben Kooperation und Knoten hinzu.
2. Die Tabelle `foerderer` wird **bewusst nicht** wiederverwendet. Jeder Eintrag dort mit `status='active'`
   erscheint **automatisch öffentlich auf der Startseite/Fördererseite** (`site_live.py:20`, `_aktive_foerderer()`).
   Außerdem setzt die Freigabe dort die Rolle Hyphist (`admin/foerderer.py:80`). Beides muss für Fachkontakte
   ausgeschlossen sein.
3. Die Einladung bekommt einen **eigenen, gehashten Einmal-Token** mit Bestätigungsseite. Der vorhandene
   Login-Token ist dafür nicht geeignet (siehe Abschnitt 3).

---

## 1. Antworten auf „Vor dem Codieren zu klären“

### 1.1 Was wird wiederverwendet?

| Vorhanden | Wiederverwendung |
|---|---|
| `Aufgabe`, `Kommentar`, `KollaborationAnhang` (models.py) | ja, bekommen je eine zusätzliche Spalte `austausch_id` (FK, nullable, CASCADE) – wie heute `foerderer_id`/`knoten_id` |
| `kollaboration.kontext_filter`, `aufgaben_fuer`, `kommentare_fuer`, `post_verarbeiten`, `_anhang_speichern` | ja, `kontext_filter` lernt den dritten Kontexttyp `Austausch`; der Rest läuft automatisch mit |
| `kollaboration._benachrichtige` | ja, mit eigenem Zweig für `Austausch` (neutrale Texte, DE/EN, eigene Links) |
| `anhang_sichtbar_fuer_nutzer` + Download-Route `/dashboard/kollaboration/datei/<id>` | ja, um den Austausch-Fall ergänzt (URL ist neutral) |
| Magic-Link-Session (`session['nutzer_logged_in']`, `nutzer_id`), `login_required`, `anmeldelink_erzeugen` | ja, für das Einloggen nach der Einladung |
| `transaktions_email.html`, `dashboard_base.html` | ja, beide enthalten keine Förder-/Zahlungsbegriffe (geprüft) |
| `kollaboration_admin.html` | ja, mit neuem `modus='austausch'` (der Zurück-Link zur „Förderer-/Kooperationsverwaltung“ muss dann umschaltbar werden; Admin-Seite, aber laut Auftrag auch dort neutral halten) |
| CSRF (`schuetze_blueprint`), Audit-Log (`protokollieren`), `post_knopf`-Makro | ja |
| Löschfristen `omn/aufbewahrung.py` (`FRISTEN`) | ja, neue Einträge |
| Rechtstexte `omn/rechtstexte.json` (5 Sprachen, `de` maßgeblich) | ja, neuer Abschnitt |
| **`Foerderer`, `roles.py`, `kooperationen_von`, `foerderer_verfall_pruefen.py`** | **nein, bewusst nicht angefasst** |

### 1.2 Neue Tabelle `austausch` (neue Tabelle → `timestamptz`, tz-aware nach Regel vom 23.09.)

| Spalte | Typ | Sichtbar für | Zweck |
|---|---|---|---|
| `id` | int PK | – | |
| `titel` | str(200) | beide | Name des Austauschs, z. B. „Elektrophysiologie an Pilzmyzel“ |
| `themenueberblick` | text | beide | vom Admin verfasster Überblick (Anforderung 8) |
| `name` | str(100) | Admin | Anzeigename der eingeladenen Person |
| `institution` | str(200), leer erlaubt | Admin | „Institution oder privat“ (kein Pflichtfeld) |
| `email` | str(150) | Admin | Einladungsadresse |
| `sprache` | str(10), eine der 5 Website-Sprachen | – | **nur** Sprache der Einladungsmail und der Bestätigungsseite (da gibt es noch kein Konto). Beim Einlösen wird sie bei einem **neuen** Konto als `Nutzer.sprache` übernommen; danach gilt nur noch die normale Spracheinstellung (siehe 4) |
| `status` | str(20) | – | `vorbereitet` → `eingeladen` → `aktiv` → `beendet` / `gesperrt` (bewusst **nicht** `active`, siehe 1.5). `beendet` = Austausch regulär abgeschlossen, `gesperrt` = Zugang entzogen; für beide gilt die Frist F4 |
| `status_geaendert_am` | timestamptz | Admin | Beginn der Frist F4 |
| `anrede` | str(10) | – | `formell` / `informell`; Standard `formell` (Entscheidung 4, siehe 4) |
| `persoenliche_einleitung` | text, leer erlaubt | beide (nur in der Einladungsmail) | optionaler eigener Einleitungssatz für die Einladung („individuelle Ansprache“) |
| `geprueft_am` | timestamptz | Admin | Inaktivitätsprüfung F2 erledigt |
| `loeschsperre_bis`, `loeschsperre_grund` | date / str(300) | Admin | berechtigter Aufbewahrungsgrund, setzt F1/F3/F4 aus (5.1) |
| `nutzer_id` | FK nutzer, nullable | – | wird erst beim Einlösen gesetzt |
| `linkedin_url` | str(255) | **nur Admin** | Profil-Link |
| `gespraech_begonnen_am` | date | **nur Admin** | Gesprächsbeginn |
| `vorgeschichte_notiz` | text | **nur Admin** | nur Robbys eigene Zusammenfassung, keine kopierten LinkedIn-Texte (Hinweis am Eingabefeld) |
| `einladung_token_hash` | str(64), unique, nullable | – | SHA-256 des Einladungstokens |
| `einladung_gueltig_bis` | timestamptz | – | Ablauf (Vorschlag 14 Tage) |
| `code_hash`, `code_gueltig_bis`, `code_fehlversuche`, `codes_angefordert_am` | str(64) / timestamptz / int / Liste bzw. Zähler | – | Bestätigungscode beim Annehmen (siehe 3) |
| `eingeladen_am`, `eingeloest_am` | timestamptz | Admin | Nachweis |
| `erstellt_am`, `letzte_aktivitaet` | timestamptz | Admin | Basis für Löschfrist/Inaktivität |

Kein Logo-Feld, kein Betrag, keine Kategorie, keine Phase mit Geldbezug (Anforderung „Admin-Ansicht neutral“).

**Felder, die erforderlich sind:** genau die erwarteten fünf (LinkedIn, Gesprächsbeginn, interne Notiz,
Sprache, Themenüberblick), dazu Name/Institution/E-Mail/Titel für die Einladung selbst und die technischen
Token-/Statusfelder. Mehr nicht.

### 1.3 Zuordnung Nutzer ↔ Austauschbereich

- **Ausschließlich über `austausch.nutzer_id`**, gesetzt beim Einlösen. **Kein E-Mail-Fallback**, anders als
  bei `kooperationen_von()`: Dort reicht heute gleiche E-Mail-Adresse, hier nicht.
- Eine zentrale Funktion `austausch_bereiche_von(nutzer)` (nur `status='aktiv'` und `nutzer_id == nutzer.id`)
  und eine Prüfung `darf_austausch_sehen(nutzer, austausch)`. **Alle** Routen nutzen nur diese beiden. Das ist
  der Anknüpfungspunkt für Phase 3 (mehrere Teilnehmer): Dort wird nur der Inhalt dieser Funktionen auf eine
  Teilnehmertabelle umgestellt.

### 1.4 Ist der vorhandene Magic-Link für Einladungen geeignet? – **Nein, nur in Teilen**

Befund `omn/dashboard.py`:

| Anforderung | Login-Link heute | Bewertung |
|---|---|---|
| einmalig + zeitlich begrenzt | ja (30 min, wird beim Aufruf verbraucht) | ok |
| Token nur als Hash gespeichert | **nein**, `Nutzer.login_token` steht im Klartext in der DB | erfüllt die Anforderung nicht |
| Schutz vor Mail-Scannern | **nein**, schon das GET auf `/dashboard/auth/<token>` löst ein und loggt ein | erfüllt die Anforderung nicht |
| funktioniert ohne Konto | **nein**, setzt bestehenden, bestätigten Nutzer voraus | ungeeignet |
| kein Überschreiben | jede Anforderung überschreibt den Token | ungeeignet für eine 14-Tage-Einladung |

**Vorschlag:** ein eigener Einladungstoken in der Tabelle `austausch` (siehe 3). Der normale Login-Link wird
nur **danach** verwendet, beim bestehenden Konto (siehe 3, Schritt 4b).
Hinweis außerhalb des Auftrags: Klartext-Token und Einlösung schon beim Öffnen gelten auch für den normalen
Login-Link. Beides könnte man später ebenso absichern, das wäre eine eigene kleine Aufgabe.

### 1.5 Trennung von Freigabe, formeller Kooperation und Mitgliedsstufe

| Begriff | Wo gespeichert | Wird von der Einladung berührt? |
|---|---|---|
| Freigabe Arbeitsbereich | `austausch.status = 'aktiv'` | ja, nur das |
| Formelle Kooperation | `foerderer.typ='kooperation'`, `status='active'` | **nein**, andere Tabelle |
| Mitgliedsstufe Hyphist/Sporist | `nutzer.ist_hyphist` / `ist_sporist` | **nein**, kein Aufruf von `roles.py` |
| „Fachkontakt“ | wird **nicht** als Feld gespeichert, sondern abgeleitet: „hat mindestens einen `austausch` mit `nutzer_id`“ | – |

Damit greifen alle bisherigen Prüfungen automatisch nicht: Hyphist-Seite (`kooperationen_von`), Startseiten-
und Fördererliste (`_aktive_foerderer`), Verfallsprüfung und Admin-Rollenfilter. Für „Fachkontakt“ braucht es
**kein neues Rollenfeld**. Ob es als Label sichtbar sein soll (offener Punkt), ist dann nur eine
Anzeigefrage.

### 1.6 Änderungen an bestehenden Nutzern und Routen

- **Keine Änderung** an bestehenden Nutzerdaten, Rollen oder Kooperationen. Die Migration legt nur die neue
  Tabelle und zwei leere FK-Spalten an.
- `dashboard.home()` bekommt **eine** zusätzliche Weiterleitung: Wer einen aktiven Austausch hat, landet auf
  `/austausch`. Reihenfolge: Knoten → Hyphist → **Austausch** → Bewerber → Basis. Bestehende Wege bleiben
  vorrangig.
- `dashboard_base.html`: ein Navigationslink „Austausch“ / „Exchange“, nur wenn vorhanden.
- `kollaboration.py`: `kontext_filter`, `_kooperation_aktivitaet_markieren` (setzt künftig zusätzlich
  `letzte_aktivitaet` beim Austausch), `_benachrichtige`, `anhang_sichtbar_fuer_nutzer` bekommen je einen
  Austausch-Zweig. Die Zweige für Förderer und Knoten bleiben Zeile für Zeile gleich.

### 1.7 Welche Tests sichern die bisherigen Funktionen ab?

Vorhanden und müssen grün bleiben: `test_kollaboration.py` (12), `test_foerderer.py` (19), `test_csrf.py`,
`test_aufbewahrung.py`, `test_migrations.py` (Schema-Drift, Null-Toleranz → erzwingt eine saubere Migration)
sowie die übrige Suite. Neue Tests stehen in Abschnitt 6.

---

## 2. Neue Routen (alle neutral, ohne „foerderer“/„kooperation“ in der URL)

| Route | Methode | Wer | Zweck |
|---|---|---|---|
| `/austausch/einladung/<token>` | GET | anonym | **Bestätigungsseite**, ändert nichts (Scanner-sicher) |
| `/austausch/einladung/<token>` | POST (CSRF) | anonym | Einladung einlösen |
| `/austausch` | GET/POST | eingeloggter Nutzer | eigener Arbeitsbereich (Aufgaben + Kommentare über `post_verarbeiten`) |
| `/admin/austausch` | GET | Superadmin | Liste aller Austauschbereiche |
| `/admin/austausch/neu` | GET/POST | Superadmin | Einladung vorbereiten |
| `/admin/austausch/<id>` | GET/POST | Superadmin | Arbeitsbereich (Team-Seite) und interne Box (LinkedIn, Notiz, Beginn) |
| `/admin/austausch/<id>/einladen` | POST | Superadmin | Einladung (neu) senden; ein neuer Token macht den alten ungültig |
| `/admin/austausch/<id>/sperren` · `/entsperren` · `/loeschen` | POST | Superadmin | Zugang entziehen oder löschen |

Ort im Code: Nutzerseite in einem neuen Blueprint `omn/austausch.py` (mit `schuetze_blueprint`, eigene
Templates `austausch_*.html` auf Basis `dashboard_base.html`), Adminseite als neues Fachmodul
`omn/admin/austausch.py` am bestehenden `admin_bp`. Jede ändernde Admin-Route ruft `protokollieren(...)` auf
und kommt in `test_csrf.py::AENDERNDE_ADMIN_ROUTEN`. Neue öffentliche Seite → laut `docs/claude/website.md`
prüfen, ob sie in `SEITEN_GRUPPEN`/Audit-Listen gehört: **Nein**, die Einladungsseite ist privat,
`noindex`, kommt also nicht in `llms.txt`.

---

## 3. Ablauf der Einladung (Sicherheit)

1. **Admin bereitet vor** (`/admin/austausch/neu`): Name, E-Mail, Institution (optional), Sprache, Titel,
   Themenüberblick, interne Felder → `status='vorbereitet'`. Noch keine Mail.
2. **Admin sendet Einladung** (POST): `token = secrets.token_urlsafe(32)`, gespeichert wird nur
   `sha256(token)`, `gueltig_bis = jetzt + 14 Tage`, `status='eingeladen'`. Die Mail geht in der gewählten
   Sprache raus. Sie enthält den Pflichtsatz zur Unabhängigkeit von finanzieller Unterstützung, einen kurzen
   Datenschutzhinweis (Art. 14) mit Link zur Datenschutzerklärung und den Link. **In der URL steht nur der
   Token**, kein Name und keine E-Mail.
3. **GET Bestätigungsseite:** sucht über den Hash. Bei unbekanntem, abgelaufenem oder benutztem Token kommt
   **dieselbe** neutrale Fehlermeldung (kein Hinweis darauf, ob es den Token gab). Bei gültigem Token
   erscheinen Titel, Themenüberblick, der Datenschutzhinweis (zweites Mal, wie gefordert) und der Knopf
   „Einladung annehmen“. **Keine Datenänderung**, `noindex`, `Referrer-Policy: no-referrer`.
4. **Annehmen löst noch nichts ein (überarbeitet nach Robbys Anmerkung vom 25.10.).** Ein Klick auf den
   Einladungslink beweist nur, dass jemand die Mail **hatte**. Er beweist nicht, dass die eingeladene Person
   selbst handelt, denn die Mail kann weitergeleitet worden sein. Deshalb wird die Identität **in dem Moment**
   geprüft, in dem jemand annimmt:
   - **POST „Einladung annehmen“:** Das System schickt einen **6-stelligen Bestätigungscode** an die
     eingeladene Adresse, aus der Datenbank und **nicht** aus dem Link. Gespeichert werden nur der Hash des
     Codes, Ablauf (15 min) und Fehlversuche. Die Austausch-ID kommt in die **Browser-Session**, die
     angenommen hat. Token, Konto und Status bleiben noch unverändert.
   - **Code eingeben** (auf derselben Seite, im selben Browser): Höchstens 5 Fehlversuche, danach ist der Code
     ungültig, und ein neuer muss angefordert werden. Neue Codes gibt es höchstens 3 je Stunde und Einladung.
   - **Erst ein richtiger Code löst ein**, und zwar **atomar** (bedingtes UPDATE
     `… WHERE einladung_token_hash = :h AND eingeloest_am IS NULL`, damit ein Doppelklick nicht zweimal
     einlöst). Danach: `token_hash = NULL`, Code gelöscht, `eingeloest_am`, `status='aktiv'`.
   - Wer die Einladung nur weitergeleitet **bekommen** hat, kommt nicht weiter: Der Code geht an die
     ursprüngliche Adresse. Mail-Scanner kommen ebenfalls nicht weiter, weil sie weder „annehmen“ klicken noch
     einen Code eintippen. Ein Code statt eines zweiten Links ist hier besser, weil ein Link wieder von
     Scannern geöffnet würde.
5. **Nach dem richtigen Code, je nach Konto:**
   - **a) Kein Konto mit dieser E-Mail:** Ein Nutzer wird angelegt mit `bestaetigt=True` (der Code belegt, dass
     die Person die Adresse **jetzt** kontrolliert), `keine_mails=True` (keine Newsletter-Einwilligung),
     `sprache` aus der Einladung, eigener `token` für Abmeldelinks und **keine** Rollenfelder. Dabei wird
     nicht `register_nutzer_core` benutzt, weil das eine überflüssige Double-Opt-in-Mail schicken würde.
   - **b) Konto existiert schon:** Der Austausch wird verknüpft (`nutzer_id`). Rollen, `gruppe` und
     `keine_mails` bleiben **unverändert**. Ein bisher unbestätigtes Konto wird bestätigt, weil die Adresse
     jetzt nachgewiesen ist.
   - **In beiden Fällen** wird die Person danach eingeloggt und landet auf `/austausch`. Der Code ist ein
     mindestens so starker Nachweis wie der normale Login-Link, denn beide gehen an dieselbe Adresse und
     gelten nur kurz. Der zusätzliche Login-Link aus der vorigen Planfassung entfällt deshalb.
   - Ist im Browser gerade ein **anderer** Nutzer eingeloggt, wird er abgemeldet. Der Austausch wird nur dem
     Konto der Einladungsadresse zugeordnet, nie dem gerade eingeloggten.
6. **Rate-Limit** für alle Schritte unter `/austausch/einladung/` über das vorhandene `ip_erlaubt(...)`.
   **Restgröße:** Wer die Einladungsmail **und** den Code bekommt, also nur mit Zutun der eingeladenen Person,
   erhält den Bereich. Das lässt sich technisch nicht verhindern. Sichtbar wird es durch die Anzeige von
   `eingeloest_am` beim Admin, begrenzen lässt es sich mit dem Sperrknopf. Zusätzlich bekommt der Admin eine
   kurze Mail „Einladung angenommen: <Titel>“.
7. **Kontolöschung:** `austausch.nutzer_id` mit `ondelete='SET NULL'`. Wird ein Konto im Admin gelöscht
   (`/admin/nutzer/loeschen`), wird der zugehörige Austausch auf `gesperrt` gesetzt und bleibt für den Admin
   bis zu seiner eigenen Löschung lesbar (Frist siehe Abschnitt 5). Ohne diese Regel würde das Löschen eines
   Kontos auf PostgreSQL am Fremdschlüssel scheitern. Ein Test sichert das ab.

---

## 4. Neutralität und Sprache

- Eigene Templates `austausch_einladung.html`, `austausch_bereich.html` und eigene Mailtexte. Kein Template
  aus `site/foerderer*`, kein Footer mit Spendenlink. `dashboard_base.html` und `transaktions_email.html`
  sind bereits neutral (geprüft).
- **Sprachen (geändert): alle 5 Website-Sprachen (de, en, nl, fr, es), keine eigene Spracheinstellung für
  den Austausch.**
  - *Feste Oberflächentexte* (Seiten, Knöpfe, Mailtexte) kommen wie die übrige Website aus
    `app/static/translations.json` (neue Schlüssel `austausch_*`, alle 5 Sprachen, `de` maßgeblich).
  - *Seiten* (Bestätigungsseite, Arbeitsbereich) zeigen die Sprache, die die Website ohnehin verwaltet
    (`resolve_lang()`, Sprachwahl/Cookie). Beim ersten Aufruf der Bestätigungsseite wird die
    Einladungssprache als Startwert genommen, solange der Besucher noch nichts gewählt hat.
  - *Mails* kennen keinen Cookie. Sie gehen deshalb in der Sprache der Einladung, später in `Nutzer.sprache`.
    Dafür braucht `omn/i18n.py` eine kleine Ergänzung `t(key, lang=None)` mit ausdrücklicher Sprache. Heute
    nimmt `t()` immer die Sprache der laufenden Anfrage.
  - Die vorhandenen Transaktionsmails (Login-Link usw.) sind bisher nur deutsch. Der Login-Link, den Abschnitt 3,
    Schritt 4b verschickt, wird für die Austausch-Nutzer in deren Sprache gebraucht und deshalb mit übersetzt. Die
    übrigen Mails bleiben, wie sie sind.
  - Mails ans Team bleiben deutsch.
  - **Von Nutzern geschriebene Inhalte werden in Phase 1 nicht übersetzt.** Das kommt mit Phase 2
    (Abschnitt 8.4), zunächst nur für die gemeinsamen Themenräume.
- **Anrede (Entscheidung 4, 25.10.):**
  - Feld `austausch.anrede`, beim Anlegen **vorbelegt mit `formell`**. Der Admin kann je Kontakt auf
    `informell` umstellen und zusätzlich einen **persönlichen Einleitungssatz** für die Einladungsmail
    schreiben.
  - Sie gilt für alles, was der Fachkontakt im Austausch-Ablauf sieht: Einladungsmail, Bestätigungsseite,
    Code-Mail, die Seite `/austausch` und Benachrichtigungen an ihn.
  - **Die bestehende Community-Oberfläche bleibt unverändert beim „du“**, also Navigation in
    `dashboard_base.html`, Login-Seite, andere Dashboard-Seiten, Website. Ein formell eingeladener
    Fachkontakt sieht dort also das gewohnte Community-„du“. Das ist so gewollt.
  - Umsetzung: In `translations.json` gibt es die Austausch-Texte, deren Anrede abweicht, in zwei Fassungen
    (`austausch_…_formell` / `austausch_…_informell`). Texte ohne Anrede, etwa Knöpfe, gibt es nur einmal.
  - Je Sprache, **Vorschlag zur Prüfung**:

    | Sprache | formell (Standard) | informell |
    |---|---|---|
    | de | Sie | du |
    | en | you (eine Fassung, Ton etwas förmlicher bei `formell`) | you |
    | nl | u | je/jij |
    | fr | vous | tu |
    | es | usted | tú |

    **Bestätigt am 25.10.:** `formell` ist in allen Sprachen Standard (u / vous / usted). Wo „tú“ oder „je“
    besser passt, etwa im lateinamerikanischen Wissenschaftsbetrieb, stellt der Admin den Kontakt auf
    `informell` um.
- Admin-Seiten: Überschrift „Fachlicher Austausch“, keine Betrags-, Logo- oder Kategoriefelder, kein Link in
  die Förderer-Verwaltung.

---

## 5. Datenschutz und Löschung (Vorschlag – rechtliche Prüfung bleibt bei dir)

Keine Rechtsberatung, aber eine Einordnung als Grundlage für deine Prüfung:

| Daten | Rechtsgrundlage (Vorschlag) | Informationspflicht |
|---|---|---|
| Name, E-Mail, LinkedIn-URL, Gesprächsbeginn, eigene Notiz **vor** Annahme | Art. 6 Abs. 1 lit. f (berechtigtes Interesse an der Fortführung eines begonnenen Fachgesprächs) | Art. 14: Daten stammen zum Teil nicht direkt aus einem Formular der Person → spätestens mit der ersten Mitteilung, also **in der Einladungsmail** |
| Konto, Inhalte im Arbeitsbereich **nach** Annahme | Art. 6 Abs. 1 lit. b (Nutzung des angebotenen Austauschbereichs) | Art. 13: auf der Bestätigungsseite und in der Datenschutzerklärung |
| interne Notiz/LinkedIn **nach** Annahme | weiter lit. f, mit Widerspruchsrecht (Art. 21) | Art. 14, Hinweis bleibt in der Erklärung |

Umsetzung:
- Neuer Abschnitt `austausch` in `omn/rechtstexte.json` (de maßgeblich, en/nl/fr/es nachziehen, `stand`
  aktualisieren), ähnlich dem vorhandenen Abschnitt `kontaktaufnahme`. Inhalt: Zweck, Rechtsgrundlagen,
  Herkunft der Daten (eigene Notizen aus einem LinkedIn- oder Mail-Gespräch), Empfänger (keine neuen
  Auftragsverarbeiter, Mail über den bestehenden Versand), Fristen, Widerspruch und Löschung.
- **Fristen und Inaktivität – festgelegt von Robby am 25.10.2026.** Die **rechtliche Prüfung dieser
  Löschregeln ist Voraussetzung für die Produktivfreigabe**, siehe 5.2.

### 5.1 Festgelegte Fristen

| # | Regel | Beginn der Frist | Wirkung | Umsetzung |
|---|---|---|---|---|
| F1 | Nicht angenommene Einladung | `eingeladen_am` (bei Erneuerung neu gesetzt) | nach **2 Jahren** ganzer Austausch gelöscht (geändert 25.10. nach der Rechtsprüfung: dieselbe Frist wie MCC-Kontakte), inkl. vom Team schon angelegter Aufgaben/Kommentare/Dateien | Löschfunktion (5.3) |
| F2 | Inaktivität | `letzte_aktivitaet` | nach **12 Monaten** im Admin **zur Prüfung markiert**, **keine** automatische Sperrung oder Löschung | Anzeige (5.4) |
| F3 | Interne Kontaktnotizen (LinkedIn-URL, Gesprächsbeginn, Vorgeschichte) | `letzte_aktivitaet` | nach **24 Monaten** ohne Aktivität **geleert**; der Austausch selbst bleibt | `LEEREN` in `aufbewahrung.py` |
| F4 | Gesperrter oder beendeter Austauschbereich | `status_geaendert_am` | nach **6 Monaten** ganz gelöscht, inkl. aller Aufgaben, Kommentare und **Dateien** | Löschfunktion (5.3) |
| F5 | Löschwunsch der betroffenen Person | sofort, unabhängig von F1–F4 | Admin-Knopf „Auf Wunsch löschen“: Austausch inkl. Dateien sofort weg; optional zusätzlich das Konto | Löschfunktion (5.3) + Audit-Log |

**Ausnahme „berechtigter Aufbewahrungsgrund“** (gilt für F1, F3, F4, nie für F5 ohne eigene Prüfung): Der
Admin kann je Austausch eine **Löschsperre** setzen. Pflicht ist ein Grund, zum Beispiel laufende
Auseinandersetzung, Nachweispflicht oder Wunsch der Person. Eine Sperre ohne Grund ist nicht möglich. Die
Sperre gilt bis zu einem Datum (`loeschsperre_bis` + `loeschsperre_grund`). Läuft sie ab, greifen die Fristen
wieder. Die Sperre wird im Audit-Log protokolliert. Ohne Sperre löscht das System automatisch, es entscheidet
also niemand stillschweigend.

**Erneuerung (Entscheidung 1):** „Einladung erneuern“ erzeugt einen neuen Token mit 14 Tagen Gültigkeit und
setzt `eingeladen_am` neu. Damit beginnt auch F1 neu. Der alte Link wird ungültig.

**F1a (bestätigt am 25.10.):** Ein Austausch, der nur **vorbereitet** und nie verschickt wurde, wird ebenfalls
nach **einem Monat** (ab `erstellt_am`) gelöscht (geändert 25.10. nach der Rechtsprüfung, Art. 14 Abs. 3 lit. a DSGVO); nach drei Wochen geht einmal eine Erinnerungsmail an den Admin.
Umsetzung wie F1 über die Löschfunktion, Löschsperre gilt auch hier.

### 5.2 Rechtliche Prüfung vor Produktivfreigabe

Zu prüfen und zu dokumentieren (im Kontrollzentrum, neben der bestehenden TIA/AVV-Ablage):
- Rechtsgrundlagen je Datenart (Tabelle oben) und Informationspflichten (Art. 13/14) in Einladungsmail,
  Bestätigungsseite und Datenschutzerklärung.
- Die Fristen F1–F5 einschließlich der Regel zur Löschsperre.
- Backups: Gelöschtes bleibt bis zum Ablauf der Rotation in den Sicherungen (lokal + Storage Box). Die
  Datenschutzerklärung sollte das allgemein nennen, falls sie es noch nicht tut.
- Erst danach geht der Austausch auf Prod live. Bis dahin ist **Staging** zulässig, mit eigenen Testadressen
  statt echter Fachkontakte.

### 5.3 Einordnung in die bestehende Aufbewahrungslogik (`omn/aufbewahrung.py`)

Die bestehende Logik hat zwei Listen:
- `FRISTEN` löscht ganze Zeilen per Massen-`DELETE`.
- `LEEREN` setzt einzelne Spalten auf NULL.

Sie läuft täglich über `flask aufbewahrung-bereinigen` (Cron, `deploy/aufbewahrung.sh`).

- **F3 passt direkt in `LEEREN`:** drei Einträge (LinkedIn-URL, Gesprächsbeginn, Vorgeschichte), 730 Tage nach
  `letzte_aktivitaet`. Die Zusatzbedingung „keine aktive Löschsperre“ ist nötig. `LEEREN` kennt heute keine
  Zusatzbedingung und bekommt deshalb, wie `FRISTEN`, ein optionales Bedingungsfeld. Achtung: `austausch` ist
  eine neue Tabelle mit `timestamptz`. Die tz-Behandlung, die `FRISTEN` schon hat, muss `LEEREN` deshalb auch
  bekommen. Heute vergleicht `LEEREN` immer naiv.
- **F1 und F4 passen nicht in `FRISTEN`.** Ein Massen-`DELETE` umgeht die Datei-Löschung. Die Datenbankzeilen
  von Aufgaben/Kommentaren/Anhängen verschwinden zwar per `ON DELETE CASCADE`, die Dateien unter
  `instance/uploads/kollaboration/` bleiben aber liegen (dieselbe Lücke wie im Bestand). Deshalb kommt eine
  **dritte Liste** `LOESCHEN_MIT_FUNKTION` dazu: (Bezeichnung, Abfrage der fälligen Zeilen, Löschfunktion). Die
  Funktion `austausch_loeschen(austausch)` entfernt erst die Dateien, dann die Zeile samt CASCADE. Dieselbe
  Funktion nutzen der Admin-Knopf (F5) und die Kontolöschung. Der Zähler erscheint wie die anderen in der
  Ausgabe von `flask aufbewahrung-bereinigen`.
- Die Löschsperre fließt in die Abfragen von F1, F3 und F4 ein:
  `loeschsperre_bis IS NULL OR loeschsperre_bis < jetzt`.
- Kommentar und Docstring in `aufbewahrung.py` sowie die Fristen in der Datenschutzerklärung werden
  nachgezogen (Projektregel: Fristen stehen in der Datenschutzerklärung).
- **Bestehende Fristen bleiben unverändert.**

### 5.4 Inaktivität (F2)

Es gibt keinen Lösch- oder Sperrlauf. Stattdessen:
- In `/admin/austausch` erscheint ein Hinweis „Prüfen – seit 12 Monaten keine Aktivität“, und die Liste lässt
  sich danach filtern.
- Die Anzahl erscheint auch auf der Admin-Übersicht.
- Der Admin entscheidet: weiterlaufen lassen (Knopf „geprüft“ setzt `geprueft_am` und blendet den Hinweis für
  weitere 12 Monate aus), beenden (→ F4) oder sperren (→ F4).
- Was als Aktivität zählt: neue Aufgabe, Statuswechsel, Kommentar, von beiden Seiten. Das ist das schon
  vorhandene `_kooperation_aktivitaet_markieren`. Reines Ansehen zählt nicht.

### 5.5 Löschwünsche (F5) und Kontolöschung

- Der Knopf „Auf Wunsch löschen“ löscht den Austausch sofort, inklusive Dateien und Anhängen. Er fragt
  zusätzlich, ob auch das Konto gelöscht werden soll. Das passiert nur, wenn das Konto keine anderen Bezüge
  hat (Knoten, Kooperation, Förderung). Sonst zeigt er einen Hinweis.
- Wird ein Konto über `/admin/nutzer/loeschen` gelöscht (Abschnitt 3, Schritt 7), fragt die Seite, ob der
  Austausch **sofort** mitgelöscht wird (Löschwunsch) oder nach F4 auf „gesperrt“ geht (z. B. Konto wegen
  Missbrauch entfernt).
- Jede Löschung wird im Audit-Log festgehalten. Dort steht nur die ID, kein Inhalt.

### 5.6 Bestandslücke Dateien

Beim Löschen eines Kooperations- oder Knotenbereichs verschwinden heute nur die Datenbankzeilen der Anhänge,
**die Dateien bleiben liegen**. Die Helferfunktion zum Löschen der Dateien (5.3) kommt in `kollaboration.py`
und wird dort, wo heute Förderer- bzw. Knotendaten gelöscht werden, gleich mitgenutzt. Das ist eine kleine
Verbesserung des Bestands, ohne dass sich sonst etwas an dessen Verhalten ändert.
- Zugriff: Eingeladene sehen nur Bereiche mit `nutzer_id == eigene id` und `status='aktiv'`. Admin-Felder
  werden im Partner-Template **gar nicht übergeben**, statt nur ausgeblendet.

---

## 6. Neue Tests (entsprechen den Abnahmekriterien)

| Abnahme | Test |
|---|---|
| 1 Einladung | GET verändert nichts (Status, Token bleiben); „annehmen“ verschickt einen Code an die **gespeicherte** Adresse und löst noch **nicht** ein; falscher Code 5× ergibt einen gesperrten Code; mehr als 3 Codes je Stunde abgelehnt; Code aus einer anderen Browser-Session abgelehnt; richtiger Code löst ein; zweite Einlösung scheitert; abgelaufen scheitert; unbekannter Token ergibt dieselbe Meldung; in der DB stehen nur Hashes, weder Token noch Code im Klartext; neues **und** bestehendes Konto danach eingeloggt und schreibt einen Kommentar; ein vorher eingeloggter anderer Nutzer ist danach abgemeldet; Kontolöschung setzt den Austausch auf `gesperrt` statt zu scheitern |
| 2 Neutralität | Einladungsmail (de+en), Bestätigungsseite, Arbeitsbereich und Benachrichtigungsmail an den Eingeladenen werden gerendert und durchsucht nach `Förder`, `Foerder`, `PayPal`, `Sporist`, `Spende`, `Zahlung`, `Hyphist`; ebenso die Pfade |
| 3 Admin-only | Marker-Werte in LinkedIn/Notiz/Beginn stehen in der Admin-Seite und **nicht** in der Partnerseite |
| 4 Sprache | Einladung mit `en` und `es` ergibt die Mail in dieser Sprache; neues Konto übernimmt die Sprache; Team-Kommentar ergibt die Mail in `Nutzer.sprache`; jeder `austausch_*`-Schlüssel existiert in allen 5 Sprachen |
| 5 Datenschutz | `test_aufbewahrung.py`: F1 (nicht angenommen, 6 Monate, inkl. Erneuerung setzt Frist neu), F1a (nur vorbereitet, 6 Monate ab Anlage), F3 (Notizen geleert, Austausch bleibt), F4 (gesperrt/beendet, 6 Monate ab Statuswechsel), Löschsperre setzt F1/F3/F4 aus und läuft ab, **Dateien werden mitgelöscht** (Datei liegt vorher im Temp-Verzeichnis, danach nicht mehr), bestehende Fristen unverändert; F2: nach 12 Monaten erscheint die Markierung, es wird **nichts** gesperrt oder gelöscht; F5: Knopf löscht sofort inkl. Dateien + Audit-Eintrag; Rechtstexte-Test: Abschnitt in allen Sprachen vorhanden |
| Anrede | `formell` + de ergibt in Einladungsmail/Bestätigungsseite „Sie“, `informell` ergibt „du“; persönlicher Einleitungssatz erscheint in der Mail; Community-Seiten (`dashboard_base`, Login) unverändert; jeder `austausch_*_formell`-Schlüssel hat ein `_informell`-Gegenstück in allen 5 Sprachen |
| Fachkontakt intern | kein „Fachkontakt“-Text auf irgendeiner Nutzer-Seite oder in Mails an Nutzer; `Nutzer` hat kein neues Feld |
| 6 Bestand | bestehende Tests unverändert grün; zusätzlich: ein Austausch taucht **nicht** in `kooperationen_von`, `_aktive_foerderer()`/Startseite und der Verfallsprüfung auf |
| 7 Rollen | nach dem Einlösen `ist_hyphist`/`ist_sporist`/`gruppe` unverändert (neues und bestehendes Konto); `/dashboard/hyphist` zeigt nichts; fremder Nutzer → 403 auf Bereich und Anhang; gesperrt → kein Zugriff |
| – | Migration: `test_kein_schema_drift_frische_db` grün; CSRF-Liste ergänzt |

---

## 7. Arbeitsschritte (je ein Commit, nach jedem Schritt Tests + ruff grün)

1. **Modell + Migration:** Tabelle `austausch`, `austausch_id` an `aufgabe`/`kommentar`, Alembic-Migration
   reviewen; lokal und gegen PG in der CI.
2. **Kollaborationskern:** Austausch-Zweige in `kollaboration.py` und Datei-Löschhelfer; Tests für unveränderte
   Bestandsbereiche.
3. **Admin:** `omn/admin/austausch.py` (Liste, anlegen, Detail mit interner Box, senden, sperren, löschen),
   Audit-Log und CSRF-Liste.
4. **Einladung + Arbeitsbereich:** `omn/austausch.py` (Bestätigungsseite, Einlösen, `/austausch`), DE/EN-Texte,
   Weiterleitung in `dashboard.home`, Navigationslink.
5. **Datenschutz und Fristen:** `aufbewahrung.py` erweitern (5.3: `LEEREN` mit Bedingung und tz-Behandlung,
   neue Liste `LOESCHEN_MIT_FUNKTION` für F1/F4), Löschsperre, Inaktivitätsmarkierung (5.4),
   „Auf Wunsch löschen“ (5.5), Datei-Löschhelfer auch für den Bestand (5.6), Abschnitt in `rechtstexte.json`
   (5 Sprachen, inkl. Fristen), neue Themen-Datei `docs/claude/austausch.md`.
6. **Abnahmetests** (Abschnitt 6), danach Staging-Deploy und Durchlauf mit eigenen Testadressen (formell und
   informell, de + eine weitere Sprache).
7. **Rechtliche Prüfung** (5.2) durch Robby. **Erst danach Prod-Deploy.**

Grobe Größe: etwa 2 neue Python-Module, 4–5 Templates, 1 Migration und 1 neue Testdatei mit etwa 25 Tests.
Bestehender Code wird nur an den in 1.6 genannten Stellen erweitert.

---

## 8. Phase 2 – Wissenschaftliche Themenräume (Architektur, erst nach Phase 1 umsetzen)

> **Ausführlicher Plan: `docs/austausch_phase2_plan.md`.** Er ist maßgeblich; hier steht nur die
> Kurzfassung, soweit sie Phase 1 betrifft.

**Grundgedanke:** Der persönliche Austauschbereich aus Phase 1 bleibt **vertraulich** zwischen einer Person und
dem Team. Die Themenräume sind ein **zweiter, gemeinsamer** Bereich für alle Berechtigten. Ein Thema, eine
Diskussion, 5 Darstellungssprachen.

### 8.1 Struktur

```
Themengebiet       (6 vorgegeben + von Teilnehmern angelegte)
└── Diskussion     (von Teilnehmern angelegt: Titel, kurze Beschreibung)
    └── Beitrag    (Text, Antworten auf Beiträge, Anhänge)
```

Vorgegebene Themengebiete (Startbestand, Texte von Robby):

1. Bioelektrische Signale & Elektrophysiologie
2. Mykologie & Mykorrhiza
3. Bodenökologie & Umweltparameter
4. Messtechnik & BioComm
5. Experimente & wissenschaftliche Validierung
6. Datenanalyse, Modelle & KI

### 8.2 Datenmodell (neue Tabellen, alle `timestamptz`)

| Tabelle | Wichtige Felder |
|---|---|
| `themengebiet` | titel, beschreibung, `sprache_original`, `vorgegeben` (bool), `erstellt_von` (nutzer_id, NULL = Team), `zusammengefuehrt_in` (FK auf themengebiet, für Zusammenführen), sichtbar (bool), erstellt_am |
| `diskussion` | themengebiet_id, titel, beschreibung, `sprache_original`, erstellt_von, erstellt_am, letzte_aktivitaet, sichtbar |
| `beitrag` | diskussion_id, `antwort_auf` (beitrag_id, nullable), `autor_nutzer_id` (NULL = Team), text, `sprache_original`, erstellt_am, bearbeitet_am, sichtbar |
| `beitrag_anhang` | beitrag_id, Dateiname, Originalname, Größe (Speicherhelfer aus `kollaboration.py` wiederverwendet, **eigenes Verzeichnis**) |
| `uebersetzung` | inhalt_typ (themengebiet/diskussion/beitrag), inhalt_id, feld (titel/beschreibung/text), ziel_sprache, `quelltext_hash`, text, anbieter (`manuell`/`claude`/`deepl`…), erstellt_am; eindeutig über (typ, id, feld, sprache, hash) |

Im Unterschied zu Phase 1 hat `beitrag` einen **echten Autor** (`autor_nutzer_id`). In Phase 1 kennt
`Kommentar.autor` nur „team“/„partner“, was bei vielen Teilnehmern nicht mehr reicht.

### 8.3 Trennung privat ↔ gemeinsam (wichtigste Architekturregel)

- **Getrennte Tabellen, getrennte Routen (`/themen/...`), getrennte Anhangverzeichnisse und eigene
  Download-Prüfung.** Zwischen `aufgabe`/`kommentar` (privat) und `beitrag` (gemeinsam) gibt es **keine
  Verbindung**.
- Es gibt **keine** Funktion „privaten Kommentar in Themenraum verschieben/teilen“. Wer etwas aus einem
  privaten Gespräch einbringen will, schreibt es bewusst neu. Damit kann niemand versehentlich Vertrauliches
  veröffentlichen.
- Der Eingabebereich in den Themenräumen trägt einen klaren Hinweis: „Sichtbar für alle Teilnehmenden der
  Themenräume“. Im privaten Bereich steht der Gegenhinweis „Nur zwischen dir und dem OpenMycoNet-Team“.
- Tests: Ein Anhang aus einem privaten Bereich ist über die Themenraum-Route nicht abrufbar und umgekehrt;
  ein Beitrag taucht nie in einem privaten Bereich auf.

### 8.4 Übersetzung von Nutzerinhalten (5 Sprachen)

- **Feste Oberflächentexte** bleiben bei `translations.json`. Die Übersetzungs-API ist **nur** für von Nutzern
  geschriebene Inhalte da (Themengebiet-/Diskussionstitel und -beschreibungen, Beiträge).
- **Das Original wird immer unverändert gespeichert**, zusammen mit seiner Sprache. Die Autorin bzw. der Autor
  wählt sie beim Schreiben aus (vorbelegt mit der aktuellen Website-Sprache), also keine Erkennung durch
  Raten.
- **Austauschbare Schnittstelle** `omn/uebersetzung.py`: `uebersetze(text, von, nach, glossar)`, darunter je
  Anbieter eine kleine Klasse. Welcher Anbieter aktiv ist, steht in der Config bzw. `.env`. Der Schlüssel
  liegt nur auf dem Server, nie im Browser.
- **Übersetzt wird nur bei Bedarf, und jede Übersetzung nur einmal:**
  - Die Seite zeigt sofort das Original und bereits vorhandene Übersetzungen aus `uebersetzung`.
  - Fehlende Übersetzungen holt die Seite einzeln nach (kleiner POST `/themen/uebersetzung/<typ>/<id>`). Der
    Server übersetzt dann, speichert und liefert zurück.
  - Ändert sich der Originaltext, passt `quelltext_hash` nicht mehr, und die alte Übersetzung wird nicht mehr
    genommen.
  - Das Seitenladen wartet also nie auf die API.
- **Anzeige:** „Automatisch übersetzt · Original anzeigen“ (Umschalter je Beitrag), dazu die
  Originalsprache.
- **Fachbegriffe:** Ein gepflegtes Glossar (Datei im Repo, z. B. arbuscular mycorrhiza, extracellular
  potential, calcium oscillations, Hyphe, Myzel, BioComm …) wird der Übersetzung mitgegeben. Bei Claude
  geschieht das als Anweisung im Prompt („diese Begriffe so übersetzen/nicht übersetzen“), bei DeepL über
  dessen Glossar-Funktion.
- **Die 6 vorgegebenen Themengebiete** werden einmal von Hand in alle 5 Sprachen übersetzt und mit
  `anbieter='manuell'` hinterlegt. Sie laufen dann über denselben Anzeigeweg, ohne API-Kosten.
- **Kostenbremse:** Tageslimit für API-Aufrufe (Config). Ist es erreicht, steht dort „Übersetzung später
  verfügbar“, und das Original bleibt sichtbar.
- **Anbieterwahl (offen, Vergleich Qualität/Kosten/Datenschutz):**

  | Anbieter | Für | Gegen |
  |---|---|---|
  | **Claude (Anthropic)**, schon im Einsatz für News-Übersetzung + Chatbot (`omn/ki.py`, `admin/news.py`) | keine neue Anbindung, kein neuer Vertrag, gut mit Fachbegriffen/Kontext | USA ohne DPF (SCC + TIA vorhanden), die TIA deckt bisher Chatbot + Admin-News ab und müsste auf Nutzerbeiträge erweitert werden |
  | **DeepL API Pro** | Sitz in Köln, keine Drittlandübermittlung, Glossar-Funktion | neuer Auftragsverarbeiter (AVV), neue Kosten, neue Abhängigkeit in `requirements.txt` oder direkt per HTTP |
  | Google Cloud Translation | breite Sprachabdeckung | USA, weiterer Konzern als Empfänger |

  Empfehlung: die Schnittstelle so bauen, dass beide Anbieter gehen. Mit **Claude** starten, weil das schon
  angebunden ist, sofern die TIA-Erweiterung für dich in Ordnung ist. Sonst gleich DeepL.
- **Datenschutz Übersetzung:** Übermittelt wird nur der Text, **ohne** Namen oder E-Mail. Ein Hinweis beim
  Schreiben („Beiträge werden zur automatischen Übersetzung an [Anbieter] übermittelt“) und ein Abschnitt in
  der Datenschutzerklärung. Private Bereiche aus Phase 1 werden **nicht** übersetzt (vertraulicher Inhalt).
  Das ließe sich später auf ausdrücklichen Wunsch einschalten.

### 8.5 Eigene Themengebiete und Ordnung

- Berechtigte dürfen **Diskussionen und Themengebiete** ohne vorherige Freigabe anlegen. Pflicht sind Titel
  und kurze Beschreibung, bei Diskussionen zusätzlich das Themengebiet.
- **Vor dem Anlegen werden ähnliche bestehende Themen angezeigt.** Einfacher Wortvergleich über Titel und
  Beschreibung, auch gegen die vorhandenen Übersetzungen, damit „Mycorrhiza“ und „Mykorrhiza“ sich finden.
  Dafür ist keine KI nötig. Danach kann man trotzdem anlegen.
- **Admin:** umbenennen, zusammenführen (Diskussionen wandern ins Ziel, das alte Gebiet verweist darauf),
  ausblenden, löschen. Dasselbe für Diskussionen und Beiträge. **Moderation ist Pflicht**, sobald Inhalte für
  viele sichtbar sind: Mindestens Ausblenden durch den Admin, dazu kurze Nutzungsregeln. Optional ein Knopf
  „Beitrag melden“.
- Bearbeiten eigener Beiträge: ja, mit `bearbeitet_am`. Die Übersetzung erneuert sich über den Hash von
  selbst.

### 8.6 Wer ist „berechtigt“? (offen, wichtig)

Eine einzige Prüffunktion `darf_themenraeume_nutzen(nutzer)`. Sie hängt **nicht** von Hyphist, Sporist,
Förderung oder Zahlung ab, und ein Test erzwingt das. Mögliche Kreise, von eng nach weit:

1. alle mit aktivem Austauschbereich (Fachkontakte) + Team **(Empfehlung für den Start)**
2. zusätzlich Knotenbetreiber und Hyphisten
3. alle bestätigten registrierten Nutzer
4. Lesen öffentlich, Schreiben nur Berechtigte (das wäre eine Veröffentlichung im Netz; Datenschutz und
   Moderation werden deutlich anspruchsvoller)

### 8.7 Folgen für Phase 1

Phase 1 bleibt wie geplant, ohne vorgezogene Tabellen. Nur drei Dinge stellen sicher, dass Phase 2 sauber
andocken kann:
- Zugriffsprüfungen laufen nur über zentrale Funktionen (1.3).
- Die Sprache läuft über die normale Website-Sprachwahl und `Nutzer.sprache` (4).
- Der Datei-Speicherhelfer in `kollaboration.py` wird so geschrieben, dass er ein Zielverzeichnis als
  Parameter nimmt.

Grobe Größe Phase 2: deutlich größer als Phase 1, etwa 5 neue Tabellen, Übersetzungsmodul, 6–8 Templates und
Moderation. Sinnvoll in zwei Schritten: **2a** Themenräume ohne Übersetzung, **2b** Übersetzung.

---

## 9. Anknüpfungspunkte für spätere Phasen (ohne Vorleistung in Phase 1)

Nummerierung nach der neuen Reihenfolge: Phase 3 = bisherige Phase 2 des Auftrags, Phase 4 = bisherige
Phase 3.

- **Phase 3 – Vorschläge weiterer Personen:** Später eine eigene Tabelle `austausch_vorschlag`
  (`austausch_id`, `vorgeschlagen_von` = nutzer_id, Name, optionale Kontaktdaten, Begründung, Status). Der
  Admin übernimmt einen Vorschlag über das vorhandene „Einladung vorbereiten“. Dafür braucht es in Phase 1
  nichts, nur dass Einladungen immer über den Admin laufen (ist so).
- **Phase 4 – mehrere Teilnehmer an einem privaten Bereich:** Durch die Themenräume (Phase 2) entfällt ein
  Teil des Bedarfs, denn gemeinsame Fachdiskussionen laufen dann dort. Phase 4 betrifft nur noch vertrauliche
  Bereiche mit mehreren Personen. `austausch.nutzer_id` wird zu einer Tabelle `austausch_teilnehmer`
  (`austausch_id`, `nutzer_id`, `beigetreten_am`, eigener Einladungstoken). Weil alle Zugriffe über
  `austausch_bereiche_von` / `darf_austausch_sehen` laufen, ändert sich nur deren Inhalt. Für „keine alten
  Inhalte für Neue“ gibt es zwei Wege: über `beigetreten_am` filtern oder neue Teilbereiche als eigene
  `austausch`-Zeilen anlegen. Außerdem bräuchte `Kommentar` dann eine `autor_nutzer_id`, weil `autor` heute
  nur `team`/`partner` kennt. Das wird erst in Phase 4 angelegt.

---

## 10. Offene Entscheidungen (von dir)

**Entschieden am 25.10.2026 (Robby):**

1. ~~Gültigkeit~~ **14 Tage**, danach durch den Admin erneuerbar (5.1).
2. ~~Löschfristen/Inaktivität~~ **F1–F5** wie in 5.1; Inaktivität nur Markierung nach 12 Monaten, keine
   automatische Sperrung. **Rechtliche Prüfung bleibt Voraussetzung für die Produktivfreigabe** (5.2).
3. ~~Label~~ **„Fachkontakt“ nur intern.** Keine Mitgliedsstufe, kein Feld an `Nutzer`, nirgends für Nutzer
   sichtbar. Im Admin heißt der Bereich „Fachlicher Austausch“; ein Admin-Filter „hat Austausch“ ist erlaubt.
4. ~~Anrede~~ **Deutsch standardmäßig „Sie“**, je Kontakt umstellbar + persönlicher Einleitungssatz;
   Community-Oberfläche unverändert; andere Sprachen siehe Tabelle in Abschnitt 4.

5. ~~Vorbereitete Einträge~~ **Bestätigt:** Nie verschickte, nur vorbereitete Austausche werden nach
   6 Monaten ab `erstellt_am` gelöscht (5.1).
6. ~~Anrede nl/fr/es~~ **Bestätigt:** förmlicher Standard u / vous / usted (Tabelle in 4).

**Alle Entscheidungen zu Phase 1 sind getroffen.** Offen bleibt nur die rechtliche Prüfung (5.2) vor dem
Prod-Deploy.
5. ~~Bestehende Konten über einen zusätzlichen Login-Link?~~ **Erledigt (25.10.):** Ersetzt durch den
   Bestätigungscode für alle (Abschnitt 3, Schritte 4–5).

Zu Phase 2 (eilt nicht, aber vor dem Bau):

6. Wer darf die Themenräume nutzen (8.6)? Empfehlung: zunächst Fachkontakte + Team.
7. Übersetzungsanbieter: Claude (TIA erweitern) oder DeepL (neue AVV)?
8. Die Beschreibungstexte der 6 vorgegebenen Themengebiete: deine Fassung aus den Anmerkungen übernehmen?
   Die Übersetzung in 5 Sprachen würde ich vorbereiten, du prüfst sie.
9. Ist die neue Phasen-Reihenfolge so richtig (Themenräume vor Wiedervorlage/Vorschlägen)?
