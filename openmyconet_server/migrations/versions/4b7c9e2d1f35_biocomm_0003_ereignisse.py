"""BioComm Schema v3: Einsaetze der Messknoten, zurueckgestellte Anlieferungen

Festgelegt 26.09.2026 (Robby, Claude) mit den Ereignissen des Paketformats v1:
Der Node meldet sich mit LAUF_START selbst an; der Messlauf landet in der
Messreihe seines Einsatzes (device_deployment). Pakete eines bekannten Geraets,
deren Messlauf noch fehlt, warten in delivery_waiting.
SQL: migrations/sql/biocomm_0003_schema.sql (+ _rechte.sql, Rueckbau _zurueck.sql).

- Nur PostgreSQL, auf SQLite ein No-op. Kern-Aenderung einmal in
  biocomm_common.core_0003 fuer sandbox und live (Schema-Paritaet).
- Wie 3f1b2c4d5e6a/8d4e2a6c1b70: laeuft als omn, der BioComm-Teil ueber eine
  eigene Verbindung als omn_owner (Passwort aus ~/.pgpass), wenn es sie gibt.
- Idempotent: gibt es sandbox.device_deployment schon, passiert nichts.

Revision ID: 4b7c9e2d1f35
Revises: 8d4e2a6c1b70
Create Date: 2026-09-26 09:00:00

"""
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '4b7c9e2d1f35'
down_revision = '8d4e2a6c1b70'
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
    return conn.execute(sa.text("SELECT to_regclass('sandbox.device_deployment') IS NOT NULL")).scalar()


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql':
        return
    v1 = _v0001()
    if not v1._eingerichtet(conn) or _eingerichtet(conn):
        return
    teile = [(SQL_DIR / 'biocomm_0003_schema.sql').read_text(encoding='utf-8')]
    if v1._rollen_da(conn):
        teile.append((SQL_DIR / 'biocomm_0003_rechte.sql').read_text(encoding='utf-8'))
    v1._ausfuehren(conn, *teile)


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql' or not _eingerichtet(conn):
        return
    rest = conn.execute(sa.text(
        'SELECT (SELECT count(*) FROM live.device_deployment) + (SELECT count(*) FROM sandbox.device_deployment)'
        ' + (SELECT count(*) FROM live.delivery_waiting) + (SELECT count(*) FROM sandbox.delivery_waiting)')).scalar()
    if rest:
        raise RuntimeError(f'Downgrade abgebrochen: {rest} Einsaetze bzw. zurueckgestellte Anlieferungen '
                           'wuerden verloren gehen. Bei Bedarf von Hand sichern und entfernen.')
    _v0001()._ausfuehren(conn, (SQL_DIR / 'biocomm_0003_zurueck.sql').read_text(encoding='utf-8'))
