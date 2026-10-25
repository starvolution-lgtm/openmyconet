"""Wissenschaftliche Themenraeume (Phase 2a, docs/austausch_phase2_plan.md).
Schritt 1: Datenmodell, Berechtigung, Original + Uebersetzung. Schritt 2: Seiten."""
import io
import os
import re
from datetime import datetime, timedelta, timezone

from omn import kollaboration
from omn.extensions import db
from omn.models import (
    Austausch, Beitrag, BeitragAnhang, Diskussion, Foerderer, Kommentar, KollaborationAnhang, Nutzer,
    ThemenTeilnahme, Themengebiet, Uebersetzung,
)
from omn.themen import (
    REGELN_FASSUNG, anzeige, darf_themenraeume_nutzen, quelltext_hash, uebersetzungen_loeschen, verlinken,
)


def _nutzer(email='n@example.com', bestaetigt=True, **felder):
    n = Nutzer(name='N', email=email, bestaetigt=bestaetigt, **felder)
    db.session.add(n)
    db.session.commit()
    return n


def _mit_austausch(n, status='aktiv'):
    db.session.add(Austausch(titel='T', name=n.name, email=n.email, status=status, nutzer_id=n.id))
    db.session.commit()


def _gebiet(**felder):
    werte = dict(titel='Mykologie & Mykorrhiza', beschreibung='Pilzphysiologie', sprache_original='de')
    werte.update(felder)
    g = Themengebiet(**werte)
    db.session.add(g)
    db.session.commit()
    return g


# --- Berechtigung ---------------------------------------------------------------

def test_kreis_fachkontakte_nur_mit_aktivem_austausch(app):
    fach = _nutzer('fach@example.com')
    _mit_austausch(fach)
    gesperrt = _nutzer('gesperrt@example.com')
    _mit_austausch(gesperrt, status='gesperrt')
    normal = _nutzer('normal@example.com')
    assert darf_themenraeume_nutzen(fach)
    assert not darf_themenraeume_nutzen(gesperrt)
    assert not darf_themenraeume_nutzen(normal)
    assert not darf_themenraeume_nutzen(None)


def test_rollen_und_foerderung_geben_keinen_zugang(app):
    """Zugang haengt nie an Hyphist, Sporist oder Foerderung."""
    sporist = _nutzer('sporist@example.com', ist_sporist=True)
    hyphist = _nutzer('hyphist@example.com', ist_hyphist=True)
    db.session.add(Foerderer(token='t', status='active', typ='kooperation', firma='Koop GmbH',
                             beschreibung='Beschreibung der Kooperation.', email=hyphist.email,
                             betrag=0, nutzer_id=hyphist.id))
    db.session.commit()
    assert not darf_themenraeume_nutzen(sporist)
    assert not darf_themenraeume_nutzen(hyphist)


def test_kreis_alle_jeder_bestaetigte_nutzer(app):
    app.config['THEMEN_KREIS'] = 'alle'
    assert darf_themenraeume_nutzen(_nutzer('a@example.com'))
    assert darf_themenraeume_nutzen(_nutzer('s@example.com', ist_sporist=True))
    assert not darf_themenraeume_nutzen(_nutzer('u@example.com', bestaetigt=False))


# --- Original + Uebersetzung -------------------------------------------------------

def test_anzeige_nimmt_uebersetzung_nur_fuer_die_aktuelle_fassung(app):
    g = _gebiet()
    db.session.add(Uebersetzung(inhalt_typ='themengebiet', inhalt_id=g.id, feld='titel', ziel_sprache='en',
                                quelltext_hash=quelltext_hash(g.titel), text='Mycology & mycorrhiza'))
    db.session.commit()
    en = anzeige(g, 'titel', 'en')
    assert en == {'text': 'Mycology & mycorrhiza', 'original': 'Mykologie & Mykorrhiza',
                  'sprache_original': 'de', 'uebersetzt': True}
    assert anzeige(g, 'titel', 'de')['uebersetzt'] is False
    assert anzeige(g, 'titel', 'nl') == {'text': 'Mykologie & Mykorrhiza', 'original': 'Mykologie & Mykorrhiza',
                                         'sprache_original': 'de', 'uebersetzt': False}
    # Original geaendert -> alte Uebersetzung passt nicht mehr
    g.titel = 'Mykologie, Mykorrhiza & Symbiosen'
    db.session.commit()
    assert anzeige(g, 'titel', 'en')['uebersetzt'] is False
    assert anzeige(g, 'titel', 'en')['text'] == 'Mykologie, Mykorrhiza & Symbiosen'


def test_uebersetzungen_werden_mit_dem_inhalt_geloescht(app):
    g = _gebiet()
    andere = _gebiet(titel='Anderes')
    for ziel in (g, andere):
        db.session.add(Uebersetzung(inhalt_typ='themengebiet', inhalt_id=ziel.id, feld='titel', ziel_sprache='en',
                                    quelltext_hash=quelltext_hash(ziel.titel), text='x'))
    db.session.commit()
    assert uebersetzungen_loeschen(g) == 1
    db.session.commit()
    assert Uebersetzung.query.count() == 1


# --- Datenmodell ---------------------------------------------------------------

def test_gebiet_loeschen_nimmt_diskussionen_beitraege_anhaenge_mit(app):
    n = _nutzer()
    g = _gebiet()
    d = Diskussion(themengebiet_id=g.id, titel='Signaturen bei Netzerneuerung', erstellt_von=n.id)
    db.session.add(d)
    db.session.commit()
    b = Beitrag(diskussion_id=d.id, autor_nutzer_id=n.id, text='Erste Beobachtung', art='beobachtung')
    db.session.add(b)
    db.session.commit()
    db.session.add(Beitrag(diskussion_id=d.id, antwort_auf=b.id, von_team=True, text='Danke'))
    db.session.add(BeitragAnhang(beitrag_id=b.id, dateiname='x.csv', originalname='x.csv', groesse=3))
    db.session.commit()
    db.session.delete(g)
    db.session.commit()
    assert Diskussion.query.count() == Beitrag.query.count() == BeitragAnhang.query.count() == 0


def test_kontoloeschung_loest_nur_den_autor(app):
    n = _nutzer()
    db.session.add(ThemenTeilnahme(nutzer_id=n.id, anzeigename='Dr. N.'))
    g = _gebiet()
    d = Diskussion(themengebiet_id=g.id, titel='D', erstellt_von=n.id)
    db.session.add(d)
    db.session.commit()
    db.session.add(Beitrag(diskussion_id=d.id, autor_nutzer_id=n.id, text='Text'))
    db.session.commit()
    assert n.themen_teilnahme.anzeigename == 'Dr. N.'
    db.session.delete(n)
    db.session.commit()
    assert ThemenTeilnahme.query.count() == 0
    b = Beitrag.query.one()
    assert b.autor_nutzer_id is None and b.von_team is False  # ehemaliges Mitglied
    assert Diskussion.query.one().erstellt_von is None


def test_themenraeume_getrennt_vom_vertraulichen_austausch(app):
    """Kein Fremdschluessel zwischen Themenraeumen und Austausch/Kollaboration."""
    vertraulich = {'aufgabe', 'kommentar', 'kollaboration_anhang', 'austausch', 'foerderer', 'knoten'}
    for tabelle in ('themengebiet', 'diskussion', 'beitrag', 'beitrag_anhang', 'themen_teilnahme', 'uebersetzung'):
        ziele = {fk.column.table.name for fk in db.metadata.tables[tabelle].foreign_keys}
        assert not (ziele & vertraulich), tabelle


# --- Schritt 2: Seiten -----------------------------------------------------------

VERBOTEN = re.compile(r'f(ö|oe)rder|paypal|sporist|spende|zahlung|hyphist|kooperation|fachkontakt', re.I)


def _teilnehmer(client, email='t@example.com', anzeigename='Dr. T. Muster', regeln=REGELN_FASSUNG):
    n = _nutzer(email)
    _mit_austausch(n)
    if anzeigename:
        db.session.add(ThemenTeilnahme(nutzer_id=n.id, anzeigename=anzeigename, regeln_fassung=regeln))
        db.session.commit()
    with client.session_transaction() as sess:
        sess['nutzer_logged_in'] = True
        sess['nutzer_id'] = n.id
    return n


def _diskussion(gebiet=None, **felder):
    g = gebiet or _gebiet()
    werte = dict(themengebiet_id=g.id, titel='Signaturen bei Netzerneuerung', beschreibung='Worum es geht')
    werte.update(felder)
    d = Diskussion(**werte)
    db.session.add(d)
    db.session.commit()
    return d


def test_ohne_login_und_ohne_berechtigung(client, app):
    assert client.get('/themen').status_code == 302
    n = _nutzer('ohne@example.com')
    with client.session_transaction() as sess:
        sess['nutzer_logged_in'] = True
        sess['nutzer_id'] = n.id
    resp = client.get('/themen')
    assert resp.status_code == 403
    assert 'nur auf Einladung' in resp.get_data(as_text=True)
    kopf = client.get('/dashboard/basis').get_data(as_text=True).split('</header>')[0]
    assert '/themen' not in kopf


def test_erster_besuch_fordert_anzeigename_und_regeln(client, app):
    n = _teilnehmer(client, anzeigename=None)
    resp = client.get('/themen/gebiet/neu')
    assert resp.status_code == 302 and '/themen/teilnahme' in resp.headers['Location']
    seite = client.post('/themen/teilnahme', data={'anzeigename': 'L. B.', 'weiter': '/themen/gebiet/neu'}).get_data(as_text=True)
    assert 'Zustimmung zu den Nutzungsregeln nötig' in seite
    assert ThemenTeilnahme.query.count() == 0
    resp = client.post('/themen/teilnahme', data={'anzeigename': '  L.   B. ', 'regeln': '1', 'weiter': '/themen/gebiet/neu'})
    assert resp.status_code == 302 and resp.headers['Location'].endswith('/themen/gebiet/neu')
    tn = db.session.get(ThemenTeilnahme, n.id)
    assert tn.anzeigename == 'L. B.' and tn.regeln_fassung == REGELN_FASSUNG and tn.regeln_akzeptiert_am
    # fremdes Ziel wird nicht angesprungen
    resp = client.post('/themen/teilnahme', data={'anzeigename': 'L. B.', 'regeln': '1', 'weiter': 'https://boese.example'})
    assert resp.headers['Location'].endswith('/themen')


def test_neue_regelfassung_verlangt_erneute_zustimmung(client, app):
    _teilnehmer(client, regeln='2020-01')
    assert '/themen/teilnahme' in client.get('/themen').headers['Location']


def test_uebersicht_mit_handuebersetzung_und_original(client, app):
    _teilnehmer(client)
    g = _gebiet(vorgegeben=True, reihenfolge=1)
    db.session.add(Uebersetzung(inhalt_typ='themengebiet', inhalt_id=g.id, feld='titel', ziel_sprache='en',
                                quelltext_hash=quelltext_hash(g.titel), text='Mycology & mycorrhiza'))
    db.session.commit()
    seite = client.get('/themen?lang=en').get_data(as_text=True)
    assert 'Mycology &amp; mycorrhiza' in seite           # Liste: Kurzform, kein Aufklappen im Link
    assert not VERBOTEN.search(seite)
    gebiet = client.get(f'/themen/gebiet/{g.id}?lang=en').get_data(as_text=True)
    assert 'Mycology &amp; mycorrhiza' in gebiet
    assert 'Mykologie &amp; Mykorrhiza' in gebiet          # Original steckt in der Seite
    assert 'Show original' in gebiet
    # "Originale zuerst": Liste zeigt das Original
    tn = ThemenTeilnahme.query.one()
    tn.original_zuerst = True
    db.session.commit()
    assert 'Mykologie &amp; Mykorrhiza' in client.get('/themen?lang=en').get_data(as_text=True)
    assert 'Themenräume' in client.get('/themen?lang=de').get_data(as_text=True)


def test_gebiet_und_diskussion_anlegen(client, app):
    n = _teilnehmer(client)
    seite = client.post('/themen/gebiet/neu', data={'titel': '', 'beschreibung': ''}).get_data(as_text=True)
    assert 'Titel und kurze Beschreibung sind Pflicht' in seite
    resp = client.post('/themen/gebiet/neu', data={'titel': 'Pilz-Bakterien-Interaktion',
                                                   'beschreibung': 'Bakterien an Hyphen', 'sprache': 'en'})
    g = Themengebiet.query.filter_by(titel='Pilz-Bakterien-Interaktion').one()
    assert resp.headers['Location'].endswith(f'/themen/gebiet/{g.id}')
    assert g.erstellt_von == n.id and g.sprache_original == 'en' and not g.vorgegeben and not g.von_team
    resp = client.post(f'/themen/gebiet/{g.id}/diskussion/neu', data={'titel': 'Phosphor und Aktivität',
                                                                     'beschreibung': 'Frage zur Verfügbarkeit'})
    d = Diskussion.query.one()
    assert resp.headers['Location'].endswith(f'/themen/diskussion/{d.id}')
    seite = client.get(f'/themen/gebiet/{g.id}').get_data(as_text=True)
    assert 'Phosphor und Aktivität' in seite and 'Dr. T. Muster' in seite


def test_beitrag_antwort_und_anhang(client, app):
    n = _teilnehmer(client)
    d = _diskussion()
    resp = client.post(f'/themen/diskussion/{d.id}', data={
        'text': 'Erste Messreihe: siehe https://example.org/daten.csv.', 'art': 'messdaten', 'sprache': 'fr',
        'dateien': (io.BytesIO(b'zeit;wert'), 'reihe.csv')}, content_type='multipart/form-data')
    assert resp.status_code == 302
    b = Beitrag.query.one()
    assert b.autor_nutzer_id == n.id and b.art == 'messdaten' and b.sprache_original == 'fr'
    anhang = BeitragAnhang.query.one()
    pfad = kollaboration.anhang_pfad_in(anhang.dateiname, 'themen')
    assert os.path.exists(pfad) and os.sep + 'themen' + os.sep in pfad
    # Antwort, dann Antwort auf die Antwort -> haengt am selben Beitrag (eine Ebene)
    client.post(f'/themen/diskussion/{d.id}', data={'text': 'Danke!', 'antwort_auf': b.id})
    antwort = Beitrag.query.filter_by(text='Danke!').one()
    client.post(f'/themen/diskussion/{d.id}', data={'text': 'Auch von mir', 'antwort_auf': antwort.id})
    assert Beitrag.query.filter_by(text='Auch von mir').one().antwort_auf == b.id
    seite = client.get(f'/themen/diskussion/{d.id}').get_data(as_text=True)
    assert '<a href="https://example.org/daten.csv"' in seite      # Link klickbar, Punkt nicht im Link
    assert 'Messdaten' in seite and 'Dr. T. Muster' in seite and 'reihe.csv' in seite
    assert client.get(f'/themen/datei/{anhang.id}').data == b'zeit;wert'


def test_leerer_beitrag_geschlossen_und_ausgeblendet(client, app):
    _teilnehmer(client)
    d = _diskussion()
    seite = client.post(f'/themen/diskussion/{d.id}', data={'text': '  '}).get_data(as_text=True)
    assert 'Der Beitrag ist leer.' in seite
    d.geschlossen = True
    db.session.commit()
    assert client.post(f'/themen/diskussion/{d.id}', data={'text': 'x'}).status_code == 403
    assert 'geschlossen' in client.get(f'/themen/diskussion/{d.id}').get_data(as_text=True)
    d.sichtbar = False
    db.session.commit()
    assert client.get(f'/themen/diskussion/{d.id}').status_code == 404


def test_antwort_auf_beitrag_einer_anderen_diskussion_abgelehnt(client, app):
    _teilnehmer(client)
    d1, d2 = _diskussion(), _diskussion(titel='Zwei')
    fremd = Beitrag(diskussion_id=d2.id, text='x', von_team=True)
    db.session.add(fremd)
    db.session.commit()
    assert client.post(f'/themen/diskussion/{d1.id}', data={'text': 'y', 'antwort_auf': fremd.id}).status_code == 403


def test_eigenen_beitrag_bearbeiten_und_entfernen(client, app):
    n = _teilnehmer(client)
    d = _diskussion()
    andere = _nutzer('andere@example.com')
    eigen = Beitrag(diskussion_id=d.id, autor_nutzer_id=n.id, text='alt')
    fremd = Beitrag(diskussion_id=d.id, autor_nutzer_id=andere.id, text='fremd')
    db.session.add_all([eigen, fremd])
    db.session.commit()
    assert client.get(f'/themen/beitrag/{fremd.id}/bearbeiten').status_code == 403
    assert client.post(f'/themen/beitrag/{fremd.id}/entfernen').status_code == 403
    client.post(f'/themen/beitrag/{eigen.id}/bearbeiten', data={'text': 'neu', 'art': 'hypothese'})
    eigen = db.session.get(Beitrag, eigen.id)
    assert eigen.text == 'neu' and eigen.art == 'hypothese' and eigen.bearbeitet_am is not None
    # Antwort eines anderen auf den eigenen Beitrag bleibt nach dem Entfernen
    db.session.add(Beitrag(diskussion_id=d.id, antwort_auf=eigen.id, autor_nutzer_id=andere.id, text='Antwort'))
    db.session.add(BeitragAnhang(beitrag_id=eigen.id, dateiname='weg.csv', originalname='weg.csv', groesse=1))
    db.session.commit()
    pfad = kollaboration.anhang_pfad_in('weg.csv', 'themen')
    with open(pfad, 'wb') as f:
        f.write(b'x')
    client.post(f'/themen/beitrag/{eigen.id}/entfernen')
    eigen = db.session.get(Beitrag, eigen.id)
    assert eigen.text == '' and eigen.entfernt_am is not None and not os.path.exists(pfad)
    seite = client.get(f'/themen/diskussion/{d.id}').get_data(as_text=True)
    assert 'Beitrag von der Verfasserin bzw. dem Verfasser entfernt.' in seite and 'Antwort' in seite


def test_ehemaliges_mitglied_und_team(client, app):
    _teilnehmer(client)
    d = _diskussion()
    db.session.add_all([Beitrag(diskussion_id=d.id, text='Ohne Konto'),
                        Beitrag(diskussion_id=d.id, text='Vom Team', von_team=True)])
    db.session.commit()
    seite = client.get(f'/themen/diskussion/{d.id}').get_data(as_text=True)
    assert 'ehemaliges Mitglied' in seite and 'OpenMycoNet-Team' in seite


def test_neu_seit_dem_letzten_besuch(client, app):
    n = _teilnehmer(client)
    g = _gebiet()
    client.get('/themen')                               # erster Besuch setzt zuletzt_gesehen
    tn = db.session.get(ThemenTeilnahme, n.id)
    tn.zuletzt_gesehen = datetime.now(timezone.utc) - timedelta(days=1)
    db.session.commit()
    _diskussion(gebiet=g)
    seite = client.get('/themen').get_data(as_text=True)
    assert '1 neu seit dem letzten Besuch' in seite
    assert 'neu seit dem letzten Besuch' not in client.get('/themen').get_data(as_text=True)


def test_vertrauliche_anhaenge_nicht_ueber_themenraeume(client, app):
    """Ein Anhang aus dem vertraulichen Austausch ist ueber /themen/datei nicht abrufbar."""
    n = _teilnehmer(client)
    a = Austausch.query.filter_by(nutzer_id=n.id).one()
    k = Kommentar(text='vertraulich', autor='team', austausch_id=a.id)
    db.session.add(k)
    db.session.commit()
    ka = KollaborationAnhang(kommentar_id=k.id, dateiname='geheim.pdf', originalname='geheim.pdf', groesse=1)
    db.session.add(ka)
    db.session.commit()
    assert client.get(f'/themen/datei/{ka.id}').status_code == 404
    assert 'vertraulich' not in client.get('/themen').get_data(as_text=True)


def test_navigation_und_link_aus_dem_austausch(client, app):
    _teilnehmer(client)
    seite = client.get('/austausch').get_data(as_text=True)
    assert 'href="/themen"' in seite and 'Zu den Themenräumen' in seite


def test_verlinken_escaped_html():
    html = str(verlinken('<script>alert(1)</script> https://a.example/x?y=1&z=2, ende'))
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert '<a href="https://a.example/x?y=1&amp;z=2" rel="nofollow noopener noreferrer"' in html
    assert html.endswith(', ende')
