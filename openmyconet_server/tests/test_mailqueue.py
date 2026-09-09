"""omn.mailer.mailqueue_drain: claimt offene Zeilen, sendet ueber EINE
SMTP-Verbindung, wiederholt Fehlversuche bis MAX_VERSUCHE, gibt haengende
Zeilen frei, raeumt alte gesendete weg."""
from datetime import timedelta

import pytest
from flask_mail import Message

from omn.extensions import db, mail
from omn.mailer import MAX_VERSUCHE, mailqueue_drain, mailqueue_einreihen
from omn.models import MailQueue
from omn.zeit import utcnow


@pytest.fixture()
def kein_testing(app):
    # Drain soll wie im Betrieb laufen (mailqueue_einreihen drained sonst schon
    # selbst synchron). record_messages() funktioniert trotzdem, weil
    # MAIL_SUPPRESS_SEND=True aus der TestConfig bleibt.
    app.config['TESTING'] = False
    yield app
    app.config['TESTING'] = True


def _einreihen(app, *empfaenger, betreff='x'):
    with app.test_request_context('/'):
        mailqueue_einreihen([Message(subject=betreff, recipients=list(empfaenger), body='b')])


def test_drain_sendet_und_markiert(kein_testing):
    app = kein_testing
    _einreihen(app, 'a@example.com', 'b@example.com')
    with mail.record_messages() as ausgehend:
        gesendet = mailqueue_drain(app)
    assert gesendet == 2
    assert {m.recipients[0] for m in ausgehend} == {'a@example.com', 'b@example.com'}
    with app.app_context():
        assert MailQueue.query.filter_by(status='offen').count() == 0
        zeilen = MailQueue.query.all()
        assert all(z.status == 'gesendet' and z.gesendet_am and z.claim_am is None for z in zeilen)


def test_drain_ist_leerlauf_fest(kein_testing):
    assert mailqueue_drain(kein_testing) == 0


def test_list_unsubscribe_header_bleibt_erhalten(kein_testing):
    app = kein_testing
    with app.test_request_context('/'):
        msg = Message(subject='rund', recipients=['u@example.com'], body='b',
                      extra_headers={'List-Unsubscribe': '<https://x/abmelden/tok>'})
        mailqueue_einreihen([msg])
    with mail.record_messages() as ausgehend:
        mailqueue_drain(app)
    assert ausgehend[0].extra_headers['List-Unsubscribe'] == '<https://x/abmelden/tok>'


def test_fehlversuch_wird_wiederholt_dann_fehler(kein_testing, monkeypatch):
    app = kein_testing
    _einreihen(app, 'boom@example.com')

    class KaputteConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def send(self, msg): raise RuntimeError('550 abgelehnt')

    monkeypatch.setattr(mail, 'connect', lambda: KaputteConn())

    for erwartet in range(1, MAX_VERSUCHE + 1):
        assert mailqueue_drain(app) == 0
        with app.app_context():
            z = MailQueue.query.one()
            assert z.versuche == erwartet
            assert '550 abgelehnt' in z.letzter_fehler
            assert z.status == ('fehler' if erwartet >= MAX_VERSUCHE else 'offen')

    # 'fehler' wird nicht mehr angefasst
    assert mailqueue_drain(app) == 0


def test_haengende_zeile_wird_freigegeben(kein_testing):
    app = kein_testing
    with app.app_context():
        db.session.add(MailQueue(
            empfaenger='stuck@example.com', betreff='x', body='b',
            status='sendet', claim_am=utcnow() - timedelta(minutes=20)))
        db.session.commit()
    with mail.record_messages() as ausgehend:
        gesendet = mailqueue_drain(app)
    assert gesendet == 1
    assert ausgehend[0].recipients == ['stuck@example.com']


def test_frisch_geclaimte_zeile_bleibt_unberuehrt(kein_testing):
    app = kein_testing
    with app.app_context():
        db.session.add(MailQueue(
            empfaenger='inflight@example.com', betreff='x', body='b',
            status='sendet', claim_am=utcnow() - timedelta(minutes=1)))
        db.session.commit()
    assert mailqueue_drain(app) == 0
    with app.app_context():
        assert MailQueue.query.one().status == 'sendet'


def test_alte_gesendete_werden_aufgeraeumt(kein_testing):
    app = kein_testing
    with app.app_context():
        db.session.add(MailQueue(
            empfaenger='alt@example.com', betreff='x', body='b',
            status='gesendet', gesendet_am=utcnow() - timedelta(days=31)))
        db.session.add(MailQueue(
            empfaenger='neu@example.com', betreff='x', body='b',
            status='gesendet', gesendet_am=utcnow() - timedelta(days=2)))
        db.session.commit()
    mailqueue_drain(app)
    with app.app_context():
        uebrig = [z.empfaenger for z in MailQueue.query.all()]
        assert uebrig == ['neu@example.com']


def test_smtp_verbindung_tot_gibt_zeilen_zurueck(kein_testing, monkeypatch):
    app = kein_testing
    _einreihen(app, 'a@example.com')

    def kein_connect():
        raise OSError('SMTP nicht erreichbar')

    monkeypatch.setattr(mail, 'connect', kein_connect)
    assert mailqueue_drain(app) == 0
    with app.app_context():
        z = MailQueue.query.one()
        assert z.status == 'offen'
        assert z.claim_am is None
