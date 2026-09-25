"""
kontakt.py — OpenMycoNet Kontaktformular (/kontakt.html)
Einbinden in omn/__init__.py: from omn.kontakt import kontakt_bp; app.register_blueprint(kontakt_bp)
"""
import logging
import os

from flask import Blueprint, jsonify, render_template, request
from flask_mail import Message

from omn.extensions import db, mail
from omn.models import Kontaktanfrage
from omn.spam_schutz import ip_erlaubt

logger = logging.getLogger(__name__)

kontakt_bp = Blueprint("kontakt", __name__)

ANLIEGEN_OPTIONEN = {"allgemein", "presse", "foerderung", "technik", "sonstiges"}
NACHRICHT_MAX_LAENGE = 5000


@kontakt_bp.route("/api/kontakt", methods=["POST"])
def kontakt_einreichen():
    """
    Erwartet Formulardaten (multipart/form-data oder x-www-form-urlencoded):
        name (optional), email, telefon (optional), anliegen, nachricht
    Gibt zurück:
        { "ok": true } oder { "error": "..." }
    """
    if request.form.get("website"):
        # Honeypot getroffen — stiller Erfolg vortäuschen, nichts speichern.
        return jsonify({"ok": True})

    ip = request.remote_addr
    if not ip_erlaubt(ip, "kontakt"):
        return jsonify({"error": "Zu viele Anfragen — bitte später erneut versuchen."}), 429

    name = (request.form.get("name") or "").strip()[:100]
    email = (request.form.get("email") or "").strip().lower()[:150]
    telefon = (request.form.get("telefon") or "").strip()[:30]
    anliegen = (request.form.get("anliegen") or "").strip()
    nachricht = (request.form.get("nachricht") or "").strip()[:NACHRICHT_MAX_LAENGE]

    if not email or "@" not in email:
        return jsonify({"error": "Bitte eine gültige E-Mail-Adresse angeben."}), 400
    if anliegen not in ANLIEGEN_OPTIONEN:
        return jsonify({"error": "Bitte ein gültiges Anliegen auswählen."}), 400
    if not nachricht:
        return jsonify({"error": "Bitte eine Nachricht eingeben."}), 400

    anfrage = Kontaktanfrage(
        name=name, email=email, telefon=telefon,
        anliegen=anliegen, nachricht=nachricht, ip=ip,
    )
    db.session.add(anfrage)
    db.session.commit()

    admin_email = os.getenv("ADMIN_NOTIFY_EMAIL") or os.getenv("MAIL_USERNAME")
    if admin_email:
        try:
            subject_name = (anfrage.name or anfrage.email).replace("\r", " ").replace("\n", " ")
            msg = Message(
                subject=f"Neue Kontaktanfrage — {subject_name}",
                recipients=[admin_email],
            )
            msg.body = f"""Neue Kontaktanfrage über das Kontaktformular:

Name: {anfrage.name or '(nicht angegeben)'}
E-Mail: {anfrage.email}
Telefon: {anfrage.telefon or '(nicht angegeben)'}
Anliegen: {anfrage.anliegen}

Nachricht:
{anfrage.nachricht}

Verwalten unter /admin/kontakt
"""
            base_url = os.getenv('BASE_URL', 'https://api.openmyconet.de')
            msg.html = render_template(
                'transaktions_email.html',
                titel='Neue Kontaktanfrage',
                zeilen=[
                    f'Name: {anfrage.name or "(nicht angegeben)"}',
                    f'E-Mail: {anfrage.email}',
                    f'Telefon: {anfrage.telefon or "(nicht angegeben)"}',
                    f'Anliegen: {anfrage.anliegen}',
                    f'Nachricht: {anfrage.nachricht}',
                ],
                cta_text='Kontaktanfrage verwalten',
                cta_url=f'{base_url}/admin/kontakt',
            )
            mail.send(msg)
        except Exception as e:
            logger.error("Kontakt-Benachrichtigung konnte nicht gesendet werden: %s", e)

    return jsonify({"ok": True})
