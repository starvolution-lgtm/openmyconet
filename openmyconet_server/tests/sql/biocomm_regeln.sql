-- =============================================================================
-- Regeltests für biocomm_schema_draft.sql (NUR lokale Wegwerf-Datenbank!)
-- Aufruf: psql -d <frische_db> -v ON_ERROR_STOP=1 -f biocomm_schema_draft.sql
--         psql -d <frische_db> -v ON_ERROR_STOP=1 -f test_regeln.sql
-- Jede Prüfung meldet "OK: …". Weicht ein Ergebnis ab, bricht das Skript mit
-- "TEST FEHLGESCHLAGEN" ab. Alles läuft in einer Transaktion und wird am Ende
-- zurückgerollt; die Datenbank bleibt leer.
-- =============================================================================
BEGIN;
SET search_path = live;
SET client_min_messages = notice;

-- Hilfsfunktionen (temporär) ------------------------------------------------
CREATE FUNCTION pg_temp.muss_scheitern(p_name text, p_sql text, p_fragment text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    BEGIN
        EXECUTE p_sql;
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM ILIKE '%' || p_fragment || '%' THEN
            RAISE NOTICE 'OK: % (abgewiesen: %)', p_name, SQLERRM;
            RETURN;
        END IF;
        RAISE EXCEPTION 'TEST FEHLGESCHLAGEN: % — falscher Fehler: %', p_name, SQLERRM;
    END;
    RAISE EXCEPTION 'TEST FEHLGESCHLAGEN: % — wurde NICHT abgewiesen', p_name;
END $$;

CREATE FUNCTION pg_temp.muss_klappen(p_name text, p_sql text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    EXECUTE p_sql;
    RAISE NOTICE 'OK: %', p_name;
EXCEPTION WHEN OTHERS THEN
    RAISE EXCEPTION 'TEST FEHLGESCHLAGEN: % — %', p_name, SQLERRM;
END $$;

-- Grunddaten ------------------------------------------------------------------
INSERT INTO site (site_code, grid_system, grid_cell_id) VALUES ('DE-TEST-01', 'MGRS_10KM', '32UMA59');
INSERT INTO site_timezone (site_id, iana_tz, valid_from) SELECT id, 'Europe/Berlin', '2026-01-01' FROM site;
INSERT INTO device (device_serial, device_role) VALUES ('OMN-NODE-00001', 'NODE'), ('OMN-BRIDGE-00001', 'BRIDGE');
INSERT INTO device_configuration (device_id, hardware_revision, firmware_version, config_version)
    SELECT id, 'COMBO_NODE 3.2', 'fw-0.1', 'cfg-1' FROM device WHERE device_role = 'NODE';
INSERT INTO probe (probe_serial, probe_kind) VALUES ('PRB-0001', 'EXTERNAL_BIOCOMM');
INSERT INTO hardware_channel (device_id, probe_id, input_label)
    SELECT d.id, p.id, 'U8/AIN0 über INA333' FROM device d, probe p WHERE d.device_role = 'NODE';
INSERT INTO hardware_channel (device_id, input_label)
    SELECT id, 'U14/AIN0 Bodenfeuchte' FROM device WHERE device_role = 'NODE';
INSERT INTO actuator_channel (device_configuration_id, actuator_type, output_label)
    SELECT id, 'ELECTRICAL', 'DAC_OUT' FROM device_configuration;
INSERT INTO series (series_code, site_id, substrate_code, title) SELECT 'S-1', id, 'SOIL', 'Test' FROM site;
INSERT INTO acquisition_run (series_id, device_id, device_configuration_id, node_run_key, started_at)
    SELECT s.id, c.device_id, c.id, 'boot-1', '2026-09-01 00:00Z' FROM series s, device_configuration c;
INSERT INTO probe_assignment (acquisition_run_id, probe_id, is_external_biocomm)
    SELECT r.id, p.id, true FROM acquisition_run r, probe p;
INSERT INTO measurement_channel (acquisition_run_id, device_id, hardware_channel_id, channel_role,
        quantity_code, unit_code, data_kind, sample_rate_hz, sample_clock_source, gain, gain_source)
    SELECT r.id, r.device_id, h.id, 'PRIMARY', 'bioelectric_potential', 'uV', 'RAW', 860, 'RTC_SQW', 100, 'MANUAL'
      FROM acquisition_run r, hardware_channel h WHERE h.probe_id IS NOT NULL;
INSERT INTO recording_plan (acquisition_run_id, plan_version, valid_from)
    SELECT id, 1, '2026-09-01 00:00Z' FROM acquisition_run;
INSERT INTO recording_plan_channel (recording_plan_id, acquisition_run_id, measurement_channel_id, requirement, planned_sample_rate_hz)
    SELECT p.id, p.acquisition_run_id, m.id, 'REQUIRED', 860 FROM recording_plan p, measurement_channel m;
INSERT INTO recording_plan_interval (recording_plan_id, acquisition_run_id, interval_kind, period)
    SELECT id, acquisition_run_id, 'RECORDING', '[2026-09-01 00:00Z, 2026-09-08 00:00Z)' FROM recording_plan;
INSERT INTO recording_plan_interval (recording_plan_id, acquisition_run_id, interval_kind, measurement_channel_id, pause_reason, period)
    SELECT p.id, p.acquisition_run_id, 'PAUSE', m.id, 'EC_MEASUREMENT', '[2026-09-01 01:00:00Z, 2026-09-01 01:00:30Z)'
      FROM recording_plan p, measurement_channel m;
INSERT INTO recording_plan_interval (recording_plan_id, acquisition_run_id, interval_kind, measurement_channel_id, pause_reason, period)
    SELECT p.id, p.acquisition_run_id, 'PAUSE', m.id, 'EC_SETTLING', '[2026-09-01 01:00:30Z, 2026-09-01 01:00:35Z)'
      FROM recording_plan p, measurement_channel m;

-- Kurzbezeichner für die Tests
CREATE TEMP TABLE k AS SELECT
    (SELECT id FROM acquisition_run)          AS run,
    (SELECT id FROM measurement_channel)      AS mc,
    (SELECT id FROM device_configuration)     AS cfg,
    (SELECT id FROM actuator_channel)         AS act,
    (SELECT id FROM device WHERE device_role = 'NODE')   AS node,
    (SELECT id FROM device WHERE device_role = 'BRIDGE') AS bridge,
    (SELECT id FROM series)                   AS ser;

DO $t$
DECLARE
    k record;
    ha text := 'decode(repeat(''aa'', 32), ''hex'')';
    hb text := 'decode(repeat(''bb'', 32), ''hex'')';
    hc text := 'decode(repeat(''cc'', 32), ''hex'')';
    ob text := 'INSERT INTO origin_batch (acquisition_run_id, batch_sequence_no, batch_content, measured_period, payload_hash, batch_hash, payload_format, payload_location, payload_inline, payload_size_bytes, batch_status) VALUES (%s, %s, ''RAW'', ''[2026-09-01 00:00Z, 2026-09-01 00:01Z)'', %s, %s, ''draft-1'', ''INLINE'', ''\x00'', 1, %L)';
    sb text := 'INSERT INTO sample_block (acquisition_run_id, measurement_channel_id, origin_batch_id, first_sample_index, sample_count, time_anchor, sample_rate_hz, value_encoding, payload_location, payload_inline, payload_hash) VALUES (%s, %s, %s, %s, 51600, %L, 860, ''int16le'', ''INLINE'', ''\x00'', %s)';
    st text := 'INSERT INTO stimulation (acquisition_run_id, device_configuration_id, actuator_channel_id, actuator_type, trigger_source, execution_state, actual_start, actual_duration_ms, attempted_at, control_decision_id) VALUES (%s, %s, %s, ''ELECTRICAL'', %L, %L, %s, %s, %s, NULL)';
    v_a bigint; v_b bigint; v_stim bigint; v_run2 bigint; v_seq bigint;
BEGIN
    SELECT * INTO k FROM k;

    RAISE NOTICE '--- 1. origin_batch: Identität Run + Sequenz + Hash, Konfliktkandidat bleibt erhalten';
    PERFORM pg_temp.muss_klappen('Batch Seq 1 / Hash A als CANONICAL', format(ob, k.run, 1, ha, ha, 'CANONICAL'));
    PERFORM pg_temp.muss_klappen('Konfliktkandidat Seq 1 / Hash B wird zusätzlich gespeichert', format(ob, k.run, 1, hb, hb, 'PENDING'));
    PERFORM pg_temp.muss_scheitern('Seq 1 / Hash A ein zweites Mal', format(ob, k.run, 1, ha, ha, 'PENDING'), 'origin_batch_acquisition_run_id_batch_sequence_no_payload_h');
    SELECT id INTO v_a FROM origin_batch WHERE payload_hash = decode(repeat('aa', 32), 'hex');
    SELECT id INTO v_b FROM origin_batch WHERE payload_hash = decode(repeat('bb', 32), 'hex');
    PERFORM pg_temp.muss_scheitern('zweiter CANONICAL-Kandidat für Seq 1',
        format('UPDATE origin_batch SET batch_status = ''CANONICAL'' WHERE id = %s', v_b), 'origin_batch_one_canonical');
    PERFORM pg_temp.muss_klappen('Kandidat B auf CONFLICT setzen (Statusspalte ist änderbar)',
        format('UPDATE origin_batch SET batch_status = ''CONFLICT'', status_basis = ''MANUAL_REVIEW'' WHERE id = %s', v_b));

    RAISE NOTICE '--- 2. Unveränderlichkeit';
    PERFORM pg_temp.muss_scheitern('payload_hash eines origin_batch ändern',
        format('UPDATE origin_batch SET payload_hash = %s WHERE id = %s', hc, v_a), 'unveränderliche Spalten');
    PERFORM pg_temp.muss_scheitern('origin_batch löschen', format('DELETE FROM origin_batch WHERE id = %s', v_b), 'DELETE verboten');
    PERFORM pg_temp.muss_scheitern('device_configuration ändern',
        format('UPDATE device_configuration SET firmware_version = ''fw-0.2'' WHERE id = %s', k.cfg), 'unveränderliche Spalten');
    PERFORM pg_temp.muss_scheitern('Verstärkung eines Messkanals nachträglich ändern (= neuer Run nötig)',
        format('UPDATE measurement_channel SET gain = 200 WHERE id = %s', k.mc), 'unveränderliche Spalten');
    PERFORM pg_temp.muss_scheitern('recording_plan ändern',
        'UPDATE recording_plan SET valid_from = valid_from - interval ''1 day''', 'unveränderliche Spalten');

    RAISE NOTICE '--- 3. sample_block';
    PERFORM pg_temp.muss_klappen('Block aus CANONICAL-Batch', format(sb, k.run, k.mc, v_a, 0, '2026-09-01 00:00Z', ha));
    PERFORM pg_temp.muss_scheitern('Block aus CONFLICT-Batch', format(sb, k.run, k.mc, v_b, 51600, '2026-09-01 00:01Z', hb), 'nicht CANONICAL');
    PERFORM pg_temp.muss_scheitern('gleicher sample_index ein zweites Mal (überlappender Block)',
        format(sb, k.run, k.mc, v_a, 1000, '2026-09-01 00:00:01Z', hb), 'conflicting key value violates exclusion constraint');
    PERFORM pg_temp.muss_scheitern('sample_block löschen', 'DELETE FROM sample_block', 'DELETE verboten');

    RAISE NOTICE '--- 4. Stimulation: Ist-Zeiten nur bei EXECUTED/PARTIAL, Zustände, EC-Ausschluss';
    PERFORM pg_temp.muss_scheitern('PLANNED mit Ist-Start', format(st, k.run, k.cfg, k.act, 'MANUAL', 'PLANNED', '''2026-09-01 02:00Z''', 1000, 'NULL'), 'stimulation_check');
    PERFORM pg_temp.muss_scheitern('EXECUTED ohne Ist-Zeiten', format(st, k.run, k.cfg, k.act, 'MANUAL', 'EXECUTED', 'NULL', 'NULL', 'NULL'), 'stimulation_check');
    PERFORM pg_temp.muss_scheitern('CANCELLED mit Ist-Dauer', format(st, k.run, k.cfg, k.act, 'MANUAL', 'CANCELLED', 'NULL', 500, 'NULL'), 'stimulation_check');
    PERFORM pg_temp.muss_klappen('FAILED mit Versuchszeitpunkt, ohne Ist-Zeiten', format(st, k.run, k.cfg, k.act, 'MANUAL', 'FAILED', 'NULL', 'NULL', '''2026-09-01 02:00Z'''));
    PERFORM pg_temp.muss_scheitern('Versuchszeitpunkt bei EXECUTED', format(st, k.run, k.cfg, k.act, 'MANUAL', 'EXECUTED', '''2026-09-01 02:00Z''', 1000, '''2026-09-01 02:00Z'''), 'stimulation_check');
    PERFORM pg_temp.muss_scheitern('CLOSED_LOOP ohne control_decision', format(st, k.run, k.cfg, k.act, 'CLOSED_LOOP', 'PLANNED', 'NULL', 'NULL', 'NULL'), 'stimulation_check');
    PERFORM pg_temp.muss_klappen('PLANNED anlegen', format(st, k.run, k.cfg, k.act, 'SCHEDULED', 'PLANNED', 'NULL', 'NULL', 'NULL'));
    SELECT max(id) INTO v_stim FROM stimulation;
    PERFORM pg_temp.muss_scheitern('PLANNED -> EXECUTED, überlappt EC-Messfenster (Annahme)',
        format('UPDATE stimulation SET execution_state = ''EXECUTED'', actual_start = ''2026-09-01 00:59:50Z'', actual_duration_ms = 20000 WHERE id = %s', v_stim), 'EC-Messfenster');
    PERFORM pg_temp.muss_klappen('PLANNED -> EXECUTED außerhalb des EC-Fensters',
        format('UPDATE stimulation SET execution_state = ''EXECUTED'', actual_start = ''2026-09-01 02:00Z'', actual_duration_ms = 1000 WHERE id = %s', v_stim));
    PERFORM pg_temp.muss_scheitern('EXECUTED -> CANCELLED (Endzustand)',
        format('UPDATE stimulation SET execution_state = ''CANCELLED'', actual_start = NULL, actual_duration_ms = NULL WHERE id = %s', v_stim), 'endgültig');
    PERFORM pg_temp.muss_scheitern('Parameterzeile OPTICAL an elektrischer Stimulation',
        format('INSERT INTO stimulation_param_optical (stimulation_id, actuator_type, wavelength_nm, pattern, intensity, intensity_unit, duration_ms) VALUES (%s, ''OPTICAL'', 470, ''PULSE'', 50, ''%%'', 1000)', v_stim), 'foreign key');

    RAISE NOTICE '--- 5. Sequenz nie über zwei Runs (B13)';
    INSERT INTO acquisition_run (series_id, device_id, device_configuration_id, node_run_key, started_at)
        VALUES (k.ser, k.node, k.cfg, 'boot-2', '2026-09-08 00:00Z') RETURNING id INTO v_run2;
    INSERT INTO stimulation_sequence (acquisition_run_id, label) VALUES (v_run2, 'Test') RETURNING id INTO v_seq;
    PERFORM pg_temp.muss_scheitern('Stimulation aus Run 1 in Sequenz von Run 2',
        format('INSERT INTO stimulation_sequence_member VALUES (%s, %s, %s, 0)', v_seq, v_stim, k.run), 'foreign key');

    RAISE NOTICE '--- 6. Qualität';
    PERFORM pg_temp.muss_scheitern('MISSING als gespeicherter Code', 'INSERT INTO ref_quality_code VALUES (''MISSING'', 10, ''x'')', 'ref_quality_code_code_check');
    PERFORM pg_temp.muss_scheitern('DUPLICATE als gespeicherter Code', 'INSERT INTO ref_quality_code VALUES (''DUPLICATE'', 11, ''x'')', 'ref_quality_code_code_check');
    PERFORM pg_temp.muss_scheitern('neuer Code ohne Einordnung in die Abdeckungszuordnung',
        format('WITH n AS (INSERT INTO ref_quality_code VALUES (''DRIFT'', 12, ''x'')) INSERT INTO quality_annotation (measurement_channel_id, sample_index_range, quality_code, origin, processing_version) VALUES (%s, ''[0,100)'', ''DRIFT'', ''ALGORITHM'', ''v1'')', k.mc), 'nicht eingeordnet');
    PERFORM pg_temp.muss_klappen('TIMING_UNCERTAIN als Bereich annotieren',
        format('INSERT INTO quality_annotation (measurement_channel_id, sample_index_range, quality_code, origin) VALUES (%s, ''[500000,680000)'', ''TIMING_UNCERTAIN'', ''INGESTION'')', k.mc));
    PERFORM pg_temp.muss_scheitern('Annotation nachträglich ändern', 'UPDATE quality_annotation SET quality_code = ''SATURATED''', 'unveränderliche Spalten');
    PERFORM pg_temp.muss_klappen('Annotation widerrufen (neue REVOKE-Zeile)',
        format('INSERT INTO quality_annotation (measurement_channel_id, sample_index_range, action, origin, assessed_by, supersedes_annotation_id) SELECT %s, ''[500000,680000)'', ''REVOKE'', ''MANUAL_REVIEW'', ''robby'', max(id) FROM quality_annotation', k.mc));

    RAISE NOTICE '--- 7. Zeitbasis und Plan';
    PERFORM pg_temp.muss_scheitern('STEP_FORWARD bei vorgehender Uhr',
        format('INSERT INTO clock_sync_event (device_id, acquisition_run_id, reference_source, reference_time, device_time, correction_mode, applied_at) VALUES (%s, %s, ''BRIDGE'', ''2026-09-01 03:00Z'', ''2026-09-01 03:00:05Z'', ''STEP_FORWARD'', now())', k.node, k.run), 'clock_sync_event_check');
    PERFORM pg_temp.muss_klappen('RUN_BREAK bei vorgehender Uhr',
        format('INSERT INTO clock_sync_event (device_id, acquisition_run_id, reference_source, reference_time, device_time, correction_mode, applied_at) VALUES (%s, %s, ''BRIDGE'', ''2026-09-01 03:00Z'', ''2026-09-01 03:00:05Z'', ''RUN_BREAK'', now())', k.node, k.run));
    PERFORM pg_temp.muss_scheitern('neue Planversion rückwirkend in bereits aufgezeichnete Daten',
        format('INSERT INTO recording_plan (acquisition_run_id, plan_version, valid_from) VALUES (%s, 2, ''2026-09-01 00:00:30Z'')', k.run), 'bereits gespeicherten Daten');

    RAISE NOTICE '--- 8. Transport und Provenienz';
    PERFORM pg_temp.muss_scheitern('SD-Import über eine Bridge (Bridge hat keinen SD-Slot)',
        format('INSERT INTO batch_delivery (origin_batch_id, transport_code, bridge_device_id, bridge_role, delivery_status) VALUES (%s, ''SD_IMPORT'', %s, ''BRIDGE'', ''ACCEPTED'')', v_a, k.bridge), 'batch_delivery_check');
    PERFORM pg_temp.muss_klappen('LoRa-Anlieferung über Bridge + SD-Import desselben Batches',
        format('INSERT INTO batch_delivery (origin_batch_id, transport_code, bridge_device_id, bridge_role, delivery_status) VALUES (%1$s, ''LORA'', %2$s, ''BRIDGE'', ''ACCEPTED''), (%1$s, ''SD_IMPORT'', NULL, NULL, ''DUPLICATE'')', v_a, k.bridge));
    PERFORM pg_temp.muss_scheitern('ACCEPTED ohne zugeordneten origin_batch',
        'INSERT INTO batch_delivery (transport_code, delivery_status) VALUES (''USB'', ''ACCEPTED'')', 'batch_delivery_check');
    PERFORM pg_temp.muss_scheitern('Bridge als messendes Gerät eines Runs',
        format('INSERT INTO acquisition_run (series_id, device_id, device_configuration_id, node_run_key, started_at) VALUES (%s, %s, %s, ''x'', now())', k.ser, k.bridge, k.cfg), 'foreign key');
    PERFORM pg_temp.muss_scheitern('Verstärkung ohne Herkunft',
        format('INSERT INTO measurement_channel (acquisition_run_id, device_id, hardware_channel_id, channel_role, quantity_code, unit_code, data_kind, sample_rate_hz, sample_clock_source, gain) SELECT %s, %s, id, ''ENVIRONMENTAL'', ''soil_moisture'', ''%%'', ''RAW'', 1, ''SOFTWARE_TIMER'', 2 FROM hardware_channel WHERE probe_id IS NULL', v_run2, k.node), 'measurement_channel_check');

    RAISE NOTICE '--- 9. Trennung Sandbox / Live';
    PERFORM pg_temp.muss_scheitern('SBX-Site in live', 'INSERT INTO live.site (site_code, grid_system, grid_cell_id) VALUES (''SBX-DE-01'', ''MGRS_10KM'', ''x'')', 'site_code_not_sandbox');
    PERFORM pg_temp.muss_scheitern('echte Site in sandbox', 'INSERT INTO sandbox.site (site_code, grid_system, grid_cell_id) VALUES (''DE-01'', ''MGRS_10KM'', ''x'')', 'site_code_sandbox');
    PERFORM pg_temp.muss_klappen('SBX-Site in sandbox', 'INSERT INTO sandbox.site (site_code, grid_system, grid_cell_id) VALUES (''SBX-DE-01'', ''MGRS_10KM'', ''x'')');

    RAISE NOTICE '=== ALLE REGELTESTS BESTANDEN ===';
END
$t$;

ROLLBACK;
