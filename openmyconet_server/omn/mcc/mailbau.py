"""Vorstellungs-Mails des Server-MCC: Vorlagen laden und Mail bauen (Klartext + HTML).

Vorlagen liegen je Sprache als Datei in omn/mcc/vorlagen/<name>_<sprache>.md:
Kopfzeilen "Vorlage:" / "Betreff:", Trennzeile "---", danach der Text. Platzhalter
{{TITEL}} (optional, entfaellt samt Leerzeichen) und {{NAME}}. Ein Absatz, der ganz
aus **fett** besteht, wird zur Zwischenueberschrift, Zeilen mit "- " zur Liste,
URLs werden klickbar. Herkunft: lokales MCC (_App/kontakte.py), dort erprobt.
"""
import re
from pathlib import Path

from flask import render_template
from markupsafe import Markup, escape

VORLAGEN_DIR = Path(__file__).resolve().parent / 'vorlagen'
SPRACHEN = {'de': 'DE', 'en': 'EN'}
LOGO_URL = 'https://www.openmyconet.de/logo-openmyconet.png'
DATENSCHUTZ_URL = {
    'de': 'https://www.openmyconet.de/datenschutz.html#kontaktaufnahme',
    'en': 'https://www.openmyconet.de/datenschutz.html?lang=en#kontaktaufnahme',
}
DATENSCHUTZ_TEXT = {'de': 'Hinweise zum Datenschutz', 'en': 'Privacy notice'}
# Fusszeile fuer den Klartext-Teil (im HTML steht sie in mcc/kontakt_email.html;
# bei Aenderung beide Stellen)
KONTAKT_KLARTEXT = ('-- \nOpenMycoNet\nBackesweg 32a\n63477 Maintal\n'
                    'Tel.: +49 (0)6181 4346300\nMobil: +49 (0)172 131 4576\n')

_FETT = re.compile(r'\*\*(.+?)\*\*')
_URL = re.compile(r'https?://[^\s<]+')


def vorlagen():
    """{name: {"titel": ..., "sprachen": {"de": {"betreff", "text"}, ...}}}"""
    ergebnis = {}
    for datei in sorted(VORLAGEN_DIR.glob('*_*.md')):
        name, _, sprache = datei.stem.rpartition('_')
        if sprache not in SPRACHEN or not name:
            continue
        kopf, trenner, text = datei.read_text(encoding='utf-8-sig').replace('\r\n', '\n').partition('\n---\n')
        if not trenner:
            continue
        felder = {}
        for zeile in kopf.splitlines():
            k, _, v = zeile.partition(':')
            felder[k.strip().lower()] = v.strip()
        eintrag = ergebnis.setdefault(name, {'titel': felder.get('vorlage') or name, 'sprachen': {}})
        eintrag['sprachen'][sprache] = {'betreff': felder.get('betreff', ''), 'text': text.strip('\n') + '\n'}
    return ergebnis


def fuellen(s, titel, name):
    """{{TITEL}} leer -> samt folgendem Leerzeichen weg ("Guten Tag Anna Müller,")."""
    s = s.replace('{{TITEL}}', titel) if titel else re.sub(r'\{\{TITEL\}\}[ \t]*', '', s)
    return re.sub(r'[ \t]{2,}', ' ', s.replace('{{NAME}}', name))


def _inline_html(text):
    """Eine Textstelle -> HTML: escapen, **fett**, Links klickbar, Zeilenumbrueche."""
    h = str(escape(text))
    h = _FETT.sub(r'<strong>\1</strong>', h)

    def link(m):
        url, rest = m.group(0), ''
        while url and url[-1] in '.,;:!?)':
            url, rest = url[:-1], url[-1] + rest
        return f'<a href="{url}" style="color:#0a7050;">{url}</a>{rest}'
    h = _URL.sub(link, h)
    # Eingabe ist oben vollstaendig escaped; ergaenzt werden nur <strong>/<a>/<br>
    # (test_namen_werden_im_html_escaped)
    return Markup(h.replace('\n', '<br>\n'))  # nosec B704


def text_zu_bloecken(text):
    """Absaetze (Leerzeile) -> Ueberschrift (ganzer Absatz **fett**), Liste ("- ") oder Absatz."""
    bloecke = []
    for absatz in re.split(r'\n\s*\n', text.strip()):
        zeilen = absatz.splitlines()
        if re.fullmatch(r'\*\*[^*\n]+\*\*', absatz.strip()):
            bloecke.append({'art': 'ueberschrift', 'html': _inline_html(absatz.strip()[2:-2])})
        elif all(z.startswith('- ') for z in zeilen):
            bloecke.append({'art': 'liste', 'punkte': [_inline_html(z[2:]) for z in zeilen]})
        else:
            bloecke.append({'art': 'absatz', 'html': _inline_html(absatz)})
    return bloecke


def mail_bauen(vorlage, sprache, titel, name):
    """-> {betreff, text (Klartext), html} oder ValueError."""
    v = vorlagen().get(vorlage)
    if not v or sprache not in v['sprachen']:
        raise ValueError('Vorlage oder Sprache nicht gefunden.')
    roh = v['sprachen'][sprache]
    betreff = _FETT.sub(r'\1', fuellen(roh['betreff'], titel, name))
    text_mit_fett = fuellen(roh['text'], titel, name)
    html = render_template('mcc/kontakt_email.html', sprache=sprache, betreff=betreff, logo_url=LOGO_URL,
                           bloecke=text_zu_bloecken(text_mit_fett),
                           datenschutz_url=DATENSCHUTZ_URL[sprache], datenschutz_text=DATENSCHUTZ_TEXT[sprache])
    text = (_FETT.sub(r'\1', text_mit_fett).rstrip('\n') + '\n\n' + KONTAKT_KLARTEXT
            + f'{DATENSCHUTZ_TEXT[sprache]}: {DATENSCHUTZ_URL[sprache]}\n')
    return {'betreff': betreff, 'text': text, 'html': html}
