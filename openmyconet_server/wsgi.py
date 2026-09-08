"""WSGI-Einstiegspunkt fuer gunicorn:  gunicorn -w 2 -b 127.0.0.1:5000 wsgi:app

Baut die App ueber die Factory frisch auf -- keine Abhaengigkeit vom
Modul-Level-`app`-Singleton in app.py (der bleibt nur als Bruecke fuer die
Wartungs-Scripts bestehen).
"""
from omn import create_app

app = create_app()


if __name__ == '__main__':
    app.run(debug=False)
