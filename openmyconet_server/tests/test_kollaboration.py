"""Tests fuer den Hyphist-Kollaborationsbereich (Aufgaben + Kommentare + Anhaenge)."""
import io
from datetime import datetime, timedelta

from conftest import eingeloggt
from extensions import db, mail
from models import Nutzer, Foerderer, Knoten, Aufgabe, Kommentar, KollaborationAnhang


def _nutzer(app, email='partner@example.com', hyphist=True):
    with app.app_context():
        n = Nutzer(name='Partner', email=email, bestaetigt=True, ist_hyphist=hyphist)
        db.session.add(n)
        db.session.commit()
        return n.id


def _koop(app, email='partner@example.com', status='active', nutzer_id=None, firma='Koop GmbH'):
    with app.app_context():
        f = Foerderer(
            token=f'tok-{firma}', status=status, typ='kooperation', firma=firma,
            beschreibung='Beschreibung der Kooperation.', email=email, betrag=0,
            ansprechpartner='Partner', nutzer_id=nutzer_id,
            status_geaendert_am=datetime.utcnow() - timedelta(days=30),
        )
        db.session.add(f)
        db.session.commit()
        return f.id


def _als_nutzer(client, nutzer_id):
    with client.session_transaction() as sess:
        sess['nutzer_logged_in'] = True
        sess['nutzer_id'] = nutzer_id


def test_partner_sieht_aktive_kooperation_und_legt_aufgabe_an(client, app):
    nid = _nutzer(app)
    kid = _koop(app, nutzer_id=nid)
    _als_nutzer(client, nid)

    resp = client.get('/dashboard/hyphist')
    assert resp.status_code == 200
    assert 'Koop GmbH' in resp.get_data(as_text=True)

    with mail.record_messages() as ausgehend:
        resp = client.post('/dashboard/hyphist', data={
            'foerderer_id': kid, 'action': 'aufgabe_neu',
            'titel': 'Sensor kalibrieren', 'beschreibung': 'bis Freitag',
        })
    assert resp.status_code == 200
    with app.app_context():
        a = Aufgabe.query.filter_by(foerderer_id=kid).one()
        assert a.titel == 'Sensor kalibrieren'
        assert a.erstellt_von == 'partner'
    assert len(ausgehend) == 1  # Team wird benachrichtigt


def test_dashboard_home_leitet_hyphist_in_kooperationsbereich(client, app):
    """Regression: /dashboard (home) leitete mit 500 (NameError _kooperationen),
    weil der Rollen-Redirect eine nicht existierende Hilfsfunktion aufrief."""
    nid = _nutzer(app)
    _koop(app, nutzer_id=nid)
    _als_nutzer(client, nid)

    resp = client.get('/dashboard')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/dashboard/hyphist')

    resp = client.get('/dashboard', follow_redirects=True)
    assert resp.status_code == 200
    assert 'Koop GmbH' in resp.get_data(as_text=True)


def test_dashboard_home_hyphist_ohne_kooperation_landet_in_basis(client, app):
    nid = _nutzer(app)  # ist_hyphist=True, aber keine aktive Kooperation
    _als_nutzer(client, nid)

    resp = client.get('/dashboard')
    assert resp.status_code == 302
    assert resp.headers['Location'].endswith('/dashboard/basis')


def test_partner_kann_nicht_in_fremde_kooperation_schreiben(client, app):
    nid = _nutzer(app, email='a@example.com')
    fremd = _koop(app, email='b@example.com', firma='Fremd GmbH')
    _als_nutzer(client, nid)

    resp = client.post('/dashboard/hyphist', data={
        'foerderer_id': fremd, 'action': 'aufgabe_neu', 'titel': 'X',
    })
    assert resp.status_code == 403


def test_kommentar_mit_anhang_und_download_schutz(client, app):
    nid = _nutzer(app, email='a@example.com')
    kid = _koop(app, email='a@example.com', nutzer_id=nid)
    fremd_nid = _nutzer(app, email='c@example.com')
    _als_nutzer(client, nid)

    resp = client.post('/dashboard/hyphist', data={
        'foerderer_id': kid, 'action': 'kommentar_neu', 'text': 'Log im Anhang',
        'dateien': (io.BytesIO(b'boot ok\nfirmware 1.2'), 'boot.log'),
    }, content_type='multipart/form-data')
    assert resp.status_code == 200

    with app.app_context():
        anhang = KollaborationAnhang.query.one()
        assert anhang.originalname == 'boot.log'
        anhang_id = anhang.id

    # Eigentuemer darf laden
    assert client.get(f'/dashboard/kollaboration/datei/{anhang_id}').status_code == 200

    # Fremder Nutzer nicht
    _als_nutzer(client, fremd_nid)
    assert client.get(f'/dashboard/kollaboration/datei/{anhang_id}').status_code == 403


def test_aktivitaet_verschiebt_verfallsdatum(client, app):
    nid = _nutzer(app)
    kid = _koop(app, nutzer_id=nid)
    _als_nutzer(client, nid)

    client.post('/dashboard/hyphist', data={
        'foerderer_id': kid, 'action': 'kommentar_neu', 'text': 'Lebenszeichen',
    })
    with app.app_context():
        f = Foerderer.query.get(kid)
        assert (datetime.utcnow() - f.status_geaendert_am) < timedelta(minutes=1)


def test_admin_kollaboration_seite_und_aufgabe(client, app, superadmin):
    kid = _koop(app)
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')

    resp = client.get(f'/admin/kollaboration/foerderer/{kid}')
    assert resp.status_code == 200

    with mail.record_messages() as ausgehend:
        resp = client.post(f'/admin/kollaboration/foerderer/{kid}', data={
            'action': 'aufgabe_neu', 'titel': 'Vertrag prüfen',
        })
    assert resp.status_code == 200
    with app.app_context():
        a = Aufgabe.query.filter_by(foerderer_id=kid).one()
        assert a.erstellt_von == 'team'
    assert len(ausgehend) == 1  # Partner wird benachrichtigt


def _knoten(app, nutzer_id, knoten_id='DE-001'):
    with app.app_context():
        k = Knoten(knoten_id=knoten_id, nutzer_id=nutzer_id, substrat='Waldboden')
        db.session.add(k)
        db.session.commit()
        return k.id


def test_knotenbetreiber_aufgabe_und_kommentar_pro_knoten(client, app):
    nid = _nutzer(app, email='kb@example.com', hyphist=False)
    k1 = _knoten(app, nid, 'DE-001')
    k2 = _knoten(app, nid, 'DE-002')
    _als_nutzer(client, nid)

    resp = client.get('/dashboard/knotenbetreiber')
    assert resp.status_code == 200
    assert 'DE-001' in resp.get_data(as_text=True)

    client.post('/dashboard/knotenbetreiber', data={
        'knoten_pk': k1, 'action': 'aufgabe_neu', 'titel': 'Firmware 1.3 flashen',
    })
    with app.app_context():
        a = Aufgabe.query.one()
        assert a.knoten_id == k1 and a.foerderer_id is None
        assert a.erstellt_von == 'partner'

    # Aufgabe von Knoten 1 darf nicht über Knoten 2 umgeschaltet werden
    with app.app_context():
        aid = Aufgabe.query.one().id
    resp = client.post('/dashboard/knotenbetreiber', data={
        'knoten_pk': k2, 'action': 'aufgabe_toggle', 'aufgabe_id': aid,
    })
    assert resp.status_code == 403


def test_knotenbetreiber_fremder_knoten_403(client, app):
    nid = _nutzer(app, email='a@example.com', hyphist=False)
    other = _nutzer(app, email='b@example.com', hyphist=False)
    fremd_k = _knoten(app, other, 'DE-099')
    _als_nutzer(client, nid)
    resp = client.post('/dashboard/knotenbetreiber', data={
        'knoten_pk': fremd_k, 'action': 'aufgabe_neu', 'titel': 'X',
    })
    assert resp.status_code == 403


def test_admin_kollaboration_knoten(client, app, superadmin):
    nid = _nutzer(app, email='kb2@example.com', hyphist=False)
    kid = _knoten(app, nid, 'DE-050')
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')

    resp = client.get(f'/admin/kollaboration/knoten/{kid}')
    assert resp.status_code == 200
    assert 'DE-050' in resp.get_data(as_text=True)

    with mail.record_messages() as ausgehend:
        client.post(f'/admin/kollaboration/knoten/{kid}', data={
            'action': 'kommentar_neu', 'text': 'Bitte Sensor prüfen',
        })
    with app.app_context():
        c = Kommentar.query.filter_by(knoten_id=kid).one()
        assert c.autor == 'team'
    assert len(ausgehend) == 1  # Betreiber wird benachrichtigt


def test_admin_kollaboration_nur_fuer_kooperation(client, app, superadmin):
    with app.app_context():
        f = Foerderer(token='t-fx', status='active', typ='foerderer', firma='Zahlfirma',
                      beschreibung='x', email='z@example.com', betrag=50)
        db.session.add(f)
        db.session.commit()
        fid = f.id
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    assert client.get(f'/admin/kollaboration/foerderer/{fid}').status_code == 404
