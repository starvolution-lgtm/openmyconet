"""
cleanup_content_blocks_index.py -- Einmaliges Aufraeum-Skript.

Loescht alle ContentBlock-Zeilen mit schluessel LIKE 'index_%'. Diese wurden
per seed_content_index.py angelegt und ueber applyContentBlocks() (index.html)
zur Laufzeit ueber den servergerenderten translations.json-Text gelegt.

Der Mechanismus wurde am 25.08.2026 aus index.html entfernt (siehe
CONTENT_BLOCKS.md) -- translations.json ist jetzt die einzige Textquelle
fuer die Startseite. Diese Zeilen sind seitdem funktionslos, das Skript
raeumt sie auf, damit niemand spaeter in der DB auf veraltete Texte stoesst.

Aufruf: python cleanup_content_blocks_index.py
Sicher mehrfach ausfuehrbar -- loescht nur, wenn noch Zeilen vorhanden sind.
"""
from app import app
from extensions import db
from models import ContentBlock

with app.app_context():
    treffer = ContentBlock.query.filter(ContentBlock.schluessel.like('index_%')).all()
    anzahl = len(treffer)
    for row in treffer:
        db.session.delete(row)
    db.session.commit()
    print(f'{anzahl} ContentBlock-Zeilen mit Praefix "index_" geloescht.')
