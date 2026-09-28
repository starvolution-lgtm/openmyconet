"""
llms.py -- Textfassung der Website fuer KI-Assistenten (Vorschlag llms.txt).

  /llms.txt          kurzes Inhaltsverzeichnis in Markdown: was OpenMycoNet ist,
                     die Einordnung "kein Wirkungsnachweis", die Seiten mit Link
  /llms-full.txt     alle Website-Texte auf Deutsch, nach Themen
  /llms-full-en.txt  dasselbe auf Englisch

Alles wird aus translations.json erzeugt (Themengruppen aus omn/wissensbasis.py,
dieselben wie beim RAG-Chatbot) -- keine zweite Textkopie, die veralten kann.
Nicht fuer Suchmaschinen gedacht: `X-Robots-Tag: noindex` + canonical auf die
Startseite, damit die Textfassung den HTML-Seiten keine Konkurrenz macht.
Links zeigen immer auf die kanonische Domain (auch auf Staging).
"""
from flask import Response

from omn.i18n import TRANSLATIONS
from omn.wissensbasis import abschnitte, clean

WEBSITE = 'https://www.openmyconet.de'

# (Pfad, Titel-Key oder {lang: Titel}, Beschreibungs-Key oder None)
SEITEN = [
    ('/', {'de': 'Startseite', 'en': 'Home'}, 'meta_desc_index'),
    ('/mykorrhiza-netzwerke.html', 'myk_page_title', 'myk_meta_desc'),
    ('/bioelektrizitaet-biocomm.html', 'myk2_page_title', 'myk2_meta_desc'),
    ('/citizen-science-openmyconet.html', 'myk3_page_title', 'myk3_meta_desc'),
    ('/wie-wir-arbeiten', 'wwa_page_title', 'wwa_meta_desc'),
    ('/biocomm', 'bc_page_title', 'bc_meta_desc'),
    ('/biocomm/hardware', 'bch_page_title', 'bch_meta_desc'),
    ('/biocomm/software', 'bcs_page_title', 'bcs_meta_desc'),
    ('/biocomm/datenlabor', 'bdl_page_title', 'bdl_meta_desc'),
    ('/quellennachweise.html', {'de': 'Quellennachweise & Erkenntnispfad',
                                'en': 'References & path of knowledge'}, 'q_subtitle'),
    ('/foerderer.html', {'de': 'Förderung & Kooperation', 'en': 'Funding & cooperation'}, None),
    ('/medien.html', 'h1_medien', 'desc_medien'),
    ('/news', {'de': 'Neuigkeiten', 'en': 'News'}, None),
    ('/kontakt', 'kontakt_page_title', 'kontakt_meta_desc'),
    ('/datenschutz.html', {'de': 'Datenschutz', 'en': 'Privacy policy'}, None),
]

# Themengruppe -> Seite, auf der die Texte stehen (fuer die Quellenangabe).
GRUPPEN_SEITE = {
    'mykorrhiza-grundlagen': '/mykorrhiza-netzwerke.html',
    'kritische-einordnung': '/mykorrhiza-netzwerke.html',
    'elektrische-aktivitaet': '/bioelektrizitaet-biocomm.html',
    'reize-und-reaktionen': '/quellennachweise.html',
    'biocomm-plattform': '/biocomm',
    'biocomm-hardware': '/biocomm/hardware',
    'biocomm-software': '/biocomm/software',
    'biocomm-datenlabor': '/biocomm/datenlabor',
    'biocomm-datenlabor-nutzung': '/biocomm/datenlabor',
    'rollen-methodik': '/wie-wir-arbeiten',
    'citizen-science': '/citizen-science-openmyconet.html',
    'datenschutz': '/datenschutz.html',
    'foerderer-kooperation': '/foerderer.html',
    'medien-musik-buch': '/medien.html',
    'quellen-erkenntnispfad': '/quellennachweise.html',
}
# Nur Zusammenfassung anderer Gruppen (fuer den Chatbot praktisch), in der
# Volltextfassung waere es eine Dublette.
NICHT_IM_VOLLTEXT = {'entwicklungsstand'}

TEXTE = {
    'de': {
        'einordnung': 'Einordnung',
        'seiten': 'Seiten',
        'volltext': 'Vollständige Texte',
        'volltext_de': 'Alle Website-Texte auf Deutsch, nach Themen',
        'volltext_en': 'All website texts in English, by topic',
        'titel_volltext': 'OpenMycoNet — alle Website-Texte (Deutsch)',
        'hinweis_volltext': ('Automatisch aus den Texten der Website erzeugt. Maßgeblich ist die '
                             'jeweils verlinkte Seite.'),
        'seite': 'Seite',
    },
    'en': {
        'einordnung': 'Context',
        'seiten': 'Pages',
        'titel_volltext': 'OpenMycoNet — all website texts (English)',
        'hinweis_volltext': ('Generated automatically from the website texts. The linked page is '
                             'authoritative.'),
        'seite': 'Page',
    },
}


def _t(lang, key):
    return TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS['de'].get(key)


def _url(pfad, lang):
    return WEBSITE + pfad + ('' if lang == 'de' else f'?lang={lang}')


def _seitenliste(lang):
    zeilen = []
    for pfad, titel, beschreibung in SEITEN:
        name = (titel.get(lang) or titel['de']) if isinstance(titel, dict) else clean(_t(lang, titel))
        zeile = f'- [{name}]({_url(pfad, lang)})'
        if beschreibung:
            zeile += f': {clean(_t(lang, beschreibung))}'
        zeilen.append(zeile)
    return zeilen


def llms_txt():
    de, en = TEXTE['de'], TEXTE['en']
    teile = [
        '# OpenMycoNet',
        '',
        f"> {clean(_t('de', 'meta_desc_index'))}",
        '',
        f"## {de['einordnung']}",
        '',
        f"**{clean(_t('de', 'bdl_interp_title'))}** {clean(_t('de', 'bdl_interp_p'))}",
        '',
        f"## {de['seiten']}",
        '',
        *_seitenliste('de'),
        '',
        f"## {de['volltext']}",
        '',
        f"- [llms-full.txt]({WEBSITE}/llms-full.txt): {de['volltext_de']}",
        f"- [llms-full-en.txt]({WEBSITE}/llms-full-en.txt): {de['volltext_en']}",
        '',
        '## English',
        '',
        f"> {clean(_t('en', 'meta_desc_index'))}",
        '',
        f"**{clean(_t('en', 'bdl_interp_title'))}** {clean(_t('en', 'bdl_interp_p'))}",
        '',
        f"### {en['seiten']}",
        '',
        *_seitenliste('en'),
        '',
    ]
    return '\n'.join(teile)


def llms_full(lang):
    tx = TEXTE[lang]
    teile = [f"# {tx['titel_volltext']}", '', f"> {clean(_t(lang, 'meta_desc_index'))}", '',
             tx['hinweis_volltext'], '']
    for slug, titel, absaetze in abschnitte(TRANSLATIONS, lang):
        if slug in NICHT_IM_VOLLTEXT:
            continue
        teile += [f'## {titel}', '', f"{tx['seite']}: {_url(GRUPPEN_SEITE.get(slug, '/'), lang)}", '']
        for absatz in absaetze:
            teile += [absatz, '']
    return '\n'.join(teile)


def _antwort(text):
    r = Response(text, mimetype='text/plain')
    r.headers['X-Robots-Tag'] = 'noindex'
    r.headers['Link'] = f'<{WEBSITE}/>; rel="canonical"'
    r.headers['Cache-Control'] = 'public, max-age=3600'
    return r


def register(app):
    app.add_url_rule('/llms.txt', 'llms_txt', lambda: _antwort(llms_txt()))
    app.add_url_rule('/llms-full.txt', 'llms_full_de', lambda: _antwort(llms_full('de')))
    app.add_url_rule('/llms-full-en.txt', 'llms_full_en', lambda: _antwort(llms_full('en')))
