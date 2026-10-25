"""austausch.vorbereitet_erinnert_am

Admin-Erinnerung vor Frist F1a: ein nur vorbereiteter, nie verschickter Austausch
wird nach einem Monat geloescht (Art. 14 Abs. 3 lit. a DSGVO, Robby 25.10.2026);
vorher geht einmal eine Mail an den Admin. Die Spalte haelt fest, dass sie raus ist.
Kein Backfill. Idempotent wie ea38adc43e8d (Adoptionspfad: create_all legt die
Spalte schon an).

Revision ID: a0d6f3552d84
Revises: ea38adc43e8d
Create Date: 2026-10-25 14:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a0d6f3552d84'
down_revision = 'ea38adc43e8d'
branch_labels = None
depends_on = None


def _spalten():
    return {s['name'] for s in sa.inspect(op.get_bind()).get_columns('austausch')}


def upgrade():
    if 'vorbereitet_erinnert_am' in _spalten():
        return
    with op.batch_alter_table('austausch', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vorbereitet_erinnert_am', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    if 'vorbereitet_erinnert_am' not in _spalten():
        return
    with op.batch_alter_table('austausch', schema=None) as batch_op:
        batch_op.drop_column('vorbereitet_erinnert_am')
