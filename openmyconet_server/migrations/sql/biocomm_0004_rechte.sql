-- =============================================================================
-- BioComm Schema v4 -- Rechte (Migration 5c8d0f3a2e46), nur wenn die Rollen
-- omn_owner, omn und omn_geo existieren. Laeuft als Eigentuemer.
-- Standardrechte geben omn SELECT/INSERT. Zusaetzlich: Schluessel widerrufen
-- und die letzte Nutzung vermerken.
-- =============================================================================
GRANT UPDATE (revoked_at, last_used_at) ON sandbox.device_credential, live.device_credential TO omn;
REVOKE EXECUTE ON PROCEDURE biocomm_common.core_0004(text) FROM PUBLIC;
