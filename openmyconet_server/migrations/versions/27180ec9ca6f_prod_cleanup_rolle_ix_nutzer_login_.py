"""prod-cleanup: rolle + ix_nutzer_login_token erneut entfernen

Revision ID: 27180ec9ca6f
Revises: 966393848d7c
Create Date: 2026-09-09 12:35:00.000000

Der erste Deploy nach der Alembic-Aktivierung lief noch mit der alten
release.sh-Logik (die bereits laufende Skript-Kopie war die alte) und hat
`migrate_add_columns.py` nochmal gefahren -- das legt `nutzer.rolle` (MIGRATIONS-
Liste) UND `ix_nutzer_login_token` (hartcodiert) wieder an, wenn sie fehlen.
Auf Prod sind dadurch beide zurueckgekommen (funktional harmlos, aber tote
Spalte + redundanter Index neben dem inline-uq_nutzer_login_token).

Diese Migration raeumt beides idempotent weg. Auf Staging / frischen DBs ist
sie ein No-op. Die alten migrate_*.py werden im selben Commit geloescht, damit
das nicht nochmal passieren kann.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '27180ec9ca6f'
down_revision = '966393848d7c'
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    hat_rolle = 'rolle' in {c['name'] for c in insp.get_columns('nutzer')}
    hat_lt_index = 'ix_nutzer_login_token' in {i['name'] for i in insp.get_indexes('nutzer')}
    if not hat_rolle and not hat_lt_index:
        return

    with op.batch_alter_table('nutzer', schema=None) as batch_op:
        if hat_lt_index:
            batch_op.drop_index('ix_nutzer_login_token')
        if hat_rolle:
            batch_op.drop_column('rolle')


def downgrade():
    pass
