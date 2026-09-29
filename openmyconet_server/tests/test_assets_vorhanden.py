"""Jede per asset() eingebundene Datei muss im Repo liegen (29.09.2026, beim Umstellen der
Bilder auf kleinere WebP-Fassungen). asset() haengt ?v=<Datei-Zeitstempel> an und setzt
v=0, wenn die Datei fehlt -- dann waere die Seite nach dem Deploy (rsync --delete) kaputt.
Ausgenommen: serververwaltete Grossmedien (mp3/pdf, deploy-exclude.txt)."""
import re

import pytest

from omn.llms import SEITEN

PFADE = sorted({p.split('#')[0] for p, _, _ in SEITEN})


@pytest.mark.parametrize('pfad', PFADE)
def test_keine_fehlenden_assets(client, pfad):
    html = client.get(pfad).get_data(as_text=True)
    fehlend = sorted({m for m in re.findall(r'([\w./-]+)\?v=0\b', html)
                      if not m.endswith(('.mp3', '.pdf'))})
    assert not fehlend, f'{pfad}: fehlende Dateien {fehlend}'


def test_medien_laedt_cover_erst_bei_bedarf(client):
    html = client.get('/medien.html').get_data(as_text=True)
    assert html.count('class="omn-cover-img') == 5
    assert html.count('data-src=') == 4            # nur das erste Cover sofort
    assert '.jpeg' not in html                     # alte JPEG-Cover sind ersetzt
    assert 'fetchpriority="high"' in html          # Broschuerenbild = groesstes Element
