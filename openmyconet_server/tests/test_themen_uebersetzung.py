"""Themenraeume Phase 2b, Schritt 2: fehlende Uebersetzungen nachladen
(POST /themen/uebersetzung), Platzhalter in den Seiten, Hinweis beim Schreiben,
Zaehler + Loeschen im Admin. Der Anbieter ist immer eine Attrappe."""
import json

from test_themen import _admin, _diskussion, _gebiet, _teilnehmer

from omn import uebersetzung as ue
from omn.admin.audit import AdminAudit
from omn.extensions import db
from omn.models import Beitrag, ThemenTeilnahme, Uebersetzung


def _anbieter(monkeypatch, antwort=lambda text: 'EN: ' + text):
    aufrufe = []

    def attrappe(system, text):
        aufrufe.append(text)
        return antwort(text)
    monkeypatch.setitem(ue.ANBIETER, 'claude', attrappe)
    return aufrufe


def _holen(client, **daten):
    return client.post('/themen/uebersetzung?lang=en', data=json.dumps(daten), content_type='application/json')


def test_seite_zeigt_platzhalter_statt_die_api_zu_rufen(client, app, monkeypatch):
    aufrufe = _anbieter(monkeypatch)
    _teilnehmer(client)
    d = _diskussion()
    seite = client.get(f'/themen/diskussion/{d.id}?lang=en').get_data(as_text=True)
    assert aufrufe == []                                    # Seite selbst uebersetzt nie
    assert f'data-typ="diskussion" data-id="{d.id}" data-feld="titel"' in seite
    assert 'translating …' in seite
    assert 'Signaturen bei Netzerneuerung' in seite         # Original sofort lesbar
    assert '/themen/uebersetzung' in seite and 'X-CSRFToken' in seite
    # Originalsprache -> kein Platzhalter
    assert 'class="th-ue"' not in client.get(f'/themen/diskussion/{d.id}?lang=de').get_data(as_text=True)


def test_nachladen_erzeugt_einmal_und_liefert_fertige_anzeige(client, app, monkeypatch):
    aufrufe = _anbieter(monkeypatch)
    _teilnehmer(client)
    d = _diskussion()
    r = _holen(client, typ='diskussion', id=d.id, feld='beschreibung', links=True)
    assert r.status_code == 200
    html = r.get_json()['html']
    assert 'EN: Worum es geht' in html
    assert 'Machine-translated from: Deutsch' in html and 'Worum es geht' in html
    assert _holen(client, typ='diskussion', id=d.id, feld='beschreibung').get_json()['html']
    assert len(aufrufe) == 1 and Uebersetzung.query.count() == 1
    # danach steht die Uebersetzung direkt in der Seite, ohne Platzhalter
    seite = client.get(f'/themen/diskussion/{d.id}?lang=en').get_data(as_text=True)
    assert 'EN: Worum es geht' in seite
    # Kurzform fuer Listen: nur der Text
    kurz = _holen(client, typ='diskussion', id=d.id, feld='titel', kurz=True).get_json()['html']
    assert kurz == 'EN: Signaturen bei Netzerneuerung'


def test_antwort_wird_escaped(client, app, monkeypatch):
    _anbieter(monkeypatch, lambda text: '<script>alert()</script>' + text)
    _teilnehmer(client)
    d = _diskussion()
    html = _holen(client, typ='diskussion', id=d.id, feld='titel').get_json()['html']
    assert '<script>' not in html and '&lt;script&gt;' in html


def test_nachladen_ohne_uebersetzung_gibt_none(client, app, monkeypatch):
    _teilnehmer(client)
    d = _diskussion()
    # conftest-Anbieter wirft immer -> None, nichts gespeichert
    assert _holen(client, typ='diskussion', id=d.id, feld='titel').get_json() == {'html': None}
    app.config['UEBERSETZUNG_AKTIV'] = False
    _anbieter(monkeypatch)
    assert _holen(client, typ='diskussion', id=d.id, feld='titel').get_json() == {'html': None}
    assert Uebersetzung.query.count() == 0
    # ausgeschaltet -> auch kein Platzhalter und kein Hinweis beim Schreiben
    seite = client.get(f'/themen/diskussion/{d.id}?lang=en').get_data(as_text=True)
    assert 'class="th-ue"' not in seite and 'Anthropic' not in seite


def test_tageslimit_keine_platzhalter_mehr(client, app, monkeypatch):
    _anbieter(monkeypatch)
    _teilnehmer(client)
    d = _diskussion()
    app.config['UEBERSETZUNG_TAGESLIMIT'] = 0
    assert 'class="th-ue"' not in client.get(f'/themen/diskussion/{d.id}?lang=en').get_data(as_text=True)
    assert _holen(client, typ='diskussion', id=d.id, feld='titel').get_json() == {'html': None}


def test_nachladen_prueft_feld_und_sichtbarkeit(client, app, monkeypatch):
    aufrufe = _anbieter(monkeypatch)
    _teilnehmer(client)
    d = _diskussion()
    b = Beitrag(diskussion_id=d.id, text='Ausgeblendet', sprache_original='de', von_team=True, sichtbar=False)
    db.session.add(b)
    db.session.commit()
    assert _holen(client, typ='diskussion', id=d.id, feld='geheim').status_code == 400
    assert _holen(client, typ='nutzer', id=1, feld='name').status_code == 400
    assert _holen(client, typ='diskussion', id='x', feld='titel').status_code == 400
    assert _holen(client, typ='beitrag', id=b.id, feld='text').status_code == 404
    assert _holen(client, typ='diskussion', id=9999, feld='titel').status_code == 404
    d.sichtbar = False
    db.session.commit()
    assert _holen(client, typ='diskussion', id=d.id, feld='titel').status_code == 404
    assert aufrufe == []


def test_nachladen_nur_fuer_berechtigte(client, app, monkeypatch):
    aufrufe = _anbieter(monkeypatch)
    d = _diskussion()
    r = _holen(client, typ='diskussion', id=d.id, feld='titel')
    assert r.status_code == 302                              # nicht eingeloggt
    assert aufrufe == []


def test_originale_zuerst_laedt_erst_beim_aufklappen(client, app, monkeypatch):
    _anbieter(monkeypatch)
    _teilnehmer(client)
    d = _diskussion()
    tn = ThemenTeilnahme.query.one()
    tn.original_zuerst = True
    db.session.commit()
    seite = client.get(f'/themen/diskussion/{d.id}?lang=en').get_data(as_text=True)
    assert 'data-spaet="1"' in seite and 'Show translation' in seite
    # Listen: bei "Originale zuerst" kein Platzhalter
    liste = client.get(f'/themen/gebiet/{d.themengebiet_id}?lang=en').get_data(as_text=True)
    assert 'data-typ="diskussion"' not in liste
    html = _holen(client, typ='diskussion', id=d.id, feld='titel').get_json()['html']
    assert 'Show translation · machine-translated' in html


def test_hinweis_beim_schreiben(client, app):
    _teilnehmer(client)
    d = _diskussion()
    seite = client.get(f'/themen/diskussion/{d.id}?lang=de').get_data(as_text=True)
    assert 'automatisch übersetzt (Anthropic)' in seite and '/datenschutz.html?lang=de' in seite
    neu = client.get(f'/themen/gebiet/{d.themengebiet_id}/diskussion/neu?lang=fr').get_data(as_text=True)
    assert 'traduits automatiquement (Anthropic)' in neu and 'Politique de confidentialité' in neu


def test_admin_zaehler_und_loeschen(client, app, superadmin, monkeypatch):
    _anbieter(monkeypatch)
    g = _gebiet()
    db.session.add(Uebersetzung(inhalt_typ='themengebiet', inhalt_id=g.id, feld='titel', ziel_sprache='en',
                                quelltext_hash='x', text='Handfassung', anbieter='manuell'))
    db.session.commit()
    assert ue.uebersetzung_erzeugen(g, 'beschreibung', 'en')
    auto = Uebersetzung.query.filter_by(anbieter='claude').one()
    _admin(client)
    uebersicht = client.get('/admin/themen').get_data(as_text=True)
    assert 'Heute (UTC): <strong>1</strong> von 100' in uebersicht
    liste = client.get('/admin/themen/uebersetzungen').get_data(as_text=True)
    assert 'EN: ' in liste and 'Handfassung' not in liste          # Handuebersetzungen nicht hier
    # Handuebersetzung kann hier nicht geloescht werden
    hand = Uebersetzung.query.filter_by(anbieter='manuell').one()
    assert client.post(f'/admin/themen/uebersetzung/{hand.id}/loeschen').status_code == 404
    r = client.post(f'/admin/themen/uebersetzung/{auto.id}/loeschen')
    assert r.status_code == 302
    assert Uebersetzung.query.filter_by(anbieter='claude').count() == 0
    assert AdminAudit.query.filter_by(aktion='themen_uebersetzung_geloescht').count() == 1


def test_admin_zeigt_ausgeschaltet(client, app, superadmin):
    app.config['UEBERSETZUNG_AKTIV'] = False
    _admin(client)
    assert 'UEBERSETZUNG_AKTIV=0' in client.get('/admin/themen').get_data(as_text=True)


# --- Widerspruch: eigene Texte nicht uebersetzen (E1, Robby 26.10.2026) ----------------

def _eigener_beitrag(n, d, text='Eigene Messung mit 3 Elektroden.'):
    b = Beitrag(diskussion_id=d.id, autor_nutzer_id=n.id, text=text, sprache_original='de',
                uebersetzen=not n.themen_teilnahme.nicht_uebersetzen)
    db.session.add(b)
    db.session.commit()
    return b


def test_einstellung_nicht_uebersetzen(client, app, monkeypatch):
    aufrufe = _anbieter(monkeypatch)
    n = _teilnehmer(client)
    d = _diskussion()
    b = _eigener_beitrag(n, d)
    assert ue.uebersetzung_erzeugen(b, 'text', 'en') == 'EN: Eigene Messung mit 3 Elektroden.'
    assert 'name="nicht_uebersetzen"' in client.get('/themen/einstellungen?lang=de').get_data(as_text=True)
    client.post('/themen/einstellungen', data={'anzeigename': 'Dr. T. Muster', 'nicht_uebersetzen': '1'})
    db.session.refresh(b)
    assert b.uebersetzen is False and n.themen_teilnahme.nicht_uebersetzen is True
    assert Uebersetzung.query.count() == 0                 # vorhandene geloescht
    # kein Platzhalter, keine Erzeugung, Nachladen liefert nichts
    seite = client.get(f'/themen/diskussion/{d.id}?lang=en').get_data(as_text=True)
    assert f'data-typ="beitrag" data-id="{b.id}"' not in seite
    assert 'Eigene Messung mit 3 Elektroden.' in seite
    assert _holen(client, typ='beitrag', id=b.id, feld='text').get_json() == {'html': None}
    assert len(aufrufe) == 1
    # neue Beitraege erben die Einstellung
    client.post(f'/themen/diskussion/{d.id}', data={'text': 'Noch ein Beitrag', 'sprache': 'de'})
    neu = Beitrag.query.filter_by(text='Noch ein Beitrag').one()
    assert neu.uebersetzen is False
    # Inhalte anderer (Team-Diskussion) werden weiter uebersetzt
    assert _holen(client, typ='diskussion', id=d.id, feld='titel').get_json()['html']
    # wieder einschalten
    client.post('/themen/einstellungen', data={'anzeigename': 'Dr. T. Muster'})
    db.session.refresh(b)
    assert b.uebersetzen is True


def test_widerspruch_bleibt_nach_kontoloeschung(client, app, monkeypatch):
    aufrufe = _anbieter(monkeypatch)
    n = _teilnehmer(client)
    d = _diskussion()
    n.themen_teilnahme.nicht_uebersetzen = True
    b = _eigener_beitrag(n, d)
    db.session.delete(n)
    db.session.commit()
    b = db.session.get(Beitrag, b.id)
    assert b.autor_nutzer_id is None and b.uebersetzen is False
    assert ue.uebersetzung_erzeugen(b, 'text', 'en') is None
    assert aufrufe == []


def test_nutzungsregeln_nennen_uebersetzung(client, app):
    from omn.themen import REGELN_FASSUNG
    assert REGELN_FASSUNG == '2026-10-26'
    n = _teilnehmer(client, regeln='2026-10-25')        # alte Fassung -> neu zustimmen
    seite = client.get('/themen?lang=de', follow_redirects=True).get_data(as_text=True)
    assert 'an Anthropic übermittelt' in seite and 'Einstellungen' in seite
    assert n.themen_teilnahme.regeln_fassung == '2026-10-25'


# --- Umschalter oben auf der Seite (Robby 26.10.2026) ---------------------------------

def test_umschalter_ganze_seite(client, app):
    _teilnehmer(client)
    d = _diskussion()
    seite = client.get(f'/themen/diskussion/{d.id}?lang=en').get_data(as_text=True)
    assert 'View: translated' in seite and 'Show everything in the original' in seite
    r = client.post('/themen/ansicht', data={'ansicht': 'original', 'weiter': f'/themen/diskussion/{d.id}?lang=en'})
    assert r.status_code == 302 and r.headers['Location'].endswith(f'/themen/diskussion/{d.id}?lang=en')
    assert ThemenTeilnahme.query.one().original_zuerst is True
    seite = client.get(f'/themen/diskussion/{d.id}?lang=en').get_data(as_text=True)
    assert 'View: originals' in seite and 'Show everything translated' in seite and 'data-spaet="1"' in seite
    client.post('/themen/ansicht', data={'ansicht': 'uebersetzt', 'weiter': '/themen'})
    assert ThemenTeilnahme.query.one().original_zuerst is False
    # fremde Ziele -> Uebersicht
    r = client.post('/themen/ansicht', data={'ansicht': 'original', 'weiter': 'https://example.org/'})
    assert r.headers['Location'].endswith('/themen')
    for seite in ('/themen', f'/themen/gebiet/{d.themengebiet_id}'):
        assert 'th-ansicht' in client.get(seite + '?lang=en').get_data(as_text=True)
