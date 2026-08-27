"""
Migration fuer den Kollaborationsbereich (Aufgabenliste + Kommentare + Anhaenge).

1. Legt die neuen Tabellen an (Aufgabe, Kommentar, KollaborationAnhang) --
   db.create_all() ruehrt bestehende Tabellen nicht an.
2. Ergaenzt die Spalte foerderer.nutzer_id (nullable FK) -- create_all legt
   keine neuen Spalten an bestehenden Tabellen an.
3. Backfill: verknuepft bestehende Kooperations-Eintraege ueber E-Mail-Gleichheit
   mit dem passenden Nutzer-Account.

Aufruf: python migrate_kollaboration.py
Sicher mehrfach ausfuehrbar. Vorher DB-Backup ziehen (Schema-Aenderung).
"""
import sqlite3

from app import app
from extensions import db


def _spalte_existiert(cur, tabelle, spalte):
    cur.execute(f'PRAGMA table_info({tabelle})')
    return any(row[1] == spalte for row in cur.fetchall())


def main():
    with app.app_context():
        db.create_all()
        print('db.create_all(): neue Tabellen (falls fehlend) angelegt.')

        db_datei = db.engine.url.database
        conn = sqlite3.connect(db_datei)
        cur = conn.cursor()

        if _spalte_existiert(cur, 'foerderer', 'nutzer_id'):
            print('foerderer.nutzer_id existiert bereits — uebersprungen.')
        else:
            cur.execute('ALTER TABLE foerderer ADD COLUMN nutzer_id INTEGER')
            print('foerderer.nutzer_id hinzugefuegt.')

        cur.execute("""
            UPDATE foerderer
               SET nutzer_id = (SELECT nutzer.id FROM nutzer
                                 WHERE lower(nutzer.email) = lower(foerderer.email))
             WHERE nutzer_id IS NULL
               AND EXISTS (SELECT 1 FROM nutzer
                            WHERE lower(nutzer.email) = lower(foerderer.email))
        """)
        print(f'Backfill: {cur.rowcount} Foerderer-Zeile(n) mit Nutzer verknuepft.')

        conn.commit()
        conn.close()
    print('Fertig.')


if __name__ == '__main__':
    main()
