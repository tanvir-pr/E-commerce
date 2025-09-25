"""Verification email copy. English only in v1."""

from urllib.parse import quote


def build_verification_url(public_web_url: str, token: str) -> str:
    base = public_web_url.rstrip("/")
    return f"{base}/en/verify-email?token={quote(token, safe='')}"


def verification_email_body(url: str) -> str:
    return f"Verify your email:\n{url}\n\nThis link expires in 30 minutes.\n"


def build_reset_url(public_web_url: str, token: str) -> str:
    base = public_web_url.rstrip("/")
    return f"{base}/en/reset-password?token={quote(token, safe='')}"


def reset_email_body(url: str) -> str:
    return f"Reset your password:\n{url}\n\nThis link expires in 30 minutes and can be used once.\n"


def build_invite_url(public_web_url: str, token: str) -> str:
    base = public_web_url.rstrip("/")
    return f"{base}/en/accept-invite?token={quote(token, safe='')}"


def invite_email_body(url: str) -> str:
    return (
        "Set your staff password:\n"
        f"{url}\n\n"
        "This link expires in 24 hours and can be used once. "
        "After you sign in, enroll two-factor authentication.\n"
    )
