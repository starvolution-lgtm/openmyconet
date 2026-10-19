from conftest import eingeloggt
from omn.extensions import db
from omn.models import AdminUser


def test_admin_ohne_login_wird_umgeleitet(client):
    resp = client.get('/admin', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_login_falsches_passwort(client, superadmin):
    resp = eingeloggt(client, 'superadmin_test', 'falsches-passwort')
    assert resp.status_code == 200
    assert 'Falscher Benutzername oder Passwort' in resp.get_data(as_text=True)


def test_login_superadmin_erfolgreich_und_zugriff(client, superadmin):
    resp = eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/admin')

    resp = client.get('/admin')
    assert resp.status_code == 200


def test_login_editor_erfolgreich_aber_kein_superadmin_zugriff(client, editor):
    resp = eingeloggt(client, 'editor_test', 'auch-geheim-123')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/admin/news')

    # Editor darf die eigene Seite sehen ...
    resp = client.get('/admin/news')
    assert resp.status_code == 200

    # ... aber nicht den Superadmin-Bereich (role_required('superadmin')).
    resp = client.get('/admin')
    assert resp.status_code == 403


def test_logout_beendet_session(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    assert client.get('/admin').status_code == 200

    client.get('/logout')
    resp = client.get('/admin', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_gesperrte_ip_kommt_auch_mit_richtigem_passwort_nicht_durch(client, superadmin, monkeypatch):
    """Das Limit muss VOR der Passwortpruefung greifen, sonst bremst es keinen Brute-Force."""
    monkeypatch.setattr('omn.admin.auth.ip_gesperrt', lambda *a, **kw: True)
    resp = eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    assert resp.status_code == 200
    assert 'Zu viele Fehlversuche' in resp.get_data(as_text=True)
    assert client.get('/admin', follow_redirects=False).status_code == 302


def test_geloeschtes_konto_verliert_die_session_sofort(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    assert client.get('/admin').status_code == 200
    db.session.delete(db.session.get(AdminUser, superadmin.id))
    db.session.commit()
    resp = client.get('/admin', follow_redirects=False)
    assert resp.status_code == 302
    assert '/login' in resp.headers['Location']


def test_rolle_kommt_aus_der_db_nicht_aus_dem_cookie(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    assert client.get('/admin').status_code == 200
    db.session.get(AdminUser, superadmin.id).role = 'editor'
    db.session.commit()
    assert client.get('/admin').status_code == 403


def test_superadmin_ohne_2fa_wird_zur_einrichtung_umgeleitet(app, client, superadmin):
    app.config['ADMIN_2FA_ERZWINGEN'] = True
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    resp = client.get('/admin', follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/admin/2fa')
    # Einrichtungsseite und Abmelden bleiben erreichbar (kein Aussperren)
    assert client.get('/admin/2fa').status_code == 200
    assert client.get('/logout', follow_redirects=False).status_code == 302


def test_superadmin_mit_2fa_hat_zugriff(app, client, superadmin):
    app.config['ADMIN_2FA_ERZWINGEN'] = True
    superadmin.totp_secret = 'JBSWY3DPEHPK3PXP'
    superadmin.totp_aktiviert = True
    db.session.commit()
    # Mit aktiver 2FA fragt der Login den Code; Session direkt setzen, die Pflicht ist hier das Thema.
    with client.session_transaction() as sess:
        sess['admin_logged_in'] = True
        sess['admin_user_id'] = superadmin.id
    assert client.get('/admin').status_code == 200


def test_editor_darf_foerderer_und_kollaboration_nicht(client, editor):
    eingeloggt(client, 'editor_test', 'auch-geheim-123')
    assert client.get('/admin/foerderer').status_code == 403
    assert client.get('/admin/kollaboration/knoten/1').status_code == 403


def test_login_fuehrt_zurueck_ins_mcc(client, superadmin):
    """Vom Handy ist /admin gesperrt (Client-Zertifikat) -- nach dem Login zurueck zum Ziel."""
    resp = client.get('/mcc/kontakte', follow_redirects=False)
    assert resp.status_code == 302 and 'weiter=/mcc/kontakte' in resp.headers['Location']
    resp = client.post('/login?weiter=/mcc/kontakte',
                       data={'username': 'superadmin_test', 'password': 'sehr-geheim-123'})
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/mcc/kontakte')


def test_login_weiter_nur_eigene_pfade(client, superadmin):
    for boese in ('https://evil.example', '//evil.example', '/news', '/mcc/../x', '/mcc' + chr(92) + 'x'):
        client.get('/logout')
        resp = client.post('/login', query_string={'weiter': boese},
                           data={'username': 'superadmin_test', 'password': 'sehr-geheim-123'})
        assert resp.headers['Location'].endswith('/admin'), boese


def test_login_mit_2fa_behaelt_das_ziel(client, superadmin):
    import pyotp
    superadmin.totp_secret = pyotp.random_base32()
    superadmin.totp_aktiviert = True
    db.session.commit()
    client.post('/login?weiter=/mcc', data={'username': 'superadmin_test', 'password': 'sehr-geheim-123'})
    resp = client.post('/login/2fa', data={'code': pyotp.TOTP(superadmin.totp_secret).now()})
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/mcc')
