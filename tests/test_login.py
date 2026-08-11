"""Unit tests for QR login — fake QR + fake Telethon client, no network."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import login


class _FakeQR:
    def __init__(self, wait_outcomes):
        # Each entry is either an exception to raise on wait(), or None to succeed.
        self._wait_outcomes = list(wait_outcomes)
        self.url = "tg://login?token=fake"
        self.expires = datetime.now(timezone.utc) + timedelta(seconds=30)
        self.recreate_calls = 0

    def wait(self, timeout=None):
        return ("wait", self._wait_outcomes.pop(0))

    def recreate(self):
        self.recreate_calls += 1
        self.expires = datetime.now(timezone.utc) + timedelta(seconds=30)
        return ("recreate", None)


class _FakeLoop:
    def run_until_complete(self, marker):
        kind, outcome = marker
        if kind == "wait" and outcome is not None:
            raise outcome
        return None


class _FakeClient:
    def __init__(self, qr):
        self._qr = qr
        self.loop = _FakeLoop()
        self.disconnected = False
        self.sign_in_calls = []

    def qr_login(self):
        return self._qr

    def sign_in(self, password=None):
        self.sign_in_calls.append(password)

    def disconnect(self):
        self.disconnected = True


def test_qr_login_returns_on_first_successful_scan():
    qr = _FakeQR([None])
    client = _FakeClient(qr)

    login._qr_login(client)

    assert qr.recreate_calls == 0
    assert client.disconnected is False


def test_qr_login_refreshes_after_expiry_then_succeeds():
    qr = _FakeQR([asyncio.TimeoutError(), None])
    client = _FakeClient(qr)

    login._qr_login(client)

    assert qr.recreate_calls == 1
    assert client.disconnected is False


def test_qr_login_gives_up_after_max_refreshes(monkeypatch):
    monkeypatch.setattr(login, "_QR_MAX_REFRESHES", 3)
    qr = _FakeQR([asyncio.TimeoutError()] * 3)
    client = _FakeClient(qr)

    with pytest.raises(SystemExit):
        login._qr_login(client)

    assert qr.recreate_calls == 3
    assert client.disconnected is True


def test_qr_login_retries_2fa_on_invalid_password(monkeypatch):
    qr = _FakeQR([login.errors.SessionPasswordNeededError(request=None)])
    client = _FakeClient(qr)
    attempts = []

    def sign_in(password=None):
        attempts.append(password)
        if len(attempts) == 1:
            raise login.errors.PasswordHashInvalidError(request=None)

    client.sign_in = sign_in
    entered = iter(["wrong", "right"])
    monkeypatch.setattr("getpass.getpass", lambda prompt: next(entered))

    login._qr_login(client)

    assert attempts == ["wrong", "right"]
