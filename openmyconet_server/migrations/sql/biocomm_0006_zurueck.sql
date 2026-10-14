-- =============================================================================
-- BioComm Schema v6 -- Rueckbau (downgrade der Migration 7a1c5e9d2b84).
-- Die Migration prueft vorher, dass keine Sonde Revision oder Sensormodelle
-- traegt (sonst gingen die Angaben verloren).
-- =============================================================================
ALTER TABLE sandbox.probe
    DROP CONSTRAINT probe_sensor_models_objekt, DROP CONSTRAINT probe_revision_nicht_leer,
    DROP COLUMN sensor_models, DROP COLUMN revision;
ALTER TABLE live.probe
    DROP CONSTRAINT probe_sensor_models_objekt, DROP CONSTRAINT probe_revision_nicht_leer,
    DROP COLUMN sensor_models, DROP COLUMN revision;
DROP PROCEDURE biocomm_common.core_0006(text);
