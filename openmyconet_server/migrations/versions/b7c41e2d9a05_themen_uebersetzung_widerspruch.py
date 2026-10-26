"""Themenraeume: Widerspruch gegen die automatische Uebersetzung

themen_teilnahme.nicht_uebersetzen (Einstellung der Person) und je Inhalt
themengebiet/diskussion/beitrag.uebersetzen (beim Anlegen aus der Einstellung
uebernommen, bei Aenderung der Einstellung fuer alle eigenen Inhalte gesetzt).
Je Inhalt, damit der Widerspruch auch nach einer Kontoloeschung gilt (Beitraege
bleiben dann ohne Namen stehen). Robby, 26.10.2026 (E1). Bestehende Zeilen:
uebersetzen = true, nicht_uebersetzen = false. Idempotent.

Revision ID: b7c41e2d9a05
Revises: d6e22ac1bc06
Create Date: 2026-10-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c41e2d9a05'
down_revision = 'd6e22ac1bc06'
branch_labels = None
depends_on = None

SPALTEN = {
    'themen_teilnahme': ('nicht_uebersetzen', sa.false()),
    'themengebiet': ('uebersetzen', sa.true()),
    'diskussion': ('uebersetzen', sa.true()),
    'beitrag': ('uebersetzen', sa.true()),
}


def _spalten(tabelle):
    return {s['name'] for s in sa.inspect(op.get_bind()).get_columns(tabelle)}


def upgrade():
    for tabelle, (spalte, standard) in SPALTEN.items():
        if spalte in _spalten(tabelle):
            continue
        with op.batch_alter_table(tabelle, schema=None) as batch_op:
            batch_op.add_column(sa.Column(spalte, sa.Boolean(), server_default=standard, nullable=False))


def downgrade():
    for tabelle, (spalte, _standard) in SPALTEN.items():
        if spalte not in _spalten(tabelle):
            continue
        with op.batch_alter_table(tabelle, schema=None) as batch_op:
            batch_op.drop_column(spalte)
