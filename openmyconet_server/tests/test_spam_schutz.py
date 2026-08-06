"""Testet die echte Rate-Limit-Logik selbst (in den anderen Testdateien wird
sie bewusst per Fixture umgangen, siehe conftest.py)."""

import spam_schutz


def test_rate_limit_greift_nach_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(spam_schutz, 'RATE_DIR', str(tmp_path))

    for _ in range(3):
        assert spam_schutz.ip_erlaubt('192.0.2.1', 'testkey', limit=3, window=3600) is True

    assert spam_schutz.ip_erlaubt('192.0.2.1', 'testkey', limit=3, window=3600) is False


def test_rate_limit_pro_ip_getrennt(tmp_path, monkeypatch):
    monkeypatch.setattr(spam_schutz, 'RATE_DIR', str(tmp_path))

    for _ in range(2):
        spam_schutz.ip_erlaubt('192.0.2.1', 'testkey', limit=2, window=3600)
    assert spam_schutz.ip_erlaubt('192.0.2.1', 'testkey', limit=2, window=3600) is False

    # andere IP hat ein eigenes, noch unverbrauchtes Kontingent
    assert spam_schutz.ip_erlaubt('192.0.2.2', 'testkey', limit=2, window=3600) is True
