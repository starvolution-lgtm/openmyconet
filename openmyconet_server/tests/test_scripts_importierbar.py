"""Jeder Wartungs-Script im Repo-Root muss sich ohne Seiteneffekt importieren
lassen -- der Code steht in `def main()` hinter `if __name__ == '__main__'`,
nicht im Modul-Body. Sonst wuerde schon `import x` (z.B. in einem Import-Check
oder versehentlich) die echte DB anfassen. Faengt zusaetzlich kaputte
`from omn...`-Importe nach einem Refactor ab -- billiger Smoke-Test.
"""
import importlib
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
# wsgi.py baut bewusst beim Import die App (gunicorn-Einstieg) -> ausgenommen.
_SCRIPTS = sorted(
    p.stem for p in _ROOT.glob('*.py') if p.stem != 'wsgi'
)


@pytest.mark.parametrize('modname', _SCRIPTS)
def test_script_importierbar_ohne_seiteneffekt(modname):
    importlib.import_module(modname)
