# Phase 2 – Wissenschaftliche Themenräume – Umsetzungsplan

Stand: 25.10.2026 · Grundlage: Robbys Anmerkungen vom 25.10. + Codeanalyse
Status: **Phase 2a zur Umsetzung freigegeben** (Robby, 25.10.2026, nach Abschluss von Phase 1). Phase 2b
(Übersetzung) erst nach 2a.

**Entscheidungen zum Start von 2a (25.10.2026):** Anzeigename frei wählbar (vorbelegt mit dem Kontonamen);
in 2a keine Mails, nur „neu seit deinem letzten Besuch“; Evidenz-Kennzeichnung optional schon in 2a;
Design: ganzes Nutzer-Dashboard hell im Admin-/MCC-Stil (Datenlabor bleibt dunkel), gilt auch für die
Themenräume. Abweichung vom Datenmodell unten: `beitrag`, `diskussion` und `themengebiet` haben zusätzlich
`von_team` (Team vs. ehemaliges Mitglied unterscheidbar), `beitrag.entfernt_am` für entfernte Beiträge.

**Überarbeitet am 25.10. nach Robbys Durchsicht:**
- Die 6 vorgegebenen Themengebiete gibt es schon in **2a** in allen 5 Sprachen, von Hand übersetzt, ohne API
  (Abschnitte 2, 3.5, 12).
- **Teilnehmerkreis:** Start mit Fachkontakten und Team. Ziel ist, die Themenräume allen registrierten
  Mycelists zu öffnen, unabhängig von der Mitgliedsstufe. Die Texte sind von Anfang an darauf ausgelegt
  (Abschnitt 5).
- **Original sofort erreichbar,** auf Wunsch immer zuerst (Abschnitt 7.4).
- **Kontolöschung und Rechte der Verfasser** neu geregelt, mit Freigabepflicht vor dem Produktivstart
  (Abschnitt 9.3, neue Tabelle `themen_teilnahme`).

---

## 0. Kurzfassung

- Neben dem **vertraulichen** Austauschbereich aus Phase 1 (eine Person ↔ Team) entsteht ein **gemeinsamer**
  Bereich: die wissenschaftlichen Themenräume.
- Aufbau: **Themengebiet → Diskussion → Beitrag.** Sechs Gebiete sind vorgegeben, weitere Gebiete und alle
  Diskussionen legen die Teilnehmenden selbst an, ohne vorherige Freigabe.
- **Ein Thema, eine Diskussion, fünf Darstellungssprachen.** Beiträge werden bei Bedarf automatisch
  übersetzt. Das Original bleibt unverändert und lässt sich jederzeit anzeigen.
- **Privat und gemeinsam sind technisch getrennt.** Es gibt keinen Weg, vertrauliche Inhalte aus Phase 1
  versehentlich in einen Themenraum zu bringen.
- Zugang **unabhängig** von Förderung, Zahlung und Mitgliedsstufe. Die Themenräume verändern keine
  Mitgliedsstufe.
- Vorschlag: in zwei Schritten bauen, **2a** Themenräume ohne Übersetzung, **2b** Übersetzung.

---

## 1. Anforderungen (aus den Anmerkungen)

1. Sechs vorgegebene Themengebiete, in allen 5 Website-Sprachen hinterlegt.
2. Berechtigte Teilnehmende können **eigene Themengebiete** und **Diskussionen** anlegen. Pflicht: Titel und
   kurze Beschreibung, bei Diskussionen zusätzlich das Themengebiet. Keine vorherige Freigabe.
3. Vor dem Anlegen werden **ähnliche bestehende Themen** angezeigt.
4. Der Admin kann Themen **umbenennen und zusammenführen**.
5. Beiträge, Antworten und Anhänge innerhalb der Diskussionen.
6. Gemeinsame Themenräume sind **ausdrücklich getrennt** von privaten Austausch- und Kooperationsbereichen.
7. Kein finanzieller Zugangsvorbehalt, keine automatische Änderung der Mitgliedsstufe.
8. Übersetzung der Nutzerinhalte in die 5 Sprachen:
   - Das Original wird unverändert gespeichert.
   - Es gilt die bestehende Sprachwahl der Website.
   - Die Anbindung läuft serverseitig.
   - Jede Übersetzung wird zwischengespeichert und nur bei Bedarf erzeugt.
   - „Original anzeigen“ ist immer möglich.
   - Fachbegriffe werden berücksichtigt.
   - Der Datenschutz ist geprüft.
   - Der Anbieter ist austauschbar.
9. Die festen Oberflächentexte laufen weiter über `translations.json`. Die API ist nur für Nutzerinhalte da.

---

## 2. Vorgegebene Themengebiete

| # | Titel (de) | Beschreibung (de) |
|---|---|---|
| 1 | Bioelektrische Signale & Elektrophysiologie | Signalformen, zeitliche Muster, Messmethoden, Artefakte, Signalverarbeitung |
| 2 | Mykologie & Mykorrhiza | Pilzphysiologie, Hyphennetze, Symbiosen, Wachstum und biologische Aktivität |
| 3 | Bodenökologie & Umweltparameter | Bodenchemie, Feuchtigkeit, Temperatur, Nährstoffe und ökologische Zusammenhänge |
| 4 | Messtechnik & BioComm | Sensorik, Elektroden, Hardware, Kalibrierung, Messqualität und Feldbetrieb |
| 5 | Experimente & wissenschaftliche Validierung | Hypothesen, Versuchsdesign, Kontrollgruppen, Reproduzierbarkeit und biologische Referenzmethoden |
| 6 | Datenanalyse, Modelle & KI | Zeitreihen, Mustererkennung, statistische Auswertung, Simulation und mögliche Closed-Loop-Verfahren |

Diese Texte werden **einmal von Hand** in en/nl/fr/es übersetzt (ich bereite das vor, du prüfst es) und
**schon in Schritt 2a** mit der Migration angelegt. Dafür ist keine Übersetzungs-API nötig. Sie liegen in der
Tabelle `uebersetzung` (3.5) mit `anbieter='manuell'`. Diese Tabelle entsteht deshalb schon in 2a; 2b füllt sie
dann zusätzlich automatisch. So gibt es nur einen Anzeigeweg.

---

## 3. Datenmodell

Alle Tabellen sind neu, Zeitpunkte als `timestamptz` (Regel vom 23.09.2026). Keine Änderung an bestehenden
Tabellen.

### 3.1 `themengebiet`
| Spalte | Typ | Bemerkung |
|---|---|---|
| id | int PK | |
| titel | str(200) | Original |
| beschreibung | text | Original, kurz (Grenze z. B. 500 Zeichen) |
| sprache_original | str(10) | eine der 5 Sprachen |
| vorgegeben | bool | die 6 Startgebiete |
| erstellt_von | FK nutzer, nullable | NULL = Team |
| zusammengefuehrt_in | FK themengebiet, nullable | gesetzt nach dem Zusammenführen; die alte Adresse leitet weiter |
| sichtbar | bool | Admin kann ausblenden |
| reihenfolge | int | vorgegebene oben, eigene darunter |
| erstellt_am | timestamptz | |

### 3.2 `diskussion`
| Spalte | Typ | Bemerkung |
|---|---|---|
| id | int PK | |
| themengebiet_id | FK themengebiet | |
| titel, beschreibung, sprache_original | wie oben | |
| erstellt_von | FK nutzer, nullable | NULL = Team |
| erstellt_am, letzte_aktivitaet | timestamptz | Sortierung „zuletzt aktiv“ |
| sichtbar | bool | |
| geschlossen | bool | Admin kann eine Diskussion schließen (lesbar, keine neuen Beiträge) |

### 3.3 `beitrag`
| Spalte | Typ | Bemerkung |
|---|---|---|
| id | int PK | |
| diskussion_id | FK diskussion | |
| antwort_auf | FK beitrag, nullable | **eine** Ebene Antworten reicht (keine tiefen Bäume, bleibt übersichtlich) |
| autor_nutzer_id | FK nutzer, nullable | NULL = Team. Anders als in Phase 1 gibt es hier einen echten Autor |
| text | text | **Klartext** mit Zeilenumbrüchen, Links werden klickbar; kein HTML (siehe 8) |
| sprache_original | str(10) | |
| erstellt_am, bearbeitet_am | timestamptz | |
| sichtbar | bool | Moderation |

Die geplante Evidenz-Kennzeichnung je Beitrag (Hypothese, Literatur, Beobachtung, Messdaten) wäre hier nur
eine zusätzliche Spalte `art`. Ob sie schon in 2a kommt, ist offener Punkt 7.

### 3.4 `beitrag_anhang`
Wie `KollaborationAnhang` (Dateiname, Originalname, Größe), aber mit `beitrag_id`. Dateien liegen in einem
**eigenen** Verzeichnis `instance/uploads/themen/`. Der Speicherhelfer aus `kollaboration.py` wird
wiederverwendet; er bekommt in Phase 1 ohnehin das Zielverzeichnis als Parameter. Erlaubte Formate wie
bisher, also Bilder, PDF, Text/CSV/JSON und ZIP, je 5 MB.

### 3.5 `uebersetzung` (Tabelle schon in 2a für die 6 Startgebiete, automatische Einträge ab 2b)
| Spalte | Typ | Bemerkung |
|---|---|---|
| id | int PK | |
| inhalt_typ | str(20) | `themengebiet` / `diskussion` / `beitrag` |
| inhalt_id | int | |
| feld | str(20) | `titel` / `beschreibung` / `text` |
| ziel_sprache | str(10) | |
| quelltext_hash | str(64) | SHA-256 des Originals. Ändert sich das Original, passt die alte Übersetzung nicht mehr |
| text | text | Übersetzung |
| anbieter | str(20) | `manuell` / `claude` / `deepl` … |
| erstellt_am | timestamptz | |

Eindeutig über (inhalt_typ, inhalt_id, feld, ziel_sprache, quelltext_hash). Löschen eines Inhalts löscht seine
Übersetzungen mit. Das geschieht per Code, weil die Tabelle mehrere Inhaltstypen bedient und deshalb keinen
echten Fremdschlüssel hat.

### 3.6 `themen_teilnahme` (neu nach Robbys Durchsicht)
Eine Zeile je Person, die die Themenräume betreten hat. Sie hält alles, was nur die Themenräume betrifft.
Die bestehende Tabelle `nutzer` wird dafür nicht verändert.

| Spalte | Typ | Bemerkung |
|---|---|---|
| nutzer_id | FK nutzer, PK, `ondelete` siehe 9.3 | |
| anzeigename | str(100) | so erscheint die Person; vorbelegt mit `Nutzer.name`, änderbar |
| regeln_akzeptiert_am | timestamptz | Zustimmung zu den Nutzungsregeln (Fassung siehe nächste Spalte) |
| regeln_fassung | str(20) | z. B. `2027-01`; bei geänderten Regeln erneut zustimmen |
| beitraege_nach_loeschung | str(10) | `entfernen` (Standard) / `behalten` (ohne Namen), siehe 9.3 |
| original_zuerst | bool | Anzeigewunsch aus 7.4 |
| zuletzt_gesehen | timestamptz | für „neu seit deinem letzten Besuch“ |

---

## 4. Trennung privat ↔ gemeinsam (zentrale Sicherheitsregel)

| | Privater Austausch (Phase 1) | Themenräume (Phase 2) |
|---|---|---|
| Tabellen | `austausch`, `aufgabe`, `kommentar`, `kollaboration_anhang` | `themengebiet`, `diskussion`, `beitrag`, `beitrag_anhang` |
| Adressen | `/austausch…` | `/themen…` |
| Dateien | `instance/uploads/kollaboration/` | `instance/uploads/themen/` |
| Download-Prüfung | „gehört der Bereich mir?“ | „darf ich Themenräume nutzen?“ |
| Übersetzung | **nein** | ja (2b) |
| Hinweis am Eingabefeld | „Nur zwischen dir und dem OpenMycoNet-Team“ | „Sichtbar für alle Teilnehmenden der Themenräume“ |

- Zwischen den beiden Welten gibt es **keinen Fremdschlüssel und keine Funktion zum Verschieben oder Teilen**.
  Wer etwas aus einem vertraulichen Gespräch in einen Themenraum einbringen will, schreibt es bewusst neu.
- Vom privaten Bereich führt höchstens ein **Link** („Zu den Themenräumen“) hinüber.
- Tests sichern das ab (Abschnitt 11).

---

## 5. Berechtigung

Eine einzige Prüffunktion `darf_themenraeume_nutzen(nutzer)` in `omn/themen.py`. **Alle** Routen und der
Datei-Download nutzen nur sie. Sie greift **nie** auf `ist_hyphist`, `ist_sporist`, `foerderer` oder Zahlungen
zu. Ein Test prüft, dass ein Sporist ohne andere Berechtigung keinen Zugang bekommt und ein Fachkontakt ohne
Rolle schon.

Mögliche Kreise, von eng nach weit:

1. **alle mit aktivem Austauschbereich (Fachkontakte) + Team** – **Start** (kontrolliert, wenige Personen)
2. zusätzlich Knotenbetreiber (haben einen Knoten) und Hyphisten (formelle Kooperation)
3. **alle bestätigten registrierten Nutzer (Mycelists), unabhängig von der Mitgliedsstufe** – **erklärtes Ziel**
   (Robby, 25.10.)
4. Lesen öffentlich im Netz, Schreiben nur Berechtigte

**Weg von Kreis 1 zu Kreis 3:**
- Technisch ist nur eine Zeile in `darf_themenraeume_nutzen` zu ändern, und eine Config-Einstellung
  `THEMEN_KREIS` reicht.
- **Inhaltlich:** Wer in Kreis 1 schreibt, schreibt für ein kleines Fachpublikum. Damit niemand später
  überrascht ist:
  - Nutzungsregeln, Hinweis am Eingabefeld und Datenschutzerklärung sagen **von Anfang an**, dass die
    Themenräume künftig allen registrierten Mitgliedern offenstehen werden.
  - Vor der Öffnung erhalten alle bisherigen Teilnehmenden **eine Ankündigung mit Frist**, etwa 4 Wochen,
    über die Mail-Queue. In dieser Zeit können sie eigene Beiträge noch löschen.
- Mit der Öffnung wachsen Moderationsaufwand und Spam-Risiko. Mindestens der Knopf „Beitrag melden“ (8) und
  ein Beitragslimit je Nutzer und Tag sollten dann vorhanden sein.

Variante 4 hieße: Beiträge wären öffentlich und von Suchmaschinen auffindbar. Datenschutz (Namen der
Autoren), Moderation und Spam-Schutz würden deutlich anspruchsvoller. Deshalb nicht für den Start.

Das Team schreibt über den Admin-Bereich und erscheint als „OpenMycoNet-Team“.

**Anzeigename der Autoren:** `Nutzer.name`. Neu ist, dass andere Teilnehmende ihn sehen. Bisher hat ihn außer
dem Team niemand gesehen. Das muss die Datenschutzerklärung nennen. Außerdem sollte man den Namen vor dem
ersten Beitrag ändern können (kleines Feld „So erscheinst du in den Themenräumen“).

---

## 6. Seiten und Routen

Eigener Blueprint `omn/themen.py` (mit `schuetze_blueprint`), Seiten auf Basis `dashboard_base.html`, alle
`login_required` + `darf_themenraeume_nutzen`. Seiten `noindex`, nicht in `llms.txt` und nicht in den
öffentlichen Audit-Listen. Sollte später Variante 4 kommen, würden sie dort ergänzt.

| Route | Methode | Inhalt |
|---|---|---|
| `/themen` | GET | Übersicht der Themengebiete (vorgegebene oben), je mit Anzahl Diskussionen und letzter Aktivität |
| `/themen/gebiet/neu` | GET/POST | neues Themengebiet; Schritt 1 zeigt ähnliche Themen, Schritt 2 bestätigen |
| `/themen/gebiet/<id>` | GET | Diskussionen eines Gebiets, sortiert nach letzter Aktivität |
| `/themen/gebiet/<id>/diskussion/neu` | GET/POST | neue Diskussion, ebenfalls mit Ähnlichkeitsanzeige |
| `/themen/diskussion/<id>` | GET/POST | Beiträge, Antworten, Anhänge; POST = neuer Beitrag oder neue Antwort |
| `/themen/beitrag/<id>/bearbeiten` | GET/POST | nur eigene Beiträge |
| `/themen/datei/<id>` | GET | Anhang-Download nach Berechtigungsprüfung |
| `/themen/uebersetzung` | POST (CSRF) | **2b:** liefert eine fehlende Übersetzung nach (siehe 7.3) |

Admin (`omn/admin/themen.py` am `admin_bp`, nur Superadmin, alle ändernden Aktionen als POST mit
`protokollieren(...)` und Eintrag in `test_csrf.py::AENDERNDE_ADMIN_ROUTEN`):

| Route | Zweck |
|---|---|
| `/admin/themen` | Übersicht aller Gebiete/Diskussionen, neueste Beiträge, ausgeblendete Inhalte |
| `/admin/themen/gebiet/<id>/umbenennen` | Titel/Beschreibung ändern (Übersetzungen erneuern sich über den Hash) |
| `/admin/themen/gebiet/<id>/zusammenfuehren` | alle Diskussionen ins Zielgebiet verschieben, `zusammengefuehrt_in` setzen, altes Gebiet ausblenden |
| `/admin/themen/diskussion/<id>/verschieben` | Diskussion in anderes Gebiet |
| `/admin/themen/…/ausblenden` · `/einblenden` · `/loeschen` | für Gebiet, Diskussion, Beitrag |
| `/admin/themen/diskussion/<id>/schliessen` | keine neuen Beiträge mehr |

---

## 7. Übersetzung (Schritt 2b)

### 7.1 Grundregeln
- **Original immer unverändert** in `beitrag.text` usw., dazu `sprache_original`. Die Sprache wählt die
  schreibende Person in einem Auswahlfeld, vorbelegt mit der aktuellen Website-Sprache. Eine automatische
  Erkennung ist nicht nötig.
- **Lesesprache = Website-Sprache** (`resolve_lang()`, bestehende Sprachwahl). Keine eigene Einstellung.
- **Nur Nutzerinhalte** werden übersetzt (Titel, Beschreibungen, Beiträge). Knöpfe und feste Texte bleiben in
  `translations.json`.

### 7.2 Schnittstelle `omn/uebersetzung.py`
```
uebersetze(text, von, nach) -> str        # wirft UebersetzungFehler
uebersetzung_holen(inhalt, feld, sprache)  # Cache-Lookup, sonst None
```
- Darunter eine kleine Klasse je Anbieter (`ClaudeAnbieter`, später ggf. `DeepLAnbieter`). Welche aktiv ist,
  bestimmt `UEBERSETZUNG_ANBIETER` in der `.env`. Schlüssel nur serverseitig (`ANTHROPIC_API_KEY` gibt es
  schon).
- `ClaudeAnbieter` baut auf dem vorhandenen Muster der News-Übersetzung auf (`omn/admin/news.py`,
  `_uebersetzung_anfordern`; Modell/Antwortauswertung aus `omn/ki.py`).
- Fehler (kein Schlüssel, API nicht erreichbar, Ablehnung) brechen nie die Seite ab. Dann bleibt das
  Original sichtbar mit dem Hinweis „Übersetzung zurzeit nicht verfügbar“.

### 7.3 Übersetzen nur bei Bedarf, jeweils nur einmal
1. Die Seite lädt sofort mit allen **vorhandenen** Übersetzungen aus der Tabelle. Wo eine fehlt, steht
   zunächst das Original mit dem Hinweis „wird übersetzt …“.
2. Ein kleines Skript fragt die fehlenden Übersetzungen **einzeln** per POST `/themen/uebersetzung` nach
   (Typ, ID, Feld, Zielsprache). CSP-Nonce und CSRF-Header sind vorhanden.
3. Der Server prüft die Berechtigung und schaut im Cache nach. Fehlt die Übersetzung noch, ruft er den Anbieter
   auf, speichert das Ergebnis und gibt es zurück.
4. Jede Kombination aus Inhalt, Feld, Sprache und Originalfassung wird so **genau einmal** übersetzt, egal wie
   viele Personen sie lesen. Wenn niemand einen Beitrag auf Niederländisch liest, entsteht nie eine
   niederländische Übersetzung.
5. Doppelte gleichzeitige Anfragen verhindert die Eindeutigkeit der Tabelle: Der zweite Speicherversuch
   scheitert still, und das vorhandene Ergebnis wird genommen.

### 7.4 Anzeige – das Original ist immer unmittelbar erreichbar
- Jede Übersetzung trägt sichtbar „Automatisch übersetzt aus dem Englischen · **Original anzeigen**“. Das
  Original ist **schon in der Seite enthalten**. Ein Klick klappt es direkt darunter auf, ohne Nachladen und
  ohne Wartezeit, und das funktioniert auch, wenn die Übersetzung gerade fehlschlägt.
- **„Originale zuerst anzeigen“** als persönliche Einstellung (`themen_teilnahme.original_zuerst`). Dann
  steht immer das Original oben und die Übersetzung aufklappbar darunter. Das ist für alle, die die
  Originalsprache lesen können oder Aussagen genau prüfen wollen.
- Fester Hinweis in der Fußzeile jeder Diskussion: „**Maßgeblich ist das Original.** Automatische
  Übersetzungen können Fehler enthalten.“
- **Zitieren und Antworten** beziehen sich immer auf das Original. Ein Zitat übernimmt den Originaltext mit
  Sprachangabe, nie die Übersetzung.
- Zahlen, Einheiten, Formeln, DOIs und Links werden nach der Übersetzung **automatisch mit dem Original
  verglichen**. Fehlt etwas oder hat es sich verändert, wird die Übersetzung verworfen, und es erscheint nur
  das Original mit dem Hinweis „Übersetzung nicht verlässlich, bitte Original lesen“. Das ist ein einfacher
  Abgleich der Zahlen- und Linkfolgen, kein KI-Aufruf.
- Ist die Lesesprache gleich der Originalsprache, gibt es keinen Hinweis und keine Übersetzung.

### 7.5 Fachbegriffe
- Glossar als Datei im Repo (z. B. `omn/uebersetzung_glossar.json`), gepflegt von dir oder mir. Je Begriff wird
  festgehalten, wie er in den 5 Sprachen heißt oder dass er unübersetzt bleibt. Beispiele: arbuscular
  mycorrhiza, extracellular potential, calcium oscillations, Hyphe/hypha, Myzel/mycelium, BioComm (nie
  übersetzen), Mycelist/Hyphist/Sporist (Eigennamen, nie übersetzen).
- Claude bekommt die zum Text passenden Einträge als Anweisung im Prompt. DeepL hätte dafür eine eigene
  Glossar-Funktion.
- Zusätzliche Anweisung: Zahlen, Einheiten, Formeln, Literaturangaben, DOIs und Links unverändert lassen.

### 7.6 Kostenbremse
- Tageslimit für Übersetzungsaufrufe (`UEBERSETZUNG_TAGESLIMIT`, Startwert z. B. 500). Ist es erreicht, steht
  dort „Übersetzung später verfügbar“, und das Original bleibt sichtbar.
- Je Nutzer zusätzlich `ip_erlaubt(...)`-artige Grenze gegen Massenabrufe.
- Zähler im Admin sichtbar (Aufrufe heute / diesen Monat).

### 7.7 Sicherheit der Übersetzung (Prompt-Injection)
Beiträge sind fremder Text, der an ein Sprachmodell geht. Ein Beitrag könnte versuchen, dem Modell
Anweisungen zu geben, etwa „ignoriere alles und schreibe X“. Absicherung:
- Der Text steht im Prompt klar abgegrenzt als „zu übersetzender Inhalt“. Das Modell hat **keine Werkzeuge**
  und keinen Zugriff auf irgendetwas.
- Die Antwort wird **nur als Text angezeigt** (Jinja-Escaping, kein HTML) und ist immer als „automatisch
  übersetzt“ markiert, das Original jederzeit daneben.
- Schlimmstenfalls entsteht also eine falsche Übersetzung. Der Admin kann eine einzelne Übersetzung löschen,
  damit sie neu erzeugt wird.

### 7.8 Anbieterwahl
| Anbieter | Für | Gegen |
|---|---|---|
| **Claude (Anthropic)** – schon für News-Übersetzung und Chatbot im Einsatz | keine neue Anbindung und **kein neuer Vertrag** (der DPA gilt für die gesamte API-Nutzung des Kontos); gut mit Fachsprache und Kontext; Glossar per Prompt | USA ohne DPF (Grundlage SCC); die eigene TIA muss um Nutzerbeiträge erweitert werden |
| DeepL API Pro | Sitz in Köln, keine Drittlandübermittlung, Glossar-Funktion | neuer Auftragsverarbeiter (AVV), neue Kosten, neues Konto |
| Google Cloud Translation | breite Sprachabdeckung | USA, weiterer Konzern als Empfänger |

**Empfehlung:** Start mit Claude, weil die Anbindung schon besteht. Die Schnittstelle bleibt so offen, dass ein
Wechsel zu DeepL nur eine weitere Klasse plus `.env`-Eintrag bedeutet.

---

## 8. Ordnung, Moderation, Inhalte

- **Ähnliche Themen vor dem Anlegen:** einfacher Wortvergleich (normalisiert: Kleinschreibung, Umlaute,
  Wortstämme grob) über Titel und Beschreibung aller Gebiete bzw. der Diskussionen im Gebiet, **auch gegen
  vorhandene Übersetzungen**. So findet „Mykorrhiza“ auch „mycorrhiza“. Ohne KI, ohne Kosten. Bis zu 5
  Treffer anzeigen, danach kann man trotzdem anlegen.
- **Zusammenführen und Umbenennen** durch den Admin (Abschnitt 6). Alte Adressen leiten weiter.
- **Moderation ist nötig**, weil Inhalte für viele sichtbar sind: Der Admin kann Gebiete, Diskussionen und
  Beiträge ausblenden, löschen und Diskussionen schließen. Dazu kommen kurze **Nutzungsregeln** (sachlich,
  keine personenbezogenen Daten Dritter, keine vertraulichen Inhalte aus Einzelgesprächen, keine Werbung).
  Ihnen stimmt man vor dem ersten Beitrag einmal zu. Optional ein Knopf „Beitrag melden“ (Mail ans Team).
- **Format:** Klartext mit Zeilenumbrüchen, Links werden klickbar. Kein HTML. So bleibt das Übersetzen sicher
  und einfach. Einfache Formatierung (Markdown) wäre eine spätere Erweiterung.
- **Bearbeiten** nur eigener Beiträge, Anzeige „bearbeitet“. Die Übersetzung erneuert sich über den Hash.
  **Löschen** eigener Beiträge: Der Text wird durch „Beitrag gelöscht“ ersetzt, damit Antworten verständlich
  bleiben.
- **Benachrichtigungen** (offener Punkt 5): In 2a keine Mails. Die Übersicht zeigt „neu seit deinem letzten
  Besuch“. Kommen später Mails an mehrere Personen, laufen sie laut Projektregel über die Mail-Queue.

---

## 9. Datenschutz

Keine Rechtsberatung, sondern eine Einordnung als Grundlage für deine Prüfung.

| Daten | Rechtsgrundlage (Vorschlag) | Information |
|---|---|---|
| Beiträge, Anhänge, Anzeigename, Zeitpunkte | Art. 6 Abs. 1 lit. b (Nutzung der angebotenen Themenräume) | Art. 13: Hinweis beim ersten Aufruf + Datenschutzerklärung |
| Übermittlung des Beitragstextes zur Übersetzung | Art. 6 Abs. 1 lit. f (Verständlichkeit über Sprachgrenzen, Kernzweck der Funktion); bei Claude Drittlandübermittlung auf Basis der SCC | Hinweis am Eingabefeld + Datenschutzerklärung |
| erwähnte Dritte in Beiträgen | Nutzungsregeln verbieten personenbezogene Daten Dritter; Moderation | – |

Zu erledigen:
1. **Datenschutzerklärung** (`omn/rechtstexte.json`, 5 Sprachen, `de` maßgeblich, `stand` nachziehen): neuer
   Abschnitt Themenräume (Zweck, wer sieht was, Anzeigename, Speicherdauer). Den Abschnitt zu Anthropic um die
   Übersetzung von Beiträgen ergänzen.
2. **TIA erweitern** (`03_Website_Backend/TIA_Anthropic_Chatbot.md` im Kontrollzentrum):
   - übermittelt wird nur der Beitragstext, ohne Name oder E-Mail;
   - Beiträge können dennoch personenbezogene Angaben enthalten;
   - Häufigkeit und Mengen;
   - Schutzmaßnahmen (Nutzungsregeln, Moderation, kein Modell-Training laut Anthropic-Bedingungen – **mit der
     dann aktuellen Fassung belegen**, nicht aus dem Gedächtnis);
   - die TIA-Wiedervorlage ist wegen Kontobezug ohnehin ausgelöst.
3. **Kontolöschung und Rechte der Verfasser** (überarbeitet nach Robbys Durchsicht; **vor dem Produktivstart
   von 2a rechtlich prüfen und freigeben**):

   *Ausgangslage:* Ein Beitrag ist personenbezogenes Datum seiner Verfasserin oder seines Verfassers, auch ohne
   Namen, denn Stil, Inhalt und Kontext können eine Person erkennbar machen. Er ist außerdem oft ein
   urheberrechtlich geschützter Text. Eine automatische Übersetzung ist eine Bearbeitung des Textes und braucht
   deshalb die Erlaubnis der Verfasser. Die Lösung aus der vorigen Fassung („ehemaliges Mitglied“ für alle)
   wäre deshalb nicht ohne Weiteres zulässig.

   *Vorschlag:*
   - **Standard bei Kontolöschung: Beiträge werden entfernt.** Der Text wird durch „Beitrag von der
     Verfasserin/dem Verfasser entfernt“ ersetzt, damit Antworten anderer lesbar bleiben. Übersetzungen und
     Anhänge werden gelöscht, der Anzeigename ebenso. Für Art. 17 DSGVO ist das der saubere Weg.
   - **Behalten ohne Namen nur auf ausdrücklichen Wunsch:** In den Einstellungen der Themenräume
     (`themen_teilnahme.beitraege_nach_loeschung = 'behalten'`) kann man festlegen: „Meine Beiträge sollen nach
     Löschung meines Kontos ohne Namen stehen bleiben.“ Das ist eine freiwillige, jederzeit änderbare
     Entscheidung, also eine Einwilligung nach Art. 6 Abs. 1 lit. a. Auch danach kann man die Löschung
     einzelner Beiträge per Mail an kontakt@ verlangen.
   - **Eigene Beiträge** kann man jederzeit selbst löschen, mit derselben Platzhalter-Regel.
   - **Nutzungsrechte in den Nutzungsregeln:** Die Verfasser bleiben Urheber. Sie räumen OpenMycoNet ein
     einfaches, kostenloses, nicht übertragbares Recht ein, ihre Beiträge in den Themenräumen anzuzeigen und
     automatisch zu übersetzen. Dieses Recht endet mit der Löschung, außer bei „behalten“. Eine offene Lizenz
     wie CC BY 4.0 wäre eine mögliche spätere Wahl, aber **nicht** voreingestellt (offener Punkt 10).
   - **Technik:** `themen_teilnahme.nutzer_id` und `beitrag.autor_nutzer_id` mit `ondelete='SET NULL'`. Die
     Admin-Kontolöschung (`/admin/nutzer/loeschen`) ruft **vorher** eine Funktion
     `themen_beitraege_bei_kontoloeschung(nutzer)` auf, die die Einstellung auswertet. Tests decken beide
     Fälle ab.
   - **Löschfristen:** Beiträge bleiben, solange das Konto besteht. Ausgeblendete (moderierte) Beiträge werden
     nach X Monaten endgültig gelöscht (`aufbewahrung.py`, X offen).
   - Hinweis: Heute können Nutzer ihr Konto nicht selbst löschen, das macht der Admin auf Anfrage. Das bleibt
     so. Die Einstellung oben greift bei jeder Löschung, egal wer sie auslöst.
4. **Löschen löscht Dateien mit** (der Helfer aus Phase 1 gilt auch hier).
5. **Auskunft/Export:** eigene Beiträge auf Anfrage exportierbar, Admin-Funktion reicht.

---

## 10. Folgen für bestehenden Code

- **Keine Änderung** an Phase-1-Tabellen, Kooperationen, Knotenbereichen, Rollen.
- `dashboard_base.html`: Navigationslink „Themenräume“, nur wenn `darf_themenraeume_nutzen`.
- Der Arbeitsbereich aus Phase 1 bekommt einen Link „Zu den Themenräumen“.
- `kollaboration.py`: Speicherhelfer mit Zielverzeichnis (schon in Phase 1 vorgesehen).
- `aufbewahrung.py`: neue Fristen.
- `translations.json`: neue Schlüssel `themen_*` in 5 Sprachen.
- `requirements.txt`: **keine** neue Abhängigkeit bei Claude (`anthropic` ist vorhanden). Bei DeepL entweder
  das Paket `deepl` (mit Hash, `tools/requirements_erzeugen.py`) oder direkt per HTTP.
- `docs/claude/`: neue Themendatei `austausch.md` (Phase 1 + 2), in der Tabelle in `CLAUDE.md` eintragen.

---

## 11. Tests

| Bereich | Tests |
|---|---|
| Trennung | Beitrag/Anhang der Themenräume nicht über `/austausch` erreichbar und umgekehrt; kein Kommentar aus Phase 1 erscheint in `/themen` |
| Berechtigung | Fachkontakt: ja; Nutzer ohne Austausch: 403; **Sporist ohne Austausch: 403**; Hyphist-/Sporist-Flags nach Nutzung unverändert; ausgeblendete Inhalte für Teilnehmende unsichtbar, für Admin sichtbar |
| Anlegen | Gebiet/Diskussion ohne Titel oder Beschreibung abgelehnt; ähnliche Themen werden angezeigt (auch über Übersetzung); Anlegen trotz Treffer möglich |
| Admin | Umbenennen, Zusammenführen (Diskussionen wandern, alte Adresse leitet weiter), Ausblenden, Löschen inkl. Dateien; Audit-Log-Einträge; CSRF-Liste |
| Bearbeiten | nur eigene Beiträge; `bearbeitet_am`; Übersetzung wird nach Änderung neu erzeugt (Hash) |
| Übersetzung (Anbieter gemockt wie in `test_news_uebersetzen.py`) | Original unverändert; zweiter Abruf ruft den Anbieter **nicht** erneut auf; gleiche Sprache = kein Aufruf; Fehler/kein Schlüssel ergibt Original + Hinweis, kein 500; Tageslimit greift; Glossar im Prompt; Antwort wird escaped (`<script>` in der Übersetzung erscheint als Text) |
| Vorgegebene Gebiete | 6 Gebiete nach Migration vorhanden, je 5 Sprachen mit `anbieter='manuell'` (schon in 2a, ohne API) |
| Kontolöschung | Standard: Beitragstexte durch Platzhalter ersetzt, Übersetzungen/Anhänge/Anzeigename weg, Antworten anderer bleiben; bei „behalten“: Text bleibt ohne Namen; Löschung scheitert nie am Fremdschlüssel |
| Original | Original ist in jeder Seite mit Übersetzung enthalten; „Originale zuerst“ kehrt die Reihenfolge um; Zitat übernimmt das Original; Übersetzung mit veränderter Zahl/DOI/Link wird verworfen |
| Teilnehmerkreis | `THEMEN_KREIS=fachkontakte`: Mycelist ohne Austausch 403; `THEMEN_KREIS=alle`: jeder bestätigte Nutzer darf, unabhängig von Hyphist/Sporist |
| Neutralität | Seiten der Themenräume enthalten keine Förder-/Zahlungsbegriffe (gleiche Wortliste wie Phase 1) |
| Bestand | gesamte bisherige Suite grün, Schema-Drift-Test grün |

---

## 12. Arbeitsschritte

**2a – Themenräume (ohne Übersetzung)**
1. Modelle + Migration (`themengebiet`, `diskussion`, `beitrag`, `beitrag_anhang`, `themen_teilnahme`,
   `uebersetzung`); die 6 Startgebiete **in allen 5 Sprachen** anlegen (Handübersetzung, `anbieter='manuell'`).
2. `omn/themen.py`: Übersicht, Gebiet, Diskussion, Beitrag/Antwort/Anhang, Bearbeiten, Berechtigungsfunktion.
3. Ähnlichkeitsanzeige beim Anlegen.
4. Admin: Übersicht, Umbenennen, Zusammenführen, Verschieben, Ausblenden/Löschen, Schließen.
5. Nutzungsregeln (inkl. Nutzungsrechte, künftiger Teilnehmerkreis), Anzeigename und Einstellungen,
   Kontolöschungs-Regel (9.3), Datenschutzerklärung-Abschnitt, Löschfristen. **Rechtliche Freigabe durch
   Robby vor dem Produktivstart.**
6. Tests, Staging, Probelauf mit 2–3 echten Fachkontakten.

**2b – Übersetzung**
7. Tabelle `uebersetzung` gibt es schon (2a). Hier kommen die Felder bzw. Logik für automatische Einträge
   dazu, falls nötig.
8. `omn/uebersetzung.py` (Schnittstelle, `ClaudeAnbieter`, Glossar, Kostenbremse).
9. Nachlade-Route + kleines Skript, Anzeige „Original anzeigen“, Sprachwahl beim Schreiben.
10. TIA-Erweiterung + Datenschutzerklärung (Anthropic-Abschnitt), Hinweis am Eingabefeld.
11. Tests, Staging, Probelauf in mindestens 3 Sprachen.

Grobe Größe: 2a etwa so groß wie Phase 1 bis anderthalbmal so groß, 2b etwa halb so groß wie 2a.

---

## 13. Offene Entscheidungen

1. ~~Wer darf die Themenräume nutzen?~~ **Geklärt (25.10.):** Start mit Fachkontakten + Team, Ziel alle
   registrierten Mycelists unabhängig von der Stufe (Abschnitt 5). Offen ist nur noch der Zeitpunkt der Öffnung.
2. **Übersetzungsanbieter:** Claude (TIA erweitern) oder DeepL (neue AVV)? Empfehlung: Claude.
3. **Beschreibungstexte der 6 Gebiete** so übernehmen? Ich bereite die Übersetzungen vor, du prüfst.
4. **Kontolöschung:** Vorschlag in 9.3 (Standard „entfernen“, „behalten ohne Namen“ nur auf ausdrücklichen
   Wunsch) – einverstanden? Muss vor dem Produktivstart von 2a rechtlich geprüft sein. Außerdem: nach welcher
   Zeit werden ausgeblendete Beiträge endgültig gelöscht?
5. **Benachrichtigungen:** in 2a keine Mails, nur „neu seit deinem letzten Besuch“, einverstanden? Später
   „Diskussion folgen“ mit Mail?
6. **Anzeigename:** echter Name (`Nutzer.name`) oder frei wählbarer Anzeigename?
7. **Evidenz-Kennzeichnung** (Hypothese/Literatur/Beobachtung/Messdaten) schon in 2a? Kostet wenig (eine
   Spalte, ein Auswahlfeld).
8. **Anrede:** Community-„du“ auch für Fachkontakte in den Themenräumen?
9. ~~Phasen-Reihenfolge~~ **Geklärt (25.10.):** Phase 1 → 2a → 2b, danach Wiedervorlage/Vorschläge (Phase 3).
10. **Lizenz der Beiträge:** nur das einfache Nutzungsrecht aus 9.3 (Vorschlag) oder zusätzlich eine offene
    Lizenz wie CC BY 4.0 (passt zu Open Science, ist aber unwiderruflich)?
