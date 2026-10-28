"""Themenraeume: Benachrichtigungen ueber neue Beitraege

Neue Tabelle themen_abo (wer welcher Diskussion folgt, gesehen/benachrichtigt fuer
die Drosselung; timestamptz) und themen_teilnahme.benachrichtigungen (Standard an).
Robby, 28.10.2026. Idempotent.

Revision ID: d9f2b6c18e47
Revises: c3e8a1f47b62
Create Date: 2026-10-28 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd9f2b6c18e47'
down_revision = 'c3e8a1f47b62'
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    if not insp.has_table('themen_abo'):
        op.create_table(
            'themen_abo',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('nutzer_id', sa.Integer(), nullable=False),
            sa.Column('diskussion_id', sa.Integer(), nullable=False),
            sa.Column('aktiv', sa.Boolean(), nullable=False),
            sa.Column('gesehen_am', sa.DateTime(timezone=True), nullable=True),
            sa.Column('benachrichtigt_am', sa.DateTime(timezone=True), nullable=True),
            sa.Column('erstellt_am', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['diskussion_id'], ['diskussion.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['nutzer_id'], ['nutzer.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('nutzer_id', 'diskussion_id', name='uq_themen_abo'),
        )
        with op.batch_alter_table('themen_abo', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_themen_abo_diskussion_id'), ['diskussion_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_themen_abo_nutzer_id'), ['nutzer_id'], unique=False)
    if 'benachrichtigungen' not in {s['name'] for s in insp.get_columns('themen_teilnahme')}:
        with op.batch_alter_table('themen_teilnahme', schema=None) as batch_op:
            batch_op.add_column(sa.Column('benachrichtigungen', sa.Boolean(), server_default=sa.true(),
                                          nullable=False))


def downgrade():
    insp = sa.inspect(op.get_bind())
    if 'benachrichtigungen' in {s['name'] for s in insp.get_columns('themen_teilnahme')}:
        with op.batch_alter_table('themen_teilnahme', schema=None) as batch_op:
            batch_op.drop_column('benachrichtigungen')
    if insp.has_table('themen_abo'):
        op.drop_table('themen_abo')
