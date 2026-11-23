"""Kontaktanfragen aus dem Admin beantworten: Tabelle kontakt_antwort (Robby 23.11.2026)

Neue Tabelle -> gesendet_am als timestamptz (Regel 23.09.2026). FK auf
kontaktanfrage mit ON DELETE CASCADE: Antworten verschwinden mit der Anfrage
(Loeschfrist 6 Monate nach Eingang, omn/aufbewahrung.py).
Idempotent wie 33c8e25dd93c (im Test-Adoptionspfad gibt es die Tabelle schon).

Revision ID: b7e4c2a91d35
Revises: f3b7d91a2c64
Create Date: 2026-11-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e4c2a91d35'
down_revision = 'f3b7d91a2c64'
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table('kontakt_antwort'):
        return
    op.create_table('kontakt_antwort',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('anfrage_id', sa.Integer(), nullable=False),
    sa.Column('gesendet_am', sa.DateTime(timezone=True), nullable=False),
    sa.Column('an', sa.String(length=150), nullable=False),
    sa.Column('betreff', sa.String(length=200), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('gesendet_von', sa.String(length=80), nullable=False),
    sa.ForeignKeyConstraint(['anfrage_id'], ['kontaktanfrage.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('kontakt_antwort', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_kontakt_antwort_anfrage_id'), ['anfrage_id'], unique=False)


def downgrade():
    with op.batch_alter_table('kontakt_antwort', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_kontakt_antwort_anfrage_id'))
    op.drop_table('kontakt_antwort')
