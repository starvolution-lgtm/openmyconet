"""Konfiguration fuer die App-Factory (create_app in app.py).

Bis 2026-09 lag die Config als Block direkter app.config[...]-Zuweisungen in
app.py und wurde nur einmal beim Import gelesen -- daraus kamen wiederholt Bugs
(MAIL_SUPPRESS_SEND/MAIL_DEFAULT_SENDER erst nach init_app gesetzt, .env-Reload
braucht HUP). Jetzt: Klassen, die create_app per config.from_object(...) laedt;
Tests reichen TestConfig herein, bevor irgendeine Extension initialisiert wird.

SECRET_KEY: kein stiller Fallback. Fehlt der Key, bricht create_app ab (nicht
schon der Import dieser Datei -- sonst kann pytest die Config-Klasse nicht mal
importieren, wenn SECRET_KEY fehlt).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# .env muss geladen sein, BEVOR die Klassenkoerper unten os.getenv auswerten
# (passiert beim Import dieser Datei).
load_dotenv()

_ROOT = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')  # Hard-Fail in create_app, nicht hier

    SQLALCHEMY_DATABASE_URI = 'sqlite:///openmyconet.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # gunicorn -w 2: zwei Prozesse schreiben parallel in dieselbe SQLite-Datei.
    # timeout laesst den zweiten Writer bis zu 15 s auf die Sperre warten,
    # statt sofort "database is locked" zu werfen.
    SQLALCHEMY_ENGINE_OPTIONS = {'connect_args': {'timeout': 15}}

    # Session-Cookie-Haertung: nur ueber HTTPS, kein JS-Zugriff, kein Mitfahren
    # bei Cross-Site-POSTs (CSRF-Grundschutz).
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # 12 MB Gesamt-Request. Handy-Fotos (News-Bild) sind oft 4-8 MB; die werden
    # serverseitig auf 1600 px verkleinert + nach WebP konvertiert
    # (admin.save_news_image). Foerderer-Logo bleibt bei 5 MB (eigene Meldung).
    MAX_CONTENT_LENGTH = 12 * 1024 * 1024

    # Wurzel fuer Nutzer-Uploads (News-Bilder, Foerderer-Logos). Prod: unter
    # static/, damit url_for('static', ...) sie ausliefert. Tests biegen das auf
    # ein Temp-Verzeichnis um (conftest).
    UPLOAD_ROOT = str(_ROOT / 'app' / 'static' / 'uploads')

    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', '587'))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER')


class TestConfig(Config):
    TESTING = True
    # CSRF-Schutz (csrf.py) fuer die meisten Tests aus -- die POST-Requests der
    # Test-Clients schicken kein Token mit. test_csrf.py schaltet ihn gezielt an.
    CSRF_ENABLED = False
    # Flask-Mail 0.10 friert MAIL_SUPPRESS_SEND / MAIL_DEFAULT_SENDER bei
    # init_app ein. Weil create_app(TestConfig) init_app NACH from_object ruft,
    # genuegen jetzt diese beiden Werte -- die alten extensions['mail']-Hacks im
    # conftest entfallen.
    MAIL_SUPPRESS_SEND = True
    MAIL_DEFAULT_SENDER = 'test@openmyconet.test'
    SERVER_NAME = 'testserver.local'
