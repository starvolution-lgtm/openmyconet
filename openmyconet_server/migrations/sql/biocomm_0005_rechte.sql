-- =============================================================================
-- BioComm Schema v5 -- Rechte (Migration 6d9e1a4b3f57), nur wenn die Rollen
-- omn_owner, omn und omn_geo existieren. Laeuft als Eigentuemer.
-- Standardrechte geben omn SELECT/INSERT. Zusaetzlich: Schluessel widerrufen.
-- =============================================================================
GRANT UPDATE (revoked_at) ON sandbox.device_signing_key, live.device_signing_key TO omn;
REVOKE EXECUTE ON PROCEDURE biocomm_common.core_0005(text) FROM PUBLIC;
