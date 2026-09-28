"""
registrierung.py — OpenMycoNet allgemeine Registrierung (Double-Opt-in)
Einbinden in app.py: from registrierung import registrierung_bp, register_nutzer_core;
app.register_blueprint(registrierung_bp)
"""

import logging
import os
import secrets
from datetime import timedelta

from flask import Blueprint, request, jsonify, render_template
from flask_mail import Message

from omn.extensions import db, mail
from omn.models import Nutzer
from omn.spam_schutz import ip_erlaubt
from omn.zeit import utcnow

logger = logging.getLogger(__name__)

registrierung_bp = Blueprint("registrierung", __name__)


def register_nutzer_core(name, email, sprache, land, gruppe, ip=None, rollback_on_mail_fail=True,
                         newsletter=False):
    """
    Legt einen neuen Nutzer an und verschickt die Bestätigungsmail (Double-Opt-in).
    Gibt (nutzer, fehlertext) zurück.

    newsletter: nur True, wenn die Person ausdrücklich eingewilligt hat (Häkchen
    „Ja, ich möchte per E-Mail … informiert werden“ auf der Startseite). Sonst
    `keine_mails=True` — Rund-Mails (Newsletter, News-Benachrichtigung) gehen nur
    an bestätigte Nutzer MIT Einwilligung. Bewerbung, Förderer- und
    Kooperationsanträge haben kein solches Häkchen und legen daher ohne
    Einwilligung an. Transaktionale Mails sind davon unberührt.

    rollback_on_mail_fail=True (Standard, für die eigenständige Registrierung, wo die
    Bestätigungsmail der ganze Zweck der Anfrage ist): schlägt der Mailversand fehl,
    wird der Nutzer wieder gelöscht und (None, fehlertext) zurückgegeben.

    rollback_on_mail_fail=False (für den Fall, dass die Registrierung nur ein
    Nebeneffekt einer anderen Anfrage ist, z.B. einer Knoten-Bewerbung): der Nutzer
    bleibt bestehen (unbestätigt) auch wenn die Mail fehlschlägt, der Fehler wird nur
    geloggt, (nutzer, fehlertext) wird zurückgegeben.
    """
    if Nutzer.query.filter_by(email=email).first():
        return None, 'Diese E-Mail ist bereits registriert.'

    token = secrets.token_urlsafe(32)
    nutzer = Nutzer(
        name=name, email=email, sprache=sprache,
        land=land, gruppe=gruppe, token=token, ip=ip,
        keine_mails=not newsletter,
        newsletter_einwilligung_am=utcnow() if newsletter else None,
    )
    db.session.add(nutzer)
    db.session.commit()

    base_url = os.getenv('BASE_URL', 'https://api.openmyconet.de')
    confirm_url = f'{base_url}/confirm/{token}'
    msg = Message(
        subject='OpenMycoNet — Bitte bestätige deine Registrierung',
        recipients=[email]
    )
    msg.body = f'''Hallo {name},

vielen Dank für deine Registrierung bei OpenMycoNet!

Bitte bestätige deine E-Mail-Adresse durch Klick auf folgenden Link:

{confirm_url}

Dieser Link ist einmalig und nur für dich bestimmt.

Das OpenMycoNet-Team
https://www.openmyconet.de
'''
    msg.html = render_template(
        'transaktions_email.html',
        titel='Bitte bestätige deine Registrierung',
        zeilen=[
            f'Hallo {name},',
            'vielen Dank für deine Registrierung bei OpenMycoNet! Bitte bestätige deine E-Mail-Adresse:',
        ],
        cta_text='E-Mail bestätigen',
        cta_url=confirm_url,
        hinweis='Dieser Link ist einmalig und nur für dich bestimmt.',
    )
    try:
        mail.send(msg)
    except Exception as e:
        fehler = f'Mailversand fehlgeschlagen: {e!s}'
        if rollback_on_mail_fail:
            db.session.delete(nutzer)
            db.session.commit()
            return None, fehler
        logger.error("Registrierungs-Bestätigungsmail konnte nicht gesendet werden (%s): %s", email, e)
        return nutzer, fehler

    return nutzer, None


# Hoechstens ein Einwilligungslink je Nutzer in diesem Zeitraum (sonst koennte
# jemand eine fremde Adresse ueber das Formular mit Mails fluten).
EINWILLIGUNG_SPERRE = timedelta(hours=1)


def einwilligung_url(nutzer):
    base_url = os.getenv('BASE_URL', 'https://api.openmyconet.de')
    return f'{base_url}/newsletter/einwilligen/{nutzer.token}'


def einwilligung_nachricht(nutzer, bestand=False):
    """Mail mit dem Einwilligungslink. Erst der Klick (und das Bestaetigen auf der
    Seite) meldet an; wer nichts tut, bekommt keine Rund-Mails.
    bestand=True: einmalige Nachfrage an Bestandsnutzer (`flask einwilligung-anfragen`)."""
    url = einwilligung_url(nutzer)
    if bestand:
        zeilen = [
            f'Hallo {nutzer.name},',
            'wir haben unsere E-Mail-Einstellungen überarbeitet: Newsletter und '
            'News-Benachrichtigungen schicken wir ab sofort nur noch, wenn du '
            'ausdrücklich zugestimmt hast.',
            'Möchtest du weiterhin über Neuigkeiten von OpenMycoNet informiert werden? '
            'Dann bestätige das bitte über den Knopf unten. Wenn nicht, musst du nichts '
            'tun: Du bekommst dann keine weiteren Rund-Mails, dein Konto bleibt bestehen.',
        ]
        betreff = 'OpenMycoNet — Möchtest du weiter Neuigkeiten bekommen?'
    else:
        zeilen = [
            f'Hallo {nutzer.name},',
            'du möchtest per E-Mail über Neuigkeiten von OpenMycoNet informiert werden. '
            'Bitte bestätige das über den Knopf unten.',
            'Warst du das nicht? Dann ignoriere diese Mail einfach, es passiert nichts.',
        ]
        betreff = 'OpenMycoNet — Bitte bestätige: Neuigkeiten per E-Mail'
    msg = Message(subject=betreff, recipients=[nutzer.email])
    msg.body = '\n\n'.join([*zeilen, url, 'Das OpenMycoNet-Team\nhttps://www.openmyconet.de']) + '\n'
    msg.html = render_template(
        'transaktions_email.html',
        titel='Neuigkeiten per E-Mail',
        zeilen=zeilen,
        cta_text='Ja, ich möchte Neuigkeiten bekommen',
        cta_url=url,
        hinweis='Du kannst dich in jeder Rund-Mail mit einem Klick wieder abmelden.',
    )
    return msg


def _einwilligung_anfragen(nutzer):
    """Bestehender Nutzer ohne Einwilligung setzt beim erneuten Registrieren das
    Haekchen: nichts direkt umstellen, sondern Einwilligungslink schicken
    (Robby, 28.09.2026). Innerhalb der Sperre still nichts tun."""
    jetzt = utcnow()
    if nutzer.einwilligung_angefragt_am and jetzt - nutzer.einwilligung_angefragt_am < EINWILLIGUNG_SPERRE:
        return None
    try:
        mail.send(einwilligung_nachricht(nutzer))
    except Exception as e:
        logger.error("Einwilligungsmail konnte nicht gesendet werden (%s): %s", nutzer.email, e)
        return f'Mailversand fehlgeschlagen: {e!s}'
    nutzer.einwilligung_angefragt_am = jetzt
    db.session.commit()
    return None


@registrierung_bp.route("/api/register", methods=["POST"])
def api_register():
    """
    Erwartet Formulardaten (multipart/form-data oder x-www-form-urlencoded):
        name, email, land, gruppe, newsletter (Checkbox, nur bei Einwilligung
        mitgeschickt), sowie die Sprache entweder als "lang" (so
        sendet es index.html, wie auch bei /api/bewerbung) oder als "sprache"
        (so sendet es das eigenständige register.html-Formular).
    Gibt zurück:
        { "ok": true } oder { "error": "..." }
    """
    if request.form.get("website"):
        # Honeypot getroffen — stiller Erfolg vortäuschen, nichts speichern.
        return jsonify({"ok": True})

    ip = request.remote_addr
    if not ip_erlaubt(ip, "register"):
        return jsonify({"error": "Zu viele Anfragen — bitte später erneut versuchen."}), 429

    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip().lower()
    sprache = (request.form.get("lang") or request.form.get("sprache") or "de").strip()
    land = (request.form.get("land") or "").strip()
    gruppe = (request.form.get("gruppe") or "allgemein").strip()
    # Browser schicken eine angehakte Checkbox als "on" mit, eine leere gar nicht.
    newsletter = (request.form.get("newsletter") or "").strip().lower() in ("on", "1", "true", "ja")

    if not email:
        return jsonify({"error": "E-Mail-Adresse fehlt."}), 400

    vorhanden = Nutzer.query.filter_by(email=email).first()
    if vorhanden and newsletter and vorhanden.keine_mails:
        fehler = _einwilligung_anfragen(vorhanden)
        if fehler:
            return jsonify({"error": fehler}), 400
        return jsonify({"ok": True, "einwilligung_angefragt": True})

    _nutzer, fehler = register_nutzer_core(
        name, email, sprache, land, gruppe, ip=ip, newsletter=newsletter,
    )
    if fehler:
        return jsonify({"error": fehler}), 400
    return jsonify({"ok": True})
