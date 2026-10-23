"""foerderer.bezahlt_am: Rechnung erst bei der Freigabe (23.10.2026)

Seit 23.10.2026 vergibt die PayPal-IPN keine Rechnungsnummer mehr; die Rechnung
entsteht bei der Admin-Freigabe (omn/foerderer.py::rechnung_ausstellen). Damit das
Zahlungsdatum auf der Rechnung stimmt, wird es beim Zahlungseingang festgehalten.

Backfill: Eintraege, die gerade auf Freigabe warten (zahlung_eingegangen), haben
status_geaendert_am = Zeitpunkt der IPN. Bei schon freigegebenen Eintraegen ist der
Zahlungszeitpunkt nicht mehr sicher bekannt -> NULL (PDF schreibt dann nur
"Bezahlt via PayPal."; deren Rechnung liegt ohnehin schon vor).
Idempotent wie 45daf66ebcc7 (Test-Adoptionspfad legt die Spalte per create_all an).

Revision ID: 13bce7cc5521
Revises: 33c8e25dd93c
Create Date: 2026-10-23 10:54:13.451324

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '13bce7cc5521'
down_revision = '33c8e25dd93c'
branch_labels = None
depends_on = None


def upgrade():
    if 'bezahlt_am' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('foerderer')}:
        with op.batch_alter_table('foerderer', schema=None) as batch_op:
            batch_op.add_column(sa.Column('bezahlt_am', sa.DateTime(), nullable=True))
    op.execute("UPDATE foerderer SET bezahlt_am = status_geaendert_am "
               "WHERE status = 'zahlung_eingegangen' AND bezahlt_am IS NULL")


def downgrade():
    with op.batch_alter_table('foerderer', schema=None) as batch_op:
        batch_op.drop_column('bezahlt_am')
