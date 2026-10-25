# Fachlicher Austausch mit eingeladenen Fachkontakten (seit 25.10.2026)

Pläne: `docs/austausch_phase1_plan.md` (umgesetzt), `docs/austausch_phase2_plan.md`
(Themenräume + Übersetzung, nur Architektur, **nicht** freigegeben).

## Wozu
Gespräche, die z. B. auf LinkedIn oder per Mail begonnen haben, in einem geschützten
Bereich fortführen. Kostenlos, ohne jeden Bezug zu Förderung/Zahlung, **keine
Mitgliedsstufe**: „Fachkontakt“ ist nur die interne Lesart „hat einen Austausch“, kein
Feld an `Nutzer`, nirgends für Nutzer sichtbar.

## Aufbau
- Tabelle `austausch` (Modell `Austausch`, timestamptz, Migration `ea38adc43e8d`).
  **Bewusst nicht `foerderer`**: aktive Förderer-Zeilen erscheinen öffentlich
  (`site_live._aktive_foerderer`) und ihre Freigabe setzt Hyphist. Status
  `vorbereitet → eingeladen → aktiv → beendet/gesperrt`, nie `active`.
- Dritter Kontext des Kollaborationsbereichs: `aufgabe.austausch_id`,
  `kommentar.austausch_id` (CASCADE). Logik in `omn/kollaboration.py`.
- Zugriff **nur** über `kollaboration.austausch_bereiche_von(nutzer)` /
  `darf_austausch_sehen(nutzer, a)`: `nutzer_id` + Status `aktiv`, **kein E-Mail-Fallback**
  (anders als `kooperationen_von`). Phase 4 (mehrere Teilnehmer) ändert nur diese zwei.
- `omn/austausch.py`: Helfer (Zeit, Fristen, Löschen inkl. Dateien), Einladung, Code,
  Blueprint `austausch_bp` (`/austausch/einladung/<token>`, `/austausch`).
- `omn/admin/austausch.py`: `/admin/austausch` (Liste, Vorbereiten/Bearbeiten,
  Detail mit Arbeitsbereich, Einladen, Sperren/Beenden/Wieder öffnen, Geprüft,
  Löschsperre, Sofort löschen). Alles POST + `protokollieren`, in
  `test_csrf.AENDERNDE_ADMIN_ROUTEN`.

## Einladung (Sicherheit)
Token nur als SHA-256 (`einladung_token_hash`), 14 Tage, neuer Versand macht den alten
Link ungültig. **GET der Einladungsseite ändert nichts** (Mail-Scanner). „Annehmen“
schickt einen 6-stelligen Code an die **gespeicherte** Adresse (HMAC mit SECRET_KEY,
15 min, 5 Fehlversuche, 3 je Stunde, nur in derselben Browser-Session). Erst der
richtige Code löst **atomar** ein (bedingtes UPDATE), legt ein Konto an (bestätigt,
`keine_mails=True`, keine Rolle) bzw. verknüpft das bestehende **ohne** Rollen-/
Einstellungsänderung (nur `bestaetigt` wird gesetzt) und loggt ein.

## Sprache und Anrede
5 Sprachen über `translations.json` (Schlüssel `austausch_*`), Anrede je Kontakt
(`austausch.anrede` formell/informell, Standard formell: Sie/u/vous/usted):
Schlüssel mit Anrede-Unterschied als `…_formell`/`…_informell`, abgerufen über
`kollaboration.ta()` bzw. `austausch.txa()`. Mails: `t(key, lang)` mit ausdrücklicher
Sprache (Einladung: `austausch.sprache`, danach `Nutzer.sprache`). Seiten: Website-
Sprachwahl. Community-Oberfläche (`dashboard_base`, Login) bleibt beim „du“.

## Fristen (`omn/aufbewahrung.py`)
F1 nicht angenommen → 2 Jahre nach der (letzten) Einladung, ganzer Austausch (dieselbe
Frist wie MCC-Kontakte, damit für eine Person nur **eine** Frist gilt – Robby 25.10.);
F1a nur vorbereitet, nie eingeladen → 1 Monat (Art. 14 Abs. 3 lit. a), nach 3 Wochen
einmal Admin-Mail (`austausch.vorbereitet_erinnern`, im Cron von `flask aufbewahrung-
bereinigen`, Spalte `vorbereitet_erinnert_am`);
F3 Profil-Link, Gesprächsbeginn, Vorgeschichte → 24 Monate nach `letzte_aktivitaet`
geleert; F4 beendet/gesperrt → 6 Monate nach `status_geaendert_am`, ganzer Austausch;
F2 Inaktivität 12 Monate → **nur** Markierung im Admin. Aktive Löschsperre (Grund +
Datum, Admin) setzt F1–F4 aus. Ganze Austausche über `AUSTAUSCH_LOESCHEN` (ORM-Löschen
+ Dateien nach dem Commit), **nie** über `FRISTEN` (Massen-DELETE ließe Dateien liegen).
Kontolöschung im Admin sperrt den Austausch (→ F4); Löschwunsch = „Endgültig löschen“.
Datenschutzerklärung Abschnitt `austausch` (9.) nennt genau diese Fristen.

## Immer gültig
- Nichts, was ein Fachkontakt sieht (Seiten, Mails, URLs), enthält Förder-/Zahlungs-
  begriffe oder „Fachkontakt“/„Kooperation“/„Hyphist“ (`test_austausch.VERBOTEN`).
- Admin-only Felder (LinkedIn, Notiz, Gesprächsbeginn, Kontaktdaten) werden dem
  Arbeitsbereich-Template **gar nicht** übergeben.
- Ein Austausch vergibt nie eine Rolle (`roles.py` wird nicht aufgerufen).
- Neue Texte: alle 5 Sprachen und, wenn Anrede vorkommt, beide Fassungen.
- Rechtlich geprüft und freigegeben von Robby am 25.10.2026 (`docs/austausch_rechtspruefung.md`,
  Interessenabwägung + VVT-Eintrag im Kontrollzentrum `03_Website_Backend`). Änderungen an
  Datenarten, Fristen oder Texten → Datenschutzerklärung Abschnitt 9 + Interessenabwägung nachziehen.

## Phase 2a: Wissenschaftliche Themenräume (seit 25.10.2026)
Gemeinsamer Bereich `/themen` (Blueprint `omn/themen.py`), Moderation `/admin/themen`
(`omn/admin/themen.py`). Themengebiet → Diskussion → Beitrag (eine Ebene Antworten, optionale
Evidenz-Art, Anhänge unter `instance/uploads/themen/`), `themen_teilnahme` (frei wählbarer
Anzeigename, Zustimmung zur Regelfassung `REGELN_FASSUNG`, „Originale zuerst“), `uebersetzung`
(an den Hash des Originals gebunden; 2a nur Handübersetzungen der 6 Startgebiete, Migration
`8be9ab181351`). Ähnliche Themen beim Anlegen: Wortvergleich ohne KI (`themen.aehnliche`).
- **Schalter `THEMEN_FREIGEGEBEN`** (Config): auf Prod (`OMN_ENV=prod`) aus → alle `/themen`-Routen
  404, kein Link; Staging an. Erst nach Robbys Rechtsprüfung umstellen (`docs/themen_rechtspruefung.md`).
- **Kreis `THEMEN_KREIS`**: `fachkontakte` (aktiver Austausch) | `alle` (bestätigte Nutzer). Nur über
  `themen.darf_themenraeume_nutzen` prüfen – nie Rolle/Förderung.
- **Wissen bleibt** (Robby 25.10.): Beiträge CC BY 4.0; Kontolöschung → Beiträge bleiben ohne Namen
  („ehemaliges Mitglied“, `autor_nutzer_id` NULL, `von_team` False); eigene Beiträge entfernen = Text
  leer + `entfernt_am`, Platzhalter bleibt. Ausgeblendete Beiträge (`ausgeblendet_am`) nach 6 Monaten
  gelöscht (`aufbewahrung.py`). Datenschutzerklärung Abschnitt `themenraeume` (10.).
- Texte ohne direkte Anrede (`themen_*` in `translations.json`, 5 Sprachen).
- **Getrennt vom Austausch:** keine FKs zu aufgabe/kommentar/austausch (Test), eigene Download-Route.
- Ändert sich die Regelfassung, `REGELN_FASSUNG` erhöhen (alle stimmen neu zu).
