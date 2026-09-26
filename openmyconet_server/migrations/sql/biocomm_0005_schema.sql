-- =============================================================================
-- BioComm Schema v5 (Alembic-Migration 6d9e1a4b3f57) -- Signaturen der Messknoten
-- Festgelegt 26.09.2026 (Claude, Robby informiert): Jeder Messknoten signiert
-- seine Pakete mit Ed25519 (Anhang des Paketformats v1, Art 2). Der Server
-- kennt nur den oeffentlichen Schluessel; wer die Datenbank oder ein Backup
-- liest, kann damit keine Pakete faelschen. Der private Schluessel entsteht im
-- Knoten aus dem eFuse-HMAC-Schluessel des ESP32-S3 und verlaesst ihn nie
-- (docs/dateneingang_format_v1.md, Abschnitt Signatur).
--
-- NICHT von Hand ausfuehren. 0001-0004 bleiben unveraendert; die Kern-Aenderung
-- steht genau einmal in biocomm_common.core_0005(p_target) und gilt fuer
-- sandbox UND live.
-- =============================================================================

CREATE OR REPLACE PROCEDURE biocomm_common.core_0005(p_target text)
LANGUAGE plpgsql AS $core$
DECLARE
    v_suchpfad text := current_setting('search_path');
BEGIN
    IF p_target NOT IN ('sandbox', 'live') THEN
        RAISE EXCEPTION 'core_0005: nur sandbox oder live erlaubt, nicht %', p_target;
    END IF;
    PERFORM set_config('search_path', p_target, true);

    -- Oeffentliche Signaturschluessel der Messknoten. Ein Knoten kann mehrere
    -- haben (Austausch der Platine, neuer eFuse-Schluessel); gueltig ist jeder
    -- nicht widerrufene. Widerrufen = revoked_at setzen, nie loeschen: jede
    -- Signatur bleibt mit ihrem Schluessel nachpruefbar.
    CREATE TABLE device_signing_key (
        id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        device_id   bigint NOT NULL REFERENCES device(id),
        algorithm   text   NOT NULL CHECK (algorithm IN ('ED25519')),
        public_key  bytea  NOT NULL UNIQUE CHECK (octet_length(public_key) = 32),
        label       text,
        created_at  timestamptz NOT NULL DEFAULT now(),
        revoked_at  timestamptz,
        CHECK (revoked_at IS NULL OR revoked_at >= created_at)
    );
    CREATE INDEX device_signing_key_device ON device_signing_key (device_id);
    CREATE TRIGGER device_signing_key_fixed_columns
        BEFORE UPDATE OR DELETE ON device_signing_key
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification('revoked_at');

    -- Signatur eines Pakets, beim Anlegen geschrieben und danach unveraenderlich
    -- (der Trigger origin_batch_immutable erlaubt nur die Statusspalten).
    -- Ohne Signatur (sandbox, Sandbox-Generator, Format v0) alle drei NULL.
    ALTER TABLE origin_batch
        ADD COLUMN signature_algorithm text CHECK (signature_algorithm IN ('ED25519')),
        ADD COLUMN signature bytea,
        ADD COLUMN signing_key_id bigint REFERENCES device_signing_key(id),
        ADD CONSTRAINT origin_batch_signatur_vollstaendig CHECK (
            (signature_algorithm IS NULL AND signature IS NULL AND signing_key_id IS NULL)
            OR (signature_algorithm = 'ED25519' AND octet_length(signature) = 64 AND signing_key_id IS NOT NULL));

    PERFORM set_config('search_path', v_suchpfad, true);
END
$core$;

CALL biocomm_common.core_0005('sandbox');
CALL biocomm_common.core_0005('live');
