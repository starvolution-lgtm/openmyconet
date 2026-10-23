"""Gemeinsames fuer die Claude-Aufrufe (Chatbot omn/rag_chatbot.py, News-Uebersetzung
omn/admin/news.py), seit dem SDK-Wechsel anthropic 0.x -> 1.x (23.10.2026).

- MODELL: aktuelles Sonnet. Claude Sonnet 5.5 denkt standardmaessig ("adaptive thinking");
  DENKEN_AUS schaltet das ab ("between_tools" = niedrigste Stufe, ohne Werkzeuge also
  gar kein Nachdenken) -- so verhalten sich beide Aufrufe wie vorher mit Sonnet 4.6
  (keine Denk-Tokens, die von max_tokens abgehen, keine Wartezeit).
- antwort_text(): Antwort nach Block-Typ lesen statt content[0].text, weil neuere
  Modelle vor dem Text einen (leeren) thinking-Block liefern koennen. Lehnt das Modell
  ab (stop_reason "refusal") oder kommt kein Text, gibt es KeineAntwort.
"""

MODELL = "claude-sonnet-5-5"
DENKEN_AUS = {"type": "between_tools"}


class KeineAntwort(Exception):
    """Modell hat abgelehnt oder keinen Text geliefert."""


def antwort_text(response) -> str:
    if response.stop_reason == "refusal":
        raise KeineAntwort("Anfrage vom Modell abgelehnt (stop_reason refusal)")
    text = "".join(b.text for b in response.content if b.type == "text")
    if not text.strip():
        raise KeineAntwort(f"Leere Antwort (stop_reason {response.stop_reason})")
    return text
