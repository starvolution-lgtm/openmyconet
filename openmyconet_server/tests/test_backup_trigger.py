"""Kontrollzentrum-Backup-Kachel + die manuellen Trigger-Routen."""
import subprocess

import pytest
from conftest import eingeloggt

import admin
import kontrollzentrum


@pytest.fixture(autouse=True)
def _kz_cache_reset():
    kontrollzentrum._cache['ergebnisse'] = None
    kontrollzentrum._cache['zeitpunkt'] = 0.0


# --- check_backup / check_backup_offsite ---

def test_check_backup_ohne_verzeichnis_gibt_none(monkeypatch, tmp_path):
    monkeypatch.setattr(kontrollzentrum, 'BACKUP_DIR', str(tmp_path / 'fehlt'))
    assert kontrollzentrum.check_backup() is None
    assert kontrollzentrum.check_backup_offsite() is None


def test_check_backup_frisch_ist_ok(monkeypatch, tmp_path):
    (tmp_path / 'openmyconet-2026-09-06-020000.db.gz').write_bytes(b'x' * 100)
    monkeypatch.setattr(kontrollzentrum, 'BACKUP_DIR', str(tmp_path))
    status, detail = kontrollzentrum.check_backup()
    assert status == 'ok'
    assert '1 Backups' in detail


def test_check_backup_veraltet_ist_fehler(monkeypatch, tmp_path):
    import os
    import time
    f = tmp_path / 'openmyconet-alt.db.gz'
    f.write_bytes(b'x')
    alt = time.time() - 40 * 3600
    os.utime(f, (alt, alt))
    monkeypatch.setattr(kontrollzentrum, 'BACKUP_DIR', str(tmp_path))
    status, _ = kontrollzentrum.check_backup()
    assert status == 'fehler'


def test_check_backup_leer_ist_fehler(monkeypatch, tmp_path):
    monkeypatch.setattr(kontrollzentrum, 'BACKUP_DIR', str(tmp_path))
    status, detail = kontrollzentrum.check_backup()
    assert status == 'fehler'
    assert 'Kein Backup' in detail


# --- Trigger-Routen ---

def test_backup_jetzt_nur_superadmin(client, editor):
    r = client.post('/admin/backup/jetzt', follow_redirects=False)
    assert r.status_code == 302  # nicht eingeloggt -> login
    eingeloggt(client, 'editor_test', 'auch-geheim-123')
    r = client.post('/admin/backup/jetzt', follow_redirects=False)
    assert r.status_code == 403


def test_backup_jetzt_ruft_skript_und_flasht(client, superadmin, monkeypatch):
    aufrufe = []

    def fake_run(cmd, **kw):
        aufrufe.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout='Backup ok: xy.db.gz\n', stderr='')

    monkeypatch.setattr(admin.subprocess, 'run', fake_run)
    monkeypatch.setattr('os.path.isfile', lambda p: True)

    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    r = client.post('/admin/backup/jetzt', follow_redirects=True)
    assert r.status_code == 200
    assert aufrufe and aufrufe[0][0] == '/bin/bash'
    assert 'backup_db.sh' in aufrufe[0][1]
    assert 'DB-Backup ok' in r.get_data(as_text=True)


def test_restore_check_route_meldet_fehlercode(client, superadmin, monkeypatch):
    def fake_run(cmd, **kw):
        return subprocess.CompletedProcess(cmd, 2, stdout='', stderr='integrity_check != ok\n')

    monkeypatch.setattr(admin.subprocess, 'run', fake_run)
    monkeypatch.setattr('os.path.isfile', lambda p: True)

    eingeloggt(client, 'superadmin_test', 'sehr-geheim-123')
    r = client.post('/admin/backup/restore-check', follow_redirects=True)
    assert 'Restore-Check FEHLGESCHLAGEN' in r.get_data(as_text=True)
