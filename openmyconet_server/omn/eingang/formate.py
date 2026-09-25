"""Welches Paketformat liegt vor? Einzige Weiche zwischen den Formaten.

- v1 (omn/eingang/format_v1.py): Binaerpaket mit Kennung b'OMNB', Datei *.omb.
  Das Format der Node-Firmware (C4, festgelegt am 25.09.2026).
- v0 (omn/eingang/format_v0.py): vorlaeufiges JSON-Format des Prototyps, Datei
  *.json. Bleibt lesbar (Tests, Testknoten, Altdaten).

Beide liefern Paket-Objekte mit denselben Feldern; formatabhaengig sind nur
`paket.format` (Kennung, landet in origin_batch.payload_format), `genesis()`
(Kettenanfang) und `batch_hash_ist()`.
"""
from omn.eingang import format_v0, format_v1
from omn.eingang.format_v0 import PaketUnlesbar  # noqa: F401  (Weitergabe fuer Aufrufer)

DATEIENDUNGEN = ('*.omb', '*.json')
KENNUNGEN = (format_v0.FORMAT_KENNUNG, format_v1.FORMAT_KENNUNG)


def paket_lesen(rohdaten):
    """bytes -> Paket (v0 oder v1). Wirft PaketUnlesbar."""
    if rohdaten[:4] == format_v1.MAGIC:
        return format_v1.paket_lesen(rohdaten)
    return format_v0.paket_lesen(rohdaten)


def paket_schreiben(paket):
    """Paket -> bytes im eigenen Format des Pakets."""
    if paket.format == format_v1.FORMAT_KENNUNG:
        return format_v1.paket_schreiben(paket)
    return format_v0.paket_schreiben(paket)
