"""Gibt das komplette SQLite-Schema (Tabellen + Indizes) aus -- fuer den
Abgleich gegen die Alembic-Baseline vor einem `flask db stamp`, spaeter auch
fuer die Schema-Parity-Pruefung beim Postgres-Cutover.

Aufruf auf dem Server:  cd /home/omn/app && venv/bin/python deploy/schema_dump.py
Reiner Lesezugriff, ruehrt die DB nicht an.
"""
import os
import sqlite3
import sys

DB = os.path.join(os.path.dirname(__file__), '..', 'instance', 'openmyconet.db')

if not os.path.exists(DB):
    sys.exit(f'Keine DB unter {DB}')

con = sqlite3.connect(DB)

print('=== sqlite_master (CREATE TABLE / CREATE INDEX) ===')
for typ, name, sql in con.execute(
    "SELECT type, name, sql FROM sqlite_master "
    "WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' "
    "ORDER BY type, name"
):
    print(f'\n-- {typ} {name}')
    print(sql.strip() + ';')

print('\n=== PRAGMA table_info je Tabelle (Name | Typ | notnull | default | pk) ===')
for (tab,) in con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' "
    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
):
    print(f'\n-- {tab}')
    for _cid, cname, ctype, notnull, dflt, pk in con.execute(f'PRAGMA table_info("{tab}")'):
        print(f'   {cname:<28} {ctype:<14} notnull={notnull} default={dflt!r} pk={pk}')

print('\n=== alembic_version ===')
try:
    rows = list(con.execute('SELECT version_num FROM alembic_version'))
    print(rows or '(leer)')
except sqlite3.OperationalError:
    print('(Tabelle existiert nicht -- DB noch nicht unter Alembic)')

con.close()
