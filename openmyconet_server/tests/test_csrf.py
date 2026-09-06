"""Testet den CSRF-Schutz aus csrf.py. conftest setzt CSRF_ENABLED=False --
hier gezielt wieder an, damit die Mechanik selbst geprueft wird."""
import pytest


@pytest.fixture()
def csrf_client(app):
    app.config['CSRF_ENABLED'] = True
    return app.test_client()


def _token(client, pfad='/login'):
    client.get(pfad)  # erzeugt session['_csrf_token']
    with client.session_transaction() as s:
        return s['_csrf_token']


def test_post_ohne_token_wird_abgelehnt(csrf_client):
    r = csrf_client.post('/login', data={'username': 'x', 'password': 'y'})
    assert r.status_code == 400


def test_post_mit_falschem_token_wird_abgelehnt(csrf_client):
    _token(csrf_client)
    r = csrf_client.post('/login', data={'username': 'x', 'password': 'y', '_csrf': 'falsch'})
    assert r.status_code == 400


def test_post_mit_gueltigem_token_geht_durch(csrf_client, superadmin):
    tok = _token(csrf_client)
    r = csrf_client.post('/login', data={
        'username': 'superadmin_test', 'password': 'sehr-geheim-123', '_csrf': tok,
    })
    assert r.status_code == 302  # Login erfolgreich -> Redirect, nicht 400


def test_token_auch_per_header_akzeptiert(csrf_client):
    tok = _token(csrf_client)
    r = csrf_client.post('/login', data={'username': 'x', 'password': 'y'},
                         headers={'X-CSRFToken': tok})
    assert r.status_code == 200  # kein 400 -> Token akzeptiert, nur Login falsch


def test_get_braucht_kein_token(csrf_client):
    assert csrf_client.get('/login').status_code == 200


def test_geschuetzte_seiten_sind_no_store(csrf_client):
    # Session-gebundene Seiten duerfen nicht aus dem (bf)cache wiederhergestellt
    # werden -- sonst Formular-Replay mit totem CSRF-Token.
    r = csrf_client.get('/login')
    assert 'no-store' in r.headers.get('Cache-Control', '')


def test_admin_login_leitet_auf_kanonischen_host(csrf_client):
    # www./ohne-Sub -> api., damit die hostgebundene Session nicht abreisst.
    r = csrf_client.get('/login', base_url='https://www.openmyconet.de')
    assert r.status_code == 308
    assert r.headers['Location'] == 'https://api.openmyconet.de/login'
    # api. selbst wird nicht umgeleitet.
    assert csrf_client.get('/login', base_url='https://api.openmyconet.de').status_code == 200


def test_oeffentliche_json_api_ohne_token_nicht_blockiert(csrf_client):
    # /api/register ist bewusst NICHT csrf-geschuetzt (cross-origin fetch).
    r = csrf_client.post('/api/register', data={'name': 'A', 'email': ''})
    assert r.status_code != 400 or 'CSRF' not in r.get_data(as_text=True)
