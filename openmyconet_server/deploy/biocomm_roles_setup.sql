-- =============================================================================
-- BioComm — Rollen und Rechte (Variante A: drei Datenbankrollen)
-- Stand: 23.09.2026 · Entscheidung Robby: Variante A
--
-- !!! AUF PROD UND STAGING NICHT OHNE ROBBY AUSFÜHREN !!!
-- Der Lauf auf dem Server ist ein gemeinsamer root-Schritt. Lokal gegen eine
-- Wegwerf-Instanz getestet (siehe Bericht Teil 2).
--
-- ROLLEN
--   omn_owner  besitzt alle BioComm-Schemas und -Tabellen. Nur für Migrationen
--              (Deploy). Die Web-App verbindet sich nie als omn_owner.
--   omn        bestehende App-Rolle (Web/API). Darf in sandbox/live lesen und
--              einfügen, nur Statusspalten ändern, nichts löschen, und hat
--              KEINEN Zugriff auf *_private (exakte Koordinaten).
--   omn_geo    einzige Rolle mit Zugriff auf *_private (Geokodierung,
--              Berechnung der öffentlichen Rasterzelle).
--
-- GRENZE DES SCHUTZES (ehrlich): Alle Prozesse laufen heute als Unix-User
-- omn. Liegen die Passwörter von omn_owner/omn_geo in Dateien dieses Users,
-- schützt die Trennung gegen Fehler und SQL-Injection in der Web-App, nicht
-- gegen eine vollständige Übernahme des Servers. Stärker wäre ein eigener
-- Unix-User für Geo-Prozesse und Migrationen (Frage im Bericht).
--
-- AUFRUF: NICHT direkt, sondern ueber den root-Wrapper (erzeugt die
-- Passwoerter selbst, uebergibt sie ohne Kommandozeile und traegt sie in
-- /home/omn/.pgpass ein -- kein Mensch muss sie kennen):
--   su - root -c 'bash /home/omn/app/deploy/root_biocomm_rollen.sh omn_staging'
--   (danach analog omn_prod; Rollen sind clusterweit und entstehen nur einmal.)
--
-- ABLAUF
--   Teil A: Rollen, Erweiterung, leere Schemas mit Eigentümer omn_owner,
--           Schema-Rechte, Standardrechte für künftige Tabellen.
--   Teil B: entfällt -- die Spaltenrechte vergibt die Migration 3f1b2c4d5e6a
--           selbst (migrations/sql/biocomm_0001_rechte.sql, als omn_owner).
--   Teil C: Selbstprüfung (nur wenn die Tabellen schon existieren).
--
-- REIHENFOLGE: Dieses Skript MUSS vor der Migration laufen. Läuft die Migration
-- ohne vorhandenes omn_owner, gehören die Schemas omn und die Trennung fehlt.
-- =============================================================================

\set QUIET on
\if :{?owner_pw}
\else
    \echo 'FEHLER: -v owner_pw=... fehlt'
    \quit
\endif
\if :{?geo_pw}
\else
    \echo 'FEHLER: -v geo_pw=... fehlt'
    \quit
\endif

BEGIN;

-- -----------------------------------------------------------------------------
-- Teil A1: Rollen (idempotent; bestehende Rollen und Passwörter bleiben)
-- -----------------------------------------------------------------------------
SELECT format('CREATE ROLE omn_owner LOGIN NOINHERIT NOCREATEDB NOCREATEROLE PASSWORD %L', :'owner_pw')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'omn_owner') \gexec
SELECT format('CREATE ROLE omn_geo LOGIN NOINHERIT NOCREATEDB NOCREATEROLE PASSWORD %L', :'geo_pw')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'omn_geo') \gexec

-- Sicherheitsnetz: omn darf nie Mitglied von omn_owner oder omn_geo sein
-- (Mitgliedschaft würde die Trennung aushebeln).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_auth_members m
                 JOIN pg_roles r ON r.oid = m.roleid
                 JOIN pg_roles u ON u.oid = m.member
                WHERE u.rolname = 'omn' AND r.rolname IN ('omn_owner', 'omn_geo')) THEN
        RAISE EXCEPTION 'omn ist Mitglied von omn_owner/omn_geo – Trennung wäre wirkungslos';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'omn') THEN
        RAISE EXCEPTION 'App-Rolle omn fehlt – falsche Instanz?';
    END IF;
END $$;

-- omn_owner darf in dieser Datenbank verbinden (Migrationen)
SELECT format('GRANT CONNECT ON DATABASE %I TO omn_owner, omn_geo', current_database()) \gexec

-- -----------------------------------------------------------------------------
-- Teil A2: Erweiterung (braucht den Superuser bzw. DB-Owner) und Schemas
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS biocomm_common  AUTHORIZATION omn_owner;
CREATE SCHEMA IF NOT EXISTS sandbox         AUTHORIZATION omn_owner;
CREATE SCHEMA IF NOT EXISTS live            AUTHORIZATION omn_owner;
CREATE SCHEMA IF NOT EXISTS sandbox_private AUTHORIZATION omn_owner;
CREATE SCHEMA IF NOT EXISTS live_private    AUTHORIZATION omn_owner;

-- btree_gist (EXCLUDE-Constraints) im Schema biocomm_common, nicht in public:
-- public enthält so nur Website-Tabellen (wichtig für staging_db_reset.sh).
CREATE EXTENSION IF NOT EXISTS btree_gist SCHEMA biocomm_common;

-- Backups (pg_dump in backup_db.sh / backup_storagebox.sh) laufen als
-- omn_owner und müssen alles lesen können, auch die Website-Tabellen in public
-- (gehören omn) -- aber ohne Schreibrecht dort.
-- WITH INHERIT TRUE ist nötig: omn_owner ist NOINHERIT angelegt und würde das
-- Leserecht sonst nur nach explizitem SET ROLE nutzen (lokal gefunden: pg_dump
-- als omn_owner scheiterte an public.nutzer). Gilt nur für diese Mitgliedschaft.
GRANT pg_read_all_data TO omn_owner WITH INHERIT TRUE;

-- -----------------------------------------------------------------------------
-- Teil A3: Schema-Rechte
-- -----------------------------------------------------------------------------
REVOKE ALL ON SCHEMA biocomm_common, sandbox, live, sandbox_private, live_private FROM PUBLIC;
GRANT  USAGE ON SCHEMA biocomm_common, sandbox, live TO omn, omn_geo;
GRANT  USAGE ON SCHEMA sandbox_private, live_private TO omn_geo;
-- ausdrücklich: omn bekommt auf *_private nichts
REVOKE ALL ON SCHEMA sandbox_private, live_private FROM omn;

-- -----------------------------------------------------------------------------
-- Teil A4: Standardrechte für Tabellen, die omn_owner künftig anlegt
-- -----------------------------------------------------------------------------
ALTER DEFAULT PRIVILEGES FOR ROLE omn_owner IN SCHEMA sandbox, live
    GRANT SELECT, INSERT ON TABLES TO omn;
ALTER DEFAULT PRIVILEGES FOR ROLE omn_owner IN SCHEMA sandbox, live
    GRANT SELECT ON TABLES TO omn_geo;
ALTER DEFAULT PRIVILEGES FOR ROLE omn_owner IN SCHEMA sandbox_private, live_private
    GRANT SELECT, INSERT, UPDATE ON TABLES TO omn_geo;
-- Funktionen/Prozeduren (create_core!) nicht für PUBLIC ausführbar.
-- Trigger feuern trotzdem: EXECUTE wird nur beim Anlegen des Triggers geprüft.
ALTER DEFAULT PRIVILEGES FOR ROLE omn_owner
    REVOKE EXECUTE ON ROUTINES FROM PUBLIC;

COMMIT;

-- -----------------------------------------------------------------------------
-- Teil B entfällt (Spaltenrechte setzt die Migration, siehe Kopf).
-- -----------------------------------------------------------------------------
SELECT to_regclass('live.origin_batch') IS NOT NULL AS tabellen_da \gset
\if :tabellen_da

-- -----------------------------------------------------------------------------
-- Teil C: Selbstprüfung – bricht mit Fehler ab, wenn eine Regel nicht greift
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF has_schema_privilege('omn', 'live_private', 'USAGE')
       OR has_schema_privilege('omn', 'sandbox_private', 'USAGE') THEN
        RAISE EXCEPTION 'PRÜFUNG: omn hat Zugriff auf *_private';
    END IF;
    IF has_table_privilege('omn', 'live_private.site_location_private', 'SELECT') THEN
        RAISE EXCEPTION 'PRÜFUNG: omn kann site_location_private lesen';
    END IF;
    IF NOT has_table_privilege('omn_geo', 'live_private.site_location_private', 'SELECT') THEN
        RAISE EXCEPTION 'PRÜFUNG: omn_geo kann site_location_private nicht lesen';
    END IF;
    IF has_table_privilege('omn', 'live.sample_block', 'UPDATE')
       OR has_table_privilege('omn', 'live.sample_block', 'DELETE')
       OR has_table_privilege('omn', 'live.sample_block', 'TRUNCATE') THEN
        RAISE EXCEPTION 'PRÜFUNG: omn darf sample_block ändern/löschen';
    END IF;
    IF has_column_privilege('omn', 'live.origin_batch', 'payload_hash', 'UPDATE') THEN
        RAISE EXCEPTION 'PRÜFUNG: omn darf payload_hash ändern';
    END IF;
    IF NOT has_column_privilege('omn', 'live.origin_batch', 'batch_status', 'UPDATE') THEN
        RAISE EXCEPTION 'PRÜFUNG: omn darf batch_status nicht setzen';
    END IF;
    IF has_function_privilege('omn', 'biocomm_common.create_core(text)', 'EXECUTE') THEN
        RAISE EXCEPTION 'PRÜFUNG: omn darf create_core ausführen';
    END IF;
    IF NOT has_table_privilege('omn_owner', 'public.nutzer', 'SELECT') THEN
        RAISE EXCEPTION 'PRÜFUNG: omn_owner kann public.nutzer nicht lesen (Backups!)';
    END IF;
    IF has_table_privilege('omn_owner', 'public.nutzer', 'UPDATE') THEN
        RAISE EXCEPTION 'PRÜFUNG: omn_owner darf public.nutzer ändern';
    END IF;
    RAISE NOTICE 'Rollen-Selbstprüfung bestanden';
END $$;
\else
\echo 'Hinweis: BioComm-Tabellen fehlen noch – Selbstprüfung (Teil C) übersprungen. Nach der Migration erneut ausführen.'
\endif
