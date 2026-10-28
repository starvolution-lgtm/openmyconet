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


# --- "Steht an": Zaehler fuer Leiste + Uebersicht (Design 28.10.2026) -----------------------

def steht_an():
    """Was im Admin Handlung braucht, je Bereich {schluessel: (anzahl, url, text)}.
    Nur fuer eingeloggte Superadmins, einmal je Anfrage berechnet (am request-Objekt: flask.g
    lebt so lange wie der App-Kontext und der kann mehrere Anfragen ueberdauern, z. B. in Tests)."""
    from datetime import datetime, timedelta, timezone

    from omn import austausch as aus
    from omn.models import Austausch, Beitrag, Bewerbung, Fehlerprotokoll, Foerderer, Kontaktanfrage
    from omn.zeit import utcnow
    if not session.get('admin_logged_in') or session.get('admin_role') != 'superadmin':
        return {}
    vorhanden = getattr(request, '_omn_steht_an', None)
    if vorhanden is not None:
        return vorhanden
    eintraege = {}

    def merken(schluessel, anzahl, endpoint, einzahl, mehrzahl, **args):
        if anzahl:
            eintraege[schluessel] = (anzahl, url_for(endpoint, **args), einzahl if anzahl == 1 else mehrzahl.format(n=anzahl))

    try:
        merken('bewerbungen', Bewerbung.query.filter_by(status='neu').count(), 'admin.bewerbungen_admin',
               '1 neue Bewerbung', '{n} neue Bewerbungen')
        merken('kontakt', Kontaktanfrage.query.filter_by(status='neu').count(), 'admin.kontakt_admin',
               '1 neue Kontaktanfrage', '{n} neue Kontaktanfragen')
        foerderer = (Foerderer.query.filter_by(status='zahlung_eingegangen').count()
                     + Foerderer.query.filter_by(typ='kooperation', status='pending').count())
        merken('foerderer', foerderer, 'admin.foerderer_admin', '1 Förderer/Kooperation zu prüfen',
               '{n} Förderer/Kooperationen zu prüfen')
        bezug = aus.jetzt()
        pruefen = sum(1 for a in Austausch.query.filter_by(status='aktiv').all() if aus.inaktiv_zu_pruefen(a, bezug))
        merken('austausch', pruefen, 'admin.austausch_liste', '1 Austausch zur Prüfung (12 Monate ohne Aktivität)',
               '{n} Austausche zur Prüfung (12 Monate ohne Aktivität)', filter='pruefen')
        vorbereitet = Austausch.query.filter_by(status='vorbereitet').count()
        merken('austausch_vorbereitet', vorbereitet, 'admin.austausch_liste', '1 Austausch vorbereitet, noch nicht eingeladen',
               '{n} Austausche vorbereitet, noch nicht eingeladen')
        merken('fehler', Fehlerprotokoll.query.filter(Fehlerprotokoll.zeitpunkt >= utcnow() - timedelta(days=1)).count(),
               'admin.fehler_admin', '1 Fehler in den letzten 24 Stunden', '{n} Fehler in den letzten 24 Stunden')
        seit = datetime.now(timezone.utc) - timedelta(days=1)
        merken('themen', Beitrag.query.filter(Beitrag.von_team.is_(False), Beitrag.erstellt_am >= seit).count(),
               'admin.themen_admin', '1 neuer Beitrag in den Themenräumen (24 Std.)',
               '{n} neue Beiträge in den Themenräumen (24 Std.)')
    except Exception:  # Zaehler duerfen nie eine Admin-Seite kaputt machen
        current_app.logger.exception('Steht-an-Zaehler fehlgeschlagen')
        db.session.rollback()
    request._omn_steht_an = eintraege
    return eintraege


@admin_bp.app_context_processor
def _steht_an_helfer():
    def zaehler(*schluessel):
        an = steht_an()
        return sum(an[s][0] for s in schluessel if s in an)
    return {'steht_an': steht_an, 'steht_an_zahl': zaehler}
