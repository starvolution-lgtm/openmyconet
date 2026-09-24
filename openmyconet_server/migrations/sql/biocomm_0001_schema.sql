-- =============================================================================
-- BioComm Sandkasten / Live -- Schema v1 (Alembic-Migration 3f1b2c4d5e6a)
-- Quelle: Entwurf im Kontrollzentrum 11_BioComm_Sandkasten/Entwurf_SQL_Storage/
-- biocomm_schema_draft.sql, Stand 24.09.2026, freigegeben als Arbeitsgrundlage.
-- Grundlage: biocomm-sandbox-spec-v7.md. Lokal gegen PostgreSQL 18.6 geprueft
-- (tests/sql/biocomm_regeln.sql, 43 Regeln).
--
-- NICHT von Hand ausfuehren: wird von migrations/versions/3f1b2c4d5e6a_*.py
-- eingespielt (nur PostgreSQL; auf SQLite No-op). Aenderungen am Schema kommen
-- als NEUE Migration + neue SQL-Datei, diese Datei bleibt unveraendert.
--
-- Zieldatenbank: PostgreSQL 18 (Prod/Staging seit 09.09.2026, siehe
-- Phase1_Konsistenzbericht.md). Nutzt PG-Funktionen, die SQLite nicht hat:
-- Schemas, Range-/Multirange-Typen, EXCLUDE-Constraints, generierte Spalten,
-- UNIQUE NULLS NOT DISTINCT (ab PG 15).
--
-- SCHEMA-PARITÄT AUS EINER QUELLE
--   Der gesamte Kern steht genau einmal in der Prozedur
--   biocomm_common.create_core(p_target). Sie wird für 'sandbox' und 'live'
--   aufgerufen (Abschnitt 9). Einzige Sandbox-exklusive Struktur:
--   sandbox.sandbox_scenario (+ Zuordnung zu Serien), Abschnitt 10.
--   In der späteren Umsetzung ruft eine Alembic-Migration dieselbe Prozedur
--   (bzw. dieselbe Python-Funktion) für beide Schemas auf.
--
-- KONVENTIONEN IM ENTWURF
--   * Englische Tabellen-/Spaltennamen wie in v7, deutsche Kommentare.
--     (Abweichung von der Repo-Konvention "deutschsprachiger Code",
--     Frage 5 im Bericht.)
--   * ANNAHME = folgt nicht aus v7, muss bestätigt werden.
--   * VARIANTE = offener Punkt aus v7 Abschnitt 8, bewusst nicht entschieden.
--   * LASTTEST = Parameter, den der Lasttest (B14) festlegt.
--   * Zeitstempel als timestamptz (intern UTC). Seit 23.09.2026 Regel für
--     alle neuen Tabellen (Repo-CLAUDE.md), bestehende bleiben naiv-UTC.
--   * Aufzählungen mit festem Zustandsautomaten als CHECK, pflegbare
--     Stammdaten (v7 3.11) als Referenztabellen.
--   * IDs: bigint identity. Node-seitige Kennungen (Run, Batch-Sequenz)
--     stehen zusätzlich als eigene Spalten, weil der Node die Backend-IDs
--     nicht kennt und sie in die Hash-Kette eingehen.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 0. Voraussetzungen
-- -----------------------------------------------------------------------------
-- Gemeinsames Schema NUR für Funktionen (keine Daten). Sandbox und Live teilen
-- damit dieselbe Logik; ein DROP SCHEMA sandbox CASCADE berührt es nicht.
-- Bedingt statt IF NOT EXISTS: PostgreSQL prüft bei CREATE SCHEMA IF NOT
-- EXISTS zuerst das CREATE-Recht auf der Datenbank. Mit Rollentrennung legt
-- biocomm_roles_setup.sql die Schemas vorab an, omn_owner hat dieses Recht
-- nicht (im lokalen Test gefunden).
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'biocomm_common') THEN
        CREATE SCHEMA biocomm_common;
    END IF;
END $$;

-- btree_gist wird für EXCLUDE-Constraints mit "bigint WITH =" gebraucht.
-- Seit PG 13 "trusted", darf also vom DB-Owner ohne Superuser angelegt werden.
-- Bewusst im Schema biocomm_common statt public: so enthält public nur die
-- Website-Tabellen, und staging_db_reset.sh kann public austauschen, ohne die
-- BioComm-Schemas (und deren EXCLUDE-Constraints) zu berühren.
CREATE EXTENSION IF NOT EXISTS btree_gist SCHEMA biocomm_common;


-- -----------------------------------------------------------------------------
-- 1. Unveränderlichkeit (v7: device_configuration, recording_plan-Versionen,
--    origin_batch, sample_block; außerdem Qualitäts-Historie und clock_sync)
-- -----------------------------------------------------------------------------
-- Technische Absicherung in drei Schichten:
--   (a) Rechte: die App-Rolle erhält auf diese Tabellen nur SELECT/INSERT,
--       kein UPDATE/DELETE/TRUNCATE (Abschnitt 11, Rollen-Variante A).
--   (b) Dieser Trigger: verbietet UPDATE und DELETE auch für Rollen, die
--       Rechte hätten (Schutz gegen Programmierfehler, Admin-Skripte).
--       Optionale Trigger-Argumente = Spalten, die sich ändern dürfen
--       (z. B. Statusfelder an origin_batch).
--   (c) Inhaltshashes (payload_hash) machen nachträgliche Änderungen an
--       ausgelagerten Payloads (Datei/Objektspeicher) erkennbar.
-- TRUNCATE feuert keine Zeilen-Trigger, deshalb (a) zwingend.
-- Der Schema-Owner kann Trigger abschalten; das ist gewollt (Cutover-DROP).
CREATE OR REPLACE FUNCTION biocomm_common.forbid_modification()
RETURNS trigger
LANGUAGE plpgsql AS $fn$
DECLARE
    v_alt jsonb;
    v_neu jsonb;
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION '%.%: Zeilen sind unveränderlich, DELETE verboten',
            TG_TABLE_SCHEMA, TG_TABLE_NAME;
    END IF;
    v_alt := to_jsonb(OLD) - coalesce(TG_ARGV, '{}'::text[]);
    v_neu := to_jsonb(NEW) - coalesce(TG_ARGV, '{}'::text[]);
    IF v_alt IS DISTINCT FROM v_neu THEN
        RAISE EXCEPTION '%.%: unveränderliche Spalten dürfen nicht geändert werden (erlaubt: %)',
            TG_TABLE_SCHEMA, TG_TABLE_NAME,
            coalesce(nullif(array_to_string(TG_ARGV, ', '), ''), 'keine');
    END IF;
    RETURN NEW;
END
$fn$;


-- -----------------------------------------------------------------------------
-- 2. Weitere Prüf-Trigger (Regeln, die CHECK/FK allein nicht abbilden)
-- -----------------------------------------------------------------------------
-- Alle Funktionen adressieren Tabellen über TG_TABLE_SCHEMA, damit dieselbe
-- Funktion für sandbox und live korrekt arbeitet (kein search_path-Risiko).

-- 2a. sample_block nur aus kanonischen Ursprungsbatches (v7 3.9: widersprüch-
--     liche Payloads bleiben in Quarantäne und werden nicht still kanonisch).
CREATE OR REPLACE FUNCTION biocomm_common.require_canonical_batch()
RETURNS trigger
LANGUAGE plpgsql AS $fn$
DECLARE
    v_status text;
BEGIN
    EXECUTE format('SELECT batch_status FROM %I.origin_batch WHERE id = $1', TG_TABLE_SCHEMA)
        INTO v_status USING NEW.origin_batch_id;
    IF v_status IS DISTINCT FROM 'CANONICAL' THEN
        RAISE EXCEPTION 'sample_block: origin_batch % ist nicht CANONICAL (Status %)',
            NEW.origin_batch_id, v_status;
    END IF;
    RETURN NEW;
END
$fn$;

-- 2b. Qualitätscode nur verwenden, wenn er in der aktiven Version der
--     Abdeckungszuordnung eingeordnet ist (v7 3.8 und 6).
CREATE OR REPLACE FUNCTION biocomm_common.require_mapped_quality_code()
RETURNS trigger
LANGUAGE plpgsql AS $fn$
DECLARE
    v_ok boolean;
BEGIN
    IF NEW.quality_code IS NULL THEN          -- REVOKE-Einträge tragen keinen Code
        RETURN NEW;
    END IF;
    EXECUTE format($q$
        SELECT EXISTS (
            SELECT 1
              FROM %1$I.coverage_mapping m
              JOIN %1$I.coverage_mapping_version v ON v.id = m.mapping_version_id
             WHERE m.quality_code = $1
               AND v.id = (SELECT id FROM %1$I.coverage_mapping_version
                            WHERE activated_at IS NOT NULL AND activated_at <= now()
                            ORDER BY activated_at DESC LIMIT 1))
        $q$, TG_TABLE_SCHEMA)
        INTO v_ok USING NEW.quality_code;
    IF NOT v_ok THEN
        RAISE EXCEPTION 'quality_annotation: Code % ist in der aktiven Abdeckungszuordnung nicht eingeordnet',
            NEW.quality_code;
    END IF;
    RETURN NEW;
END
$fn$;

-- 2c. Aufzeichnungsplan nicht rückwirkend (v7 3.4: "Eine Datenlücke darf
--     nicht rückwirkend zur geplanten Pause erklärt werden").
--     Regel: valid_from einer neuen Planversion muss hinter dem spätesten
--     bereits gespeicherten RAW-Sample des Runs liegen; Intervalle eines
--     Plans dürfen nicht vor dessen valid_from beginnen.
--     ANNAHME: Maßstab ist measured_at der gespeicherten RAW-Daten, nicht
--     die Serverzeit. Nur so funktioniert die Regel auch für nachträglich
--     generierte Sandbox-Jahre. Einschränkung: Solange RAW per SD noch nicht
--     angeliefert ist, sieht die Prüfung diese Daten nicht. recorded_at
--     (Serverzeit des Eintrags) bleibt deshalb als zweiter Beleg gespeichert;
--     die Cutover-Berechnung für live verwendet zusätzlich nur Planversionen
--     mit recorded_at <= Beginn des bewerteten Tages. Für die Sandbox
--     (nachträglich generiertes Jahr) entfällt diese Zusatzprüfung
--     (siehe Übersicht, Abschnitt 7).
CREATE OR REPLACE FUNCTION biocomm_common.forbid_retroactive_plan()
RETURNS trigger
LANGUAGE plpgsql AS $fn$
DECLARE
    v_letzte timestamptz;
    v_valid_from timestamptz;
BEGIN
    IF TG_TABLE_NAME = 'recording_plan' THEN
        EXECUTE format($q$
            SELECT max(sb.time_anchor
                       + make_interval(secs => (sb.sample_count / sb.sample_rate_hz)::double precision))
              FROM %1$I.sample_block sb
             WHERE sb.acquisition_run_id = $1
            $q$, TG_TABLE_SCHEMA)
            INTO v_letzte USING NEW.acquisition_run_id;
        IF v_letzte IS NOT NULL AND NEW.valid_from < v_letzte THEN
            RAISE EXCEPTION 'recording_plan: valid_from % liegt vor bereits gespeicherten Daten (%)',
                NEW.valid_from, v_letzte;
        END IF;
    ELSIF TG_TABLE_NAME = 'recording_plan_interval' THEN
        EXECUTE format('SELECT valid_from FROM %I.recording_plan WHERE id = $1', TG_TABLE_SCHEMA)
            INTO v_valid_from USING NEW.recording_plan_id;
        IF lower(NEW.period) < v_valid_from THEN
            RAISE EXCEPTION 'recording_plan_interval: beginnt vor valid_from der Planversion';
        END IF;
    END IF;
    RETURN NEW;
END
$fn$;

-- 2d. Stimulation: Zustandsübergänge (v7 3.6). Nur PLANNED ist offen; alle
--     anderen Zustände sind endgültig. Soll-Parameter sind ohnehin in eigenen,
--     unveränderlichen Tabellen.
--     ANNAHME: Eine laufende Stimulation bleibt im Backend PLANNED, bis der
--     Node den Endzustand meldet (v7 kennt keinen Zustand "RUNNING").
CREATE OR REPLACE FUNCTION biocomm_common.check_stimulation_transition()
RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.execution_state IS DISTINCT FROM OLD.execution_state
       AND OLD.execution_state <> 'PLANNED' THEN
        RAISE EXCEPTION 'stimulation %: Zustand % ist endgültig', OLD.id, OLD.execution_state;
    END IF;
    RETURN NEW;
END
$fn$;


-- 2e. EC-Messung und Stimulation schließen sich aus.
--     ANNAHME bis zur Antwort von Richard (EC-Anregung und Stimulation
--     teilen sich evtl. denselben Ausgang DAC_OUT): Eine ausgeführte
--     Stimulation (EXECUTED/PARTIAL) darf kein geplantes EC-Messfenster des
--     Runs überlappen. Eigener Trigger, damit er bei gegenteiliger Antwort
--     ersatzlos entfernt werden kann.
CREATE OR REPLACE FUNCTION biocomm_common.forbid_stimulation_during_ec()
RETURNS trigger
LANGUAGE plpgsql AS $fn$
DECLARE
    v_konflikt boolean;
BEGIN
    -- BEFORE-Trigger laufen vor den CHECK-Constraints: fehlen Ist-Zeiten,
    -- entscheidet der CHECK (sonst wäre der Bereich unbegrenzt und
    -- überlappte scheinbar jedes EC-Fenster; im lokalen Test gefunden).
    IF NEW.execution_state NOT IN ('EXECUTED', 'PARTIAL')
       OR NEW.actual_start IS NULL OR NEW.actual_duration_ms IS NULL THEN
        RETURN NEW;
    END IF;
    EXECUTE format($q$
        SELECT EXISTS (
            SELECT 1 FROM %I.recording_plan_interval i
             WHERE i.acquisition_run_id = $1
               AND i.pause_reason = 'EC_MEASUREMENT'
               AND i.period && tstzrange($2, $2 + make_interval(secs => $3 / 1000.0)))
        $q$, TG_TABLE_SCHEMA)
        INTO v_konflikt
        USING NEW.acquisition_run_id, NEW.actual_start, NEW.actual_duration_ms;
    IF v_konflikt THEN
        RAISE EXCEPTION 'stimulation %: überlappt ein geplantes EC-Messfenster', NEW.id;
    END IF;
    RETURN NEW;
END
$fn$;


-- -----------------------------------------------------------------------------
-- 3.–8. KERN: eine Quelle für sandbox und live
-- -----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE biocomm_common.create_core(p_target text)
LANGUAGE plpgsql AS $core$
DECLARE
    -- Suchpfad des Aufrufers; wird am Ende wiederhergestellt. Sonst stuende er
    -- fuer den Rest der Transaktion auf p_target, und z. B. Alembic faende seine
    -- Tabelle alembic_version nicht mehr (im lokalen Test gefunden).
    v_suchpfad text := current_setting('search_path');
BEGIN
    IF p_target NOT IN ('sandbox', 'live') THEN
        RAISE EXCEPTION 'create_core: nur sandbox oder live erlaubt, nicht %', p_target;
    END IF;

    -- Private Geodaten in eigenem Schema: die Web-/API-Rolle bekommt darauf
    -- kein USAGE (v7 3.10, Rollen-Variante A in Abschnitt 11).
    -- ggf. vom Rollen-Skript vorab angelegt (dann ohne CREATE-Recht auf der DB)
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = p_target) THEN
        EXECUTE format('CREATE SCHEMA %I', p_target);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = p_target || '_private') THEN
        EXECUTE format('CREATE SCHEMA %I', p_target || '_private');
    END IF;
    PERFORM set_config('search_path', p_target, true);   -- nur für diese Transaktion

    -- =========================================================================
    -- 3. Stammdaten / Referenzlisten (v7 3.11)
    -- =========================================================================
    -- ANNAHME: Referenzlisten liegen je Schema (nicht geteilt), damit jedes
    -- Schema in sich geschlossen ist und DROP SCHEMA sandbox CASCADE beim
    -- Cutover nichts in live berührt. Alternative: gemeinsames Schema
    -- biocomm_ref (weniger Doppelpflege, dafür Querabhängigkeit).

    CREATE TABLE ref_channel_role (
        code        text PRIMARY KEY,
        description text NOT NULL
    );
    INSERT INTO ref_channel_role VALUES
        ('PRIMARY',       'untersuchte Zielgröße'),
        ('ENVIRONMENTAL', 'Umwelt-/Substratkontext'),
        ('SYSTEM',        'technische Telemetrie');

    CREATE TABLE ref_unit (
        code        text PRIMARY KEY,           -- UCUM-Code (v7 3.3: Empfehlung)
        description text NOT NULL
    );
    INSERT INTO ref_unit VALUES                 -- ANNAHME: Startliste
        ('uV',      'Mikrovolt'),
        ('V',       'Volt'),
        ('{count}', 'ADC-Rohwert, unkalibriert'),
        ('Cel',     'Grad Celsius'),
        ('%',       'Prozent'),
        ('mS/cm',   'Millisiemens pro Zentimeter'),
        ('[ppm]',   'parts per million'),
        ('dB[mW]',  'dBm'),
        ('Hz',      'Hertz'),
        ('ms',      'Millisekunde'),
        ('nm',      'Nanometer'),
        ('uA',      'Mikroampere');

    CREATE TABLE ref_quantity (
        code              text PRIMARY KEY,
        description       text NOT NULL,
        default_unit_code text REFERENCES ref_unit(code)
    );
    INSERT INTO ref_quantity VALUES             -- v7 3.3, Einheiten = ANNAHME
        ('bioelectric_potential',   'bioelektrisches Potential',   'uV'),
        ('soil_temperature',        'Bodentemperatur',             'Cel'),
        ('soil_moisture',           'Bodenfeuchte',                '%'),
        ('electrical_conductivity', 'elektrische Leitfähigkeit',   'mS/cm'),
        ('co2',                     'CO2-Konzentration',           '[ppm]'),
        ('air_temperature',         'Lufttemperatur',              'Cel'),
        ('relative_humidity',       'relative Luftfeuchte',        '%'),
        ('battery_voltage',         'Akkuspannung (MAX17048)',     'V'),
        ('battery_state_of_charge', 'Akku-Ladezustand (MAX17048)', '%'),
        ('rssi',                    'Empfangsfeldstärke',          'dB[mW]');
        -- MAX17048-Werte sind SYSTEM-Kanäle; wichtig, weil die Platine keinen
        -- Tiefentladeschutz hat (Netzlistenprüfung COMBO_NODE Rev 3.2).

    -- Taktquelle einer Aufzeichnung (Netzlistenprüfung: ADS1115 ALERT/RDY
    -- nicht verbunden, DS3231 INT/SQW an IO5 als möglicher Abtasttakt).
    CREATE TABLE ref_clock_source (
        code        text PRIMARY KEY,
        description text NOT NULL
    );
    INSERT INTO ref_clock_source VALUES
        ('RTC_SQW',        'Rechtecksignal der DS3231 (INT/SQW an IO5)'),
        ('SOFTWARE_TIMER', 'Timer der MCU'),
        ('ADC_FREE_RUN',   'ADC im Dauerbetrieb, Takt aus dem ADC');

    -- Reset-Ursache am Run-Ende (u. a. Hardware-Watchdog TPS3823). Die
    -- endgültige Liste liefert die Firmware; ANNAHME: Startwerte.
    CREATE TABLE ref_reset_cause (
        code        text PRIMARY KEY,
        description text NOT NULL
    );
    INSERT INTO ref_reset_cause VALUES
        ('POWER_ON',     'Einschalten'),
        ('BROWNOUT',     'Unterspannung'),
        ('WATCHDOG_HW',  'Hardware-Watchdog TPS3823'),
        ('WATCHDOG_SW',  'Software-Watchdog'),
        ('SOFTWARE',     'Neustart durch Firmware'),
        ('EXTERNAL_PIN', 'Reset-Taster/-Pin'),
        ('UNKNOWN',      'unbekannt');

    CREATE TABLE ref_actuator_type (
        code        text PRIMARY KEY,
        description text NOT NULL
    );
    INSERT INTO ref_actuator_type VALUES
        ('ELECTRICAL', 'elektrische Stimulation'),
        ('OPTICAL',    'optische Stimulation'),
        ('VIBRATION',  'Vibrations-/Schwingungsstimulation');

    CREATE TABLE ref_transport (
        code        text PRIMARY KEY,
        description text NOT NULL
    );
    INSERT INTO ref_transport VALUES            -- v7 3.9, "spätere Wege" ergänzbar
        ('LORA',      'LoRa Punkt-zu-Punkt über Bridge'),
        ('BLE',       'Bluetooth LE über Bridge'),
        ('SD_IMPORT', 'Import von der SD-Karte des Nodes (J11)'),
        ('USB',       'USB-Übertragung');

    CREATE TABLE ref_time_source (
        code        text PRIMARY KEY,
        description text NOT NULL
    );
    INSERT INTO ref_time_source VALUES          -- C8 offen, daher nur Beispiele
        ('BRIDGE',  'Zeit der Bridge'),
        ('GNSS',    'Satellitenzeit'),
        ('NTP',     'NTP/Gateway'),
        ('MANUAL',  'manuelle Referenz');

    CREATE TABLE substrate (
        code  text PRIMARY KEY,
        label text NOT NULL
    );
    INSERT INTO substrate VALUES                -- v7 3.11
        ('WOOD_CHIPS',  'Holzspäne'),
        ('SOIL',        'Erde/terrestrisch'),
        ('STRAW',       'Stroh'),
        ('COMPOST',     'Kompost'),
        ('AQUATIC',     'Aquatisch'),
        ('OTHER',       'Sonstig');

    -- Qualitätscodes (v7 3.8). MISSING und DUPLICATE sind ausdrücklich keine
    -- gespeicherten Codes, VALID ist kein Bit -> per CHECK ausgeschlossen.
    CREATE TABLE ref_quality_code (
        code         text PRIMARY KEY
                     CHECK (code NOT IN ('MISSING', 'DUPLICATE', 'VALID')),
        bit_position smallint NOT NULL UNIQUE CHECK (bit_position BETWEEN 0 AND 62),
        description  text NOT NULL
    );
    INSERT INTO ref_quality_code VALUES         -- C2: Liste vorläufig
        ('OUT_OF_RANGE',     0, 'außerhalb des Messbereichs'),
        ('SATURATED',        1, 'ADC-Sättigung'),
        ('SENSOR_ERROR',     2, 'Sensorfehler'),
        ('TIMING_UNCERTAIN', 3, 'zeitliche Zuordnung außerhalb der Toleranz'),
        ('INTERPOLATED',     4, 'interpolierter Wert');

    -- Versionierte Abdeckungswirkung je Code (v7 3.8, Tabelle in 6).
    CREATE TABLE coverage_mapping_version (
        id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        version_label text NOT NULL UNIQUE,
        created_at    timestamptz NOT NULL DEFAULT now(),
        activated_at  timestamptz,                -- NULL = Entwurf, noch nicht wirksam
        note          text
    );
    CREATE TABLE coverage_mapping (
        mapping_version_id bigint NOT NULL REFERENCES coverage_mapping_version(id),
        quality_code       text   NOT NULL REFERENCES ref_quality_code(code),
        counts_as_recorded boolean NOT NULL,
        PRIMARY KEY (mapping_version_id, quality_code)
    );
    INSERT INTO coverage_mapping_version (version_label, activated_at, note)
        VALUES ('v1', now(), 'Zuordnung gemäß Spezifikation v7, Abschnitt 6');
    INSERT INTO coverage_mapping (mapping_version_id, quality_code, counts_as_recorded)
        SELECT v.id, c.code, c.zaehlt
          FROM coverage_mapping_version v,
               (VALUES ('OUT_OF_RANGE', true), ('SATURATED', true),
                       ('TIMING_UNCERTAIN', true), ('SENSOR_ERROR', false),
                       ('INTERPOLATED', false)) AS c(code, zaehlt)
         WHERE v.version_label = 'v1';
    CREATE TRIGGER coverage_mapping_immutable
        BEFORE UPDATE OR DELETE ON coverage_mapping
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();
    CREATE TRIGGER coverage_mapping_version_immutable
        BEFORE UPDATE OR DELETE ON coverage_mapping_version
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification('activated_at');
    -- ANNAHME: activated_at darf einmalig gesetzt werden (Entwurf -> aktiv);
    -- eine Zuordnung, die schon für Cutover-Berechnungen benutzt wurde, darf
    -- nicht mehr geändert werden. Feinschliff (nur NULL -> Wert) bei Umsetzung.


    -- =========================================================================
    -- 4. Standorte und Geodaten (v7 3.10)
    -- =========================================================================
    CREATE TABLE site (
        id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        site_code       text NOT NULL UNIQUE,          -- z. B. SBX-DE-01
        grid_system     text NOT NULL CHECK (grid_system IN ('MGRS_10KM')),
        grid_cell_id    text NOT NULL,                 -- beim Anlegen berechnet, nie Site-ID
        elevation_m_rounded integer,                   -- optional, gerundet
        created_at      timestamptz NOT NULL DEFAULT now()
        -- bewusst KEIN UNIQUE auf grid_cell_id: mehrere Sites je Zelle erlaubt
        -- (v7: interne Tests mit zwei Sites in derselben Zelle).
    );

    -- IANA-Zeitzone historisiert (gültig ab/bis), nie überschrieben.
    CREATE TABLE site_timezone (
        id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        site_id     bigint NOT NULL REFERENCES site(id),
        iana_tz     text   NOT NULL,   -- Gültigkeit gegen pg_timezone_names prüft die App
        valid_from  timestamptz NOT NULL,
        valid_to    timestamptz,
        CHECK (valid_to IS NULL OR valid_to > valid_from),
        EXCLUDE USING gist (site_id WITH =,
                            tstzrange(valid_from, valid_to) WITH &&)
    );

    -- Exakte Koordinaten: eigenes Schema <ziel>_private (Name dynamisch).
    EXECUTE format($q$
        CREATE TABLE %1$I.site_location_private (
            site_id     bigint PRIMARY KEY REFERENCES %2$I.site(id),
            latitude    numeric(9,6) NOT NULL CHECK (latitude  BETWEEN -90  AND 90),
            longitude   numeric(9,6) NOT NULL CHECK (longitude BETWEEN -180 AND 180),
            elevation_m numeric(7,1),
            source      text,
            recorded_at timestamptz NOT NULL DEFAULT now()
        )$q$, p_target || '_private', p_target);


    -- =========================================================================
    -- 5. Hardware-Provenienz (v7 3.2)
    -- =========================================================================
    CREATE TABLE device (
        id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        device_serial text NOT NULL UNIQUE,            -- z. B. OMN-NODE-00017
        device_role   text NOT NULL CHECK (device_role IN ('NODE', 'BRIDGE')),
        created_at    timestamptz NOT NULL DEFAULT now(),
        note          text,
        UNIQUE (id, device_role)                       -- Ziel für Rollen-FKs
        -- ANNAHME: Rolle eines Geräts ist fest. Live-Verknüpfung zur
        -- bestehenden Verwaltungstabelle public.knoten später über eine
        -- eigene Zuordnung, nicht hier (Parität: sandbox kennt knoten nicht).
    );

    CREATE TABLE device_configuration (
        id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        device_id         bigint NOT NULL REFERENCES device(id),
        hardware_revision text   NOT NULL,
        firmware_version  text   NOT NULL,
        config_version    text   NOT NULL,
        settings          jsonb  NOT NULL DEFAULT '{}',   -- technische Einstellungen
        incompatibilities jsonb  NOT NULL DEFAULT '[]',   -- C5 offen
        created_at        timestamptz NOT NULL DEFAULT now(),
        UNIQUE (device_id, hardware_revision, firmware_version, config_version),
        UNIQUE (id, device_id)
    );
    CREATE TRIGGER device_configuration_immutable
        BEFORE UPDATE OR DELETE ON device_configuration
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();

    CREATE TABLE probe (
        id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        probe_serial text NOT NULL UNIQUE,
        probe_kind   text NOT NULL CHECK (probe_kind IN ('EXTERNAL_BIOCOMM', 'OTHER')),
        created_at   timestamptz NOT NULL DEFAULT now(),
        note         text
    );

    -- Stabile Identität eines realen physischen Eingangs/Sensors/Kontakts.
    -- Neue Sonde, neuer Node oder anderer Eingang = neue Zeile.
    CREATE TABLE hardware_channel (
        id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        device_id   bigint NOT NULL REFERENCES device(id),  -- Node mit dem Eingang
        probe_id    bigint REFERENCES probe(id),            -- NULL bei Onboard-Sensoren
        input_label text   NOT NULL,                        -- z. B. 'IN+ / Eingang 1'
        description text,
        UNIQUE NULLS NOT DISTINCT (device_id, probe_id, input_label),
        UNIQUE (id, device_id)
    );

    -- Physischer Ausgang (v7 3.6, A4). Grenzwerte versioniert über die
    -- unveränderliche device_configuration.
    -- ANNAHME: Aktoren hängen immer an einer device_configuration, optional
    -- zusätzlich an einer Sonde (LEDs im Sondenkörper).
    CREATE TABLE actuator_channel (
        id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        device_configuration_id bigint NOT NULL REFERENCES device_configuration(id),
        probe_id                bigint REFERENCES probe(id),
        actuator_type           text   NOT NULL REFERENCES ref_actuator_type(code),
        output_label            text   NOT NULL,          -- z. B. 'J_STIM', 'LED_PWM1'
        operating_limits        jsonb  NOT NULL DEFAULT '{}',
        UNIQUE NULLS NOT DISTINCT (device_configuration_id, probe_id, output_label),
        UNIQUE (id, actuator_type),
        UNIQUE (id, device_configuration_id)
    );
    CREATE TRIGGER actuator_channel_immutable
        BEFORE UPDATE OR DELETE ON actuator_channel
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();


    -- =========================================================================
    -- 6. Wissenschaft und Technik: series, acquisition_run, Kanäle, Plan
    -- =========================================================================
    CREATE TABLE series (
        id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        series_code    text   NOT NULL UNIQUE,
        site_id        bigint NOT NULL REFERENCES site(id),
        substrate_code text   NOT NULL REFERENCES substrate(code),
        title          text   NOT NULL,
        study_period   tstzrange,               -- Untersuchungszeitraum
        context        text,                    -- Versuchskontext
        created_at     timestamptz NOT NULL DEFAULT now()
        -- keine Samplingrate (B1)
    );

    CREATE TABLE acquisition_run (
        id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        series_id               bigint NOT NULL REFERENCES series(id),
        device_id               bigint NOT NULL,
        device_role             text   NOT NULL DEFAULT 'NODE' CHECK (device_role = 'NODE'),
        device_configuration_id bigint NOT NULL,
        -- Node-seitige Run-Kennung. ANNAHME: vom Node erzeugt (z. B. Boot-
        -- Zähler oder zufällige ID), geht in die Hash-Kette ein (C4).
        node_run_key            text   NOT NULL,
        started_at              timestamptz NOT NULL,   -- Gerätezeit (measured_at-Basis)
        ended_at                timestamptz,
        end_reason              text CHECK (end_reason IN (
                                    'RESTART', 'FIRMWARE_CHANGE', 'PROBE_CHANGE',
                                    'CONFIG_CHANGE', 'RTC_RUN_BREAK', 'POWER_LOSS',
                                    'CRASH', 'SAFETY_SHUTDOWN', 'PLANNED_END', 'UNKNOWN')),
                                    -- ANNAHME: Liste vorläufig (C5)
        -- Reset-Ursache, falls der Run durch einen Reset endete (liefert die
        -- Firmware später; z. B. Hardware-Watchdog TPS3823).
        reset_cause             text REFERENCES ref_reset_cause(code),
        CHECK (ended_at IS NULL OR ended_at >= started_at),
        CHECK ((ended_at IS NULL) = (end_reason IS NULL)),
        CHECK (reset_cause IS NULL OR ended_at IS NOT NULL),
        -- genau ein messender NODE (B2): Rolle über zusammengesetzten FK
        FOREIGN KEY (device_id, device_role) REFERENCES device(id, device_role),
        -- Konfiguration muss zu genau diesem Gerät gehören (B2)
        FOREIGN KEY (device_configuration_id, device_id)
            REFERENCES device_configuration(id, device_id),
        UNIQUE (device_id, node_run_key),
        UNIQUE (id, device_id),
        UNIQUE (id, device_configuration_id)
    );

    CREATE TABLE probe_assignment (
        id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        acquisition_run_id bigint NOT NULL REFERENCES acquisition_run(id),
        probe_id           bigint NOT NULL REFERENCES probe(id),
        is_external_biocomm boolean NOT NULL,   -- Kopie von probe.probe_kind für den Index unten
        UNIQUE (acquisition_run_id, probe_id)
    );
    -- Betriebsregel BioComm v1 (nicht Kernmodell, bewusst eigener, später
    -- entfernbarer Index): höchstens eine externe BioComm-Sonde je Run.
    CREATE UNIQUE INDEX probe_assignment_v1_one_external
        ON probe_assignment (acquisition_run_id) WHERE is_external_biocomm;

    CREATE TABLE measurement_channel (
        id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        acquisition_run_id  bigint NOT NULL,
        device_id           bigint NOT NULL,           -- Redundanz nur für Konsistenz-FKs
        hardware_channel_id bigint NOT NULL,
        channel_role        text   NOT NULL REFERENCES ref_channel_role(code),
        quantity_code       text   NOT NULL REFERENCES ref_quantity(code),
        unit_code           text   NOT NULL REFERENCES ref_unit(code),
        data_kind           text   NOT NULL CHECK (data_kind IN ('RAW', 'DERIVED')),
        sample_rate_hz      numeric CHECK (sample_rate_hz > 0),  -- NULL = ereignisbezogen
        -- Taktquelle der Abtastung (RTC_SQW, SOFTWARE_TIMER, ADC_FREE_RUN)
        sample_clock_source text REFERENCES ref_clock_source(code),
        -- Verstärkung: INA333 per DIP-Schalter, NICHT auslesbar -> Herkunft
        -- MANUAL (beim Run-Start eingetragen). Da die Zeile unveränderlich
        -- ist, bedeutet jede Änderung der Verstärkung einen neuen Run.
        gain                numeric CHECK (gain > 0),
        gain_source         text CHECK (gain_source IN ('MANUAL', 'DEVICE_REPORTED')),
        CHECK ((gain IS NULL) = (gain_source IS NULL)),
        CHECK (sample_rate_hz IS NULL OR data_kind = 'DERIVED' OR sample_clock_source IS NOT NULL),
        calibration         jsonb NOT NULL DEFAULT '{}',
        technical_config    jsonb NOT NULL DEFAULT '{}',
        -- DERIVED: erzeugende Verarbeitung (v7 3.3, 3.9)
        processing_origin   text CHECK (processing_origin IN ('NODE', 'BACKEND')),
        processing_version  text,
        CHECK ((data_kind = 'RAW'     AND processing_origin IS NULL AND processing_version IS NULL)
            OR (data_kind = 'DERIVED' AND processing_origin IS NOT NULL AND processing_version IS NOT NULL)),
        -- Kanal gehört zum Run, Hardwarekanal zum messenden Node des Runs
        FOREIGN KEY (acquisition_run_id, device_id) REFERENCES acquisition_run(id, device_id),
        FOREIGN KEY (hardware_channel_id, device_id) REFERENCES hardware_channel(id, device_id),
        UNIQUE (id, acquisition_run_id),
        UNIQUE (id, channel_role),
        UNIQUE (id, data_kind)
        -- ANNAHME: auch DERIVED-Kanäle tragen genau einen hardware_channel
        -- (den der Hauptquelle), damit Serien über Runs zusammensetzbar bleiben.
    );
    -- Ein RAW-Kanal je Run, Hardwarekanal und Messgröße (ein Sensor kann
    -- mehrere Größen liefern, z. B. SCD41: CO2, Temperatur, Feuchte).
    CREATE UNIQUE INDEX measurement_channel_raw_unique
        ON measurement_channel (acquisition_run_id, hardware_channel_id, quantity_code)
        WHERE data_kind = 'RAW';
    CREATE TRIGGER measurement_channel_immutable
        BEFORE UPDATE OR DELETE ON measurement_channel
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();
    -- ANNAHME: Kanalkonfiguration ist je Run fest (Änderung der PRIMARY-Rate
    -- beendet den Run, v7 3.1).

    CREATE TABLE derived_channel_source (
        derived_channel_id bigint NOT NULL REFERENCES measurement_channel(id),
        source_channel_id  bigint NOT NULL REFERENCES measurement_channel(id),
        PRIMARY KEY (derived_channel_id, source_channel_id),
        CHECK (derived_channel_id <> source_channel_id)
    );

    -- Aufzeichnungsplan (B9): unveränderliche Versionen je Run.
    CREATE TABLE recording_plan (
        id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        acquisition_run_id bigint  NOT NULL REFERENCES acquisition_run(id),
        plan_version       integer NOT NULL CHECK (plan_version >= 1),
        valid_from         timestamptz NOT NULL,     -- Gerätezeit-Basis
        recorded_at        timestamptz NOT NULL DEFAULT now(),
        note               text,
        UNIQUE (acquisition_run_id, plan_version),
        UNIQUE (acquisition_run_id, valid_from),
        UNIQUE (id, acquisition_run_id)
    );
    CREATE TRIGGER recording_plan_immutable
        BEFORE UPDATE OR DELETE ON recording_plan
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();
    CREATE TRIGGER recording_plan_not_retroactive
        BEFORE INSERT ON recording_plan
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_retroactive_plan();

    -- Vorgesehene PRIMARY-Kanäle, erforderlich oder optional (B9, B10).
    CREATE TABLE recording_plan_channel (
        recording_plan_id      bigint NOT NULL,
        acquisition_run_id     bigint NOT NULL,
        measurement_channel_id bigint NOT NULL,
        channel_role           text   NOT NULL DEFAULT 'PRIMARY' CHECK (channel_role = 'PRIMARY'),
        requirement            text   NOT NULL CHECK (requirement IN ('REQUIRED', 'OPTIONAL')),
        planned_sample_rate_hz numeric NOT NULL CHECK (planned_sample_rate_hz > 0),
        PRIMARY KEY (recording_plan_id, measurement_channel_id),
        FOREIGN KEY (recording_plan_id, acquisition_run_id)
            REFERENCES recording_plan(id, acquisition_run_id),
        FOREIGN KEY (measurement_channel_id, acquisition_run_id)
            REFERENCES measurement_channel(id, acquisition_run_id),
        FOREIGN KEY (measurement_channel_id, channel_role)
            REFERENCES measurement_channel(id, channel_role)
    );
    CREATE TRIGGER recording_plan_channel_immutable
        BEFORE UPDATE OR DELETE ON recording_plan_channel
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();

    -- Geplante Aufzeichnungsintervalle und Pausen.
    -- ANNAHME: als explizite Zeitintervalle gespeichert. Alternative:
    -- Wiederholungsregel (z. B. "stündlich 30 s EC-Messung") + Expansion im Job.
    --
    -- RECORDING-Intervalle gelten für alle Kanäle des Plans. PAUSE-Intervalle
    -- gelten entweder für alle Kanäle (measurement_channel_id NULL) oder nur
    -- für einen Kanal. Wichtigster Fall laut Netzlistenprüfung: Bio und EC
    -- teilen sich ADS1115 U8/AIN0 über einen Analogschalter. EC-Messfenster
    -- sind deshalb geplante Pausen des Bio-Kanals (pause_reason
    -- EC_MEASUREMENT), gefolgt von einer Einschwingzeit (EC_SETTLING; Dauer
    -- wartet auf Richard). Beide zählen nicht in den Nenner der 80-%-Regel.
    CREATE TABLE recording_plan_interval (
        id                     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        recording_plan_id      bigint NOT NULL,
        acquisition_run_id     bigint NOT NULL,
        interval_kind          text   NOT NULL CHECK (interval_kind IN ('RECORDING', 'PAUSE')),
        measurement_channel_id bigint,
        pause_reason           text   CHECK (pause_reason IN
                                   ('SCHEDULED', 'EC_MEASUREMENT', 'EC_SETTLING', 'MAINTENANCE', 'OTHER')),
        period                 tstzrange NOT NULL CHECK (NOT isempty(period)),
        channel_scope          bigint GENERATED ALWAYS AS (coalesce(measurement_channel_id, 0)) STORED,
        CHECK ((interval_kind = 'PAUSE') = (pause_reason IS NOT NULL)),
        CHECK (interval_kind = 'PAUSE' OR measurement_channel_id IS NULL),
        FOREIGN KEY (recording_plan_id, acquisition_run_id)
            REFERENCES recording_plan(id, acquisition_run_id),
        FOREIGN KEY (measurement_channel_id, acquisition_run_id)
            REFERENCES measurement_channel(id, acquisition_run_id),
        -- keine Überlappung gleicher Art im selben Geltungsbereich
        EXCLUDE USING gist (recording_plan_id WITH =, interval_kind WITH =,
                            channel_scope WITH =, period WITH &&)
    );
    CREATE INDEX recording_plan_interval_period
        ON recording_plan_interval USING gist (acquisition_run_id, period);
    CREATE TRIGGER recording_plan_interval_immutable
        BEFORE UPDATE OR DELETE ON recording_plan_interval
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();
    CREATE TRIGGER recording_plan_interval_not_retroactive
        BEFORE INSERT ON recording_plan_interval
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_retroactive_plan();


    -- =========================================================================
    -- 7. Transport, Ursprungspaket, RAW-Blöcke (v7 3.5, 3.9)
    -- =========================================================================
    CREATE TABLE origin_batch (
        id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        acquisition_run_id  bigint NOT NULL REFERENCES acquisition_run(id),

        -- 8.1.1 ENTSCHIEDEN (Robby, 23.09.2026): eine gemeinsame Sequenz und
        -- eine Chain je Run für RAW- und Aggregat-Batches. Der Node schreibt
        -- JEDEN origin_batch auf seine SD-Karte (J11); LoRa/BLE liefern
        -- zusätzlich zeitnah, das sind nur weitere batch_delivery desselben
        -- origin_batch. Der SD-Import schließt damit alle Lücken.
        -- VERWORFEN: Stream-Kennung mit eigener Sequenz je Stream.
        batch_sequence_no   bigint NOT NULL CHECK (batch_sequence_no >= 0),
        -- Inhaltsart nur beschreibend, NICHT Teil der Identität oder Chain.
        -- ANNAHME: Werteliste vorläufig, legt die Firmware fest (C4).
        batch_content       text   NOT NULL
                            CHECK (batch_content IN ('RAW', 'AGGREGATE', 'EVENT', 'TELEMETRY', 'MIXED')),
        measured_period     tstzrange NOT NULL,        -- Messzeitraum (Gerätezeit)

        -- Hash-Kette (C4: Serialisierung und Genesis-Wert offen).
        payload_hash        bytea  NOT NULL CHECK (octet_length(payload_hash) = 32),
        previous_batch_hash bytea  CHECK (octet_length(previous_batch_hash) = 32),
                                   -- NULL nur bis C4 den Genesis-Wert festlegt
        batch_hash          bytea  NOT NULL CHECK (octet_length(batch_hash) = 32),

        -- Kanonische, transportneutrale Ursprungspayload (A2). Wo sie liegt,
        -- entscheidet der Lasttest; eine der drei Formen ist Pflicht.
        payload_format      text   NOT NULL,           -- Formatkennung inkl. Version (C4)
        payload_location    text   NOT NULL CHECK (payload_location IN (
                                   'INLINE',            -- bytea unten
                                   'OBJECT_STORE',      -- Datei-/Objektspeicher, payload_ref
                                   'SAMPLE_BLOCKS')),   -- Fall 1: RAW-Blöcke SIND die Payload
        payload_inline      bytea,
        payload_ref         text,
        payload_size_bytes  bigint NOT NULL CHECK (payload_size_bytes >= 0),
        CHECK ((payload_location = 'INLINE'        AND payload_inline IS NOT NULL AND payload_ref IS NULL)
            OR (payload_location = 'OBJECT_STORE'  AND payload_inline IS NULL     AND payload_ref IS NOT NULL)
            OR (payload_location = 'SAMPLE_BLOCKS' AND payload_inline IS NULL     AND payload_ref IS NULL)),

        -- Zustände (B6): fachlicher Status und Chain-Vollständigkeit getrennt.
        batch_status        text   NOT NULL DEFAULT 'PENDING'
                            CHECK (batch_status IN ('PENDING', 'CANONICAL', 'CONFLICT', 'REJECTED')),
        chain_state         text   NOT NULL DEFAULT 'PREDECESSOR_MISSING'
                            CHECK (chain_state IN ('LINKED', 'PREDECESSOR_MISSING')),
        -- Offener Punkt 8.1.2 (NICHT entschieden): woraus folgte der Status?
        status_basis        text   CHECK (status_basis IN (
                                   'SINGLE_CANDIDATE',   -- kein Konkurrent
                                   'SUCCESSOR_LINK',     -- Nachfolger verweist per previous_batch_hash
                                   'MANUAL_REVIEW')),
        status_changed_at   timestamptz NOT NULL DEFAULT now(),
        created_at          timestamptz NOT NULL DEFAULT now(),

        -- Identität eines Ursprungskandidaten (A1): Run + Sequenz + Hash,
        -- NICHT Run + Sequenz allein.
        UNIQUE (acquisition_run_id, batch_sequence_no, payload_hash),
        UNIQUE (id, acquisition_run_id)
    );
    -- Höchstens ein KANONISCHER Kandidat je Sequenzplatz; Konfliktkandidaten
    -- (gleicher Platz, anderer Hash) bleiben daneben erhalten.
    CREATE UNIQUE INDEX origin_batch_one_canonical
        ON origin_batch (acquisition_run_id, batch_sequence_no)
        WHERE batch_status = 'CANONICAL';
    CREATE INDEX origin_batch_prev_hash ON origin_batch (previous_batch_hash);
    CREATE INDEX origin_batch_batch_hash ON origin_batch (batch_hash);
    CREATE TRIGGER origin_batch_immutable
        BEFORE UPDATE OR DELETE ON origin_batch
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification(
            'batch_status', 'chain_state', 'status_basis', 'status_changed_at');

    -- Konkrete Anlieferung (A1). Staging-Schicht: eine Zeile je Eingang.
    CREATE TABLE batch_delivery (
        id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        origin_batch_id      bigint REFERENCES origin_batch(id),  -- gesetzt ab Validierung
        transport_code       text   NOT NULL REFERENCES ref_transport(code),
        bridge_device_id     bigint,
        bridge_role          text   CHECK (bridge_role = 'BRIDGE'),
        received_at          timestamptz NOT NULL DEFAULT now(),
        -- Transportcontainer (LoRa-Fragmente, SD-Datei, USB-Rahmen) wird für
        -- die Nachvollziehbarkeit aufbewahrt, ist aber NICHT die Ursprungspayload.
        transport_ref        text,
        transport_hash       bytea CHECK (octet_length(transport_hash) = 32),
        delivery_status      text   NOT NULL DEFAULT 'RECEIVED'
                             CHECK (delivery_status IN ('RECEIVED', 'VALIDATED', 'ACCEPTED',
                                                        'DUPLICATE', 'CONFLICT', 'REJECTED')),
        status_reason        text,
        status_changed_at    timestamptz NOT NULL DEFAULT now(),
        CHECK ((bridge_device_id IS NULL) = (bridge_role IS NULL)),
        -- microSD-Slot sitzt am Node, die Bridge hat keinen: ein SD-Import
        -- läuft nie über eine Bridge.
        CHECK (transport_code <> 'SD_IMPORT' OR bridge_device_id IS NULL),
        FOREIGN KEY (bridge_device_id, bridge_role) REFERENCES device(id, device_role),
        -- Ab VALIDATED ist klar, zu welchem Ursprungskandidaten die Anlieferung gehört;
        -- REJECTED darf ohne Zuordnung bleiben (z. B. unlesbar).
        CHECK (delivery_status IN ('RECEIVED', 'REJECTED') OR origin_batch_id IS NOT NULL)
    );
    CREATE INDEX batch_delivery_origin ON batch_delivery (origin_batch_id);
    CREATE TRIGGER batch_delivery_facts_immutable
        BEFORE UPDATE OR DELETE ON batch_delivery
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification(
            'origin_batch_id', 'delivery_status', 'status_reason', 'status_changed_at');

    -- RAW-Block (B14): physische Speicherform für PRIMARY-RAW (und andere RAW).
    -- Enthält nur Blöcke aus CANONICAL-Batches (Trigger 2a). Nicht akzeptierte
    -- Payloads bleiben in origin_batch (Quarantäne).
    CREATE TABLE sample_block (
        id                     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        acquisition_run_id     bigint  NOT NULL,
        measurement_channel_id bigint  NOT NULL,
        data_kind              text    NOT NULL DEFAULT 'RAW' CHECK (data_kind = 'RAW'),
        origin_batch_id        bigint  NOT NULL,
        first_sample_index     bigint  NOT NULL CHECK (first_sample_index >= 0),
        sample_count           integer NOT NULL CHECK (sample_count > 0),   -- LASTTEST: Blockgröße
        sample_index_range     int8range GENERATED ALWAYS AS
                               (int8range(first_sample_index, first_sample_index + sample_count)) STORED,
        time_anchor            timestamptz NOT NULL,   -- measured_at des ersten Samples
        sample_rate_hz         numeric NOT NULL CHECK (sample_rate_hz > 0),
        value_encoding         text    NOT NULL,       -- z. B. 'int32le', 'int24le' (C4/LASTTEST)
        compression            text    NOT NULL DEFAULT 'none', -- LASTTEST: z. B. none/zstd/delta+zstd
        payload_location       text    NOT NULL CHECK (payload_location IN ('INLINE', 'OBJECT_STORE')),
        payload_inline         bytea,                  -- LASTTEST: BLOB ...
        payload_ref            text,                   -- ... oder Datei/Objekt
        payload_hash           bytea   NOT NULL CHECK (octet_length(payload_hash) = 32),
        -- Geräte-Qualitätsinformation (Herkunft DEVICE, v7 3.8 Ebene 1):
        -- Teil von RAW, unveränderlich. ANNAHME: lauflängenkodierte Bitmaske.
        device_quality         bytea,
        CHECK ((payload_location = 'INLINE'       AND payload_inline IS NOT NULL AND payload_ref IS NULL)
            OR (payload_location = 'OBJECT_STORE' AND payload_inline IS NULL     AND payload_ref IS NOT NULL)),
        FOREIGN KEY (measurement_channel_id, acquisition_run_id)
            REFERENCES measurement_channel(id, acquisition_run_id),
        FOREIGN KEY (measurement_channel_id, data_kind)
            REFERENCES measurement_channel(id, data_kind),
        FOREIGN KEY (origin_batch_id, acquisition_run_id)
            REFERENCES origin_batch(id, acquisition_run_id),
        -- Gleicher sample_index nie zweimal im selben Kanal (v7 3.8: kein
        -- zweiter Messwert). Inhaltlich abweichende Doppelbelegung wird damit
        -- zwangsläufig zum Konflikt in der Staging-Schicht, nie still überschrieben.
        EXCLUDE USING gist (measurement_channel_id WITH =, sample_index_range WITH &&)
    );
    -- Hinweis Partitionierung (LASTTEST): Ein EXCLUDE-Constraint auf einer
    -- partitionierten Tabelle muss den Partitionsschlüssel mit "=" enthalten.
    -- Passend wäre daher LIST/HASH-Partitionierung nach measurement_channel_id
    -- (bzw. nach acquisition_run_id mit zusätzlicher Spalte im Constraint),
    -- nicht RANGE nach Zeit. Alternative: Zeitpartitionen + Prüfung in der
    -- Ingestion statt EXCLUDE. Entscheidung im Lasttest.
    CREATE INDEX sample_block_channel_time ON sample_block (measurement_channel_id, time_anchor);
    CREATE INDEX sample_block_batch ON sample_block (origin_batch_id);
    CREATE TRIGGER sample_block_immutable
        BEFORE UPDATE OR DELETE ON sample_block
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();
    CREATE TRIGGER sample_block_canonical_only
        BEFORE INSERT ON sample_block
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.require_canonical_batch();

    -- Vorberechnete DERIVED-Auflösungen fürs Dashboard (v7 3.5; C3 offen).
    -- Fehlende Zeitfenster haben KEINE Zeile (fehlend ist nicht Null).
    CREATE TABLE derived_aggregate (
        measurement_channel_id bigint NOT NULL,        -- DERIVED-Kanal
        data_kind              text   NOT NULL DEFAULT 'DERIVED' CHECK (data_kind = 'DERIVED'),
        resolution             text   NOT NULL CHECK (resolution IN ('1s', '1min', '1h')),
        bucket_start           timestamptz NOT NULL,
        samples_expected       integer CHECK (samples_expected >= 0),
        samples_recorded       integer NOT NULL CHECK (samples_recorded > 0),
        value_min              double precision NOT NULL,
        value_max              double precision NOT NULL,
        value_mean             double precision NOT NULL,
        quality_mask           bigint NOT NULL DEFAULT 0,   -- abgeleitet, nicht Wahrheitsquelle
        PRIMARY KEY (measurement_channel_id, resolution, bucket_start),
        FOREIGN KEY (measurement_channel_id, data_kind)
            REFERENCES measurement_channel(id, data_kind)
    );
    -- LASTTEST: PARTITION BY RANGE (bucket_start) oder Materialized Views.


    -- =========================================================================
    -- 8. Qualität, Stimulation, Closed Loop, Zeitbasis, Cutover
    -- =========================================================================

    -- 8a. Nachträgliche Qualitätsbewertung (A3, B7, B8), bereichsorientiert.
    CREATE TABLE quality_annotation (
        id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        measurement_channel_id  bigint NOT NULL REFERENCES measurement_channel(id),
        sample_index_range      int8range,        -- Samplebereich ...
        time_range              tstzrange,        -- ... und/oder Zeitraum
        action                  text   NOT NULL DEFAULT 'ASSERT'
                                CHECK (action IN ('ASSERT', 'REVOKE')),
        quality_code            text   REFERENCES ref_quality_code(code),
        origin                  text   NOT NULL
                                CHECK (origin IN ('INGESTION', 'ALGORITHM', 'MANUAL_REVIEW')),
        -- Herkunft DEVICE steht in sample_block.device_quality (Ebene 1),
        -- nicht hier. ANNAHME; Alternative: materialisierte Kopie mit origin
        -- 'DEVICE' für einheitliche Abfragen.
        assessed_at             timestamptz NOT NULL DEFAULT now(),
        processing_version      text,             -- Pflicht bei ALGORITHM
        assessed_by             text,             -- Pflicht bei MANUAL_REVIEW
        supersedes_annotation_id bigint REFERENCES quality_annotation(id),
        clock_sync_event_id     bigint,           -- FK unten (Auslöser TIMING_UNCERTAIN)
        note                    text,
        CHECK (sample_index_range IS NOT NULL OR time_range IS NOT NULL),
        CHECK (sample_index_range IS NULL OR NOT isempty(sample_index_range)),
        CHECK (time_range IS NULL OR NOT isempty(time_range)),
        CHECK ((action = 'ASSERT' AND quality_code IS NOT NULL)
            OR (action = 'REVOKE' AND quality_code IS NULL AND supersedes_annotation_id IS NOT NULL)),
        CHECK (origin <> 'ALGORITHM'     OR processing_version IS NOT NULL),
        CHECK (origin <> 'MANUAL_REVIEW' OR assessed_by IS NOT NULL)
    );
    CREATE INDEX quality_annotation_channel_idx
        ON quality_annotation USING gist (measurement_channel_id, sample_index_range);
    CREATE INDEX quality_annotation_channel_time
        ON quality_annotation USING gist (measurement_channel_id, time_range);
    CREATE TRIGGER quality_annotation_immutable       -- Historie geht nie verloren
        BEFORE UPDATE OR DELETE ON quality_annotation
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();
    CREATE TRIGGER quality_annotation_mapped_code
        BEFORE INSERT ON quality_annotation
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.require_mapped_quality_code();
    -- Effektive Bitmaske je Bereich: abgeleitete Sicht (Materialized View
    -- oder Job), berücksichtigt ASSERT/REVOKE-Ketten. Nicht Wahrheitsquelle.

    -- 8b. Closed Loop (v7 3.7): eigene Entscheidungsebene.
    CREATE TABLE control_decision (
        id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        acquisition_run_id   bigint NOT NULL REFERENCES acquisition_run(id),
        evaluation_logic     text   NOT NULL,
        algorithm_version    text   NOT NULL,
        decision             text   NOT NULL CHECK (decision IN ('STIMULATE', 'NO_ACTION')),
        chosen_actuator_channel_id bigint REFERENCES actuator_channel(id),
        parameters           jsonb  NOT NULL DEFAULT '{}',
        decided_at           timestamptz NOT NULL,
        CHECK (decision = 'NO_ACTION' OR chosen_actuator_channel_id IS NOT NULL),
        UNIQUE (id, acquisition_run_id)
    );
    -- Auslösende Messdaten: Kanal + Sample-/Zeitbereich, ggf. mehrere.
    CREATE TABLE control_decision_input (
        control_decision_id    bigint NOT NULL REFERENCES control_decision(id),
        measurement_channel_id bigint NOT NULL REFERENCES measurement_channel(id),
        sample_index_range     int8range,
        time_range             tstzrange,
        CHECK (sample_index_range IS NOT NULL OR time_range IS NOT NULL),
        PRIMARY KEY (control_decision_id, measurement_channel_id)
    );
    CREATE TRIGGER control_decision_immutable
        BEFORE UPDATE OR DELETE ON control_decision
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();
    CREATE TRIGGER control_decision_input_immutable
        BEFORE UPDATE OR DELETE ON control_decision_input
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();

    -- 8c. Stimulation (v7 3.6, A4).
    CREATE TABLE stimulation (
        id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        acquisition_run_id      bigint NOT NULL,
        device_configuration_id bigint NOT NULL,
        actuator_channel_id     bigint NOT NULL,
        actuator_type           text   NOT NULL,
        trigger_source          text   NOT NULL
                                CHECK (trigger_source IN ('MANUAL', 'SCHEDULED', 'CLOSED_LOOP')),
        control_decision_id     bigint,
        planned_start           timestamptz,
        -- Ausführungszustand
        execution_state         text   NOT NULL DEFAULT 'PLANNED'
                                CHECK (execution_state IN ('PLANNED', 'EXECUTED', 'PARTIAL',
                                                           'FAILED', 'CANCELLED')),
        actual_start            timestamptz,     -- Gerätezeit
        actual_duration_ms      bigint CHECK (actual_duration_ms >= 0),
        attempted_at            timestamptz,     -- nur FAILED, optional
        state_reason            text,
        state_changed_at        timestamptz NOT NULL DEFAULT now(),
        -- Ist-Start und Ist-Dauer genau bei EXECUTED und PARTIAL (Auftrag 3)
        CHECK ((execution_state IN ('EXECUTED', 'PARTIAL'))
               = (actual_start IS NOT NULL AND actual_duration_ms IS NOT NULL)),
        CHECK (execution_state IN ('EXECUTED', 'PARTIAL')
               OR (actual_start IS NULL AND actual_duration_ms IS NULL)),
        CHECK (attempted_at IS NULL OR execution_state = 'FAILED'),
        -- CLOSED_LOOP genau dann, wenn eine Entscheidung referenziert ist
        CHECK ((trigger_source = 'CLOSED_LOOP') = (control_decision_id IS NOT NULL)),
        -- Aktor gehört zur Konfiguration des Runs, Typ passt zur Parametertabelle
        FOREIGN KEY (acquisition_run_id, device_configuration_id)
            REFERENCES acquisition_run(id, device_configuration_id),
        FOREIGN KEY (actuator_channel_id, device_configuration_id)
            REFERENCES actuator_channel(id, device_configuration_id),
        FOREIGN KEY (actuator_channel_id, actuator_type)
            REFERENCES actuator_channel(id, actuator_type),
        FOREIGN KEY (control_decision_id, acquisition_run_id)
            REFERENCES control_decision(id, acquisition_run_id),
        UNIQUE (id, actuator_type),
        UNIQUE (id, acquisition_run_id)
    );
    CREATE INDEX stimulation_run_time ON stimulation (acquisition_run_id, actual_start);
    CREATE TRIGGER stimulation_fixed_columns
        BEFORE UPDATE OR DELETE ON stimulation
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification(
            'execution_state', 'actual_start', 'actual_duration_ms',
            'attempted_at', 'state_reason', 'state_changed_at');
    CREATE TRIGGER stimulation_transition
        BEFORE UPDATE ON stimulation
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.check_stimulation_transition();
    CREATE TRIGGER stimulation_not_during_ec          -- ANNAHME, siehe 2e
        BEFORE INSERT OR UPDATE ON stimulation
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_stimulation_during_ec();

    -- Soll-Parameter je Aktortyp (je eine Tabelle). Zusammengesetzter FK
    -- erzwingt, dass eine elektrische Parameterzeile nur an einer
    -- elektrischen Stimulation hängt.
    -- Dass JEDE Stimulation genau eine Parameterzeile hat, lässt sich nicht
    -- rein deklarativ ausdrücken -> Prüfung in der Ingestion bzw. als
    -- DEFERRABLE Constraint-Trigger (ANNAHME, bei Umsetzung).
    CREATE TABLE stimulation_param_electrical (
        stimulation_id   bigint PRIMARY KEY,
        actuator_type    text NOT NULL DEFAULT 'ELECTRICAL' CHECK (actuator_type = 'ELECTRICAL'),
        waveform         text NOT NULL CHECK (waveform IN
                             ('BIPHASIC_SQUARE', 'SINE', 'GAUSS_PULSE', 'RAMP')),
        amplitude        numeric NOT NULL,
        amplitude_unit   text NOT NULL REFERENCES ref_unit(code),   -- ANNAHME: V oder uA
        frequency_hz     numeric CHECK (frequency_hz >= 0),
        duration_ms      bigint NOT NULL CHECK (duration_ms > 0),
        FOREIGN KEY (stimulation_id, actuator_type) REFERENCES stimulation(id, actuator_type)
    );
    CREATE TABLE stimulation_param_optical (
        stimulation_id   bigint PRIMARY KEY,
        actuator_type    text NOT NULL DEFAULT 'OPTICAL' CHECK (actuator_type = 'OPTICAL'),
        wavelength_nm    numeric NOT NULL CHECK (wavelength_nm > 0),
        pattern          text NOT NULL CHECK (pattern IN
                             ('CONTINUOUS', 'PULSE', 'SWEEP_FADE', 'SINE_MODULATION')),
        intensity        numeric NOT NULL CHECK (intensity >= 0),
        intensity_unit   text NOT NULL REFERENCES ref_unit(code),   -- ANNAHME: '%'
        frequency_hz     numeric CHECK (frequency_hz >= 0),
        duty_cycle       numeric CHECK (duty_cycle > 0 AND duty_cycle <= 1),
                         -- ANNAHME: aus der PC-Software übernommen, v7 nennt ihn nicht
        duration_ms      bigint NOT NULL CHECK (duration_ms > 0),
        FOREIGN KEY (stimulation_id, actuator_type) REFERENCES stimulation(id, actuator_type)
    );
    CREATE TABLE stimulation_param_vibration (
        stimulation_id   bigint PRIMARY KEY,
        actuator_type    text NOT NULL DEFAULT 'VIBRATION' CHECK (actuator_type = 'VIBRATION'),
        frequency_hz     numeric NOT NULL CHECK (frequency_hz > 0),
        amplitude        numeric NOT NULL,
        amplitude_unit   text NOT NULL REFERENCES ref_unit(code),
        waveform         text NOT NULL,          -- ANNAHME: Werteliste offen
        duration_ms      bigint CHECK (duration_ms > 0),   -- ANNAHME: v7 nennt keine Dauer
        FOREIGN KEY (stimulation_id, actuator_type) REFERENCES stimulation(id, actuator_type)
    );
    CREATE TRIGGER stimulation_param_electrical_immutable
        BEFORE UPDATE OR DELETE ON stimulation_param_electrical
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();
    CREATE TRIGGER stimulation_param_optical_immutable
        BEFORE UPDATE OR DELETE ON stimulation_param_optical
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();
    CREATE TRIGGER stimulation_param_vibration_immutable
        BEFORE UPDATE OR DELETE ON stimulation_param_vibration
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();

    -- Kombinationen als Sequenz (v7 3.6). Eine Sequenz läuft nie über zwei
    -- Runs (B13): Sequenz und jedes Mitglied tragen denselben Run, per
    -- zusammengesetztem FK erzwungen.
    CREATE TABLE stimulation_sequence (
        id                    bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        acquisition_run_id    bigint NOT NULL REFERENCES acquisition_run(id),
        label                 text,
        experiment_definition jsonb NOT NULL DEFAULT '{}',   -- Versuchsdefinition
        planned_start         timestamptz,
        created_at            timestamptz NOT NULL DEFAULT now(),
        UNIQUE (id, acquisition_run_id)
    );
    CREATE TABLE stimulation_sequence_member (
        stimulation_sequence_id bigint NOT NULL,
        stimulation_id          bigint NOT NULL UNIQUE,   -- ANNAHME: höchstens eine Sequenz je Stimulation
        acquisition_run_id      bigint NOT NULL,
        planned_offset_ms       bigint NOT NULL CHECK (planned_offset_ms >= 0),
                                -- 0 = "Synchron" (Anzeige-Label), > 0 = "Versetzt"
        PRIMARY KEY (stimulation_sequence_id, stimulation_id),
        FOREIGN KEY (stimulation_sequence_id, acquisition_run_id)
            REFERENCES stimulation_sequence(id, acquisition_run_id),
        FOREIGN KEY (stimulation_id, acquisition_run_id)
            REFERENCES stimulation(id, acquisition_run_id)
    );
    CREATE TRIGGER stimulation_sequence_member_immutable
        BEFORE UPDATE OR DELETE ON stimulation_sequence_member
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();

    -- 8d. Zeitbasis (v7 3.12).
    CREATE TABLE clock_sync_event (
        id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        device_id            bigint NOT NULL,
        acquisition_run_id   bigint NOT NULL,
        reference_source     text   NOT NULL REFERENCES ref_time_source(code),
        reference_time       timestamptz NOT NULL,
        device_time          timestamptz NOT NULL,     -- Gerätezeit im selben Moment
        offset_ms            bigint GENERATED ALWAYS AS
                             ((extract(epoch FROM (reference_time - device_time)) * 1000)::bigint) STORED,
                             -- > 0: Uhr geht nach, < 0: Uhr geht vor
        correction_mode      text   NOT NULL
                             CHECK (correction_mode IN ('NONE', 'SLEW', 'STEP_FORWARD', 'RUN_BREAK')),
        applied_at           timestamptz NOT NULL,
        -- Vorwärtssprung nur bei nachgehender Uhr, Run-Bruch nur bei vorgehender
        CHECK (correction_mode <> 'STEP_FORWARD' OR reference_time > device_time),
        CHECK (correction_mode <> 'RUN_BREAK'    OR reference_time < device_time),
        FOREIGN KEY (acquisition_run_id, device_id) REFERENCES acquisition_run(id, device_id)
    );
    CREATE INDEX clock_sync_event_run ON clock_sync_event (acquisition_run_id, applied_at);
    CREATE TRIGGER clock_sync_event_immutable
        BEFORE UPDATE OR DELETE ON clock_sync_event
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();
    ALTER TABLE quality_annotation
        ADD FOREIGN KEY (clock_sync_event_id) REFERENCES clock_sync_event(id);
    -- corrected_time ist DERIVED: Abbildung measured_at -> korrigierte Zeit je
    -- Korrekturmodell-Version, berechnet (View/Job), nicht gespeichert am Sample.

    -- 8e. Cutover-Qualifikation (v7 6): Ergebnisse der Berechnung, versioniert.
    --     In beiden Schemas vorhanden (Parität; die Sandbox testet den Job).
    CREATE TABLE qualification_evaluation (
        id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        evaluated_at       timestamptz NOT NULL DEFAULT now(),
        mapping_version_id bigint NOT NULL REFERENCES coverage_mapping_version(id),
        job_version        text   NOT NULL,
        time_basis         text   NOT NULL DEFAULT 'MEASURED_AT'
                           CHECK (time_basis IN ('MEASURED_AT', 'CORRECTED_TIME')),
        forward_step_cap   interval,   -- Obergrenze B11 (C7 offen), wie verwendet
        note               text
    );
    CREATE TABLE qualification_day (
        id                         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        evaluation_id              bigint NOT NULL REFERENCES qualification_evaluation(id),
        device_id                  bigint NOT NULL REFERENCES device(id),
        site_id                    bigint NOT NULL REFERENCES site(id),
        local_date                 date   NOT NULL,
        iana_tz                    text   NOT NULL,
        day_length                 interval NOT NULL,     -- 23/24/25 h
        forward_step_excluded      interval NOT NULL DEFAULT '0',
        provenance_complete        boolean NOT NULL,
        ingestion_path_ok          boolean NOT NULL,
        critical_conflicts_open    boolean NOT NULL,
        is_usable                  boolean NOT NULL,
        fail_reasons               text[] NOT NULL DEFAULT '{}',
        UNIQUE (evaluation_id, device_id, local_date)
    );
    CREATE TABLE qualification_channel_day (
        qualification_day_id bigint NOT NULL REFERENCES qualification_day(id),
        hardware_channel_id  bigint NOT NULL REFERENCES hardware_channel(id),
        requirement          text   NOT NULL CHECK (requirement IN ('REQUIRED', 'OPTIONAL')),
        planned_time         interval NOT NULL,
        recorded_time        interval NOT NULL,
        coverage_ratio       numeric  CHECK (coverage_ratio BETWEEN 0 AND 1),
        recording_plan_ids   bigint[] NOT NULL,
        PRIMARY KEY (qualification_day_id, hardware_channel_id)
    );
    CREATE TRIGGER qualification_evaluation_immutable
        BEFORE UPDATE OR DELETE ON qualification_evaluation
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();
    CREATE TRIGGER qualification_day_immutable
        BEFORE UPDATE OR DELETE ON qualification_day
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();
    CREATE TRIGGER qualification_channel_day_immutable
        BEFORE UPDATE OR DELETE ON qualification_channel_day
        FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification();

    PERFORM set_config('search_path', v_suchpfad, true);
END
$core$;


-- -----------------------------------------------------------------------------
-- 9. Anwendung: dieselbe Quelle für beide Namespaces (Schema-Parität)
-- -----------------------------------------------------------------------------
CALL biocomm_common.create_core('sandbox');
CALL biocomm_common.create_core('live');


-- -----------------------------------------------------------------------------
-- 10. Sandbox-exklusiv (v7 4.1) und Trennungsregeln
-- -----------------------------------------------------------------------------
CREATE TABLE sandbox.sandbox_scenario (
    id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scenario_key             text    NOT NULL,        -- stabile Kennung, z. B. 'baseline'
    scenario_version         integer NOT NULL CHECK (scenario_version >= 1),
    generator_version        text    NOT NULL,
    model_assumption_version text    NOT NULL,
    label                    text    NOT NULL,
    short_description        text    NOT NULL,
    model_assumption_note    text    NOT NULL,        -- Hinweistext zu Modellannahmen (Pflicht)
    parameter_basis          text    NOT NULL CHECK (parameter_basis IN
                             ('ARBITRARY_DEMO', 'LITERATURE_INSPIRED', 'HARDWARE_BASED', 'FIELD_DERIVED')),
    -- literaturinspirierte Parameter und angenommene Reaktion getrennt (v7 4.1)
    stimulus_parameter_source text,
    response_assumption       text,
    -- feste, versionierte synthetische Jahresachse (v7 4.2)
    synthetic_year           tstzrange NOT NULL,
    is_public                boolean NOT NULL DEFAULT false,
    created_at               timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scenario_key, scenario_version)
);
CREATE TRIGGER sandbox_scenario_immutable
    BEFORE UPDATE OR DELETE ON sandbox.sandbox_scenario
    FOR EACH ROW EXECUTE FUNCTION biocomm_common.forbid_modification('is_public');
    -- ANNAHME: Versionen sind unveränderlich, nur die Sichtbarkeit darf wechseln.

-- Szenario -> Serien (nicht umgekehrt), inkl. synthetischer Kontrollreihe.
CREATE TABLE sandbox.sandbox_scenario_series (
    scenario_id bigint NOT NULL REFERENCES sandbox.sandbox_scenario(id),
    series_id   bigint NOT NULL REFERENCES sandbox.series(id),
    series_role text   NOT NULL CHECK (series_role IN ('PRIMARY', 'CONTROL')),
    PRIMARY KEY (scenario_id, series_id)
);

-- Kennzeichnung und "keine Vermischung": synthetische Kennungen tragen das
-- Präfix SBX-, Live verbietet es. ANNAHME für Geräte-/Sondenkennungen
-- (v7 nennt das Präfix nur für Sites).
ALTER TABLE sandbox.site   ADD CONSTRAINT site_code_sandbox     CHECK (site_code     LIKE 'SBX-%');
ALTER TABLE live.site      ADD CONSTRAINT site_code_not_sandbox CHECK (site_code NOT LIKE 'SBX-%');
ALTER TABLE sandbox.device ADD CONSTRAINT device_serial_sandbox     CHECK (device_serial     LIKE 'SBX-%');
ALTER TABLE live.device    ADD CONSTRAINT device_serial_not_sandbox CHECK (device_serial NOT LIKE 'SBX-%');
ALTER TABLE sandbox.probe  ADD CONSTRAINT probe_serial_sandbox     CHECK (probe_serial     LIKE 'SBX-%');
ALTER TABLE live.probe     ADD CONSTRAINT probe_serial_not_sandbox CHECK (probe_serial NOT LIKE 'SBX-%');


-- -----------------------------------------------------------------------------
-- 11. Rollen und Rechte: siehe deploy/biocomm_roles_setup.sql (Rollen, Schemas,
--     Standardrechte, root-Schritt) und migrations/sql/biocomm_0001_rechte.sql
--     (Spaltenrechte nach Anlage der Tabellen, von der Migration eingespielt).
-- Backups: pg_dump laeuft als omn_owner (pg_read_all_data), siehe deploy/.
-- =============================================================================
