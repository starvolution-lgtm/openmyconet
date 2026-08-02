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


def ip_erlaubt(ip, key, limit=5, window=3600):
    """True, wenn unter dem Limit — zählt die Anfrage dabei gleich mit."""
    os.makedirs(RATE_DIR, exist_ok=True)
    ip = re.sub(r'[^a-fA-F0-9:.]', '', ip or '0')
    rate_file = os.path.join(RATE_DIR, hashlib.md5(f'{ip}_{key}'.encode()).hexdigest() + '.json')

    now = time.time()
    log = []
    if os.path.exists(rate_file):
        try:
            with open(rate_file, 'r') as f:
                log = json.load(f)
        except (json.JSONDecodeError, OSError):
            log = []
    log = [t for t in log if t > now - window]

    if len(log) >= limit:
        return False

    log.append(now)
    with open(rate_file, 'w') as f:
        json.dump(log, f)
    return True
