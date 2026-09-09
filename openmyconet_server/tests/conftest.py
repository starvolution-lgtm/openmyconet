"""
Gemeinsame Fixtures fuer alle Tests.

Seit dem App-Factory-Umbau (2026-09): jeder Test bekommt ueber
create_app(TestConfig) eine frische App. TestConfig traegt bereits
CSRF_ENABLED=False, MAIL_SUPPRESS_SEND=True und einen Test-Absender -- die
frueheren extensions['mail']-Hacks (Flask-Mail friert die Werte bei init_app
ein) entfallen dadurch, weil mail.init_app jetzt NACH from_object(TestConfig)
laeuft. DB + Uploads + instance_path zeigen pro Test auf Temp-Verzeichnisse,
damit nie gegen die echte openmyconet.db / echte Uploads gelaufen wird.
"""

import os
import shutil
import tempfile

import pytest
from werkzeug.security import generate_password_hash

from omn import create_app
from omn.config import TestConfig
from omn.extensions import db as _db
from omn.models import AdminUser


@pytest.fixture()
def app():
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    instance_dir = tempfile.mkdtemp(suffix='_instance')
    upload_dir = tempfile.mkdtemp(suffix='_uploads')

    class _Cfg(TestConfig):
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'
        UPLOAD_ROOT = upload_dir

    application = create_app(_Cfg, instance_path=instance_dir)

    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()
        _db.engine.dispose()
    os.close(db_fd)
    os.unlink(db_path)
    shutil.rmtree(instance_dir, ignore_errors=True)
    shutil.rmtree(upload_dir, ignore_errors=True)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _testumgebung(monkeypatch):
    # ip_erlaubt() schreibt in ein systemweites Temp-Verzeichnis, keyed nach
    # IP+Endpunkt -- ohne diesen Bypass wuerden wiederholte Testlaeufe sich
    # gegenseitig ins Rate-Limit laufen (siehe test_spam_schutz.py fuer einen
    # gezielten Test der echten Rate-Limit-Logik).
    monkeypatch.setattr('omn.registrierung.ip_erlaubt', lambda *a, **kw: True)
    monkeypatch.setattr('omn.foerderer.ip_erlaubt', lambda *a, **kw: True)
    monkeypatch.setattr('omn.dashboard.ip_erlaubt', lambda *a, **kw: True)
    monkeypatch.setattr('omn.admin.auth.ip_erlaubt', lambda *a, **kw: True)
    monkeypatch.setattr('omn.rag_chatbot.ip_erlaubt', lambda *a, **kw: True)
    # Admin-/Team-Benachrichtigungen (foerderer.py, kollaboration.py) sind an
    # ADMIN_NOTIFY_EMAIL bzw. MAIL_USERNAME geknuepft und werden sonst still
    # uebersprungen. Fest setzen macht die "Admin wird benachrichtigt"-Tests
    # unabhaengig von der Umgebung (lokal .env, CI keine .env).
    monkeypatch.setenv('ADMIN_NOTIFY_EMAIL', 'admin@openmyconet.test')


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
