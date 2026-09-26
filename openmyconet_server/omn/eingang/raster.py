"""MGRS-Rasterfeld (10 km) aus Breite/Laenge -- fuer das Anlegen von Standorten.

Oeffentlich gespeichert wird von einem Standort nur das 10-km-Rasterfeld
(site.grid_cell_id, z. B. "32UNB00"); die exakten Koordinaten gehoeren nach
<schema>_private und duerfen nur von der Rolle omn_geo geschrieben werden. Die
Admin-Maske rechnet deshalb hier um und verwirft die Koordinaten danach.

Reine Python-Rechnung (WGS84, UTM nach Krueger-Reihe, MGRS-Buchstaben nach dem
AA-Schema), ohne Zusatzbibliothek. Geprueft gegen die vier Sandbox-Standorte
(damals mit mgrs + pyproj gegengeprueft) und Referenzpunkte in
tests/test_admin_biocomm.py. Polargebiete (UPS, Breite < -80 oder > 84) sind
nicht abgedeckt -> ValueError.
"""
import math

_A = 6378137.0
_F = 1 / 298.257223563
_K0 = 0.9996
_E2 = _F * (2 - _F)
_EP2 = _E2 / (1 - _E2)
_BAENDER = 'CDEFGHJKLMNPQRSTUVWX'
_SPALTEN = ('ABCDEFGH', 'JKLMNPQR', 'STUVWXYZ')
_ZEILEN = 'ABCDEFGHJKLMNPQRSTUV'


def _utm_zone(breite, laenge):
    zone = int((laenge + 180) // 6) + 1
    if zone > 60:
        zone = 60
    if 56 <= breite < 64 and 3 <= laenge < 12:
        zone = 32                                   # Suedwestnorwegen
    if 72 <= breite < 84:                           # Spitzbergen
        for von, bis, z in ((0, 9, 31), (9, 21, 33), (21, 33, 35), (33, 42, 37)):
            if von <= laenge < bis:
                zone = z
    return zone


def utm(breite, laenge):
    """(Zone, Rechtswert, Hochwert) in Metern."""
    zone = _utm_zone(breite, laenge)
    phi = math.radians(breite)
    lam = math.radians(laenge)
    lam0 = math.radians((zone - 1) * 6 - 180 + 3)
    n = _A / math.sqrt(1 - _E2 * math.sin(phi) ** 2)
    t = math.tan(phi) ** 2
    c = _EP2 * math.cos(phi) ** 2
    a = math.cos(phi) * (lam - lam0)
    e2, e4, e6 = _E2, _E2 ** 2, _E2 ** 3
    m = _A * ((1 - e2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * phi
              - (3 * e2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * phi)
              + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * phi)
              - (35 * e6 / 3072) * math.sin(6 * phi))
    rechts = _K0 * n * (a + (1 - t + c) * a ** 3 / 6
                        + (5 - 18 * t + t ** 2 + 72 * c - 58 * _EP2) * a ** 5 / 120) + 500000.0
    hoch = _K0 * (m + n * math.tan(phi) * (a ** 2 / 2 + (5 - t + 9 * c + 4 * c ** 2) * a ** 4 / 24
                                          + (61 - 58 * t + t ** 2 + 600 * c - 330 * _EP2) * a ** 6 / 720))
    if breite < 0:
        hoch += 10000000.0
    return zone, rechts, hoch


def mgrs_10km(breite, laenge):
    """MGRS-Kennung mit 10-km-Genauigkeit, z. B. '32UNB00'."""
    breite, laenge = float(breite), float(laenge)
    if not (-80 <= breite <= 84):
        raise ValueError('Breite muss zwischen -80 und 84 Grad liegen (Polargebiete werden nicht unterstützt)')
    if not (-180 <= laenge <= 180):
        raise ValueError('Länge muss zwischen -180 und 180 Grad liegen')
    zone, rechts, hoch = utm(breite, laenge)
    band = _BAENDER[min(int((breite + 80) // 8), len(_BAENDER) - 1)]
    spalte = _SPALTEN[(zone - 1) % 3][int(rechts // 100000) - 1]
    zeile = _ZEILEN[(int(hoch // 100000) + (5 if zone % 2 == 0 else 0)) % 20]
    return f'{zone}{band}{spalte}{zeile}{int(rechts % 100000 // 10000)}{int(hoch % 100000 // 10000)}'
