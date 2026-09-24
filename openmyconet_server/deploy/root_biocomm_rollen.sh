#!/bin/bash
# ---------------------------------------------------------------------------
# root_biocomm_rollen.sh -- richtet die BioComm-Datenbankrollen ein (als root).
#
#   su - root -c 'bash /home/omn/app/deploy/root_biocomm_rollen.sh omn_staging'
#   su - root -c 'bash /home/omn/app/deploy/root_biocomm_rollen.sh omn_prod'
#
# - erzeugt fuer omn_owner / omn_geo zufaellige Passwoerter (nur, wenn in
#   /home/omn/.pgpass noch kein Eintrag steht), legt die Rollen an bzw. setzt
#   das Passwort neu, und traegt es in /home/omn/.pgpass ein (Mode 600, omn).
#   Kein Mensch muss die Passwoerter kennen; sie stehen nie auf einer
#   Kommandozeile (Uebergabe per Datei, nur fuer postgres lesbar).
# - fuehrt deploy/biocomm_roles_setup.sql als postgres fuer die angegebene
#   Datenbank aus (Schemas, Rechte, btree_gist, Backup-Leserecht).
# - prueft, dass omn sich per .pgpass als omn_owner anmelden kann.
# Idempotent. MUSS vor der Migration 3f1b2c4d5e6a laufen (je Datenbank).
# ---------------------------------------------------------------------------
set -euo pipefail
umask 077   # Passwort-Dateien nie, auch nicht kurz, fuer andere lesbar
[ "$(id -u)" -eq 0 ] || { echo "Bitte als root ausfuehren (su - root)."; exit 1; }

DB="${1:-}"
case "$DB" in
    omn_prod|omn_staging) ;;
    *) echo "Aufruf: $0 omn_staging|omn_prod"; exit 2 ;;
esac

SQL=/home/omn/app/deploy/biocomm_roles_setup.sql
PGPASS=/home/omn/.pgpass
HOST=127.0.0.1
test -f "$SQL" || { echo "FEHLER: $SQL fehlt (erst deployen)"; exit 1; }
test -f "$PGPASS" || { echo "FEHLER: $PGPASS fehlt"; exit 1; }

psql_pg() { su - postgres -c "psql -X -v ON_ERROR_STOP=1 $*"; }
rolle_da() { [ "$(su - postgres -c "psql -XAtc \"SELECT 1 FROM pg_roles WHERE rolname = '$1'\"")" = "1" ]; }
pgpass_hat() { grep -qE "^[^:]*:[^:]*:[^:]*:$1:" "$PGPASS"; }

VARS=$(mktemp)
chown postgres "$VARS"; chmod 600 "$VARS"
trap 'rm -f "$VARS" "$VARS.set"' EXIT

declare -A NEU_PW=()
for rolle in omn_owner omn_geo; do
    if pgpass_hat "$rolle"; then
        pw=unbenutzt                                  # Rolle + Passwort schon eingerichtet
    else
        pw=$(openssl rand -hex 24)
        NEU_PW[$rolle]=$pw
        if rolle_da "$rolle"; then                    # Rolle da, Passwort unbekannt -> neu setzen
            printf "ALTER ROLE %s PASSWORD '%s';\n" "$rolle" "$pw" > "$VARS"
            psql_pg -q -f "$VARS"
            echo "Passwort fuer bestehende Rolle $rolle neu gesetzt"
        fi
    fi
    kurz=${rolle#omn_}
    printf "\\\\set %s_pw '%s'\n" "$kurz" "$pw" >> "$VARS.set"
done
# owner_pw / geo_pw fuer biocomm_roles_setup.sql
mv "$VARS.set" "$VARS"; chown postgres "$VARS"; chmod 600 "$VARS"

echo "=== biocomm_roles_setup.sql fuer $DB"
psql_pg -d "$DB" -f "$VARS" -f "$SQL"

for rolle in "${!NEU_PW[@]}"; do
    printf '%s:5432:*:%s:%s\n' "$HOST" "$rolle" "${NEU_PW[$rolle]}" >> "$PGPASS"
    echo "in $PGPASS eingetragen: $rolle"
done
chown omn:omn "$PGPASS"; chmod 600 "$PGPASS"

echo "=== Anmeldetest als omn_owner (per .pgpass)"
su - omn -c "psql -X -h $HOST -U omn_owner -d $DB -Atc 'SELECT current_user'"
su - postgres -c "psql -XAtc \"SELECT 'omn_owner hat pg_read_all_data: ' || pg_has_role('omn_owner', 'pg_read_all_data', 'MEMBER')\""
echo "Fertig. Jetzt die Migration deployen (Staging: deploy_staging.sh, Prod: release.sh)."
