"""Register, verify, login, second factor, reset, refresh, and logout rules."""

import secrets
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

import structlog

from app.clock import utc_now
from app.ids import new_id
from app.ports import (
    AuditWriter,
    Mailer,
    OpaqueTokenStore,
    RateLimiter,
    RecoveryStore,
    RefreshStore,
    UserStore,
    VerificationStore,
)
from app.problems import (
    PROBLEM_CONFLICT,
    PROBLEM_CREDENTIALS,
    PROBLEM_FORBIDDEN,
    PROBLEM_INTERNAL,
    PROBLEM_RESET,
    PROBLEM_SECOND_FACTOR,
    PROBLEM_SESSION,
    PROBLEM_VERIFY,
    DuplicateEmailError,
    ProblemError,
    RoleMissingError,
)
from app.records import (
    CHALLENGE_MESSAGE,
    ENROLL_MESSAGE,
    INVALID_CODE,
    INVALID_CREDENTIALS,
    INVALID_RESET,
    INVALID_SESSION,
    INVALID_VERIFICATION,
    INVITE_ACCEPTED_MESSAGE,
    PASSWORD_UPDATED_MESSAGE,
    REGISTER_MESSAGE,
    RESET_MESSAGE,
    TOTP_DISABLED_MESSAGE,
    TOTP_ENABLED_MESSAGE,
    LoginResult,
    RefreshRecord,
    RegisterOutcome,
    SessionView,
    TokenPair,
    TotpConfirmResult,
    TotpSetupResult,
    UserRecord,
)
from app.security.passwords import ensure_password_allowed, hash_password, verify_password
from app.security.tokens import (
    encode_access_token,
    encode_ticket,
    generate_opaque_token,
    hash_token,
)
from app.security.totp import (
    decrypt_secret,
    encrypt_secret,
    generate_recovery_codes,
    new_totp_secret,
    provisioning_uri,
    qr_svg,
    recovery_digest,
    verify_totp,
)

log = structlog.get_logger()


def normalize_email(email: str) -> str:
    return email.strip().lower()


class AuthService:
    def __init__(
        self,
        users: UserStore,
        verifications: VerificationStore,
        refreshes: RefreshStore,
        audit: AuditWriter,
        mailer: Mailer,
        limiter: RateLimiter,
        *,
        secret: str,
        breach_mode: str,
        access_minutes: int = 15,
        refresh_days: int = 14,
        verification_minutes: int = 30,
        clock: Callable[[], datetime] = utc_now,
        recovery: RecoveryStore | None = None,
        resets: OpaqueTokenStore | None = None,
        invites: OpaqueTokenStore | None = None,
        reset_limiter: RateLimiter | None = None,
        totp_key: str = "",
        ticket_minutes: int = 5,
        reset_minutes: int = 30,
        invite_hours: int = 24,
    ) -> None:
        self.users = users
        self.verifications = verifications
        self.refreshes = refreshes
        self.audit = audit
        self.mailer = mailer
        self.limiter = limiter
        self.secret = secret
        self.breach_mode = breach_mode
        self.access_minutes = access_minutes
        self.refresh_days = refresh_days
        self.verification_minutes = verification_minutes
        self.clock = clock
        self.recovery = recovery
        self.resets = resets
        self.invites = invites
        self.reset_limiter = reset_limiter or limiter
        self.totp_key = totp_key
        self.ticket_minutes = ticket_minutes
        self.reset_minutes = reset_minutes
        self.invite_hours = invite_hours

    async def register(
        self,
        email: str,
        password: str,
        request_id: str | None,
        before_mail: Callable[[], Awaitable[None]] | None = None,
    ) -> RegisterOutcome:
        normalized = normalize_email(email)
        ensure_password_allowed(password, self.breach_mode)
        password_hash = hash_password(password)
        existing = await self.users.get_by_email(normalized)
        if existing is not None:
            await self._audit_register(None, request_id, "ignored")
            return RegisterOutcome(REGISTER_MESSAGE)
        try:
            user = await self.users.add(normalized, password_hash)
        except DuplicateEmailError:
            await self._audit_register(None, request_id, "ignored")
            return RegisterOutcome(REGISTER_MESSAGE)
        try:
            await self.users.assign_role(user.id, "customer")
        except RoleMissingError as exc:
            raise ProblemError(
                500,
                "Internal Server Error",
                "Something went wrong.",
                PROBLEM_INTERNAL,
            ) from exc
        raw, digest = generate_opaque_token()
        expires = self.clock() + timedelta(minutes=self.verification_minutes)
        await self.verifications.add(user.id, digest, expires)
        await self._audit_register(user.id, request_id, "created")
        if before_mail is not None:
            await before_mail()
        await self.mailer.send_verification(normalized, raw)
        return RegisterOutcome(REGISTER_MESSAGE)

    async def verify_email(self, raw_token: str, request_id: str | None) -> None:
        now = self.clock()
        record = await self.verifications.get_by_hash(hash_token(raw_token))
        if record is None or record.used_at is not None or record.expires_at <= now:
            raise self._invalid_verification()
        used = await self.verifications.mark_used(record.id, now)
        if not used:
            raise self._invalid_verification()
        await self.users.mark_email_verified(record.user_id, now)
        await self.audit.record(
            actor_id=record.user_id,
            action="email_verified",
            entity_type="user",
            entity_id=record.user_id,
            metadata={},
            request_id=request_id,
        )

    async def login(
        self,
        email: str,
        password: str,
        ip: str,
        request_id: str | None,
    ) -> LoginResult:
        normalized = normalize_email(email)
        await self.limiter.check(ip, normalized)
        user = await self.users.get_by_email(normalized)
        return await self._password_gate(user, password, request_id)

    async def login_phone(
        self,
        phone: str,
        password: str,
        ip: str,
        request_id: str | None,
        *,
        enabled: bool,
    ) -> LoginResult:
        if not enabled:
            raise _phone_disabled()
        from app.auth.phone_service import normalize_phone

        normalized = normalize_phone(phone)
        await self.limiter.check(ip, normalized)
        user = await self.users.get_by_phone(normalized)
        return await self._password_gate(user, password, request_id)

    async def refresh(self, refresh_raw: str | None, request_id: str | None) -> TokenPair:
        if not refresh_raw:
            raise self._invalid_session()
        current = await self.refreshes.get_by_hash(hash_token(refresh_raw))
        if current is None:
            raise self._invalid_session()
        now = self.clock()
        if current.revoked_at is not None or current.replaced_by_id is not None:
            await self.refreshes.revoke_family(current.family_id, now)
            log.warning(
                "refresh_token_reuse",
                family_id=str(current.family_id),
                audit_request_id=request_id,
            )
            raise self._invalid_session()
        if current.expires_at <= now:
            raise self._invalid_session()
        user = await self.users.get_by_id(current.user_id)
        if user is None or user.deleted_at is not None:
            raise self._invalid_session()
        return await self._rotate(current, now)

    async def logout(self, refresh_raw: str | None, request_id: str | None) -> None:
        if not refresh_raw:
            return
        current = await self.refreshes.get_by_hash(hash_token(refresh_raw))
        if current is None:
            return
        await self.refreshes.revoke_family(current.family_id, self.clock())
        await self.audit.record(
            actor_id=current.user_id,
            action="logout",
            entity_type="user",
            entity_id=current.user_id,
            metadata={},
            request_id=request_id,
        )

    async def list_sessions(self, user_id: UUID, refresh_raw: str | None) -> list[SessionView]:
        now = self.clock()
        current_family: UUID | None = None
        if refresh_raw:
            current = await self.refreshes.get_by_hash(hash_token(refresh_raw))
            if (
                current is not None
                and current.user_id == user_id
                and current.revoked_at is None
                and current.expires_at > now
            ):
                current_family = current.family_id
        grouped: dict[UUID, list[RefreshRecord]] = {}
        for row in await self.refreshes.list_for_user(user_id):
            grouped.setdefault(row.family_id, []).append(row)
        views: list[SessionView] = []
        for family_id, members in grouped.items():
            active = [
                item
                for item in members
                if item.revoked_at is None and item.replaced_by_id is None and item.expires_at > now
            ]
            if not active:
                continue
            views.append(
                SessionView(
                    family_id=family_id,
                    created_at=min(item.created_at for item in members),
                    expires_at=max(item.expires_at for item in active),
                    current=family_id == current_family,
                )
            )
        views.sort(key=lambda item: item.created_at, reverse=True)
        return views

    async def logout_everywhere(self, user_id: UUID, request_id: str | None) -> None:
        await self.refreshes.revoke_all_for_user(user_id, self.clock())
        await self.audit.record(
            actor_id=user_id,
            action="logout_everywhere",
            entity_type="user",
            entity_id=user_id,
            metadata={},
            request_id=request_id,
        )

    async def request_password_reset(
        self,
        email: str,
        ip: str,
        request_id: str | None,
        before_mail: Callable[[], Awaitable[None]] | None = None,
    ) -> str:
        del request_id
        normalized = normalize_email(email)
        await self.reset_limiter.hit("reset", ip, normalized)
        user = await self.users.get_by_email(normalized)
        if user is None or user.deleted_at is not None:
            return RESET_MESSAGE
        raw, digest = generate_opaque_token()
        expires = self.clock() + timedelta(minutes=self.reset_minutes)
        await self._resets().add(user.id, digest, expires)
        if before_mail is not None:
            await before_mail()
        await self.mailer.send_password_reset(normalized, raw)
        return RESET_MESSAGE

    async def reset_password(self, raw_token: str, password: str, request_id: str | None) -> None:
        now = self.clock()
        record = await self._resets().get_by_hash(hash_token(raw_token))
        if record is None or record.used_at is not None or record.expires_at <= now:
            raise self._invalid_reset()
        used = await self._resets().mark_used(record.id, now)
        if not used:
            raise self._invalid_reset()
        ensure_password_allowed(password, self.breach_mode)
        await self.users.set_password_hash(record.user_id, hash_password(password), now)
        await self.refreshes.revoke_all_for_user(record.user_id, now)
        await self.audit.record(
            actor_id=record.user_id,
            action="password_reset_completed",
            entity_type="user",
            entity_id=record.user_id,
            metadata={},
            request_id=request_id,
        )

    async def accept_invite(self, raw_token: str, password: str, request_id: str | None) -> None:
        now = self.clock()
        record = await self._invites().get_by_hash(hash_token(raw_token))
        if record is None or record.used_at is not None or record.expires_at <= now:
            raise self._invalid_reset()
        used = await self._invites().mark_used(record.id, now)
        if not used:
            raise self._invalid_reset()
        ensure_password_allowed(password, self.breach_mode)
        await self.users.set_password_hash(record.user_id, hash_password(password), now)
        await self.users.mark_email_verified(record.user_id, now)
        await self.audit.record(
            actor_id=record.user_id,
            action="staff_invite_accepted",
            entity_type="user",
            entity_id=record.user_id,
            metadata={},
            request_id=request_id,
        )

    async def start_totp_setup(self, user_id: UUID) -> TotpSetupResult:
        user = await self._live_user(user_id)
        secret = new_totp_secret()
        ciphertext = encrypt_secret(secret, self._totp_key())
        await self.users.set_totp_pending(user_id, ciphertext)
        label = user.email or user.phone or str(user.id)
        uri = provisioning_uri(secret, label)
        return TotpSetupResult(secret=secret, otpauth_uri=uri, qr_svg=qr_svg(uri))

    async def confirm_totp(
        self,
        user_id: UUID,
        code: str,
        request_id: str | None,
        *,
        issue_session: bool,
    ) -> TotpConfirmResult:
        user = await self._live_user(user_id)
        pending = user.totp_pending_ciphertext
        if not pending:
            raise ProblemError(
                400,
                "Bad Request",
                "Two-factor setup has not been started.",
                PROBLEM_SECOND_FACTOR,
            )
        try:
            secret = decrypt_secret(pending, self._totp_key())
        except ValueError:
            log.error("totp_decrypt_failed")
            raise self._invalid_code() from None
        if not verify_totp(secret, code):
            await self._audit_second_factor(user.id, request_id, False)
            raise self._invalid_code()
        now = self.clock()
        await self.users.confirm_totp(user.id, pending, now)
        pairs = generate_recovery_codes(10)
        await self._recovery().replace(user.id, [digest for _display, digest in pairs], now)
        await self.audit.record(
            actor_id=user.id,
            action="totp_enrolled",
            entity_type="user",
            entity_id=user.id,
            metadata={},
            request_id=request_id,
        )
        tokens = await self._open_session(user.id, request_id) if issue_session else None
        return TotpConfirmResult(
            recovery_codes=[display for display, _digest in pairs], tokens=tokens
        )

    async def finish_challenge(self, user_id: UUID, code: str, request_id: str | None) -> TokenPair:
        user = await self._live_user(user_id)
        if user.totp_confirmed_at is None or not user.totp_secret_ciphertext:
            await self._audit_second_factor(user.id, request_id, False)
            raise self._invalid_code()
        matched = await self._code_matches(user, code, consume_recovery=True)
        if not matched:
            await self._audit_second_factor(user.id, request_id, False)
            raise self._invalid_code()
        return await self._open_session(user.id, request_id)

    async def disable_totp(self, user_id: UUID, code: str, request_id: str | None) -> None:
        user = await self._live_user(user_id)
        roles = await self.users.list_roles(user.id)
        if "staff" in roles or "super_admin" in roles:
            raise ProblemError(
                403,
                "Forbidden",
                "Two-factor authentication is required for this account.",
                PROBLEM_FORBIDDEN,
            )
        if user.totp_confirmed_at is None:
            raise ProblemError(
                400,
                "Bad Request",
                "Two-factor authentication is not on.",
                PROBLEM_SECOND_FACTOR,
            )
        if not await self._code_matches(user, code, consume_recovery=True):
            raise self._invalid_code()
        await self.users.clear_totp(user.id)
        await self._recovery().delete_all(user.id)
        await self.audit.record(
            actor_id=user.id,
            action="totp_disabled",
            entity_type="user",
            entity_id=user.id,
            metadata={},
            request_id=request_id,
        )

    async def _password_gate(
        self,
        user: UserRecord | None,
        password: str,
        request_id: str | None,
    ) -> LoginResult:
        password_ok = verify_password(password, user.password_hash if user else None)
        active = user is not None and user.deleted_at is None and password_ok
        if user is None or not active:
            await self.audit.record(
                actor_id=user.id if user else None,
                action="login_failure",
                entity_type="user",
                entity_id=user.id if user else None,
                metadata={"result": "invalid_credentials"},
                request_id=request_id,
            )
            raise ProblemError(
                401,
                "Unauthorized",
                INVALID_CREDENTIALS,
                PROBLEM_CREDENTIALS,
            )
        assert user is not None
        roles = await self.users.list_roles(user.id)
        step = _second_factor_step(roles, user)
        if step is None:
            tokens = await self._open_session(user.id, request_id)
            return LoginResult(next_step="session", tokens=tokens)
        ticket = encode_ticket(user.id, self.secret, self.ticket_minutes, self.clock(), step)
        await self.audit.record(
            actor_id=user.id,
            action="login_password_accepted",
            entity_type="user",
            entity_id=user.id,
            metadata={"step": step},
            request_id=request_id,
        )
        return LoginResult(next_step=step, ticket=ticket)

    async def _code_matches(self, user: UserRecord, code: str, *, consume_recovery: bool) -> bool:
        ciphertext = user.totp_secret_ciphertext
        if ciphertext:
            try:
                secret = decrypt_secret(ciphertext, self._totp_key())
            except ValueError:
                log.error("totp_decrypt_failed")
                return False
            if verify_totp(secret, code):
                return True
        if not consume_recovery:
            return False
        return await self._recovery().use_matching(user.id, recovery_digest(code), self.clock())

    async def _open_session(self, user_id: UUID, request_id: str | None) -> TokenPair:
        pair = await self._issue(user_id)
        await self.audit.record(
            actor_id=user_id,
            action="login_success",
            entity_type="user",
            entity_id=user_id,
            metadata={},
            request_id=request_id,
        )
        return pair

    async def _issue(self, user_id: UUID) -> TokenPair:
        now = self.clock()
        raw, digest = generate_opaque_token()
        await self.refreshes.add(
            RefreshRecord(
                id=new_id(),
                user_id=user_id,
                family_id=new_id(),
                token_hash=digest,
                expires_at=now + timedelta(days=self.refresh_days),
                revoked_at=None,
                replaced_by_id=None,
                created_at=now,
            )
        )
        access = encode_access_token(user_id, self.secret, self.access_minutes, now)
        return TokenPair(access_token=access, refresh_token=raw)

    async def _rotate(self, current: RefreshRecord, now: datetime) -> TokenPair:
        raw, digest = generate_opaque_token()
        new_token_id = new_id()
        await self.refreshes.add(
            RefreshRecord(
                id=new_token_id,
                user_id=current.user_id,
                family_id=current.family_id,
                token_hash=digest,
                expires_at=now + timedelta(days=self.refresh_days),
                revoked_at=None,
                replaced_by_id=None,
                created_at=now,
            )
        )
        await self.refreshes.mark_replaced(current.id, new_token_id, now)
        access = encode_access_token(current.user_id, self.secret, self.access_minutes, now)
        return TokenPair(access_token=access, refresh_token=raw)

    async def _audit_register(
        self,
        user_id: UUID | None,
        request_id: str | None,
        result: str,
    ) -> None:
        await self.audit.record(
            actor_id=user_id,
            action="register",
            entity_type="user",
            entity_id=user_id,
            metadata={"result": result},
            request_id=request_id,
        )

    async def _audit_second_factor(self, user_id: UUID, request_id: str | None, ok: bool) -> None:
        await self.audit.record(
            actor_id=user_id,
            action="login_second_factor",
            entity_type="user",
            entity_id=user_id,
            metadata={"result": "ok" if ok else "rejected"},
            request_id=request_id,
        )

    async def _live_user(self, user_id: UUID) -> UserRecord:
        user = await self.users.get_by_id(user_id)
        if user is None or user.deleted_at is not None:
            raise ProblemError(401, "Unauthorized", INVALID_SESSION, PROBLEM_SESSION)
        return user

    def _recovery(self) -> RecoveryStore:
        if self.recovery is None:
            raise RuntimeError("recovery store is not configured")
        return self.recovery

    def _resets(self) -> OpaqueTokenStore:
        if self.resets is None:
            raise RuntimeError("reset store is not configured")
        return self.resets

    def _invites(self) -> OpaqueTokenStore:
        if self.invites is None:
            raise RuntimeError("invite store is not configured")
        return self.invites

    def _totp_key(self) -> str:
        if not self.totp_key:
            raise RuntimeError("TOTP encryption key is not configured")
        return self.totp_key

    def _invalid_session(self) -> ProblemError:
        return ProblemError(401, "Unauthorized", INVALID_SESSION, PROBLEM_SESSION)

    def _invalid_verification(self) -> ProblemError:
        return ProblemError(400, "Bad Request", INVALID_VERIFICATION, PROBLEM_VERIFY)

    def _invalid_reset(self) -> ProblemError:
        return ProblemError(400, "Bad Request", INVALID_RESET, PROBLEM_RESET)

    def _invalid_code(self) -> ProblemError:
        return ProblemError(401, "Unauthorized", INVALID_CODE, PROBLEM_SECOND_FACTOR)


def _second_factor_step(
    roles: list[str], user: UserRecord
) -> Literal["enroll", "challenge"] | None:
    privileged = "super_admin" in roles or "staff" in roles
    enrolled = user.totp_confirmed_at is not None
    if privileged and not enrolled:
        return "enroll"
    if enrolled:
        return "challenge"
    return None


def _phone_disabled() -> ProblemError:
    from app.problems import PROBLEM_PHONE_DISABLED

    return ProblemError(
        403,
        "Forbidden",
        "Phone registration is not available.",
        PROBLEM_PHONE_DISABLED,
    )


def unused_random_password() -> str:
    """Hash input for staff invites. The plaintext is never stored or emailed."""
    return hash_password(secrets.token_urlsafe(32))


def staff_email_taken() -> ProblemError:
    return ProblemError(
        409,
        "Conflict",
        "An account with that email already exists.",
        PROBLEM_CONFLICT,
    )


# Re-exported messages used by the router.
LOGIN_STEP_MESSAGE = {
    "session": "Logged in.",
    "enroll": ENROLL_MESSAGE,
    "challenge": CHALLENGE_MESSAGE,
}
DISABLE_MESSAGE = TOTP_DISABLED_MESSAGE
ENABLE_MESSAGE = TOTP_ENABLED_MESSAGE
RESET_DONE = PASSWORD_UPDATED_MESSAGE
INVITE_DONE = INVITE_ACCEPTED_MESSAGE
