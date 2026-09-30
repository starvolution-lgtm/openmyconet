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

## Offen: Abtastrate und EC-Takt (Stand 30.09.2026)

**Entscheidung (Robby, 30.09.2026):** Der ADS1115 kennt nur feste Datenraten
(8/16/32/64/128/250/475/860 SPS), 256 bzw. 1024 Werte pro Sekunde gehen damit nicht. Für die
realen Messungen sind **250 Werte pro Sekunde** vorgesehen. Der Oszillator des ADS1115 hat
±10 % Toleranz, echte Raten liegen also etwa zwischen 225 und 275. Die **tatsächliche Rate je
Rohdatenblock** muss deshalb mitgeschickt, gespeichert und verwendet werden. **Offen** ist, ob
die EC-Messung im echten Betrieb stündlich oder ereignisgesteuert läuft (die Website nennt
keinen Takt mehr; der Stundentakt der Sandbox bleibt, er gehört zur Simulation).

Website-Texte sind angepasst (Commit `0dfff91`). Noch **nicht** angepasst, nur geprüft:

| Stelle | Was dort passiert | Folge bei echter Rate 225–275 |
|---|---|---|
| `omn/eingang/einlesen.py:338–339` | Block wird abgelehnt, wenn seine Rate von `measurement_channel.sample_rate_hz` um mehr als 10⁻⁹ abweicht | Knoten mit gemessener Rate (z. B. 247,3) würde **REJECTED** – wichtigste Stelle |
| `omn/eingang/verdichtung.py:161, 186–193` | `samples_expected` aus der Nennrate des Kanals | Abdeckung z. B. 90 % oder über 100 % |
| `omn/datenlabor.py:398` | API `roh` meldet `rate_hz` als ganze Zahl des letzten Blocks | 247,8 → 247 |
| `app/static/datenlabor.js:677` | Lückenerkennung im Rohdaten-Diagramm mit dieser einen Rate | ungenau bei Blöcken mit verschiedenen Raten |
| `omn/eingang/ereignisse.py:200` | `planned_sample_rate_hz` aus `LAUF_START` | in Ordnung, solange nur Plan |

Schon richtig: `sample_block.sample_rate_hz` je Block (Format v1 als exakter Bruch,
`format_v1.py:164`), Zeitpunkte in der Verdichtung (`verdichtung.py:305–307`) und in der
Rohdatenansicht (`datenlabor.py:381, 392–396`) aus der Blockrate. Der Sandbox-Generator rechnet
bewusst fest mit `RATE_HZ = 250` (`omn/sandbox/szenarien.py:20`), das ist Simulation.

**Paketformat v1:** Die drei Testvektoren (`docs/dateneingang_format_v1*.omb`) und die
Beispiele in `docs/dateneingang_format_v1.md` verwenden noch **256/1 Hz** und EC-Pausen
„stündlich“. Das Format selbst ist davon unabhängig (Rate als exakter Bruch, Pausen als
Regel). Umstellen zusammen mit der Firmware: neue Testvektoren mit 250 Hz bzw. der gemessenen
Rate, Test `tests/test_format_v1.py` nachziehen.
