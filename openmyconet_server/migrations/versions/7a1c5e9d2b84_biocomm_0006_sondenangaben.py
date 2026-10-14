"""BioComm Schema v6: Sondenangaben (Revision, Sensormodelle) an der Sonde

Festgelegt 14.10.2026 (Robby, Claude): sonde_revision und sensormodelle sind
Eigenschaften der Sonde. Sie stehen im LAUF_START (Feld einstellungen) und
werden vom Server an probe.revision / probe.sensor_models geschrieben, nicht in
device_configuration.settings -- ein Sondentausch braucht damit keine neue
config_version. SQL: migrations/sql/biocomm_0006_schema.sql (+ _rechte.sql,
Rueckbau _zurueck.sql).

- Nur PostgreSQL, auf SQLite ein No-op. Kern-Aenderung einmal in
  biocomm_common.core_0006 fuer sandbox und live (Schema-Paritaet).
- Wie die frueheren BioComm-Migrationen: laeuft als omn, der BioComm-Teil ueber
  eine eigene Verbindung als omn_owner (Passwort aus ~/.pgpass), wenn es sie gibt.
- Idempotent: gibt es sandbox.probe.revision schon, passiert nichts.
- Haengt hinter den public-Migrationen (Kette ist linear): down_revision ist
  die zuletzt eingefuehrte Revision 4c8c3b65f64f.

Revision ID: 7a1c5e9d2b84
Revises: 4c8c3b65f64f
Create Date: 2026-10-14 12:00:00

"""
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '7a1c5e9d2b84'
down_revision = '4c8c3b65f64f'
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
    return conn.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns"
        " WHERE table_schema = 'sandbox' AND table_name = 'probe' AND column_name = 'revision')")).scalar()


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql':
        return
    v1 = _v0001()
    if not v1._eingerichtet(conn) or _eingerichtet(conn):
        return
    teile = [(SQL_DIR / 'biocomm_0006_schema.sql').read_text(encoding='utf-8')]
    if v1._rollen_da(conn):
        teile.append((SQL_DIR / 'biocomm_0006_rechte.sql').read_text(encoding='utf-8'))
    v1._ausfuehren(conn, *teile)


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql' or not _eingerichtet(conn):
        return
    rest = conn.execute(sa.text(
        'SELECT (SELECT count(*) FROM live.probe WHERE revision IS NOT NULL OR sensor_models IS NOT NULL)'
        ' + (SELECT count(*) FROM sandbox.probe WHERE revision IS NOT NULL OR sensor_models IS NOT NULL)')).scalar()
    if rest:
        raise RuntimeError(f'Downgrade abgebrochen: {rest} Sonde(n) tragen Revision oder Sensormodelle, die '
                           'verloren gehen wuerden. Bei Bedarf von Hand sichern und entfernen.')
    _v0001()._ausfuehren(conn, (SQL_DIR / 'biocomm_0006_zurueck.sql').read_text(encoding='utf-8'))
