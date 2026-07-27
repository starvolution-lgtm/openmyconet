"""
Einmaliges Setup-Skript: legt den ersten Superadmin-Account aus den
bisherigen ADMIN_USERNAME/ADMIN_PASSWORD-Werten in .env an.

Aufruf: python create_admin.py
Danach können ADMIN_USERNAME/ADMIN_PASSWORD aus der .env entfernt werden —
Logins laufen jetzt über die AdminUser-Tabelle.
"""
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

from app import app
from extensions import db
from models import AdminUser

username = os.getenv('ADMIN_USERNAME', 'admin')
password = os.getenv('ADMIN_PASSWORD', 'changeme')

with app.app_context():
    db.create_all()
    if AdminUser.query.filter_by(username=username).first():
        print(f'Account "{username}" existiert bereits — nichts zu tun.')
    else:
        user = AdminUser(
            username=username,
            password_hash=generate_password_hash(password),
            role='superadmin',
        )
        db.session.add(user)
        db.session.commit()
        print(f'Superadmin "{username}" angelegt.')
