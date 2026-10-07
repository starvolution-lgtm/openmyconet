"""kontakt_versand (Server-MCC Versandlog)

Versandlog des Server-MCC (/mcc/kontakte, omn/mcc/): je Vorstellungs-Mail ein
Eintrag mit Wiedervorlage. Reine Neu-Tabelle, kein Backfill. Loeschfrist 2 Jahre
(omn/aufbewahrung.py).

Revision ID: 4c8c3b65f64f
Revises: 2b6f1c9e7a30
Create Date: 2026-10-07 13:58:31.456524

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4c8c3b65f64f'
down_revision = '2b6f1c9e7a30'
branch_labels = None
depends_on = None


def upgrade():
    # Idempotent: auf einer DB, die schon per db.create_all() eine kontakt_versand hat
    # (Test-Adoptionspfad), nichts tun -- wie 45daf66ebcc7 (mail_queue).
    if sa.inspect(op.get_bind()).has_table('kontakt_versand'):
        return

    op.create_table('kontakt_versand',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('datum_versand', sa.Date(), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('titel', sa.String(length=60), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('sprache', sa.String(length=2), nullable=False),
    sa.Column('vorlage', sa.String(length=80), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('wiedervorlage', sa.Date(), nullable=True),
    sa.Column('nachfragen', sa.Integer(), nullable=False),
    sa.Column('erledigt_am', sa.Date(), nullable=True),
    sa.Column('versandart', sa.String(length=16), nullable=False),
    sa.Column('notiz', sa.Text(), nullable=False),
    sa.Column('letzte_aktivitaet', sa.Date(), nullable=False),
    sa.Column('angelegt_am', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('kontakt_versand', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_kontakt_versand_email'), ['email'], unique=False)
        batch_op.create_index(batch_op.f('ix_kontakt_versand_letzte_aktivitaet'), ['letzte_aktivitaet'], unique=False)
        batch_op.create_index(batch_op.f('ix_kontakt_versand_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_kontakt_versand_wiedervorlage'), ['wiedervorlage'], unique=False)



def downgrade():
    if not sa.inspect(op.get_bind()).has_table('kontakt_versand'):
        return
    with op.batch_alter_table('kontakt_versand', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_kontakt_versand_wiedervorlage'))
        batch_op.drop_index(batch_op.f('ix_kontakt_versand_status'))
        batch_op.drop_index(batch_op.f('ix_kontakt_versand_letzte_aktivitaet'))
        batch_op.drop_index(batch_op.f('ix_kontakt_versand_email'))

    op.drop_table('kontakt_versand')
