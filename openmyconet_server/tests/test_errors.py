"""Testet errors.py: unbehandelte Exceptions werden protokolliert (Fehlerprotokoll-
Tabelle) statt nur zu crashen, HTTPExceptions (404 etc.) bleiben unangetastet."""
from app import app as _flask_app
from errors import _unbehandelte_exception
from extensions import db
from models import Fehlerprotokoll

# Muss beim Modul-Import (Testsammlung) passieren, nicht in einer Testfunktion --
# Flask verbietet app.route() nach dem ersten bedienten Request, und andere
# Tests haben zu dem Zeitpunkt laengst welche bedient.
@_flask_app.route('/__test_boom__')
def _test_boom():
    raise RuntimeError('End-to-End-Testfehler')


def test_normale_404_bleibt_unberuehrt(client):
    r = client.get('/diese-seite-gibt-es-nicht')
    assert r.status_code == 404


def test_unbehandelte_exception_wird_protokolliert(app):
    with app.test_request_context('/irgendeine/route', method='POST'):
        try:
            raise ValueError('kaputt gegangen')
        except ValueError as exc:
            _antwort, status = _unbehandelte_exception(exc)
        assert status == 500
        eintrag = Fehlerprotokoll.query.order_by(Fehlerprotokoll.id.desc()).first()
        assert eintrag is not None
        assert eintrag.fehlertyp == 'ValueError'
        assert eintrag.pfad == '/irgendeine/route'
        assert eintrag.methode == 'POST'
        assert 'kaputt gegangen' in eintrag.nachricht
        assert 'ValueError' in eintrag.traceback


def test_kaputte_session_wird_zurueckgerollt_vor_dem_protokollieren(app):
    # Simuliert eine Session, die durch den urspruenglichen Fehler in einem
    # kaputten Zustand ist -- rollback() muss laufen, bevor der neue Eintrag
    # committet wird, sonst schlaegt auch das Protokollieren fehl.
    with app.test_request_context('/x'):
        db.session.add(Fehlerprotokoll(pfad='/schon-drin', methode='GET'))
        # keine commit() -- absichtlich "dreckige" Session vor dem Handler
        try:
            raise RuntimeError('zweiter Fehler')
        except RuntimeError as exc:
            _unbehandelte_exception(exc)
        alle = Fehlerprotokoll.query.all()
        assert any(e.fehlertyp == 'RuntimeError' for e in alle)


def test_end_to_end_ueber_eine_echte_route(client, app):
    app.config['PROPAGATE_EXCEPTIONS'] = False  # sonst wirft Flask unter TESTING durch
    try:
        resp = client.get('/__test_boom__')
        assert resp.status_code == 500
        with app.app_context():
            eintrag = Fehlerprotokoll.query.filter_by(pfad='/__test_boom__').first()
            assert eintrag is not None
            assert eintrag.fehlertyp == 'RuntimeError'
    finally:
        app.config['PROPAGATE_EXCEPTIONS'] = None
