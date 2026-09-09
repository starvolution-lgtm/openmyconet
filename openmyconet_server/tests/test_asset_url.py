"""asset()/_asset_url: normal absolut auf www.openmyconet.de, per OMN_ASSET_BASE
umbiegbar (Frontend-Audit-Job der CI serviert die App lokal)."""
from omn.public import _asset_url


def test_asset_url_default_absolut(app):
    with app.test_request_context('/'):
        url = _asset_url('site-base.css')
    assert url.startswith('https://www.openmyconet.de/site-base.css?v=')


def test_asset_url_leer_ist_basis(app):
    with app.test_request_context('/'):
        assert _asset_url('') == 'https://www.openmyconet.de/'


def test_omn_asset_base_biegt_ursprung_um(app, monkeypatch):
    monkeypatch.setenv('OMN_ASSET_BASE', '/')
    with app.test_request_context('/'):
        assert _asset_url('site-base.css').startswith('/site-base.css?v=')
        assert _asset_url('') == '/'
