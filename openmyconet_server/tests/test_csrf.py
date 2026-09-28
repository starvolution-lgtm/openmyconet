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


# --- Aendernde Admin-Aktionen nur per POST (seit 28.09.2026) -----------------
# Vorher waren Loeschen/Bestaetigen/Verschieben GET-Links: der CSRF-Schutz prueft
# nur POST, eine fremde Seite konnte sie bei eingeloggtem Admin ausloesen.
AENDERNDE_ADMIN_ROUTEN = [
    '/admin/nutzer/loeschen/1',
    '/admin/nutzer/bestaetigen/1',
    '/admin/accounts/delete/1',
    '/admin/news/delete/1',
    '/admin/news/1/verschieben/hoch',
    '/admin/inhalte/delete/1',
    '/admin/presse/delete/1',
    '/admin/presse-kandidaten/uebernehmen/1',
    '/admin/presse-kandidaten/suchbegriff/loeschen/1',
]


@pytest.mark.parametrize('pfad', AENDERNDE_ADMIN_ROUTEN)
def test_aendernde_admin_aktion_nicht_per_link(client, app, superadmin, pfad):
    """GET wird nicht ausgefuehrt: 405, oder 404, weil die Static-Route
    (static_url_path='') jedes GET auf einen unbekannten Pfad als Datei sucht."""
    from conftest import eingeloggt
    from omn.extensions import db
    from omn.models import Nutzer

    with app.app_context():
        db.session.add(Nutzer(id=1, name='Bleibt', email='bleibt@example.com', token='tok-bleibt'))
        db.session.commit()
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    assert client.get(pfad).status_code in (404, 405)
    with app.app_context():
        n = db.session.get(Nutzer, 1)
        assert n is not None and not n.bestaetigt


def test_nutzer_loeschen_ohne_token_loescht_nichts(csrf_client, app, superadmin):
    from omn.extensions import db
    from omn.models import Nutzer

    with app.app_context():
        n = Nutzer(name='Opfer', email='opfer@example.com', token='tok-opfer', bestaetigt=True)
        db.session.add(n)
        db.session.commit()
        nid = n.id
    tok = _token(csrf_client)
    csrf_client.post('/login', data={'username': 'superadmin_test', 'password': 'sehr-geheim-123', '_csrf': tok})
    # fremde Seite: POST ohne Token -> 400, Nutzer bleibt
    assert csrf_client.post(f'/admin/nutzer/loeschen/{nid}').status_code == 400
    with app.app_context():
        assert db.session.get(Nutzer, nid) is not None
    # echter Knopf im Admin: mit Token -> geloescht
    tok = _token(csrf_client, '/admin')
    csrf_client.post(f'/admin/nutzer/loeschen/{nid}', data={'_csrf': tok})
    with app.app_context():
        assert db.session.get(Nutzer, nid) is None
