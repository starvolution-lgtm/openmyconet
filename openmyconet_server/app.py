"""App-Factory fuer das OpenMycoNet-Backend.

Bis 2026-09 baute dieses Modul die Flask-App direkt beim Import (Modul-Singleton).
Jetzt: create_app(config=None). Am Dateiende steht weiterhin `app = create_app()`
als Bruecke -- `from app import app` funktioniert fuer die Wartungs-Scripts im
Root + presse_suche.py unveraendert weiter (sauberer Schnitt in Phase 3, wenn
alles nach omn/ wandert). Einstiegspunkt fuer gunicorn ist wsgi.py.
"""
from pathlib import Path

from flask import Flask
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

# config zuerst: sein Import ruft load_dotenv(), bevor die Blueprint-Module
# unten evtl. Umgebungsvariablen beim Import auswerten.
from config import Config
# extensions importiert nebenbei _sqlite_pragmas (@event.listens_for global) --
# muss vor dem ersten Engine-Connect passiert sein.
from extensions import db, mail
from admin import admin_bp
from rag_chatbot import chatbot_bp
from bewerbung import bewerbung_bp
from registrierung import registrierung_bp
from dashboard import dashboard_bp
from site_preview import site_preview_bp
from site_live import site_live_bp
from foerderer import foerderer_bp
from kontrollzentrum import kontrollzentrum_bp
from i18n import init_i18n
from csrf import init_csrf
from errors import init_errors
import public

_ROOT = Path(__file__).resolve().parent


def create_app(config=None, instance_path=None):
    app = Flask(
        __name__,
        instance_path=str(instance_path) if instance_path else None,
        template_folder=str(_ROOT / 'app' / 'templates'),
        static_folder=str(_ROOT / 'app' / 'static'),
        static_url_path='',
    )

    # nginx laeuft als HTTPS-Reverse-Proxy vor gunicorn -- ohne ProxyFix haelt
    # Flask jede Anfrage fuer HTTP (falsche http:// URLs bei _external=True).
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    app.config.from_object(config or Config)

    # Kein stiller Fallback-Key: ein geratener SECRET_KEY macht Session-Cookies
    # faelschbar (Admin-Login uebernehmbar). Fehlt der Key, soll die App gar
    # nicht erst starten.
    if not app.config.get('SECRET_KEY'):
        raise RuntimeError(
            "SECRET_KEY fehlt. In .env setzen, z. B.: "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )

    db.init_app(app)
    mail.init_app(app)
    CORS(app, origins=['https://www.openmyconet.de', 'https://openmyconet.de', 'https://api.openmyconet.de'])

    app.register_blueprint(admin_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(bewerbung_bp)
    app.register_blueprint(registrierung_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(site_preview_bp)
    app.register_blueprint(site_live_bp)
    app.register_blueprint(foerderer_bp)
    app.register_blueprint(kontrollzentrum_bp)

    init_i18n(app)
    init_csrf(app)
    init_errors(app)

    # Als LETZTES: bindet die oeffentlichen Routen + Sicherheits-Header-Hooks.
    # Nach init_errors, damit _sicherheits_header (after_request) vor dessen
    # Handler laeuft (Flask ruft after_request in umgekehrter Registrierreihenfolge).
    public.register(app)

    return app


# --- Bruecke: Modul-Level-app fuer `from app import app` (Root-Scripts) ---
app = create_app()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print('Datenbank initialisiert.')
    app.run(debug=False)
