-- =============================================================================
-- BioComm Schema v2 (Alembic-Migration 8d4e2a6c1b70) -- Dateneingang, Teil 2
-- Entscheidungen Robby, 24.09.2026 (Bericht "Prototyp Dateneingang"):
--   1. Verdichtung: versionierte Aggregate (nur einfuegen, jüngste Version gilt).
--   2. Konflikte (8.1.2): automatische Aufloesung NUR mit Kettenbeweis, sonst
--      manuell ueber eine SECURITY-DEFINER-Funktion (Eigentuemer omn_owner) mit
--      unveraenderlichem Protokoll. omn bekommt weiterhin KEINE Loeschrechte.
--   3. Pflichtpunkte vor Live: Index auf batch_delivery.transport_hash.
--
-- NICHT von Hand ausfuehren. biocomm_0001_schema.sql bleibt unveraendert; die
-- Aenderung am Kern steht genau einmal in biocomm_common.core_0002(p_target)
-- und wird fuer sandbox UND live aufgerufen (Schema-Paritaet wie create_core).
-- Englische Tabellen-/Spaltennamen wie in v7, deutsche Kommentare.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. Loeschschutz fuer sample_block mit genau einer Ausnahme
-- -----------------------------------------------------------------------------
-- Bisher verbot forbid_modification() UPDATE und DELETE. UPDATE bleibt so.
-- DELETE ist nur erlaubt, wenn (a) die Transaktion die Markierung
-- biocomm.kandidat_festlegen = 'an' gesetzt hat UND (b) der ausfuehrende
-- Nutzer der Eigentuemer der Tabelle ist. Beides zusammen gibt es nur in
-- biocomm_common.kandidat_festlegen() (SECURITY DEFINER, Eigentuemer
-- omn_owner). omn kann die Markierung zwar setzen, ist aber nie Eigentuemer
-- und hat ohnehin kein DELETE-Recht. Kein ALTER TABLE ... DISABLE TRIGGER:
-- das braeuchte eine exklusive Sperre auf sample_block.
CREATE OR REPLACE FUNCTION biocomm_common.sample_block_loeschschutz()
RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    IF current_setting('biocomm.kandidat_festlegen', true) = 'an'
       AND current_user::text = (SELECT tableowner::text FROM pg_catalog.pg_tables
                                  WHERE schemaname = TG_TABLE_SCHEMA AND tablename = TG_TABLE_NAME) THEN
        RETURN OLD;
    END IF;
    RAISE EXCEPTION '%.%: Zeilen sind unveränderlich, DELETE verboten',
        TG_TABLE_SCHEMA, TG_TABLE_NAME;
END
$fn$;


-- -----------------------------------------------------------------------------
-- 2. Kern-Aenderung: eine Quelle fuer sandbox und live
-- -----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE biocomm_common.core_0002(p_target text)
LANGUAGE plpgsql AS $core$
DECLARE
    v_suchpfad text := current_setting('search_path');
BEGIN
    IF p_target NOT IN ('sandbox', 'live') THEN
        RAISE EXCEPTION 'core_0002: nur sandbox oder live erlaubt, nicht %', p_target;
    END IF;
    PERFORM set_config('search_path', p_target, true);

    -- 2a. Versionierte Aggregate. Neue Versionen werden eingefuegt, alte
    --     bleiben. Leser nehmen je Zeitfenster die hoechste Version (Sicht
    --     derived_aggregate_current). Eine Version mit samples_recorded = 0
    --     ("Grabstein") sagt: dieses Fenster hat keine gueltigen Daten mehr
    --     (z. B. nachdem ein Kandidat in Konflikt geraten ist); fehlend bleibt
    --     damit fehlend, nie Null. Bestehende Zeilen werden Version 1.
    ALTER TABLE derived_aggregate
        ADD COLUMN aggregate_version integer NOT NULL DEFAULT 1 CHECK (aggregate_version >= 1),
        ADD COLUMN computed_at timestamptz NOT NULL DEFAULT now();
    ALTER TABLE derived_aggregate DROP CONSTRAINT derived_aggregate_pkey;
    ALTER TABLE derived_aggregate
        ADD PRIMARY KEY (measurement_channel_id, resolution, bucket_start, aggregate_version);
    ALTER TABLE derived_aggregate DROP CONSTRAINT derived_aggregate_samples_recorded_check;
    ALTER TABLE derived_aggregate
        ALTER COLUMN value_min DROP NOT NULL,
        ALTER COLUMN value_max DROP NOT NULL,
        ALTER COLUMN value_mean DROP NOT NULL,
        ADD CONSTRAINT derived_aggregate_samples_recorded_check CHECK (samples_recorded >= 0),
        ADD CONSTRAINT derived_aggregate_werte_check CHECK (
            (samples_recorded > 0 AND value_min IS NOT NULL AND value_max IS NOT NULL AND value_mean IS NOT NULL)
         OR (samples_recorded = 0 AND value_min IS NULL AND value_max IS NULL AND value_mean IS NULL)),
        ADD CONSTRAINT derived_aggregate_grabstein_check CHECK (samples_recorded > 0 OR aggregate_version > 1);
    CREATE TRIGGER derived_aggregate_immutable
        BEFORE UPDATE OR DELETE ON derived_aggregate
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();

    -- Jüngste Version je Fenster, ohne Grabsteine. NOT EXISTS statt DISTINCT
    -- ON: Filter der Leser (Kanal, Zeitraum) wirken so direkt auf den Index.
    CREATE VIEW derived_aggregate_current WITH (security_invoker = true) AS
        SELECT a.*
          FROM derived_aggregate a
         WHERE a.samples_recorded > 0
           AND NOT EXISTS (SELECT 1 FROM derived_aggregate n
                            WHERE n.measurement_channel_id = a.measurement_channel_id
                              AND n.resolution = a.resolution
                              AND n.bucket_start = a.bucket_start
                              AND n.aggregate_version > a.aggregate_version);

    -- 2b. Protokoll der Kandidatenwahl (nur einfuegen, unveraenderlich).
    --     Eine Zeile je Schritt: gewaehlter Kandidat (CHOSEN) und jeder
    --     zurueckgestellte Kandidat (SET_ASIDE), mit entfernten bzw.
    --     geschriebenen Bloecken in detail.
    CREATE TABLE candidate_resolution_log (
        id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        acquisition_run_id bigint NOT NULL REFERENCES acquisition_run(id),
        batch_sequence_no  bigint NOT NULL,
        origin_batch_id    bigint NOT NULL REFERENCES origin_batch(id),
        action             text   NOT NULL CHECK (action IN ('CHOSEN', 'SET_ASIDE')),
        basis              text   NOT NULL CHECK (basis IN ('SUCCESSOR_LINK', 'MANUAL_REVIEW')),
        performed_by       text   NOT NULL,                     -- Person bzw. "Eingang (automatisch)"
        db_user            text   NOT NULL DEFAULT session_user, -- angemeldete Datenbankrolle
        reason             text,
        detail             jsonb  NOT NULL DEFAULT '{}',
        performed_at       timestamptz NOT NULL DEFAULT clock_timestamp(),
        FOREIGN KEY (origin_batch_id, acquisition_run_id) REFERENCES origin_batch(id, acquisition_run_id)
    );
    CREATE INDEX candidate_resolution_log_batch ON candidate_resolution_log (origin_batch_id);
    CREATE TRIGGER candidate_resolution_log_immutable
        BEFORE UPDATE OR DELETE ON candidate_resolution_log
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();

    -- 2b'. Quarantaene fuer Rohdatenbloecke zurueckgestellter Kandidaten
    --     (Pruefung lokale Sitzung, 25.09.2026): Ein regulaer angenommener
    --     Batch hat payload_location = 'SAMPLE_BLOCKS', seine Payload existiert
    --     NUR in sample_block. Bevor kandidat_festlegen() diese Bloecke aus
    --     sample_block entfernt, kopiert es sie hierher. So bleiben
    --     Konfliktkandidaten vollstaendig erhalten (Quarantaene statt Loeschen)
    --     und jede Kandidatenwahl bleibt umkehrbar; auch ein Missbrauch der
    --     Web-Rolle kann keine Rohdaten mehr endgueltig vernichten.
    --     Nur einfuegen (nur ueber kandidat_festlegen, omn hat kein INSERT),
    --     unveraenderlich, kein EXCLUDE (Sample-Indizes duerfen sich hier
    --     ueberschneiden). sample_block_id = urspruengliche Zeile; die
    --     Reihenfolge der ids ist die Reihenfolge im payload_hash.
    CREATE TABLE sample_block_quarantine (
        id                     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        sample_block_id        bigint  NOT NULL UNIQUE,
        acquisition_run_id     bigint  NOT NULL,
        measurement_channel_id bigint  NOT NULL REFERENCES measurement_channel(id),
        origin_batch_id        bigint  NOT NULL,
        first_sample_index     bigint  NOT NULL,
        sample_count           integer NOT NULL,
        time_anchor            timestamptz NOT NULL,
        sample_rate_hz         numeric NOT NULL,
        value_encoding         text    NOT NULL,
        compression            text    NOT NULL,
        payload_location       text    NOT NULL,
        payload_inline         bytea,
        payload_ref            text,
        payload_hash           bytea   NOT NULL,
        device_quality         bytea,
        set_aside_at           timestamptz NOT NULL DEFAULT clock_timestamp(),
        FOREIGN KEY (origin_batch_id, acquisition_run_id) REFERENCES origin_batch(id, acquisition_run_id)
    );
    CREATE INDEX sample_block_quarantine_batch ON sample_block_quarantine (origin_batch_id, sample_block_id);
    CREATE TRIGGER sample_block_quarantine_immutable
        BEFORE UPDATE OR DELETE ON sample_block_quarantine
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();

    -- 2c. Loeschschutz sample_block (Abschnitt 1): UPDATE wie bisher verboten,
    --     DELETE nur ueber kandidat_festlegen().
    DROP TRIGGER sample_block_immutable ON sample_block;
    CREATE TRIGGER sample_block_immutable
        BEFORE UPDATE ON sample_block
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();
    CREATE TRIGGER sample_block_loeschschutz
        BEFORE DELETE ON sample_block
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.sample_block_loeschschutz();

    -- 2d. Pflichtpunkt vor Live: "schon eingelesen?" ohne Tabellenscan.
    CREATE INDEX batch_delivery_transport ON batch_delivery (transport_code, transport_hash);

    PERFORM set_config('search_path', v_suchpfad, true);
END
$core$;


-- -----------------------------------------------------------------------------
-- 3. Kandidat festlegen (Konfliktaufloesung), SECURITY DEFINER
-- -----------------------------------------------------------------------------
-- Waehlt auf einem strittigen Sequenzplatz einen CONFLICT-Kandidaten als
-- CANONICAL. Grundlage:
--   SUCCESSOR_LINK  nur, wenn die kanonischen Nachfolger (Sequenz + 1) per
--                   previous_batch_hash auf GENAU diesen Kandidaten verweisen
--                   (die Funktion prueft das selbst);
--   MANUAL_REVIEW   mit Name und Begruendung (Pflicht).
-- Verschiebt die sample_block-Zeilen der uebrigen Kandidaten in die
-- Quarantaene (sample_block_quarantine: erst kopieren, dann entfernen), schreibt die des
-- Gewinners (falls er noch keine hat; p_bloecke = Bloecke als jsonb, deren
-- Payloads zusammen den payload_hash des Gewinners ergeben muessen) und
-- protokolliert jeden Schritt. Das Paketformat (C4) kennt nur Python
-- (omn/eingang/format_v0.py); die Funktion prueft Payloads ueber den Hash.
-- Laeuft mit den Rechten des Eigentuemers (omn_owner); omn darf sie nur
-- ausfuehren (biocomm_0002_rechte.sql).
CREATE OR REPLACE FUNCTION biocomm_common.kandidat_festlegen(
    p_schema text, p_batch_id bigint, p_grundlage text, p_bloecke jsonb,
    p_bearbeitet_von text, p_begruendung text)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $fn$
DECLARE
    g           record;
    k           record;
    v_n         bigint;
    v_bloecke   bigint;
    v_hash      bytea;
    v_verweise  bigint[];
    v_wer       text;
    v_protokoll integer := 0;
    v_q         bigint;
BEGIN
    IF p_schema NOT IN ('sandbox', 'live') THEN
        RAISE EXCEPTION 'kandidat_festlegen: Schema % nicht erlaubt', p_schema;
    END IF;
    IF p_grundlage NOT IN ('SUCCESSOR_LINK', 'MANUAL_REVIEW') THEN
        RAISE EXCEPTION 'kandidat_festlegen: Grundlage % unbekannt', p_grundlage;
    END IF;
    EXECUTE format('SELECT acquisition_run_id FROM %I.origin_batch WHERE id = $1', p_schema)
        INTO v_n USING p_batch_id;
    IF v_n IS NULL THEN
        RAISE EXCEPTION 'kandidat_festlegen: Batch % unbekannt', p_batch_id;
    END IF;
    -- dieselbe Sperre wie der Eingang (omn/eingang/einlesen.py, sperren())
    PERFORM pg_advisory_xact_lock(hashtextextended(format('omn-eingang:%s:lauf:%s', p_schema, v_n), 0));
    EXECUTE format('SELECT id, acquisition_run_id AS lauf, batch_sequence_no AS seq, batch_status,'
                   ' payload_hash, batch_hash FROM %I.origin_batch WHERE id = $1', p_schema)
        INTO g USING p_batch_id;
    IF g.batch_status <> 'CONFLICT' THEN
        RAISE EXCEPTION 'kandidat_festlegen: Batch % ist %, nicht CONFLICT', p_batch_id, g.batch_status;
    END IF;
    EXECUTE format('SELECT count(*) FROM %I.origin_batch WHERE acquisition_run_id = $1'
                   ' AND batch_sequence_no = $2 AND id <> $3', p_schema)
        INTO v_n USING g.lauf, g.seq, g.id;
    IF v_n = 0 THEN
        RAISE EXCEPTION 'kandidat_festlegen: Batch % hat keinen Konkurrenten auf Sequenz % '
                        '(Ueberschneidungskonflikt, hier nicht aufloesbar)', p_batch_id, g.seq;
    END IF;

    IF p_grundlage = 'SUCCESSOR_LINK' THEN
        EXECUTE format($q$
            SELECT array_agg(DISTINCT v.id ORDER BY v.id)
              FROM %1$I.origin_batch v
              JOIN %1$I.origin_batch n
                ON n.acquisition_run_id = v.acquisition_run_id
               AND n.batch_sequence_no = v.batch_sequence_no + 1
               AND n.batch_status = 'CANONICAL'
               AND n.previous_batch_hash = v.batch_hash
             WHERE v.acquisition_run_id = $1 AND v.batch_sequence_no = $2$q$, p_schema)
            INTO v_verweise USING g.lauf, g.seq;
        IF v_verweise IS DISTINCT FROM ARRAY[g.id] THEN
            RAISE EXCEPTION 'kandidat_festlegen: kein eindeutiger Kettenbeweis fuer Batch % (Verweise: %)',
                p_batch_id, coalesce(v_verweise::text, 'keine');
        END IF;
        v_wer := 'Eingang (automatisch)';
    ELSE
        IF coalesce(btrim(p_bearbeitet_von), '') = '' OR coalesce(btrim(p_begruendung), '') = '' THEN
            RAISE EXCEPTION 'kandidat_festlegen: manuelle Aufloesung braucht Name und Begruendung';
        END IF;
        v_wer := btrim(p_bearbeitet_von);
    END IF;

    EXECUTE format('SELECT count(*) FROM %I.sample_block WHERE origin_batch_id = $1', p_schema)
        INTO v_bloecke USING g.id;
    IF v_bloecke = 0 THEN
        IF p_bloecke IS NULL OR jsonb_typeof(p_bloecke) <> 'array' OR jsonb_array_length(p_bloecke) = 0 THEN
            RAISE EXCEPTION 'kandidat_festlegen: Bloecke des Gewinners fehlen';
        END IF;
        SELECT sha256(string_agg(decode(e->>'payload', 'base64'), ''::bytea ORDER BY o))
          INTO v_hash
          FROM jsonb_array_elements(p_bloecke) WITH ORDINALITY AS t(e, o);
        IF v_hash IS DISTINCT FROM g.payload_hash THEN
            RAISE EXCEPTION 'kandidat_festlegen: Bloecke passen nicht zum payload_hash von Batch %', p_batch_id;
        END IF;
    END IF;

    -- Uebrige Kandidaten zurueckstellen: Bloecke zuerst in die Quarantaene
    -- kopieren, dann aus sample_block entfernen (nie ohne Kopie), Status
    -- CONFLICT, status_changed_at neu (die Verdichtung erkennt daran
    -- betroffene Fenster).
    PERFORM set_config('biocomm.kandidat_festlegen', 'an', true);
    FOR k IN EXECUTE format('SELECT id FROM %I.origin_batch WHERE acquisition_run_id = $1'
                            ' AND batch_sequence_no = $2 AND id <> $3 ORDER BY id', p_schema)
             USING g.lauf, g.seq, g.id LOOP
        EXECUTE format($q$
            WITH q AS (
                INSERT INTO %1$I.sample_block_quarantine (sample_block_id, acquisition_run_id,
                    measurement_channel_id, origin_batch_id, first_sample_index, sample_count, time_anchor,
                    sample_rate_hz, value_encoding, compression, payload_location, payload_inline, payload_ref,
                    payload_hash, device_quality)
                SELECT id, acquisition_run_id, measurement_channel_id, origin_batch_id, first_sample_index,
                       sample_count, time_anchor, sample_rate_hz, value_encoding, compression, payload_location,
                       payload_inline, payload_ref, payload_hash, device_quality
                  FROM %1$I.sample_block WHERE origin_batch_id = $1 ORDER BY id
                RETURNING 1)
            SELECT count(*) FROM q$q$, p_schema) INTO v_q USING k.id;
        EXECUTE format('WITH d AS (DELETE FROM %I.sample_block WHERE origin_batch_id = $1 RETURNING 1)'
                       ' SELECT count(*) FROM d', p_schema) INTO v_n USING k.id;
        IF v_n <> v_q THEN
            RAISE EXCEPTION 'kandidat_festlegen: % Bloecke entfernt, aber % in die Quarantaene kopiert (Batch %)',
                v_n, v_q, k.id;
        END IF;
        EXECUTE format('UPDATE %I.origin_batch SET batch_status = ''CONFLICT'', status_basis = NULL,'
                       ' status_changed_at = clock_timestamp() WHERE id = $1', p_schema) USING k.id;
        EXECUTE format('INSERT INTO %I.candidate_resolution_log (acquisition_run_id, batch_sequence_no,'
                       ' origin_batch_id, action, basis, performed_by, reason, detail)'
                       ' VALUES ($1, $2, $3, ''SET_ASIDE'', $4, $5, $6, $7)', p_schema)
            USING g.lauf, g.seq, k.id, p_grundlage, v_wer, p_begruendung,
                  jsonb_build_object('bloecke_entfernt', v_n, 'bloecke_in_quarantaene', v_q, 'gewinner', g.id);
        v_protokoll := v_protokoll + 1;
    END LOOP;
    PERFORM set_config('biocomm.kandidat_festlegen', '', true);

    EXECUTE format('UPDATE %I.origin_batch SET batch_status = ''CANONICAL'', status_basis = $2,'
                   ' status_changed_at = clock_timestamp() WHERE id = $1', p_schema)
        USING g.id, p_grundlage;
    v_n := 0;
    IF v_bloecke = 0 THEN
        EXECUTE format($q$
            INSERT INTO %I.sample_block (acquisition_run_id, measurement_channel_id, origin_batch_id,
                first_sample_index, sample_count, time_anchor, sample_rate_hz, value_encoding, compression,
                payload_location, payload_inline, payload_hash, device_quality)
            SELECT $1, (e->>'kanal')::bigint, $2, (e->>'erster_index')::bigint, (e->>'anzahl')::integer,
                   (e->>'zeitanker')::timestamptz, (e->>'rate_hz')::numeric, e->>'kodierung', e->>'kompression',
                   'INLINE', decode(e->>'payload', 'base64'), sha256(decode(e->>'payload', 'base64')),
                   decode(e->>'geraete_qualitaet', 'base64')
              FROM jsonb_array_elements($3) AS t(e)$q$, p_schema)
            USING g.lauf, g.id, p_bloecke;
        GET DIAGNOSTICS v_n = ROW_COUNT;
    END IF;
    EXECUTE format('INSERT INTO %I.candidate_resolution_log (acquisition_run_id, batch_sequence_no,'
                   ' origin_batch_id, action, basis, performed_by, reason, detail)'
                   ' VALUES ($1, $2, $3, ''CHOSEN'', $4, $5, $6, $7)', p_schema)
        USING g.lauf, g.seq, g.id, p_grundlage, v_wer, p_begruendung,
              jsonb_build_object('bloecke_geschrieben', v_n, 'bloecke_vorhanden', v_bloecke);
    RETURN v_protokoll + 1;
END
$fn$;


-- -----------------------------------------------------------------------------
-- 4. Anwendung: dieselbe Quelle fuer beide Namespaces
-- -----------------------------------------------------------------------------
CALL biocomm_common.core_0002('sandbox');
CALL biocomm_common.core_0002('live');
