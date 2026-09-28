"""/llms.txt + /llms-full(-en).txt: Textfassung fuer KI-Assistenten, erzeugt aus
translations.json (omn/llms.py, Gruppen aus omn/wissensbasis.py)."""
import pytest

from omn.i18n import TRANSLATIONS
from omn.llms import GRUPPEN_SEITE, NICHT_IM_VOLLTEXT, SEITEN, WEBSITE
from omn.wissensbasis import GROUPS, abschnitte, clean

URLS = ['/llms.txt', '/llms-full.txt', '/llms-full-en.txt']


@pytest.mark.parametrize('url', URLS)
def test_antwort_und_header(client, url):
    r = client.get(url)
    assert r.status_code == 200
    assert r.headers['Content-Type'] == 'text/plain; charset=utf-8'
    # Textfassung soll den HTML-Seiten in Suchmaschinen keine Konkurrenz machen
    assert r.headers['X-Robots-Tag'] == 'noindex'
    assert r.headers['Link'] == f'<{WEBSITE}/>; rel="canonical"'


def test_llms_txt_inhalt(client):
    text = client.get('/llms.txt').get_data(as_text=True)
    assert text.startswith('# OpenMycoNet\n')
    # Einordnung kommt aus den Website-Texten, nicht aus einer Kopie
    assert clean(TRANSLATIONS['de']['bdl_interp_p']) in text
    assert clean(TRANSLATIONS['en']['bdl_interp_p']) in text
    for pfad, _, _ in SEITEN:
        assert f'({WEBSITE}{pfad})' in text
        assert f'({WEBSITE}{pfad}?lang=en)' in text
    assert f'{WEBSITE}/llms-full.txt' in text and f'{WEBSITE}/llms-full-en.txt' in text
    assert '<' not in text.replace('<https', '')  # kein HTML durchgerutscht


@pytest.mark.parametrize('lang, url', [('de', '/llms-full.txt'), ('en', '/llms-full-en.txt')])
def test_volltext_enthaelt_alle_themen(client, lang, url):
    text = client.get(url).get_data(as_text=True)
    for slug, titel, absaetze in abschnitte(TRANSLATIONS, lang):
        if slug in NICHT_IM_VOLLTEXT:
            assert f'## {titel}\n' not in text or slug != 'entwicklungsstand'
            continue
        assert f'## {titel}\n' in text
        for absatz in absaetze:
            assert absatz in text
    # die FAQ der Datenlabor-Seite (fiel beim Chatbot frueher weg) ist vollstaendig drin
    assert clean(TRANSLATIONS[lang]['bdl_faq_1_a']) in text


@pytest.mark.parametrize('lang', ['de', 'en'])
def test_seiten_keys_existieren(lang):
    """Umbenannte/gestrichene Text-Keys fielen sonst still auf Deutsch oder None zurueck."""
    for _, titel, beschreibung in SEITEN:
        for key in [k for k in (titel, beschreibung) if isinstance(k, str)]:
            assert TRANSLATIONS[lang].get(key), f'{lang}: {key} fehlt'


def test_gruppen_seite_passt_zu_gruppen():
    slugs = {slug for slug, _, _ in GROUPS}
    assert set(GRUPPEN_SEITE) <= slugs
    assert slugs >= NICHT_IM_VOLLTEXT
    assert set(GRUPPEN_SEITE.values()) <= {pfad for pfad, _, _ in SEITEN}


@pytest.mark.parametrize('pfad', [p for p, _, _ in SEITEN])
def test_verlinkte_seiten_gibt_es(client, pfad):
    r = client.get(pfad)
    assert r.status_code == 200, pfad
