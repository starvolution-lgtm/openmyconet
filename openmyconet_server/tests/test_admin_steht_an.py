"""Admin: "Steht an"-Karte auf /admin und Zaehler in der Leiste (Design 28.10.2026)."""
from conftest import eingeloggt

from omn.extensions import db
from omn.models import Kontaktanfrage


def test_steht_an_und_zaehler(client, app, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    seite = client.get('/admin').get_data(as_text=True)
    assert 'Steht an' in seite and 'Nichts offen' in seite
    db.session.add_all([Kontaktanfrage(email='a@example.org', anliegen='frage', nachricht='Hallo'),
                        Kontaktanfrage(email='b@example.org', anliegen='frage', nachricht='Hallo')])
    db.session.commit()
    seite = client.get('/admin').get_data(as_text=True)
    assert '2 neue Kontaktanfragen' in seite
    assert '✉️ Kontakt <span class="nav-zaehler">2</span>' in seite      # Zaehler in der Leiste
    assert 'class=" aktiv" aria-current="page">👥 Nutzer' in seite         # aktueller Bereich
    # erledigt -> zaehlt nicht mehr
    for k in Kontaktanfrage.query.all():
        k.status = 'erledigt'
    db.session.commit()
    assert 'Nichts offen' in client.get('/admin').get_data(as_text=True)


def test_editor_sieht_keine_zaehler(client, app, editor):
    db.session.add(Kontaktanfrage(email='a@example.org', anliegen='frage', nachricht='Hallo'))
    db.session.commit()
    eingeloggt(client, 'editor_test', 'auch-geheim-123')
    seite = client.get('/admin/news').get_data(as_text=True)
    assert 'nav-zaehler' not in seite
