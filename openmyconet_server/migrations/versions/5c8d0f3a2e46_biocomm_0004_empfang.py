"""BioComm Schema v4: Zugangsschluessel fuer den Empfangsweg der Bridges

Festgelegt 26.09.2026 (Robby, Claude): Bridges liefern Pakete per HTTPS an
POST /api/v2/biocomm/paket und melden sich mit einem Schluessel je Geraet an;
gespeichert wird nur dessen SHA-256-Fingerabdruck (device_credential).
SQL: migrations/sql/biocomm_0004_schema.sql (+ _rechte.sql, Rueckbau _zurueck.sql).

- Nur PostgreSQL, auf SQLite ein No-op. Kern-Aenderung einmal in
  biocomm_common.core_0004 fuer sandbox und live (Schema-Paritaet).
- Wie die frueheren BioComm-Migrationen: laeuft als omn, der BioComm-Teil ueber
  eine eigene Verbindung als omn_owner (Passwort aus ~/.pgpass), wenn es sie gibt.
- Idempotent: gibt es sandbox.device_credential schon, passiert nichts.

Revision ID: 5c8d0f3a2e46
Revises: 4b7c9e2d1f35
Create Date: 2026-09-26 14:00:00

"""
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '5c8d0f3a2e46'
down_revision = '4b7c9e2d1f35'
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / 'sql'


def _v0001():
    """Hilfsfunktionen (Owner-Verbindung, Rollenpruefung) der 0001-Migration."""
    pfad = Path(__file__).resolve().parent / '3f1b2c4d5e6a_biocomm_schemas_sandbox_live.py'
    spec = importlib.util.spec_from_file_location('mig_biocomm_0001', pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _eingerichtet(conn):
    return conn.execute(sa.text("SELECT to_regclass('sandbox.device_credential') IS NOT NULL")).scalar()


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql':
        return
    v1 = _v0001()
    if not v1._eingerichtet(conn) or _eingerichtet(conn):
        return
    teile = [(SQL_DIR / 'biocomm_0004_schema.sql').read_text(encoding='utf-8')]
    if v1._rollen_da(conn):
        teile.append((SQL_DIR / 'biocomm_0004_rechte.sql').read_text(encoding='utf-8'))
    v1._ausfuehren(conn, *teile)


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql' or not _eingerichtet(conn):
        return
    rest = conn.execute(sa.text(
        'SELECT (SELECT count(*) FROM live.device_credential) + (SELECT count(*) FROM sandbox.device_credential)')).scalar()
    if rest:
        raise RuntimeError(f'Downgrade abgebrochen: {rest} Zugangsschluessel wuerden verloren gehen. '
                           'Bei Bedarf von Hand sichern und entfernen.')
    _v0001()._ausfuehren(conn, (SQL_DIR / 'biocomm_0004_zurueck.sql').read_text(encoding='utf-8'))
