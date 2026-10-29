"""
vorwort.py -- persoenliches Vorwort des Initiators (Robby, 29.10.2026; docs/vorwort_plan.md).

EINE Seite /ueber-den-initiator (site_live, Website-Layout, Texte vorwort_* in
translations.json, 5 Sprachen, Porträt + Unterschrift):
- oeffentlich (Footer-Link "Über den Initiator"): nur lesen, nie Kenntnisnahme;
- im wissenschaftlichen Austausch: die Eingangs-Pruefung (pruefen()) schickt Personen, die
  die aktuelle Fassung noch nicht bestaetigt haben, mit ?kenntnisnahme=1 auf dieselbe Seite.
  Nur dann -- angemeldet, berechtigt, noch offen -- erscheint der Knopf "Gelesen – weiter" (kein
  Haken, Robby 29.10.2026); gespeichert wird ausschliesslich per POST /dashboard/vorwort (CSRF),
  nie durch blosses Aufrufen.
Neue Fassung (VORWORT_FASSUNG) nur bei wesentlicher Aenderung -> alle bestaetigen einmal neu.
Schalter VORWORT_AKTIV: Eingangs-Pruefung bis zur Freigabe des Datenschutz-Halbsatzes auf Prod aus.
"""
from datetime import datetime, timezone

from flask import current_app, redirect, request, url_for

from omn.extensions import db
from omn.models import VorwortKenntnis

VORWORT_FASSUNG = '2026-10-29'


def aktiv():
    return bool(current_app.config.get('VORWORT_AKTIV', False))


def absatz_keys():
    """vorwort_p01, vorwort_p02, ... -- so viele, wie die deutsche Fassung hat."""
    from omn.i18n import TRANSLATIONS
    return sorted(k for k in TRANSLATIONS['de'] if k.startswith('vorwort_p') and k[9:].isdigit())


def kenntnis(nutzer):
    """Bestaetigung der AKTUELLEN Fassung oder None."""
    k = nutzer.vorwort_kenntnis if nutzer is not None else None
    return k if k is not None and k.fassung == VORWORT_FASSUNG else None


def sicheres_ziel(weiter):
    """Nur Ziele im wissenschaftlichen Austausch (kein offener Redirect)."""
    if weiter and weiter.startswith(('/themen', '/austausch', '/dashboard')) and '//' not in weiter \
            and '\\' not in weiter:
        return weiter
    return url_for('dashboard.home')


def pruefen(nutzer, lang=None):
    """Eingangs-Pruefung vor Themenraeumen und Austausch: Redirect auf das Vorwort, wenn die
    aktuelle Fassung noch nicht bestaetigt ist, sonst None."""
    if not aktiv() or nutzer is None or kenntnis(nutzer) is not None:
        return None
    ziel = request.full_path.rstrip('?') if request.method == 'GET' else request.path
    return redirect(url_for('site_live.ueber_den_initiator', kenntnisnahme=1, weiter=ziel,
                            **({'lang': lang} if lang else {})))


def bestaetigen(nutzer):
    k = nutzer.vorwort_kenntnis
    if k is None:
        k = VorwortKenntnis(nutzer_id=nutzer.id, fassung=VORWORT_FASSUNG)
        db.session.add(k)
    k.fassung = VORWORT_FASSUNG
    k.gelesen_am = datetime.now(timezone.utc)
    db.session.commit()
