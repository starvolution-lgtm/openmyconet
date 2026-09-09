"""drop nutzer.rolle (Geisterspalte aus altem Ad-hoc-Skript)

Revision ID: 966393848d7c
Revises: 959850bfc924
Create Date: 2026-09-09 12:28:37.754986

`nutzer.rolle` (VARCHAR(20) DEFAULT 'mycelist') wurde einst von
migrate_add_columns.py angelegt, im Datenmodell aber laengst durch die
orthogonalen Flags ist_hyphist / ist_sporist ersetzt. Die Spalte existiert nur
noch physisch auf Prod/Staging und wird nirgends gelesen/geschrieben.

Diese Migration entfernt sie -- bewusst spaltengeprueft, weil frisch aus der
Baseline erzeugte DBs (Tests, CI, lokale Neuanlagen) die Spalte nie hatten und
ein bedingungsloses drop_column dort fehlschlagen wuerde.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '966393848d7c'
down_revision = '959850bfc924'
branch_labels = None
depends_on = None


def _hat_spalte(tabelle, spalte):
    inspector = sa.inspect(op.get_bind())
    return spalte in {c['name'] for c in inspector.get_columns(tabelle)}


def upgrade():
    if _hat_spalte('nutzer', 'rolle'):
        with op.batch_alter_table('nutzer', schema=None) as batch_op:
            batch_op.drop_column('rolle')


def downgrade():
    if not _hat_spalte('nutzer', 'rolle'):
        with op.batch_alter_table('nutzer', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('rolle', sa.String(length=20),
                          nullable=True, server_default='mycelist')
            )
