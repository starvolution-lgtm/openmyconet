"""requirements.txt + requirements-dev.txt mit Pruefsummen neu erzeugen (seit 23.10.2026).

Aufruf (im Ordner openmyconet_server):
    venv/Scripts/python.exe tools/requirements_erzeugen.py

- requirements.txt: Server-Abhaengigkeiten, aus sich selbst neu aufgeloest (Versionen
  bleiben, fehlende indirekte Abhaengigkeiten + Hashes kommen dazu).
- requirements-dev.txt: NUR die Test-/CI-Werkzeuge (Liste DEV_WERKZEUGE) und deren
  Abhaengigkeiten, die nicht schon in requirements.txt stehen. Gemeinsame Pakete
  stehen nur in requirements.txt -- sonst testet die CI veraltete Versionen, wenn
  Dependabot nur requirements.txt anhebt. tests/test_requirements.py prueft das.
Installation (CI): pip install --require-hashes -r requirements.txt -r requirements-dev.txt
Braucht `uv` im venv (pip install uv).
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent
DEV_WERKZEUGE = ['pytest==8.3.4', 'ruff==0.17.1', 'bandit==1.9.4', 'pip-audit==2.10.1']
UV = [sys.executable, '-m', 'uv', 'pip', 'compile', '--generate-hashes', '--universal',
      '--python-version', '3.14', '--quiet', '--no-header']
KOPF = ('# Erzeugt von tools/requirements_erzeugen.py (uv pip compile --generate-hashes).\n'
        '# Nicht von Hand aendern; Dependabot hebt einzelne Eintraege samt Hashes an.\n')


def _name(zeile):
    m = re.match(r'^([A-Za-z0-9_.-]+)==', zeile)
    return m.group(1).lower().replace('_', '-') if m else None


def bloecke(text):
    """Text -> Liste (paketname, blocktext); ein Block = Pin-Zeile + Hash-/Kommentarzeilen."""
    erg, aktuell, name = [], [], None
    for zeile in text.splitlines(keepends=True):
        n = _name(zeile)
        if n:
            if name:
                erg.append((name, ''.join(aktuell)))
            aktuell, name = [zeile], n
        elif name:
            aktuell.append(zeile)
    if name:
        erg.append((name, ''.join(aktuell)))
    return erg


def main():
    prod = HIER / 'requirements.txt'
    dev = HIER / 'requirements-dev.txt'
    with tempfile.TemporaryDirectory() as tmp:
        ein = Path(tmp) / 'prod.in'
        ein.write_text(prod.read_text(encoding='utf-8'), encoding='utf-8')
        aus = Path(tmp) / 'prod.txt'
        subprocess.run(UV + [str(ein), '-o', str(aus)], check=True)
        prod_text = aus.read_text(encoding='utf-8').replace(str(ein).replace('\\', '/'), 'requirements.txt')
        prod.write_text(KOPF + prod_text, encoding='utf-8', newline='\n')

        dev_ein = Path(tmp) / 'dev.in'
        dev_ein.write_text('-c ' + prod.as_posix() + '\n' + '\n'.join(DEV_WERKZEUGE) + '\n', encoding='utf-8')
        dev_aus = Path(tmp) / 'dev.txt'
        subprocess.run(UV + [str(dev_ein), '-o', str(dev_aus)], check=True)
        prod_namen = {n for n, _ in bloecke(prod_text)}
        nur_dev = [b for n, b in bloecke(dev_aus.read_text(encoding='utf-8')) if n not in prod_namen]
        dev_text = ''.join(nur_dev).replace(str(dev_ein).replace('\\', '/'), 'tools/requirements_erzeugen.py')
        dev.write_text(KOPF + '# Nur Werkzeuge; zusammen mit requirements.txt installieren:\n'
                       '#   pip install --require-hashes -r requirements.txt -r requirements-dev.txt\n'
                       + dev_text, encoding='utf-8', newline='\n')
    print(f'requirements.txt: {len(prod_namen)} Pakete, requirements-dev.txt: {len(nur_dev)} Pakete')


if __name__ == '__main__':
    main()
