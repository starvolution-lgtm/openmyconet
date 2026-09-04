"""
i18n.py — Phase 4 Schritt 2: einheitlicher i18n-Mechanismus fuer die Jinja-
Templates unter app/templates/site/.

Einzige Datenquelle ist app/static/translations.json (konvertiert aus dem
bisherigen translations.js der statischen Website -- siehe
scratchpad/convert_translations.py fuer das Konvertierungsskript). Dieselbe
Datei wird vom Client per fetch() genutzt, damit das bestehende Instant-
Sprachumschalten (Flaggen-Klick, kein Reload) unveraendert weiterfunktioniert
-- serverseitiges Rendering bestimmt nur die Sprache des ERSTEN Ladens
(loest das hreflang/Duplicate-Content-Thema aus Phase 1).

Einbinden in app.py:
    from i18n import init_i18n
    init_i18n(app)
"""
import json
import os

from flask import g, request, jsonify

LANGS = ['de', 'en', 'nl', 'fr', 'es']
COOKIE_NAME = 'omn_lang'

_TRANSLATIONS_PATH = os.path.join(os.path.dirname(__file__), 'app', 'static', 'translations.json')
with open(_TRANSLATIONS_PATH, encoding='utf-8') as _f:
    TRANSLATIONS = json.load(_f)


def resolve_lang():
    """Gleiche Prioritaet wie das bisherige clientseitige getLang(): expliziter
    ?lang=-Parameter -> gespeicherte Praeferenz (hier: Cookie statt localStorage,
    serverseitig gibt es kein localStorage) -> Browser-Sprache -> 'de'."""
    p = request.args.get('lang')
    if p in LANGS:
        return p
    cookie_lang = request.cookies.get(COOKIE_NAME)
    if cookie_lang in LANGS:
        return cookie_lang
    best = request.accept_languages.best_match(LANGS)
    return best or 'de'


def t(key):
    lang = getattr(g, 'lang', 'de')
    block = TRANSLATIONS.get(lang) or TRANSLATIONS['de']
    return block.get(key, TRANSLATIONS['de'].get(key, ''))


def init_i18n(app):
    @app.before_request
    def _set_lang():
        g.lang = resolve_lang()

    @app.after_request
    def _persist_lang_cookie(response):
        # Nur setzen, wenn die Sprache explizit per URL gewaehlt wurde -- sonst
        # wuerde jeder Request (auch mit nur Browser-Spracherkennung) einen
        # Cookie schreiben, den der Nutzer nie bewusst gewaehlt hat.
        if request.args.get('lang') in LANGS:
            response.set_cookie(COOKIE_NAME, request.args.get('lang'), max_age=60 * 60 * 24 * 365, samesite='Lax')
        return response

    @app.route('/i18n/<lang>.json')
    def i18n_json(lang):
        """Ein einzelner Sprachblock aus translations.json. Der Client laedt nur
        noch die aktuelle Sprache (+ 'de' als Fallback) statt aller fuenf --
        translations.json ist ~416 KB, ein Block davon ~85 KB. Weitere Sprachen
        werden beim Flaggen-Klick nachgeladen (base.html, omnEnsureLang)."""
        if lang not in LANGS:
            return jsonify({}), 404
        response = jsonify(TRANSLATIONS.get(lang, {}))
        # Moderat cachen: kurz genug, dass Textredaktionen zeitnah durchschlagen,
        # lang genug, dass Sprachwechsel innerhalb einer Sitzung nicht neu laden.
        response.headers['Cache-Control'] = 'public, max-age=300'
        return response

    app.jinja_env.globals['t'] = t
    app.jinja_env.globals['current_lang'] = lambda: getattr(g, 'lang', 'de')
    # Fuer Array-/Objekt-Werte (z.B. leih_specs, leih_how), bei denen t() als
    # reine String-Lookup-Funktion nicht reicht -- direkter Zugriff im Template
    # via translations[current_lang()]['key'].
    app.jinja_env.globals['translations'] = TRANSLATIONS
