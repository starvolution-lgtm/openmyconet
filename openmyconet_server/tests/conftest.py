"""
Gemeinsame Fixtures fuer alle Tests.

Wichtig: app.py erzeugt die Flask-App als Modul-Singleton (kein App-Factory-
Pattern) und laedt beim Import die echten .env-Werte. Fuer Tests wird direkt
danach die DB-URI auf eine temporaere SQLite-Datei umgebogen (Flask-SQLAlchemy
3.x baut die Engine erst beim ersten Zugriff, die Umstellung nach init_app()
funktioniert deshalb noch), damit Tests niemals gegen die echte
openmyconet.db laufen.
"""

import os
import shutil
import tempfile

import pytest

from app import app as flask_app
from extensions import db as _db
from models import AdminUser
from werkzeug.security import generate_password_hash


@pytest.fixture()
def app():
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    instance_dir = tempfile.mkdtemp(suffix='_instance')
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI=f'sqlite:///{db_path}',
        MAIL_SUPPRESS_SEND=True,
        SERVER_NAME='testserver.local',
        # CSRF-Schutz (csrf.py) fuer die meisten Tests aus -- die POST-Requests
        # der Test-Clients schicken kein Token mit. test_csrf.py schaltet ihn
        # gezielt wieder ein, um die Mechanik selbst zu pruefen.
        CSRF_ENABLED=False,
    )
    # instance_path zeigt sonst auf den echten Projektordner -- ohne diese
    # Umleitung landen von Tests erzeugte Foerderer-Rechnungs-PDFs
    # (foerderer.py _rechnung_pdf_pfad()) im echten instance/rechnungen/,
    # vermischt mit tatsaechlichen Rechnungen (real passiert, Testdatei
    # OMN-2026-0001.pdf musste manuell wieder entfernt werden).
    flask_app.instance_path = instance_dir
    # Flask-Mail liest MAIL_SUPPRESS_SEND nur einmal bei init_app() (beim Import
    # von app.py, noch vor der obigen Config-Aenderung) und legt das Ergebnis im
    # Extension-State ab -- ein nachtraegliches app.config.update() greift daher
    # NICHT mehr. Ohne diese Zeile wuerden Tests echte Mails ueber den echten
    # SMTP-Server verschicken (real passiert, mit echten Rejections vom
    # Mailserver, bis dieser Fix eingebaut wurde).
    flask_app.extensions['mail'].suppress = True

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()
        _db.engine.dispose()
    os.close(db_fd)
    os.unlink(db_path)
    shutil.rmtree(instance_dir, ignore_errors=True)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _rate_limit_umgehen(monkeypatch):
    # ip_erlaubt() schreibt in ein systemweites Temp-Verzeichnis, keyed nach
    # IP+Endpunkt -- ohne diesen Bypass wuerden wiederholte Testlaeufe sich
    # gegenseitig ins Rate-Limit laufen (siehe test_spam_schutz.py fuer einen
    # gezielten Test der echten Rate-Limit-Logik).
    monkeypatch.setattr('registrierung.ip_erlaubt', lambda *a, **kw: True)
    monkeypatch.setattr('foerderer.ip_erlaubt', lambda *a, **kw: True)
    monkeypatch.setattr('dashboard.ip_erlaubt', lambda *a, **kw: True)
    monkeypatch.setattr('admin.ip_erlaubt', lambda *a, **kw: True)
    monkeypatch.setattr('rag_chatbot.ip_erlaubt', lambda *a, **kw: True)


@pytest.fixture()
def superadmin(app):
    user = AdminUser(username='superadmin_test', password_hash=generate_password_hash('sehr-geheim-123'), role='superadmin')
    _db.session.add(user)
    _db.session.commit()
    return user


@pytest.fixture()
def editor(app):
    user = AdminUser(username='editor_test', password_hash=generate_password_hash('auch-geheim-123'), role='editor')
    _db.session.add(user)
    _db.session.commit()
    return user


def eingeloggt(client, username, password):
    return client.post('/login', data={'username': username, 'password': password}, follow_redirects=False)
