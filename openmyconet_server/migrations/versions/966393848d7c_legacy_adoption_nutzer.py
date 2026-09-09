"""nutzer an das Datenmodell angleichen (Legacy-Adoption)

Revision ID: 966393848d7c
Revises: 959850bfc924
Create Date: 2026-09-09 12:28:37.754986

Die nutzer-Tabelle ist auf Prod/Staging ueber Jahre per `ALTER TABLE ADD COLUMN`
(migrate_add_columns.py) gewachsen -- drei Abweichungen vom Datenmodell, die
diese Migration in EINEM batch-Rebuild angleicht (SQLite kann die einzelnen
ALTERs nicht):

  1. Geisterspalte `rolle VARCHAR(20) DEFAULT 'mycelist'` -- im Model laengst
     durch ist_hyphist / ist_sporist ersetzt, wird nirgends gelesen/geschrieben.
  2. `ist_hyphist` / `ist_sporist` / `keine_mails` sind NULLABLE (ADD COLUMN
     kann auf gefuellter Tabelle kein NOT NULL) -- Model: `nullable=False`.
     In der Praxis stehen ueberall 0/1 (DEFAULT 0), es gibt keine NULLs.
  3. `login_token` ist per separatem UNIQUE INDEX `ix_nutzer_login_token`
     eindeutig -- das Model erzeugt ueber `unique=True` einen inline
     UNIQUE-Constraint. Funktional identisch.

nutzer ist klein (Handvoll Zeilen), der Rebuild ist unkritisch. Frisch aus der
Baseline erzeugte DBs sind bereits konform -> No-op (spalten-/indexgeprueft).

Weitere bekannte Legacy-Abweichungen auf ANDEREN Tabellen (fehlende DB-FKs
bewerbung/foerderer, news.slug ohne UNIQUE, foerderer.ansprechpartner TEXT statt
VARCHAR(120), fehlerprotokoll.id ohne NOT NULL) bleiben bewusst unangetastet --
auf SQLite alle wirkungslos (FKs mangels PRAGMA foreign_keys=ON nicht erzwungen,
VARCHAR==TEXT, INTEGER PRIMARY KEY nie NULL) und die betroffenen Tabellen haben
echte Daten. Sie werden beim Postgres-Cutover sauber (frisches Schema aus
Baseline+Migrationen, Daten nur kopiert). Allowlist: tests/test_migrations.py.

downgrade = pass: der "messy" Vor-Alembic-Zustand ist keine Chain-Stufe. Fuer
Rollbacks gibt es das DB-Backup (deploy/backup_db.sh laeuft vor der Aktivierung).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '966393848d7c'
down_revision = '959850bfc924'
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    hat_rolle = 'rolle' in {c['name'] for c in insp.get_columns('nutzer')}
    hat_lt_index = 'ix_nutzer_login_token' in {i['name'] for i in insp.get_indexes('nutzer')}
    if not hat_rolle and not hat_lt_index:
        return  # frische Baseline-DB, schon konform

    with op.batch_alter_table('nutzer', schema=None) as batch_op:
        if hat_rolle:
            batch_op.drop_column('rolle')
        if hat_lt_index:
            batch_op.drop_index('ix_nutzer_login_token')
        batch_op.alter_column('ist_hyphist', existing_type=sa.Boolean(),
                              nullable=False, existing_server_default=sa.text('0'))
        batch_op.alter_column('ist_sporist', existing_type=sa.Boolean(),
                              nullable=False, existing_server_default=sa.text('0'))
        batch_op.alter_column('keine_mails', existing_type=sa.Boolean(),
                              nullable=False, existing_server_default=sa.text('0'))
        batch_op.create_unique_constraint('uq_nutzer_login_token', ['login_token'])


def downgrade():
    pass
