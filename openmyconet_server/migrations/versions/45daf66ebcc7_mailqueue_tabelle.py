"""mailqueue tabelle

Durable Warteschlange fuer Rund-Mails (Newsletter, News-Benachrichtigung) --
ersetzt den fluechtigen Daemon-Thread in omn/mailer.py. Reine Neu-Tabelle,
kein Backfill.

Revision ID: 45daf66ebcc7
Revises: 27180ec9ca6f
Create Date: 2026-09-09 18:25:37.191393

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '45daf66ebcc7'
down_revision = '27180ec9ca6f'
branch_labels = None
depends_on = None


def upgrade():
    # Idempotent: auf einer DB, die schon per db.create_all() eine mail_queue hat
    # (Test-Adoptionspfad, alte manuelle Anlage), nichts tun.
    if sa.inspect(op.get_bind()).has_table('mail_queue'):
        return

    op.create_table('mail_queue',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('empfaenger', sa.String(length=255), nullable=False),
    sa.Column('betreff', sa.String(length=300), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('html', sa.Text(), nullable=True),
    sa.Column('header_json', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=10), nullable=False),
    sa.Column('versuche', sa.Integer(), nullable=False),
    sa.Column('letzter_fehler', sa.String(length=500), nullable=True),
    sa.Column('erstellt_am', sa.DateTime(), nullable=False),
    sa.Column('claim_am', sa.DateTime(), nullable=True),
    sa.Column('gesendet_am', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('mail_queue', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_mail_queue_erstellt_am'), ['erstellt_am'], unique=False)
        batch_op.create_index(batch_op.f('ix_mail_queue_status'), ['status'], unique=False)


def downgrade():
    if not sa.inspect(op.get_bind()).has_table('mail_queue'):
        return
    with op.batch_alter_table('mail_queue', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_mail_queue_status'))
        batch_op.drop_index(batch_op.f('ix_mail_queue_erstellt_am'))

    op.drop_table('mail_queue')