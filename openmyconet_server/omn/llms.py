"""
llms.py -- Textfassung der Website fuer KI-Assistenten (Vorschlag llms.txt).

  /llms.txt          kurzes Inhaltsverzeichnis in Markdown: was OpenMycoNet ist,
                     die Einordnung "kein Wirkungsnachweis", die Seiten mit Link
  /llms-full.txt     alle Website-Texte auf Deutsch, nach Themen
  /llms-full-en.txt  dasselbe auf Englisch
Die beiden Volltexte beginnen mit einem YAML-Frontmatter (titel, sprache,
stand, quelle, hinweis); /llms.txt bewusst nicht (muss laut Vorschlag mit '# ' beginnen).

Alles wird aus translations.json erzeugt (Themengruppen aus omn/wissensbasis.py,
dieselben wie beim RAG-Chatbot) -- keine zweite Textkopie, die veralten kann.
Nicht fuer Suchmaschinen gedacht: `X-Robots-Tag: noindex` + canonical auf die
Startseite, damit die Textfassung den HTML-Seiten keine Konkurrenz macht.
Links zeigen immer auf die kanonische Domain (auch auf Staging).
"""
import json
import os
from datetime import datetime, timezone
from html.parser import HTMLParser

from flask import Response

from omn.i18n import _TRANSLATIONS_PATH, TRANSLATIONS
from omn.wissensbasis import abschnitte, clean

# Das Impressum ist eine statische, nur deutsche Seite (nicht in translations.json).
IMPRESSUM_PATH = os.path.join(os.path.dirname(_TRANSLATIONS_PATH), 'impressum.html')


class _ImpressumLeser(HTMLParser):
    """{Ueberschrift: [Absatz, ...]}, Absatz = Liste seiner Zeilen (<br> trennt);
    dazu die mailto-Adressen."""

    def __init__(self):
        super().__init__()
        self.abschnitte, self.mails = {}, []
        self._h2, self._absatz, self._in_h2 = None, None, False
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == 'h2':
            self._in_h2, self._text = True, []
        elif tag == 'p' and self._h2:
            self._absatz, self._text = [], []
        elif tag == 'br' and self._absatz is not None:
            self._zeile_ab()
        elif tag == 'a':
            href = dict(attrs).get('href') or ''
            if href.startswith('mailto:'):
                self.mails.append(href[len('mailto:'):])

    def handle_data(self, data):
        if self._in_h2 or self._absatz is not None:
            self._text.append(data)

    def _zeile_ab(self):
        zeile = ' '.join(''.join(self._text).split())
        if zeile:
            self._absatz.append(zeile)
        self._text = []

    def handle_endtag(self, tag):
        if tag == 'h2' and self._in_h2:
            self._h2 = ' '.join(''.join(self._text).split())
            self.abschnitte[self._h2] = []
            self._in_h2 = False
        elif tag == 'p' and self._absatz is not None:
            self._zeile_ab()
            if self._absatz:
                self.abschnitte[self._h2].append(self._absatz)
            self._absatz = None


def impressum():
    """Angaben aus dem Impressum fuer llms.txt. Bewusst ohne Strasse und Telefon
    (stehen im verlinkten Impressum). Fehlt ein erwarteter Abschnitt -> KeyError,
    das faengt test_llms.py ab, bevor es live geht."""
    leser = _ImpressumLeser()
    with open(IMPRESSUM_PATH, encoding='utf-8') as f:
        leser.feed(f.read())
    a = leser.abschnitte
    anbieter = next(v for k, v in a.items() if k.startswith('Angaben gemäß'))[0]
    return {
        'anbieter': f'{anbieter[0]}, {anbieter[-2].split(" ", 1)[1]}, {anbieter[-1]}',
        'mail': leser.mails[0],
        'schutzrechte': ' '.join(a['Schutzrechte'][0]),
        'lizenz': ' '.join(next(p for p in a['Urheberrecht'] if 'CC BY' in ' '.join(p))),
    }

WEBSITE = 'https://www.openmyconet.de'

# Seiten nach Zweck gegliedert: ({lang: Ueberschrift}, [(Pfad, Titel-Key oder
# {lang: Titel}, Beschreibungs-Key oder None), ...]). Pfade mit #anker zeigen auf
# Abschnitte der Startseite.
SEITEN_GRUPPEN = [
    ({'de': 'Wissenschaft & Methode', 'en': 'Science & method'}, [
        ('/', {'de': 'Startseite', 'en': 'Home'}, 'meta_desc_index'),
        ('/mykorrhiza-netzwerke.html', 'myk_page_title', 'myk_meta_desc'),
        ('/bioelektrizitaet-biocomm.html', 'myk2_page_title', 'myk2_meta_desc'),
        ('/citizen-science-openmyconet.html', 'myk3_page_title', 'myk3_meta_desc'),
        ('/wie-wir-arbeiten', 'wwa_page_title', 'wwa_meta_desc'),
        ('/quellennachweise.html', {'de': 'Quellennachweise & Erkenntnispfad',
                                    'en': 'References & path of knowledge'}, 'q_subtitle'),
    ]),
    ({'de': 'BioComm-Plattform', 'en': 'BioComm platform'}, [
        ('/biocomm', 'bc_page_title', 'bc_meta_desc'),
        ('/biocomm/hardware', 'bch_page_title', 'bch_meta_desc'),
        ('/biocomm/software', 'bcs_page_title', 'bcs_meta_desc'),
        ('/biocomm/datenlabor', 'bdl_page_title', 'bdl_meta_desc'),
    ]),
    ({'de': 'Mitmachen & Unterstützen', 'en': 'Participation & support'}, [
        ('/#mitmachen', {'de': 'Mitmachen: einen Messknoten betreiben',
                         'en': 'Take part: operate a measurement node'}, 'desc_mitmachen'),
        ('/#anmelden', 'a_h2', 'a_intro'),
        ('/#spenden', 'h2_spenden', 'donate_p'),
        ('/foerderer.html', {'de': 'Förderung & Kooperation', 'en': 'Funding & cooperation'}, None),
        ('/kontakt', 'kontakt_page_title', 'kontakt_meta_desc'),
    ]),
    ({'de': 'Weiteres', 'en': 'More'}, [
        ('/#daten', 'label_daten', 'desc_daten'),
        ('/datenschutz.html', {'de': 'Datenschutz', 'en': 'Privacy policy'}, None),
        ('/impressum.html', {'de': 'Impressum', 'en': 'Legal notice (German)'}, None),
        ('/medien.html', 'h1_medien', 'desc_medien'),
        ('/news', {'de': 'Neuigkeiten', 'en': 'News'}, None),
    ]),
]
SEITEN = [s for _, seiten in SEITEN_GRUPPEN for s in seiten]

# Eckdaten: ({lang: Bezeichnung}, Text-Key). Alles aus den Website-Texten --
# bewusst KEINE frei formulierten Angaben (z. B. eine Datenlizenz, solange die
# Website keine nennt).
ECKDATEN = [
    ({'de': 'Initiator', 'en': 'Initiator'}, 'about_p1'),
    ({'de': 'Prinzip', 'en': 'Principle'}, 'about_p2'),
    ({'de': 'Stand der Hardware', 'en': 'Hardware status'}, 'bch_status_p'),
    ({'de': 'Stand der Software', 'en': 'Software status'}, 'bcs_page_title'),
    ({'de': 'Datenlabor', 'en': 'Data Lab'}, 'bdl_page_title'),
    ({'de': 'Finanzierung', 'en': 'Funding'}, 'donate_p'),
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
        'eckdaten': 'Projekt-Eckdaten',
        'anbieter': 'Anbieter und verantwortlich',
        'impressum': 'Impressum',
        'kontakt': 'Kontakt',
        'schutzrechte': 'Schutzrechte',
        'lizenz': 'Lizenz der Messdaten',
        'einordnung': 'Einordnung',
        'stand': 'Stand dieser Datei',
        'volltext': 'Vollständige Texte',
        'volltext_de': 'Alle Website-Texte auf Deutsch, nach Themen',
        'volltext_en': 'All website texts in English, by topic',
        'titel_volltext': 'OpenMycoNet — alle Website-Texte (Deutsch)',
        'hinweis_volltext': ('Automatisch aus den Texten der Website erzeugt. Maßgeblich ist die '
                             'jeweils verlinkte Seite.'),
        'seite': 'Seite',
    },
    'en': {
        'eckdaten': 'Project facts',
        'anbieter': 'Provider and responsible person',
        'impressum': 'legal notice',
        'kontakt': 'Contact',
        'schutzrechte': 'Intellectual property',
        'lizenz': 'Licence of the measurement data',
        'einordnung': 'Context',
        'stand': 'This file as of',
        'titel_volltext': 'OpenMycoNet — all website texts (English)',
        'hinweis_volltext': ('Generated automatically from the website texts. The linked page is '
                             'authoritative.'),
        'seite': 'Page',
    },
}


def _t(lang, key):
    return TRANSLATIONS.get(lang, {}).get(key) or TRANSLATIONS['de'].get(key)


def _url(pfad, lang):
    pfad, _, anker = pfad.partition('#')
    return (WEBSITE + pfad + ('' if lang == 'de' else f'?lang={lang}')
            + (f'#{anker}' if anker else ''))


def _seitenliste(lang, ebene):
    zeilen = []
    for gruppe, seiten in SEITEN_GRUPPEN:
        zeilen += [f"{ebene} {gruppe[lang]}", '']
        for pfad, titel, beschreibung in seiten:
            name = (titel.get(lang) or titel['de']) if isinstance(titel, dict) else clean(_t(lang, titel))
            zeile = f'- [{name}]({_url(pfad, lang)})'
            if beschreibung:
                zeile += f': {clean(_t(lang, beschreibung))}'
            zeilen.append(zeile)
        zeilen.append('')
    return zeilen


def _eckdaten(lang, ebene):
    tx = TEXTE[lang]
    imp = impressum()
    zusatz = '' if lang == 'de' else ' (Impressum, German original)'
    zeilen = [f"{ebene} {tx['eckdaten']}", '']
    zeilen += [f"- **{name[lang]}:** {clean(_t(lang, key))}" for name, key in ECKDATEN]
    zeilen += [
        f"- **{tx['anbieter']}:** {imp['anbieter']} ([{tx['impressum']}]({WEBSITE}/impressum.html))",
        f"- **{tx['kontakt']}:** {imp['mail']}",
        f"- **{tx['schutzrechte']}:** {imp['schutzrechte']}{zusatz}",
        f"- **{tx['lizenz']}:** {imp['lizenz']}{zusatz}",
        f"- **{tx['stand']}:** {stand()}",
        '',
    ]
    return zeilen


def _einordnung(lang, ebene):
    return [f"{ebene} {TEXTE[lang]['einordnung']}", '',
            f"**{clean(_t(lang, 'bdl_interp_title'))}** {clean(_t(lang, 'bdl_interp_p'))}", '']


def llms_txt():
    de = TEXTE['de']
    teile = [
        '# OpenMycoNet',
        '',
        f"> {clean(_t('de', 'meta_desc_index'))}",
        '',
        *_eckdaten('de', '##'),
        *_einordnung('de', '##'),
        *_seitenliste('de', '##'),
        f"## {de['volltext']}",
        '',
        f"- [llms-full.txt]({WEBSITE}/llms-full.txt): {de['volltext_de']}",
        f"- [llms-full-en.txt]({WEBSITE}/llms-full-en.txt): {de['volltext_en']}",
        '',
        '## English',
        '',
        f"> {clean(_t('en', 'meta_desc_index'))}",
        '',
        *_eckdaten('en', '###'),
        *_einordnung('en', '###'),
        *_seitenliste('en', '###'),
    ]
    return '\n'.join(teile)


def stand():
    """Datum der Website-Texte (UTC). Auf dem Server = Commit-Zeit des Deploys:
    `git archive` setzt die Datei-Zeit auf den Commit, rsync -a behaelt sie."""
    return datetime.fromtimestamp(os.path.getmtime(_TRANSLATIONS_PATH), timezone.utc).date().isoformat()


def _frontmatter(lang):
    """YAML-Kopf fuer die Volltexte (nicht fuer /llms.txt: die muss mit '# ' beginnen).
    Werte als JSON-Strings -- gueltiges YAML, auch mit Doppelpunkt/Anfuehrungszeichen."""
    tx = TEXTE[lang]
    felder = {
        'titel': tx['titel_volltext'],
        'sprache': lang,
        'stand': stand(),
        'quelle': WEBSITE + '/',
        'hinweis': tx['hinweis_volltext'],
    }
    zeilen = [f'{k}: {v if k in ("sprache", "stand") else json.dumps(v, ensure_ascii=False)}'
              for k, v in felder.items()]
    return ['---', *zeilen, '---', '']


def llms_full(lang):
    tx = TEXTE[lang]
    teile = [*_frontmatter(lang), f"# {tx['titel_volltext']}", '',
             f"> {clean(_t(lang, 'meta_desc_index'))}", '', tx['hinweis_volltext'], '']
    for slug, titel, absaetze in abschnitte(TRANSLATIONS, lang):
        if slug in NICHT_IM_VOLLTEXT:
            continue
        teile += [f'## {titel}', '', f"{tx['seite']}: {_url(GRUPPEN_SEITE.get(slug, '/'), lang)}", '']
        for absatz in absaetze:
            teile += [absatz, '']
    imp = impressum()
    zusatz = '' if lang == 'de' else ' (German original)'
    teile += [f"## {tx['impressum'][:1].upper()}{tx['impressum'][1:]}", '',
              f"{tx['seite']}: {WEBSITE}/impressum.html", '',
              f"{tx['anbieter']}: {imp['anbieter']} · {imp['mail']}", '',
              f"{tx['schutzrechte']}: {imp['schutzrechte']}{zusatz}", '',
              f"{tx['lizenz']}: {imp['lizenz']}{zusatz}", '']
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
