"""Plain records passed between services and repositories."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID


@dataclass
class UserRecord:
    id: UUID
    email: str | None
    password_hash: str
    email_verified_at: datetime | None
    roles: list[str]
    name: str | None = None
    phone: str | None = None
    phone_verified_at: datetime | None = None
    totp_secret_ciphertext: str | None = None
    totp_pending_ciphertext: str | None = None
    totp_confirmed_at: datetime | None = None
    deleted_at: datetime | None = None
    permissions: list[str] = field(default_factory=list)


@dataclass
class VerificationRecord:
    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    used_at: datetime | None


@dataclass
class RefreshRecord:
    id: UUID
    user_id: UUID
    family_id: UUID
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None
    replaced_by_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class RegisterOutcome:
    message: str


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


@dataclass(frozen=True)
class LoginResult:
    next_step: Literal["session", "enroll", "challenge"]
    tokens: TokenPair | None = None
    ticket: str | None = None


@dataclass(frozen=True)
class TotpSetupResult:
    secret: str
    otpauth_uri: str
    qr_svg: str


@dataclass(frozen=True)
class TotpConfirmResult:
    recovery_codes: list[str]
    tokens: TokenPair | None


@dataclass
class ResetRecord:
    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    used_at: datetime | None


@dataclass
class RecoveryCodeRecord:
    id: UUID
    user_id: UUID
    code_hash: str
    used_at: datetime | None


@dataclass
class PhoneChallengeRecord:
    id: UUID
    phone: str
    password_hash: str
    name: str
    code_hash: str
    expires_at: datetime
    attempts: int
    used_at: datetime | None


@dataclass(frozen=True)
class SessionView:
    family_id: UUID
    created_at: datetime
    expires_at: datetime
    current: bool


@dataclass(frozen=True)
class AuditEntry:
    id: UUID
    actor_id: UUID | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class StaffResult:
    id: UUID
    email: str
    permissions: list[str]


REGISTER_MESSAGE = "If the email is valid, check your inbox for a verification link."
LOGIN_MESSAGE = "Logged in."
LOGOUT_MESSAGE = "Logged out."
REFRESH_MESSAGE = "Refreshed."
VERIFY_MESSAGE = "Email verified."
INVALID_CREDENTIALS = "Invalid email or password."
INVALID_SESSION = "Session is no longer valid."
INVALID_VERIFICATION = "Verification link is invalid or expired."
RESET_MESSAGE = "If an account exists for that email, a reset link is on the way."
INVALID_RESET = "Reset link is invalid or expired."
PHONE_START_MESSAGE = "If the phone number can be registered, a verification code was sent."
PHONE_CONFIRMED_MESSAGE = "Phone number verified."
INVALID_CODE = "Invalid authentication code."
TOTP_ENABLED_MESSAGE = "Two-factor authentication is on."
TOTP_DISABLED_MESSAGE = "Two-factor authentication is off."
LOGOUT_EVERYWHERE_MESSAGE = "Signed out on every device."
DELETE_MESSAGE = "Account deletion has started. Full erasure is not complete."
PASSWORD_UPDATED_MESSAGE = "Password updated. Sign in with the new password."
INVITE_ACCEPTED_MESSAGE = "Password set. Sign in to enroll two-factor authentication."
ENROLL_MESSAGE = "Password accepted. Enroll two-factor authentication to finish signing in."
CHALLENGE_MESSAGE = "Password accepted. Enter your authentication code."
