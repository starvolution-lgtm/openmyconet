"""Oeffentliche Statusseite /status (seit 23.10.2026): nur ok/gestoert/unbekannt,
keine Interna, eigener Cache."""
import pytest

from omn import status_oeffentlich


@pytest.fixture(autouse=True)
def _cache_leeren():
    status_oeffentlich._cache['ergebnisse'] = None
    status_oeffentlich._cache['zeitpunkt'] = 0.0


def test_status_seite_zeigt_dienste(client):
    r = client.get('/status')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    for text in ('Website und Schnittstellen', 'Datenbank', 'E-Mail-Versand', 'Tägliche Datensicherung'):
        assert text in html
    assert 'in Betrieb' in html
    assert r.headers['Cache-Control'] == 'no-cache'
    # keine Interna der Server-Ampel
    for intern in ('PayPal', 'ANTHROPIC', 'journalctl', '/home/omn'):
        assert intern not in html


def test_status_englisch(client):
    assert 'Database' in client.get('/status?lang=en').get_data(as_text=True)


def test_fehlerhafte_pruefung_zeigt_stoerung_ohne_details(client, monkeypatch):
    def kaputt():
        raise RuntimeError('geheimes Detail')
    monkeypatch.setattr(status_oeffentlich, 'PRUEFUNGEN',
                        [('web', lambda: 'ok'), ('db', kaputt)])
    html = client.get('/status').get_data(as_text=True)
    assert 'gestört' in html and 'Mindestens ein Dienst' in html
    assert 'geheimes Detail' not in html


def test_cache_prueft_nur_einmal_pro_minute(client, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(status_oeffentlich, 'PRUEFUNGEN', [('db', lambda: aufrufe.append(1) or 'ok')])
    for _ in range(5):
        client.get('/status')
    assert len(aufrufe) == 1


def test_haengende_mail_ist_stoerung(app):
    from datetime import timedelta

    from omn.extensions import db
    from omn.models import MailQueue
    from omn.zeit import utcnow
    db.session.add(MailQueue(empfaenger='a@example.com', betreff='x', body='y', status='offen',
                             versuche=0, erstellt_am=utcnow() - timedelta(minutes=30)))
    db.session.commit()
    assert status_oeffentlich._mailversand() == 'stoerung'


def test_endgueltig_gescheiterte_mail_ist_keine_stoerung(app):
    from omn.extensions import db
    from omn.models import MailQueue
    db.session.add(MailQueue(empfaenger='weg@example.com', betreff='x', body='y', status='fehler', versuche=5))
    db.session.commit()
    assert status_oeffentlich._mailversand() == 'ok'


def test_unbekannt_ist_keine_stoerung(client, monkeypatch):
    monkeypatch.setattr(status_oeffentlich, 'PRUEFUNGEN', [('web', lambda: 'ok'), ('backup', lambda: 'unbekannt')])
    html = client.get('/status').get_data(as_text=True)
    assert 'Alle Dienste laufen normal' in html and 'unbekannt' in html
