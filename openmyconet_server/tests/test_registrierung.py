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


def test_mit_haekchen_einwilligung_protokolliert(client, app):
    client.post('/api/register', data={'name': 'Mit', 'email': 'proto@example.com', 'newsletter': 'on'})
    with app.app_context():
        assert Nutzer.query.filter_by(email='proto@example.com').first().newsletter_einwilligung_am is not None


def test_erneute_registrierung_mit_haekchen_schickt_einwilligungslink(client, app):
    client.post('/api/register', data={'name': 'A', 'email': 'zweimal@example.com'})
    with mail.record_messages() as ausgehend:
        resp = client.post('/api/register', data={'name': 'A', 'email': 'zweimal@example.com', 'newsletter': 'on'})
    assert resp.status_code == 200
    assert resp.get_json()['einwilligung_angefragt'] is True
    with app.app_context():
        nutzer = Nutzer.query.filter_by(email='zweimal@example.com').first()
        # nichts umgestellt, erst der Klick zaehlt
        assert nutzer.keine_mails is True
        assert nutzer.newsletter_einwilligung_am is None
        token = nutzer.token
    assert len(ausgehend) == 1
    assert f'/newsletter/einwilligen/{token}' in ausgehend[0].body

    # Sperre: innerhalb einer Stunde kein zweiter Link (keine Mail-Flut an fremde Adressen)
    with mail.record_messages() as ausgehend:
        resp = client.post('/api/register', data={'name': 'A', 'email': 'zweimal@example.com', 'newsletter': 'on'})
    assert resp.status_code == 200
    assert ausgehend == []


def test_erneute_registrierung_ohne_haekchen_bleibt_abgelehnt(client, app):
    client.post('/api/register', data={'name': 'A', 'email': 'nochmal@example.com'})
    with mail.record_messages() as ausgehend:
        resp = client.post('/api/register', data={'name': 'A', 'email': 'nochmal@example.com'})
    assert resp.status_code == 400
    assert ausgehend == []


def test_erneute_registrierung_schon_angemeldet_bleibt_abgelehnt(client):
    client.post('/api/register', data={'name': 'A', 'email': 'dabei@example.com', 'newsletter': 'on'})
    resp = client.post('/api/register', data={'name': 'A', 'email': 'dabei@example.com', 'newsletter': 'on'})
    assert resp.status_code == 400
    assert 'bereits registriert' in resp.get_json()['error']


def test_einwilligen_get_fragt_nur_post_willigt_ein(client, app):
    client.post('/api/register', data={'name': 'E', 'email': 'klick@example.com'})
    with app.app_context():
        token = Nutzer.query.filter_by(email='klick@example.com').first().token

    r = client.get(f'/newsletter/einwilligen/{token}')
    assert r.status_code == 200
    assert 'Ja, ich möchte Neuigkeiten bekommen' in r.get_data(as_text=True)
    with app.app_context():
        assert Nutzer.query.filter_by(email='klick@example.com').first().keine_mails is True

    r = client.post(f'/newsletter/einwilligen/{token}')
    assert r.status_code == 200
    with app.app_context():
        nutzer = Nutzer.query.filter_by(email='klick@example.com').first()
        assert nutzer.keine_mails is False
        assert nutzer.newsletter_einwilligung_am is not None
        assert nutzer.bestaetigt is True  # Klick beweist die Adresse


def test_einwilligen_ungueltiger_token_404(client):
    assert client.get('/newsletter/einwilligen/gibtsnicht').status_code == 404
    assert client.post('/newsletter/einwilligen/gibtsnicht').status_code == 404


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


def _bestand(app, email, *, bestaetigt=True, keine_mails=False, eingewilligt=False):
    from omn.extensions import db
    from omn.zeit import utcnow
    with app.app_context():
        db.session.add(Nutzer(name=email.split('@')[0], email=email, token=f'tok-{email}',
                              bestaetigt=bestaetigt, keine_mails=keine_mails,
                              newsletter_einwilligung_am=utcnow() if eingewilligt else None))
        db.session.commit()


def test_einwilligung_anfragen_probelauf_aendert_nichts(app):
    _bestand(app, 'alt@example.com')
    with mail.record_messages() as ausgehend:
        r = app.test_cli_runner().invoke(args=['einwilligung-anfragen'])
    assert r.exit_code == 0, r.output
    assert 'Probelauf' in r.output
    assert ausgehend == []
    assert _keine_mails(app, 'alt@example.com') is False


def test_einwilligung_anfragen_bestand(app):
    _bestand(app, 'alt@example.com')                          # bekam bisher ungefragt Mails
    _bestand(app, 'unbest@example.com', bestaetigt=False)     # nie bestaetigt
    _bestand(app, 'ja@example.com', eingewilligt=True)        # hat eingewilligt
    _bestand(app, 'weg@example.com', keine_mails=True)        # hatte sich abgemeldet
    runner = app.test_cli_runner()
    with app.app_context(), mail.record_messages() as ausgehend:
        r = runner.invoke(args=['einwilligung-anfragen', '--ausfuehren'])
    assert r.exit_code == 0, r.output
    assert {adr for m in ausgehend for adr in m.recipients} == {'alt@example.com'}
    assert '/newsletter/einwilligen/tok-alt@example.com' in ausgehend[0].body
    assert _keine_mails(app, 'alt@example.com') is True
    assert _keine_mails(app, 'unbest@example.com') is True
    assert _keine_mails(app, 'ja@example.com') is False
    assert _keine_mails(app, 'weg@example.com') is True

    # zweiter Lauf findet niemanden mehr
    with app.app_context(), mail.record_messages() as ausgehend:
        r = runner.invoke(args=['einwilligung-anfragen', '--ausfuehren'])
    assert '0 ohne dokumentierte Einwilligung' in r.output
    assert ausgehend == []
