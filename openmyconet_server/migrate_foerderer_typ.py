"""
Einmaliges Migrationsskript: fuegt die Spalte 'typ' zur bestehenden foerderer-Tabelle
hinzu (db.create_all() legt nur fehlende Tabellen an, aendert aber keine bestehenden).
Idempotent -- kann gefahrlos mehrfach ausgefuehrt werden.

Aufruf: python migrate_foerderer_typ.py
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'openmyconet.db')

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("PRAGMA table_info(foerderer)")
spalten = [row[1] for row in cur.fetchall()]

if 'typ' in spalten:
    print("Spalte 'typ' existiert bereits -- nichts zu tun.")
else:
    cur.execute("ALTER TABLE foerderer ADD COLUMN typ VARCHAR(20) DEFAULT 'foerderer'")
    cur.execute("UPDATE foerderer SET typ = 'foerderer' WHERE typ IS NULL")
    conn.commit()
    print("Spalte 'typ' hinzugefuegt.")

conn.close()
