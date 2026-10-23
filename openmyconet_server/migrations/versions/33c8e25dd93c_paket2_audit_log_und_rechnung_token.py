"""Sicherheitsdurchsicht Paket 2 (23.10.2026): Audit-Log, Rechnungs-Schluessel, Messung-API aus

- admin_audit: neue Tabelle (Zeitpunkt timestamptz, Regel 23.09.2026), siehe
  omn/admin/audit.py.
- foerderer.rechnung_token: eigener Schluessel fuer den Rechnungs-Download (vorher
  diente das PayPal-`custom`-Token zugleich als Download-Schluessel). Backfill fuer
  alle Zeilen mit Rechnungsnummer, damit alte Mail-Links (?nr=&token=) weiter gehen.
- knoten.api_key geleert: /api/v1/messung ist abgeschaltet, die alten Schluessel
  sollen auch nirgends mehr angezeigt oder angenommen werden. Spalte bleibt (vorerst).

Revision ID: 33c8e25dd93c
Revises: 7a1c5e9d2b84
Create Date: 2026-10-23 10:27:22.618333

"""
import secrets

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = '33c8e25dd93c'
down_revision = '7a1c5e9d2b84'
branch_labels = None
depends_on = None


def upgrade():
    # Idempotent wie 45daf66ebcc7: im Test-Adoptionspfad (db.create_all() vor
    # stamp/upgrade) gibt es Tabelle und Spalte schon.
    insp = sa.inspect(op.get_bind())
    if not insp.has_table('admin_audit'):
        _audit_anlegen()
    if 'rechnung_token' not in {c['name'] for c in insp.get_columns('foerderer')}:
        with op.batch_alter_table('foerderer', schema=None) as batch_op:
            batch_op.add_column(sa.Column('rechnung_token', sa.String(length=64), nullable=True))
            batch_op.create_unique_constraint('uq_foerderer_rechnung_token', ['rechnung_token'])

    conn = op.get_bind()
    ids = conn.execute(sa.text(
        "SELECT id FROM foerderer WHERE rechnung_nr IS NOT NULL AND rechnung_nr <> '' AND rechnung_token IS NULL"
    )).scalars().all()
    for fid in ids:
        conn.execute(sa.text('UPDATE foerderer SET rechnung_token = :t WHERE id = :i'),
                     {'t': secrets.token_urlsafe(32), 'i': fid})
    op.execute('UPDATE knoten SET api_key = NULL')


def _audit_anlegen():
    op.create_table('admin_audit',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('zeitpunkt', sa.DateTime(timezone=True), nullable=False),
    sa.Column('admin_user_id', sa.Integer(), nullable=True),
    sa.Column('benutzername', sa.String(length=80), nullable=False),
    sa.Column('aktion', sa.String(length=40), nullable=False),
    sa.Column('ziel', sa.String(length=200), nullable=False),
    sa.Column('ip', sa.String(length=45), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('admin_audit', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_admin_audit_admin_user_id'), ['admin_user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_admin_audit_aktion'), ['aktion'], unique=False)
        batch_op.create_index(batch_op.f('ix_admin_audit_zeitpunkt'), ['zeitpunkt'], unique=False)


def downgrade():
    # Die geleerten knoten.api_key kommen nicht zurueck (gewollt).
    with op.batch_alter_table('foerderer', schema=None) as batch_op:
        batch_op.drop_constraint('uq_foerderer_rechnung_token', type_='unique')
        batch_op.drop_column('rechnung_token')

    with op.batch_alter_table('admin_audit', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_admin_audit_zeitpunkt'))
        batch_op.drop_index(batch_op.f('ix_admin_audit_aktion'))
        batch_op.drop_index(batch_op.f('ix_admin_audit_admin_user_id'))

    op.drop_table('admin_audit')

