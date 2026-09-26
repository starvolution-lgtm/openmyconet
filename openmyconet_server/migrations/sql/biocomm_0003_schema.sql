-- =============================================================================
-- BioComm Schema v3 (Alembic-Migration 4b7c9e2d1f35) -- Ereignisse im Dateneingang
-- Festgelegt 26.09.2026 (Robby, Claude): Der Node meldet sich mit dem Ereignis
-- LAUF_START selbst an (Paketformat v1, docs/dateneingang_format_v1.md); der
-- Server legt daraus den Messlauf an.
--
-- NICHT von Hand ausfuehren. 0001/0002 bleiben unveraendert; die Kern-Aenderung
-- steht genau einmal in biocomm_common.core_0003(p_target) und gilt fuer
-- sandbox UND live.
-- =============================================================================

CREATE OR REPLACE PROCEDURE biocomm_common.core_0003(p_target text)
LANGUAGE plpgsql AS $core$
DECLARE
    v_suchpfad text := current_setting('search_path');
BEGIN
    IF p_target NOT IN ('sandbox', 'live') THEN
        RAISE EXCEPTION 'core_0003: nur sandbox oder live erlaubt, nicht %', p_target;
    END IF;
    PERFORM set_config('search_path', p_target, true);

    -- 3a. Einsatz: welcher Messknoten misst ab wann fuer welche Messreihe.
    --     Die Messreihe ist eine wissenschaftliche Festlegung, deshalb entscheidet
    --     sie nicht der Node, sondern der Einsatz auf dem Server. Ein LAUF_START
    --     landet in der Messreihe, deren Einsatz seinen Startzeitpunkt enthaelt.
    --     Historisiert wie site_timezone: nur valid_to darf spaeter gesetzt
    --     werden (Einsatz beenden), sonst unveraenderlich.
    CREATE TABLE device_deployment (
        id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        device_id   bigint NOT NULL,
        device_role text   NOT NULL DEFAULT 'NODE' CHECK (device_role = 'NODE'),
        series_id   bigint NOT NULL REFERENCES series(id),
        valid_from  timestamptz NOT NULL,
        valid_to    timestamptz,
        note        text,
        created_at  timestamptz NOT NULL DEFAULT now(),
        CHECK (valid_to IS NULL OR valid_to > valid_from),
        FOREIGN KEY (device_id, device_role) REFERENCES device(id, device_role),
        EXCLUDE USING gist (device_id WITH =, tstzrange(valid_from, valid_to) WITH &&)
    );
    CREATE TRIGGER device_deployment_fixed_columns
        BEFORE UPDATE OR DELETE ON device_deployment
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification('valid_to');

    -- 3b. Zurueckgestellte Anlieferungen: Pakete eines bekannten Geraets, deren
    --     Messlauf (noch) nicht existiert -- der LAUF_START fehlt noch (z. B.
    --     LoRa-Reihenfolge) oder dem Geraet ist fuer den Startzeitpunkt kein
    --     Einsatz zugeordnet. Die Anlieferung steht als RECEIVED in
    --     batch_delivery, das Paket hier. Sobald der Lauf existiert, verarbeitet
    --     der Eingang sie und setzt den Status der Anlieferung (erledigt =
    --     Anlieferung nicht mehr RECEIVED). Nur einfuegen, unveraenderlich.
    CREATE TABLE delivery_waiting (
        batch_delivery_id bigint PRIMARY KEY REFERENCES batch_delivery(id),
        device_serial     text   NOT NULL,
        node_run_key      text   NOT NULL,
        payload           bytea  NOT NULL,
        reason            text   NOT NULL,
        created_at        timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX delivery_waiting_lauf ON delivery_waiting (device_serial, node_run_key);
    CREATE TRIGGER delivery_waiting_immutable
        BEFORE UPDATE OR DELETE ON delivery_waiting
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();

    PERFORM set_config('search_path', v_suchpfad, true);
END
$core$;

CALL biocomm_common.core_0003('sandbox');
CALL biocomm_common.core_0003('live');
