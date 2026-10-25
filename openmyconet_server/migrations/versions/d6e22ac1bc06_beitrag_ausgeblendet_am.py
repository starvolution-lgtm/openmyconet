"""beitrag.ausgeblendet_am

Zeitpunkt, zu dem der Admin einen Beitrag ausgeblendet hat. Ausgeblendete Beitraege
werden 6 Monate danach endgueltig geloescht (Robby, 25.10.2026; omn/aufbewahrung.py).
Kein Backfill (die Themenraeume sind noch nicht in Betrieb). Idempotent.

Revision ID: d6e22ac1bc06
Revises: 8be9ab181351
Create Date: 2026-10-25 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd6e22ac1bc06'
down_revision = '8be9ab181351'
branch_labels = None
depends_on = None


def _spalten():
    return {s['name'] for s in sa.inspect(op.get_bind()).get_columns('beitrag')}


def upgrade():
    if 'ausgeblendet_am' in _spalten():
        return
    with op.batch_alter_table('beitrag', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ausgeblendet_am', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f('ix_beitrag_ausgeblendet_am'), ['ausgeblendet_am'], unique=False)


def downgrade():
    if 'ausgeblendet_am' not in _spalten():
        return
    with op.batch_alter_table('beitrag', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_beitrag_ausgeblendet_am'))
        batch_op.drop_column('ausgeblendet_am')
