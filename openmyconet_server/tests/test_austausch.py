"""Tests fuer den fachlichen Austausch mit eingeladenen Fachkontakten
(docs/austausch_phase1_plan.md). Schritt 1: Modell + Kontext-Spalten.
Schritt 2: Kollaborationskern (Kontext, Benachrichtigungen, Zugriff, Dateien)."""
import io
import os
import re
from datetime import datetime, timedelta, timezone

from werkzeug.datastructures import FileStorage

from conftest import eingeloggt
from omn import kollaboration
from omn.extensions import db, mail
from omn.models import Austausch, Aufgabe, Kommentar, Foerderer, KollaborationAnhang, Nutzer
from omn.site_live import _aktive_foerderer

# Begriffe, die in nichts auftauchen duerfen, was ein Fachkontakt zu sehen bekommt
# (Abnahmekriterium 2 + "Fachkontakt" nur intern).
VERBOTEN = re.compile(r'f(ö|oe)rder|paypal|sporist|spende|zahlung|hyphist|kooperation|fachkontakt', re.I)


def _austausch(**felder):
    werte = dict(titel='Elektrophysiologie an Myzel', name='Dr. Test', email='fach@example.com')
    werte.update(felder)
    a = Austausch(**werte)
    db.session.add(a)
    db.session.commit()
    return a


def test_standardwerte(app):
    a = _austausch()
    assert a.status == 'vorbereitet'
    assert a.anrede == 'formell'
    assert a.sprache == 'de'
    assert a.institution == ''
    assert a.nutzer_id is None
    assert a.code_fehlversuche == 0 and a.codes_angefordert == 0
    # Zeitpunkte werden gesetzt (tz-aware erst auf PostgreSQL wieder lesbar; SQLite
    # liefert nach dem Neuladen naive Werte -- das behandeln die Fristen in Schritt 5)
    assert a.erstellt_am is not None
    assert a.letzte_aktivitaet is not None
    assert a.status_geaendert_am is not None


def test_aufgaben_und_kommentare_haengen_am_austausch_und_werden_mitgeloescht(app):
    a = _austausch()
    aufgabe = Aufgabe(titel='Messprotokoll abstimmen', erstellt_von='team', austausch_id=a.id)
    db.session.add(aufgabe)
    db.session.flush()
    db.session.add(Kommentar(text='Allgemein', autor='partner', austausch_id=a.id))
    db.session.add(Kommentar(text='Zur Aufgabe', autor='team', austausch_id=a.id, aufgabe_id=aufgabe.id))
    db.session.commit()

    assert [x.titel for x in a.aufgaben] == ['Messprotokoll abstimmen']
    assert len(a.kommentare) == 2
    assert aufgabe.austausch is a

    db.session.delete(a)
    db.session.commit()
    assert Aufgabe.query.count() == 0
    assert Kommentar.query.count() == 0


def test_kontoloeschung_loest_nur_die_verknuepfung(app):
    n = Nutzer(name='Fach', email='fach@example.com', bestaetigt=True)
    db.session.add(n)
    db.session.commit()
    a = _austausch(nutzer_id=n.id, status='aktiv')
    assert n.austausche == [a]

    db.session.delete(n)
    db.session.commit()
    a = db.session.get(Austausch, a.id)
    assert a is not None
    assert a.nutzer_id is None


def test_austausch_erscheint_nicht_bei_foerderern(app):
    """Kern der Tabellen-Entscheidung: ein aktiver Austausch taucht nie in der
    oeffentlichen Foerderer-/Kooperationsliste auf."""
    _austausch(status='aktiv')
    assert _aktive_foerderer() == []
    assert Foerderer.query.count() == 0


# --- Schritt 2: Kollaborationskern -------------------------------------------

def _fachkontakt(email='fach@example.com', sprache='de', anrede='formell', status='aktiv', nutzer_sprache=None):
    n = Nutzer(name='Fach', email=email, bestaetigt=True, sprache=nutzer_sprache or sprache)
    db.session.add(n)
    db.session.commit()
    a = _austausch(email=email, sprache=sprache, anrede=anrede, status=status, nutzer_id=n.id)
    return n, a


def _mailtext(msg):
    return f'{msg.subject}\n{msg.body}\n{msg.html}'


def test_team_aufgabe_benachrichtigt_fachkontakt_formell_deutsch(app):
    _, a = _fachkontakt()
    with mail.record_messages() as ausgehend:
        kollaboration.aufgabe_anlegen(a, 'Messprotokoll abstimmen', '', 'team')
    assert len(ausgehend) == 1
    m = ausgehend[0]
    assert m.recipients == ['fach@example.com']
    assert m.subject == 'OpenMycoNet — Neue Aufgabe: Messprotokoll abstimmen'
    assert 'in Ihrem Austausch „Elektrophysiologie an Myzel“' in m.body
    assert 'Sie erhalten diese Nachricht' in m.body
    assert '/austausch' in m.body
    assert not VERBOTEN.search(_mailtext(m))


def test_anrede_informell_und_sprache_des_kontos(app):
    # Einladung auf Deutsch, Konto inzwischen auf Spanisch -> Konto gewinnt
    _, a = _fachkontakt(anrede='informell', sprache='de', nutzer_sprache='es')
    with mail.record_messages() as ausgehend:
        kollaboration.kommentar_anlegen(a, 'Gibt es Rohdaten zur Messung?', 'team')
    m = ausgehend[0]
    assert m.subject == 'OpenMycoNet — Nuevo comentario: Gibt es Rohdaten zur Messung?'
    assert 'en tu intercambio' in m.body
    assert 'Recibes este mensaje' in m.body
    assert '<html lang="es">' in m.html
    assert 'El equipo de OpenMycoNet' in m.html
    assert not VERBOTEN.search(_mailtext(m))


def test_alle_sprachen_formell_ohne_verbotene_begriffe(app):
    faelle = [('de', 'Ihrem'), ('en', 'your exchange'), ('nl', 'uw uitwisseling'),
              ('fr', 'votre échange'), ('es', 'su intercambio')]
    for i, (lang, erwartet) in enumerate(faelle):
        _, a = _fachkontakt(email=f'f{i}@example.com', sprache=lang)
        with mail.record_messages() as ausgehend:
            kollaboration.aufgabe_anlegen(a, 'Titel', '', 'team')
        assert erwartet in ausgehend[0].body, lang
        assert not VERBOTEN.search(_mailtext(ausgehend[0])), lang


def test_keine_mail_an_fachkontakt_vor_dem_einloesen(app):
    a = _austausch(status='eingeladen')
    with mail.record_messages() as ausgehend:
        kollaboration.aufgabe_anlegen(a, 'Vorbereitung', '', 'team')
    assert ausgehend == []


def test_beitrag_des_fachkontakts_benachrichtigt_team(app):
    _, a = _fachkontakt()
    with mail.record_messages() as ausgehend:
        kollaboration.kommentar_anlegen(a, 'Hier meine Daten', 'partner')
    m = ausgehend[0]
    assert m.recipients == ['admin@openmyconet.test']
    assert f'/admin/austausch/{a.id}' in m.body
    assert 'Neuer Kommentar: Hier meine Daten' in m.body


def test_aktivitaet_setzt_letzte_aktivitaet(app):
    _, a = _fachkontakt()
    a.letzte_aktivitaet = datetime.now(timezone.utc) - timedelta(days=400)
    db.session.commit()
    kollaboration.aufgabe_anlegen(a, 'Neu', '', 'partner')
    neu = db.session.get(Austausch, a.id).letzte_aktivitaet
    if neu.tzinfo is None:  # SQLite liefert naiv zurueck
        neu = neu.replace(tzinfo=timezone.utc)
    assert datetime.now(timezone.utc) - neu < timedelta(minutes=1)


def test_status_wechsel_findet_austausch_kontext(app):
    _, a = _fachkontakt()
    aufgabe = kollaboration.aufgabe_anlegen(a, 'Abschliessen', '', 'team')
    with mail.record_messages() as ausgehend:
        kollaboration.aufgabe_status_wechseln(aufgabe, 'team')
    assert aufgabe.status == 'erledigt'
    assert ausgehend[0].subject == 'OpenMycoNet — Aufgabe erledigt: Abschliessen'


def test_zugriff_nur_ueber_nutzer_id_und_status_aktiv(app):
    n, a = _fachkontakt()
    assert kollaboration.austausch_bereiche_von(n) == [a]
    assert kollaboration.darf_austausch_sehen(n, a)

    # gleiche E-Mail, aber nicht verknuepft -> kein Zugriff (kein E-Mail-Fallback)
    fremd = _austausch(email='fach@example.com', status='aktiv', titel='Fremd')
    assert fremd not in kollaboration.austausch_bereiche_von(n)
    assert not kollaboration.darf_austausch_sehen(n, fremd)

    for status in ('vorbereitet', 'eingeladen', 'beendet', 'gesperrt'):
        a.status = status
        db.session.commit()
        assert kollaboration.austausch_bereiche_von(n) == []
        assert not kollaboration.darf_austausch_sehen(n, a)


def _anhang_kommentar(kontext, wer='partner'):
    datei = FileStorage(stream=io.BytesIO(b'messwerte 1 2 3'), filename='messung.csv')
    k, fehler = kollaboration.kommentar_anlegen(kontext, 'Mit Anhang', wer, dateien=[datei])
    assert fehler == []
    return k.anhaenge[0]


def test_anhang_sichtbarkeit_im_austausch(app):
    n, a = _fachkontakt()
    anhang = _anhang_kommentar(a)
    assert kollaboration.anhang_sichtbar_fuer_nutzer(anhang, n)

    andere = Nutzer(name='Andere', email='andere@example.com', bestaetigt=True)
    db.session.add(andere)
    db.session.commit()
    assert not kollaboration.anhang_sichtbar_fuer_nutzer(anhang, andere)

    a.status = 'gesperrt'
    db.session.commit()
    assert not kollaboration.anhang_sichtbar_fuer_nutzer(anhang, n)


def test_download_route_fuer_austausch_anhang(client, app):
    n, a = _fachkontakt()
    anhang = _anhang_kommentar(a)
    with client.session_transaction() as sess:
        sess['nutzer_logged_in'] = True
        sess['nutzer_id'] = n.id
    resp = client.get(f'/dashboard/kollaboration/datei/{anhang.id}')
    assert resp.status_code == 200
    assert resp.data == b'messwerte 1 2 3'


def test_dateien_eines_austauschs_werden_beim_loeschen_entfernt(app):
    _, a = _fachkontakt()
    anhang = _anhang_kommentar(a)
    pfad = kollaboration.anhang_pfad(anhang)
    assert os.path.exists(pfad)

    pfade = kollaboration.kontext_anhang_pfade(a)
    assert pfade == [pfad]
    db.session.delete(a)
    db.session.commit()
    assert kollaboration.dateien_entfernen(pfade) == 1
    assert not os.path.exists(pfad)
    assert KollaborationAnhang.query.count() == 0
    # zweiter Aufruf: fehlende Datei ist kein Fehler
    assert kollaboration.dateien_entfernen(pfade) == 0


def test_bestand_foerderer_loeschen_entfernt_auch_dateien(client, app, superadmin):
    f = Foerderer(token='tok-koop', status='active', typ='kooperation', firma='Koop GmbH',
                  beschreibung='Beschreibung der Kooperation.', email='koop@example.com', betrag=0)
    db.session.add(f)
    db.session.commit()
    pfad = kollaboration.anhang_pfad(_anhang_kommentar(f))
    assert os.path.exists(pfad)

    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    resp = client.post('/admin/foerderer', data={'foerderer_id': f.id, 'action': 'delete'})
    assert resp.status_code == 200
    assert Foerderer.query.count() == 0
    assert not os.path.exists(pfad)


# --- Schritt 3: Admin --------------------------------------------------------

FORMULAR = {
    'titel': 'Elektrische Signaturen', 'name': 'Dr. Muster', 'email': 'Muster@Example.com',
    'institution': '', 'sprache': 'fr', 'anrede': 'formell',
    'themenueberblick': 'Wir sprechen über Messreihen.', 'persoenliche_einleitung': '',
    'linkedin_url': 'https://www.linkedin.com/in/muster', 'gespraech_begonnen_am': '2026-10-01',
    'vorgeschichte_notiz': 'INTERN-NOTIZ-MARKER',
}


def _admin(client):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')


def test_admin_legt_austausch_an_ohne_mail(client, app, superadmin):
    _admin(client)
    with mail.record_messages() as ausgehend:
        resp = client.post('/admin/austausch/neu', data=FORMULAR)
    assert resp.status_code == 302
    a = Austausch.query.one()
    assert a.status == 'vorbereitet'
    assert a.email == 'muster@example.com'
    assert a.institution == ''
    assert a.sprache == 'fr' and a.anrede == 'formell'
    assert a.gespraech_begonnen_am.isoformat() == '2026-10-01'
    assert a.nutzer_id is None
    assert ausgehend == []  # Vorbereiten verschickt nichts

    seite = client.get(f'/admin/austausch/{a.id}').get_data(as_text=True)
    assert 'INTERN-NOTIZ-MARKER' in seite
    assert 'https://www.linkedin.com/in/muster' in seite
    liste = client.get('/admin/austausch').get_data(as_text=True)
    assert 'Elektrische Signaturen' in liste


def test_admin_formular_prueft_eingaben(client, app, superadmin):
    _admin(client)
    falsch = dict(FORMULAR, titel='', email='keine-mail', linkedin_url='javascript:alert(1)',
                  gespraech_begonnen_am='31.12.')
    seite = client.post('/admin/austausch/neu', data=falsch).get_data(as_text=True)
    assert 'Bitte einen Titel' in seite
    assert 'E-Mail-Adresse ist ungültig' in seite
    assert 'https://' in seite
    assert 'Gesprächsbeginns ist ungültig' in seite
    assert Austausch.query.count() == 0


def test_admin_bearbeiten(client, app, superadmin):
    a = _austausch()
    _admin(client)
    resp = client.post(f'/admin/austausch/{a.id}/bearbeiten', data=dict(FORMULAR, anrede='informell',
                                                                     linkedin_url='', vorgeschichte_notiz=''))
    assert resp.status_code == 302
    a = db.session.get(Austausch, a.id)
    assert a.anrede == 'informell'
    assert a.linkedin_url is None and a.vorgeschichte_notiz is None  # leer -> NULL wie nach Frist F3


def test_admin_arbeitsbereich_aufgabe_und_kommentar(client, app, superadmin):
    _, a = _fachkontakt()
    _admin(client)
    with mail.record_messages() as ausgehend:
        resp = client.post(f'/admin/austausch/{a.id}', data={'action': 'aufgabe_neu', 'titel': 'Daten teilen'})
        client.post(f'/admin/austausch/{a.id}', data={'action': 'kommentar_neu', 'text': 'Hallo'})
    assert resp.status_code == 200
    assert Aufgabe.query.filter_by(austausch_id=a.id).count() == 1
    assert Kommentar.query.filter_by(austausch_id=a.id).count() == 1
    assert len(ausgehend) == 2  # Fachkontakt wird benachrichtigt
    seite = client.get(f'/admin/austausch/{a.id}').get_data(as_text=True)
    assert 'zurück zur Übersicht „Fachlicher Austausch“' in seite
    assert 'Förderer-/Kooperationsverwaltung' not in seite


def test_admin_status_sperren_beenden_entsperren(client, app, superadmin):
    n, a = _fachkontakt()
    _admin(client)
    client.post(f'/admin/austausch/{a.id}/sperren')
    assert db.session.get(Austausch, a.id).status == 'gesperrt'
    assert kollaboration.austausch_bereiche_von(n) == []
    client.post(f'/admin/austausch/{a.id}/entsperren')
    assert db.session.get(Austausch, a.id).status == 'aktiv'
    client.post(f'/admin/austausch/{a.id}/beenden')
    assert db.session.get(Austausch, a.id).status == 'beendet'

    ohne_konto = _austausch(status='gesperrt', titel='Ohne Konto', einladung_token_hash='x' * 64)
    client.post(f'/admin/austausch/{ohne_konto.id}/entsperren')
    ohne_konto = db.session.get(Austausch, ohne_konto.id)
    assert ohne_konto.status == 'vorbereitet'
    assert ohne_konto.einladung_token_hash is None  # alte Einladung gilt nicht weiter


def test_admin_aktionen_im_audit_log(client, app, superadmin):
    from omn.models import AdminAudit
    _, a = _fachkontakt()
    _admin(client)
    client.post(f'/admin/austausch/{a.id}/sperren')
    client.post(f'/admin/austausch/{a.id}/entsperren')
    aktionen = [x.aktion for x in AdminAudit.query.all()]
    assert 'austausch_gesperrt' in aktionen and 'austausch_entsperrt' in aktionen


def test_inaktivitaet_nur_markieren(client, app, superadmin):
    """Frist F2: nach 12 Monaten ohne Aktivitaet nur Hinweis, keine Sperre."""
    from omn import austausch as aus
    _, a = _fachkontakt()
    a.letzte_aktivitaet = datetime.now(timezone.utc) - timedelta(days=400)
    db.session.commit()
    assert aus.inaktiv_zu_pruefen(a)
    _admin(client)
    liste = client.get('/admin/austausch?filter=pruefen').get_data(as_text=True)
    assert 'Prüfen – 12 Monate ohne Aktivität' in liste
    assert db.session.get(Austausch, a.id).status == 'aktiv'  # nichts gesperrt

    client.post(f'/admin/austausch/{a.id}/geprueft')
    assert not aus.inaktiv_zu_pruefen(db.session.get(Austausch, a.id))
    liste = client.get('/admin/austausch?filter=pruefen').get_data(as_text=True)
    assert 'Nichts zur Prüfung' in liste


def test_loeschsperre_nur_mit_grund_und_zukunftsdatum(client, app, superadmin):
    a = _austausch()
    _admin(client)
    client.post(f'/admin/austausch/{a.id}/loeschsperre', data={'bis': '2099-01-01', 'grund': ''})
    assert db.session.get(Austausch, a.id).loeschsperre_bis is None
    client.post(f'/admin/austausch/{a.id}/loeschsperre', data={'bis': '2000-01-01', 'grund': 'Nachweis'})
    assert db.session.get(Austausch, a.id).loeschsperre_bis is None
    client.post(f'/admin/austausch/{a.id}/loeschsperre', data={'bis': '2099-01-01', 'grund': 'Nachweis'})
    a = db.session.get(Austausch, a.id)
    assert a.loeschsperre_bis.isoformat() == '2099-01-01' and a.loeschsperre_grund == 'Nachweis'
    client.post(f'/admin/austausch/{a.id}/loeschsperre', data={'aufheben': '1'})
    a = db.session.get(Austausch, a.id)
    assert a.loeschsperre_bis is None and a.loeschsperre_grund == ''


def test_admin_loescht_sofort_mit_dateien_und_konto(client, app, superadmin):
    n, a = _fachkontakt()
    pfad = kollaboration.anhang_pfad(_anhang_kommentar(a))
    _admin(client)
    resp = client.post(f'/admin/austausch/{a.id}/loeschen', data={'konto_mitloeschen': '1'})
    assert resp.status_code == 302
    assert Austausch.query.count() == 0
    assert Kommentar.query.count() == 0
    assert not os.path.exists(pfad)
    assert db.session.get(Nutzer, n.id) is None


def test_konto_mit_anderen_bezuegen_bleibt(client, app, superadmin):
    n, a = _fachkontakt()
    n.ist_sporist = True
    db.session.commit()
    _admin(client)
    client.post(f'/admin/austausch/{a.id}/loeschen', data={'konto_mitloeschen': '1'})
    assert Austausch.query.count() == 0
    assert db.session.get(Nutzer, n.id) is not None


def test_admin_austausch_nur_fuer_superadmin(client, app, editor):
    a = _austausch()
    eingeloggt(client, 'editor_test', 'auch-geheim-123')
    assert client.get('/admin/austausch').status_code == 403
    assert client.get(f'/admin/austausch/{a.id}').status_code == 403
    assert client.post(f'/admin/austausch/{a.id}/loeschen').status_code == 403
    assert Austausch.query.count() == 1


def test_bestand_kooperation_admin_seite_unveraendert(client, app, superadmin):
    f = Foerderer(token='tok-k3', status='active', typ='kooperation', firma='Koop GmbH',
                  beschreibung='Beschreibung der Kooperation.', email='k@example.com', betrag=0)
    db.session.add(f)
    db.session.commit()
    _admin(client)
    seite = client.get(f'/admin/kollaboration/foerderer/{f.id}').get_data(as_text=True)
    assert 'Förderer-/Kooperationsverwaltung' in seite
    assert 'Fachkontakt' not in seite


def test_bestand_kooperationsmail_unveraendert(app):
    """Regression: die Mails der Kooperationen behalten Wortlaut und Betreff."""
    n = Nutzer(name='Partner', email='partner@example.com', bestaetigt=True, ist_hyphist=True)
    db.session.add(n)
    db.session.commit()
    f = Foerderer(token='tok-k2', status='active', typ='kooperation', firma='Koop GmbH',
                  beschreibung='Beschreibung der Kooperation.', email='partner@example.com',
                  betrag=0, nutzer_id=n.id)
    db.session.add(f)
    db.session.commit()
    with mail.record_messages() as ausgehend:
        aufgabe = kollaboration.aufgabe_anlegen(f, 'Vertrag prüfen', '', 'team')
        kollaboration.aufgabe_status_wechseln(aufgabe, 'team')
        kollaboration.aufgabe_status_wechseln(aufgabe, 'team')
        kollaboration.kommentar_anlegen(f, 'Kurzer Hinweis', 'team')
    assert [m.subject for m in ausgehend] == [
        'OpenMycoNet — Neue Aufgabe: Vertrag prüfen',
        'OpenMycoNet — Aufgabe erledigt: Vertrag prüfen',
        'OpenMycoNet — Aufgabe wieder geoeffnet: Vertrag prüfen',
        'OpenMycoNet — Neuer Kommentar: Kurzer Hinweis',
    ]
    assert 'Kooperation "Koop GmbH"' in ausgehend[0].body
    assert '<html lang="de">' in ausgehend[0].html
    assert 'Das OpenMycoNet-Team' in ausgehend[0].html
