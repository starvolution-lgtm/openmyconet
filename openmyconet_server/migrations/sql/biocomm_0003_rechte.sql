-- =============================================================================
-- BioComm Schema v3 -- Rechte (Migration 4b7c9e2d1f35), nur wenn die Rollen
-- omn_owner, omn und omn_geo existieren. Laeuft als Eigentuemer.
-- Die Standardrechte des Rollen-Skripts geben omn auf die neuen Tabellen
-- SELECT/INSERT. Zusaetzlich: einen Einsatz beenden (valid_to).
-- =============================================================================
GRANT UPDATE (valid_to) ON sandbox.device_deployment, live.device_deployment TO omn;
REVOKE EXECUTE ON PROCEDURE biocomm_common.core_0003(text) FROM PUBLIC;
