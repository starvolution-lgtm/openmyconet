-- =============================================================================
-- BioComm Schema v2 -- Rueckbau (downgrade der Migration 8d4e2a6c1b70).
-- Nur moeglich, solange es keine zweite Aggregat-Version, keinen Grabstein und
-- keinen Protokolleintrag und keine Quarantaene-Zeile gibt; sonst bricht der Rueckbau ab (die Migration
-- prueft das vorher und meldet es verstaendlich).
-- =============================================================================
DO $$
DECLARE
    s text;
BEGIN
    FOREACH s IN ARRAY ARRAY['sandbox', 'live'] LOOP
        EXECUTE format('DROP VIEW %I.derived_aggregate_current', s);
        EXECUTE format('DROP TABLE %I.sample_block_quarantine', s);
        EXECUTE format('DROP TABLE %I.candidate_resolution_log', s);
        EXECUTE format('DROP INDEX %I.batch_delivery_transport', s);
        EXECUTE format('DROP TRIGGER sample_block_loeschschutz ON %I.sample_block', s);
        EXECUTE format('DROP TRIGGER sample_block_immutable ON %I.sample_block', s);
        EXECUTE format('CREATE TRIGGER sample_block_immutable BEFORE UPDATE OR DELETE ON %I.sample_block'
                       ' FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification()', s);
        EXECUTE format('DROP TRIGGER derived_aggregate_immutable ON %I.derived_aggregate', s);
        EXECUTE format('ALTER TABLE %I.derived_aggregate DROP CONSTRAINT derived_aggregate_grabstein_check,'
                       ' DROP CONSTRAINT derived_aggregate_werte_check,'
                       ' DROP CONSTRAINT derived_aggregate_samples_recorded_check,'
                       ' DROP CONSTRAINT derived_aggregate_pkey', s);
        EXECUTE format('ALTER TABLE %I.derived_aggregate DROP COLUMN aggregate_version, DROP COLUMN computed_at,'
                       ' ALTER COLUMN value_min SET NOT NULL, ALTER COLUMN value_max SET NOT NULL,'
                       ' ALTER COLUMN value_mean SET NOT NULL,'
                       ' ADD CONSTRAINT derived_aggregate_samples_recorded_check CHECK (samples_recorded > 0),'
                       ' ADD PRIMARY KEY (measurement_channel_id, resolution, bucket_start)', s);
    END LOOP;
END $$;
DROP FUNCTION biocomm_common.kandidat_festlegen(text, bigint, text, jsonb, text, text);
DROP PROCEDURE biocomm_common.core_0002(text);
DROP FUNCTION biocomm_common.sample_block_loeschschutz();
