"""Alembic-Migrationen: laufen sauber durch und decken sich mit den Modellen.

Nutzt bewusst NICHT die `app`-Fixture aus conftest -- die legt das Schema per
`db.create_all()` an, dann wuerde `flask db upgrade` die Baseline gegen schon
existierende Tabellen fahren. Hier stattdessen eine frische, leere Temp-DB.
"""
import os
import re
import sqlite3
import tempfile

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, stamp, upgrade

from omn import create_app
from omn.config import TestConfig
from omn.extensions import db

BASELINE_REV = '959850bfc924'
BIOCOMM_REV = '3f1b2c4d5e6a'
HEAD_REV = '5c8d0f3a2e46'
BIOCOMM_VORHER = 'fa5a744c1177'
BIOCOMM_SCHEMAS = ('sandbox', 'sandbox_private', 'live', 'live_private', 'biocomm_common')
REGELN_SQL = os.path.join(os.path.dirname(__file__), 'sql', 'biocomm_regeln.sql')

# nutzer-Tabelle so, wie sie ueber Jahre per ALTER TABLE ADD COLUMN auf
# Prod/Staging gewachsen ist. Plus die weiteren Legacy-Quirks anderer Tabellen
# (fehlende DB-FKs, news.slug ohne UNIQUE, ansprechpartner TEXT,
# fehlerprotokoll.id ohne NOT NULL) -- siehe LEGACY_DRIFT.
_LEGACY_SCHEMA = """
CREATE TABLE nutzer (
    id INTEGER NOT NULL, name VARCHAR(100) NOT NULL, email VARCHAR(150) NOT NULL,
    sprache VARCHAR(10), land VARCHAR(100), gruppe VARCHAR(50), bestaetigt BOOLEAN,
    token VARCHAR(100), registriert_am DATETIME, ip VARCHAR(45), fachrolle VARCHAR(30),
    login_token VARCHAR(100), login_token_angefordert_am DATETIME,
    rolle VARCHAR(20) DEFAULT 'mycelist',
    ist_hyphist BOOLEAN DEFAULT 0, ist_sporist BOOLEAN DEFAULT 0, keine_mails BOOLEAN DEFAULT 0,
    PRIMARY KEY (id), UNIQUE (email), UNIQUE (token)
);
CREATE UNIQUE INDEX ix_nutzer_login_token ON nutzer (login_token);
CREATE TABLE bewerbung (
    id INTEGER NOT NULL, name VARCHAR(100), email VARCHAR(150) NOT NULL,
    rolle VARCHAR(50), profession VARCHAR(200), substrat VARCHAR(200), adresse VARCHAR(300),
    lat FLOAT, lon FLOAT, motivation TEXT, sprache VARCHAR(10), status VARCHAR(20),
    erstellt_am DATETIME, nutzer_id INTEGER, ip VARCHAR(45),
    PRIMARY KEY (id)
);
CREATE INDEX ix_bewerbung_status ON bewerbung (status);
CREATE INDEX ix_bewerbung_nutzer_id ON bewerbung (nutzer_id);
CREATE TABLE foerderer (
    id INTEGER NOT NULL, token VARCHAR(64) NOT NULL, status VARCHAR(20),
    firma VARCHAR(120) NOT NULL, beschreibung TEXT NOT NULL, website VARCHAR(255),
    kategorie VARCHAR(80), email VARCHAR(180) NOT NULL, betrag FLOAT, logo_datei VARCHAR(255),
    paypal_txn_id VARCHAR(128), rechnung_nr VARCHAR(32), erstellt_am DATETIME, aktiviert_am DATETIME,
    laeuft_ab_am DATE, typ VARCHAR(20) DEFAULT 'foerderer', gegenleistung_erwartet TEXT DEFAULT '',
    ansprechpartner TEXT DEFAULT '', status_geaendert_am DATETIME, nutzer_id INTEGER,
    PRIMARY KEY (id), UNIQUE (token)
);
CREATE INDEX ix_foerderer_status ON foerderer (status);
CREATE INDEX ix_foerderer_nutzer_id ON foerderer (nutzer_id);
CREATE TABLE fehlerprotokoll (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zeitpunkt DATETIME, pfad VARCHAR(300), methode VARCHAR(10), ip VARCHAR(45),
    fehlertyp VARCHAR(120), nachricht TEXT, traceback TEXT
);
CREATE INDEX ix_fehlerprotokoll_zeitpunkt ON fehlerprotokoll (zeitpunkt);
CREATE TABLE news (
    id INTEGER NOT NULL, titel VARCHAR(200) NOT NULL, inhalt TEXT NOT NULL, sprache VARCHAR(10),
    veroeffentlicht DATETIME, bild_dateiname VARCHAR(255), untertitel VARCHAR(300),
    tags VARCHAR(255), slug VARCHAR(250),
    PRIMARY KEY (id)
);
CREATE INDEX ix_news_veroeffentlicht ON news (veroeffentlicht);
INSERT INTO nutzer (id, name, email, ist_hyphist, ist_sporist, keine_mails)
    VALUES (1, 'Bestand', 'bestand@example.test', 0, 1, 0);
"""

# Bekannte Legacy-Abweichungen Prod/Staging <-> Modell, die auf SQLite alle
# wirkungslos sind (FKs mangels PRAGMA foreign_keys=ON nicht erzwungen,
# VARCHAR==TEXT Storage-Klasse, INTEGER PRIMARY KEY nie NULL, slug-Eindeutigkeit
# schon per generate_unique_slug() im Code). Werden beim Postgres-Cutover
# (Postgres-Block-Plan Schritt 3) automatisch sauber. Signatur: "op:tabelle:detail".
LEGACY_DRIFT = {
    'add_fk:bewerbung:nutzer_id',
    'add_fk:foerderer:nutzer_id',
    'modify_type:foerderer:ansprechpartner',
    'modify_nullable:fehlerprotokoll:id',
    'add_constraint:news:slug',
}


def _signatur(eintrag):
    """Kurzsignatur eines compare_metadata-Diff-Eintrags: 'op:tabelle:detail'."""
    e = eintrag[0] if isinstance(eintrag, list) else eintrag
    op_name = e[0]
    text = repr(e)
    m_tab = re.search(r"table=<?(?:Table\(')?([a-z_]+)", text) or re.search(r", '([a-z_]+)',", text)
    tab = m_tab.group(1) if m_tab else '?'
    if op_name in ('modify_nullable', 'modify_type', 'modify_default'):
        return f'{op_name}:{e[2]}:{e[3]}'
    m_col = re.search(r"Column\('([a-z_]+)'", text)
    return f'{op_name}:{tab}:{m_col.group(1) if m_col else "?"}'


PG_URL = (os.getenv('DATABASE_URL') or '').strip()
nur_sqlite = pytest.mark.skipif(bool(PG_URL), reason='SQLite-spezifisch (rohes SQLite-DDL)')


@pytest.fixture()
def leere_db_app():
    fd = pfad = None
    if PG_URL:
        db_uri = PG_URL
    else:
        fd, pfad = tempfile.mkstemp(suffix='.db')
        db_uri = f'sqlite:///{pfad}'
    instance = tempfile.mkdtemp(suffix='_mig_instance')

    class _Cfg(TestConfig):
        SQLALCHEMY_DATABASE_URI = db_uri

    app = create_app(_Cfg, instance_path=instance)
    with app.app_context():
        db.drop_all()  # Reste (v.a. bei geteiltem Postgres); alembic_version separat
        _aufraeumen_extra()
    yield app
    with app.app_context():
        db.drop_all()
        _aufraeumen_extra()
        db.session.remove()
        db.engine.dispose()
    if fd is not None:
        os.close(fd)
        os.unlink(pfad)


def _aufraeumen_extra():
    """alembic_version + (nur Postgres) die BioComm-Schemas der Migration
    3f1b2c4d5e6a -- die kennt db.drop_all() nicht, weil es keine Modelle dafuer gibt."""
    try:
        db.session.execute(db.text('DROP TABLE IF EXISTS alembic_version'))
        if db.engine.dialect.name == 'postgresql':
            db.session.execute(db.text('DROP SCHEMA IF EXISTS ' + ', '.join(BIOCOMM_SCHEMAS) + ' CASCADE'))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _drift(metadata=None):
    with db.engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={'compare_type': True})
        roh = compare_metadata(ctx, db.metadata)
    return [d for d in roh if 'alembic_version' not in repr(d)]


def test_upgrade_laeuft_bis_head(leere_db_app):
    with leere_db_app.app_context():
        upgrade()
        tabellen = db.inspect(db.engine).get_table_names()
    assert {'nutzer', 'messung', 'alembic_version'} <= set(tabellen)


def test_kein_schema_drift_frische_db(leere_db_app):
    """Frische Installation: Modelle == Migrations-Kette, ZERO Toleranz.
    Faengt eine Model-Aenderung ohne zugehoerige Migration."""
    with leere_db_app.app_context():
        upgrade()
        diff = _drift()
    assert diff == [], f'Modelle weichen von der Migrations-Kette ab:\n{diff}'


@nur_sqlite
def test_legacy_adoption(leere_db_app):
    """Prod-/Staging-Weg: bestehende Tabellen mit den ueber Jahre gewachsenen
    Abweichungen -> stamp Baseline -> upgrade head. Danach: rolle weg,
    Bestandszeile erhalten, und der Rest-Drift ist GENAU die bekannte
    Legacy-Allowlist (nichts Unerwartetes)."""
    with leere_db_app.app_context():
        dbfile = db.engine.url.database
        con = sqlite3.connect(dbfile)
        con.executescript(_LEGACY_SCHEMA)
        con.commit()
        con.close()
        db.create_all()

        stamp(revision=BASELINE_REV)
        upgrade()

        con = sqlite3.connect(dbfile)
        nutzer_cols = {r[1] for r in con.execute('PRAGMA table_info(nutzer)')}
        zeile = list(con.execute('SELECT id, name, ist_sporist FROM nutzer'))
        con.close()

        rest = {_signatur(d) for d in _drift()}

    assert 'rolle' not in nutzer_cols, 'Geisterspalte nicht entfernt'
    assert zeile == [(1, 'Bestand', 1)], 'Bestandszeile verloren'
    unerwartet = rest - LEGACY_DRIFT
    assert not unerwartet, f'Neuer, nicht abgedeckter Drift nach Adoption: {unerwartet}'


@nur_sqlite
def test_prod_cleanup_reghosting(leere_db_app):
    """Prod hat nach dem ersten Deploy `rolle` + `ix_nutzer_login_token` erneut
    bekommen (alte migrate_add_columns.py-Kopie lief nochmal). 27180ec9ca6f muss
    beide bei `upgrade` wieder entfernen -- idempotent, ohne Datenverlust."""
    with leere_db_app.app_context():
        dbfile = db.engine.url.database
        con = sqlite3.connect(dbfile)
        con.executescript(_LEGACY_SCHEMA)
        con.commit()
        con.close()
        db.create_all()

        stamp(revision=BASELINE_REV)
        upgrade(revision='966393848d7c')  # nur bis zur Adoption

        # simuliert den erneuten migrate_add_columns.py-Lauf
        con = sqlite3.connect(dbfile)
        con.execute("ALTER TABLE nutzer ADD COLUMN rolle VARCHAR(20) DEFAULT 'mycelist'")
        con.execute('CREATE UNIQUE INDEX ix_nutzer_login_token ON nutzer (login_token)')
        con.commit()
        con.close()

        upgrade()  # 27180ec9ca6f raeumt auf

        con = sqlite3.connect(dbfile)
        cols = {r[1] for r in con.execute('PRAGMA table_info(nutzer)')}
        idx = {i[1] for i in con.execute('PRAGMA index_list(nutzer)')}
        zeile = list(con.execute('SELECT id, name, ist_sporist FROM nutzer'))
        con.close()

    assert 'rolle' not in cols
    assert 'ix_nutzer_login_token' not in idx
    assert zeile == [(1, 'Bestand', 1)]


# --- BioComm-Schemas (Migration 3f1b2c4d5e6a) ---------------------------------
nur_postgres = pytest.mark.skipif(not PG_URL, reason='BioComm-Schemas gibt es nur auf PostgreSQL')


def _schemas_und_tabellen():
    zeilen = db.session.execute(db.text(
        "SELECT table_schema, table_name FROM information_schema.tables"
        " WHERE table_schema IN :s AND table_type = 'BASE TABLE'"
    ).bindparams(db.bindparam('s', expanding=True)), {'s': list(BIOCOMM_SCHEMAS)}).all()
    ergebnis = {}
    for schema, tabelle in zeilen:
        ergebnis.setdefault(schema, set()).add(tabelle)
    return ergebnis


def test_biocomm_migration_auf_sqlite_noop(leere_db_app):
    """Auf SQLite (lokal, CI-Job backend) legt die Migration nichts an."""
    if PG_URL:
        pytest.skip('SQLite-Pfad')
    with leere_db_app.app_context():
        upgrade()
        rev = db.session.execute(db.text('SELECT version_num FROM alembic_version')).scalar()
    assert rev == HEAD_REV


@nur_postgres
def test_biocomm_schemas_paritaet(leere_db_app):
    """sandbox und live aus einer Quelle: identische Tabellen, bis auf die
    Sandbox-exklusiven Szenario-Tabellen; private Koordinaten je eigenes Schema."""
    with leere_db_app.app_context():
        upgrade()
        t = _schemas_und_tabellen()
    assert t['sandbox'] - t['live'] == {'sandbox_scenario', 'sandbox_scenario_series'}
    assert t['live'] - t['sandbox'] == set()
    assert t['live_private'] == t['sandbox_private'] == {'site_location_private'}
    assert {'origin_batch', 'sample_block', 'quality_annotation', 'recording_plan_interval'} <= t['live']


@nur_postgres
def test_biocomm_regeln(leere_db_app):
    """Die 43 Regeltests aus dem Entwurf (Konflikt-Batch, Ist-Zeiten,
    Unveraenderlichkeit, Exclusion auf sample_index, ...). Das Skript bricht
    bei jeder Abweichung mit 'TEST FEHLGESCHLAGEN' ab und rollt am Ende zurueck."""
    with open(REGELN_SQL, encoding='utf-8') as f:
        regeln = f.read()
    with leere_db_app.app_context():
        upgrade()
        conn = db.engine.raw_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(regeln)
            conn.rollback()
        finally:
            conn.close()


@nur_postgres
def test_biocomm_idempotent_und_downgrade(leere_db_app):
    """Ein zweiter Lauf (Version zurueckgesetzt, Schemas noch da) laeuft durch;
    downgrade entfernt die Schemas vollstaendig."""
    with leere_db_app.app_context():
        upgrade()
        stamp(revision=BIOCOMM_VORHER)
        upgrade()                                   # Schemas schon da -> No-op
        assert set(_schemas_und_tabellen()) == set(BIOCOMM_SCHEMAS) - {'biocomm_common'}
        downgrade(revision=BIOCOMM_VORHER)
        db.session.commit()
        assert _schemas_und_tabellen() == {}
        rest = db.session.execute(db.text(
            "SELECT count(*) FROM pg_namespace WHERE nspname IN :s"
        ).bindparams(db.bindparam('s', expanding=True)), {'s': list(BIOCOMM_SCHEMAS)}).scalar()
    assert rest == 0


def test_biocomm_owner_url_ohne_fremdes_passwort():
    """Die omn_owner-Verbindung darf das Passwort aus DATABASE_URL (das von omn)
    NICHT uebernehmen -- sonst schlaegt die Anmeldung fehl (Staging, 2026-09-24).
    Laeuft auf jeder Engine, reine URL-Logik."""
    import importlib.util

    from sqlalchemy.engine import make_url

    pfad = os.path.join(os.path.dirname(__file__), '..', 'migrations', 'versions',
                        '3f1b2c4d5e6a_biocomm_schemas_sandbox_live.py')
    spec = importlib.util.spec_from_file_location('mig_biocomm', pfad)
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)

    url = make_url('postgresql+psycopg://omn:geheim@127.0.0.1:5432/omn_staging?sslmode=disable')
    owner = mig._owner_url(url)
    assert owner.username == 'omn_owner'
    assert owner.password is None
    assert (owner.host, owner.port, owner.database) == ('127.0.0.1', 5432, 'omn_staging')
    assert owner.drivername == 'postgresql+psycopg'
    assert dict(owner.query) == {'sslmode': 'disable'}
