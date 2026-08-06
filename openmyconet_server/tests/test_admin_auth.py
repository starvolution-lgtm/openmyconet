from conftest import eingeloggt


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
