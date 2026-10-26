"""Tests fuer den fachlichen Austausch mit eingeladenen Fachkontakten
(docs/austausch_phase1_plan.md). Schritt 1: Modell + Kontext-Spalten.
Schritt 2: Kollaborationskern (Kontext, Benachrichtigungen, Zugriff, Dateien)."""
import io
import os
import re
from datetime import date, datetime, timedelta, timezone

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
    assert m.subject == 'OpenMycoNet — Nuevo mensaje: Gibt es Rohdaten zur Messung?'
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
    a.aufgaben_aktiv = True          # seit 26.10.2026 je Austausch einschaltbar, Standard aus
    db.session.commit()
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


# --- Schritt 4: Einladung, Bestaetigungscode, Arbeitsbereich -------------------

def _einladen(**felder):
    """Austausch anlegen + Einladung verschicken; gibt (austausch, token, mail) zurueck."""
    from omn import austausch as aus
    werte = dict(linkedin_url='https://www.linkedin.com/in/geheim-marker',
                 vorgeschichte_notiz='INTERN-NOTIZ-MARKER', themenueberblick='Messreihen an Myzel.')
    werte.update(felder)
    a = _austausch(**werte)
    with mail.record_messages() as ausgehend:
        aus.einladung_verschicken(a)
    m = ausgehend[0]
    token = re.search(r'/austausch/einladung/([A-Za-z0-9_-]+)', m.body).group(1)
    return a, token, m


def _code_aus(msg):
    return re.search(r'\n(\d{6})\n', msg.body).group(1)


def _annehmen(client, token):
    with mail.record_messages() as ausgehend:
        resp = client.post(f'/austausch/einladung/{token}', data={'action': 'annehmen'})
    return resp, ausgehend


def test_einladungsmail_formell_deutsch_und_neutral(app):
    from omn import austausch as aus
    a, token, m = _einladen()
    assert m.recipients == ['fach@example.com']
    assert m.subject == 'Einladung zum fachlichen Austausch: Elektrophysiologie an Myzel'
    assert 'Guten Tag Dr. Test,' in m.body
    assert 'wir laden Sie herzlich' in m.body
    assert 'unabhängig von jeder finanziellen Unterstützung' in m.body
    assert 'keine Erwartung und keine Gegenleistung' in m.body
    assert 'Art. 6 Abs. 1 lit. f DSGVO' in m.body and 'datenschutz.html' in m.body
    assert '14 Tage gültig' in m.body
    assert 'Messreihen an Myzel.' in m.body
    assert 'INTERN-NOTIZ-MARKER' not in _mailtext(m) and 'geheim-marker' not in _mailtext(m)
    assert not VERBOTEN.search(_mailtext(m))
    # nur der Hash liegt in der DB, kein Klartext-Token, keine Person in der URL
    a = db.session.get(Austausch, a.id)
    assert a.einladung_token_hash == aus.token_hash(token) != token
    assert 'fach' not in token and 'example' not in token
    assert a.status == 'eingeladen'
    bis = aus.aware(a.einladung_gueltig_bis)
    assert timedelta(days=13, hours=23) < bis - datetime.now(timezone.utc) <= timedelta(days=14)


def test_einladungsmail_informell_spanisch_mit_einleitung(app):
    _, _, m = _einladen(sprache='es', anrede='informell', persoenliche_einleitung='Gracias por la charla en LinkedIn.')
    assert 'Hola, Dr. Test:' in m.body
    assert 'invitarte' in m.body
    assert 'Gracias por la charla en LinkedIn.' in m.body
    assert 'Si no aceptas la invitación' in m.body
    assert '<html lang="es">' in m.html
    assert not VERBOTEN.search(_mailtext(m))


def test_link_oeffnen_aendert_nichts(client, app):
    """Mail-Scanner: beliebig viele GETs loesen weder Code noch Einloesung aus."""
    a, token, _ = _einladen()
    with mail.record_messages() as ausgehend:
        for _ in range(3):
            resp = client.get(f'/austausch/einladung/{token}')
    assert resp.status_code == 200
    assert ausgehend == []
    a = db.session.get(Austausch, a.id)
    assert a.status == 'eingeladen' and a.code_hash is None and a.codes_angefordert == 0
    assert a.eingeloest_am is None and a.nutzer_id is None
    seite = resp.get_data(as_text=True)
    assert 'Elektrophysiologie an Myzel' in seite
    assert 'Einladung annehmen' in seite
    assert 'f***@example.com' in seite  # Adresse nur maskiert
    assert 'INTERN-NOTIZ-MARKER' not in seite and 'geheim-marker' not in seite
    assert not VERBOTEN.search(seite)
    assert resp.headers['X-Robots-Tag'] == 'noindex, nofollow'


def test_annehmen_schickt_code_an_gespeicherte_adresse_und_loest_noch_nicht_ein(client, app):
    a, token, _ = _einladen()
    resp, ausgehend = _annehmen(client, token)
    assert resp.status_code == 200
    assert 'Bestätigungscode eingeben' in resp.get_data(as_text=True)
    assert len(ausgehend) == 1 and ausgehend[0].recipients == ['fach@example.com']
    assert ausgehend[0].subject == 'Ihr Bestätigungscode für OpenMycoNet'
    code = _code_aus(ausgehend[0])
    a = db.session.get(Austausch, a.id)
    assert a.status == 'eingeladen' and a.nutzer_id is None and a.eingeloest_am is None
    assert a.code_hash and code not in a.code_hash
    assert not VERBOTEN.search(_mailtext(ausgehend[0]))


def test_richtiger_code_legt_konto_an_und_loggt_ein(client, app):
    a, token, _ = _einladen(sprache='fr')
    _, ausgehend = _annehmen(client, token)
    with mail.record_messages() as admin_mails:
        resp = client.post(f'/austausch/einladung/{token}', data={'action': 'code', 'code': _code_aus(ausgehend[0])})
    assert resp.status_code == 302 and '/austausch' in resp.headers['Location']
    a = db.session.get(Austausch, a.id)
    assert a.status == 'aktiv' and a.eingeloest_am is not None
    assert a.einladung_token_hash is None and a.code_hash is None
    n = a.nutzer
    assert n.email == 'fach@example.com' and n.bestaetigt
    assert n.keine_mails and n.newsletter_einwilligung_am is None
    assert not n.ist_hyphist and not n.ist_sporist
    assert n.sprache == 'fr'
    assert any('Einladung angenommen' in x.subject for x in admin_mails)

    seite = client.get('/austausch').get_data(as_text=True)
    assert 'Elektrophysiologie an Myzel' in seite
    assert 'Échange scientifique' in seite
    # zweites Einloesen: Link ist verbraucht
    resp = client.get(f'/austausch/einladung/{token}')
    assert resp.status_code == 404
    assert 'ungültig, abgelaufen oder wurde bereits angenommen' in resp.get_data(as_text=True) or \
        "n'est pas valable" in resp.get_data(as_text=True)


def test_bestehendes_konto_behaelt_rollen_und_einstellungen(client, app):
    n = Nutzer(name='Alt', email='Fach@Example.com', bestaetigt=False, ist_sporist=True,
               gruppe='forschung', keine_mails=False, sprache='nl', token='tok-alt')
    db.session.add(n)
    db.session.commit()
    a, token, _ = _einladen()
    _, ausgehend = _annehmen(client, token)
    client.post(f'/austausch/einladung/{token}', data={'action': 'code', 'code': _code_aus(ausgehend[0])})
    n = db.session.get(Nutzer, n.id)
    assert db.session.get(Austausch, a.id).nutzer_id == n.id
    assert Nutzer.query.count() == 1
    assert n.bestaetigt  # Adresse ist durch den Code belegt
    assert n.ist_sporist and not n.ist_hyphist
    assert n.gruppe == 'forschung' and n.keine_mails is False and n.sprache == 'nl' and n.name == 'Alt'
    with client.session_transaction() as sess:
        assert sess['nutzer_id'] == n.id


def test_anderer_eingeloggter_nutzer_wird_ersetzt(client, app):
    fremd = Nutzer(name='Fremd', email='fremd@example.com', bestaetigt=True)
    db.session.add(fremd)
    db.session.commit()
    with client.session_transaction() as sess:
        sess['nutzer_logged_in'] = True
        sess['nutzer_id'] = fremd.id
    a, token, _ = _einladen()
    _, ausgehend = _annehmen(client, token)
    client.post(f'/austausch/einladung/{token}', data={'action': 'code', 'code': _code_aus(ausgehend[0])})
    a = db.session.get(Austausch, a.id)
    assert a.nutzer_id != fremd.id
    with client.session_transaction() as sess:
        assert sess['nutzer_id'] == a.nutzer_id


def test_code_aus_anderem_browser_wird_abgelehnt(client, app):
    a, token, _ = _einladen()
    _, ausgehend = _annehmen(client, token)
    anderer = app.test_client()
    resp = anderer.post(f'/austausch/einladung/{token}', data={'action': 'code', 'code': _code_aus(ausgehend[0])})
    assert 'im selben Browser' in resp.get_data(as_text=True)
    assert db.session.get(Austausch, a.id).status == 'eingeladen'


def test_fuenf_fehlversuche_sperren_den_code(client, app):
    a, token, _ = _einladen()
    _, ausgehend = _annehmen(client, token)
    code = _code_aus(ausgehend[0])
    falsch = '000000' if code != '000000' else '111111'
    for _i in range(5):
        seite = client.post(f'/austausch/einladung/{token}', data={'action': 'code', 'code': falsch}).get_data(as_text=True)
    assert 'Zu viele Fehlversuche' in seite
    seite = client.post(f'/austausch/einladung/{token}', data={'action': 'code', 'code': code}).get_data(as_text=True)
    assert 'Zu viele Fehlversuche' in seite
    assert db.session.get(Austausch, a.id).status == 'eingeladen'
    # neuer Code funktioniert wieder
    with mail.record_messages() as neu:
        client.post(f'/austausch/einladung/{token}', data={'action': 'code_neu'})
    resp = client.post(f'/austausch/einladung/{token}', data={'action': 'code', 'code': _code_aus(neu[0])})
    assert resp.status_code == 302
    assert db.session.get(Austausch, a.id).status == 'aktiv'


def test_hoechstens_drei_codes_je_stunde(client, app):
    _a, token, _ = _einladen()
    mails = []
    for _ in range(4):
        resp, ausgehend = _annehmen(client, token)
        mails += ausgehend
    assert len(mails) == 3
    assert 'schon drei Codes angefordert' in resp.get_data(as_text=True)


def test_abgelaufener_code(client, app):
    a, token, _ = _einladen()
    _, ausgehend = _annehmen(client, token)
    a = db.session.get(Austausch, a.id)
    a.code_gueltig_bis = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.session.commit()
    seite = client.post(f'/austausch/einladung/{token}', data={'action': 'code', 'code': _code_aus(ausgehend[0])}).get_data(as_text=True)
    assert 'Der Code ist abgelaufen' in seite
    assert db.session.get(Austausch, a.id).status == 'eingeladen'


def test_abgelaufene_und_unbekannte_einladung_gleiche_meldung(client, app):
    a, token, _ = _einladen()
    a.einladung_gueltig_bis = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.session.commit()
    abgelaufen = client.get(f'/austausch/einladung/{token}')
    unbekannt = client.get('/austausch/einladung/gibt-es-nicht')
    assert abgelaufen.status_code == unbekannt.status_code == 404
    assert 'ungültig, abgelaufen oder wurde bereits angenommen' in abgelaufen.get_data(as_text=True)
    assert 'ungültig, abgelaufen oder wurde bereits angenommen' in unbekannt.get_data(as_text=True)
    assert client.post(f'/austausch/einladung/{token}', data={'action': 'annehmen'}).status_code == 404


def test_admin_verschickt_und_erneuert_einladung(client, app, superadmin):
    from omn.models import AdminAudit
    a = _austausch()
    _admin(client)
    with mail.record_messages() as erste:
        client.post(f'/admin/austausch/{a.id}/einladen')
    alt = re.search(r'/austausch/einladung/([A-Za-z0-9_-]+)', erste[0].body).group(1)
    assert db.session.get(Austausch, a.id).status == 'eingeladen'
    with mail.record_messages() as zweite:
        client.post(f'/admin/austausch/{a.id}/einladen')
    neu = re.search(r'/austausch/einladung/([A-Za-z0-9_-]+)', zweite[0].body).group(1)
    assert alt != neu
    assert client.get(f'/austausch/einladung/{alt}').status_code == 404
    assert client.get(f'/austausch/einladung/{neu}').status_code == 200
    aktionen = [x.aktion for x in AdminAudit.query.all()]
    assert 'austausch_eingeladen' in aktionen and 'austausch_erneut_eingeladen' in aktionen


def test_admin_einladung_bei_mailfehler_unveraendert(client, app, superadmin, monkeypatch):
    a = _austausch()
    _admin(client)

    def kaputt(msg):
        raise ConnectionError('SMTP weg')
    monkeypatch.setattr('omn.austausch.mail.send', kaputt)
    resp = client.post(f'/admin/austausch/{a.id}/einladen', follow_redirects=True)
    assert 'nicht verschickt werden' in resp.get_data(as_text=True)
    a = db.session.get(Austausch, a.id)
    assert a.status == 'vorbereitet' and a.einladung_token_hash is None


def test_nach_annahme_keine_einladung_mehr(client, app, superadmin):
    _, a = _fachkontakt()
    _admin(client)
    with mail.record_messages() as ausgehend:
        client.post(f'/admin/austausch/{a.id}/einladen')
    assert ausgehend == []
    assert db.session.get(Austausch, a.id).status == 'aktiv'


def _als(client, nutzer_id):
    with client.session_transaction() as sess:
        sess['nutzer_logged_in'] = True
        sess['nutzer_id'] = nutzer_id


def test_arbeitsbereich_neutral_ohne_interne_felder(client, app):
    n, a = _fachkontakt()
    a.linkedin_url = 'https://www.linkedin.com/in/geheim-marker'
    a.vorgeschichte_notiz = 'INTERN-NOTIZ-MARKER'
    a.institution = 'INSTITUT-MARKER'
    db.session.commit()
    _als(client, n.id)
    resp = client.get('/austausch')
    seite = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'Nur zwischen Ihnen und dem OpenMycoNet-Team sichtbar.' in seite
    for marker in ('INTERN-NOTIZ-MARKER', 'geheim-marker', 'INSTITUT-MARKER', 'fach@example.com'):
        assert marker not in seite
    assert not VERBOTEN.search(seite)


def test_arbeitsbereich_schreiben_mit_uebersetzten_meldungen(client, app):
    n, a = _fachkontakt(sprache='es', anrede='informell')
    _als(client, n.id)
    with mail.record_messages() as ausgehend:
        seite = client.post('/austausch', data={'austausch_id': a.id, 'action': 'kommentar_neu',
                                                'text': 'Hola equipo'}).get_data(as_text=True)
    assert 'Mensaje enviado.' in seite
    assert Kommentar.query.filter_by(austausch_id=a.id, autor='partner').count() == 1
    assert ausgehend[0].recipients == ['admin@openmyconet.test']
    seite = client.post('/austausch', data={'austausch_id': a.id, 'action': 'aufgabe_neu', 'titel': 'x'}).get_data(as_text=True)
    assert 'En este intercambio no hay tareas.' in seite      # Aufgaben ausgeschaltet
    a.aufgaben_aktiv = True
    db.session.commit()
    seite = client.post('/austausch', data={'austausch_id': a.id, 'action': 'aufgabe_neu', 'titel': ''}).get_data(as_text=True)
    assert 'La tarea necesita un título.' in seite
    assert 'Solo visible para ti' in seite


def test_arbeitsbereich_fremder_austausch_403_und_ohne_login(client, app):
    n, _a = _fachkontakt()
    _, fremd = _fachkontakt(email='zweite@example.com')
    assert client.get('/austausch').status_code == 302  # nicht eingeloggt -> Login
    _als(client, n.id)
    resp = client.post('/austausch', data={'austausch_id': fremd.id, 'action': 'kommentar_neu', 'text': 'x'})
    assert resp.status_code == 403
    assert Kommentar.query.count() == 0


def test_dashboard_leitet_fachkontakt_zum_austausch(client, app):
    n, a = _fachkontakt()
    _als(client, n.id)
    resp = client.get('/dashboard')
    # seit 26.10.2026: ohne Start-Themenraum in die Themenraum-Uebersicht ...
    assert resp.status_code == 302 and resp.headers['Location'].endswith('/themen')
    # ... und ohne Zugang zu den Themenraeumen wie bisher in den Austausch
    app.config['THEMEN_FREIGEGEBEN'] = False
    assert client.get('/dashboard').headers['Location'].endswith('/austausch')
    app.config['THEMEN_FREIGEGEBEN'] = True
    # kein Hyphist-Bereich, keine Kooperation
    seite = client.get('/dashboard/hyphist').get_data(as_text=True)
    assert 'Elektrophysiologie an Myzel' not in seite
    assert not db.session.get(Nutzer, n.id).ist_hyphist
    a.status = 'gesperrt'
    db.session.commit()
    assert client.get('/austausch').get_data(as_text=True).count('Elektrophysiologie an Myzel') == 0


# --- Schritt 5: Fristen, Kontoloeschung, Datenschutzerklaerung -----------------

def _alt(tage):
    return datetime.now(timezone.utc) - timedelta(days=tage)


def _bereinigen():
    from omn.aufbewahrung import bereinigen
    return bereinigen()


def test_f1_nicht_angenommen_nach_2_jahren_geloescht_inkl_dateien(app):
    """Eine Frist fuer Kontaktaufnahme und Einladung: 2 Jahre (Robby, 25.10.2026)."""
    alt = _austausch(status='eingeladen', eingeladen_am=_alt(740), titel='Alt')
    pfad = kollaboration.anhang_pfad(_anhang_kommentar(alt, wer='team'))
    frisch = _austausch(status='eingeladen', eingeladen_am=_alt(700), titel='Frisch')
    ergebnis = _bereinigen()
    assert ergebnis['Austausch nicht angenommen'] == 1
    assert db.session.get(Austausch, alt.id) is None and not os.path.exists(pfad)
    assert db.session.get(Austausch, frisch.id) is not None
    assert Kommentar.query.count() == 0


def test_f1_erneuerte_einladung_beginnt_neu(app):
    """Erneuern setzt eingeladen_am neu -> Frist laeuft ab dem neuen Versand."""
    from omn import austausch as aus
    a = _austausch(erstellt_am=_alt(400))
    with mail.record_messages():
        aus.einladung_verschicken(a)
    assert _bereinigen()['Austausch nicht angenommen'] == 0
    assert db.session.get(Austausch, a.id) is not None


def test_f1a_nur_vorbereitet_nach_einem_monat(app):
    alt = _austausch(erstellt_am=_alt(31), titel='Alt')
    frisch = _austausch(erstellt_am=_alt(25), titel='Frisch')
    assert _bereinigen()['Austausch nur vorbereitet'] == 1
    assert db.session.get(Austausch, alt.id) is None
    assert db.session.get(Austausch, frisch.id) is not None


def test_erinnerung_vor_f1a_einmal_an_admin(app):
    from omn import austausch as aus
    faellig = _austausch(erstellt_am=_alt(22), titel='Bald weg')
    _austausch(erstellt_am=_alt(10), titel='Noch Zeit')
    _austausch(erstellt_am=_alt(25), titel='Schon eingeladen', status='eingeladen', eingeladen_am=_alt(25))
    _austausch(erstellt_am=_alt(25), titel='Gesperrt', loeschsperre_bis=date.today() + timedelta(days=5),
               loeschsperre_grund='Grund')
    with mail.record_messages() as ausgehend:
        assert aus.vorbereitet_erinnern() == 1
        assert aus.vorbereitet_erinnern() == 0  # nur einmal
    assert len(ausgehend) == 1
    m = ausgehend[0]
    assert m.recipients == ['admin@openmyconet.test']
    assert 'Bald weg' in m.body and f'/admin/austausch/{faellig.id}' in m.body
    assert 'Noch Zeit' not in m.body and 'Schon eingeladen' not in m.body and 'Gesperrt' not in m.body
    assert db.session.get(Austausch, faellig.id).vorbereitet_erinnert_am is not None


def test_cli_aufbewahrung_verschickt_erinnerung(app):
    _austausch(erstellt_am=_alt(22), titel='Bald weg')
    with mail.record_messages() as ausgehend:
        erg = app.test_cli_runner().invoke(args=['aufbewahrung-bereinigen'])
    assert erg.exit_code == 0, erg.output
    assert '1 vorbereitete Einladung(en) zur Erinnerung gemeldet' in erg.output
    assert len(ausgehend) == 1


def test_einladungsmail_gespraechsbeginn_und_eigener_widerspruchssatz(app):
    _, _, m = _einladen()
    assert 'das Datum unseres Gesprächsbeginns' in m.body
    assert '2 Jahre nach unserem letzten Kontakt' in m.body
    widerspruch = 'Sie können der Speicherung Ihrer Angaben jederzeit widersprechen'
    # eigener, abgesetzter Absatz -- nicht im Datenschutz-Absatz versteckt
    absaetze = m.body.split('\n\n')
    eigen = [x for x in absaetze if widerspruch in x]
    assert len(eigen) == 1 and not eigen[0].startswith('Datenschutz:')
    assert widerspruch in m.html
    _, _, m_es = _einladen(email='es@example.com', sprache='es', anrede='informell')
    assert 'Puedes oponerte en cualquier momento' in m_es.body


def test_f3_notizen_nach_24_monaten_geleert_austausch_bleibt(app):
    _, a = _fachkontakt()
    a.linkedin_url = 'https://www.linkedin.com/in/x'
    a.gespraech_begonnen_am = date(2024, 1, 1)
    a.vorgeschichte_notiz = 'Notiz'
    a.letzte_aktivitaet = _alt(740)
    _, b = _fachkontakt(email='b@example.com')
    b.vorgeschichte_notiz = 'Bleibt'
    b.letzte_aktivitaet = _alt(700)
    db.session.commit()
    ergebnis = _bereinigen()
    assert ergebnis['Austausch Profil-Link'] == 1 and ergebnis['Austausch Vorgeschichte'] == 1
    a = db.session.get(Austausch, a.id)
    assert a.linkedin_url is None and a.gespraech_begonnen_am is None and a.vorgeschichte_notiz is None
    assert a.status == 'aktiv'  # nur geleert, nichts gesperrt oder geloescht (F2 ist nur Markierung)
    assert db.session.get(Austausch, b.id).vorgeschichte_notiz == 'Bleibt'


def test_f4_beendet_und_gesperrt_nach_6_monaten(app):
    _, alt = _fachkontakt()
    alt.status = 'gesperrt'
    alt.status_geaendert_am = _alt(190)
    _, beendet = _fachkontakt(email='b@example.com')
    beendet.status = 'beendet'
    beendet.status_geaendert_am = _alt(190)
    _, frisch = _fachkontakt(email='c@example.com')
    frisch.status = 'gesperrt'
    frisch.status_geaendert_am = _alt(10)
    _, aktiv = _fachkontakt(email='d@example.com')
    aktiv.status_geaendert_am = _alt(900)
    aktiv.letzte_aktivitaet = _alt(900)
    db.session.commit()
    assert _bereinigen()['Austausch beendet/gesperrt'] == 2
    assert {a.id for a in Austausch.query.all()} == {frisch.id, aktiv.id}


def test_loeschsperre_setzt_fristen_aus_bis_sie_ablaeuft(app):
    a = _austausch(status='gesperrt', status_geaendert_am=_alt(400), vorgeschichte_notiz='Nachweis',
                   letzte_aktivitaet=_alt(800), loeschsperre_bis=date.today() + timedelta(days=30),
                   loeschsperre_grund='Nachweispflicht')
    ergebnis = _bereinigen()
    assert ergebnis['Austausch beendet/gesperrt'] == 0 and ergebnis['Austausch Vorgeschichte'] == 0
    a = db.session.get(Austausch, a.id)
    assert a.vorgeschichte_notiz == 'Nachweis'
    a.loeschsperre_bis = date.today() - timedelta(days=1)
    db.session.commit()
    assert _bereinigen()['Austausch beendet/gesperrt'] == 1
    assert Austausch.query.count() == 0


def test_kontoloeschung_im_admin_sperrt_austausch(client, app, superadmin):
    n, a = _fachkontakt()
    _admin(client)
    resp = client.post(f'/admin/nutzer/loeschen/{n.id}', follow_redirects=True)
    assert 'wird nach 6 Monaten gelöscht' in resp.get_data(as_text=True)
    assert db.session.get(Nutzer, n.id) is None
    a = db.session.get(Austausch, a.id)
    assert a.status == 'gesperrt' and a.nutzer_id is None


def test_admin_uebersicht_zeigt_pruefhinweis(client, app, superadmin):
    _, a = _fachkontakt()
    _admin(client)
    assert 'zur Prüfung' not in client.get('/admin').get_data(as_text=True)
    a.letzte_aktivitaet = _alt(400)
    db.session.commit()
    seite = client.get('/admin').get_data(as_text=True)
    assert '1 fachlicher Austausch seit 12 Monaten ohne Aktivität' in seite


def test_datenschutzerklaerung_abschnitt_austausch(client):
    from omn.i18n import LANGS
    from omn.rechtstexte import RECHTSTEXTE
    for lang in LANGS:
        abschnitte = RECHTSTEXTE[lang]['datenschutz']['abschnitte']
        ids = [x['id'] for x in abschnitte]
        assert ids.index('austausch') == ids.index('kontaktaufnahme') + 1
        text = next(x['html'] for x in abschnitte if x['id'] == 'austausch')
        for frist in ('6', '24'):
            assert frist in text, (lang, frist)
        assert 'kontakt@openmyconet.de' in text
        assert [int(x['h'].split('.')[0]) for x in abschnitte] == list(range(1, len(abschnitte) + 1))
    de = next(x['html'] for x in RECHTSTEXTE['de']['datenschutz']['abschnitte'] if x['id'] == 'austausch')
    assert '2 Jahre nach unserem letzten Kontakt' in de and 'nach einem Monat' in de
    seite = client.get('/datenschutz.html').get_data(as_text=True)
    assert 'id="austausch"' in seite and '9. Fachlicher Austausch auf Einladung' in seite
    assert '(siehe Abschnitt 13)' in seite  # Verweis auf "Messdaten" mitgezogen (seit Themenraeume: 13)


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


# --- Seit 26.10.2026: Start-Themenraum, Aufgaben nur auf Wunsch, eigene Knoepfe -----------

def _gebiet_und_diskussion():
    from omn.models import Diskussion, Themengebiet
    g = Themengebiet(titel='Vererbung', beschreibung='B', von_team=True)
    db.session.add(g)
    db.session.commit()
    d = Diskussion(themengebiet_id=g.id, titel='450 Millionen Jahre', beschreibung='B', von_team=True)
    db.session.add(d)
    db.session.commit()
    return g, d


def test_start_themenraum_nach_login_und_im_austausch(client, app):
    n, a = _fachkontakt()
    g, d = _gebiet_und_diskussion()
    a.start_diskussion_id = d.id
    db.session.commit()
    _als(client, n.id)
    assert client.get('/dashboard').headers['Location'].endswith(f'/themen/diskussion/{d.id}')
    seite = client.get('/austausch').get_data(as_text=True)
    assert 'Zum Themenraum: 450 Millionen Jahre' in seite
    # Diskussion ausgeblendet -> Ziel ignoriert, Gebiet als Ersatz
    a.start_gebiet_id = g.id
    d.sichtbar = False
    db.session.commit()
    assert client.get('/dashboard').headers['Location'].endswith(f'/themen/gebiet/{g.id}')
    # Ziel geloescht -> Uebersicht
    a.start_gebiet_id = 9999
    db.session.commit()
    assert client.get('/dashboard').headers['Location'].endswith('/themen')


def test_messknoten_geht_vor_und_hat_eigenen_knopf(client, app):
    from omn.models import Knoten
    n, a = _fachkontakt()
    _g, d = _gebiet_und_diskussion()
    a.start_diskussion_id = d.id
    db.session.add(Knoten(knoten_id='K-1', nutzer_id=n.id))
    db.session.commit()
    _als(client, n.id)
    assert client.get('/dashboard').headers['Location'].endswith('/dashboard/knotenbetreiber')
    seite = client.get('/austausch').get_data(as_text=True)
    assert '/dashboard/knotenbetreiber' in seite and 'Messknoten' in seite      # Knopf in der Leiste
    assert 'Fachlicher Austausch' in seite and '/themen' in seite


def test_aufgaben_ausgeblendet_bis_admin_einschaltet(client, app, superadmin):
    n, a = _fachkontakt()
    db.session.add(Aufgabe(titel='Alte Aufgabe', erstellt_von='team', austausch_id=a.id))
    db.session.commit()
    _als(client, n.id)
    seite = client.get('/austausch').get_data(as_text=True)
    assert 'Alte Aufgabe' not in seite and 'Vertrauliche Nachrichten' in seite
    _admin(client)
    admin = client.get(f'/admin/austausch/{a.id}').get_data(as_text=True)
    assert 'Aufgaben sind in diesem Austausch ausgeblendet (1 gespeichert)' in admin
    g, _d = _gebiet_und_diskussion()
    form = client.get(f'/admin/austausch/{a.id}/bearbeiten').get_data(as_text=True)
    assert f'value="g:{g.id}"' in form and 'name="aufgaben_aktiv"' in form
    client.post(f'/admin/austausch/{a.id}/bearbeiten', data={
        'titel': a.titel, 'name': a.name, 'email': a.email, 'sprache': 'de', 'anrede': 'formell',
        'aufgaben_aktiv': '1', 'start': f'g:{g.id}'})
    a = db.session.get(Austausch, a.id)
    assert a.aufgaben_aktiv is True and a.start_gebiet_id == g.id and a.start_diskussion_id is None
    _als(client, n.id)
    assert 'Alte Aufgabe' in client.get('/austausch').get_data(as_text=True)
    # ungueltige Auswahl -> kein Start
    _admin(client)
    client.post(f'/admin/austausch/{a.id}/bearbeiten', data={
        'titel': a.titel, 'name': a.name, 'email': a.email, 'sprache': 'de', 'anrede': 'formell', 'start': 'd:9999'})
    a = db.session.get(Austausch, a.id)
    assert a.start_gebiet_id is None and a.start_diskussion_id is None and a.aufgaben_aktiv is False
