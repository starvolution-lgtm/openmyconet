-- =============================================================================
-- BioComm Schema v5 -- Rueckbau (downgrade der Migration 6d9e1a4b3f57).
-- Die Migration prueft vorher, dass es keine Signaturschluessel gibt (dann
-- gibt es auch keine signierten Pakete).
-- =============================================================================
ALTER TABLE sandbox.origin_batch
    DROP CONSTRAINT origin_batch_signatur_vollstaendig,
    DROP COLUMN signing_key_id, DROP COLUMN signature, DROP COLUMN signature_algorithm;
ALTER TABLE live.origin_batch
    DROP CONSTRAINT origin_batch_signatur_vollstaendig,
    DROP COLUMN signing_key_id, DROP COLUMN signature, DROP COLUMN signature_algorithm;
DROP TABLE sandbox.device_signing_key, live.device_signing_key;
DROP PROCEDURE biocomm_common.core_0005(text);
