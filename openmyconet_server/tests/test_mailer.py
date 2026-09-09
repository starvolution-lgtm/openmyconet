"""omn.mailer.mailqueue_einreihen: legt je Empfaenger eine MailQueue-Zeile an,
kein Hintergrund-Thread. Unter TESTING wird direkt synchron gedrained, damit
mail.record_messages() deterministisch bleibt."""
import threading

from flask_mail import Message

from omn.extensions import mail
from omn.mailer import mailqueue_einreihen
from omn.models import MailQueue


def test_leere_liste_ist_noop(app):
    with app.test_request_context('/'), mail.record_messages() as ausgehend:
        mailqueue_einreihen([])
    assert ausgehend == []
    with app.app_context():
        assert MailQueue.query.count() == 0


def test_sendet_alle_nachrichten(app):
    msgs = [Message(subject='x', recipients=[f'u{i}@example.com'], body='b') for i in range(3)]
    with app.test_request_context('/'), mail.record_messages() as ausgehend:
        mailqueue_einreihen(msgs)
    assert {a.recipients[0] for a in ausgehend} == {'u0@example.com', 'u1@example.com', 'u2@example.com'}
    with app.app_context():
        assert MailQueue.query.filter_by(status='gesendet').count() == 3


def test_eine_zeile_je_empfaenger(app):
    msg = Message(subject='rund', recipients=['a@example.com', 'b@example.com'], body='hallo')
    with app.test_request_context('/'):
        mailqueue_einreihen([msg])
    with app.app_context():
        assert sorted(z.empfaenger for z in MailQueue.query.all()) == ['a@example.com', 'b@example.com']


def test_unter_testing_kein_thread(app):
    # Unter TESTING darf KEIN Hintergrund-Thread aufgemacht werden -- sonst
    # werden Tests mit mail.record_messages() nichtdeterministisch.
    vorher = threading.active_count()
    msgs = [Message(subject='x', recipients=['u@example.com'], body='b')]
    with app.test_request_context('/'):
        mailqueue_einreihen(msgs)
    assert threading.active_count() == vorher


def test_ohne_testing_kein_versand_im_request(app, monkeypatch):
    # TESTING aus -> einreihen schreibt nur Zeilen und kehrt sofort zurueck,
    # nichts wird im Request gesendet. Der Drain (Cron) macht das spaeter.
    app.config['TESTING'] = False
    versucht = threading.Event()

    class LahmeConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def send(self, msg): versucht.set()

    monkeypatch.setattr(mail, 'connect', lambda: LahmeConn())
    try:
        with app.test_request_context('/'):
            mailqueue_einreihen([Message(subject='x', recipients=['u@example.com'], body='b')])
        assert not versucht.is_set()
        with app.app_context():
            assert MailQueue.query.filter_by(status='offen').count() == 1
    finally:
        app.config['TESTING'] = True
