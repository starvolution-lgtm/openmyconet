"""App-Factory fuer das OpenMycoNet-Backend (Package `omn`).

`create_app(config=None)` -- kein Modul-Level-App-Singleton mehr. Einstieg fuer
gunicorn: `wsgi.py` (`wsgi:app`). Wartungs-Scripts im Repo-Root bauen sich die
App selbst: `from omn import create_app; app = create_app()`.
"""
import mimetypes
from pathlib import Path

from flask import Flask

# WebVTT-Songtextspuren (app/static/lyrics/*.vtt): sicherstellen, dass Flasks
# statischer Handler sie als text/vtt ausliefert -- sonst parst der Browser die
# <track>-Spur nicht (haengt sonst am OS-mimetypes-Zustand).
mimetypes.add_type('text/vtt', '.vtt')
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

# config zuerst: sein Import ruft load_dotenv(), bevor die Blueprint-Module
# unten evtl. Umgebungsvariablen beim Import auswerten.
from omn.config import Config
# extensions importiert nebenbei _sqlite_pragmas (@event.listens_for global) --
# muss vor dem ersten Engine-Connect passiert sein.
from omn.extensions import db, mail, migrate
from omn.admin import admin_bp
from omn.rag_chatbot import chatbot_bp
from omn.bewerbung import bewerbung_bp
from omn.registrierung import registrierung_bp
from omn.dashboard import dashboard_bp
from omn.site_preview import site_preview_bp
from omn.site_live import site_live_bp
from omn.foerderer import foerderer_bp
from omn.kontrollzentrum import kontrollzentrum_bp
from omn.i18n import init_i18n
from omn.csrf import init_csrf
from omn.errors import init_errors
from omn.cli import register_cli
from omn import public

# omn/ liegt im Repo-Root; Templates/Static bleiben unter <root>/app/.
_ROOT = Path(__file__).resolve().parent.parent


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
    # render_as_batch nur auf SQLite -- dort kann Alembic ALTER TABLE nur
    # eingeschraenkt und baut betroffene Tabellen nach. Postgres macht echtes
    # ALTER, da waere batch nur unnoetiger Tabellen-Rebuild.
    # compare_type: autogenerate erkennt sonst Spaltentyp-Aenderungen nicht.
    # compare_server_default bewusst AUS -- die Modelle nutzen Python-seitige
    # default=, kaum server_default; die Pruefung meldet sonst Falsch-Positive.
    _batch = app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite')
    migrate.init_app(app, db, render_as_batch=_batch, compare_type=True)
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
    register_cli(app)

    # Als LETZTES: bindet die oeffentlichen Routen + Sicherheits-Header-Hooks.
    # Nach init_errors, damit _sicherheits_header (after_request) vor dessen
    # Handler laeuft (Flask ruft after_request in umgekehrter Registrierreihenfolge).
    public.register(app)

    return app
