# Status: BioComm-Dateneingang

Stand: 25.09.2026 · Branch `dateneingang-prototyp` · Bearbeitung: Cody (Cloud-Sitzung)

| Bereich | Status | Nachweis |
|---|---|---|
| Teil 1: Prototyp Eingang (Format v0, Prüfen, Einordnen, Kette, CLI, Testknoten) | erledigt | `docs/dateneingang_prototyp_bericht.md` |
| A. Versionierte Aggregate (`biocomm_0002`), Verdichtung über Lücken | erledigt | `tests/test_dateneingang.py::test_verdichtung_ueber_luecken_mit_versionen` |
| B. Konflikte: Kettenbeweis automatisch, sonst manuell (SECURITY DEFINER + Protokoll) | erledigt | `test_kettenbeweis_*`, `test_manuelle_aufloesung_per_cli`, `test_rechte_als_rolle_omn` |
| C1. Leser nur CANONICAL / jüngste Aggregat-Version | erledigt | `test_leser_zeigen_keine_konfliktkandidaten` |
| C2. Größengrenzen je Paket | erledigt | `test_groessengrenzen` |
| C3. Index `batch_delivery.transport_hash` | erledigt | `test_index_fuer_schon_eingelesen` |
| C4. Test „Kanal nur als DERIVED“ | erledigt | `test_kanal_nur_als_derived` |
| E. Verdichtung automatisch (26.09.2026): nur geänderte Läufe/Zeiträume, Funkstille, Cron alle 5 min | erledigt | `test_verdichtung_automatisch_nur_geaenderte_laeufe`, `test_verdichtung_schliesst_nach_funkstille_ab`, `test_verdichtung_per_cli_fuer_den_zeitgeber` |
| F. Node-Signaturen (26.09.2026): Ed25519, Schema v5, live Pflicht, `flask biocomm-knotenschluessel` | erledigt | `tests/test_signatur.py`, `test_format_v1.py::test_testvektor_signiert_ist_stabil` |
| D. Pull Request nach `main` | offen, CI grün, Merge durch Robby / lokale Sitzung | https://github.com/starvolution-lgtm/openmyconet/pull/2 |
| Deploy Staging/Prod | nicht beauftragt | lokale Sitzung mit Robby |

**Tests:** lokal PostgreSQL 16.13 (264 bestanden) und SQLite (230 bestanden), Ruff und
Bandit grün. CI (backend, backend-postgres mit PostgreSQL 18 und Python 3.14, frontend-audit)
grün auf `d49d4ce` (letzter Code-Commit) und `434080d`; danach nur noch diese Doku-Änderung.

**Offen, nicht beauftragt:** HTTP-Endpunkt, Geräte-Authentifizierung, C4 (Format),
Node-Aggregate, Geräte-Qualität, Uhrkorrekturen, Objektspeicher für RAW.

**Fragen an Robby:** siehe `docs/dateneingang_teil2_bericht.md`, Abschnitt „Fragen“ (keine blockierend).

## Abtastrate (erledigt 14.10.2026) und EC-Takt (offen)

**Entscheidung (Robby, 30.09.2026):** Der ADS1115 kennt nur feste Datenraten
(8/16/32/64/128/250/475/860 SPS), 256 bzw. 1024 Werte pro Sekunde gehen damit nicht. Für die
realen Messungen sind **250 Werte pro Sekunde** vorgesehen. Der Oszillator des ADS1115 hat
±10 % Toleranz, echte Raten liegen also etwa zwischen 225 und 275. Die **tatsächliche Rate je
Rohdatenblock** wird mitgeschickt, gespeichert und verwendet. **Offen** ist nur noch, ob
die EC-Messung im echten Betrieb stündlich oder ereignisgesteuert läuft (die Website nennt
keinen Takt mehr; der Stundentakt der Sandbox bleibt, er gehört zur Simulation).

**Umgesetzt 14.10.2026** (Test `test_dateneingang.py::test_gemessene_abtastrate`):

| Stelle | Jetzt |
|---|---|
| `omn/eingang/einlesen.py` | Blockrate darf um `RATE_TOLERANZ` = 12 % (Datenblatt + Spielraum) von der Nennrate des Kanals abweichen, weiter daneben → **REJECTED** (falsch konfigurierter Knoten) |
| `omn/eingang/verdichtung.py` | `samples_expected` je Fenster mit dem Mittel der Blockraten seiner Werte; Fenster ohne Werte mit dem Mittel der geladenen Blöcke, ohne Blöcke mit der Nennrate |
| `omn/datenlabor.py` | API `roh`: `rate_hz` = Mittel über die gezeigten Werte (2 Nachkommastellen), neu `rate_min_hz` |
| `app/static/datenlabor.js` | Lückenerkennung mit der kleinsten Blockrate, Anzeige mit einer Nachkommastelle |
| `omn/eingang/ereignisse.py` | `planned_sample_rate_hz` aus `LAUF_START` = Nennrate, unverändert (Plan) |
| `omn/eingang/testknoten.py` | `TestKnoten.ist_rate`: tatsächliche Rate neben der Nennrate |

Schon richtig: `sample_block.sample_rate_hz` je Block (Format v1 als exakter Bruch,
`format_v1.py:164`), Zeitpunkte in der Verdichtung (`verdichtung.py:305–307`) und in der
Rohdatenansicht (`datenlabor.py:381, 392–396`) aus der Blockrate. Der Sandbox-Generator rechnet
bewusst fest mit `RATE_HZ = 250` (`omn/sandbox/szenarien.py:20`), das ist Simulation.

**Paketformat v1:** Die drei Testvektoren (`docs/dateneingang_format_v1*.omb`) und die
Beispiele in `docs/dateneingang_format_v1.md` verwenden noch **256/1 Hz** und EC-Pausen
„stündlich“. Das Format selbst ist davon unabhängig (Rate als exakter Bruch, Pausen als
Regel). Umstellen zusammen mit der Firmware: neue Testvektoren mit 250 Hz bzw. der gemessenen
Rate, Test `tests/test_format_v1.py` nachziehen.
