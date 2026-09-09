"""Gemeinsames Fundament des Admin-Panels: der Blueprint, der Host-Redirect,
der CSRF-Schutz und die von mehreren Fachmodulen genutzten Decorators.

Die Fachmodule (auth, uebersicht, news, ...) importieren `admin_bp` von hier
und haengen ihre Routen daran; `omn/admin/__init__.py` laedt sie alle.
"""
from functools import wraps

from flask import Blueprint, redirect, request, session, url_for

from omn.csrf import schuetze_blueprint

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

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not session.get('admin_logged_in'):
                return redirect(url_for('admin.login'))
            if session.get('admin_role') not in roles:
                return 'Kein Zugriff — diese Seite ist dem Superadmin vorbehalten.', 403
            return f(*args, **kwargs)
        return decorated
    return decorator
