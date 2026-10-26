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
                  'sprache_original': 'de', 'uebersetzt': True, 'automatisch': False, 'nachladen': False,
                  'typ': 'themengebiet', 'id': g.id, 'feld': 'titel'}
    assert anzeige(g, 'titel', 'de')['uebersetzt'] is False
    assert anzeige(g, 'titel', 'de')['nachladen'] is False          # Originalsprache: nichts zu tun
    nl = anzeige(g, 'titel', 'nl')
    assert (nl['text'], nl['uebersetzt'], nl['nachladen']) == ('Mykologie & Mykorrhiza', False, True)
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


# --- Schritt 3: aehnliche Themen, Schalter fuer Prod ------------------------------

def test_woerter_finden_sich_ueber_sprachen_hinweg():
    from omn.themen import woerter
    assert woerter('Mykorrhiza und Phosphor') & woerter('Mycology & mycorrhiza') == {'mikorh'}
    assert woerter('Mycologie & mycorhize') & woerter('Mykorrhiza') == {'mikorh'}
    assert woerter('Elektrische Signale') == woerter('Electrical signals')
    assert woerter('und die der with from about') == set()     # nur Fuellwoerter / zu kurz


def test_neues_gebiet_zeigt_aehnliche_ueber_uebersetzungen(client, app):
    _teilnehmer(client)
    g = _gebiet(titel='Mykologie & Mykorrhiza', beschreibung='Pilzphysiologie und Symbiosen', vorgegeben=True)
    db.session.add(Uebersetzung(inhalt_typ='themengebiet', inhalt_id=g.id, feld='titel', ziel_sprache='en',
                                quelltext_hash=quelltext_hash(g.titel), text='Mycology & mycorrhiza'))
    db.session.commit()
    daten = {'titel': 'Mycorrhizal networks', 'beschreibung': 'Exchange of nutrients', 'sprache': 'en'}
    seite = client.post('/themen/gebiet/neu?lang=de', data=daten).get_data(as_text=True)
    assert 'Ähnliche Themen gibt es schon' in seite
    assert f'/themen/gebiet/{g.id}' in seite and 'Trotzdem anlegen' in seite
    assert 'value="Mycorrhizal networks"' in seite                 # Eingaben bleiben erhalten
    assert Themengebiet.query.count() == 1
    resp = client.post('/themen/gebiet/neu', data={**daten, 'trotzdem': '1'})
    assert resp.status_code == 302 and Themengebiet.query.count() == 2


def test_ohne_aehnliche_wird_direkt_angelegt(client, app):
    _teilnehmer(client)
    _gebiet(titel='Mykologie & Mykorrhiza', beschreibung='Pilzphysiologie')
    resp = client.post('/themen/gebiet/neu', data={'titel': 'Bodenfeuchte im Winter', 'beschreibung': 'Frostperioden'})
    assert resp.status_code == 302 and Themengebiet.query.count() == 2


def test_aehnliche_diskussionen_nur_im_selben_gebiet(client, app):
    _teilnehmer(client)
    g1, g2 = _gebiet(titel='Eins'), _gebiet(titel='Zwei')
    _diskussion(gebiet=g2, titel='Calcium-Oszillationen im Myzel', beschreibung='Messungen')
    daten = {'titel': 'Calcium oscillations', 'beschreibung': 'Imaging data'}
    resp = client.post(f'/themen/gebiet/{g1.id}/diskussion/neu', data=daten)
    assert resp.status_code == 302                                   # anderes Gebiet -> kein Treffer
    seite = client.post(f'/themen/gebiet/{g2.id}/diskussion/neu', data=daten).get_data(as_text=True)
    assert 'Ähnliche Themen gibt es schon' in seite and 'Calcium-Oszillationen im Myzel' in seite


def test_schalter_verbirgt_themenraeume(client, app):
    _teilnehmer(client)
    app.config['THEMEN_FREIGEGEBEN'] = False
    for pfad in ('/themen', '/themen/teilnahme', '/themen/gebiet/neu', '/themen/einstellungen'):
        assert client.get(pfad).status_code == 404, pfad
    seite = client.get('/austausch').get_data(as_text=True)
    assert '/themen' not in seite and 'Themenräume' not in seite


def test_schalter_seit_freigabe_ueberall_an_per_env_abschaltbar(monkeypatch):
    """Seit Robbys Freigabe (25.10.2026) standardmaessig an, auch auf Prod;
    THEMEN_FREIGEGEBEN=0 schliesst die Themenraeume wieder."""
    import importlib

    import omn.config as konfig
    monkeypatch.delenv('THEMEN_FREIGEGEBEN', raising=False)
    try:
        monkeypatch.setenv('OMN_ENV', 'prod')
        assert importlib.reload(konfig).Config.THEMEN_FREIGEGEBEN is True
        monkeypatch.setenv('THEMEN_FREIGEGEBEN', '0')
        assert importlib.reload(konfig).Config.THEMEN_FREIGEGEBEN is False
    finally:
        monkeypatch.undo()
        importlib.reload(konfig)


# --- Schritt 4: Moderation im Admin -------------------------------------------------

def _admin(client):
    from conftest import eingeloggt
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')


def test_admin_themen_nur_superadmin(client, app, editor):
    from conftest import eingeloggt
    _gebiet()
    eingeloggt(client, 'editor_test', 'auch-geheim-123')
    assert client.get('/admin/themen').status_code == 403
    assert client.post('/admin/themen/gebiet/1/loeschen').status_code == 403
    assert Themengebiet.query.count() == 1


def test_admin_uebersicht_und_team_gebiet(client, app, superadmin):
    from omn.models import AdminAudit
    _admin(client)
    assert client.get('/admin/themen').status_code == 200
    resp = client.post('/admin/themen/gebiet/neu', data={'titel': 'Netzwerkmodelle', 'beschreibung': 'Graphen',
                                                         'sprache': 'en'})
    g = Themengebiet.query.one()
    assert resp.headers['Location'].endswith(f'/admin/themen/gebiet/{g.id}')
    assert g.von_team and g.sprache_original == 'en'
    assert 'themen_gebiet_angelegt' in [a.aktion for a in AdminAudit.query.all()]


def test_admin_umbenennen_bindet_handuebersetzungen_neu(client, app, superadmin):
    g = _gebiet()
    db.session.add(Uebersetzung(inhalt_typ='themengebiet', inhalt_id=g.id, feld='titel', ziel_sprache='en',
                                quelltext_hash=quelltext_hash(g.titel), text='Alt'))
    db.session.commit()
    _admin(client)
    client.post(f'/admin/themen/gebiet/{g.id}', data={
        'titel': 'Mykologie, Mykorrhiza & Symbiosen', 'beschreibung': 'Neu', 'sprache': 'de', 'reihenfolge': '3',
        'u_en_titel': 'Mycology, mycorrhiza & symbioses', 'u_fr_beschreibung': 'Nouveau'})
    g = db.session.get(Themengebiet, g.id)
    assert g.titel == 'Mykologie, Mykorrhiza & Symbiosen' and g.reihenfolge == 3
    assert anzeige(g, 'titel', 'en')['text'] == 'Mycology, mycorrhiza & symbioses'
    assert anzeige(g, 'beschreibung', 'fr')['text'] == 'Nouveau'
    assert Uebersetzung.query.filter_by(text='Alt').count() == 0
    assert Uebersetzung.query.count() == 2


def test_admin_zusammenfuehren(client, app, superadmin):
    a, b = _gebiet(titel='Mykorrhiza'), _gebiet(titel='Mycorrhiza (doppelt)')
    alt = _gebiet(titel='Schon frueher hierher', sichtbar=False, zusammengefuehrt_in=b.id)
    d = _diskussion(gebiet=b)
    _admin(client)
    assert client.post(f'/admin/themen/gebiet/{b.id}/zusammenfuehren', data={'ziel_id': b.id}).status_code == 302
    assert db.session.get(Themengebiet, b.id).zusammengefuehrt_in is None      # nicht mit sich selbst
    client.post(f'/admin/themen/gebiet/{b.id}/zusammenfuehren', data={'ziel_id': a.id})
    b, alt, d = db.session.get(Themengebiet, b.id), db.session.get(Themengebiet, alt.id), db.session.get(Diskussion, d.id)
    assert d.themengebiet_id == a.id
    assert b.zusammengefuehrt_in == a.id and not b.sichtbar
    assert alt.zusammengefuehrt_in == a.id                                      # keine Weiterleitungsketten
    # Teilnehmende werden von der alten Adresse weitergeleitet
    teilnehmer = app.test_client()
    _teilnehmer(teilnehmer)
    resp = teilnehmer.get(f'/themen/gebiet/{b.id}')
    assert resp.status_code == 301 and resp.headers['Location'].endswith(f'/themen/gebiet/{a.id}')


def test_admin_gebiet_ausblenden_und_loeschen(client, app, superadmin):
    g = _gebiet()
    d = _diskussion(gebiet=g)
    b = Beitrag(diskussion_id=d.id, text='mit Datei', von_team=True)
    db.session.add(b)
    db.session.commit()
    db.session.add(BeitragAnhang(beitrag_id=b.id, dateiname='g.csv', originalname='g.csv', groesse=1))
    db.session.add(Uebersetzung(inhalt_typ='themengebiet', inhalt_id=g.id, feld='titel', ziel_sprache='en',
                                quelltext_hash=quelltext_hash(g.titel), text='x'))
    db.session.commit()
    pfad = kollaboration.anhang_pfad_in('g.csv', 'themen')
    with open(pfad, 'wb') as f:
        f.write(b'x')
    teilnehmer = app.test_client()
    _teilnehmer(teilnehmer)
    _admin(client)
    client.post(f'/admin/themen/gebiet/{g.id}/ausblenden')
    assert teilnehmer.get(f'/themen/gebiet/{g.id}').status_code == 404
    assert teilnehmer.get(f'/themen/diskussion/{d.id}').status_code == 404
    client.post(f'/admin/themen/gebiet/{g.id}/einblenden')
    assert teilnehmer.get(f'/themen/gebiet/{g.id}').status_code == 200
    client.post(f'/admin/themen/gebiet/{g.id}/loeschen')
    assert Themengebiet.query.count() == Diskussion.query.count() == Beitrag.query.count() == 0
    assert Uebersetzung.query.count() == 0 and not os.path.exists(pfad)


def test_admin_diskussion_moderieren(client, app, superadmin):
    g1, g2 = _gebiet(titel='Eins'), _gebiet(titel='Zwei')
    d = _diskussion(gebiet=g1)
    teilnehmer = app.test_client()
    _teilnehmer(teilnehmer)
    _admin(client)
    client.post(f'/admin/themen/diskussion/{d.id}/verschieben', data={'gebiet_id': g2.id})
    assert db.session.get(Diskussion, d.id).themengebiet_id == g2.id
    client.post(f'/admin/themen/diskussion/{d.id}/schliessen')
    assert teilnehmer.post(f'/themen/diskussion/{d.id}', data={'text': 'x'}).status_code == 403
    client.post(f'/admin/themen/diskussion/{d.id}/oeffnen')
    assert teilnehmer.post(f'/themen/diskussion/{d.id}', data={'text': 'x'}).status_code == 302
    client.post(f'/admin/themen/diskussion/{d.id}/ausblenden')
    assert teilnehmer.get(f'/themen/diskussion/{d.id}').status_code == 404
    client.post(f'/admin/themen/diskussion/{d.id}/einblenden')
    client.post(f'/admin/themen/diskussion/{d.id}/loeschen')
    assert Diskussion.query.count() == 0 and Beitrag.query.count() == 0


def test_admin_beitrag_moderieren_und_team_beitrag(client, app, superadmin):
    d = _diskussion()
    teilnehmer = app.test_client()
    n = _teilnehmer(teilnehmer)
    b = Beitrag(diskussion_id=d.id, autor_nutzer_id=n.id, text='UNPASSEND-MARKER')
    db.session.add(b)
    db.session.commit()
    antwort = Beitrag(diskussion_id=d.id, antwort_auf=b.id, autor_nutzer_id=n.id, text='Antwort bleibt')
    db.session.add(antwort)
    db.session.commit()
    _admin(client)
    assert 'UNPASSEND-MARKER' in client.get(f'/admin/themen/diskussion/{d.id}').get_data(as_text=True)
    client.post(f'/admin/themen/beitrag/{b.id}/ausblenden')
    seite = teilnehmer.get(f'/themen/diskussion/{d.id}').get_data(as_text=True)
    assert 'UNPASSEND-MARKER' not in seite and 'Antwort bleibt' in seite
    client.post(f'/admin/themen/beitrag/{b.id}/einblenden')
    client.post(f'/admin/themen/beitrag/{b.id}/loeschen')
    assert db.session.get(Beitrag, b.id) is None
    assert db.session.get(Beitrag, antwort.id).antwort_auf is None
    client.post(f'/admin/themen/diskussion/{d.id}', data={'text': 'Hinweis vom Team', 'art': 'literatur'})
    team = Beitrag.query.filter_by(text='Hinweis vom Team').one()
    assert team.von_team and team.autor_nutzer_id is None
    assert 'OpenMycoNet-Team' in teilnehmer.get(f'/themen/diskussion/{d.id}').get_data(as_text=True)


# --- Schritt 5: Regeln, Kontoloeschung, Fristen, Datenschutzerklaerung --------------

def test_nutzungsregeln_mit_cc_by_in_allen_sprachen(client, app):
    from omn.i18n import LANGS, TRANSLATIONS
    for lang in LANGS:
        text = TRANSLATIONS[lang]['themen_regeln_text']
        assert 'CC BY 4.0' in text and '6' in text and 'kontakt@openmyconet.de' in text, lang
    _teilnehmer(client, anzeigename=None)
    seite = client.get('/themen/teilnahme').get_data(as_text=True)
    assert 'CC BY 4.0' in seite and 'creativecommons.org/licenses/by/4.0/deed.de' in seite
    d = _diskussion()
    client.post('/themen/teilnahme', data={'anzeigename': 'X', 'regeln': '1'})
    assert 'CC BY 4.0' in client.get(f'/themen/diskussion/{d.id}').get_data(as_text=True)


def test_kontoloeschung_im_admin_behaelt_beitraege_ohne_namen(client, app, superadmin):
    n = _nutzer('weg@example.com')
    db.session.add(ThemenTeilnahme(nutzer_id=n.id, anzeigename='ANZEIGENAME-MARKER', regeln_fassung=REGELN_FASSUNG))
    d = _diskussion(erstellt_von=n.id)
    b = Beitrag(diskussion_id=d.id, autor_nutzer_id=n.id, text='Wissen, das bleibt')
    db.session.add(b)
    db.session.commit()
    db.session.add(BeitragAnhang(beitrag_id=b.id, dateiname='bleibt.csv', originalname='bleibt.csv', groesse=1))
    db.session.commit()
    _admin(client)
    seite = client.post(f'/admin/nutzer/loeschen/{n.id}', follow_redirects=True).get_data(as_text=True)
    assert 'bleiben ohne Namen' in seite
    b = db.session.get(Beitrag, b.id)
    assert b.text == 'Wissen, das bleibt' and b.autor_nutzer_id is None and not b.von_team
    assert BeitragAnhang.query.count() == 1 and ThemenTeilnahme.query.count() == 0
    teilnehmer = app.test_client()
    _teilnehmer(teilnehmer)
    seite = teilnehmer.get(f'/themen/diskussion/{d.id}').get_data(as_text=True)
    assert 'Wissen, das bleibt' in seite and 'ehemaliges Mitglied' in seite and 'ANZEIGENAME-MARKER' not in seite


def test_ausgeblendete_beitraege_nach_6_monaten_geloescht(client, app, superadmin):
    from omn.aufbewahrung import bereinigen
    d = _diskussion()
    alt = Beitrag(diskussion_id=d.id, text='alt', von_team=True, sichtbar=False,
                  ausgeblendet_am=datetime.now(timezone.utc) - timedelta(days=190))
    frisch = Beitrag(diskussion_id=d.id, text='frisch', von_team=True, sichtbar=False,
                     ausgeblendet_am=datetime.now(timezone.utc) - timedelta(days=100))
    sichtbar = Beitrag(diskussion_id=d.id, text='sichtbar', von_team=True)
    db.session.add_all([alt, frisch, sichtbar])
    db.session.commit()
    antwort = Beitrag(diskussion_id=d.id, text='Antwort', von_team=True, antwort_auf=alt.id)
    db.session.add(antwort)
    db.session.add(BeitragAnhang(beitrag_id=alt.id, dateiname='alt.csv', originalname='alt.csv', groesse=1))
    db.session.commit()
    pfad = kollaboration.anhang_pfad_in('alt.csv', 'themen')
    with open(pfad, 'wb') as f:
        f.write(b'x')
    assert bereinigen()['Themenräume ausgeblendete Beiträge'] == 1
    assert {x.text for x in Beitrag.query.all()} == {'frisch', 'sichtbar', 'Antwort'}
    assert db.session.get(Beitrag, antwort.id).antwort_auf is None
    assert not os.path.exists(pfad)


def test_ausblenden_setzt_zeitpunkt_einblenden_loescht_ihn(client, app, superadmin):
    d = _diskussion()
    b = Beitrag(diskussion_id=d.id, text='x', von_team=True)
    db.session.add(b)
    db.session.commit()
    _admin(client)
    client.post(f'/admin/themen/beitrag/{b.id}/ausblenden')
    assert db.session.get(Beitrag, b.id).ausgeblendet_am is not None
    client.post(f'/admin/themen/beitrag/{b.id}/einblenden')
    assert db.session.get(Beitrag, b.id).ausgeblendet_am is None


def test_datenschutzerklaerung_abschnitt_themenraeume(client):
    from omn.i18n import LANGS
    from omn.rechtstexte import RECHTSTEXTE
    for lang in LANGS:
        ab = RECHTSTEXTE[lang]['datenschutz']['abschnitte']
        ids = [x['id'] for x in ab]
        assert ids.index('themenraeume') == ids.index('austausch') + 1, lang
        text = next(x['html'] for x in ab if x['id'] == 'themenraeume')
        assert 'CC BY 4.0' in text and '6' in text and 'kontakt@openmyconet.de' in text, lang
        assert [int(x['h'].split('.')[0]) for x in ab] == list(range(1, len(ab) + 1)), lang
    seite = client.get('/datenschutz.html').get_data(as_text=True)
    assert 'id="themenraeume"' in seite and '10. Wissenschaftliche Themenräume' in seite


def test_verlinken_escaped_html():
    html = str(verlinken('<script>alert(1)</script> https://a.example/x?y=1&z=2, ende'))
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert '<a href="https://a.example/x?y=1&amp;z=2" rel="nofollow noopener noreferrer"' in html
    assert html.endswith(', ende')
