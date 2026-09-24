#!/bin/bash
# ---------------------------------------------------------------------------
# backup_storagebox.sh -- taegliches, verschluesseltes, dedupliziertes Backup
# auf die Hetzner Storage Box (BorgBackup 1.4, als omn).
#
#   bash /home/omn/app/deploy/backup_storagebox.sh
#
# Ausgeloest vom systemd-User-Timer omn-backup-storagebox.timer (taeglich
# ~03:15, nach dem lokalen Dump um 02:30). Konfiguration: deploy/borg_common.sh.
#
# Umfang (siehe deploy/BACKUP.md, Abschnitt Storage Box):
#   - frische PostgreSQL-Dumps omn_prod + omn_staging (pg_dump -Fc -Z0: ohne
#     eigene Kompression, damit borg deduplizieren kann; borg komprimiert zstd)
#   - .env von Prod + Staging, ~/.pgpass, authorized_keys  (im Repo verschluesselt)
#   - Crontab, systemd-User-Units, lesbare nginx-Konfiguration
#   - Uploads (Prod + Staging), serververwaltete Grossmedien (mp3/pdf/png),
#     instance/ (SQLite-Rollback-Reserve, Logs)
# Nicht enthalten: Code (liegt im Git), venv, Let's-Encrypt-Zertifikate (nur
# root-lesbar, per certbot neu ausstellbar), BioComm-Rohdaten (spaeter).
#
# Aufbewahrung: 14 taeglich, 8 woechentlich, 12 monatlich.
# Fehler -> Alarm-Mail + healthchecks.io /fail (falls konfiguriert).
# ---------------------------------------------------------------------------
set -uo pipefail
HIER="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=borg_common.sh
. "$HIER/borg_common.sh"

ARBEIT=/home/omn/.cache/omn-backup-staging
LOCK=/tmp/omn-backup-storagebox.lock

fehler() {
    alarm "Storage-Box-Backup FEHLGESCHLAGEN" "$1"
    rm -rf "$ARBEIT"
    exit 1
}

exec 9>"$LOCK"
flock -n 9 || { echo "laeuft bereits -- Abbruch"; exit 0; }

konf_laden || fehler "Konfiguration fehlt ($KONF)"
command -v borg >/dev/null || fehler "borg ist nicht installiert"

umask 077
rm -rf "$ARBEIT"; mkdir -p "$ARBEIT"
echo "$(date '+%F %T')  Start Storage-Box-Backup nach $BORG_REPO"

# --- 1. Datenbank-Dumps + Metadaten -----------------------------------------
db_aus_env() { grep -E '^DATABASE_URL=' "$1" 2>/dev/null | head -1 | sed -E 's#.*/([^/?]+).*#\1#'; }
PROD_DB=$(db_aus_env /home/omn/app/.env)
STAGING_DB=$(db_aus_env /home/omn/app-staging/.env)
[ -n "$PROD_DB" ] || fehler "DATABASE_URL in /home/omn/app/.env nicht gefunden"
# Dump als omn_owner (liest dank pg_read_all_data auch die privaten
# BioComm-Koordinaten), sobald dessen Passwort in ~/.pgpass steht.
DUMP_USER=omn
grep -qE '^[^:]*:[^:]*:[^:]*:omn_owner:' "$PGPASSFILE" 2>/dev/null && DUMP_USER=omn_owner

# Generierte Sandbox-Daten nicht sichern: `flask sandbox-generieren` erzeugt sie
# jederzeit identisch neu. Struktur + Stammdaten (ref_*, substrate,
# coverage_mapping*) bleiben im Dump. pg_dump >= 17: --filter. Dieselbe Auswahl
# (sandbox_daten.sql-Bedingung unten) gilt fuer die Referenzzaehlung.
filter_fuer() {
    psql -X -h 127.0.0.1 -U "$DUMP_USER" -d "$1" -Atc \
        "SELECT 'exclude table_data ' || quote_ident(schemaname) || '.' || quote_ident(tablename)
           FROM pg_tables WHERE schemaname IN ('sandbox', 'sandbox_private')
            AND tablename NOT LIKE 'ref\_%' AND tablename NOT IN ('substrate', 'coverage_mapping', 'coverage_mapping_version')" \
        > "$ARBEIT/filter_$1.txt"
}
filter_fuer "$PROD_DB" || fehler "Filterliste fuer $PROD_DB fehlgeschlagen"
pg_dump -Fc -Z 0 -h 127.0.0.1 -U "$DUMP_USER" -d "$PROD_DB" --filter="$ARBEIT/filter_$PROD_DB.txt" \
    -f "$ARBEIT/prod.dump" || fehler "pg_dump $PROD_DB fehlgeschlagen"
N_TABS=$(pg_restore --list "$ARBEIT/prod.dump" | grep -c 'TABLE DATA' || true)
[ "$N_TABS" -ge 15 ] || fehler "prod.dump enthaelt nur $N_TABS Tabellen"
if [ -n "$STAGING_DB" ]; then
    filter_fuer "$STAGING_DB" || fehler "Filterliste fuer $STAGING_DB fehlgeschlagen"
    pg_dump -Fc -Z 0 -h 127.0.0.1 -U "$DUMP_USER" -d "$STAGING_DB" --filter="$ARBEIT/filter_$STAGING_DB.txt" \
        -f "$ARBEIT/staging.dump" || fehler "pg_dump $STAGING_DB fehlgeschlagen"
fi
# Exakte Zeilenzahlen je Tabelle direkt nach dem Dump -- Referenz fuer den
# Restore-Test (Schreibzugriffe dazwischen sind moeglich, daher dort nur Warnung).
# Ohne die nicht gesicherten Sandbox-Daten (gleiche Bedingung wie filter_fuer).
psql -h 127.0.0.1 -U "$DUMP_USER" -d "$PROD_DB" -Atq > "$ARBEIT/prod_tabellen.txt" 2>/dev/null <<'SQL' || true
SELECT format('SELECT %L || ''='' || count(*) FROM %I.%I;', t.table_schema || '.' || t.table_name, t.table_schema, t.table_name)
  FROM information_schema.tables t
 WHERE t.table_type = 'BASE TABLE' AND t.table_schema NOT IN ('pg_catalog', 'information_schema')
   AND NOT (t.table_schema IN ('sandbox', 'sandbox_private') AND t.table_name NOT LIKE 'ref\_%'
            AND t.table_name NOT IN ('substrate', 'coverage_mapping', 'coverage_mapping_version'))
 ORDER BY t.table_schema, t.table_name
\gexec
SQL
crontab -l > "$ARBEIT/crontab.txt" 2>/dev/null || true
{ borg --version; pg_dump --version; . /etc/os-release; echo "$PRETTY_NAME"; } > "$ARBEIT/versionen.txt"

# --- 2. borg create ----------------------------------------------------------
PFADE=(
    "$ARBEIT"
    /home/omn/app/.env
    /home/omn/app-staging/.env
    /home/omn/.pgpass
    /home/omn/.ssh/authorized_keys
    /home/omn/.config/systemd/user
    /home/omn/app/app/static/uploads
    /home/omn/app-staging/app/static/uploads
    /home/omn/app/instance
    /etc/nginx
)
for f in /home/omn/app/app/static/*.mp3 /home/omn/app/app/static/*.pdf \
         /home/omn/app/app/static/biocomm-bridge.png /home/omn/app/app/static/biocomm-komplett.png; do
    [ -e "$f" ] && PFADE+=("$f")
done
VORHANDEN=()
for p in "${PFADE[@]}"; do [ -e "$p" ] && VORHANDEN+=("$p"); done

borg create --stats --compression zstd,6 --exclude-caches \
    --exclude '/home/omn/app/instance/logs/*.log.*' \
    "::omn-{now:%Y-%m-%d_%H%M}" "${VORHANDEN[@]}"
RC=$?
# borg: 0 = ok, 1 = Warnung (z. B. einzelne nicht lesbare Datei in /etc/nginx), >=2 = Fehler
[ $RC -le 1 ] || fehler "borg create Exit $RC"
[ $RC -eq 0 ] || echo "WARNUNG: borg create mit Warnungen (Exit 1), Archiv trotzdem angelegt"

# --- 3. Aufbewahrung ---------------------------------------------------------
borg prune --list --glob-archives 'omn-*' \
    --keep-daily 14 --keep-weekly 8 --keep-monthly 12 || fehler "borg prune fehlgeschlagen"
borg compact || fehler "borg compact fehlgeschlagen"

rm -rf "$ARBEIT"
erfolg_melden
echo "$(date '+%F %T')  Storage-Box-Backup ok"
