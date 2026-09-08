"""
csrf.py — schlanker CSRF-Schutz fuer die session-authentifizierten Formulare
(Admin-Panel + Nutzer-Dashboard). Kein Flask-WTF/WTForms als Abhaengigkeit.

Prinzip (Synchronizer-Token):
  * Pro Session ein zufaelliges Token in session['_csrf_token'].
  * Jedes POST/PUT/PATCH/DELETE der geschuetzten Blueprints muss das Token
    mitschicken -- als Formularfeld `_csrf` ODER Header `X-CSRFToken`.
  * Fehlt/stimmt es nicht -> 400.

Einbinden:
  app.py:        from csrf import init_csrf;  init_csrf(app)
  admin.py:      from csrf import schuetze_blueprint;  schuetze_blueprint(admin_bp)
  dashboard.py:  from csrf import schuetze_blueprint;  schuetze_blueprint(dashboard_bp)

Die Templates admin_base.html / dashboard_base.html haengen das Feld per kleinem
Skript automatisch an jedes <form method="post"> -- neue Formulare brauchen also
nichts weiter. Fuer AJAX: Header `X-CSRFToken` mit dem Wert aus `csrf_token()`.

Nicht geschuetzt (bewusst): die oeffentlichen JSON-APIs (/api/register,
/api/bewerbung, /api/chat -- werden per fetch cross-origin von der statischen
Website aufgerufen, haben eigenen Honeypot/Rate-Limit), der PayPal-IPN-Webhook
und /api/v1/messung (externe Geraete).
"""
import hmac
import secrets

from flask import abort, current_app, request, session

_FIELD = '_csrf'
_HEADER = 'X-CSRFToken'
_SESSION_KEY = '_csrf_token'
_SICHERE_METHODEN = {'GET', 'HEAD', 'OPTIONS', 'TRACE'}


def csrf_token():
    """Token der aktuellen Session holen oder neu erzeugen. Als Jinja-Global
    unter demselben Namen registriert."""
    token = session.get(_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[_SESSION_KEY] = token
    return token


def _uebermitteltes_token():
    return request.form.get(_FIELD) or request.headers.get(_HEADER) or ''


def _pruefe():
    if request.method in _SICHERE_METHODEN:
        return
    # Schalter fuer Tests (conftest setzt CSRF_ENABLED=False). Default: an.
    if current_app.config.get('CSRF_ENABLED', True) is False:
        return
    erwartet = session.get(_SESSION_KEY)
    uebermittelt = _uebermitteltes_token()
    if not erwartet or not uebermittelt or not hmac.compare_digest(str(erwartet), str(uebermittelt)):
        abort(400, description='CSRF-Token fehlt oder ist ungültig. Seite neu laden und erneut absenden.')


def _kein_cache(response):
    """Session-gebundene Seiten nie aus dem Browser-Cache (inkl. Back-/Forward-
    Cache) wiederherstellen. Sonst kann ein Formular mit veraltetem CSRF-Token
    erneut abgesendet werden -- die Pruefung schlaegt dann mit 400 fehl,
    obwohl mit dem Nutzer alles stimmt (typisch im 2FA-Login-Ablauf, der
    zwischendurch session.clear() macht)."""
    response.headers['Cache-Control'] = 'no-store, private'
    return response


def schuetze_blueprint(blueprint):
    """Haengt die CSRF-Pruefung (before_request) und den No-Store-Header
    (after_request) an den Blueprint. Muss beim Blueprint-Modulimport laufen
    (vor register_blueprint)."""
    blueprint.before_request(_pruefe)
    blueprint.after_request(_kein_cache)


def init_csrf(app):
    app.jinja_env.globals['csrf_token'] = csrf_token
