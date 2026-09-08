"""OMN_ENV / Staging-Kennzeichnung: roter Admin-Banner + Header X-OMN-Env,
nur wenn OMN_ENV != 'prod'."""
from omn.config import Config


def test_prod_default_kein_banner_kein_header(client):
    r = client.get('/login')
    assert 'omn-env-banner' not in r.get_data(as_text=True)
    assert 'X-OMN-Env' not in r.headers


def test_staging_zeigt_banner_und_header(app, client):
    app.config['OMN_ENV'] = 'staging'
    r = client.get('/login')
    html = r.get_data(as_text=True)
    assert 'omn-env-banner' in html
    assert 'STAGING' in html
    assert r.headers.get('X-OMN-Env') == 'staging'


def test_defaults_sind_prod():
    # Ohne OMN_ENV / MAIL_SUPPRESS_SEND in der Umgebung: Prod-Defaults.
    assert Config.OMN_ENV == 'prod'
    assert Config.MAIL_SUPPRESS_SEND is False
