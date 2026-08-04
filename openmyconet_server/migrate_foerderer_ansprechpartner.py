"""
Einmaliges Migrationsskript: fuegt die Spalte 'ansprechpartner' zur
bestehenden foerderer-Tabelle hinzu (Pflicht bei Kooperationsanfragen,
optional bei bezahlten Foerderer-Antraegen). Idempotent.

Aufruf: python migrate_foerderer_ansprechpartner.py
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'openmyconet.db')

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute("PRAGMA table_info(foerderer)")
spalten = [row[1] for row in cur.fetchall()]

if 'ansprechpartner' in spalten:
    print("Spalte 'ansprechpartner' existiert bereits -- nichts zu tun.")
else:
    cur.execute("ALTER TABLE foerderer ADD COLUMN ansprechpartner TEXT DEFAULT ''")
    conn.commit()
    print("Spalte 'ansprechpartner' hinzugefuegt.")

conn.close()
