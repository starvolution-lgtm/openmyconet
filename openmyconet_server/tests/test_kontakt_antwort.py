"""Kontaktanfragen aus dem Admin beantworten (/admin/kontakt/<id>/antworten, seit 23.11.2026):
Versand direkt (nicht ueber die Queue) mit Reply-To + BCC, Speicherung in kontakt_antwort,
Status 'bearbeitet', Audit-Eintrag, CSRF, Loeschen mit der Anfrage (Admin + Loeschfrist)."""
from datetime import timedelta

from conftest import eingeloggt
from omn.aufbewahrung import bereinigen
from omn.extensions import db, mail
from omn.models import AdminAudit, KontaktAntwort, Kontaktanfrage, MailQueue
from omn.rechtstexte import RECHTSTEXTE
from omn.zeit import utcnow

TEXT = 'Hallo Anna,\n\ndanke für deine Nachricht!\n\nViele Grüße\nRobby'


def _anfrage(alter_tage=1, status='neu'):
    a = Kontaktanfrage(name='Anna', email='anna@example.org', anliegen='technik', nachricht='Frage?',
                       status=status, erstellt_am=utcnow() - timedelta(days=alter_tage))
    db.session.add(a)
    db.session.commit()
    return a.id


def _antworten(client, aid, betreff='Re: Ihre Kontaktanfrage', text=TEXT):
    return client.post(f'/admin/kontakt/{aid}/antworten', data={'betreff': betreff, 'text': text})


def test_antwort_wird_gesendet_gespeichert_und_protokolliert(client, app, superadmin):
    aid = _anfrage()
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    with mail.record_messages() as ausgehend:
        r = _antworten(client, aid)
    assert r.status_code == 302 and r.headers['Location'].endswith(f'/admin/kontakt#anfrage-{aid}')

    assert len(ausgehend) == 1
    msg = ausgehend[0]
    assert msg.recipients == ['anna@example.org']
    assert msg.bcc == ['admin@openmyconet.test']
    assert msg.reply_to == RECHTSTEXTE['fakten']['mail']
    assert msg.subject == 'Re: Ihre Kontaktanfrage'
    assert msg.body.strip() == TEXT
    assert MailQueue.query.count() == 0  # direkt, nicht ueber die Rund-Mail-Queue

    antwort = KontaktAntwort.query.one()
    assert (antwort.anfrage_id, antwort.an, antwort.text) == (aid, 'anna@example.org', TEXT)
    assert antwort.gesendet_von == 'superadmin_test'
    assert antwort.gesendet_am is not None
    assert db.session.get(Kontaktanfrage, aid).status == 'bearbeitet'
    eintrag = AdminAudit.query.filter_by(aktion='kontakt_antwort').one()
    assert eintrag.ziel == f'Kontaktanfrage #{aid}' and eintrag.benutzername == 'superadmin_test'

    seite = client.get('/admin/kontakt').get_data(as_text=True)
    assert 'Verlauf — 1 Antwort' in seite and 'danke für deine Nachricht!' in seite
    assert f'Antwort an anna@example.org gesendet (Kontaktanfrage #{aid}).' in seite


def test_auch_erledigte_anfrage_wird_wieder_bearbeitet(client, app, superadmin):
    aid = _anfrage(status='erledigt')
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    _antworten(client, aid)
    assert db.session.get(Kontaktanfrage, aid).status == 'bearbeitet'


def test_zeilenumbruch_im_betreff_wird_entfernt(client, app, superadmin):
    aid = _anfrage()
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    with mail.record_messages() as ausgehend:
        _antworten(client, aid, betreff='Re: Hallo\r\nBcc: fremd@example.com')
    assert ausgehend[0].subject == 'Re: Hallo Bcc: fremd@example.com'
    assert ausgehend[0].bcc == ['admin@openmyconet.test']


def test_leerer_text_sendet_nichts(client, app, superadmin):
    aid = _anfrage()
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    with mail.record_messages() as ausgehend:
        r = _antworten(client, aid, text='   ')
    assert r.status_code == 400 and not ausgehend
    assert KontaktAntwort.query.count() == 0
    assert db.session.get(Kontaktanfrage, aid).status == 'neu'


def test_mailfehler_speichert_nichts_und_behaelt_den_text(client, app, superadmin, monkeypatch):
    aid = _anfrage()
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')

    def _kaputt(msg):
        raise OSError('SMTP nicht erreichbar')
    monkeypatch.setattr(mail, 'send', _kaputt)
    r = _antworten(client, aid)
    assert r.status_code == 502
    seite = r.get_data(as_text=True)
    assert 'konnte nicht gesendet werden' in seite and 'danke für deine Nachricht!' in seite
    assert KontaktAntwort.query.count() == 0
    assert AdminAudit.query.filter_by(aktion='kontakt_antwort').count() == 0
    assert db.session.get(Kontaktanfrage, aid).status == 'neu'


def test_unbekannte_anfrage(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    with mail.record_messages() as ausgehend:
        assert _antworten(client, 999).status_code == 404
    assert not ausgehend


def test_nur_superadmin(client, app, editor):
    aid = _anfrage()
    eingeloggt(client, 'editor_test', 'auch-geheim-123')
    with mail.record_messages() as ausgehend:
        assert _antworten(client, aid).status_code == 403
    assert not ausgehend and KontaktAntwort.query.count() == 0


def test_ohne_csrf_token_wird_nichts_gesendet(app, superadmin):
    app.config['CSRF_ENABLED'] = True
    c = app.test_client()
    aid = _anfrage()
    c.get('/login')
    with c.session_transaction() as s:
        tok = s['_csrf_token']
    c.post('/login', data={'username': 'superadmin_test', 'password': 'sehr-geheim-123', '_csrf': tok})
    with mail.record_messages() as ausgehend:
        assert _antworten(c, aid).status_code == 400
        assert not ausgehend
        r = c.post(f'/admin/kontakt/{aid}/antworten', data={'betreff': 'Re: x', 'text': TEXT, '_csrf': tok})
    assert r.status_code == 302 and len(ausgehend) == 1


def test_loeschen_im_admin_nimmt_antworten_mit(client, app, superadmin):
    aid = _anfrage()
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    _antworten(client, aid)
    client.post('/admin/kontakt', data={'anfrage_id': aid, 'action': 'delete'})
    assert db.session.get(Kontaktanfrage, aid) is None
    assert KontaktAntwort.query.count() == 0


def test_loeschfrist_antworten_gehen_mit_der_anfrage(client, app, superadmin):
    alt, jung = _anfrage(alter_tage=200), _anfrage(alter_tage=100)
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    _antworten(client, alt)   # Antwort selbst ist frisch -- zaehlt trotzdem ab Eingang der Anfrage
    _antworten(client, jung)
    ergebnis = bereinigen()
    assert ergebnis['Kontakt-Antworten'] == 1 and ergebnis['Kontaktanfragen'] == 1
    assert [a.anfrage_id for a in KontaktAntwort.query.all()] == [jung]
    assert db.session.get(Kontaktanfrage, jung) is not None
