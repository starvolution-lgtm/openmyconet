"""BioComm Schema v2: versionierte Aggregate, Kandidatenwahl, Eingangs-Index

Entscheidungen Robby (24.09.2026) zum Bericht "Prototyp Dateneingang":
versionierte Aggregate statt eigener Rolle, Konfliktaufloesung nur mit
Kettenbeweis automatisch, sonst manuell ueber biocomm_common.kandidat_festlegen
(SECURITY DEFINER, Eigentuemer omn_owner, Protokoll nur einfuegen), Index auf
batch_delivery (transport_code, transport_hash). SQL:
migrations/sql/biocomm_0002_schema.sql (+ _rechte.sql, Rueckbau _zurueck.sql).

- Nur PostgreSQL, auf SQLite ein No-op. Die 0001-Dateien bleiben unveraendert;
  die Kern-Aenderung steht einmal in biocomm_common.core_0002 und gilt fuer
  sandbox und live (Schema-Paritaet).
- Wie 3f1b2c4d5e6a: laeuft die Migration als gewoehnliche Rolle (omn) und gibt
  es omn_owner, wird der BioComm-Teil ueber eine eigene Verbindung als
  omn_owner ausgefuehrt (Passwort aus ~/.pgpass). Dieselben Hilfsfunktionen,
  aus der 0001-Migration geladen.
- Idempotent: ist kandidat_festlegen() schon vorhanden, passiert nichts.

Revision ID: 8d4e2a6c1b70
Revises: 3f1b2c4d5e6a
Create Date: 2026-09-25 09:00:00

"""
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '8d4e2a6c1b70'
down_revision = '3f1b2c4d5e6a'
branch_labels = None
depends_on = None

SQL_DIR = Path(__file__).resolve().parent.parent / 'sql'
FUNKTION = 'biocomm_common.kandidat_festlegen(text,bigint,text,jsonb,text,text)'


def _v0001():
    """Hilfsfunktionen (Owner-Verbindung, Rollenpruefung) der 0001-Migration."""
    pfad = Path(__file__).resolve().parent / '3f1b2c4d5e6a_biocomm_schemas_sandbox_live.py'
    spec = importlib.util.spec_from_file_location('mig_biocomm_0001', pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _eingerichtet(conn):
    return conn.execute(sa.text('SELECT to_regprocedure(:f) IS NOT NULL'), {'f': FUNKTION}).scalar()


def upgrade():
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql':
        return
    v1 = _v0001()
    if not v1._eingerichtet(conn) or _eingerichtet(conn):
        return
    teile = [(SQL_DIR / 'biocomm_0002_schema.sql').read_text(encoding='utf-8')]
    if v1._rollen_da(conn):
        teile.append((SQL_DIR / 'biocomm_0002_rechte.sql').read_text(encoding='utf-8'))
    v1._ausfuehren(conn, *teile)


def downgrade():
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql' or not _eingerichtet(conn):
        return
    rest = conn.execute(sa.text(
        'SELECT (SELECT count(*) FROM live.derived_aggregate WHERE aggregate_version > 1)'
        ' + (SELECT count(*) FROM sandbox.derived_aggregate WHERE aggregate_version > 1)'
        ' + (SELECT count(*) FROM live.candidate_resolution_log)'
        ' + (SELECT count(*) FROM sandbox.candidate_resolution_log)'
        ' + (SELECT count(*) FROM live.sample_block_quarantine)'
        ' + (SELECT count(*) FROM sandbox.sample_block_quarantine)')).scalar()
    if rest:
        raise RuntimeError(f'Downgrade abgebrochen: {rest} Aggregat-Versionen > 1, Protokolleintraege bzw. Quarantaene-Bloecke '
                           'wuerden verloren gehen. Bei Bedarf von Hand sichern und entfernen.')
    _v0001()._ausfuehren(conn, (SQL_DIR / 'biocomm_0002_zurueck.sql').read_text(encoding='utf-8'))
