"""
themen.py -- wissenschaftliche Themenraeume (Phase 2a, docs/austausch_phase2_plan.md).

Gemeinsamer Bereich fuer alle Berechtigten: Themengebiet -> Diskussion -> Beitrag.
Strikt getrennt vom vertraulichen fachlichen Austausch (omn/austausch.py): keine
Verbindung zu aufgabe/kommentar, eigene Routen (/themen...), eigenes Upload-
Verzeichnis (instance/uploads/themen/), eigene Berechtigung.

Schritt 1 (dieses Modul): Berechtigung, Texte im Original + Uebersetzungen lesen.
Seiten und Admin folgen in den naechsten Schritten.
"""
import hashlib

from flask import current_app

from omn.models import Uebersetzung

# Evidenz-Kennzeichnung je Beitrag (optional, Robby 25.10.2026)
ARTEN = ('hypothese', 'literatur', 'beobachtung', 'messdaten')
KREISE = ('fachkontakte', 'alle')


def darf_themenraeume_nutzen(nutzer):
    """Die EINE Pruefung fuer alle Themenraum-Routen und -Downloads.
    Haengt bewusst NIE an ist_hyphist, ist_sporist, Foerderung oder Zahlung.
    Kreis 'fachkontakte' (Start): wer einen aktiven fachlichen Austausch hat.
    Kreis 'alle' (Ziel): jeder bestaetigte Nutzer (Mycelists)."""
    if nutzer is None or not nutzer.bestaetigt:
        return False
    kreis = current_app.config.get('THEMEN_KREIS', 'fachkontakte')
    if kreis == 'alle':
        return True
    from omn.kollaboration import austausch_bereiche_von
    return bool(austausch_bereiche_von(nutzer))


def quelltext_hash(text):
    """Bindet eine Uebersetzung an genau eine Fassung des Originals. Muss mit
    _hash() in Migration 8be9ab181351 uebereinstimmen (Startgebiete)."""
    return hashlib.sha256((text or '').strip().encode('utf-8')).hexdigest()


def inhalt_typ(inhalt):
    return inhalt.__tablename__


def uebersetzung_holen(inhalt, feld, sprache):
    """Vorhandene Uebersetzung dieses Felds in `sprache` fuer die AKTUELLE
    Originalfassung, sonst None. Erzeugt nichts (automatisch erst ab Phase 2b)."""
    original = getattr(inhalt, feld) or ''
    if not original or sprache == inhalt.sprache_original:
        return None
    eintrag = Uebersetzung.query.filter_by(
        inhalt_typ=inhalt_typ(inhalt), inhalt_id=inhalt.id, feld=feld,
        ziel_sprache=sprache, quelltext_hash=quelltext_hash(original),
    ).first()
    return eintrag.text if eintrag else None


def anzeige(inhalt, feld, sprache):
    """Was die Seite zeigt: {'text', 'original', 'sprache_original', 'uebersetzt'}.
    Das Original ist IMMER dabei (Abschnitt 7.4: sofort erreichbar)."""
    original = getattr(inhalt, feld) or ''
    uebersetzt = uebersetzung_holen(inhalt, feld, sprache)
    return {
        'text': uebersetzt if uebersetzt is not None else original,
        'original': original,
        'sprache_original': inhalt.sprache_original,
        'uebersetzt': uebersetzt is not None,
    }


def uebersetzungen_loeschen(inhalt):
    """Beim Loeschen eines Inhalts mit aufrufen (kein echter FK auf uebersetzung)."""
    from omn.extensions import db
    n = (Uebersetzung.query.filter_by(inhalt_typ=inhalt_typ(inhalt), inhalt_id=inhalt.id)
         .delete(synchronize_session=False))
    db.session.flush()
    return n
