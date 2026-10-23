"""requirements.txt / requirements-dev.txt (seit 23.10.2026, tools/requirements_erzeugen.py):
beide voll gepinnt mit Pruefsummen, und kein Paket in beiden Dateien -- sonst installierte
die CI fuer gemeinsame Pakete die Dev-Version, und ein Dependabot-Update, das nur
requirements.txt anhebt, liefe ungetestet durch."""
import re
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent


def _pakete(datei):
    text = (HIER / datei).read_text(encoding='utf-8')
    pakete = {}
    for block in re.split(r'\n(?=[A-Za-z0-9_.-]+==)', text):
        m = re.match(r'([A-Za-z0-9_.-]+)==(\S+)', block.strip())
        if m:
            pakete[m.group(1).lower().replace('_', '-')] = ('--hash=sha256:' in block)
    return pakete


def test_alle_pakete_mit_pruefsumme():
    for datei in ('requirements.txt', 'requirements-dev.txt'):
        pakete = _pakete(datei)
        assert pakete, datei
        ohne = [n for n, hat_hash in pakete.items() if not hat_hash]
        assert not ohne, f'{datei}: ohne --hash: {ohne}'


def test_keine_ueberschneidung():
    gemeinsam = set(_pakete('requirements.txt')) & set(_pakete('requirements-dev.txt'))
    assert not gemeinsam, (f'Pakete in beiden Dateien: {sorted(gemeinsam)} -- '
                           'tools/requirements_erzeugen.py neu laufen lassen')


def test_keine_lokalen_pfade():
    for datei in ('requirements.txt', 'requirements-dev.txt'):
        text = (HIER / datei).read_text(encoding='utf-8')
        assert 'AppData' not in text and 'C:/' not in text and 'C:\\' not in text, datei
