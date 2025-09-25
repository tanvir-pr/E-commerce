"""Opaque tokens and signed access tokens. Raw secrets are never stored."""

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

import jwt

from app.problems import InvalidAccessToken


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_opaque_token() -> tuple[str, str]:
    """Return (raw, sha256 hex). token_urlsafe(32) draws 32 random bytes."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)


def tokens_match(left: str, right: str) -> bool:
    left_bytes = left.encode("utf-8")
    right_bytes = right.encode("utf-8")
    if len(left_bytes) != len(right_bytes):
        return False
    return secrets.compare_digest(left_bytes, right_bytes)


def encode_access_token(user_id: UUID, secret: str, minutes: int, now: datetime) -> str:
    payload = {
        "sub": str(user_id),
        "typ": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    encoded = jwt.encode(payload, secret, algorithm="HS256")
    if isinstance(encoded, bytes):
        return encoded.decode("ascii")
    return encoded


def encode_ticket(user_id: UUID, secret: str, minutes: int, now: datetime, purpose: str) -> str:
    if purpose not in {"enroll", "challenge"}:
        raise ValueError("unsupported ticket purpose")
    payload = {
        "sub": str(user_id),
        "typ": purpose,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
    }
    encoded = jwt.encode(payload, secret, algorithm="HS256")
    if isinstance(encoded, bytes):
        return encoded.decode("ascii")
    return encoded


def decode_ticket(token: str, secret: str, purpose: str) -> UUID:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise InvalidAccessToken from exc
    if payload.get("typ") != purpose:
        raise InvalidAccessToken
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise InvalidAccessToken
    try:
        return UUID(subject)
    except ValueError as exc:
        raise InvalidAccessToken from exc


def decode_access_token(token: str, secret: str) -> UUID:
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise InvalidAccessToken from exc
    if payload.get("typ") != "access":
        raise InvalidAccessToken
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise InvalidAccessToken
    try:
        return UUID(subject)
    except ValueError as exc:
        raise InvalidAccessToken from exc
