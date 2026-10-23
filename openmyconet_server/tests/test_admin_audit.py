"""Sicherheitsdurchsicht Paket 2 (23.10.2026): Audit-Log, Login-Alarm,
Passwort-Mindestlaenge 12."""
import pyotp
from conftest import eingeloggt

from omn.extensions import db, mail
from omn.models import AdminAudit, AdminUser, Nutzer


def _aktionen():
    return [a.aktion for a in AdminAudit.query.order_by(AdminAudit.id).all()]


# --- Login-Protokoll + Alarm ---

def test_erster_login_von_neuer_ip_protokolliert_und_alarmiert(client, superadmin):
    with mail.record_messages() as ausgehend:
        eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    assert _aktionen() == ['login']
    eintrag = AdminAudit.query.one()
    assert eintrag.benutzername == 'superadmin_test'
    assert eintrag.ip == '127.0.0.1'
    assert eintrag.zeitpunkt is not None
    assert len(ausgehend) == 1
    assert 'neuer IP' in ausgehend[0].subject


def test_zweiter_login_von_bekannter_ip_ohne_alarm(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    client.get('/logout')
    with mail.record_messages() as ausgehend:
        eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    assert _aktionen() == ['login', 'login']
    assert ausgehend == []


def test_login_von_anderer_ip_alarmiert(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    client.get('/logout')
    with mail.record_messages() as ausgehend:
        client.post('/login', data={'username': 'superadmin_test', 'password': 'sehr-geheim-123'},
                    environ_base={'REMOTE_ADDR': '198.51.100.9'})
    assert len(ausgehend) == 1
    assert '198.51.100.9' in ausgehend[0].body


def test_fehlversuch_protokolliert_unbekannten_namen_nicht(client, superadmin):
    client.post('/login', data={'username': 'superadmin_test', 'password': 'falsch'})
    client.post('/login', data={'username': 'geheimes-passwort-im-falschen-feld', 'password': 'x'})
    eintraege = AdminAudit.query.order_by(AdminAudit.id).all()
    assert [e.aktion for e in eintraege] == ['login_fehlgeschlagen', 'login_fehlgeschlagen']
    assert eintraege[0].benutzername == 'superadmin_test'
    assert eintraege[1].benutzername == ''
    assert 'geheimes' not in eintraege[1].ziel


def test_fehlversuch_serie_sperrt_und_alarmiert(client, superadmin, monkeypatch):
    # conftest schaltet die Sperre ab; hier: nach diesem Fehlversuch ist die IP gesperrt.
    aufrufe = []

    def gesperrt(*a, **kw):
        aufrufe.append(a)
        return len(aufrufe) > 1   # 1. Aufruf: Vorpruefung (noch frei), 2.: nach dem Fehlversuch
    monkeypatch.setattr('omn.admin.auth.ip_gesperrt', gesperrt)
    with mail.record_messages() as ausgehend:
        client.post('/login', data={'username': 'superadmin_test', 'password': 'falsch'})
    assert _aktionen() == ['login_fehlgeschlagen', 'login_ip_gesperrt']
    assert len(ausgehend) == 1
    assert 'Login-Sperre' in ausgehend[0].subject


def test_2fa_falscher_code_von_neuer_ip_alarmiert(client, superadmin):
    superadmin.totp_secret = pyotp.random_base32()
    superadmin.totp_aktiviert = True
    db.session.commit()
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    with mail.record_messages() as ausgehend:
        client.post('/login/2fa', data={'code': '000000'})
    assert _aktionen() == ['login_passwort_ok', 'login_2fa_fehlgeschlagen']
    assert len(ausgehend) == 1
    assert 'falscher 2FA-Code' in ausgehend[0].subject
    # richtiger Code -> vollstaendiger Login, wieder mit Alarm (erste Anmeldung von dieser IP)
    with mail.record_messages() as ausgehend:
        client.post('/login/2fa', data={'code': pyotp.TOTP(superadmin.totp_secret).now()})
    assert _aktionen()[-1] == 'login'
    assert len(ausgehend) == 1


# --- Admin-Aktionen ---

def test_aktionen_landen_im_audit_log(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    nutzer = Nutzer(name='Zu Loeschen', email='weg@example.com', bestaetigt=False)
    db.session.add(nutzer)
    db.session.commit()
    client.post(f'/admin/nutzer/bestaetigen/{nutzer.id}')
    client.post(f'/admin/nutzer/rolle/{nutzer.id}', data={'ist_hyphist': '1'})
    client.post(f'/admin/nutzer/loeschen/{nutzer.id}')
    client.post('/admin/accounts', data={'username': 'neu', 'password': 'zwoelf-zeichen!', 'role': 'editor'})
    assert _aktionen()[1:] == ['nutzer_bestaetigt', 'nutzer_rolle', 'nutzer_geloescht', 'account_angelegt']
    assert all(a.benutzername == 'superadmin_test' for a in AdminAudit.query.all())

    seite = client.get('/admin/audit').get_data(as_text=True)
    assert 'nutzer_geloescht' in seite and 'account_angelegt' in seite


def test_audit_ansicht_nur_superadmin(client, editor):
    eingeloggt(client, 'editor_test', 'auch-geheim-123')
    assert client.get('/admin/audit').status_code == 403


def test_audit_fehler_blockiert_aktion_nicht(client, superadmin, monkeypatch):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')

    def kaputt(*a, **kw):
        raise RuntimeError('DB weg')
    monkeypatch.setattr('omn.admin.audit.AdminAudit', kaputt)
    nutzer = Nutzer(name='X', email='x@example.com', bestaetigt=False)
    db.session.add(nutzer)
    db.session.commit()
    assert client.post(f'/admin/nutzer/bestaetigen/{nutzer.id}').status_code == 302
    assert db.session.get(Nutzer, nutzer.id).bestaetigt is True


# --- Passwort-Mindestlaenge ---

def test_passwort_unter_12_zeichen_abgelehnt(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    r = client.post('/admin/password', data={'aktuelles_passwort': 'sehr-geheim-123',
                                             'neues_passwort': 'elf-zeichen', 'neues_passwort_wiederholt': 'elf-zeichen'})
    assert 'mindestens 12 Zeichen' in r.get_data(as_text=True)
    r = client.post('/admin/password', data={'aktuelles_passwort': 'sehr-geheim-123',
                                             'neues_passwort': 'zwoelf-zeichen', 'neues_passwort_wiederholt': 'zwoelf-zeichen'})
    assert 'erfolgreich' in r.get_data(as_text=True)
    assert 'passwort_geaendert' in _aktionen()


def test_neuer_account_unter_12_zeichen_abgelehnt(client, superadmin):
    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    r = client.post('/admin/accounts', data={'username': 'kurz', 'password': 'nur-elf-zei', 'role': 'editor'})
    assert 'mindestens 12 Zeichen' in r.get_data(as_text=True)
    assert AdminUser.query.filter_by(username='kurz').first() is None
