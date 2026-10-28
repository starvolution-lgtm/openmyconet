"""Benachrichtigungen aus den Themenraeumen (omn/themen_mails.py, Robby 28.10.2026):
automatisch folgen, Folgen-Knopf, Drosselung bis zum naechsten Besuch, kein Beitragstext
in der Mail, Abbestell-Link ohne Login, Admin-Mail, Schalter."""
import re

from test_themen import _diskussion, _teilnehmer

from omn.extensions import db, mail
from omn.models import ThemenAbo, ThemenTeilnahme

ADMIN = 'admin@openmyconet.test'


def _schreiben(client, d, text):
    with mail.record_messages() as ausgehend:
        client.post(f'/themen/diskussion/{d.id}', data={'text': text, 'sprache': 'de'})
    return ausgehend


def _an(ausgehend, adresse):
    return [m for m in ausgehend if m.recipients == [adresse]]


def test_folgen_drosselung_und_ohne_text(client, app):
    d = _diskussion()
    a = _teilnehmer(client, email='a@example.com', anzeigename='Dr. A')
    raus = _schreiben(client, d, 'Erster Beitrag von A')
    assert ThemenAbo.query.filter_by(nutzer_id=a.id, diskussion_id=d.id, aktiv=True).count() == 1
    assert len(_an(raus, ADMIN)) == 1 and _an(raus, 'a@example.com') == []      # nie an sich selbst

    _teilnehmer(client, email='b@example.com', anzeigename='Dr. B')
    raus = _schreiben(client, d, 'Geheime Messwerte von B')
    an_a = _an(raus, 'a@example.com')
    assert len(an_a) == 1
    m = an_a[0]
    assert 'Dr. B' in m.body and 'Signaturen bei Netzerneuerung' in m.subject
    assert 'Geheime Messwerte' not in m.body and 'Geheime Messwerte' not in m.html     # ohne Beitragstext
    assert m.extra_headers['List-Unsubscribe-Post'] == 'List-Unsubscribe=One-Click'

    # zweiter Beitrag, A war noch nicht da -> keine weitere Mail an A (Admin bekommt jede)
    raus = _schreiben(client, d, 'Noch ein Beitrag von B')
    assert _an(raus, 'a@example.com') == [] and len(_an(raus, ADMIN)) == 1

    # A sieht die Diskussion an -> naechste Mail wieder erlaubt
    with client.session_transaction() as sess:
        sess['nutzer_id'] = a.id
    client.get(f'/themen/diskussion/{d.id}')
    with client.session_transaction() as sess:
        sess['nutzer_id'] = ThemenTeilnahme.query.filter_by(anzeigename='Dr. B').one().nutzer_id
    assert len(_an(_schreiben(client, d, 'Dritter Beitrag'), 'a@example.com')) == 1


def test_abbestell_link_ohne_login(client, app):
    d = _diskussion()
    a = _teilnehmer(client, email='a@example.com')
    _schreiben(client, d, 'Hallo')
    _teilnehmer(client, email='b@example.com', anzeigename='Dr. B')
    m = _an(_schreiben(client, d, 'Antwort'), 'a@example.com')[0]
    link = re.search(r'https?://\S+/themen-folgen-beenden/\S+', m.body).group(0)
    pfad = link.split('://', 1)[1].split('/', 1)[1]
    with client.session_transaction() as sess:
        sess.clear()                                         # ohne Login
    seite = client.get('/' + pfad)
    assert seite.status_code == 200 and 'Unfollow' not in seite.get_data(as_text=True)
    assert ThemenAbo.query.filter_by(nutzer_id=a.id).one().aktiv is True          # GET aendert nichts
    seite = client.post('/' + pfad).get_data(as_text=True)
    assert 'Erledigt' in seite
    assert ThemenAbo.query.filter_by(nutzer_id=a.id).one().aktiv is False
    assert client.get('/themen-folgen-beenden/falsch').status_code == 404


def test_folgen_knopf_und_einstellung(client, app):
    d = _diskussion()
    a = _teilnehmer(client, email='a@example.com')
    seite = client.get(f'/themen/diskussion/{d.id}?lang=de').get_data(as_text=True)
    assert 'E-Mail bei neuen Beiträgen: aus' in seite and '>Folgen<' in seite
    client.post(f'/themen/diskussion/{d.id}/folgen', data={'aktion': 'folgen'})
    assert ThemenAbo.query.filter_by(nutzer_id=a.id).one().aktiv is True
    assert 'Nicht mehr folgen' in client.get(f'/themen/diskussion/{d.id}?lang=de').get_data(as_text=True)
    # global abgeschaltet -> keine Mail trotz Folgen
    client.post('/themen/einstellungen', data={'anzeigename': 'Dr. A'})
    assert ThemenTeilnahme.query.filter_by(nutzer_id=a.id).one().benachrichtigungen is False
    _teilnehmer(client, email='b@example.com', anzeigename='Dr. B')
    assert _an(_schreiben(client, d, 'Hallo'), 'a@example.com') == []


def test_schalter_aus_nur_admin_mail(client, app):
    app.config['THEMEN_BENACHRICHTIGUNG'] = False
    d = _diskussion()
    _teilnehmer(client, email='a@example.com')
    _schreiben(client, d, 'Hallo')
    _teilnehmer(client, email='b@example.com', anzeigename='Dr. B')
    raus = _schreiben(client, d, 'Antwort')
    assert _an(raus, 'a@example.com') == [] and len(_an(raus, ADMIN)) == 1


def test_neue_diskussion_folgt_automatisch_und_admin_mail(client, app):
    from test_themen import _gebiet
    g = _gebiet()
    a = _teilnehmer(client, email='a@example.com')
    with mail.record_messages() as raus:
        client.post(f'/themen/gebiet/{g.id}/diskussion/neu',
                    data={'titel': 'Ganz neues Thema', 'beschreibung': 'Worum es geht', 'sprache': 'de',
                          'trotzdem': '1'})
    assert ThemenAbo.query.filter_by(nutzer_id=a.id, aktiv=True).count() == 1
    assert any('Ganz neues Thema' in m.subject for m in _an(raus, ADMIN))


def test_kontoloeschung_entfernt_abos(client, app):
    d = _diskussion()
    a = _teilnehmer(client, email='a@example.com')
    _schreiben(client, d, 'Hallo')
    db.session.delete(a)
    db.session.commit()
    assert ThemenAbo.query.count() == 0
