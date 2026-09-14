"""kontaktanfrage tabelle

Revision ID: 1e00d5c30c69
Revises: 45daf66ebcc7
Create Date: 2026-09-14 12:09:15.591822

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1e00d5c30c69'
down_revision = '45daf66ebcc7'
branch_labels = None
depends_on = None


def upgrade():
    # Idempotent: auf einer DB, die schon per db.create_all() eine kontaktanfrage
    # hat (Test-Adoptionspfad, alte manuelle Anlage), nichts tun -- siehe
    # 45daf66ebcc7 (mailqueue) fuer dasselbe Muster.
    if sa.inspect(op.get_bind()).has_table('kontaktanfrage'):
        return

    op.create_table('kontaktanfrage',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=True),
    sa.Column('email', sa.String(length=150), nullable=False),
    sa.Column('telefon', sa.String(length=30), nullable=True),
    sa.Column('anliegen', sa.String(length=50), nullable=False),
    sa.Column('nachricht', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('erstellt_am', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('kontaktanfrage', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_kontaktanfrage_status'), ['status'], unique=False)


def downgrade():
    if not sa.inspect(op.get_bind()).has_table('kontaktanfrage'):
        return
    with op.batch_alter_table('kontaktanfrage', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_kontaktanfrage_status'))

    op.drop_table('kontaktanfrage')
