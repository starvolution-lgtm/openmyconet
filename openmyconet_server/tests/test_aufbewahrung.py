"""Loeschfristen (omn/aufbewahrung.py): Chat-Verlaeufe + Fehlerprotokoll nach 90 Tagen."""
from datetime import timedelta

from omn.aufbewahrung import bereinigen
from omn.extensions import db
from omn.models import ChatLog, Fehlerprotokoll
from omn.zeit import utcnow


def _anlegen(alter_tage):
    t = utcnow() - timedelta(days=alter_tage)
    db.session.add(ChatLog(message='Frage', answer='Antwort', lang='de', chunks_used='', erstellt_am=t))
    db.session.add(Fehlerprotokoll(zeitpunkt=t, pfad='/x', methode='GET', ip='203.0.113.7',
                                   fehlertyp='ValueError', nachricht='kaputt', traceback=''))
    db.session.commit()


def test_loescht_nur_abgelaufene(app):
    with app.app_context():
        _anlegen(91)   # abgelaufen
        _anlegen(89)   # noch in der Frist
        ergebnis = bereinigen()
        assert ergebnis == {'Chat-Verläufe': 1, 'Fehlerprotokoll': 1}
        assert ChatLog.query.count() == 1
        assert Fehlerprotokoll.query.count() == 1
        # zweiter Lauf: nichts mehr zu tun
        assert bereinigen() == {'Chat-Verläufe': 0, 'Fehlerprotokoll': 0}


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
