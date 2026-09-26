-- =============================================================================
-- BioComm Schema v4 (Alembic-Migration 5c8d0f3a2e46) -- Empfangsweg fuer Bridges
-- Festgelegt 26.09.2026 (Robby, Claude): Bridges liefern Pakete per HTTPS an
-- POST /api/v2/biocomm/paket (omn/eingang/empfang.py) und melden sich mit einem
-- Zugangsschluessel je Geraet an.
--
-- NICHT von Hand ausfuehren. 0001-0003 bleiben unveraendert; die Kern-Aenderung
-- steht genau einmal in biocomm_common.core_0004(p_target) und gilt fuer
-- sandbox UND live.
-- =============================================================================

CREATE OR REPLACE PROCEDURE biocomm_common.core_0004(p_target text)
LANGUAGE plpgsql AS $core$
DECLARE
    v_suchpfad text := current_setting('search_path');
BEGIN
    IF p_target NOT IN ('sandbox', 'live') THEN
        RAISE EXCEPTION 'core_0004: nur sandbox oder live erlaubt, nicht %', p_target;
    END IF;
    PERFORM set_config('search_path', p_target, true);

    -- Zugangsschluessel eines Geraets (vorerst nur Bridges). Gespeichert wird
    -- NUR der SHA-256-Fingerabdruck des Schluessels (32 Byte); der Schluessel
    -- selbst wird beim Anlegen einmal angezeigt (flask biocomm-schluessel) und
    -- steht nirgends auf dem Server. Zufallsschluessel mit 256 Bit brauchen
    -- keinen langsamen Passwort-Hash. Widerrufen = revoked_at setzen; nie
    -- loeschen (Nachvollziehbarkeit, welche Anlieferung mit welchem Schluessel kam).
    CREATE TABLE device_credential (
        id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        device_id    bigint NOT NULL REFERENCES device(id),
        token_hash   bytea  NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),
        label        text,
        created_at   timestamptz NOT NULL DEFAULT now(),
        revoked_at   timestamptz,
        last_used_at timestamptz,
        CHECK (revoked_at IS NULL OR revoked_at >= created_at)
    );
    CREATE INDEX device_credential_device ON device_credential (device_id);
    CREATE TRIGGER device_credential_fixed_columns
        BEFORE UPDATE OR DELETE ON device_credential
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification('revoked_at', 'last_used_at');

    PERFORM set_config('search_path', v_suchpfad, true);
END
$core$;

CALL biocomm_common.core_0004('sandbox');
CALL biocomm_common.core_0004('live');
