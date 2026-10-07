"""Server-MCC, Schritt 1: Kontakte -- Versandlog, Vorstellungs-Mails, Erinnerung.

- Versand per SMTP ueber das Postfach robert.jank@ (eigene Zugangsdaten MCC_MAIL_*
  in der .env; Server/Port wie die Website). Bewusst NICHT ueber Flask-Mail, das an
  kontakt@ haengt. Einzelmail sofort, nicht ueber die Mail-Queue. Erst nach
  erfolgreichem Versand wird eingetragen; MAIL_SUPPRESS_SEND (Staging) -> nichts
  verschickt, Eintrag mit versandart 'unterdrueckt'.
- Faellig = Status offen/nachfrage und Wiedervorlage <= heute (Ortsdatum Berlin).
- Erinnerung: `flask mcc-erinnerung` (Cron morgens, deploy/mcc_erinnerung.sh) schickt
  Robby nur dann eine Mail, wenn etwas faellig ist -- mit Namen (Robby, 07.10.2026).
"""
import csv
import io
import logging
import re
import smtplib
import ssl
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from zoneinfo import ZoneInfo

from flask import (Response, current_app, flash, g, redirect, render_template, request,
                   session, url_for)
from flask_mail import Message
from markupsafe import escape

from omn.admin import role_required
from omn.extensions import db, mail
from omn.mcc import mcc_bp
from omn.mcc.mailbau import SPRACHEN, mail_bauen, vorlagen
from omn.models import KontaktVersand

logger = logging.getLogger(__name__)

STATUS = {
    'offen': 'offen',
    'positiv': 'positiv',
    'negativ': 'negativ',
    'nachfrage': 'keine Antwort / Nachfrage geplant',
}
FAELLIG_STATUS = ('offen', 'nachfrage')
_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
ORTSZEIT = ZoneInfo('Europe/Berlin')
# CSP nur fuer die Mail-Vorschau im iframe: die HTML-Mail braucht Inline-Styles
# (Mailprogramme ignorieren Stylesheets); Skripte bleiben ganz verboten.
VORSCHAU_CSP = ("default-src 'none'; style-src 'unsafe-inline'; img-src https://www.openmyconet.de; "
                "frame-ancestors 'self'; base-uri 'none'; form-action 'none'")


def heute():
    return datetime.now(ORTSZEIT).date()


def _tage_einstellung(schluessel, standard):
    try:
        return max(0, int(current_app.config.get(schluessel) or standard))
    except (TypeError, ValueError):
        return standard


def wiedervorlage_tage():
    return _tage_einstellung('MCC_WIEDERVORLAGE_TAGE', 14)


def nachfrage_tage():
    return _tage_einstellung('MCC_NACHFRAGE_TAGE', 7)


def faellige(stichtag=None):
    stichtag = stichtag or heute()
    return (KontaktVersand.query
            .filter(KontaktVersand.status.in_(FAELLIG_STATUS),
                    KontaktVersand.wiedervorlage.isnot(None),
                    KontaktVersand.wiedervorlage <= stichtag)
            .order_by(KontaktVersand.wiedervorlage, KontaktVersand.id).all())


def ist_faellig(k, stichtag):
    return k.status in FAELLIG_STATUS and k.wiedervorlage is not None and k.wiedervorlage <= stichtag


# --- Eingaben pruefen --------------------------------------------------------------
def _text(wert, laenge):
    return ' '.join(str(wert or '').split())[:laenge]


def _datum(wert, feld):
    try:
        return date.fromisoformat(str(wert).strip())
    except ValueError:
        raise ValueError(f'{feld}: kein gültiges Datum.')


def _tage(wert, feld):
    try:
        n = int(str(wert).strip())
    except (TypeError, ValueError):
        raise ValueError(f'{feld}: bitte eine ganze Zahl angeben.')
    if not 0 <= n <= 3650:
        raise ValueError(f'{feld}: 0 bis 3650 Tage.')
    return n


def _person(f):
    """-> (email, titel, name, sprache) oder ValueError."""
    email = _text(f.get('email'), 254)
    if not _EMAIL.match(email):
        raise ValueError('Bitte eine gültige E-Mail-Adresse angeben.')
    name = _text(f.get('name'), 200)
    if not name:
        raise ValueError('Bitte den Namen angeben.')
    sprache = str(f.get('sprache', '')).lower()
    if sprache not in SPRACHEN:
        raise ValueError('Sprache muss DE oder EN sein.')
    return email, _text(f.get('titel'), 60), name, sprache


def _vermerk(notiz, text):
    zeile = f'{heute():%d.%m.%Y} {text}'.strip()
    return (notiz + '\n' + zeile).strip() if notiz else zeile


# --- Versand -----------------------------------------------------------------------
def versand_konfig():
    """-> (konfig, fehlende .env-Schluessel)."""
    c = current_app.config
    k = {
        'server': c.get('MAIL_SERVER'), 'port': c.get('MAIL_PORT') or 587,
        'benutzer': c.get('MCC_MAIL_USERNAME'), 'passwort': c.get('MCC_MAIL_PASSWORD'),
        'absender': c.get('MCC_MAIL_SENDER'), 'absender_name': c.get('MCC_MAIL_SENDER_NAME') or '',
        'bcc': c.get('MCC_MAIL_BCC') or '',
    }
    pflicht = {'server': 'MAIL_SERVER', 'benutzer': 'MCC_MAIL_USERNAME',
               'passwort': 'MCC_MAIL_PASSWORD', 'absender': 'MCC_MAIL_SENDER'}
    return k, [env for feld, env in pflicht.items() if not str(k[feld] or '').strip()]


def versand_unterdrueckt():
    return bool(current_app.config.get('MAIL_SUPPRESS_SEND'))


def _smtp_senden(an, inhalt):
    """Verschickt die Mail oder wirft ValueError mit Klartext (dann nichts versendet)."""
    k, fehlend = versand_konfig()
    if fehlend:
        raise ValueError('Versand nicht eingerichtet: in der .env fehlt ' + ', '.join(fehlend) + '.')
    msg = EmailMessage()
    msg['Subject'] = inhalt['betreff']
    msg['From'] = formataddr((k['absender_name'], k['absender']))
    msg['To'] = an
    if k['bcc']:
        msg['Bcc'] = k['bcc']  # send_message: Empfaenger ja, Kopfzeile wird nicht mitgeschickt
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=k['absender'].rpartition('@')[2] or None)
    msg.set_content(inhalt['text'])
    msg.add_alternative(inhalt['html'], subtype='html')
    port = int(k['port'])
    try:
        if port == 465:
            verbindung = smtplib.SMTP_SSL(k['server'], port, timeout=30, context=ssl.create_default_context())
        else:
            verbindung = smtplib.SMTP(k['server'], port, timeout=30)
        with verbindung as s:
            if port != 465:
                s.starttls(context=ssl.create_default_context())
            s.login(k['benutzer'], k['passwort'])
            s.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise ValueError('Anmeldung am Mailserver abgelehnt (MCC_MAIL_USERNAME/MCC_MAIL_PASSWORD prüfen). '
                         'Nichts versendet.')
    except (smtplib.SMTPException, OSError) as e:
        logger.error('Vorstellungs-Mail an %s fehlgeschlagen: %s', an, e)
        raise ValueError(f'Versand fehlgeschlagen ({type(e).__name__}). Nichts versendet, nichts eingetragen.')


# --- Seiten ------------------------------------------------------------------------
@mcc_bp.route('')
@mcc_bp.route('/')
@role_required('superadmin')
def start():
    from omn.mcc.dateien import stand_anzeige
    from omn.mcc.server import ampel_kurz
    from omn.mcc.spiegel import offene_punkte
    stichtag = heute()
    return render_template('mcc/start.html', faellig=len(faellige(stichtag)), stand=stand_anzeige(), ampel=ampel_kurz(),
                           offen_punkte=sum(d['anzahl'] for d in offene_punkte()),
                           offen=KontaktVersand.query.filter(KontaktVersand.status.in_(FAELLIG_STATUS)).count(),
                           gesamt=KontaktVersand.query.count())


@mcc_bp.route('/kontakte')
@role_required('superadmin')
def kontakte():
    stichtag = heute()
    filter_status = request.args.get('status', '')
    abfrage = KontaktVersand.query
    if filter_status in STATUS:
        abfrage = abfrage.filter(KontaktVersand.status == filter_status)
    # Offene/Nachfrage nach Wiedervorlage zuerst, Erledigte (positiv/negativ) ans Ende
    eintraege = sorted(abfrage.all(), key=lambda k: (k.status not in FAELLIG_STATUS, k.wiedervorlage is None,
                                                     k.wiedervorlage or date.max, k.datum_versand, k.id))
    if filter_status == 'faellig':
        eintraege = [k for k in eintraege if ist_faellig(k, stichtag)]
    return render_template('mcc/kontakte.html', eintraege=eintraege, filter_status=filter_status,
                           status_namen=STATUS, sprachen=SPRACHEN, stichtag=stichtag,
                           vorlagen_titel={n: v['titel'] for n, v in vorlagen().items()},
                           faellig=len(faellige(stichtag)), nachfrage_tage=nachfrage_tage(),
                           ist_faellig=ist_faellig)


def _eintrag_oder_404(kid):
    return db.get_or_404(KontaktVersand, kid)


def _zurueck_zur_liste():
    ziel = request.form.get('zurueck', '')
    # nur eigene Liste mit Filter, nie fremde Adressen
    if not re.fullmatch(r'(faellig|offen|positiv|negativ|nachfrage)?', ziel):
        ziel = ''
    return redirect(url_for('mcc.kontakte', status=ziel or None) + '#k-liste')


@mcc_bp.route('/kontakte/<int:kid>/ergebnis', methods=['POST'])
@role_required('superadmin')
def ergebnis(kid):
    k = _eintrag_oder_404(kid)
    aktion = request.form.get('aktion')
    notiz = _text(request.form.get('notiz'), 500)
    try:
        if aktion in ('positiv', 'negativ'):
            k.status = aktion
            k.erledigt_am = heute()
            k.notiz = _vermerk(k.notiz, aktion + (f': {notiz}' if notiz else ''))
            meldung = f'{k.name}: als {aktion} abgehakt.'
        elif aktion == 'nachfrage':
            tage = _tage(request.form.get('tage', nachfrage_tage()), 'Neue Wiedervorlage')
            k.status = 'nachfrage'
            k.nachfragen += 1
            k.wiedervorlage = heute() + timedelta(days=tage)
            k.notiz = _vermerk(k.notiz, f'Nachfrage {k.nachfragen}' + (f': {notiz}' if notiz else ''))
            meldung = f'{k.name}: Nachfrage {k.nachfragen} vermerkt, Wiedervorlage {k.wiedervorlage:%d.%m.%Y}.'
        else:
            raise ValueError('Unbekannte Aktion.')
    except ValueError as e:
        flash(str(e), 'error')
        return _zurueck_zur_liste()
    k.letzte_aktivitaet = heute()
    db.session.commit()
    flash(meldung, 'success')
    return _zurueck_zur_liste()


@mcc_bp.route('/kontakte/<int:kid>/bearbeiten', methods=['POST'])
@role_required('superadmin')
def bearbeiten(kid):
    k = _eintrag_oder_404(kid)
    f = request.form
    try:
        email, titel, name, sprache = _person(f)
        status = f.get('status', '')
        if status not in STATUS:
            raise ValueError('Unbekannter Status.')
        k.datum_versand = _datum(f.get('datum_versand'), 'Versanddatum')
        k.wiedervorlage = _datum(f['wiedervorlage'], 'Wiedervorlage') if f.get('wiedervorlage') else None
        k.nachfragen = _tage(f.get('nachfragen', k.nachfragen), 'Anzahl Nachfragen')
    except ValueError as e:
        flash(str(e), 'error')
        return _zurueck_zur_liste()
    vorlage = _text(f.get('vorlage'), 80)
    k.email, k.titel, k.name, k.sprache, k.status = email, titel, name, sprache, status
    k.vorlage = vorlage or k.vorlage
    k.notiz = str(f.get('notiz') or '').replace('\r\n', '\n').strip()[:2000]
    if status in FAELLIG_STATUS:
        k.erledigt_am = None
    k.letzte_aktivitaet = heute()
    db.session.commit()
    flash(f'{k.name}: gespeichert.', 'success')
    return _zurueck_zur_liste()


@mcc_bp.route('/kontakte/<int:kid>/loeschen', methods=['POST'])
@role_required('superadmin')
def loeschen(kid):
    k = _eintrag_oder_404(kid)
    name = k.name
    db.session.delete(k)
    db.session.commit()
    flash(f'{name}: Eintrag gelöscht.', 'success')
    return _zurueck_zur_liste()


@mcc_bp.route('/kontakte/export.csv')
@role_required('superadmin')
def export_csv():
    """Gesamtexport (Semikolon, UTF-8 mit BOM -> Excel liest Umlaute richtig)."""
    spalten = ['id', 'datum_versand', 'email', 'titel', 'name', 'sprache', 'vorlage', 'status',
               'wiedervorlage', 'nachfragen', 'erledigt_am', 'versandart', 'notiz']
    puffer = io.StringIO()
    w = csv.writer(puffer, delimiter=';', lineterminator='\r\n')
    w.writerow(spalten)
    for k in KontaktVersand.query.order_by(KontaktVersand.id).all():
        werte = {s: getattr(k, s) for s in spalten}
        werte['sprache'] = SPRACHEN.get(k.sprache, k.sprache)
        werte['status'] = STATUS.get(k.status, k.status)
        w.writerow(['' if werte[s] is None else werte[s] for s in spalten])
    return Response('﻿' + puffer.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':
                             f'attachment; filename="kontakte_{heute():%Y-%m-%d}.csv"'})


@mcc_bp.route('/vorlagen', methods=['GET'])
@role_required('superadmin')
def vorlagen_seite(werte=None):
    k, fehlend = versand_konfig()
    alle = vorlagen()
    werte = werte or {'vorlage': next(iter(alle), ''), 'sprache': 'de',
                      'wiedervorlage_tage': wiedervorlage_tage()}
    absender = (f'{k["absender_name"]} <{k["absender"]}>' if k['absender_name'] else k['absender']) \
        if k['absender'] else ''
    return render_template('mcc/vorlagen.html', vorlagen=alle, werte=werte, fehlend=fehlend,
                           absender=absender, bcc=k['bcc'], unterdrueckt=versand_unterdrueckt(),
                           faellig=len(faellige()))


@mcc_bp.route('/vorlagen/vorschau', methods=['GET', 'POST'])
@role_required('superadmin')
def vorschau():
    """HTML der Mail fuer das Vorschau-iframe -- genau das, was versendet wuerde.

    Zwei Wege: mcc.js schickt die Eingaben per fetch (POST, Header X-MCC-Vorschau)
    -> landen in der Session, Antwort 204; das iframe laedt danach per GET. So
    stehen Namen nie in einer URL (Logs), und es funktioniert auch dort, wo
    Formular-POSTs in ein iframe blockiert werden. Ohne JavaScript schickt der
    Knopf "Vorschau aktualisieren" das Formular direkt ins iframe (POST -> HTML)."""
    if request.method == 'POST':
        f = request.form
        werte = {'vorlage': _text(f.get('vorlage'), 80), 'sprache': str(f.get('sprache', 'de')).lower()[:2],
                 'titel': _text(f.get('titel'), 60), 'name': _text(f.get('name'), 200)}
        if request.headers.get('X-MCC-Vorschau'):
            session['mcc_vorschau'] = werte
            return '', 204
    else:
        werte = session.get('mcc_vorschau') or {'vorlage': next(iter(vorlagen()), ''), 'sprache': 'de',
                                                'titel': '', 'name': ''}
    try:
        inhalt = mail_bauen(werte['vorlage'], werte['sprache'], werte['titel'], werte['name'] or '‹Name›')
    except ValueError as e:
        inhalt = {'html': f'<p>{escape(str(e))}</p>'}
    g.csp_override = VORSCHAU_CSP
    return Response(inhalt['html'], mimetype='text/html')


@mcc_bp.route('/vorlagen/senden', methods=['POST'])
@role_required('superadmin')
def senden():
    f = request.form
    werte = {s: f.get(s, '') for s in ('email', 'titel', 'name', 'sprache', 'vorlage', 'wiedervorlage_tage', 'notiz')}
    try:
        email, titel, name, sprache = _person(f)
        vorlage = _text(f.get('vorlage'), 80)
        if vorlage not in vorlagen():
            raise ValueError('Unbekannte Vorlage.')
        tage =_tage(f.get('wiedervorlage_tage', wiedervorlage_tage()), 'Wiedervorlage')
        inhalt = mail_bauen(vorlage, sprache, titel, name)
        if versand_unterdrueckt():
            versandart = 'unterdrueckt'
        else:
            _smtp_senden(email, inhalt)
            versandart = 'server'
    except ValueError as e:
        flash(str(e), 'error')
        return vorlagen_seite(werte), 400
    stichtag = heute()
    k = KontaktVersand(datum_versand=stichtag, email=email, titel=titel, name=name, sprache=sprache,
                       vorlage=vorlage, status='offen', wiedervorlage=stichtag + timedelta(days=tage),
                       nachfragen=0, versandart=versandart, letzte_aktivitaet=stichtag,
                       notiz=str(f.get('notiz') or '').replace('\r\n', '\n').strip()[:2000])
    db.session.add(k)
    db.session.commit()
    if versandart == 'unterdrueckt':
        flash(f'Mailversand ist hier abgeschaltet (Staging) – nichts verschickt, Eintrag für {name} trotzdem '
              f'angelegt, Wiedervorlage {k.wiedervorlage:%d.%m.%Y}.', 'success')
    else:
        flash(f'✅ Mail an {email} gesendet. Im Versandlog eingetragen, Wiedervorlage {k.wiedervorlage:%d.%m.%Y}.',
              'success')
    return redirect(url_for('mcc.vorlagen_seite'))


# --- Erinnerung (Cron) ---------------------------------------------------------------
def erinnerung_senden(stichtag=None):
    """Mail an Robby, wenn Kontakte faellig sind. -> Anzahl faelliger Kontakte (0 = keine Mail)."""
    liste = faellige(stichtag)
    if not liste:
        return 0
    an = (current_app.config.get('MCC_ERINNERUNG_AN') or current_app.config.get('MCC_MAIL_SENDER')
          or current_app.config.get('ADMIN_NOTIFY_EMAIL'))
    if not an:
        logger.error('mcc-erinnerung: kein Empfaenger (MCC_ERINNERUNG_AN) gesetzt')
        return len(liste)
    n = len(liste)
    zeilen = [f'{("" if not k.titel else k.titel + " ")}{k.name} – versendet {k.datum_versand:%d.%m.%Y}, '
              f'Wiedervorlage {k.wiedervorlage:%d.%m.%Y}' + (f', {k.nachfragen}× nachgefragt' if k.nachfragen else '')
              for k in liste]
    link = 'https://api.openmyconet.de/mcc/kontakte?status=faellig'
    titel = f'{n} Kontakt{"e" if n != 1 else ""} fällig'
    msg = Message(subject=f'MCC: {titel}', recipients=[an])
    msg.body = f'{titel}:\n\n' + '\n'.join('- ' + z for z in zeilen) + f'\n\nZum Abhaken: {link}\n'
    msg.html = render_template('transaktions_email.html', titel=titel, zeilen=zeilen,
                               cta_text='Im MCC abhaken', cta_url=link,
                               hinweis='Diese Erinnerung kommt nur an Tagen, an denen etwas fällig ist.')
    mail.send(msg)
    return n
