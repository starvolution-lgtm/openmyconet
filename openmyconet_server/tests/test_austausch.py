"""Tests fuer den fachlichen Austausch mit eingeladenen Fachkontakten
(docs/austausch_phase1_plan.md). Schritt 1: Modell + Kontext-Spalten."""
from omn.extensions import db
from omn.models import Austausch, Aufgabe, Kommentar, Foerderer, Nutzer
from omn.site_live import _aktive_foerderer


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
