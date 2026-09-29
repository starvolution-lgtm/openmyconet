"""knoten prototyp

Kennzeichnet die Knoten des alten Messwegs (/api/v1/messung) als Prototyp-/
Testknoten (Auftrag Robby 29.09.2026: der "1 aktive Knoten" der Startseite war ein
Prototyp, es gibt noch kein Messnetz). Alle bestehenden Zeilen bekommen ueber den
Server-Default TRUE -- geloescht oder sonst veraendert wird nichts. Das echte
Messnetz laeuft ueber den BioComm-Dateneingang (Schema live).

sa.true() statt autogenerate-'1': PostgreSQL lehnt einen Integer-Default fuer
boolean ab.

Revision ID: 2b6f1c9e7a30
Revises: 8f545721d47e
Create Date: 2026-09-29 13:22:42.858531

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2b6f1c9e7a30'
down_revision = '8f545721d47e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('knoten', schema=None) as batch_op:
        batch_op.add_column(sa.Column('prototyp', sa.Boolean(), server_default=sa.true(), nullable=False))


def downgrade():
    with op.batch_alter_table('knoten', schema=None) as batch_op:
        batch_op.drop_column('prototyp')
