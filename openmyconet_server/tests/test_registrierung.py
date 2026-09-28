from conftest import eingeloggt
from omn.extensions import mail
from omn.models import Nutzer


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


# --- Einwilligung in Rund-Mails (Newsletter-Häkchen) ------------------------

def _keine_mails(app, email):
    with app.app_context():
        return Nutzer.query.filter_by(email=email).first().keine_mails


def test_ohne_haekchen_keine_rundmails(client, app):
    client.post('/api/register', data={'name': 'Ohne', 'email': 'ohne@example.com'})
    assert _keine_mails(app, 'ohne@example.com') is True


def test_mit_haekchen_rundmails_erlaubt(client, app):
    # So schickt der Browser eine angehakte Checkbox (FormData auf index.html).
    client.post('/api/register', data={'name': 'Mit', 'email': 'mit@example.com', 'newsletter': 'on'})
    assert _keine_mails(app, 'mit@example.com') is False


def test_erneute_registrierung_aendert_einwilligung_nicht(client, app):
    client.post('/api/register', data={'name': 'A', 'email': 'zweimal@example.com'})
    resp = client.post('/api/register', data={'name': 'A', 'email': 'zweimal@example.com', 'newsletter': 'on'})
    assert resp.status_code == 400
    assert _keine_mails(app, 'zweimal@example.com') is True


def test_bewerbung_legt_ohne_einwilligung_an(app):
    # Wege ohne Häkchen (Knoten-Bewerbung, Förderer, Kooperation) nutzen den Standard.
    from omn.registrierung import register_nutzer_core
    with app.app_context():
        nutzer, _ = register_nutzer_core('B', 'bew@example.com', 'de', '', 'biocomm',
                                         rollback_on_mail_fail=False)
        assert nutzer.keine_mails is True


def test_newsletter_nur_an_bestaetigte_mit_haekchen(client, app, superadmin):
    for email, haekchen in (('nl-ja@example.com', True), ('nl-nein@example.com', False)):
        daten = {'name': 'X', 'email': email}
        if haekchen:
            daten['newsletter'] = 'on'
        client.post('/api/register', data=daten)
        with app.app_context():
            token = Nutzer.query.filter_by(email=email).first().token
        client.get(f'/confirm/{token}')

    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    with mail.record_messages() as ausgehend:
        client.post('/admin/newsletter', data={
            'betreff': 'Test', 'inhalt': 'Hallo {name}', 'bestaetigt_senden': '1',
        }, follow_redirects=True)
    assert {adr for m in ausgehend for adr in m.recipients} == {'nl-ja@example.com'}
