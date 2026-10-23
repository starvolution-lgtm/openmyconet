"""KI-Uebersetzungsentwurf fuer News (omn/admin/news.py::news_uebersetzen).

Loest das wiederkehrende "Text uebersetzen, Bild neu einfuegen, Tags neu
eintippen"-Problem beim Anlegen einer Story in allen 5 Sprachen. Kein Test
hier ruft die echte Anthropic-API -- _uebersetzung_anfordern() wird
monkeypatcht, genau wie andere aeussere Abhaengigkeiten in dieser Suite
(bzw. am Ende: echtes SDK gegen eine Attrappe statt der API)."""
import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from conftest import eingeloggt
from omn.admin import news as news_mod
from omn.extensions import db
from omn.models import News


def _quelle_anlegen(client):
    daten = {
        'titel': 'Neuer Knoten im Wald', 'untertitel': 'Ein Meilenstein',
        'inhalt': '<p>Wir haben einen neuen Knoten installiert.</p>', 'sprache': 'de', 'tags': 'Update',
    }
    client.post('/admin/news', data=daten, follow_redirects=True)
    with client.application.app_context():
        return News.query.filter_by(titel='Neuer Knoten im Wald').first().id


def test_neue_news_bekommt_uebersetzung_gruppe(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    news_id = _quelle_anlegen(client)
    with app.app_context():
        news = News.query.get(news_id)
        assert news.uebersetzung_gruppe
        assert len(news.uebersetzung_gruppe) == 32  # uuid4().hex


def test_edit_zeigt_alle_vier_fehlenden_sprachen(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    news_id = _quelle_anlegen(client)
    html = client.get(f'/admin/news/edit/{news_id}').get_data(as_text=True)
    for sprache in ('English', 'Nederlands', 'Français', 'Español'):
        assert sprache in html
    assert 'Entwurf erzeugen' in html


def test_uebersetzung_get_zeigt_ki_entwurf_ohne_zu_speichern(client, app, superadmin, monkeypatch):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    news_id = _quelle_anlegen(client)

    monkeypatch.setattr(
        news_mod, '_uebersetzung_anfordern',
        lambda news, ziel_sprache: (
            'TITEL: New Node in the Forest\n'
            'UNTERTITEL: A milestone\n'
            'INHALT:\n<p>We installed a new node.</p>'
        ),
    )
    r = client.get(f'/admin/news/{news_id}/uebersetzen/en')
    html = r.get_data(as_text=True)
    assert 'New Node in the Forest' in html
    assert 'A milestone' in html
    with app.app_context():
        assert News.query.filter_by(sprache='en').count() == 0  # nichts gespeichert


def test_uebersetzung_ohne_api_key_zeigt_fallback_statt_zu_crashen(client, app, superadmin, monkeypatch):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    news_id = _quelle_anlegen(client)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)

    r = client.get(f'/admin/news/{news_id}/uebersetzen/en')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Neuer Knoten im Wald' in html  # Originaltext als Fallback
    assert 'nicht möglich' in html


def test_uebersetzung_post_speichert_mit_selber_gruppe_und_bild(client, app, superadmin, monkeypatch):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    news_id = _quelle_anlegen(client)
    with app.app_context():
        quelle = News.query.get(news_id)
        quelle.bild_dateiname = 'beispiel.webp'
        db.session.commit()
        gruppe = quelle.uebersetzung_gruppe

    client.post(f'/admin/news/{news_id}/uebersetzen/en', data={
        'titel': 'New Node in the Forest', 'untertitel': 'A milestone',
        'inhalt': '<p>We installed a new node.</p>', 'tags': 'Update',
    }, follow_redirects=True)

    with app.app_context():
        neu = News.query.filter_by(sprache='en').first()
        assert neu is not None
        assert neu.uebersetzung_gruppe == gruppe
        assert neu.bild_dateiname == 'beispiel.webp'  # von der Quelle uebernommen, kein Re-Upload


def test_uebersetzung_existiert_schon_leitet_zu_bestehender_weiter(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    news_id = _quelle_anlegen(client)
    with app.app_context():
        quelle = News.query.get(news_id)
        bestehend = News(titel='Existing EN', inhalt='x', sprache='en', slug='existing-en',
                          uebersetzung_gruppe=quelle.uebersetzung_gruppe)
        db.session.add(bestehend)
        db.session.commit()
        bestehend_id = bestehend.id

    r = client.get(f'/admin/news/{news_id}/uebersetzen/en', follow_redirects=False)
    assert r.status_code == 302
    assert f'/admin/news/edit/{bestehend_id}' in r.headers['Location']


def test_uebersetzung_gleiche_sprache_wie_quelle_ist_ungueltig(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    news_id = _quelle_anlegen(client)
    r = client.get(f'/admin/news/{news_id}/uebersetzen/de')
    assert r.status_code == 400


# --- Echtes SDK (anthropic 1.x) gegen eine Attrappe statt der API ---

_ECHTER_CLIENT = anthropic.Anthropic
_NEWS = SimpleNamespace(titel='Titel', untertitel='', inhalt='<p>Text</p>')


def _sdk_mit_antwort(monkeypatch, content, stop_reason='end_turn'):
    gesendet = {}

    def handler(anfrage):
        gesendet.update(json.loads(anfrage.content))
        return httpx2.Response(200, json={
            'id': 'msg_test', 'type': 'message', 'role': 'assistant', 'model': 'claude-sonnet-5-5',
            'content': content, 'stop_reason': stop_reason, 'stop_sequence': None,
            'usage': {'input_tokens': 10, 'output_tokens': 5}})

    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test')
    monkeypatch.setattr('omn.admin.news.anthropic.Anthropic', lambda **kw: _ECHTER_CLIENT(
        **kw, http_client=httpx2.Client(transport=httpx2.MockTransport(handler))))
    return gesendet


def test_uebersetzung_echtes_sdk_liest_text(monkeypatch):
    gesendet = _sdk_mit_antwort(monkeypatch, [
        {'type': 'thinking', 'thinking': '', 'signature': 'sig'},
        {'type': 'text', 'text': 'TITEL: Title\nUNTERTITEL: LEER\nINHALT:\n<p>Text</p>'},
    ])
    assert news_mod._uebersetzung_anfordern(_NEWS, 'en').startswith('TITEL: Title')
    assert gesendet['model'] == 'claude-sonnet-5-5'
    assert gesendet['thinking'] == {'type': 'between_tools'}


def test_uebersetzung_echtes_sdk_ablehnung_wird_fehler(monkeypatch):
    _sdk_mit_antwort(monkeypatch, [], stop_reason='refusal')
    with pytest.raises(news_mod.NewsUebersetzungFehler):
        news_mod._uebersetzung_anfordern(_NEWS, 'en')
