"""News-Veroeffentlichung mit optionaler E-Mail-Benachrichtigung (Checkbox
`mail_senden`) + tokengesicherter Abmelde-Link (/abmelden/<token>)."""
from conftest import eingeloggt
from omn.extensions import db, mail
from omn.models import News, Nutzer


def _nutzer(app, email, *, sprache='de', bestaetigt=True, keine_mails=False, token=None):
    with app.app_context():
        n = Nutzer(name=email.split('@')[0], email=email, sprache=sprache,
                   bestaetigt=bestaetigt, keine_mails=keine_mails,
                   token=token or f'tok-{email}')
        db.session.add(n)
        db.session.commit()


def _news_posten(client, mail_senden=False, sprache='de', mail_sprachen=None):
    daten = {'titel': 'Grosse Neuigkeit', 'untertitel': 'Untertitel',
             'inhalt': 'Wir haben einen neuen Knoten im Wald.', 'sprache': sprache, 'tags': ''}
    if mail_senden:
        daten['mail_senden'] = '1'
        daten['mail_sprachen'] = mail_sprachen if mail_sprachen is not None else ['de']
    return client.post('/admin/news', data=daten, follow_redirects=True)


def test_ohne_checkbox_keine_mail(client, app, superadmin):
    _nutzer(app, 'de1@example.com')
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    with mail.record_messages() as ausgehend:
        r = _news_posten(client, mail_senden=False)
    assert r.status_code == 200
    assert ausgehend == []


def test_mail_nur_an_gewaehlte_sprachen_und_bestaetigt(client, app, superadmin):
    _nutzer(app, 'de-ok@example.com', sprache='de')
    _nutzer(app, 'en-skip@example.com', sprache='en')
    _nutzer(app, 'de-unbestaetigt@example.com', sprache='de', bestaetigt=False)
    _nutzer(app, 'de-abgemeldet@example.com', sprache='de', keine_mails=True)
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')

    with mail.record_messages() as ausgehend:
        r = _news_posten(client, mail_senden=True, sprache='de', mail_sprachen=['de'])
    assert r.status_code == 200

    empfaenger = {adr for m in ausgehend for adr in m.recipients}
    assert empfaenger == {'de-ok@example.com'}

    m = ausgehend[0]
    with app.app_context():
        news = News.query.filter_by(titel='Grosse Neuigkeit').first()
    assert f'/news/{news.slug}' in m.body
    assert '/abmelden/tok-de-ok@example.com' in m.body
    assert '/abmelden/tok-de-ok@example.com' in m.html
    assert 'Beitrag lesen' in m.html
    # RFC 8058 One-Click-Unsubscribe
    lu = dict(m.extra_headers)
    assert lu['List-Unsubscribe'] == '<http://testserver.local/abmelden/tok-de-ok@example.com>'
    assert lu['List-Unsubscribe-Post'] == 'List-Unsubscribe=One-Click'


def test_englische_news_an_mehrere_sprachgruppen(client, app, superadmin):
    _nutzer(app, 'de-u@example.com', sprache='de')
    _nutzer(app, 'en-u@example.com', sprache='en')
    _nutzer(app, 'fr-skip@example.com', sprache='fr')
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')

    with mail.record_messages() as ausgehend:
        r = _news_posten(client, mail_senden=True, sprache='en', mail_sprachen=['de', 'en'])
    assert r.status_code == 200
    empfaenger = {adr for m in ausgehend for adr in m.recipients}
    assert empfaenger == {'de-u@example.com', 'en-u@example.com'}


def test_checkbox_an_aber_keine_sprache_kein_versand(client, app, superadmin):
    _nutzer(app, 'de-u@example.com', sprache='de')
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    with mail.record_messages() as ausgehend:
        r = _news_posten(client, mail_senden=True, mail_sprachen=[])
    assert r.status_code == 200
    assert ausgehend == []
    assert 'keine Sprache' in r.get_data(as_text=True)


def test_abmelden_get_dann_post(client, app):
    _nutzer(app, 'weg@example.com', token='geheim-abc')

    r = client.get('/abmelden/geheim-abc')
    assert r.status_code == 200
    assert 'weg@example.com' in r.get_data(as_text=True)

    with app.app_context():
        assert Nutzer.query.filter_by(email='weg@example.com').first().keine_mails is False

    r2 = client.post('/abmelden/geheim-abc')
    assert r2.status_code == 200
    assert 'keine' in r2.get_data(as_text=True).lower()
    with app.app_context():
        assert Nutzer.query.filter_by(email='weg@example.com').first().keine_mails is True


def test_abmelden_ungueltiger_token(client):
    r = client.get('/abmelden/gibtsnicht')
    assert r.status_code == 404
    assert 'ungültig' in r.get_data(as_text=True)


def test_newsletter_respektiert_abmeldung(client, app, superadmin):
    _nutzer(app, 'nl-ok@example.com')
    _nutzer(app, 'nl-weg@example.com', keine_mails=True)
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    with mail.record_messages() as ausgehend:
        client.post('/admin/newsletter', data={
            'betreff': 'Test', 'inhalt': 'Hallo {name}', 'bestaetigt_senden': '1',
        }, follow_redirects=True)
    empfaenger = {adr for m in ausgehend for adr in m.recipients}
    assert empfaenger == {'nl-ok@example.com'}
    assert '/abmelden/tok-nl-ok@example.com' in ausgehend[0].body
