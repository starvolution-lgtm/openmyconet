"""Gemeinsames Fundament des Admin-Panels: der Blueprint, der Host-Redirect,
der CSRF-Schutz und die von mehreren Fachmodulen genutzten Decorators.

Die Fachmodule (auth, uebersicht, news, ...) importieren `admin_bp` von hier
und haengen ihre Routen daran; `omn/admin/__init__.py` laedt sie alle.
"""
from functools import wraps

from flask import Blueprint, current_app, flash, redirect, request, session, url_for

from omn.csrf import schuetze_blueprint
from omn.extensions import db
from omn.models import AdminUser

admin_bp = Blueprint('admin', __name__)

# Das Admin-Panel nur unter EINEM kanonischen Host. Das Session-Cookie ist
# hostgebunden -- laeuft der Login-Ablauf (v. a. der 2FA-Zwischenschritt) mal
# ueber www. und mal ueber api., geht die Session verloren -> CSRF-"Bad Request".
# /login wird von nginx auf beiden server_names ausgeliefert, deshalb hier hart.
KANONISCHER_HOST = 'api.openmyconet.de'
_HOST_UMLEITEN = {'www.openmyconet.de', 'openmyconet.de'}


@admin_bp.before_request
def _kanonischer_host():
    if request.host in _HOST_UMLEITEN:
        ziel = f'https://{KANONISCHER_HOST}{request.path}'
        if request.query_string:
            ziel += '?' + request.query_string.decode('latin-1')
        # 308: Methode + Body bleiben erhalten (falls doch mal direkt gepostet wird).
        return redirect(ziel, code=308)
    return None


schuetze_blueprint(admin_bp)  # CSRF-Pruefung fuer alle POST-Routen des Admin-Panels


# --- geteilte Decorators ---

# Seiten, die auch ein Superadmin OHNE aktive 2FA erreichen muss (Einrichtung
# der 2FA selbst, Abmelden) -- sonst sperrt die Pflicht ihn aus.
_OHNE_2FA_ERLAUBT = {'admin.zwei_faktor', 'admin.logout'}


def _zurueck_nach():
    """Nur GET-Seiten als Ziel merken -- ein POST-Pfad als Ziel ergaebe nach dem Login 405."""
    return request.path if request.method == 'GET' else None


def _admin_pruefen():
    """None = Zugriff ok, sonst eine Antwort (Umleitung/Fehler).

    Die Session ist ein signiertes Cookie -- ohne diese Pruefung bliebe ein
    geloeschtes oder herabgestuftes Konto bis zum Ablauf des Cookies gueltig.
    Deshalb bei jeder Anfrage gegen die DB abgleichen und die Rolle von dort
    nehmen (nicht aus dem Cookie).
    """
    # weiter= : nach dem Login zurueck hierher (vom Handy aus also ins MCC, nicht nach /admin)
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin.login', weiter=_zurueck_nach()))
    user = db.session.get(AdminUser, session.get('admin_user_id'))
    if user is None:
        session.clear()
        return redirect(url_for('admin.login', weiter=_zurueck_nach()))
    session['admin_role'] = user.role
    session['admin_2fa_aktiv'] = bool(user.totp_aktiviert)
    if (current_app.config.get('ADMIN_2FA_ERZWINGEN', True) and user.role == 'superadmin'
            and not user.totp_aktiviert and request.endpoint not in _OHNE_2FA_ERLAUBT):
        flash('Für den Superadmin ist die Zwei-Faktor-Anmeldung Pflicht — bitte jetzt einrichten.', 'error')
        return redirect(url_for('admin.zwei_faktor'))
    return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        abbruch = _admin_pruefen()
        if abbruch is not None:
            return abbruch
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            abbruch = _admin_pruefen()
            if abbruch is not None:
                return abbruch
            if session.get('admin_role') not in roles:
                return 'Kein Zugriff — diese Seite ist dem Superadmin vorbehalten.', 403
            return f(*args, **kwargs)
        return decorated
    return decorator
