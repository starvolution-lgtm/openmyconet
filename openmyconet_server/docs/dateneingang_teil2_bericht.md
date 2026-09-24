# Bericht: BioComm-Dateneingang, Teil 2

Stand 25.09.2026 · Branch `dateneingang-prototyp` · Auftrag von Robby vom 24.09.2026.
Nichts deployt, kein Server angefasst, das Rollen-Skript nicht ausgeführt.

## Kurzfassung

Alle Punkte A bis C sind umgesetzt und getestet. Dafür gibt es eine neue Migration
`8d4e2a6c1b70` mit `migrations/sql/biocomm_0002_*.sql`. Die 0001-Dateien bleiben
unverändert, die Änderung gilt über `biocomm_common.core_0002` für `sandbox` und `live`.

- **Aggregate** sind jetzt versioniert. Die Verdichtung läuft auch über Lücken, jede
  Nachlieferung erzeugt eine neue Version, und Leser sehen nur die jüngste.
- **Konflikte** werden automatisch nur bei einem Kettenbeweis aufgelöst, sonst manuell
  (`flask biocomm-konflikt`). Beides läuft über eine `SECURITY DEFINER`-Funktion mit
  unveränderlichem Protokoll. `omn` kann weiterhin nichts löschen.
- **Pflichtpunkte vor Live:**
  - Das Datenlabor zeigt nur kanonische Daten.
  - Es gibt Größengrenzen je Paket.
  - Der Index auf `batch_delivery` ist angelegt.
  - Der Test für „Kanal nur als DERIVED“ ist ergänzt.

## A. Versionierte Aggregate

- **Schema:** Das Schema bekommt zwei neue Spalten:
  - `derived_aggregate.aggregate_version` (Teil des Primärschlüssels);
  - `computed_at` (Zeitpunkt der Berechnung).

  Aggregate sind jetzt unveränderlich (Trigger). Die Sicht
  `derived_aggregate_current` liefert je Fenster die höchste Version. Bestehende
  Zeilen (Sandbox-Generator) werden Version 1.
- **Grabstein:** Hat ein Fenster keine gültigen Samples mehr, zum Beispiel weil sein
  Batch in Konflikt geraten ist, wird eine Version mit `samples_recorded = 0` und leeren
  Werten eingefügt. Die Sicht blendet sie aus. Fehlend bleibt fehlend, es entsteht nie
  ein Nullwert.
- **Verdichtung** (`omn/eingang/verdichtung.py`):
  - Es zählen nur Blöcke kanonischer Batches.
  - Ein Fenster wird berechnet, sobald es abgeschlossen ist. Das heißt: Sein Ende liegt
    vor dem letzten Sample des Kanals oder vor dem Ende des Messlaufs. Lücken in der
    Kette halten nichts mehr an.
  - Ein Fenster wird neu berechnet, wenn ein Batch, der es berührt, neuer ist als die
    aktuelle Version (`status_changed_at > computed_at`). Das betrifft neue Batches,
    Nachlieferungen, Konflikte und getauschte Kandidaten.
  - Weicht das Ergebnis von der aktuellen Version ab, wird eine neue Version eingefügt.
- **`samples_expected`** = Abtastrate × geplante Messzeit im Fenster, also innerhalb des
  Messlaufs, innerhalb der `RECORDING`-Intervalle und ohne die `PAUSE`-Intervalle des
  Kanals. Fehlende Samples sind damit als Differenz zu `samples_recorded` sichtbar.
- **Annahme V1 (Samples je Kanal in Sequenzreihenfolge):** Für die Richtigkeit ist sie
  **nicht mehr nötig**. Sie bestimmt nur noch, wie oft ein Fenster neu versioniert wird,
  und begründet, warum ein Fenster erst nach dem Horizont verdichtet wird. Hält die
  Firmware V1 nicht ein, entstehen mehr Versionen, aber keine falschen Werte.

## B. Konfliktauflösung

- **Kettenbeweis (automatisch):** Verweisen die kanonischen Nachfolger (Sequenz + 1) per
  `previous_batch_hash` auf **genau einen** Kandidaten eines strittigen Platzes, wird
  dieser `CANONICAL` (`status_basis = SUCCESSOR_LINK`). Die anderen bleiben `CONFLICT` in
  Quarantäne. Geprüft wird in drei Fällen:
  - nach jedem Konflikt, wenn der Nachfolger schon da ist;
  - nach jedem neuen kanonischen Batch, wenn der Nachfolger später kommt;
  - rückwärts mehrstufig, denn ein neu kanonischer Kandidat kann seinen eigenen
    Vorgänger beweisen.
- **Manuell:**
  - `flask biocomm-konflikt` listet die offenen Konflikte.
  - `flask biocomm-konflikt --gewinner ID --von NAME --grund TEXT [--verdichten]` legt
    einen Kandidaten fest (`MANUAL_REVIEW`). Name und Begründung sind Pflicht.
- **Datenbankfunktion** `biocomm_common.kandidat_festlegen` (SECURITY DEFINER,
  Eigentümer `omn_owner`, `search_path` fest):
  - Sie nimmt dieselbe Sperre je Messlauf wie der Eingang.
  - Beim Kettenbeweis prüft sie den Beweis selbst.
  - Sie entfernt die `sample_block`-Zeilen der übrigen Kandidaten und schreibt die des
    Gewinners. Dessen Blockpayloads müssen zusammen seinen `payload_hash` ergeben, das
    prüft die Funktion.
  - Sie protokolliert jeden Schritt in `candidate_resolution_log`: `CHOSEN` oder
    `SET_ASIDE`, Grundlage, wer (`performed_by` und die angemeldete Datenbankrolle),
    wann, Begründung und die Zahl der Blöcke.
  - Das Protokoll ist unveränderlich, `omn` darf es nur lesen.
- **Löschen:** `omn` hat weiterhin kein DELETE-Recht. Der Löschschutz von `sample_block`
  lässt DELETE nur zu, wenn die Transaktion die Markierung `biocomm.kandidat_festlegen`
  gesetzt hat **und** der Ausführende Eigentümer der Tabelle ist. Beides gibt es nur
  innerhalb der Funktion. Ich habe mich gegen `ALTER TABLE … DISABLE TRIGGER`
  entschieden, weil das `sample_block` exklusiv sperren würde.
- Der Schalter `KONFLIKT_STUFT_BESTEHENDEN_ZURUECK` bleibt auf „beide `CONFLICT`“.

## C. Pflichtpunkte vor Live-Betrieb

1. **Leser:** Das Datenlabor (Rohdaten, Rohdatenstunden, Zeitreihen) liest `sample_block`
   nur noch über kanonische Batches und Aggregate nur noch über
   `derived_aggregate_current`. Weitere Leser gibt es im Code nicht. Ein Test legt einen
   `CONFLICT` an und prüft, dass Rohdaten und Minutenwert im Datenlabor verschwinden.
2. **Größengrenzen:**
   - `MAX_PAKET_BYTES` (roh, 4 MiB) und `MAX_ENTPACKT_BYTES` (Summe der entpackten
     Blöcke, 32 MiB) führen zu `REJECTED` mit Grund, bevor etwas entpackt wird.
   - Unbekannte Kodierungen werden jetzt abgelehnt, weil sich ihre Größe nicht begrenzen
     lässt.
3. **Index:** `batch_delivery (transport_code, transport_hash)`.
4. **Test „Kanal nur als DERIVED“:** ergänzt.

## Tests

- **Lokal (Cloud-Rechner, PostgreSQL 16.13):**
  - komplette Suite: **264 bestanden, 3 übersprungen**;
  - SQLite: **230 bestanden, 37 übersprungen**;
  - `ruff check .` grün, `bandit -ll` ohne Befund.
  - PostgreSQL 18 ist hier weiterhin nicht installierbar (Paketquelle gesperrt). PG 18
    prüft die CI.
- **Neue oder geänderte Tests** in `tests/test_dateneingang.py` (24 Tests):
  - Konflikt ohne Beweis bleibt offen;
  - Kettenbeweis zugunsten des ersten Kandidaten;
  - Kettenbeweis zugunsten des zweiten, bei dem der Nachfolger erst später kommt und die
    Blöcke getauscht werden;
  - manuelle Auflösung per CLI (Pflichtangaben, Funktion verweigert einen falschen
    Kettenbeweis, Protokoll, zweiter Versuch wird abgelehnt);
  - Verdichtung über Lücken mit zweimaligem Nachliefern (Versionen 1, 2, 3; Leser sieht
    nur die jüngste; Mittelwert nachgerechnet);
  - `samples_expected` mit geplanter Pause;
  - Leser zeigen keine Konfliktkandidaten (Datenlabor-API, mit Grabstein);
  - Größengrenzen, Kanal nur als DERIVED, Index vorhanden;
  - Rechte als `omn`: ganzer Weg inklusive zweistufigem Kettenbeweis und manueller
    Auflösung.
- **Gegenprobe als `omn`** (alle verweigert):
  - `DELETE` auf `sample_block`, auch mit gesetzter Markierung;
  - `DELETE`/`UPDATE` auf Aggregate;
  - Einfügen ins Protokoll;
  - Ändern von `payload_hash`;
  - Lesen von `*_private`.
- **Migrationstests:** Die 43 Regeltests, die Schema-Parität, die Idempotenz und das
  Downgrade laufen mit Schema v2 grün.
- **CI auf dem letzten Commit:** siehe Pull Request (Abschnitt Lieferung).

## Neue oder geänderte Annahmen

- **Kettenbeweis:** Nur **kanonische** Nachfolger zählen. Ist der Nachfolgerplatz selbst
  strittig, gibt es keinen Beweis, bis er geklärt ist; danach geht es rückwärts weiter.
  **Beobachteter Sonderfall:** Ein Nachfolger kann einen Kandidaten beweisen, dessen
  eigener Vorgänger den Platz davor verloren hat, also zwei auseinanderlaufende Ketten.
  Der Gewinner steht dann sichtbar auf `PREDECESSOR_MISSING`; aufgelöst wird davor nichts
  automatisch.
- **Überschneidungskonflikte** (gleiche Sample-Indizes auf verschiedenen Sequenzplätzen)
  kann die Funktion nicht auflösen. Sie meldet das ausdrücklich. Dafür wäre ein
  Eingriff als `omn_owner` nötig.
- **Blockangaben bei der Auflösung:** Die Funktion prüft die Payloads über den Hash.
  Kanal, Lauf und RAW sichern die Fremdschlüssel. Zeitanker, Index und Rate kommen vom
  Aufrufer (aus dem Quarantäne-Paket) und sind in Format v0 **nicht** durch einen Hash
  gedeckt. Vorschlag für C4: die Blockangaben in den `payload_hash` aufnehmen.
- **Ablage des Gewinners:** Ein per Auflösung gewählter Gewinner behält
  `payload_location = INLINE`, weil die Spalte nicht änderbar ist; er hat zusätzlich
  `sample_block`-Zeilen.
- **Welche Messläufe verdichtet werden:** `flask biocomm-verdichten` ohne `--lauf`
  verdichtet nur Läufe, die über den Eingang beliefert wurden (Anlieferung mit
  `transport_hash`). Die Modell-Aggregate des Sandbox-Generators bleiben so unberührt.
- **Grenzwerte** 4 MiB / 32 MiB sind Prototyp-Werte. Ein Paket mit 60 s Bio-Rohdaten hat
  rund 25 KB.
- `db_user` im Protokoll ist `session_user`, also die angemeldete Rolle (auf dem Server
  `omn`, in den Tests `postgres`).

## Hinweise für die lokale Sitzung (Deploy mit Robby)

- **Migration `8d4e2a6c1b70`:**
  - Sie läuft wie `3f1b2c4d5e6a`: als `omn`, der BioComm-Teil über eine eigene
    Verbindung als `omn_owner` (Passwort aus `~/.pgpass`).
  - Es gibt keine neuen Rollen und keine Änderung am Rollen-Skript.
  - Die Rechte-Datei `biocomm_0002_rechte.sql` gibt `omn` nur `EXECUTE` auf
    `kandidat_festlegen` und nimmt ihm `INSERT` auf Protokoll und Sicht.
- **Dauer:** Auf Staging und Prod baut die Migration den Primärschlüssel von
  `sandbox.derived_aggregate` neu auf (Generator-Daten). Das dauert je nach Datenmenge
  einige Sekunden bis Minuten; das DB-Backup in `release.sh` läuft vorher.
- **Downgrade:** Er verweigert sich, sobald es eine zweite Aggregat-Version oder einen
  Protokolleintrag gibt.

## Fragen an Robby

**Blockierend:** keine.

**Kann warten:**

1. **Wer schreibt die Node-Firmware?** Davon hängt ab, wer das Paketformat (C4) und
   Zusagen wie V1 verbindlich festlegt. Für diesen Auftrag blockiert das nichts, weil V1
   nicht mehr für die Richtigkeit gebraucht wird.
2. **Überschneidungskonflikte:** Sollen sie ein eigenes Werkzeug bekommen, oder bleiben
   sie ein seltener Eingriff von Hand?
3. **Wer darf manuell auflösen?** Soll die manuelle Auflösung wie jetzt jede Sitzung als
   `omn` ausführen dürfen, oder soll sie auf eine eigene Rolle beschränkt werden?
4. **Grenzwerte:** Sind 4 MiB roh und 32 MiB entpackt je Paket als Startwerte recht?
5. **Statusdatei:** Die im Auftrag genannte Statusdatei „im vorgegebenen Format“ habe ich
   im Repo nicht gefunden. Ich habe `docs/dateneingang_status.md` angelegt. Bitte sagt
   mir, welches Format gemeint ist, dann passe ich sie an.

## Nicht Teil dieses Auftrags (unverändert offen)

HTTP-Endpunkt, Geräte-Authentifizierung und Signaturen, Node-seitige Aggregate,
Geräte-Qualität, Uhrkorrekturen, Objektspeicher für RAW, Staging/Prod.
