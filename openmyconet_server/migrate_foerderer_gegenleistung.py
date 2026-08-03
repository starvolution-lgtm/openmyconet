"""
Einmaliges Migrationsskript: fuegt die Spalte 'gegenleistung_erwartet' zur
bestehenden foerderer-Tabelle hinzu (fuer Kooperationsanfragen). Idempotent.

Aufruf: python migrate_foerderer_gegenleistung.py
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'openmyconet.db')

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("PRAGMA table_info(foerderer)")
spalten = [row[1] for row in cur.fetchall()]

if 'gegenleistung_erwartet' in spalten:
    print("Spalte 'gegenleistung_erwartet' existiert bereits -- nichts zu tun.")
else:
    cur.execute("ALTER TABLE foerderer ADD COLUMN gegenleistung_erwartet TEXT DEFAULT ''")
    conn.commit()
    print("Spalte 'gegenleistung_erwartet' hinzugefuegt.")

conn.close()
