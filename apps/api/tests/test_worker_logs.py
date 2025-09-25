"""Worker logs must not include email or reset tokens. Console OTP is explicit."""

import asyncio
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet


class _Smtp:
    sent: list[str] = []

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        return None

    def __enter__(self) -> "_Smtp":
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def send_message(self, message: object) -> None:
        get_content = getattr(message, "get_content", None)
        if callable(get_content):
            _Smtp.sent.append(str(get_content()))
        else:
            _Smtp.sent.append(str(message))


def _settings(provider: str) -> SimpleNamespace:
    return SimpleNamespace(
        smtp_host="localhost",
        smtp_port=1025,
        smtp_from="store@localhost",
        public_web_url="http://localhost:3000",
        sms_provider=provider,
        redis_url="redis://localhost:6379/0",
        secret_key="test-secret",
        database_url="postgresql+asyncpg://store:store@localhost/store",
        totp_encryption_key=Fernet.generate_key().decode(),
    )


@pytest.fixture
def worker(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-unit-tests")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://store:store@localhost/store")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("TOTP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    from app.config import get_settings

    get_settings.cache_clear()
    import app.worker as worker_module

    yield worker_module
    get_settings.cache_clear()


def test_email_jobs_do_not_log_tokens(
    worker: object,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(worker, "get_settings", lambda: _settings("console"))
    worker.setup_logging()
    monkeypatch.setattr(worker.smtplib, "SMTP", _Smtp)
    _Smtp.sent.clear()
    token = "verify-token-should-not-be-logged"
    reset = "reset-token-should-not-be-logged"
    invite = "invite-token-should-not-be-logged"
    asyncio.run(worker.send_verification_email({"job_id": "j1"}, "a@example.com", token))
    asyncio.run(worker.send_password_reset_email({"job_id": "j2"}, "a@example.com", reset))
    asyncio.run(worker.send_staff_invite_email({"job_id": "j3"}, "a@example.com", invite))
    captured = capsys.readouterr().out
    assert token not in captured
    assert reset not in captured
    assert invite not in captured
    assert "verification_email_sent" in captured
    assert "password_reset_email_sent" in captured
    mailed = "\n".join(_Smtp.sent)
    assert token in mailed
    assert reset in mailed
    assert invite in mailed


def test_console_sms_logs_otp_and_other_providers_do_not(
    worker: object,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(worker, "get_settings", lambda: _settings("console"))
    worker.setup_logging()
    asyncio.run(worker.send_phone_otp({"job_id": "j4"}, "+8801711111111", "123456"))
    console_out = capsys.readouterr().out
    assert "DEV ONLY" in console_out
    assert "123456" in console_out

    monkeypatch.setattr(worker, "get_settings", lambda: _settings("none"))
    with pytest.raises(RuntimeError):
        asyncio.run(worker.send_phone_otp({"job_id": "j5"}, "+8801711111111", "654321"))
    other = capsys.readouterr().out
    assert "654321" not in other
    assert "sms_provider_unsupported" in other
