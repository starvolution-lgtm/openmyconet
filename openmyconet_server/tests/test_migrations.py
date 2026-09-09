"""Alembic-Migrationen: laufen sauber durch und decken sich mit den Modellen.

Nutzt bewusst NICHT die `app`-Fixture aus conftest -- die legt das Schema per
`db.create_all()` an, dann wuerde `flask db upgrade` die Baseline gegen schon
existierende Tabellen fahren. Hier stattdessen eine frische, leere Temp-DB.
"""
import os
import tempfile

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import upgrade

from omn import create_app
from omn.config import TestConfig
from omn.extensions import db


@pytest.fixture()
def leere_db_app():
    fd, pfad = tempfile.mkstemp(suffix='.db')
    instance = tempfile.mkdtemp(suffix='_mig_instance')

    class _Cfg(TestConfig):
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{pfad}'

    app = create_app(_Cfg, instance_path=instance)
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()
    os.close(fd)
    os.unlink(pfad)


def test_upgrade_laeuft_bis_head(leere_db_app):
    with leere_db_app.app_context():
        upgrade()  # Baseline -> drop_nutzer_rolle, ohne Fehler
        con = db.engine.connect()
        try:
            tabellen = db.inspect(db.engine).get_table_names()
        finally:
            con.close()
    assert 'nutzer' in tabellen
    assert 'messung' in tabellen
    assert 'alembic_version' in tabellen


def test_kein_schema_drift(leere_db_app):
    """Nach `upgrade` darf autogenerate nichts mehr finden -- sonst wurde eine
    Model-Aenderung ohne zugehoerige Migration committet."""
    with leere_db_app.app_context():
        upgrade()
        with db.engine.connect() as conn:
            ctx = MigrationContext.configure(
                conn, opts={'compare_type': True, 'target_metadata': db.metadata}
            )
            diff = compare_metadata(ctx, db.metadata)

    # alembic_version steht in der DB, nicht in den Modellen -> ignorieren.
    def betrifft_alembic_version(eintrag):
        text = repr(eintrag)
        return "'alembic_version'" in text or '"alembic_version"' in text

    echte = [d for d in diff if not betrifft_alembic_version(d)]
    assert echte == [], f'Modelle weichen von der Migrations-Kette ab:\n{echte}'
