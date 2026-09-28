"""Loeschfristen (omn/aufbewahrung.py): Chat-Verlaeufe + Fehlerprotokoll nach 90 Tagen."""
from datetime import timedelta

from omn.aufbewahrung import bereinigen
from omn.extensions import db
from omn.models import ChatLog, Fehlerprotokoll, Kontaktanfrage
from omn.zeit import utcnow


def _anlegen(alter_tage):
    t = utcnow() - timedelta(days=alter_tage)
    db.session.add(ChatLog(message='Frage', answer='Antwort', lang='de', chunks_used='', erstellt_am=t))
    db.session.add(Fehlerprotokoll(zeitpunkt=t, pfad='/x', methode='GET', ip='203.0.113.7',
                                   fehlertyp='ValueError', nachricht='kaputt', traceback=''))
    db.session.add(Kontaktanfrage(name='A', email='a@example.com', anliegen='frage', nachricht='Hallo',
                                  status='erledigt', ip='203.0.113.7', erstellt_am=t))
    db.session.commit()


def test_loescht_nur_abgelaufene(app):
    with app.app_context():
        _anlegen(200)  # alles abgelaufen
        _anlegen(100)  # Chat + Fehler abgelaufen (90 Tage), Kontakt noch drin (6 Monate)
        _anlegen(89)   # alles noch in der Frist
        ergebnis = bereinigen()
        assert ergebnis == {'Chat-Verläufe': 2, 'Fehlerprotokoll': 2, 'Kontaktanfragen': 1}
        assert ChatLog.query.count() == 1
        assert Fehlerprotokoll.query.count() == 1
        assert Kontaktanfrage.query.count() == 2
        # zweiter Lauf: nichts mehr zu tun
        assert bereinigen() == {'Chat-Verläufe': 0, 'Fehlerprotokoll': 0, 'Kontaktanfragen': 0}


def test_cli(app):
    with app.app_context():
        _anlegen(200)
    runner = app.test_cli_runner()
    r = runner.invoke(args=['aufbewahrung-bereinigen'])
    assert r.exit_code == 0, r.output
    assert 'Chat-Verläufe: 1 gelöscht' in r.output
    # --still (Standard): ohne Loeschungen keine Ausgabe (Cron-Log bleibt leer)
    r = runner.invoke(args=['aufbewahrung-bereinigen'])
    assert r.exit_code == 0 and r.output == ''
    with app.app_context():
        assert ChatLog.query.count() == 0 and Fehlerprotokoll.query.count() == 0
        assert Kontaktanfrage.query.count() == 0
