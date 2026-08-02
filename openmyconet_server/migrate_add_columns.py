"""
Einmaliges Migrationsskript für bestehende SQLite-DBs:
fügt neue Spalten hinzu, die db.create_all() nicht nachträglich anlegt
(create_all legt nur komplett fehlende Tabellen an, keine neuen Spalten
an bereits existierenden Tabellen).

Aufruf: python migrate_add_columns.py
Sicher mehrfach ausführbar — prüft vorher, ob die Spalte schon existiert.
"""
import re
import sqlite3
import os
import unicodedata

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'openmyconet.db')

MIGRATIONS = [
    ('news', 'bild_dateiname', 'VARCHAR(255)'),
    ('news', 'untertitel', 'VARCHAR(300)'),
    ('news', 'tags', 'VARCHAR(255)'),
    ('news', 'slug', 'VARCHAR(250)'),
    ('bewerbung', 'nutzer_id', 'INTEGER'),
    ('bewerbung', 'ip', 'VARCHAR(45)'),
    ('nutzer', 'ip', 'VARCHAR(45)'),
    ('nutzer', 'fachrolle', 'VARCHAR(30)'),
    ('nutzer', 'login_token', 'VARCHAR(100)'),
    ('nutzer', 'login_token_angefordert_am', 'DATETIME'),
]

UMLAUT_MAP = {'ä': 'ae', 'ö': 'oe', 'ü': 'ue', 'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue', 'ß': 'ss'}


def slugify(text):
    for k, v in UMLAUT_MAP.items():
        text = text.replace(k, v)
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    text = re.sub(r'[^\w\s-]', '', text).strip().lower()
    text = re.sub(r'[\s_-]+', '-', text)
    return text.strip('-') or 'artikel'


def spalte_existiert(cur, tabelle, spalte):
    cur.execute(f'PRAGMA table_info({tabelle})')
    return any(row[1] == spalte for row in cur.fetchall())


def backfill_slugs(cur):
    """Vergibt fehlenden News-Einträgen einen eindeutigen Slug (aus dem Titel)."""
    cur.execute('SELECT id, titel FROM news WHERE slug IS NULL OR slug = "" ORDER BY id')
    fehlende = cur.fetchall()
    if not fehlende:
        return
    cur.execute('SELECT slug FROM news WHERE slug IS NOT NULL')
    vergeben = {row[0] for row in cur.fetchall()}
    for news_id, titel in fehlende:
        basis = slugify(titel or f'artikel-{news_id}')
        slug = basis
        i = 2
        while slug in vergeben:
            slug = f'{basis}-{i}'
            i += 1
        vergeben.add(slug)
        cur.execute('UPDATE news SET slug = ? WHERE id = ?', (slug, news_id))
        print(f'news.id={news_id} -> slug "{slug}" vergeben.')


def main():
    if not os.path.exists(DB_PATH):
        print(f'Keine DB unter {DB_PATH} gefunden — nichts zu migrieren (wird beim ersten Start neu angelegt).')
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    for tabelle, spalte, typ in MIGRATIONS:
        if spalte_existiert(cur, tabelle, spalte):
            print(f'{tabelle}.{spalte} existiert bereits — übersprungen.')
        else:
            cur.execute(f'ALTER TABLE {tabelle} ADD COLUMN {spalte} {typ}')
            print(f'{tabelle}.{spalte} hinzugefügt.')
    backfill_slugs(cur)
    # ALTER TABLE ADD COLUMN kennt in SQLite keine UNIQUE-Constraints -- Index separat anlegen,
    # damit auf bestehenden DBs dieselbe Eindeutigkeit gilt wie beim frischen db.create_all().
    cur.execute('CREATE UNIQUE INDEX IF NOT EXISTS ix_nutzer_login_token ON nutzer (login_token)')
    conn.commit()
    conn.close()

if __name__ == '__main__':
    main()
