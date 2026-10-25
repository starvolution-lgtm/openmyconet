"""
themen.py -- wissenschaftliche Themenraeume (Phase 2a, docs/austausch_phase2_plan.md).

Gemeinsamer Bereich fuer alle Berechtigten: Themengebiet -> Diskussion -> Beitrag.
Strikt getrennt vom vertraulichen fachlichen Austausch (omn/austausch.py): keine
Verbindung zu aufgabe/kommentar, eigene Routen (/themen...), eigenes Upload-
Verzeichnis (instance/uploads/themen/), eigene Berechtigung (darf_themenraeume_nutzen).

Texte werden IMMER im Original gespeichert (+ sprache_original, gewaehlt beim
Schreiben, vorbelegt mit der Website-Sprache). Andere Sprachen kommen aus
Uebersetzung (in 2a nur die Handuebersetzungen der 6 Startgebiete; automatisch ab 2b).
Beitraege sind Klartext; Links werden beim Anzeigen klickbar (verlinken), kein HTML.

Seitentexte ohne direkte Anrede (Sie/du ist fuer die Themenraeume noch offen).
Moderation (Ausblenden, Zusammenfuehren, Schliessen) liegt im Admin (Schritt 4).
"""
import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Blueprint, abort, current_app, flash, make_response, redirect, render_template, request, send_file, url_for,
)
from markupsafe import Markup, escape

from omn import kollaboration
from omn.csrf import schuetze_blueprint
from omn.extensions import db
from omn.i18n import LANGS, SPRACHNAMEN, t
from omn.models import Beitrag, BeitragAnhang, Diskussion, ThemenTeilnahme, Themengebiet, Uebersetzung
from omn.spam_schutz import ip_erlaubt

# Evidenz-Kennzeichnung je Beitrag (optional, Robby 25.10.2026)
ARTEN = ('hypothese', 'literatur', 'beobachtung', 'messdaten')
KREISE = ('fachkontakte', 'alle')
# Fassung der Nutzungsregeln; bei Aenderung erhoehen -> alle stimmen beim naechsten Besuch neu zu
REGELN_FASSUNG = '2026-10-25'
UPLOAD_ORDNER = 'themen'
TITEL_MAX = 200
BESCHREIBUNG_MAX = 500
TEXT_MAX = 20000

themen_bp = Blueprint('themen', __name__)
schuetze_blueprint(themen_bp)


# --- Berechtigung -------------------------------------------------------------

def themen_freigegeben():
    """Schalter bis zur rechtlichen Freigabe (Config THEMEN_FREIGEGEBEN): auf Prod
    zunaechst aus -> alle /themen-Routen 404, kein Link in Navigation und Austausch."""
    return bool(current_app.config.get('THEMEN_FREIGEGEBEN', False))


def darf_themenraeume_nutzen(nutzer):
    """Die EINE Pruefung fuer alle Themenraum-Routen und -Downloads.
    Haengt bewusst NIE an ist_hyphist, ist_sporist, Foerderung oder Zahlung.
    Kreis 'fachkontakte' (Start): wer einen aktiven fachlichen Austausch hat.
    Kreis 'alle' (Ziel): jeder bestaetigte Nutzer (Mycelists)."""
    if not themen_freigegeben() or nutzer is None or not nutzer.bestaetigt:
        return False
    kreis = current_app.config.get('THEMEN_KREIS', 'fachkontakte')
    if kreis == 'alle':
        return True
    return bool(kollaboration.austausch_bereiche_von(nutzer))


@themen_bp.app_context_processor
def _vorlagen_helfer():
    return {'themen_zugang': darf_themenraeume_nutzen}


# --- Original + Uebersetzung ---------------------------------------------------

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
    Das Original ist IMMER dabei (Plan 7.4: sofort erreichbar)."""
    original = getattr(inhalt, feld) or ''
    uebersetzt = uebersetzung_holen(inhalt, feld, sprache)
    return {
        'text': uebersetzt if uebersetzt is not None else original,
        'original': original,
        'sprache_original': inhalt.sprache_original,
        'uebersetzt': uebersetzt is not None,
    }


def uebersetzungen_loeschen(inhalt):
    """Beim Loeschen/Entfernen eines Inhalts mit aufrufen (kein echter FK)."""
    n = (Uebersetzung.query.filter_by(inhalt_typ=inhalt_typ(inhalt), inhalt_id=inhalt.id)
         .delete(synchronize_session=False))
    db.session.flush()
    return n


_URL = re.compile(r'https?://[^\s<>"\']+')


@themen_bp.app_template_filter('verlinken')
def verlinken(text):
    """Klartext sicher anzeigen: alles escapen, danach http(s)-Adressen klickbar
    machen (rel=nofollow, neues Fenster). Satzzeichen am Ende gehoeren nicht zum Link."""
    teile, pos = [], 0
    for m in _URL.finditer(text or ''):
        url = m.group(0).rstrip('.,;:!?)')
        ende = m.start() + len(url)
        teile.append(escape(text[pos:m.start()]))
        teile.append(Markup('<a href="{0}" rel="nofollow noopener noreferrer" target="_blank">{0}</a>').format(url))
        pos = ende
    teile.append(escape((text or '')[pos:]))
    return Markup('').join(teile)


# --- Aehnliche Themen (Plan 8: vor dem Anlegen zeigen, ohne KI) --------------------

# Haeufige Woerter (ab 4 Buchstaben) in den 5 Sprachen, die nichts ueber das Thema sagen
_FUELLWOERTER = {
    'eine', 'einer', 'eines', 'einem', 'einen', 'und', 'oder', 'aber', 'auch', 'nicht', 'sind', 'wird', 'werden',
    'kann', 'koennen', 'mit', 'ohne', 'fuer', 'ueber', 'unter', 'zwischen', 'durch', 'beim', 'diese', 'dieser',
    'dieses', 'sowie', 'frage', 'fragen', 'thema', 'with', 'from', 'that', 'this', 'there', 'their', 'about',
    'between', 'during', 'could', 'would', 'should', 'have', 'into', 'what', 'which', 'question', 'topic',
    'voor', 'zijn', 'wordt', 'deze', 'naar', 'over', 'tussen', 'tijdens', 'avec', 'dans', 'pour', 'sont', 'entre',
    'pendant', 'sujet', 'como', 'para', 'durante', 'sobre', 'esta', 'este', 'tema',
}


def _normalisieren(text):
    """Kleinschreibung, Akzente/Umlaute weg (ae/oe/ue), grobe Lautangleichung
    (c->k, ph->f, th->t, y->i), damit z. B. 'Mykorrhiza', 'mycorrhiza' und
    'mycorhize' zusammenfinden."""
    text = (text or '').lower()
    for a, b in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')):
        text = text.replace(a, b)
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    for a, b in (('ph', 'f'), ('th', 't'), ('c', 'k'), ('y', 'i')):
        text = text.replace(a, b)
    return re.sub(r'(.)\1+', r'\1', text)   # Doppelbuchstaben zusammenziehen (rr -> r)


STAMM_LAENGE = 6


def _stamm(wort):
    """Grober Wortstamm fuer 5 Sprachen: die ersten 6 Zeichen ('elektrische',
    'electrical' -> 'elektr'; 'mykorrhiza', 'mycorhize' -> 'mikorh')."""
    return wort[:STAMM_LAENGE]


def woerter(text):
    """Aussagekraeftige Wortstaemme eines Texts (ab 4 Buchstaben, ohne Fuellwoerter)."""
    roh = re.findall(r'[a-z0-9]+', _normalisieren(text))
    fuell = {_normalisieren(w) for w in _FUELLWOERTER}
    return {_stamm(w) for w in roh if len(w) >= 4 and w not in fuell}


def _alle_fassungen(inhalt):
    """Original + vorhandene Uebersetzungen von Titel und Beschreibung."""
    texte = [inhalt.titel, inhalt.beschreibung]
    texte += [u.text for u in Uebersetzung.query.filter_by(inhalt_typ=inhalt_typ(inhalt), inhalt_id=inhalt.id)]
    return ' '.join(texte)


def aehnliche(titel, beschreibung, kandidaten, hoechstens=5):
    """Bis zu `hoechstens` aehnliche Gebiete/Diskussionen, aehnlichste zuerst. Treffer,
    wenn ein Wortstamm des neuen Titels vorkommt oder mindestens ein Viertel aller
    Wortstaemme uebereinstimmt -- grob, aber ohne KI, Kosten oder Datenweitergabe."""
    titel_w = woerter(titel)
    alle_w = titel_w | woerter(beschreibung)
    if not alle_w:
        return []
    treffer = []
    for k in kandidaten:
        k_w = woerter(_alle_fassungen(k))
        gemeinsam = alle_w & k_w
        anteil = len(gemeinsam) / len(alle_w)
        if (titel_w & k_w) or anteil >= 0.25:
            treffer.append((len(titel_w & k_w), anteil, k))
    treffer.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [k for _, _, k in treffer[:hoechstens]]


# --- Hilfen ---------------------------------------------------------------------

def jetzt():
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def anzeigename(beitrag_oder_ersteller, lang):
    """Name eines Verfassers: Team, ehemaliges Mitglied oder der frei gewaehlte Anzeigename."""
    von_team = getattr(beitrag_oder_ersteller, 'von_team', False)
    nutzer = getattr(beitrag_oder_ersteller, 'autor', None) or getattr(beitrag_oder_ersteller, 'ersteller', None)
    if von_team:
        return t('austausch_von_team', lang)
    if nutzer is None:
        return t('themen_ehemalig', lang)
    teilnahme = nutzer.themen_teilnahme
    return teilnahme.anzeigename if teilnahme else nutzer.name


def _sprache_aus_formular(lang):
    s = request.form.get('sprache')
    return s if s in LANGS else lang


def _sicheres_ziel(weiter):
    if weiter and weiter.startswith('/themen') and '//' not in weiter and '\\' not in weiter:
        return weiter
    return url_for('themen.uebersicht')


def _seite(vorlage, lang, status=200, **kw):
    from omn.datenlabor import ui_texte
    html = render_template(
        vorlage, lang=lang, T=ui_texte(lang), sprachen=SPRACHNAMEN, arten=ARTEN,
        tx=lambda k, **w: _einsetzen(t(k, lang), w), name_von=lambda x: anzeigename(x, lang),
        **kw,
    )
    antwort = make_response(html, status)
    antwort.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return antwort


def _einsetzen(text, werte):
    for k, v in werte.items():
        text = text.replace('{' + k + '}', str(v))
    return text


def zugang(f):
    """Eingeloggt + bestaetigt + berechtigt + Nutzungsregeln (aktuelle Fassung)
    zugestimmt. Uebergibt (nutzer, teilnahme, lang)."""
    @wraps(f)
    def innen(*args, **kwargs):
        from omn.datenlabor import _nutzer, seiten_sprache
        if not themen_freigegeben():
            abort(404)
        nutzer = _nutzer()
        if nutzer is None:
            return redirect(url_for('dashboard.login'))
        lang = seiten_sprache(nutzer)
        if not darf_themenraeume_nutzen(nutzer):
            return _seite('themen_kein_zugang.html', lang, status=403, nutzer=nutzer)
        teilnahme = nutzer.themen_teilnahme
        if teilnahme is None or teilnahme.regeln_fassung != REGELN_FASSUNG:
            return redirect(url_for('themen.teilnahme', weiter=request.path))
        return f(nutzer, teilnahme, lang, *args, **kwargs)
    return innen


def _schreiben_erlaubt(nutzer):
    return ip_erlaubt(f'nutzer-{nutzer.id}', 'themen_schreiben', limit=60, window=3600)


def _gebiet_oder_404(gebiet_id):
    g = db.session.get(Themengebiet, gebiet_id)
    if g is None or (not g.sichtbar and g.zusammengefuehrt_in is None):
        abort(404)
    return g


def _diskussion_oder_404(diskussion_id):
    d = db.session.get(Diskussion, diskussion_id)
    if d is None or not d.sichtbar or not d.themengebiet.sichtbar:
        abort(404)
    return d


# --- Teilnahme + Einstellungen --------------------------------------------------

@themen_bp.route('/themen/teilnahme', methods=['GET', 'POST'])
def teilnahme():
    from omn.datenlabor import _nutzer, seiten_sprache
    if not themen_freigegeben():
        abort(404)
    nutzer = _nutzer()
    if nutzer is None:
        return redirect(url_for('dashboard.login'))
    lang = seiten_sprache(nutzer)
    if not darf_themenraeume_nutzen(nutzer):
        return _seite('themen_kein_zugang.html', lang, status=403, nutzer=nutzer)
    vorhanden = nutzer.themen_teilnahme
    weiter = request.values.get('weiter')
    fehler = []
    name = (vorhanden.anzeigename if vorhanden else nutzer.name) or ''
    if request.method == 'POST':
        name = ' '.join((request.form.get('anzeigename') or '').split())[:100]
        if not name:
            fehler.append(t('themen_anzeigename_fehlt', lang))
        if not request.form.get('regeln'):
            fehler.append(t('themen_regeln_noetig', lang))
        if not fehler:
            if vorhanden is None:
                vorhanden = ThemenTeilnahme(nutzer_id=nutzer.id, anzeigename=name)
                db.session.add(vorhanden)
            vorhanden.anzeigename = name
            vorhanden.regeln_fassung = REGELN_FASSUNG
            vorhanden.regeln_akzeptiert_am = jetzt()
            db.session.commit()
            return redirect(_sicheres_ziel(weiter))
    return _seite('themen_teilnahme.html', lang, nutzer=nutzer, anzeigename_wert=name, fehler=fehler,
                  weiter=weiter or '', erneut=vorhanden is not None)


@themen_bp.route('/themen/einstellungen', methods=['GET', 'POST'])
@zugang
def einstellungen(nutzer, teilnahme, lang):
    fehler = []
    if request.method == 'POST':
        name = ' '.join((request.form.get('anzeigename') or '').split())[:100]
        if not name:
            fehler.append(t('themen_anzeigename_fehlt', lang))
        else:
            teilnahme.anzeigename = name
            teilnahme.original_zuerst = bool(request.form.get('original_zuerst'))
            db.session.commit()
            flash(t('themen_einstellungen_gespeichert', lang))
            return redirect(url_for('themen.einstellungen'))
    return _seite('themen_einstellungen.html', lang, nutzer=nutzer, teilnahme=teilnahme, fehler=fehler)


# --- Uebersicht, Gebiet, Diskussion ---------------------------------------------

@themen_bp.route('/themen')
@zugang
def uebersicht(nutzer, teilnahme, lang):
    """Alle sichtbaren Gebiete (vorgegebene oben). 'Neu seit dem letzten Besuch'
    zaehlt Diskussionen mit Aktivitaet seit dem vorigen Aufruf dieser Seite."""
    vorher = _aware(teilnahme.zuletzt_gesehen)
    gebiete = (Themengebiet.query.filter_by(sichtbar=True)
               .order_by(Themengebiet.vorgegeben.desc(), Themengebiet.reihenfolge, Themengebiet.titel).all())
    zeilen = []
    for g in gebiete:
        diskussionen = [d for d in g.diskussionen if d.sichtbar]
        letzte = max((_aware(d.letzte_aktivitaet) for d in diskussionen), default=None)
        neu = sum(1 for d in diskussionen if vorher and _aware(d.letzte_aktivitaet) > vorher
                  and d.erstellt_von != nutzer.id)
        zeilen.append({'g': g, 'titel': anzeige(g, 'titel', lang), 'beschreibung': anzeige(g, 'beschreibung', lang),
                       'anzahl': len(diskussionen), 'neu': neu, 'letzte': letzte})
    teilnahme.zuletzt_gesehen = jetzt()
    db.session.commit()
    return _seite('themen_uebersicht.html', lang, nutzer=nutzer, teilnahme=teilnahme, zeilen=zeilen)


def _formular_lesen(lang):
    titel = ' '.join((request.form.get('titel') or '').split())[:TITEL_MAX]
    beschreibung = (request.form.get('beschreibung') or '').strip()[:BESCHREIBUNG_MAX]
    fehler = [] if titel and beschreibung else [t('themen_pflicht_titel_beschreibung', lang)]
    return titel, beschreibung, _sprache_aus_formular(lang), fehler


@themen_bp.route('/themen/gebiet/neu', methods=['GET', 'POST'])
@zugang
def gebiet_neu(nutzer, teilnahme, lang):
    titel = beschreibung = ''
    sprache = lang
    fehler = []
    if request.method == 'POST':
        titel, beschreibung, sprache, fehler = _formular_lesen(lang)
        if not fehler and not request.form.get('trotzdem'):
            kandidaten = Themengebiet.query.filter_by(sichtbar=True).all()
            treffer = aehnliche(titel, beschreibung, kandidaten)
            if treffer:
                return _seite('themen_formular.html', lang, nutzer=nutzer, art_formular='gebiet', titel_wert=titel,
                              beschreibung_wert=beschreibung, sprache_wert=sprache, fehler=[], gebiet=None,
                              treffer=[{'ziel': url_for('themen.gebiet', gebiet_id=k.id),
                                        'titel': anzeige(k, 'titel', lang),
                                        'beschreibung': anzeige(k, 'beschreibung', lang)} for k in treffer])
        if not fehler and not _schreiben_erlaubt(nutzer):
            fehler = [t('themen_zu_viele', lang)]
        if not fehler:
            g = Themengebiet(titel=titel, beschreibung=beschreibung, sprache_original=sprache, erstellt_von=nutzer.id)
            db.session.add(g)
            db.session.commit()
            return redirect(url_for('themen.gebiet', gebiet_id=g.id))
    return _seite('themen_formular.html', lang, nutzer=nutzer, art_formular='gebiet', titel_wert=titel,
                  beschreibung_wert=beschreibung, sprache_wert=sprache, fehler=fehler, gebiet=None)


@themen_bp.route('/themen/gebiet/<int:gebiet_id>')
@zugang
def gebiet(nutzer, teilnahme, lang, gebiet_id):
    g = _gebiet_oder_404(gebiet_id)
    if g.zusammengefuehrt_in:
        return redirect(url_for('themen.gebiet', gebiet_id=g.zusammengefuehrt_in), code=301)
    diskussionen = sorted((d for d in g.diskussionen if d.sichtbar),
                          key=lambda d: _aware(d.letzte_aktivitaet), reverse=True)
    zeilen = [{'d': d, 'titel': anzeige(d, 'titel', lang), 'beschreibung': anzeige(d, 'beschreibung', lang),
               'anzahl': sum(1 for b in d.beitraege if b.sichtbar)} for d in diskussionen]
    return _seite('themen_gebiet.html', lang, nutzer=nutzer, teilnahme=teilnahme, g=g,
                  titel=anzeige(g, 'titel', lang), beschreibung=anzeige(g, 'beschreibung', lang), zeilen=zeilen)


@themen_bp.route('/themen/gebiet/<int:gebiet_id>/diskussion/neu', methods=['GET', 'POST'])
@zugang
def diskussion_neu(nutzer, teilnahme, lang, gebiet_id):
    g = _gebiet_oder_404(gebiet_id)
    if g.zusammengefuehrt_in:
        return redirect(url_for('themen.diskussion_neu', gebiet_id=g.zusammengefuehrt_in))
    titel = beschreibung = ''
    sprache = lang
    fehler = []
    if request.method == 'POST':
        titel, beschreibung, sprache, fehler = _formular_lesen(lang)
        if not fehler and not request.form.get('trotzdem'):
            kandidaten = [d for d in g.diskussionen if d.sichtbar]
            treffer = aehnliche(titel, beschreibung, kandidaten)
            if treffer:
                return _seite('themen_formular.html', lang, nutzer=nutzer, art_formular='diskussion',
                              titel_wert=titel, beschreibung_wert=beschreibung, sprache_wert=sprache, fehler=[],
                              gebiet=g, gebiet_titel=anzeige(g, 'titel', lang),
                              treffer=[{'ziel': url_for('themen.diskussion', diskussion_id=k.id),
                                        'titel': anzeige(k, 'titel', lang),
                                        'beschreibung': anzeige(k, 'beschreibung', lang)} for k in treffer])
        if not fehler and not _schreiben_erlaubt(nutzer):
            fehler = [t('themen_zu_viele', lang)]
        if not fehler:
            d = Diskussion(themengebiet_id=g.id, titel=titel, beschreibung=beschreibung, sprache_original=sprache,
                           erstellt_von=nutzer.id)
            db.session.add(d)
            db.session.commit()
            return redirect(url_for('themen.diskussion', diskussion_id=d.id))
    return _seite('themen_formular.html', lang, nutzer=nutzer, art_formular='diskussion', titel_wert=titel,
                  beschreibung_wert=beschreibung, sprache_wert=sprache, fehler=fehler, gebiet=g,
                  gebiet_titel=anzeige(g, 'titel', lang))


def _beitrag_ansicht(b, lang):
    return {'b': b, 'text': anzeige(b, 'text', lang), 'name': anzeigename(b, lang),
            'anhaenge': [a for a in b.anhaenge]}


@themen_bp.route('/themen/diskussion/<int:diskussion_id>', methods=['GET', 'POST'])
@zugang
def diskussion(nutzer, teilnahme, lang, diskussion_id):
    d = _diskussion_oder_404(diskussion_id)
    fehler = []
    if request.method == 'POST':
        if d.geschlossen:
            abort(403)
        text = (request.form.get('text') or '').strip()[:TEXT_MAX]
        art = request.form.get('art') if request.form.get('art') in ARTEN else None
        antwort_auf = request.form.get('antwort_auf', type=int)
        if antwort_auf:
            eltern = db.session.get(Beitrag, antwort_auf)
            if eltern is None or eltern.diskussion_id != d.id:
                abort(403)
            antwort_auf = eltern.antwort_auf or eltern.id   # nur eine Ebene
        if not text:
            fehler.append(t('themen_leer', lang))
        elif not _schreiben_erlaubt(nutzer):
            fehler.append(t('themen_zu_viele', lang))
        else:
            b = Beitrag(diskussion_id=d.id, antwort_auf=antwort_auf or None, autor_nutzer_id=nutzer.id, text=text,
                        art=art, sprache_original=_sprache_aus_formular(lang))
            db.session.add(b)
            db.session.flush()
            for datei in request.files.getlist('dateien'):
                if not datei or not datei.filename:
                    continue
                abgelegt = kollaboration.datei_ablegen(datei, UPLOAD_ORDNER)
                if abgelegt is None:
                    fehler.append(t('austausch_fehler_anhang', lang).replace('{datei}', datei.filename))
                    continue
                dateiname, originalname, groesse = abgelegt
                db.session.add(BeitragAnhang(beitrag_id=b.id, dateiname=dateiname, originalname=originalname,
                                             groesse=groesse))
            d.letzte_aktivitaet = jetzt()
            db.session.commit()
            flash(t('themen_gespeichert', lang))
            if fehler:
                flash(' '.join(fehler), 'error')
            return redirect(url_for('themen.diskussion', diskussion_id=d.id) + f'#beitrag-{b.id}')

    sichtbar = [b for b in d.beitraege if b.sichtbar]
    oben = sorted((b for b in sichtbar if b.antwort_auf is None), key=lambda b: _aware(b.erstellt_am))
    antworten = {}
    for b in sorted((b for b in sichtbar if b.antwort_auf is not None), key=lambda b: _aware(b.erstellt_am)):
        antworten.setdefault(b.antwort_auf, []).append(_beitrag_ansicht(b, lang))
    faden = [{**_beitrag_ansicht(b, lang), 'antworten': antworten.get(b.id, [])} for b in oben]
    # Antworten auf ausgeblendete/geloeschte Beitraege nicht verlieren: ans Ende haengen
    oben_ids = {b.id for b in oben}
    for eltern_id, liste in antworten.items():
        if eltern_id not in oben_ids:
            faden.extend({**x, 'antworten': []} for x in liste)
    return _seite('themen_diskussion.html', lang, nutzer=nutzer, teilnahme=teilnahme, d=d,
                  titel=anzeige(d, 'titel', lang), beschreibung=anzeige(d, 'beschreibung', lang),
                  gebiet_titel=anzeige(d.themengebiet, 'titel', lang), faden=faden, fehler=fehler)


# --- Eigene Beitraege bearbeiten / entfernen -------------------------------------

def _eigener_beitrag(nutzer, beitrag_id):
    b = db.session.get(Beitrag, beitrag_id)
    if b is None or b.autor_nutzer_id != nutzer.id or b.entfernt_am is not None or not b.sichtbar:
        abort(403)
    if b.diskussion.geschlossen:
        abort(403)
    return b


@themen_bp.route('/themen/beitrag/<int:beitrag_id>/bearbeiten', methods=['GET', 'POST'])
@zugang
def beitrag_bearbeiten(nutzer, teilnahme, lang, beitrag_id):
    b = _eigener_beitrag(nutzer, beitrag_id)
    fehler = []
    if request.method == 'POST':
        text = (request.form.get('text') or '').strip()[:TEXT_MAX]
        if not text:
            fehler.append(t('themen_leer', lang))
        else:
            if text != b.text:
                uebersetzungen_loeschen(b)   # passten ohnehin nicht mehr (Hash)
                b.text = text
                b.bearbeitet_am = jetzt()
            b.art = request.form.get('art') if request.form.get('art') in ARTEN else None
            b.sprache_original = _sprache_aus_formular(b.sprache_original)
            db.session.commit()
            return redirect(url_for('themen.diskussion', diskussion_id=b.diskussion_id) + f'#beitrag-{b.id}')
    return _seite('themen_bearbeiten.html', lang, nutzer=nutzer, b=b, fehler=fehler)


def beitrag_entfernen(b):
    """Text weg, Anhaenge + Dateien + Uebersetzungen weg; die Zeile bleibt als
    Platzhalter, damit Antworten anderer verstaendlich bleiben. Committet selbst."""
    pfade = [kollaboration.anhang_pfad_in(a.dateiname, UPLOAD_ORDNER) for a in b.anhaenge]
    for a in list(b.anhaenge):
        db.session.delete(a)
    uebersetzungen_loeschen(b)
    b.text = ''
    b.art = None
    b.entfernt_am = jetzt()
    db.session.commit()
    kollaboration.dateien_entfernen(pfade)


def _pfade_und_uebersetzungen(beitraege):
    pfade = []
    for b in beitraege:
        pfade += [kollaboration.anhang_pfad_in(a.dateiname, UPLOAD_ORDNER) for a in b.anhaenge]
        uebersetzungen_loeschen(b)
    return pfade


def beitrag_loeschen(b):
    """Admin: Beitrag endgueltig loeschen (Zeile, Anhaenge, Dateien, Uebersetzungen).
    Antworten darauf bleiben (antwort_auf -> NULL) und stehen dann am Ende des Fadens."""
    for antwort in Beitrag.query.filter_by(antwort_auf=b.id):
        antwort.antwort_auf = None
    pfade = _pfade_und_uebersetzungen([b])
    db.session.delete(b)
    db.session.commit()
    return kollaboration.dateien_entfernen(pfade)


def diskussion_loeschen(d):
    """Admin: Diskussion samt aller Beitraege, Anhaenge, Dateien und Uebersetzungen."""
    pfade = _pfade_und_uebersetzungen(d.beitraege)
    uebersetzungen_loeschen(d)
    db.session.delete(d)
    db.session.commit()
    return kollaboration.dateien_entfernen(pfade)


def gebiet_loeschen(g):
    """Admin: Themengebiet samt aller Diskussionen (siehe diskussion_loeschen).
    Verweise anderer Gebiete, die hierher zusammengefuehrt wurden, werden geloest."""
    pfade = []
    for d in g.diskussionen:
        pfade += _pfade_und_uebersetzungen(d.beitraege)
        uebersetzungen_loeschen(d)
    for alt in Themengebiet.query.filter_by(zusammengefuehrt_in=g.id):
        alt.zusammengefuehrt_in = None
    uebersetzungen_loeschen(g)
    db.session.delete(g)
    db.session.commit()
    return kollaboration.dateien_entfernen(pfade)


def gebiet_zusammenfuehren(quelle, ziel):
    """Admin: alle Diskussionen von `quelle` nach `ziel`; die Quelle wird ausgeblendet
    und leitet kuenftig aufs Ziel weiter. Fruehere Weiterleitungen auf die Quelle zeigen
    ebenfalls aufs Ziel (keine Ketten)."""
    if quelle.id == ziel.id:
        raise ValueError('Quelle und Ziel sind gleich')
    for d in list(quelle.diskussionen):
        d.themengebiet = ziel   # ueber die Beziehung, damit delete-orphan nichts loescht
    for alt in Themengebiet.query.filter_by(zusammengefuehrt_in=quelle.id):
        alt.zusammengefuehrt_in = ziel.id
    quelle.zusammengefuehrt_in = ziel.id
    quelle.sichtbar = False
    db.session.commit()


@themen_bp.route('/themen/beitrag/<int:beitrag_id>/entfernen', methods=['POST'])
@zugang
def beitrag_entfernen_route(nutzer, teilnahme, lang, beitrag_id):
    b = _eigener_beitrag(nutzer, beitrag_id)
    beitrag_entfernen(b)
    return redirect(url_for('themen.diskussion', diskussion_id=b.diskussion_id) + f'#beitrag-{b.id}')


@themen_bp.route('/themen/datei/<int:anhang_id>')
@zugang
def datei(nutzer, teilnahme, lang, anhang_id):
    a = db.session.get(BeitragAnhang, anhang_id)
    if a is None or not a.beitrag.sichtbar or not a.beitrag.diskussion.sichtbar:
        abort(404)
    return send_file(kollaboration.anhang_pfad_in(a.dateiname, UPLOAD_ORDNER), as_attachment=True,
                     download_name=a.originalname or a.dateiname)
