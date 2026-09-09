from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
mail = Mail()
migrate = Migrate()


@event.listens_for(Engine, 'connect')
def _sqlite_pragmas(dbapi_connection, connection_record):
    """Pro SQLite-Verbindung: WAL-Modus (Leser blockieren den Writer nicht mehr
    und umgekehrt) + NORMAL-Sync (mit WAL absturzsicher, aber deutlich schneller)
    + 15 s Busy-Timeout. journal_mode=WAL ist eine dauerhafte Eigenschaft der
    Datei; die anderen Pragmas gelten pro Verbindung und werden hier neu gesetzt.

    Liegt hier (nicht in app.py), weil das @event.listens_for global an die
    SQLAlchemy-Engine-Klasse bindet und genau einmal registriert werden muss --
    extensions wird als Modul-Singleton genau einmal importiert.

    ACHTUNG Backup: Im WAL-Modus stecken die juengsten Transaktionen ggf. noch in
    der -wal-Datei neben openmyconet.db. Vor `cp`-Backups einen Checkpoint fahren
    (siehe CLAUDE.md, Deployment) oder openmyconet.db + -wal + -shm zusammen sichern.
    """
    cur = dbapi_connection.cursor()
    cur.execute('PRAGMA journal_mode=WAL')
    cur.execute('PRAGMA synchronous=NORMAL')
    cur.execute('PRAGMA busy_timeout=15000')
    cur.close()
