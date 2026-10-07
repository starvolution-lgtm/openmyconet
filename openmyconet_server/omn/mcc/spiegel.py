"""Server-MCC, Schritt 2: Statusdateien des Kontrollzentrums, nur lesend.

Das lokale MCC (Kontrollzentrum _App/spiegel.py) schickt beim Start und alle 15
Minuten die Statusdateien als tar.gz ueber SSH an `flask mcc-spiegel-empfangen`.
Hier werden sie in instance/mcc_spiegel/ abgelegt (vom Deploy ausgenommen, nicht
oeffentlich ausgeliefert) und unter /mcc/status, /mcc/datei/..., /mcc/offen
angezeigt. Abhaken bleibt am PC: es gibt nie zwei Fassungen einer Datei.

Ein Upload ersetzt den ganzen Spiegel (neuer Ordner, dann Tausch) -- lokal
geloeschte Dateien verschwinden also auch hier. Die Auswertung (Uebersicht,
offene Punkte) entspricht _App/app.py (parse_uebersicht, offene_punkte).
"""
import io
import json
import re
import shutil
import tarfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import bleach
import markdown as md_lib
from flask import current_app

MAX_DATEI = 2 * 1024 * 1024      # je Datei
MAX_GESAMT = 20 * 1024 * 1024    # entpackt insgesamt
MAX_ANZAHL = 500
STAND_DATEI = '.stand.json'

MD_ERWEITERUNGEN = ['tables', 'fenced_code', 'sane_lists', 'nl2br']
ERLAUBTE_TAGS = ['p', 'br', 'hr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'em', 'b', 'i', 'code', 'pre',
                 'blockquote', 'ul', 'ol', 'li', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'a', 'del', 'sup', 'sub']
ERLAUBTE_ATTRIBUTE = {'a': ['href', 'title'], 'th': ['align'], 'td': ['align']}

STATUS_KLASSE = {'🟢': 'gut', '🟡': 'arbeit', '🔴': 'offen'}
STATUS_LABEL = {'🟢': 'Aktuell', '🟡': 'In Arbeit', '🔴': 'Nicht begonnen'}


def ordner():
    return Path(current_app.instance_path) / 'mcc_spiegel'


# --- Empfangen -----------------------------------------------------------------
def empfangen(daten: bytes, quelle=''):
    """tar.gz -> neuer Spiegel. Nur .md-Dateien in Unterordnern, Groessen begrenzt.
    -> {'anzahl', 'bytes'} oder ValueError (dann bleibt der alte Spiegel)."""
    ziel = ordner()
    ziel.parent.mkdir(parents=True, exist_ok=True)
    neu = ziel.with_name('mcc_spiegel.neu')
    alt = ziel.with_name('mcc_spiegel.alt')
    for p in (neu, alt):
        shutil.rmtree(p, ignore_errors=True)
    neu.mkdir()
    anzahl = gesamt = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(daten), mode='r:gz') as tar:
            for m in tar:
                if not m.isfile():
                    continue
                pfad = PurePosixPath(m.name)
                if (pfad.is_absolute() or '..' in pfad.parts or pfad.suffix.lower() != '.md'
                        or any(t.startswith('.') for t in pfad.parts)):
                    raise ValueError(f'unzulässiger Eintrag: {m.name}')
                if m.size > MAX_DATEI:
                    raise ValueError(f'zu groß: {m.name}')
                anzahl += 1
                gesamt += m.size
                if anzahl > MAX_ANZAHL or gesamt > MAX_GESAMT:
                    raise ValueError('zu viele oder zu große Dateien')
                tar.extract(m, neu, filter='data')  # data-Filter: keine Links/Rechte/Pfad-Tricks
    except (tarfile.TarError, OSError, EOFError) as e:
        shutil.rmtree(neu, ignore_errors=True)
        raise ValueError(f'Archiv nicht lesbar: {e}')
    except ValueError:
        shutil.rmtree(neu, ignore_errors=True)
        raise
    (neu / STAND_DATEI).write_text(json.dumps({
        'zeit': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'anzahl': anzahl, 'bytes': gesamt, 'quelle': quelle[:100]}), encoding='utf-8')
    if ziel.exists():
        ziel.rename(alt)
    neu.rename(ziel)
    shutil.rmtree(alt, ignore_errors=True)
    return {'anzahl': anzahl, 'bytes': gesamt}


def stand():
    """{'zeit': datetime (UTC, tz-aware), 'anzahl', ...} oder None (noch nie gespiegelt)."""
    try:
        s = json.loads((ordner() / STAND_DATEI).read_text(encoding='utf-8'))
        s['zeit'] = datetime.fromisoformat(s['zeit'])
        return s
    except (OSError, ValueError, KeyError):
        return None


# --- Lesen ---------------------------------------------------------------------
def sicherer_pfad(rel):
    """Datei im Spiegel oder None (kein Weg hinaus, nur .md)."""
    basis = ordner().resolve()
    try:
        p = (basis / rel).resolve()
    except (OSError, ValueError):
        return None
    if not p.is_relative_to(basis) or p.suffix.lower() != '.md' or not p.is_file():
        return None
    return p


def markdown_html(text):
    html = md_lib.markdown(text, extensions=MD_ERWEITERUNGEN)
    return bleach.clean(html, tags=ERLAUBTE_TAGS, attributes=ERLAUBTE_ATTRIBUTE,
                        protocols=['http', 'https', 'mailto'], strip=True)


def uebersicht():
    """Aus 00_UEBERSICHT.md: Letzte Aktualisierung, Bereichs-Tabelle, Prioritaeten.
    None, solange nichts gespiegelt ist."""
    datei = sicherer_pfad('00_UEBERSICHT.md')
    if not datei:
        return None
    text = datei.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'\*\*Letzte Aktualisierung:\*\*\s*(.+)', text)
    letzte = m.group(1).strip() if m else 'unbekannt'
    jetzt = datetime.now(timezone.utc).timestamp()
    bereiche = []
    for row in re.finditer(r'^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*`([^`]+)`\s*\|\s*$', text, re.MULTILINE):
        bereich, status_text, pfad = (g.strip() for g in row.groups())
        if bereich.lower() in ('bereich', '---'):
            continue
        emoji = next((e for e in STATUS_KLASSE if e in status_text), '🟡')
        p = sicherer_pfad(pfad)
        tage = int((jetzt - p.stat().st_mtime) // 86400) if p else None
        bereiche.append({'bereich': bereich, 'status_text': status_text, 'pfad': pfad if p else None,
                         'klasse': STATUS_KLASSE[emoji], 'label': STATUS_LABEL[emoji],
                         'tage_alt': tage, 'stale': tage is not None and tage >= 30})
    prio = []
    pm = re.search(r'## Aktuell wichtigste offene Punkte.*?\n(.*?)(?:\n---|\n## )', text, re.DOTALL)
    if pm:
        for zeile in pm.group(1).splitlines():
            m2 = re.match(r'^\d+\.\s+(.*)', zeile.strip())
            if m2:
                prio.append(m2.group(1))
    return {'letzte': letzte, 'bereiche': bereiche, 'prioritaeten': prio}


_CHECKBOX = re.compile(r'^\s*[-*]\s+\[ \]\s+(.*)')
_LISTE = re.compile(r'^\s*(?:\d+\.|[-*])\s+(?!\[[ xX]\])(.*)')
_UEBERSCHRIFT = re.compile(r'^(#{1,6})\s+(.*)')


def offene_punkte():
    """Offene Kontrollkaestchen und Listenpunkte unter Ueberschriften mit "Frage"
    aus Status-Dateien und Versuchsplan (wie _App/app.py::offene_punkte)."""
    basis = ordner()
    ergebnis = []
    if not basis.is_dir():
        return ergebnis
    for datei in sorted(basis.rglob('*.md')):
        if 'Status' not in datei.name and 'Versuchsplan' not in datei.name:
            continue
        stapel, gruppen, im_code = [], {}, False
        for zeile in datei.read_text(encoding='utf-8', errors='replace').splitlines():
            if zeile.strip().startswith('```'):
                im_code = not im_code
                continue
            if im_code:
                continue
            m = _UEBERSCHRIFT.match(zeile)
            if m:
                ebene = len(m.group(1))
                stapel = [s for s in stapel if s[0] < ebene] + [(ebene, m.group(2).strip())]
                continue
            abschnitt = ' › '.join(t for _, t in stapel[1:]) or (stapel[0][1] if stapel else '')
            frage_abschnitt = any('frage' in t.lower() for _, t in stapel)
            cb = _CHECKBOX.match(zeile)
            li = _LISTE.match(zeile) if frage_abschnitt and not cb else None
            treffer = cb or li
            if treffer:
                html = markdown_html(treffer.group(1).strip()).removeprefix('<p>').removesuffix('</p>')
                gruppen.setdefault(abschnitt, []).append({'html': html, 'frage': bool(li)})
        if gruppen:
            rel = datei.relative_to(basis).as_posix()
            ergebnis.append({'datei': rel, 'titel': datei.stem.replace('_', ' '), 'gruppen': gruppen,
                             'anzahl': sum(len(v) for v in gruppen.values())})
    return ergebnis
