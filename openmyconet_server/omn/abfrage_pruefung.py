"""WSGI-Schicht vor Flask: Anfragen mit ungueltigem UTF-8 im Query-String
bekommen sofort 400.

Hintergrund (03.10.2026): Scanner schicken Bytefolgen wie `?\\xb0...`.
Werkzeug dekodiert `request.args` strikt als UTF-8 -- der erste Zugriff
(`resolve_lang()` im before_request) warf `UnicodeDecodeError`, das landete als
500 im Fehlerprotokoll und loeste eine Fehler-Mail aus. Ein Errorhandler in
Flask reicht nicht: auch die after_request-Hooks lesen `request.args` und
wuerden erneut werfen. Darum wird die Anfrage abgewiesen, bevor Flask sie sieht.
"""


class UngueltigeAbfrageAbweisen:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        # PEP 3333: QUERY_STRING ist ein latin-1-"native string" mit den Rohbytes.
        roh = environ.get('QUERY_STRING', '')
        try:
            roh.encode('latin-1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            body = b'Bad Request'
            start_response('400 Bad Request', [
                ('Content-Type', 'text/plain; charset=utf-8'),
                ('Content-Length', str(len(body))),
            ])
            return [body]
        return self.wsgi_app(environ, start_response)
