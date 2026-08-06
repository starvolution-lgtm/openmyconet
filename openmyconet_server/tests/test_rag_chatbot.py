"""Regressionstest fuer die dokumentierte Ranking-Schwaeche in rag_chatbot.py:
kurze, generische Woerter durften nicht mehr per Zufalls-Textfragment einen
thematisch unverwandten Synonym-Key triggern (z.B. "daten" in "datenschutz")."""

from rag_chatbot import expand_keywords, find_chunks


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
