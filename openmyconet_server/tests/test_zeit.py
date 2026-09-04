"""Testet zeit.utcnow() -- der Ersatz fuer das deprecated datetime.utcnow()
im ganzen Backend (models.py-Defaults, Token-Ablauf, Rechnungsjahr, Verfalls-
pruefung). Muss weiterhin ein naives, aber korrektes UTC-Datetime liefern."""
from datetime import datetime, timedelta, timezone

from zeit import utcnow


def test_liefert_naives_datetime():
    assert utcnow().tzinfo is None


def test_entspricht_der_echten_utc_zeit():
    referenz = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs(utcnow() - referenz) < timedelta(seconds=2)
