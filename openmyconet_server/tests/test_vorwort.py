"""Persoenliches Vorwort des Initiators (omn/vorwort.py, docs/vorwort_plan.md):
oeffentliche Seite ohne Kenntnisnahme, Eingangs-Pruefung vor Themenraeumen und Austausch,
Kenntnisnahme nur per POST, neue Fassung -> erneut, Schalter, Admin-Anzeige."""
import pytest
from test_themen import _teilnehmer

from omn import vorwort
from omn.extensions import db
from omn.models import VorwortKenntnis


@pytest.fixture()
def an(app):
    app.config['VORWORT_AKTIV'] = True
    return app


def test_oeffentliche_seite_ohne_kenntnisnahme(client, app):
    seite = client.get('/ueber-den-initiator?lang=de').get_data(as_text=True)
    assert 'Ein paar persönliche Worte' in seite and 'Gas-Wasser-Installateur' in seite
    assert 'initiator-portraet.webp' in seite and 'initiator-unterschrift-hell.png' in seite
    assert 'Gelesen – weiter' not in seite
    # auch mit ?kenntnisnahme=1, aber ohne Login: kein Knopf
    assert 'Gelesen – weiter' not in client.get('/ueber-den-initiator?kenntnisnahme=1').get_data(as_text=True)
    en = client.get('/ueber-den-initiator?lang=en').get_data(as_text=True)
    assert 'A few personal words' in en and 'the German original is authoritative' in en
    assert 'Über den Initiator' in client.get('/impressum.html?lang=de').get_data(as_text=True)   # Footer


def test_alle_sprachen_gleich_viele_absaetze(app):
    from omn.i18n import TRANSLATIONS
    keys = vorwort.absatz_keys()
    assert len(keys) == 12
    for sprache in ('de', 'en', 'nl', 'fr', 'es'):
        assert all(TRANSLATIONS[sprache].get(k) for k in keys), sprache
    assert 'welchen Beitrag er geleistet hat' in ' '.join(TRANSLATIONS['de'][k] for k in keys)


def test_eingangspruefung_themenraeume(client, an):
    n = _teilnehmer(client)
    r = client.get('/themen?lang=de')
    assert r.status_code == 302 and '/ueber-den-initiator?kenntnisnahme=1' in r.headers['Location']
    seite = client.get(r.headers['Location']).get_data(as_text=True)
    assert 'Gelesen – weiter' in seite and 'name="weiter" value="/themen?lang=de"' in seite
    assert 'type="checkbox"' not in seite                              # kein Haken (Robby 29.10.2026)
    assert VorwortKenntnis.query.count() == 0                       # Aufrufen speichert nichts
    r = client.post('/dashboard/vorwort', data={'weiter': '/themen?lang=de'})
    assert r.headers['Location'].endswith('/themen?lang=de')
    k = VorwortKenntnis.query.one()
    assert k.nutzer_id == n.id and k.fassung == vorwort.VORWORT_FASSUNG
    assert client.get('/themen?lang=de').status_code == 200
    # danach: kein Haken mehr, nur "Zur Kenntnis genommen am"
    seite = client.get('/ueber-den-initiator?kenntnisnahme=1&lang=de').get_data(as_text=True)
    assert 'Gelesen – weiter' not in seite and 'Zur Kenntnis genommen am' in seite


def test_eingangspruefung_austausch_und_neue_fassung(client, an, monkeypatch):
    _teilnehmer(client)
    r = client.get('/austausch')
    assert r.status_code == 302 and 'kenntnisnahme=1' in r.headers['Location']
    client.post('/dashboard/vorwort', data={'weiter': '/austausch'})
    assert client.get('/austausch').status_code == 200
    monkeypatch.setattr(vorwort, 'VORWORT_FASSUNG', '2099-01-01')      # wesentliche Aenderung
    assert client.get('/austausch').status_code == 302


def test_fremdes_ziel_und_schalter_aus(client, app):
    _teilnehmer(client)
    assert client.get('/themen').status_code == 200                    # Schalter aus (TestConfig)
    app.config['VORWORT_AKTIV'] = True
    r = client.post('/dashboard/vorwort', data={'weiter': 'https://example.org/'})
    assert r.headers['Location'].endswith('/dashboard')


def test_admin_zeigt_kenntnisnahme(client, an, superadmin):
    from conftest import eingeloggt
    from omn.models import Austausch
    n = _teilnehmer(client)
    a = Austausch.query.filter_by(nutzer_id=n.id).one()
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    assert 'noch nicht zur Kenntnis genommen' in client.get(f'/admin/austausch/{a.id}').get_data(as_text=True)
    vorwort.bestaetigen(n)
    seite = client.get(f'/admin/austausch/{a.id}').get_data(as_text=True)
    assert 'zur Kenntnis genommen am' in seite and 'veraltet' not in seite


def test_kontoloeschung_entfernt_kenntnisnahme(client, an):
    n = _teilnehmer(client)
    vorwort.bestaetigen(n)
    db.session.delete(n)
    db.session.commit()
    assert VorwortKenntnis.query.count() == 0


def test_llms_nennt_seite(client):
    assert '/ueber-den-initiator' in client.get('/llms.txt').get_data(as_text=True)
