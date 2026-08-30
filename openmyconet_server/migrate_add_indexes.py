"""
Einmaliges Migrationsskript: legt auf einer bestehenden SQLite-DB die Indizes an,
die neu per index=True / __table_args__ in models.py definiert wurden.

db.create_all() legt Indizes nur bei komplett neuen Tabellen an -- fuer schon
existierende Tabellen muessen sie per CREATE INDEX nachgezogen werden.

Aufruf:  venv/bin/python migrate_add_indexes.py   (bzw. venv/Scripts/python.exe)
Sicher mehrfach ausfuehrbar (CREATE INDEX IF NOT EXISTS). Reiner Lesezugriffs-
Beschleuniger -- aendert keine Daten, kein Backup zwingend noetig.

Die Indexnamen sind identisch mit denen, die SQLAlchemy beim frischen
db.create_all() vergibt (ix_<tabelle>_<spalte>), damit beide Wege dasselbe
Schema ergeben.
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'openmyconet.db')

# (Indexname, Tabelle, Spalten-SQL)
INDIZES = [
    ('ix_knoten_nutzer_id',                'knoten',              'nutzer_id'),
    ('ix_bewerbung_status',                'bewerbung',           'status'),
    ('ix_bewerbung_nutzer_id',             'bewerbung',           'nutzer_id'),
    ('ix_messung_knoten_zeit',             'messung',             'knoten_id, zeitstempel'),
    ('ix_news_veroeffentlicht',            'news',                'veroeffentlicht'),
    ('ix_chat_log_erstellt_am',            'chat_log',            'erstellt_am'),
    ('ix_foerderer_status',                'foerderer',           'status'),
    ('ix_foerderer_nutzer_id',             'foerderer',           'nutzer_id'),
    ('ix_presseeintrag_veroeffentlicht',   'presseeintrag',       'veroeffentlicht'),
    ('ix_pressekandidat_status',           'pressekandidat',      'status'),
    ('ix_aufgabe_foerderer_id',            'aufgabe',             'foerderer_id'),
    ('ix_aufgabe_knoten_id',               'aufgabe',             'knoten_id'),
    ('ix_kommentar_foerderer_id',          'kommentar',           'foerderer_id'),
    ('ix_kommentar_knoten_id',             'kommentar',           'knoten_id'),
    ('ix_kommentar_aufgabe_id',            'kommentar',           'aufgabe_id'),
    ('ix_kollaboration_anhang_kommentar_id', 'kollaboration_anhang', 'kommentar_id'),
]


def tabelle_existiert(cur, tabelle):
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (tabelle,))
    return cur.fetchone() is not None


def main():
    if not os.path.exists(DB_PATH):
        print(f'Keine DB unter {DB_PATH} — nichts zu migrieren (db.create_all() legt die Indizes beim ersten Start an).')
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for name, tabelle, spalten in INDIZES:
        if not tabelle_existiert(cur, tabelle):
            print(f'{name}: Tabelle "{tabelle}" fehlt — uebersprungen.')
            continue
        cur.execute(f'CREATE INDEX IF NOT EXISTS {name} ON {tabelle} ({spalten})')
        print(f'{name} ON {tabelle} ({spalten}) — ok.')
    conn.commit()
    cur.execute('ANALYZE')  # aktualisiert die Query-Planner-Statistiken
    conn.commit()
    conn.close()
    print('Fertig.')


if __name__ == '__main__':
    main()
