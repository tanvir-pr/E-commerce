"""Week 2 rules: second factor, policy, reset, and phone OTP."""

from datetime import UTC, datetime
from uuid import uuid4

import pyotp
import pytest
from app.auth.phone_service import PhoneService
from app.auth.service import AuthService
from app.problems import ProblemError
from app.records import REGISTER_MESSAGE, RESET_MESSAGE
from app.security.passwords import hash_password
from app.security.policy import Access, Actor, decide, require_self
from app.security.tokens import hash_token
from app.users.service import UserService
from cryptography.fernet import Fernet
from tests.fakes import (
    FakeAudit,
    FakeLimiter,
    FakeMailer,
    FakeOpaqueTokens,
    FakePhoneChallenges,
    FakeRecovery,
    FakeRefreshes,
    FakeSms,
    FakeUsers,
    FakeVerifications,
)

PASSWORD = "password12345"
SUPPORT = Access(
    roles=frozenset({"staff", "super_admin"}),
    permission="support",
    require_totp=True,
)


def build() -> tuple[AuthService, FakeUsers, FakeRefreshes, FakeMailer, FakeRecovery, FakeAudit]:
    users = FakeUsers()
    refreshes = FakeRefreshes()
    mailer = FakeMailer()
    audit = FakeAudit()
    recovery = FakeRecovery()
    service = AuthService(
        users=users,
        verifications=FakeVerifications(),
        refreshes=refreshes,
        audit=audit,
        mailer=mailer,
        limiter=FakeLimiter(),
        secret="test-secret-key-for-unit-tests",
        breach_mode="stub",
        recovery=recovery,
        resets=FakeOpaqueTokens(),
        invites=FakeOpaqueTokens(),
        reset_limiter=FakeLimiter(),
        totp_key=Fernet.generate_key().decode(),
    )
    return service, users, refreshes, mailer, recovery, audit


def _actor(roles: set[str], permissions: set[str], *, totp: bool = True) -> Actor:
    return Actor(
        user_id=uuid4(),
        roles=frozenset(roles),
        permissions=frozenset(permissions),
        totp_enabled=totp,
    )


@pytest.mark.asyncio
async def test_wrong_totp_does_not_issue_a_session() -> None:
    service, users, refreshes, _mailer, _recovery, _audit = build()
    await users.add("staff@example.com", hash_password(PASSWORD))
    user = users.by_email["staff@example.com"]
    await users.assign_role(user.id, "staff")
    secret = pyotp.random_base32()
    from app.security.totp import encrypt_secret

    user.totp_secret_ciphertext = encrypt_secret(secret, service.totp_key)
    user.totp_confirmed_at = datetime.now(UTC)
    result = await service.login("staff@example.com", PASSWORD, "10.0.0.8", None)
    assert result.next_step == "challenge"
    assert result.tokens is None
    assert refreshes.rows == []

    with pytest.raises(ProblemError) as wrong:
        await service.finish_challenge(user.id, "000000", None)
    assert wrong.value.status == 401
    assert refreshes.rows == []


@pytest.mark.asyncio
async def test_recovery_code_is_single_use() -> None:
    service, users, refreshes, _mailer, recovery, _audit = build()
    await users.add("staff@example.com", hash_password(PASSWORD))
    user = users.by_email["staff@example.com"]
    await users.assign_role(user.id, "staff")
    started = await service.start_totp_setup(user.id)
    assert user.totp_pending_ciphertext is not None
    assert started.secret not in user.totp_pending_ciphertext
    confirmed = await service.confirm_totp(
        user.id,
        pyotp.TOTP(started.secret).now(),
        None,
        issue_session=False,
    )
    assert confirmed.tokens is None
    assert len(confirmed.recovery_codes) == 10
    raw = confirmed.recovery_codes[0]
    assert all(row.code_hash != raw for row in recovery.rows)
    assert refreshes.rows == []

    first = await service.finish_challenge(user.id, raw, None)
    assert first.access_token
    assert len(refreshes.rows) == 1
    with pytest.raises(ProblemError) as second:
        await service.finish_challenge(user.id, raw, None)
    assert second.value.status == 401
    assert len(refreshes.rows) == 1


@pytest.mark.asyncio
async def test_privileged_login_without_enrollment_does_not_open_a_session() -> None:
    service, users, refreshes, _mailer, _recovery, _audit = build()
    await service.register("owner@example.com", PASSWORD, None)
    user = users.by_email["owner@example.com"]
    await users.assign_role(user.id, "super_admin")
    result = await service.login("owner@example.com", PASSWORD, "10.0.0.8", None)
    assert result.next_step == "enroll"
    assert result.tokens is None
    assert result.ticket
    assert refreshes.rows == []


def test_customer_cannot_pass_staff_policy() -> None:
    customer = _actor({"customer"}, set())
    assert decide(customer, SUPPORT) is False


def test_warehouse_cannot_pass_support_policy() -> None:
    warehouse = _actor({"staff"}, {"warehouse"})
    assert decide(warehouse, SUPPORT) is False
    support = _actor({"staff"}, {"support"})
    assert decide(support, SUPPORT) is True


def test_customer_cannot_read_another_customer() -> None:
    owner = uuid4()
    other = uuid4()
    with pytest.raises(ProblemError) as denied:
        require_self(owner, other)
    assert denied.value.status == 403
    require_self(owner, owner)


def test_super_admin_without_totp_cannot_pass_admin_policy() -> None:
    access = Access(roles=frozenset({"super_admin"}), permission=None, require_totp=True)
    owner = _actor({"super_admin"}, set(), totp=False)
    assert decide(owner, access) is False
    enrolled = _actor({"super_admin"}, set(), totp=True)
    assert decide(enrolled, access) is True


@pytest.mark.asyncio
async def test_password_reset_is_single_use() -> None:
    service, users, _refreshes, mailer, _recovery, _audit = build()
    await service.register("person@example.com", PASSWORD, None)
    await service.request_password_reset("person@example.com", "10.0.0.8", None)
    raw = mailer.resets[0][1]
    stored = service.resets
    assert stored is not None
    assert stored.rows[0].token_hash == hash_token(raw)
    assert stored.rows[0].token_hash != raw
    await service.reset_password(raw, "new-password-99", None)
    with pytest.raises(ProblemError) as second:
        await service.reset_password(raw, "another-password-99", None)
    assert second.value.status == 400
    signed_in = await service.login("person@example.com", "new-password-99", "10.0.0.8", None)
    assert signed_in.tokens is not None
    with pytest.raises(ProblemError):
        await service.login("person@example.com", PASSWORD, "10.0.0.8", None)
    assert users.by_email["person@example.com"].password_hash != hash_password(PASSWORD)


@pytest.mark.asyncio
async def test_register_and_reset_responses_do_not_reveal_the_account() -> None:
    service, _users, _refreshes, mailer, _recovery, _audit = build()
    first = await service.register("person@example.com", PASSWORD, None)
    second = await service.register("person@example.com", "different-password-9", None)
    assert first.message == second.message == REGISTER_MESSAGE
    missing = await service.request_password_reset("missing@example.com", "10.0.0.8", None)
    found = await service.request_password_reset("person@example.com", "10.0.0.8", None)
    assert missing == found == RESET_MESSAGE
    assert len(mailer.resets) == 1
    assert len(mailer.sent) == 1


@pytest.mark.asyncio
async def test_phone_otp_attempt_limit_and_duplicate_response() -> None:
    users = FakeUsers()
    challenges = FakePhoneChallenges()
    sms = FakeSms()
    service = PhoneService(
        users=users,
        challenges=challenges,
        sms=sms,
        limiter=FakeLimiter(),
        audit=FakeAudit(),
        breach_mode="stub",
        max_attempts=3,
    )
    phone = "+8801711111111"
    with pytest.raises(ProblemError) as disabled:
        await service.start(phone, PASSWORD, "Ada", "10.0.0.8", enabled=False)
    assert disabled.value.status == 403

    await service.start(phone, PASSWORD, "Ada", "10.0.0.8", enabled=True)
    assert len(sms.sent) == 1
    code = sms.sent[0][1]
    assert challenges.rows[0].code_hash != code
    assert challenges.rows[0].code_hash == hash_token(code)
    for _ in range(3):
        with pytest.raises(ProblemError):
            await service.confirm(phone, "000000", None, enabled=True)
    with pytest.raises(ProblemError):
        await service.confirm(phone, code, None, enabled=True)
    assert users.by_phone == {}

    fresh = FakePhoneChallenges()
    fresh_sms = FakeSms()
    ok = PhoneService(
        users=users,
        challenges=fresh,
        sms=fresh_sms,
        limiter=FakeLimiter(),
        audit=FakeAudit(),
        breach_mode="stub",
        max_attempts=3,
    )
    started = await ok.start(phone, PASSWORD, "Ada", "10.0.0.8", enabled=True)
    await ok.confirm(phone, fresh_sms.sent[0][1], None, enabled=True)
    duplicate = await ok.start(phone, PASSWORD, "Ada", "10.0.0.8", enabled=True)
    assert started == duplicate
    assert len(fresh_sms.sent) == 1


@pytest.mark.asyncio
async def test_profile_name_update_leaves_verification_timestamps() -> None:
    users = FakeUsers()
    await users.add("person@example.com", hash_password(PASSWORD))
    user = users.by_email["person@example.com"]
    verified = datetime(2024, 1, 1, tzinfo=UTC)
    user.email_verified_at = verified
    user.phone_verified_at = verified
    service = UserService(users)
    updated = await service.update_name(user.id, "Ada Lovelace")
    assert updated.name == "Ada Lovelace"
    assert updated.email_verified_at == verified
    assert updated.phone_verified_at == verified


@pytest.mark.asyncio
async def test_delete_me_keeps_audit_rows_and_revokes_sessions() -> None:
    users = FakeUsers()
    refreshes = FakeRefreshes()
    audit = FakeAudit()
    await users.add("person@example.com", hash_password(PASSWORD))
    user = users.by_email["person@example.com"]
    await audit.record(
        actor_id=user.id,
        action="login_success",
        entity_type="user",
        entity_id=user.id,
        metadata={},
        request_id=None,
    )
    from app.ids import new_id
    from app.records import RefreshRecord

    now = datetime.now(UTC)
    await refreshes.add(
        RefreshRecord(
            id=new_id(),
            user_id=user.id,
            family_id=new_id(),
            token_hash="abc",
            expires_at=datetime(2099, 1, 1, tzinfo=UTC),
            revoked_at=None,
            replaced_by_id=None,
            created_at=now,
        )
    )
    await UserService(users).delete_me(user.id, refreshes, audit, None)
    assert user.deleted_at is not None
    assert refreshes.rows[0].revoked_at is not None
    assert [row["action"] for row in audit.rows] == [
        "login_success",
        "account_deletion_requested",
    ]
