"""vorwort_kenntnis: Kenntnisnahme des persoenlichen Vorworts

Neue Tabelle (timestamptz), je Konto die zuletzt bestaetigte Fassung + Zeitpunkt.
Robby, 29.10.2026 (docs/vorwort_plan.md). Idempotent.

Revision ID: e5a8c3d27f19
Revises: d9f2b6c18e47
Create Date: 2026-10-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5a8c3d27f19'
down_revision = 'd9f2b6c18e47'
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table('vorwort_kenntnis'):
        return
    op.create_table(
        'vorwort_kenntnis',
        sa.Column('nutzer_id', sa.Integer(), nullable=False),
        sa.Column('fassung', sa.String(length=20), nullable=False),
        sa.Column('gelesen_am', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['nutzer_id'], ['nutzer.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('nutzer_id'),
    )


def downgrade():
    if sa.inspect(op.get_bind()).has_table('vorwort_kenntnis'):
        op.drop_table('vorwort_kenntnis')
