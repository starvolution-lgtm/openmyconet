-- =============================================================================
-- BioComm Schema v1 -- Rechte nach Anlage der Tabellen (Rollen-Variante A)
-- Wird von der Migration 3f1b2c4d5e6a NUR ausgefuehrt, wenn die Rollen
-- omn_owner, omn und omn_geo existieren (Server nach deploy/biocomm_roles_setup.sql;
-- in CI/lokal fehlen sie -> Datei wird uebersprungen). Laeuft als Tabellen-Owner.
--
-- Grundrechte (SELECT/INSERT fuer omn, SELECT fuer omn_geo, *_private nur fuer
-- omn_geo) setzen schon die ALTER DEFAULT PRIVILEGES des Rollen-Skripts. Hier
-- nur, was sich nicht per Standardrecht ausdruecken laesst: Spaltenrechte fuer
-- die Statusfelder, die sich laut Modell aendern duerfen. Alle anderen
-- Aenderungen verhindern zusaetzlich die Unveraenderlichkeits-Trigger.
-- =============================================================================
GRANT UPDATE (batch_status, chain_state, status_basis, status_changed_at)
    ON sandbox.origin_batch, live.origin_batch TO omn;
GRANT UPDATE (origin_batch_id, delivery_status, status_reason, status_changed_at)
    ON sandbox.batch_delivery, live.batch_delivery TO omn;
GRANT UPDATE (execution_state, actual_start, actual_duration_ms, attempted_at,
              state_reason, state_changed_at)
    ON sandbox.stimulation, live.stimulation TO omn;
GRANT UPDATE (ended_at, end_reason, reset_cause)
    ON sandbox.acquisition_run, live.acquisition_run TO omn;
GRANT UPDATE (valid_to)
    ON sandbox.site_timezone, live.site_timezone TO omn;
GRANT UPDATE (is_public) ON sandbox.sandbox_scenario TO omn;
-- omn_geo schreibt die oeffentliche Rasterzelle
GRANT UPDATE (grid_cell_id) ON sandbox.site, live.site TO omn_geo;
-- ausdruecklich: omn hat auf die privaten Tabellen keinerlei Rechte
REVOKE ALL ON ALL TABLES IN SCHEMA sandbox_private, live_private FROM omn;
REVOKE EXECUTE ON PROCEDURE biocomm_common.create_core(text) FROM PUBLIC;
