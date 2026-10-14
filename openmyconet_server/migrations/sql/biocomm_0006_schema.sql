-- =============================================================================
-- BioComm Schema v6 (Alembic-Migration 7a1c5e9d2b84) -- Sondenangaben
-- Festgelegt 14.10.2026 (Robby, Claude): Revision und Sensormodelle einer Sonde
-- sind Eigenschaften der Sonde, nicht der Geraetekonfiguration. Der Node meldet
-- sie im LAUF_START (Feld einstellungen, Schluessel sonde_revision und
-- sensormodelle); der Server nimmt sie dort heraus und schreibt sie an die
-- Sonde. Ein Sondentausch zwingt damit nicht mehr zu einer neuen
-- config_version (docs/dateneingang_format_v1.md, Abschnitt "Wo gehoert welche
-- Metadatenart hin?").
--
-- NICHT von Hand ausfuehren. 0001-0005 bleiben unveraendert; die Kern-Aenderung
-- steht genau einmal in biocomm_common.core_0006(p_target) und gilt fuer
-- sandbox UND live.
--
-- Beide Spalten sind NULL fuer Sonden, die vor dieser Migration oder ohne
-- Angaben angelegt wurden. Der Eingang fuellt sie nur, wenn sie NULL sind, und
-- lehnt abweichende Angaben fuer dieselbe Seriennummer ab (neue Sonde, neue
-- Seriennummer). Das erzwingt der Code (omn/eingang/ereignisse.py), nicht die
-- Datenbank.
-- =============================================================================

CREATE OR REPLACE PROCEDURE biocomm_common.core_0006(p_target text)
LANGUAGE plpgsql AS $core$
DECLARE
    v_suchpfad text := current_setting('search_path');
BEGIN
    IF p_target NOT IN ('sandbox', 'live') THEN
        RAISE EXCEPTION 'core_0006: nur sandbox oder live erlaubt, nicht %', p_target;
    END IF;
    PERFORM set_config('search_path', p_target, true);

    ALTER TABLE probe
        ADD COLUMN revision      text,
        ADD COLUMN sensor_models jsonb,
        ADD CONSTRAINT probe_revision_nicht_leer CHECK (revision IS NULL OR length(btrim(revision)) > 0),
        ADD CONSTRAINT probe_sensor_models_objekt CHECK (
            sensor_models IS NULL OR jsonb_typeof(sensor_models) = 'object');

    PERFORM set_config('search_path', v_suchpfad, true);
END
$core$;

CALL biocomm_common.core_0006('sandbox');
CALL biocomm_common.core_0006('live');
