from extensions import db, mail
from models import Nutzer


def test_registrierung_erfolgreich(client, app):
    with mail.record_messages() as ausgehend:
        resp = client.post('/api/register', data={
            'name': 'Test Nutzer', 'email': 'test@example.com', 'land': 'DE', 'gruppe': 'allgemein',
        })
    assert resp.status_code == 200
    assert resp.get_json() == {'ok': True}

    with app.app_context():
        nutzer = Nutzer.query.filter_by(email='test@example.com').first()
        assert nutzer is not None
        assert nutzer.bestaetigt is False
        assert nutzer.token

    assert len(ausgehend) == 1
    assert 'test@example.com' in ausgehend[0].recipients
    assert nutzer.token in ausgehend[0].body


def test_registrierung_doppelte_email_abgelehnt(client):
    client.post('/api/register', data={'name': 'A', 'email': 'doppelt@example.com'})
    resp = client.post('/api/register', data={'name': 'B', 'email': 'doppelt@example.com'})
    assert resp.status_code == 400
    assert 'bereits registriert' in resp.get_json()['error']


def test_registrierung_ohne_email_400(client):
    resp = client.post('/api/register', data={'name': 'Ohne Mail'})
    assert resp.status_code == 400


def test_registrierung_honeypot_stiller_erfolg(client, app):
    resp = client.post('/api/register', data={
        'name': 'Bot', 'email': 'bot@example.com', 'website': 'https://spam.example',
    })
    assert resp.status_code == 200
    assert resp.get_json() == {'ok': True}
    with app.app_context():
        assert Nutzer.query.filter_by(email='bot@example.com').first() is None


def test_confirm_bestaetigt_nutzer(client, app):
    client.post('/api/register', data={'name': 'Confirm Test', 'email': 'confirm@example.com'})
    with app.app_context():
        token = Nutzer.query.filter_by(email='confirm@example.com').first().token

    resp = client.get(f'/confirm/{token}')
    assert resp.status_code == 200
    assert 'bestätigt' in resp.get_data(as_text=True)

    with app.app_context():
        assert Nutzer.query.filter_by(email='confirm@example.com').first().bestaetigt is True


def test_confirm_ungueltiger_token_404(client):
    resp = client.get('/confirm/nicht-existierender-token')
    assert resp.status_code == 404
