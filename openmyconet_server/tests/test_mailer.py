"""omn.mailer.versende_im_hintergrund: unter TESTING synchron, sonst Thread;
eine wiederverwendete SMTP-Verbindung; leere Liste = no-op."""
import threading

from flask_mail import Message

from omn.extensions import mail
from omn.mailer import versende_im_hintergrund


def test_leere_liste_ist_noop(app):
    with app.test_request_context('/'), mail.record_messages() as ausgehend:
        versende_im_hintergrund([])
    assert ausgehend == []


def test_sendet_alle_nachrichten(app):
    msgs = [Message(subject='x', recipients=[f'u{i}@example.com'], body='b') for i in range(3)]
    with app.test_request_context('/'), mail.record_messages() as ausgehend:
        versende_im_hintergrund(msgs)
    assert {a.recipients[0] for a in ausgehend} == {'u0@example.com', 'u1@example.com', 'u2@example.com'}


def test_unter_testing_synchron_kein_thread(app):
    # Unter TESTING darf KEIN Hintergrund-Thread aufgemacht werden -- sonst
    # werden Tests mit mail.record_messages() nichtdeterministisch.
    vorher = threading.active_count()
    msgs = [Message(subject='x', recipients=['u@example.com'], body='b')]
    with app.test_request_context('/'):
        versende_im_hintergrund(msgs)
    assert threading.active_count() == vorher


def test_ohne_testing_blockiert_nicht(app, monkeypatch):
    # TESTING aus -> Thread; die Nachricht-"Sendung" kuenstlich langsam machen
    # und pruefen, dass der Aufruf trotzdem sofort zurueckkehrt.
    app.config['TESTING'] = False
    langsam = threading.Event()

    class LahmeConn:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def send(self, msg): langsam.wait(2)

    monkeypatch.setattr(mail, 'connect', lambda: LahmeConn())
    try:
        with app.test_request_context('/'):
            versende_im_hintergrund([Message(subject='x', recipients=['u@example.com'], body='b')])
        # kehrt sofort zurueck, obwohl send() 2 s blockieren wuerde
        assert not langsam.is_set()
    finally:
        langsam.set()
        app.config['TESTING'] = True
