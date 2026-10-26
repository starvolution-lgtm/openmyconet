"""austausch: Aufgaben-Schalter + Start-Themenraum

austausch.aufgaben_aktiv (Standard false: der Austausch zeigt nur noch vertrauliche
Nachrichten + Dateien; vorhandene Aufgaben bleiben gespeichert, je Austausch im Admin
wieder einschaltbar) und austausch.start_gebiet_id / start_diskussion_id (Ziel nach
dem Login, bewusst ohne Fremdschluessel). Robby, 26.10.2026. Idempotent.

Revision ID: c3e8a1f47b62
Revises: b7c41e2d9a05
Create Date: 2026-10-26 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3e8a1f47b62'
down_revision = 'b7c41e2d9a05'
branch_labels = None
depends_on = None


def _spalten():
    return {s['name'] for s in sa.inspect(op.get_bind()).get_columns('austausch')}


def upgrade():
    vorhanden = _spalten()
    with op.batch_alter_table('austausch', schema=None) as batch_op:
        if 'aufgaben_aktiv' not in vorhanden:
            batch_op.add_column(sa.Column('aufgaben_aktiv', sa.Boolean(), server_default=sa.false(), nullable=False))
        if 'start_gebiet_id' not in vorhanden:
            batch_op.add_column(sa.Column('start_gebiet_id', sa.Integer(), nullable=True))
        if 'start_diskussion_id' not in vorhanden:
            batch_op.add_column(sa.Column('start_diskussion_id', sa.Integer(), nullable=True))


def downgrade():
    vorhanden = _spalten()
    with op.batch_alter_table('austausch', schema=None) as batch_op:
        for spalte in ('start_diskussion_id', 'start_gebiet_id', 'aufgaben_aktiv'):
            if spalte in vorhanden:
                batch_op.drop_column(spalte)
