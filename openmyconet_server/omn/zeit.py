"""
zeit.py — einzige Quelle fuer "jetzt" im Backend.

datetime.utcnow() ist seit Python 3.12 deprecated (wird in einer kuenftigen
Version entfernt); der empfohlene Ersatz datetime.now(timezone.utc) liefert
aber ein *tz-aware* Objekt. Alle Zeitstempel dieser App sind bisher naiv, aber
implizit UTC, in SQLite gespeichert (das kennt keinen Zeitzonen-Typ) -- ein
Wechsel auf echte tz-aware Werte wuerde ueberall dort, wo mit einer aus der DB
gelesenen Zeit verglichen wird (Token-Ablauf in dashboard.py, Rechnungsjahr
und Verfallspruefung in foerderer*.py, Aufgaben-Zeitstempel in
kollaboration.py), "TypeError: can't compare offset-naive and offset-aware
datetimes" ausloesen -- und braeuchte eine Migration aller ~15
Zeitstempel-Spalten, ohne echten Nutzen: die App rechnet ausschliesslich in
UTC/Europe-Berlin-Kontext und zeigt nirgends mehrere Zeitzonen an.

utcnow() hier liefert deshalb bewusst weiter ein naives datetime -- exakt das
gleiche Verhalten wie das bisherige datetime.utcnow(), nur ohne die
Deprecation-Warnung und ohne Migrationsrisiko.
"""
from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)
