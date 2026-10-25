"""austausch (Fachkontakte einladen, Phase 1)

Neue Tabelle `austausch` (fachlicher Austausch mit eingeladenen Fachkontakten,
docs/austausch_phase1_plan.md) und je eine Kontext-Spalte `austausch_id` an
`aufgabe` und `kommentar` (dritter Kontext des Kollaborationsbereichs neben
foerderer_id/knoten_id). Kein Backfill, bestehende Zeilen bleiben unveraendert
(austausch_id = NULL).

Idempotent wie 4c8c3b65f64f: im Test-Adoptionspfad legt db.create_all() Tabelle
und Spalten schon an, dann hier nichts doppelt anlegen. Die Fremdschluessel an
aufgabe/kommentar bekommen feste Namen, damit downgrade() sie findet.

Revision ID: ea38adc43e8d
Revises: 13bce7cc5521
Create Date: 2026-10-25 12:31:18.472472

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ea38adc43e8d'
down_revision = '13bce7cc5521'
branch_labels = None
depends_on = None


def _spalten(insp, tabelle):
    return {s['name'] for s in insp.get_columns(tabelle)}


def upgrade():
    insp = sa.inspect(op.get_bind())

    if not insp.has_table('austausch'):
        op.create_table('austausch',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('titel', sa.String(length=200), nullable=False),
        sa.Column('themenueberblick', sa.Text(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('institution', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('sprache', sa.String(length=10), nullable=False),
        sa.Column('anrede', sa.String(length=10), nullable=False),
        sa.Column('persoenliche_einleitung', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('status_geaendert_am', sa.DateTime(timezone=True), nullable=False),
        sa.Column('nutzer_id', sa.Integer(), nullable=True),
        sa.Column('linkedin_url', sa.String(length=255), nullable=True),
        sa.Column('gespraech_begonnen_am', sa.Date(), nullable=True),
        sa.Column('vorgeschichte_notiz', sa.Text(), nullable=True),
        sa.Column('einladung_token_hash', sa.String(length=64), nullable=True),
        sa.Column('einladung_gueltig_bis', sa.DateTime(timezone=True), nullable=True),
        sa.Column('eingeladen_am', sa.DateTime(timezone=True), nullable=True),
        sa.Column('eingeloest_am', sa.DateTime(timezone=True), nullable=True),
        sa.Column('code_hash', sa.String(length=64), nullable=True),
        sa.Column('code_gueltig_bis', sa.DateTime(timezone=True), nullable=True),
        sa.Column('code_fehlversuche', sa.Integer(), nullable=False),
        sa.Column('codes_angefordert', sa.Integer(), nullable=False),
        sa.Column('codes_fenster_beginn', sa.DateTime(timezone=True), nullable=True),
        sa.Column('geprueft_am', sa.DateTime(timezone=True), nullable=True),
        sa.Column('loeschsperre_bis', sa.Date(), nullable=True),
        sa.Column('loeschsperre_grund', sa.String(length=300), nullable=False),
        sa.Column('erstellt_am', sa.DateTime(timezone=True), nullable=False),
        sa.Column('letzte_aktivitaet', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['nutzer_id'], ['nutzer.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('einladung_token_hash')
        )
        with op.batch_alter_table('austausch', schema=None) as batch_op:
            batch_op.create_index(batch_op.f('ix_austausch_email'), ['email'], unique=False)
            batch_op.create_index(batch_op.f('ix_austausch_letzte_aktivitaet'), ['letzte_aktivitaet'], unique=False)
            batch_op.create_index(batch_op.f('ix_austausch_nutzer_id'), ['nutzer_id'], unique=False)
            batch_op.create_index(batch_op.f('ix_austausch_status'), ['status'], unique=False)

    for tabelle in ('aufgabe', 'kommentar'):
        if 'austausch_id' in _spalten(insp, tabelle):
            continue
        with op.batch_alter_table(tabelle, schema=None) as batch_op:
            batch_op.add_column(sa.Column('austausch_id', sa.Integer(), nullable=True))
            batch_op.create_index(batch_op.f(f'ix_{tabelle}_austausch_id'), ['austausch_id'], unique=False)
            batch_op.create_foreign_key(f'fk_{tabelle}_austausch_id', 'austausch',
                                        ['austausch_id'], ['id'], ondelete='CASCADE')


def downgrade():
    insp = sa.inspect(op.get_bind())

    for tabelle in ('kommentar', 'aufgabe'):
        if 'austausch_id' not in _spalten(insp, tabelle):
            continue
        with op.batch_alter_table(tabelle, schema=None) as batch_op:
            batch_op.drop_constraint(f'fk_{tabelle}_austausch_id', type_='foreignkey')
            batch_op.drop_index(batch_op.f(f'ix_{tabelle}_austausch_id'))
            batch_op.drop_column('austausch_id')

    if insp.has_table('austausch'):
        with op.batch_alter_table('austausch', schema=None) as batch_op:
            batch_op.drop_index(batch_op.f('ix_austausch_status'))
            batch_op.drop_index(batch_op.f('ix_austausch_nutzer_id'))
            batch_op.drop_index(batch_op.f('ix_austausch_letzte_aktivitaet'))
            batch_op.drop_index(batch_op.f('ix_austausch_email'))
        op.drop_table('austausch')
