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
