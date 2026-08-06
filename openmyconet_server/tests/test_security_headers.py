def test_security_header_auf_jeder_antwort(client):
    resp = client.get('/login')
    assert 'Content-Security-Policy' in resp.headers
    assert resp.headers['X-Content-Type-Options'] == 'nosniff'
    assert resp.headers['X-Frame-Options'] == 'SAMEORIGIN'
    assert resp.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
