-- =============================================================================
-- BioComm Schema v2 -- Rechte (Migration 8d4e2a6c1b70), wie 0001 nur, wenn die
-- Rollen omn_owner, omn und omn_geo existieren. Laeuft als Eigentuemer.
--
-- Die Standardrechte des Rollen-Skripts geben omn auf neue Tabellen und
-- Sichten SELECT/INSERT. Hier nur die Abweichungen:
-- - Protokoll der Kandidatenwahl: omn darf lesen, aber NICHT selbst einfuegen;
--   Eintraege entstehen nur in kandidat_festlegen() (SECURITY DEFINER).
-- - Die Sicht derived_aggregate_current ist nur zum Lesen da.
-- - omn darf kandidat_festlegen() ausfuehren (Standardrechte nehmen PUBLIC das
--   EXECUTE auf Routinen von omn_owner). Loeschrechte bekommt omn nicht.
-- =============================================================================
REVOKE INSERT ON sandbox.candidate_resolution_log, live.candidate_resolution_log FROM omn;
GRANT SELECT ON sandbox.candidate_resolution_log, live.candidate_resolution_log TO omn;
REVOKE INSERT ON sandbox.derived_aggregate_current, live.derived_aggregate_current FROM omn;
GRANT SELECT ON sandbox.derived_aggregate_current, live.derived_aggregate_current TO omn;
REVOKE ALL ON FUNCTION biocomm_common.kandidat_festlegen(text, bigint, text, jsonb, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION biocomm_common.kandidat_festlegen(text, bigint, text, jsonb, text, text) TO omn;
REVOKE EXECUTE ON PROCEDURE biocomm_common.core_0002(text) FROM PUBLIC;
