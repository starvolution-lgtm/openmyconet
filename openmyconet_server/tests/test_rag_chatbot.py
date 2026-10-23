"""Regressionstest fuer die dokumentierte Ranking-Schwaeche in rag_chatbot.py:
kurze, generische Woerter durften nicht mehr per Zufalls-Textfragment einen
thematisch unverwandten Synonym-Key triggern (z.B. "daten" in "datenschutz")."""

import json

import anthropic
import httpx2

from omn.rag_chatbot import expand_keywords, find_chunks


def test_daten_triggert_nicht_mehr_datenschutz_synonyme():
    expanded = expand_keywords(['daten'])
    assert 'gps' not in expanded
    assert 'privat' not in expanded
    assert 'anonym' not in expanded


def test_operation_triggert_nicht_mehr_kooperation_synonyme():
    expanded = expand_keywords(['operation'])
    assert 'paypal' not in expanded
    assert 'sponsor' not in expanded


def test_eigener_key_matcht_weiterhin_sich_selbst():
    expanded = expand_keywords(['datenschutz'])
    assert 'gps' in expanded
    assert 'privat' in expanded


def test_flexionsform_matcht_weiterhin_den_key():
    # "verfügbarkeit" ist eine Flexionsform von "verfügbar" -- diese Richtung
    # (key in Query-Wort enthalten) soll weiterhin funktionieren.
    expanded = expand_keywords(['verfügbarkeit'])
    assert 'pcb' in expanded


def test_daten_allein_bevorzugt_nicht_mehr_datenschutz_chunk():
    # Vor dem Fix gewann Chunk 4 ("Datenschutz & Transparenz") hier klar durch
    # die zusaetzlich injizierten Synonyme "gps"/"datenschutz" -- jetzt zaehlt
    # nur noch der tatsaechliche Wortvorkommen-Treffer von "daten", den auch
    # andere Chunks (z.B. "Messdaten") gleichwertig haben.
    ergebnis = find_chunks('Daten', 'de', top_k=1)
    assert ergebnis[0]['id'] != 4


def test_mycorrhiza_lateinische_schreibweise_matcht_mykorrhiza_chunk():
    # "Mycorrhiza" (c) matchte bisher nicht "Mykorrhiza" (y) in den deutschen
    # Chunks -- eine Anfrage wie "Studien zu Mycorrhiza und CO2" fand dadurch
    # den Chunk mit den Kohlenstoff-Studien (Soudzilovskaia/Hu/Mason) gar
    # nicht. expand_keywords() muss jetzt "mykorrhiza" injizieren.
    expanded = expand_keywords(['mycorrhiza'])
    assert 'mykorrhiza' in expanded


def test_co2_abkuerzung_wird_zu_kohlenstoff_normalisiert():
    ergebnis = find_chunks('wo finde ich Studien zu Mycorrhiza und CO2', 'de', top_k=5)
    assert any(c['slug'] == 'mykorrhiza-grundlagen' for c in ergebnis)


class _FakeAntwort:
    stop_reason = 'end_turn'
    content = [type('T', (), {'type': 'text', 'text': 'Antwort'})()]


class _FakeClient:
    def __init__(self, **kw):
        self.messages = self

    def create(self, **kw):
        _FakeClient.letzter_aufruf = kw
        return _FakeAntwort()


def test_chat_zu_lange_nachricht_wird_abgewiesen(client):
    resp = client.post('/api/chat', json={'message': 'x' * 5000})
    assert resp.status_code == 400


def test_chat_ungueltiger_verlauf_fuehrt_nicht_zu_500(client, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test')
    monkeypatch.setattr('omn.rag_chatbot.anthropic.Anthropic', _FakeClient)
    verlauf = ['kein objekt', 5, None, {'role': 'user', 'content': 7}, {'role': 'system', 'content': 'x'},
               {'role': 'user', 'content': 'a' * 5000}]
    resp = client.post('/api/chat', json={'message': 'Was ist OpenMycoNet?', 'history': verlauf})
    assert resp.status_code == 200
    gesendet = _FakeClient.letzter_aufruf['messages']
    assert all(len(m['content']) <= 2000 for m in gesendet)
    assert [m['role'] for m in gesendet] == ['user', 'user']   # nur der gueltige Verlaufseintrag + die Frage


def test_chat_json_kein_objekt_400(client):
    assert client.post('/api/chat', json=['x']).status_code == 400


# --- Echtes SDK (anthropic 1.x) gegen eine Attrappe statt der API ---
# Prueft Anfrage + Antwort-Auswertung mit dem echten Client, ohne Netz und Key.

_ECHTER_CLIENT = anthropic.Anthropic

def _sdk_mit_antwort(monkeypatch, antwort_json):
    gesendet = {}

    def handler(anfrage):
        gesendet.update(json.loads(anfrage.content))
        return httpx2.Response(200, json=antwort_json)

    def fabrik(**kw):
        return _ECHTER_CLIENT(**kw, http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))

    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test')
    monkeypatch.setattr('omn.rag_chatbot.anthropic.Anthropic', fabrik)
    return gesendet


def _antwort(content, stop_reason='end_turn'):
    return {'id': 'msg_test', 'type': 'message', 'role': 'assistant', 'model': 'claude-sonnet-5-5',
            'content': content, 'stop_reason': stop_reason, 'stop_sequence': None,
            'usage': {'input_tokens': 10, 'output_tokens': 5}}


def test_chat_echtes_sdk_liest_text_nach_thinking_block(client, monkeypatch):
    gesendet = _sdk_mit_antwort(monkeypatch, _antwort([
        {'type': 'thinking', 'thinking': '', 'signature': 'sig'},
        {'type': 'text', 'text': 'Hallo aus dem Test'},
    ]))
    resp = client.post('/api/chat', json={'message': 'Was ist OpenMycoNet?'})
    assert resp.status_code == 200
    assert resp.get_json()['answer'] == 'Hallo aus dem Test'
    assert gesendet['model'] == 'claude-sonnet-5-5'
    assert gesendet['thinking'] == {'type': 'between_tools'}


def test_chat_echtes_sdk_ablehnung_gibt_502(client, monkeypatch):
    _sdk_mit_antwort(monkeypatch, _antwort([], stop_reason='refusal'))
    resp = client.post('/api/chat', json={'message': 'Was ist OpenMycoNet?'})
    assert resp.status_code == 502
