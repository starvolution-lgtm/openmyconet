"""Wissenschaftliche Themenraeume (Phase 2a, docs/austausch_phase2_plan.md).
Schritt 1: Datenmodell, Berechtigung, Original + Uebersetzung."""
from omn.extensions import db
from omn.models import (
    Austausch, Beitrag, BeitragAnhang, Diskussion, Foerderer, Nutzer, ThemenTeilnahme, Themengebiet, Uebersetzung,
)
from omn.themen import anzeige, darf_themenraeume_nutzen, quelltext_hash, uebersetzungen_loeschen


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
