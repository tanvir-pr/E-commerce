"""Phone registration OTP. Active only when the public flag is on."""

import secrets
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

from app.clock import utc_now
from app.ports import AuditWriter, PhoneChallengeStore, RateLimiter, SmsSender, UserStore
from app.problems import (
    PROBLEM_INTERNAL,
    PROBLEM_PHONE_DISABLED,
    PROBLEM_VALIDATION,
    PROBLEM_VERIFY,
    DuplicatePhoneError,
    ProblemError,
    RoleMissingError,
)
from app.records import PHONE_CONFIRMED_MESSAGE, PHONE_START_MESSAGE
from app.security.passwords import ensure_password_allowed, hash_password
from app.security.tokens import hash_token, tokens_match


def normalize_phone(raw: str) -> str:
    cleaned = "".join(raw.split())
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    if not cleaned.startswith("+"):
        raise _phone_invalid()
    digits = cleaned[1:]
    if not digits.isdigit() or not 8 <= len(digits) <= 15:
        raise _phone_invalid()
    return "+" + digits


class PhoneService:
    def __init__(
        self,
        users: UserStore,
        challenges: PhoneChallengeStore,
        sms: SmsSender,
        limiter: RateLimiter,
        audit: AuditWriter,
        *,
        breach_mode: str,
        otp_minutes: int = 5,
        max_attempts: int = 5,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.users = users
        self.challenges = challenges
        self.sms = sms
        self.limiter = limiter
        self.audit = audit
        self.breach_mode = breach_mode
        self.otp_minutes = otp_minutes
        self.max_attempts = max_attempts
        self.clock = clock

    async def start(
        self,
        phone: str,
        password: str,
        name: str,
        ip: str,
        *,
        enabled: bool,
        before_send: Callable[[], Awaitable[None]] | None = None,
    ) -> str:
        if not enabled:
            raise _disabled()
        normalized = normalize_phone(phone)
        await self.limiter.hit("phone", ip, normalized)
        cleaned_name = name.strip()
        if not cleaned_name or len(cleaned_name) > 200:
            raise ProblemError(
                422,
                "Validation error",
                "One or more fields are invalid.",
                PROBLEM_VALIDATION,
                errors=[{"field": "name", "message": "Enter a name."}],
            )
        ensure_password_allowed(password, self.breach_mode)
        existing = await self.users.get_by_phone(normalized)
        if existing is not None:
            return PHONE_START_MESSAGE
        code = f"{secrets.randbelow(1_000_000):06d}"
        expires = self.clock() + timedelta(minutes=self.otp_minutes)
        await self.challenges.add(
            normalized,
            hash_password(password),
            cleaned_name,
            hash_token(code),
            expires,
        )
        if before_send is not None:
            await before_send()
        await self.sms.send_otp(normalized, code)
        return PHONE_START_MESSAGE

    async def confirm(
        self,
        phone: str,
        code: str,
        request_id: str | None,
        *,
        enabled: bool,
    ) -> str:
        if not enabled:
            raise _disabled()
        normalized = normalize_phone(phone)
        now = self.clock()
        challenge = await self.challenges.latest_open(normalized, now)
        if challenge is None or challenge.attempts >= self.max_attempts:
            raise _invalid_otp()
        if not tokens_match(challenge.code_hash, hash_token(code.strip())):
            await self.challenges.increment_attempts(challenge.id)
            raise _invalid_otp()
        used = await self.challenges.mark_used(challenge.id, now)
        if not used:
            raise _invalid_otp()
        try:
            user = await self.users.add_phone_user(
                normalized, challenge.password_hash, challenge.name, now
            )
        except DuplicatePhoneError:
            raise _invalid_otp() from None
        try:
            await self.users.assign_role(user.id, "customer")
        except RoleMissingError as exc:
            raise ProblemError(
                500,
                "Internal Server Error",
                "Something went wrong.",
                PROBLEM_INTERNAL,
            ) from exc
        await self.audit.record(
            actor_id=user.id,
            action="phone_registered",
            entity_type="user",
            entity_id=user.id,
            metadata={},
            request_id=request_id,
        )
        return PHONE_CONFIRMED_MESSAGE


def _disabled() -> ProblemError:
    return ProblemError(
        403,
        "Forbidden",
        "Phone registration is not available.",
        PROBLEM_PHONE_DISABLED,
    )


def _phone_invalid() -> ProblemError:
    return ProblemError(
        422,
        "Validation error",
        "One or more fields are invalid.",
        PROBLEM_VALIDATION,
        errors=[{"field": "phone", "message": "Enter a phone number like +8801XXXXXXXXX."}],
    )


def _invalid_otp() -> ProblemError:
    return ProblemError(
        400,
        "Bad Request",
        "The code is invalid or expired.",
        PROBLEM_VERIFY,
    )
