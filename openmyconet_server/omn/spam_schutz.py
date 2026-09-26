"""
spam_schutz.py — gemeinsamer Spam-Schutz für /api/register und /api/bewerbung.

Rate-Limiter ist das gleiche dateibasierte Muster wie im alten contact.php
(Verzeichnis im Temp-Ordner, ein JSON-Log pro IP+Key, gleitendes Zeitfenster).
"""

import hashlib
import json
import os
import re
import tempfile
import time

RATE_DIR = os.path.join(tempfile.gettempdir(), 'omn_rl')


def _rate_datei(ip, key):
    ip = re.sub(r'[^a-fA-F0-9:.]', '', ip or '0')
    # MD5 nur als kurzer, dateisystemsicherer Name fuer die Rate-Limit-Datei --
    # keine Sicherheitsfunktion (kein Passwort-Hash, keine Integritaetspruefung).
    schluessel = hashlib.md5(f'{ip}_{key}'.encode(), usedforsecurity=False).hexdigest()
    return os.path.join(RATE_DIR, schluessel + '.json')


def _log_lesen(rate_file, window, now):
    log = []
    if os.path.exists(rate_file):
        try:
            with open(rate_file, 'r') as f:
                log = json.load(f)
        except (json.JSONDecodeError, OSError):
            log = []
    return [t for t in log if t > now - window]


def ip_gesperrt(ip, key, limit=5, window=3600):
    """True, wenn das Limit erreicht ist -- zaehlt NICHT mit (z. B. vor einer
    Pruefung, bei der nur Fehlversuche zaehlen sollen)."""
    return len(_log_lesen(_rate_datei(ip, key), window, time.time())) >= limit


def ip_erlaubt(ip, key, limit=5, window=3600):
    """True, wenn unter dem Limit — zählt die Anfrage dabei gleich mit."""
    os.makedirs(RATE_DIR, exist_ok=True)
    rate_file = _rate_datei(ip, key)
    now = time.time()
    log = _log_lesen(rate_file, window, now)

    if len(log) >= limit:
        return False

    log.append(now)
    with open(rate_file, 'w') as f:
        json.dump(log, f)
    return True
