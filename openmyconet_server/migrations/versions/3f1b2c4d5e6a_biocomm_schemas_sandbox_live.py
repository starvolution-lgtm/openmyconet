"""BioComm-Schemas sandbox/live (Schema v1)

Legt die BioComm-Datenarchitektur an: biocomm_common (Funktionen, btree_gist),
sandbox + sandbox_private und live + live_private -- beide Kerne aus EINER
Quelle (biocomm_common.create_core, Schema-Paritaet), dazu die Sandbox-exklusiven
Szenario-Tabellen. SQL: migrations/sql/biocomm_0001_schema.sql (+ _rechte.sql).
Entwurf, Begruendungen, Regeltests: Kontrollzentrum 11_BioComm_Sandkasten/.

- Nur PostgreSQL. Auf SQLite (lokal, CI-Job backend) ein No-op.
- Keine SQLAlchemy-Modelle fuer diese Schemas: Autogenerate/Drift-Test sehen nur
  das Standardschema (include_schemas ist aus), die BioComm-Schemas bleiben
  dort bewusst unsichtbar.
- Rollentrennung (Variante A, deploy/biocomm_roles_setup.sql): existiert die
  Rolle omn_owner und laeuft die Migration als gewoehnliche Rolle (omn), wird
  der BioComm-Teil ueber eine EIGENE Verbindung als omn_owner ausgefuehrt
  (Passwort aus ~/.pgpass). omn ist bewusst kein Mitglied von omn_owner. Diese
  Verbindung committet selbststaendig; deshalb ist upgrade() idempotent.
- Idempotent: ist biocomm_common.create_core schon vorhanden (z. B. Staging,
  dessen Website-Tabellen per staging_db_reset.sh aus einem aelteren Prod-Stand
  kommen), passiert nichts.

Revision ID: 3f1b2c4d5e6a
Revises: fa5a744c1177
Create Date: 2026-09-24 12:00:00

"""
from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '3f1b2c4d5e6a'
down_revision = 'fa5a744c1177'
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / 'sql'
OWNER = 'omn_owner'
SCHEMAS = ('sandbox', 'sandbox_private', 'live', 'live_private', 'biocomm_common')


def _roh_ausfuehren(sa_conn, sql):
    """Ueber den rohen psycopg-Cursor: mehrere Anweisungen, $$-Bloecke und
    %-Zeichen (format('%I')) ohne SQLAlchemy-/Parameter-Parsing."""
    with sa_conn.connection.dbapi_connection.cursor() as cur:
        cur.execute(sql)


def _owner_verbindung_noetig(conn):
    ist_super, nutzer, owner_da = conn.execute(sa.text(
        "SELECT (SELECT rolsuper FROM pg_roles WHERE rolname = current_user),"
        " current_user,"
        " EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :o)"), {'o': OWNER}).one()
    return bool(owner_da) and not ist_super and nutzer != OWNER


def _owner_url(url):
    """Verbindungs-URL als omn_owner OHNE Passwort (libpq nimmt es aus ~/.pgpass).
    Bewusst URL.create statt url.set(password=None): set() ignoriert None und
    liesse das Passwort von omn stehen -> 'password authentication failed for
    user omn_owner' (auf Staging passiert, 2026-09-24)."""
    return sa.engine.URL.create(
        drivername=url.drivername, username=OWNER, password=None,
        host=url.host, port=url.port, database=url.database, query=url.query)


def _ausfuehren(conn, *sql_texte):
    if _owner_verbindung_noetig(conn):
        engine = sa.create_engine(_owner_url(conn.engine.url))
        try:
            with engine.begin() as owner_conn:
                for sql in sql_texte:
                    _roh_ausfuehren(owner_conn, sql)
        finally:
            engine.dispose()
    else:
        for sql in sql_texte:
            _roh_ausfuehren(conn, sql)


def _eingerichtet(conn):
    return conn.execute(sa.text(
        "SELECT to_regprocedure('biocomm_common.create_core(text)') IS NOT NULL")).scalar()


def _rollen_da(conn):
    return conn.execute(sa.text(
        "SELECT count(*) FROM pg_roles WHERE rolname IN ('omn_owner', 'omn', 'omn_geo')")).scalar() == 3


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql':
        return
    if _eingerichtet(conn):
        return
    teile = [(SQL_DIR / 'biocomm_0001_schema.sql').read_text(encoding='utf-8')]
    if _rollen_da(conn):
        teile.append((SQL_DIR / 'biocomm_0001_rechte.sql').read_text(encoding='utf-8'))
    _ausfuehren(conn, *teile)


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql' or not _eingerichtet(conn):
        return
    # Schutz: Live-Messdaten nie per Downgrade wegwerfen.
    live_daten = conn.execute(sa.text(
        "SELECT (SELECT count(*) FROM live.origin_batch) + (SELECT count(*) FROM live.sample_block)")).scalar()
    if live_daten:
        raise RuntimeError(f'Downgrade abgebrochen: live enthaelt {live_daten} Batches/Bloecke. '
                           'Schemas bei Bedarf von Hand sichern und entfernen.')
    _ausfuehren(conn, 'DROP SCHEMA IF EXISTS ' + ', '.join(SCHEMAS) + ' CASCADE')
