"""Server-MCC Schritt 2: gespiegelte Statusdateien (omn/mcc/spiegel.py, dateien.py)."""
import io
import tarfile

import pytest

from conftest import eingeloggt
from omn.mcc import spiegel

UEBERSICHT = """# OpenMycoNet — MCC Übersicht

**Letzte Aktualisierung:** 7. Oktober 2026

| Bereich | Status | Statusdatei |
|---|---|---|
| BioComm Hardware | 🟡 Revision läuft | `01_Hardware/Hardware_Status.md` |
| Website / Backend | 🟢 aktuell | `03_Website/Website_Status.md` |
| Firmware | 🔴 nicht begonnen | `04_Firmware/Firmware_Status.md` |

---

## Aktuell wichtigste offene Punkte (projektübergreifend)

1. Lieferung abwarten
2. Firmware spezifizieren

---
"""
HARDWARE = """# Hardware

## Offene Punkte
- [ ] Sondenspitzen bestellen
- [x] Erledigtes
<script>alert(1)</script>

## Offene Fragen
1. Welche LED?
"""


def _tar(dateien):
    puffer = io.BytesIO()
    with tarfile.open(fileobj=puffer, mode='w:gz') as tar:
        for name, inhalt in dateien.items():
            daten = inhalt.encode('utf-8')
            info = tarfile.TarInfo(name)
            info.size = len(daten)
            info.mtime = 1780000000  # Ende Mai 2026 -> ueber 30 Tage alt
            tar.addfile(info, io.BytesIO(daten))
    return puffer.getvalue()


STANDARD = {'00_UEBERSICHT.md': UEBERSICHT, '01_Hardware/Hardware_Status.md': HARDWARE,
            '03_Website/Website_Status.md': '# Website\n\n- [ ] Datenschutz prüfen\n'}


@pytest.fixture()
def gespiegelt(app):
    with app.app_context():
        spiegel.empfangen(_tar(STANDARD), quelle='test')
    return app


@pytest.fixture()
def angemeldet(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    return client


def test_empfangen_und_auswerten(gespiegelt):
    s = spiegel.stand()
    assert s['anzahl'] == 3 and s['zeit'].tzinfo is not None
    ue = spiegel.uebersicht()
    assert ue['letzte'] == '7. Oktober 2026'
    assert [b['bereich'] for b in ue['bereiche']] == ['BioComm Hardware', 'Website / Backend', 'Firmware']
    assert [b['klasse'] for b in ue['bereiche']] == ['arbeit', 'gut', 'offen']
    assert ue['bereiche'][2]['pfad'] is None  # Firmware-Datei nicht mitgeschickt
    assert ue['bereiche'][0]['stale'] is True  # mtime aus dem Archiv bleibt erhalten
    assert ue['prioritaeten'] == ['Lieferung abwarten', 'Firmware spezifizieren']
    offen = {d['titel']: d for d in spiegel.offene_punkte()}
    hw = offen['Hardware Status']['gruppen']
    assert [p['html'] for p in hw['Offene Punkte']] == ['Sondenspitzen bestellen']
    assert hw['Offene Fragen'][0]['frage'] is True


def test_neuer_upload_ersetzt_alles(gespiegelt):
    spiegel.empfangen(_tar({'00_UEBERSICHT.md': UEBERSICHT}))
    assert spiegel.sicherer_pfad('01_Hardware/Hardware_Status.md') is None
    assert spiegel.stand()['anzahl'] == 1


@pytest.mark.parametrize('name', ['../boese.md', '/etc/boese.md', 'skript.sh', '.versteckt/x.md'])
def test_unzulaessige_eintraege_behalten_alten_spiegel(gespiegelt, name):
    with pytest.raises(ValueError):
        spiegel.empfangen(_tar({'00_UEBERSICHT.md': 'neu', name: 'x'}))
    assert spiegel.stand()['anzahl'] == 3
    assert 'Lieferung abwarten' in spiegel.sicherer_pfad('00_UEBERSICHT.md').read_text(encoding='utf-8')


def test_kaputtes_archiv(gespiegelt):
    with pytest.raises(ValueError):
        spiegel.empfangen(b'kein tar')
    assert spiegel.stand()['anzahl'] == 3


def test_seiten(gespiegelt, angemeldet):
    t = angemeldet.get('/mcc/status').get_data(as_text=True)
    assert 'BioComm Hardware' in t and 'Lieferung abwarten' in t and 'Datei nicht gespiegelt' in t
    r = angemeldet.get('/mcc/datei/01_Hardware/Hardware_Status.md')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'Sondenspitzen bestellen' in html and '<script>alert' not in html
    t = angemeldet.get('/mcc/offen').get_data(as_text=True)
    assert 'Sondenspitzen bestellen' in t and 'Datenschutz prüfen' in t and 'Erledigtes' not in t
    start = angemeldet.get('/mcc').get_data(as_text=True)
    assert 'Statusdateien' in start and 'noch nicht gespiegelt' not in start


@pytest.mark.parametrize('pfad', ['../../omn/config.py', '..%2F..%2Fwsgi.py', '00_UEBERSICHT.txt', 'gibtsnicht.md'])
def test_datei_nur_aus_dem_spiegel(gespiegelt, angemeldet, pfad):
    assert angemeldet.get(f'/mcc/datei/{pfad}').status_code == 404


def test_ohne_spiegel(app, angemeldet):
    assert 'Noch keine Statusdateien' in angemeldet.get('/mcc/status').get_data(as_text=True)
    assert angemeldet.get('/mcc/offen').status_code == 200


def test_ohne_login(gespiegelt, client):
    for pfad in ('/mcc/status', '/mcc/offen', '/mcc/datei/00_UEBERSICHT.md'):
        assert client.get(pfad).status_code == 302


def test_cli_empfangen(app):
    r = app.test_cli_runner().invoke(args=['mcc-spiegel-empfangen', '--quelle', 'PC'], input=_tar(STANDARD))
    assert r.exit_code == 0, r.output
    assert '3 Dateien gespiegelt' in r.output
    r = app.test_cli_runner().invoke(args=['mcc-spiegel-empfangen'], input=b'kaputt')
    assert r.exit_code != 0 and spiegel.stand()['anzahl'] == 3
