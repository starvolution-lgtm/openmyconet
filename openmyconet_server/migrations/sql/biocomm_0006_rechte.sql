-- =============================================================================
-- BioComm Schema v6 -- Rechte (Migration 7a1c5e9d2b84), nur wenn die Rollen
-- omn_owner, omn und omn_geo existieren. Laeuft als Eigentuemer.
-- Standardrechte geben omn SELECT/INSERT. Zusaetzlich: Revision und
-- Sensormodelle einer schon bekannten Sonde nachtragen (nur NULL -> Wert, das
-- prueft der Code).
-- =============================================================================
GRANT UPDATE (revision, sensor_models) ON sandbox.probe, live.probe TO omn;
REVOKE EXECUTE ON PROCEDURE biocomm_common.core_0006(text) FROM PUBLIC;
