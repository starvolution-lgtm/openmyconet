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
| D. Pull Request nach `main` | offen, CI grün, Merge durch Robby / lokale Sitzung | https://github.com/starvolution-lgtm/openmyconet/pull/2 |
| Deploy Staging/Prod | nicht beauftragt | lokale Sitzung mit Robby |

**Tests:** lokal PostgreSQL 16.13 (264 bestanden) und SQLite (230 bestanden), Ruff und
Bandit grün. CI (backend, backend-postgres mit PostgreSQL 18 und Python 3.14, frontend-audit)
grün auf `d49d4ce` (letzter Code-Commit) und `434080d`; danach nur noch diese Doku-Änderung.

**Offen, nicht beauftragt:** HTTP-Endpunkt, Geräte-Authentifizierung, C4 (Format),
Node-Aggregate, Geräte-Qualität, Uhrkorrekturen, Objektspeicher für RAW.

**Fragen an Robby:** siehe `docs/dateneingang_teil2_bericht.md`, Abschnitt „Fragen“ (keine blockierend).
