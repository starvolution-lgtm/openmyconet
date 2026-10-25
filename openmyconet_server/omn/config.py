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
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# .env muss geladen sein, BEVOR die Klassenkoerper unten os.getenv auswerten
# (passiert beim Import dieser Datei).
load_dotenv()

_ROOT = Path(__file__).resolve().parent.parent  # omn/ -> Repo-Root


def _db_url():
    """DB-URL aus DATABASE_URL, sonst die lokale SQLite-Datei.
    Prod/Staging setzen DATABASE_URL seit dem Cutover (2026-09-09) -> PostgreSQL 18;
    ohne die Variable (lokal, CI-Job backend) -> SQLite.
    postgres:// bzw. postgresql:// werden auf den psycopg3-Treiber gezwungen
    (nicht das alte psycopg2)."""
    url = (os.getenv('DATABASE_URL') or '').strip() or 'sqlite:///openmyconet.db'
    for praefix in ('postgres://', 'postgresql://'):
        if url.startswith(praefix):
            return 'postgresql+psycopg://' + url[len(praefix):]
    return url


_DB_URL = _db_url()
_IST_PG = _DB_URL.startswith('postgresql+psycopg')


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')  # Hard-Fail in create_app, nicht hier

    SQLALCHEMY_DATABASE_URI = _DB_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLite: gunicorn -w 2 -- zwei Prozesse schreiben parallel in dieselbe
    #   Datei; timeout laesst den zweiten Writer bis zu 15 s auf die Sperre
    #   warten statt sofort "database is locked" zu werfen.
    # Postgres: pool_pre_ping faengt vom Server gekappte Verbindungen ab
    #   (idle timeout, Neustart), pool_recycle erneuert sie vorsorglich.
    SQLALCHEMY_ENGINE_OPTIONS = (
        {'pool_pre_ping': True, 'pool_recycle': 1800}
        if _IST_PG
        else {'connect_args': {'timeout': 15}}
    )

    # Session-Cookie-Haertung: nur ueber HTTPS, kein JS-Zugriff, kein Mitfahren
    # bei Cross-Site-POSTs (CSRF-Grundschutz).
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # __Host-: der Browser nimmt das Cookie nur mit Secure, Pfad / und ohne
    # Domain-Attribut an -- ein Cookie von einer Subdomain kann es nicht ueberschreiben.
    SESSION_COOKIE_NAME = '__Host-session'
    # Admin-Login: Cookie wird bei jeder Anfrage erneuert -> 8 Stunden Leerlauf.
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    # Superadmin ohne aktive 2FA wird auf die Einrichtungsseite umgeleitet.
    ADMIN_2FA_ERZWINGEN = True

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
    # Staging setzt MAIL_SUPPRESS_SEND=True in seiner .env -> nie echte Mails.
    # Auch fuer Prod ein Not-Aus ohne Deploy (ENV setzen + reload).
    MAIL_SUPPRESS_SEND = os.getenv('MAIL_SUPPRESS_SEND', '').strip().lower() in ('1', 'true', 'yes', 'on')

    # Server-MCC (/mcc, omn/mcc/): Vorstellungs-Mails gehen ueber das eigene Postfach
    # robert.jank@ (MAIL_SERVER/MAIL_PORT wie oben, eigener Login). Ohne diese Werte
    # zeigt /mcc/vorlagen "Versand nicht eingerichtet". Erinnerung an MCC_ERINNERUNG_AN
    # (Standard: MCC_MAIL_SENDER), verschickt ueber den normalen Website-Zugang.
    MCC_MAIL_USERNAME = os.getenv('MCC_MAIL_USERNAME')
    MCC_MAIL_PASSWORD = os.getenv('MCC_MAIL_PASSWORD')
    MCC_MAIL_SENDER = os.getenv('MCC_MAIL_SENDER')
    MCC_MAIL_SENDER_NAME = os.getenv('MCC_MAIL_SENDER_NAME', 'Robert Jank – OpenMycoNet')
    MCC_MAIL_BCC = os.getenv('MCC_MAIL_BCC')
    MCC_ERINNERUNG_AN = os.getenv('MCC_ERINNERUNG_AN')
    MCC_WIEDERVORLAGE_TAGE = os.getenv('MCC_WIEDERVORLAGE_TAGE', '14')
    MCC_NACHFRAGE_TAGE = os.getenv('MCC_NACHFRAGE_TAGE', '7')

    # 'prod' | 'staging' (| beliebig). Steuert den Umgebungs-Banner im Admin +
    # den Header X-OMN-Env. Staging setzt OMN_ENV=staging in seiner .env.
    OMN_ENV = os.getenv('OMN_ENV', 'prod').strip() or 'prod'

    # Wissenschaftliche Themenraeume (Phase 2a): wer teilnehmen darf.
    # 'fachkontakte' (Start) = aktiver fachlicher Austausch; 'alle' = jeder bestaetigte
    # Nutzer (erklaertes Ziel, Robby 25.10.2026). Nie an Rolle/Foerderung gebunden.
    THEMEN_KREIS = os.getenv('THEMEN_KREIS', 'fachkontakte').strip() or 'fachkontakte'
    # Schalter bis zur rechtlichen Freigabe (Nutzungsregeln + Datenschutzerklaerung,
    # Phase 2a Schritt 5): auf Prod (OMN_ENV=prod) verborgen -- Routen 404, kein
    # Navigationslink --, auf Staging/lokal sichtbar. THEMEN_FREIGEGEBEN=1/0 in der
    # .env ueberschreibt das. Nach der Freigabe wird der Standard hier umgestellt.
    THEMEN_FREIGEGEBEN = (os.getenv('THEMEN_FREIGEGEBEN', '0' if OMN_ENV == 'prod' else '1').strip().lower()
                          in ('1', 'true', 'yes', 'on'))

    # Datenbankschema für das Datenlabor: 'sandbox' (Simulation) oder 'live' (echte Messdaten).
    # Nach dem Cutover auf DATENLABOR_SCHEMA=live setzen; Sandbox bleibt parallel verfügbar.
    DATENLABOR_SCHEMA = os.getenv('DATENLABOR_SCHEMA', 'sandbox')


class TestConfig(Config):
    TESTING = True
    # CSRF-Schutz (csrf.py) fuer die meisten Tests aus -- die POST-Requests der
    # Test-Clients schicken kein Token mit. test_csrf.py schaltet ihn gezielt an.
    CSRF_ENABLED = False
    # Die meisten Tests melden einen Superadmin ohne 2FA an; test_admin_auth.py
    # schaltet die Pflicht gezielt an.
    ADMIN_2FA_ERZWINGEN = False
    # Flask-Mail 0.10 friert MAIL_SUPPRESS_SEND / MAIL_DEFAULT_SENDER bei
    # init_app ein. Weil create_app(TestConfig) init_app NACH from_object ruft,
    # genuegen jetzt diese beiden Werte -- die alten extensions['mail']-Hacks im
    # conftest entfallen.
    MAIL_SUPPRESS_SEND = True
    MAIL_DEFAULT_SENDER = 'test@openmyconet.test'
    SERVER_NAME = 'testserver.local'
    # Themenraeume in Tests immer an (der Prod-Schalter hat einen eigenen Test)
    THEMEN_FREIGEGEBEN = True
