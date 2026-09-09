"""Admin-Panel — ein gemeinsamer Blueprint `admin_bp`, aufgeteilt in Fachmodule.

`core` haelt den Blueprint, den kanonischen-Host-Redirect, den CSRF-Schutz und
die geteilten Decorators. Jedes Fachmodul haengt seine Routen an `admin_bp`;
sie muessen deshalb hier importiert werden, damit die `@admin_bp.route`-
Dekoratoren beim App-Start laufen.

`omn/__init__.py` importiert nur `admin_bp` von hier; `omn/kontrollzentrum.py`
nur `role_required`; die Tests greifen `sanitize_news_html` ab.
"""
from omn.admin.core import admin_bp, role_required
from omn.admin import (  # noqa: F401  -- Import registriert die Routen
    auth,
    foerderer,
    inhalte,
    knoten,
    news,
    presse,
    uebersicht,
    wartung,
)
from omn.admin.news import sanitize_news_html  # Re-Export fuer die Tests

__all__ = ['admin_bp', 'role_required', 'sanitize_news_html']
