"""Argon2id passwords and the Have I Been Pwned stub."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

from app.problems import PROBLEM_VALIDATION, ProblemError

# OWASP minimum Argon2id parameters (2024 cheat sheet): m=19 MiB, t=2, p=1.
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)

_DUMMY_PLAINTEXT = "dummy-password-not-used-for-login"
_dummy_hash: str | None = None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def _dummy() -> str:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password(_DUMMY_PLAINTEXT)
    return _dummy_hash


def verify_password(password: str, password_hash: str | None) -> bool:
    candidate = password_hash if password_hash is not None else _dummy()
    try:
        return bool(_hasher.verify(candidate, password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_is_breached(password: str, mode: str) -> bool:
    """Return True when the password must be rejected.

    Have I Been Pwned k-anonymity hook (not enabled):
    SHA-1 the password, send the first 5 hex characters to the HIBP range API,
    and look for the remaining suffix in the response. Week 1 does not call HIBP.

    When mode is ``stub`` (BREACH_CHECK=stub) this always returns False, so any
    password that meets the length rule is accepted.
    """
    if mode == "stub":
        return False
    raise RuntimeError(
        "Have I Been Pwned k-anonymity is not implemented. Set BREACH_CHECK=stub. "
        f"Rejected a password of length {len(password)}."
    )


def ensure_password_allowed(password: str, breach_mode: str) -> None:
    errors: list[dict[str, str]] = []
    if len(password) < 10:
        errors.append({"field": "password", "message": "Must be at least 10 characters."})
    elif len(password) > 128:
        errors.append({"field": "password", "message": "Must be at most 128 characters."})
    elif password_is_breached(password, breach_mode):
        errors.append({"field": "password", "message": "This password is not allowed."})
    if errors:
        raise ProblemError(
            422,
            "Validation error",
            "One or more fields are invalid.",
            PROBLEM_VALIDATION,
            errors=errors,
        )
