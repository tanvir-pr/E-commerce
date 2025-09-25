"""Service-level auth rules. No database required."""

from datetime import UTC, datetime

import pytest
from app.auth.service import AuthService
from app.email_content import build_verification_url, verification_email_body
from app.problems import ProblemError
from app.records import REGISTER_MESSAGE
from app.scripts.seed_superadmin import PLACEHOLDER_SEED_PASSWORD, SeedRefused, ensure_seed_allowed
from app.security.passwords import hash_password, password_is_breached
from app.security.tokens import generate_opaque_token, hash_token
from tests.fakes import (
    FakeAudit,
    FakeLimiter,
    FakeMailer,
    FakeRefreshes,
    FakeUsers,
    FakeVerifications,
)

PASSWORD = "password12345"


def build() -> tuple[
    AuthService, FakeUsers, FakeVerifications, FakeRefreshes, FakeMailer, FakeAudit
]:
    users = FakeUsers()
    verifications = FakeVerifications()
    refreshes = FakeRefreshes()
    mailer = FakeMailer()
    audit = FakeAudit()
    service = AuthService(
        users=users,
        verifications=verifications,
        refreshes=refreshes,
        audit=audit,
        mailer=mailer,
        limiter=FakeLimiter(),
        secret="test-secret-key-for-unit-tests",
        breach_mode="stub",
    )
    return service, users, verifications, refreshes, mailer, audit


@pytest.mark.asyncio
async def test_verification_token_is_hashed_and_single_use() -> None:
    service, users, verifications, _refreshes, mailer, _audit = build()
    await service.register("Person@Example.com", PASSWORD, "req-1")
    assert len(mailer.sent) == 1
    raw = mailer.sent[0][1]
    assert len(verifications.rows) == 1
    stored = verifications.rows[0]
    assert stored.token_hash != raw
    assert stored.token_hash == hash_token(raw)

    await service.verify_email(raw, "req-2")
    user = users.by_email["person@example.com"]
    assert user.email_verified_at is not None
    assert stored.used_at is not None

    with pytest.raises(ProblemError) as second:
        await service.verify_email(raw, "req-3")
    assert second.value.status == 400
    assert stored.used_at is not None


@pytest.mark.asyncio
async def test_expired_verification_is_rejected() -> None:
    service, users, verifications, _refreshes, mailer, _audit = build()
    await service.register("person@example.com", PASSWORD, None)
    verifications.rows[0].expires_at = datetime(2000, 1, 1, tzinfo=UTC)
    with pytest.raises(ProblemError):
        await service.verify_email(mailer.sent[0][1], None)
    assert verifications.rows[0].used_at is None
    assert users.by_email["person@example.com"].email_verified_at is None


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_same_body() -> None:
    service, users, verifications, _refreshes, mailer, _audit = build()
    first = await service.register("A@Example.com", PASSWORD, None)
    stored_hash = users.by_email["a@example.com"].password_hash
    second = await service.register("a@example.com", "different-password-9", None)
    assert first == second
    assert first.message == REGISTER_MESSAGE
    assert second.message == REGISTER_MESSAGE
    assert len(mailer.sent) == 1
    assert len(verifications.rows) == 1
    assert users.by_email["a@example.com"].password_hash == stored_hash


@pytest.mark.asyncio
async def test_refresh_reuse_revokes_family() -> None:
    service, _users, _verifications, refreshes, _mailer, _audit = build()
    await service.register("person@example.com", PASSWORD, None)
    issued = await service.login("person@example.com", PASSWORD, "127.0.0.1", None)
    assert issued.tokens is not None
    rotated = await service.refresh(issued.tokens.refresh_token, None)
    assert rotated.refresh_token != issued.tokens.refresh_token
    assert all(row.token_hash != issued.tokens.refresh_token for row in refreshes.rows)
    assert any(row.token_hash == hash_token(issued.tokens.refresh_token) for row in refreshes.rows)

    with pytest.raises(ProblemError) as reused:
        await service.refresh(issued.tokens.refresh_token, "req-reuse")
    assert reused.value.status == 401
    assert all(row.revoked_at is not None for row in refreshes.rows)

    with pytest.raises(ProblemError):
        await service.refresh(rotated.refresh_token, None)


@pytest.mark.asyncio
async def test_login_errors_are_generic() -> None:
    service, users, _verifications, _refreshes, _mailer, _audit = build()
    await users.add("person@example.com", hash_password(PASSWORD))
    with pytest.raises(ProblemError) as unknown:
        await service.login("missing@example.com", PASSWORD, "10.0.0.8", None)
    with pytest.raises(ProblemError) as wrong:
        await service.login("person@example.com", "not-the-password", "10.0.0.8", None)
    assert unknown.value.status == wrong.value.status == 401
    assert unknown.value.title == wrong.value.title
    assert unknown.value.detail == wrong.value.detail
    assert unknown.value.detail == "Invalid email or password."


@pytest.mark.asyncio
async def test_register_persists_before_sending_mail() -> None:
    service, _users, _verifications, _refreshes, _mailer, _audit = build()
    order: list[str] = []

    class OrderedMailer:
        async def send_verification(self, email: str, token: str) -> None:
            del email, token
            order.append("mail")

    async def before_mail() -> None:
        order.append("commit")

    service.mailer = OrderedMailer()
    await service.register("person@example.com", PASSWORD, None, before_mail=before_mail)
    assert order == ["commit", "mail"]


def test_breach_stub_returns_false() -> None:
    assert password_is_breached("any-password-10", "stub") is False


def test_token_hash_is_sha256() -> None:
    raw, digest = generate_opaque_token()
    assert raw != digest
    assert digest == hash_token(raw)


def test_verification_email_url() -> None:
    url = build_verification_url("http://localhost:3000/", "abc_DEF-123")
    assert url == "http://localhost:3000/en/verify-email?token=abc_DEF-123"
    assert url in verification_email_body(url)


def test_seed_refuses_placeholder_in_production() -> None:
    with pytest.raises(SeedRefused):
        ensure_seed_allowed("production", PLACEHOLDER_SEED_PASSWORD)


def test_seed_allows_local_placeholder_and_custom_production_password() -> None:
    ensure_seed_allowed("local", PLACEHOLDER_SEED_PASSWORD)
    ensure_seed_allowed("production", "a-real-password-1")
