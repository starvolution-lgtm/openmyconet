"""
registrierung.py — OpenMycoNet allgemeine Registrierung (Double-Opt-in)
Einbinden in app.py: from registrierung import registrierung_bp, register_nutzer_core;
app.register_blueprint(registrierung_bp)
"""

import logging
import os
import secrets

from flask import Blueprint, request, jsonify
from flask_mail import Message

from extensions import db, mail
from models import Nutzer
from spam_schutz import ip_erlaubt

logger = logging.getLogger(__name__)

registrierung_bp = Blueprint("registrierung", __name__)


def register_nutzer_core(name, email, sprache, land, gruppe, ip=None, rollback_on_mail_fail=True):
    """
    Legt einen neuen Nutzer an und verschickt die Bestätigungsmail (Double-Opt-in).
    Gibt (nutzer, fehlertext) zurück.

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
        land=land, gruppe=gruppe, token=token, ip=ip
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
    try:
        mail.send(msg)
    except Exception as e:
        fehler = f'Mailversand fehlgeschlagen: {str(e)}'
        if rollback_on_mail_fail:
            db.session.delete(nutzer)
            db.session.commit()
            return None, fehler
        logger.error("Registrierungs-Bestätigungsmail konnte nicht gesendet werden (%s): %s", email, e)
        return nutzer, fehler

    return nutzer, None


@registrierung_bp.route("/api/register", methods=["POST"])
def api_register():
    """
    Erwartet Formulardaten (multipart/form-data oder x-www-form-urlencoded):
        name, email, land, gruppe, sowie die Sprache entweder als "lang" (so
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

    if not email:
        return jsonify({"error": "E-Mail-Adresse fehlt."}), 400

    nutzer, fehler = register_nutzer_core(name, email, sprache, land, gruppe, ip=ip)
    if fehler:
        return jsonify({"error": fehler}), 400
    return jsonify({"ok": True})
