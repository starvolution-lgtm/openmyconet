def test_security_header_auf_jeder_antwort(client):
    resp = client.get('/login')
    assert 'Content-Security-Policy' in resp.headers
    assert resp.headers['X-Content-Type-Options'] == 'nosniff'
    assert resp.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert resp.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
    assert 'max-age=' in resp.headers['Strict-Transport-Security']
    assert 'geolocation=()' in resp.headers['Permissions-Policy']
    assert resp.headers['Cross-Origin-Opener-Policy'] == 'same-origin'


def test_security_txt_erreichbar(client):
    resp = client.get('/.well-known/security.txt')
    assert resp.status_code == 200
    assert resp.headers['Content-Type'].startswith('text/plain')
    text = resp.get_data(as_text=True)
    assert 'Contact:' in text
    assert 'Expires:' in text


def test_corp_und_csp_meldeweg(client):
    resp = client.get('/login')
    assert resp.headers['Cross-Origin-Resource-Policy'] == 'same-site'
    csp = resp.headers['Content-Security-Policy']
    assert 'report-uri /api/csp-bericht' in csp and 'report-to csp' in csp
    assert resp.headers['Reporting-Endpoints'] == 'csp="/api/csp-bericht"'


class _Mitschnitt:
    def __init__(self):
        self.zeilen = []

    def warning(self, fmt, *args):
        self.zeilen.append(fmt % args)


def test_csp_bericht_alt_und_neu_wird_geloggt(client, monkeypatch):
    # Logger direkt ersetzen statt caplog: andere Tests (init_errors) aendern die
    # Logging-Konfiguration, caplog sieht dann je nach Reihenfolge nichts.
    log = _Mitschnitt()
    monkeypatch.setattr('omn.public._log', log)
    alt = {'csp-report': {'document-uri': 'https://www.openmyconet.de/', 'violated-directive': 'script-src',
                          'blocked-uri': 'https://boese.example/x.js'}}
    neu = [{'type': 'csp-violation', 'body': {'documentURL': 'https://api.openmyconet.de/login',
                                               'effectiveDirective': 'img-src', 'blockedURL': 'https://tracker.example/p.gif'}}]
    assert client.post('/api/csp-bericht', json=alt).status_code == 204
    r = client.post('/api/csp-bericht', data=__import__('json').dumps(neu), content_type='application/reports+json')
    assert r.status_code == 204
    text = ' | '.join(log.zeilen)
    assert 'boese.example' in text and 'tracker.example' in text


def test_csp_bericht_muell_und_zu_gross(client, monkeypatch):
    log = _Mitschnitt()
    monkeypatch.setattr('omn.public._log', log)
    assert client.post('/api/csp-bericht', data='kein json', content_type='application/csp-report').status_code == 204
    assert client.post('/api/csp-bericht', data='x' * 20000, content_type='application/csp-report').status_code == 204
    assert log.zeilen == []
