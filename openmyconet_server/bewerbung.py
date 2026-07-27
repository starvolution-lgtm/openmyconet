"""
bewerbung.py — OpenMycoNet Knotenbetreiber-Bewerbungen
Einbinden in app.py: from bewerbung import bewerbung_bp; app.register_blueprint(bewerbung_bp)
"""

import os
import logging
from flask import Blueprint, request, jsonify
from flask_mail import Message

from extensions import db, mail
from models import Bewerbung

logger = logging.getLogger(__name__)

bewerbung_bp = Blueprint("bewerbung", __name__)


@bewerbung_bp.route("/api/bewerbung", methods=["POST"])
def bewerbung_einreichen():
    """
    Erwartet Formulardaten (multipart/form-data oder x-www-form-urlencoded):
        name, email, rolle, profession, node_substrat, adresse, lat, lon, motivation, lang
    Gibt zurück:
        { "ok": true } oder { "error": "..." }
    """
    email = (request.form.get("email") or "").strip().lower()
    motivation = (request.form.get("motivation") or "").strip()
    substrat = (request.form.get("node_substrat") or "").strip()

    if not email or not motivation or not substrat:
        return jsonify({"error": "Pflichtfelder fehlen (E-Mail, Substrat, Motivation)"}), 400

    def parse_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    bewerbung = Bewerbung(
        name=(request.form.get("name") or "").strip(),
        email=email,
        rolle=(request.form.get("rolle") or "").strip(),
        profession=(request.form.get("profession") or "").strip(),
        substrat=substrat,
        adresse=(request.form.get("adresse") or "").strip(),
        lat=parse_float(request.form.get("lat")),
        lon=parse_float(request.form.get("lon")),
        motivation=motivation,
        sprache=(request.form.get("lang") or "de").strip(),
    )
    db.session.add(bewerbung)
    db.session.commit()

    admin_email = os.getenv("ADMIN_NOTIFY_EMAIL") or os.getenv("MAIL_USERNAME")
    if admin_email:
        try:
            subject_name = (bewerbung.name or bewerbung.email).replace("\r", " ").replace("\n", " ")
            msg = Message(
                subject=f"Neue Knotenbetreiber-Bewerbung — {subject_name}",
                recipients=[admin_email],
            )
            msg.body = f"""Neue Bewerbung für einen BioComm-Knoten:

Name: {bewerbung.name or '(nicht angegeben)'}
E-Mail: {bewerbung.email}
Rolle: {bewerbung.rolle or '(nicht angegeben)'}
Beruf/Hintergrund: {bewerbung.profession or '(nicht angegeben)'}
Substrat: {bewerbung.substrat}
Adresse: {bewerbung.adresse or '(nicht angegeben)'}
Koordinaten: {bewerbung.lat}, {bewerbung.lon}

Bewerbungstext:
{bewerbung.motivation}

Verwalten unter /admin/bewerbungen
"""
            mail.send(msg)
        except Exception as e:
            logger.error("Bewerbungs-Benachrichtigung konnte nicht gesendet werden: %s", e)

    return jsonify({"ok": True})
