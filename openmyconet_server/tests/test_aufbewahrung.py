"""Loeschfristen (omn/aufbewahrung.py): Chat-Verlaeufe + Fehlerprotokoll 90 Tage,
Kontaktanfragen 6 Monate ab Eingang, abgelehnte Bewerbungen 6 Monate nach der Absage."""
from datetime import timedelta

from conftest import eingeloggt
from omn.aufbewahrung import bereinigen
from omn.extensions import db
from omn.models import Bewerbung, ChatLog, Fehlerprotokoll, Kontaktanfrage
from omn.zeit import utcnow

NICHTS = {'Chat-Verläufe': 0, 'Fehlerprotokoll': 0, 'Kontaktanfragen': 0, 'abgelehnte Bewerbungen': 0,
          'Kontakt-Versandlog': 0}


def _anlegen(alter_tage):
    t = utcnow() - timedelta(days=alter_tage)
    db.session.add(ChatLog(message='Frage', answer='Antwort', lang='de', chunks_used='', erstellt_am=t))
    db.session.add(Fehlerprotokoll(zeitpunkt=t, pfad='/x', methode='GET', ip='203.0.113.7',
                                   fehlertyp='ValueError', nachricht='kaputt', traceback=''))
    db.session.add(Kontaktanfrage(name='A', email='a@example.com', anliegen='frage', nachricht='Hallo',
                                  status='erledigt', ip='203.0.113.7', erstellt_am=t))
    db.session.commit()


def _bewerbung(status, eingang_tage, entschieden_tage=None):
    jetzt = utcnow()
    b = Bewerbung(name='B', email=f'{status}-{eingang_tage}-{entschieden_tage}@example.com', status=status,
                  erstellt_am=jetzt - timedelta(days=eingang_tage),
                  status_geaendert_am=None if entschieden_tage is None else jetzt - timedelta(days=entschieden_tage))
    db.session.add(b)
    db.session.commit()
    return b.email


def test_loescht_nur_abgelaufene(app):
    with app.app_context():
        _anlegen(200)  # alles abgelaufen
        _anlegen(100)  # Chat + Fehler abgelaufen (90 Tage), Kontakt noch drin (6 Monate)
        _anlegen(89)   # alles noch in der Frist
        ergebnis = bereinigen()
        assert ergebnis == {'Chat-Verläufe': 2, 'Fehlerprotokoll': 2, 'Kontaktanfragen': 1,
                            'abgelehnte Bewerbungen': 0, 'Kontakt-Versandlog': 0}
        assert ChatLog.query.count() == 1
        assert Fehlerprotokoll.query.count() == 1
        assert Kontaktanfrage.query.count() == 2
        # zweiter Lauf: nichts mehr zu tun
        assert bereinigen() == NICHTS


def test_bewerbungen_nur_absagen_nach_der_entscheidung(app):
    with app.app_context():
        weg_1 = _bewerbung('abgelehnt', eingang_tage=400, entschieden_tage=200)
        weg_2 = _bewerbung('abgelehnt', eingang_tage=200)                        # Alt-Zeile: ab Eingang
        bleibt = [
            _bewerbung('abgelehnt', eingang_tage=400, entschieden_tage=30),     # Absage erst kuerzlich
            _bewerbung('abgelehnt', eingang_tage=100),                          # Alt-Zeile, junger Eingang
            _bewerbung('angenommen', eingang_tage=400, entschieden_tage=300),   # Betreiber: bleibt
            _bewerbung('warteliste', eingang_tage=400, entschieden_tage=300),
            _bewerbung('neu', eingang_tage=400),
        ]
        assert bereinigen()['abgelehnte Bewerbungen'] == 2
        emails = {b.email for b in Bewerbung.query.all()}
        assert emails == set(bleibt)
        assert weg_1 not in emails and weg_2 not in emails


def test_admin_statuswechsel_setzt_zeitpunkt(client, app, superadmin):
    with app.app_context():
        _bewerbung('neu', eingang_tage=10)
        b_id = Bewerbung.query.one().id
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    client.post('/admin/bewerbungen', data={'bewerbung_id': b_id, 'status': 'abgelehnt'})
    with app.app_context():
        b = db.session.get(Bewerbung, b_id)
        assert b.status == 'abgelehnt'
        assert b.status_geaendert_am is not None
        assert utcnow() - b.status_geaendert_am < timedelta(minutes=1)


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
