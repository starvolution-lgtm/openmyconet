"""Songtext-Spuren fuer den Musik-Player (WCAG 1.2.1 / axe `audio-caption`).

- 5 WebVTT-Dateien unter app/static/lyrics/ (eine je Track aus OMN_TRACKS)
- <track kind="captions"> im Player -> axe `audio-caption` erfuellt
- lesbare Volltext-Fassung + i18n-Label auf /medien.html
"""
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
LYRICS = REPO / "app" / "static" / "lyrics"

TRACKS = [
    "listen-to-the-forest",
    "listening-to-the-trees",
    "the-oldest-living-network",
    "three-ways-of-knowing",
    "nobody-funds-the-ground",
]


@pytest.mark.parametrize("stem", TRACKS)
def test_vtt_datei_ist_wohlgeformt(stem):
    vtt = (LYRICS / f"{stem}.vtt").read_text(encoding="utf-8")
    assert vtt.startswith("WEBVTT"), "erste Zeile muss WEBVTT sein"
    cues = re.findall(r"^\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}$", vtt, re.M)
    assert len(cues) >= 5, f"{stem}: zu wenige Cues ({len(cues)})"
    # keine SubRip-Kommata mehr im Zeitstempel
    assert ",00" not in vtt and not re.search(r"\d,\d{3} -->", vtt)


def test_manifest_und_vtt_decken_sich():
    base = (REPO / "app" / "templates" / "site" / "base.html").read_text(encoding="utf-8")
    genannt = set(re.findall(r'asset\("lyrics/([a-z-]+)\.vtt"\)', base))
    assert genannt == set(TRACKS)
    assert '<track id="omn-cc" kind="captions"' in base


def test_pa11y_ignoriert_audio_caption_nicht_mehr():
    cfg = json.loads((REPO / ".pa11yci.json").read_text(encoding="utf-8"))
    assert "audio-caption" not in cfg["defaults"]["ignore"]


def test_medien_seite_hat_songtexte(client):
    html = client.get("/medien.html").get_data(as_text=True)
    assert 'id="songtexte"' in html
    assert "Beneath the roots and fallen leaves" in html  # aus "Listen to the Forest"
    assert "Nobody in the hall" in html                    # aus "Nobody Funds the Ground"
    assert "Songtexte" in html                             # de-Label (Default)


@pytest.mark.parametrize("lang,label", [
    ("en", "Lyrics"), ("nl", "Songteksten"), ("fr", "Paroles"), ("es", "Letras"),
])
def test_songtext_label_uebersetzt(client, lang, label):
    daten = client.get(f"/i18n/{lang}.json").get_json()
    assert daten["musik_texte_label"] == label
    assert daten["musik_texte_hint"]


def test_vtt_wird_als_text_vtt_ausgeliefert(client):
    r = client.get("/lyrics/listen-to-the-forest.vtt")
    assert r.status_code == 200
    assert r.mimetype == "text/vtt"
