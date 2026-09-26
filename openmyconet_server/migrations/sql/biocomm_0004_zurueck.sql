-- =============================================================================
-- BioComm Schema v4 -- Rueckbau (downgrade der Migration 5c8d0f3a2e46).
-- Die Migration prueft vorher, dass es keine Zugangsschluessel gibt.
-- =============================================================================
DROP TABLE sandbox.device_credential, live.device_credential;
DROP PROCEDURE biocomm_common.core_0004(text);
