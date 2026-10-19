"""Regressionstest fuer die dokumentierte Ranking-Schwaeche in rag_chatbot.py:
kurze, generische Woerter durften nicht mehr per Zufalls-Textfragment einen
thematisch unverwandten Synonym-Key triggern (z.B. "daten" in "datenschutz")."""

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
    content = [type('T', (), {'text': 'Antwort'})()]


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
