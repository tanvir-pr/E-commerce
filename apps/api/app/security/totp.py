"""TOTP secrets at rest, recovery codes, and a one-time QR image."""

import secrets

import pyotp
import segno
from cryptography.fernet import Fernet, InvalidToken

from app.security.tokens import hash_token

ISSUER = "Store"
_RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def ensure_totp_key(key: str) -> None:
    try:
        Fernet(key.encode("ascii"))
    except Exception as exc:
        raise RuntimeError("TOTP_ENCRYPTION_KEY must be a Fernet key.") from exc


def encrypt_secret(secret: str, key: str) -> str:
    token = Fernet(key.encode("ascii")).encrypt(secret.encode("utf-8"))
    return token.decode("ascii")


def decrypt_secret(ciphertext: str, key: str) -> str:
    try:
        plain = Fernet(key.encode("ascii")).decrypt(ciphertext.encode("ascii"))
    except (InvalidToken, ValueError) as exc:
        raise ValueError("totp ciphertext could not be read") from exc
    return plain.decode("utf-8")


def verify_totp(secret: str, code: str) -> bool:
    compact = "".join(code.split())
    if not compact.isdigit() or not 6 <= len(compact) <= 8:
        return False
    return bool(pyotp.TOTP(secret).verify(compact, valid_window=1))


def provisioning_uri(secret: str, label: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=label, issuer_name=ISSUER)


def qr_svg(data: str) -> str:
    return segno.make(data, error="m").svg_inline(scale=4)


def new_totp_secret() -> str:
    return pyotp.random_base32()


def normalize_recovery_code(raw: str) -> str:
    return "".join(ch for ch in raw.upper() if ch.isalnum())


def generate_recovery_codes(count: int = 10) -> list[tuple[str, str]]:
    """Return (display, sha256) pairs. Only the hash is stored."""
    codes: list[tuple[str, str]] = []
    for _ in range(count):
        compact = "".join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(8))
        display = f"{compact[:4]}-{compact[4:]}"
        codes.append((display, hash_token(compact)))
    return codes


def recovery_digest(raw: str) -> str:
    return hash_token(normalize_recovery_code(raw))
