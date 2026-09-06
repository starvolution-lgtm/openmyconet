"""Admin-Zwei-Faktor (TOTP). CSRF ist in den Tests aus (conftest)."""
import json

import pyotp
from conftest import eingeloggt

from extensions import db
from models import AdminUser


def test_setup_aktiviert_und_zeigt_recovery_codes(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    client.post('/admin/2fa', data={'aktion': 'start'})
    with client.session_transaction() as sess:
        secret = sess['2fa_setup_secret']
    resp = client.post('/admin/2fa', data={'aktion': 'bestaetigen',
                                           'code': pyotp.TOTP(secret).now()})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert 'Recovery-Codes' in body

    user = db.session.get(AdminUser, superadmin.id)
    assert user.totp_aktiviert is True
    assert user.totp_secret == secret
    assert len(json.loads(user.totp_recovery)) == 10


def test_setup_falscher_code_aktiviert_nicht(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    client.post('/admin/2fa', data={'aktion': 'start'})
    resp = client.post('/admin/2fa', data={'aktion': 'bestaetigen', 'code': '000000'})
    assert 'stimmt nicht' in resp.get_data(as_text=True)
    assert db.session.get(AdminUser, superadmin.id).totp_aktiviert in (False, None)


def test_login_verlangt_zweiten_faktor(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    client.post('/admin/2fa', data={'aktion': 'start'})
    with client.session_transaction() as sess:
        secret = sess['2fa_setup_secret']
    client.post('/admin/2fa', data={'aktion': 'bestaetigen', 'code': pyotp.TOTP(secret).now()})
    client.get('/logout')

    # Passwort allein -> Weiterleitung auf die Code-Seite, KEIN Admin-Zugriff.
    resp = eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/login/2fa')
    assert client.get('/admin', follow_redirects=False).status_code == 302

    seite = client.get('/login/2fa')
    assert seite.status_code == 200
    assert 'Authenticator' in seite.get_data(as_text=True)

    # Falscher Code -> bleibt draussen.
    assert client.post('/login/2fa', data={'code': '000000'}).status_code == 200
    assert client.get('/admin', follow_redirects=False).status_code == 302

    # Richtiger Code -> drin.
    resp = client.post('/login/2fa', data={'code': pyotp.TOTP(secret).now()})
    assert resp.status_code == 302
    assert client.get('/admin').status_code == 200


def test_recovery_code_funktioniert_einmal(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    client.post('/admin/2fa', data={'aktion': 'start'})
    with client.session_transaction() as sess:
        secret = sess['2fa_setup_secret']
    client.post('/admin/2fa', data={'aktion': 'bestaetigen', 'code': pyotp.TOTP(secret).now()})

    # Recovery-Codes kann der Test nicht im Klartext abgreifen -> einen frischen
    # Satz setzen, dessen Klartext wir kennen.
    user = db.session.get(AdminUser, superadmin.id)
    from werkzeug.security import generate_password_hash
    user.totp_recovery = json.dumps([generate_password_hash('1234509876')])
    db.session.commit()
    client.get('/logout')

    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    resp = client.post('/login/2fa', data={'code': '1234-50987-6'})  # Trenner egal
    assert resp.status_code == 302
    assert client.get('/admin').status_code == 200

    # verbraucht -> zweiter Versuch scheitert
    client.get('/logout')
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    assert client.post('/login/2fa', data={'code': '1234509876'}).status_code == 200
    assert client.get('/admin', follow_redirects=False).status_code == 302


def test_deaktivieren_braucht_passwort(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    client.post('/admin/2fa', data={'aktion': 'start'})
    with client.session_transaction() as sess:
        secret = sess['2fa_setup_secret']
    client.post('/admin/2fa', data={'aktion': 'bestaetigen', 'code': pyotp.TOTP(secret).now()})

    resp = client.post('/admin/2fa', data={'aktion': 'deaktivieren', 'passwort': 'falsch'})
    assert 'Passwort stimmt nicht' in resp.get_data(as_text=True)
    assert db.session.get(AdminUser, superadmin.id).totp_aktiviert is True

    client.post('/admin/2fa', data={'aktion': 'deaktivieren', 'passwort': 'sehr-geheim-123'})
    user = db.session.get(AdminUser, superadmin.id)
    assert user.totp_aktiviert is False
    assert user.totp_secret is None
