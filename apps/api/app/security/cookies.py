"""First-party session cookies.

__Host- cookies require Secure, Path=/, and no Domain attribute. Path must not
be narrowed to /api/v1/auth. Chromium treats http://localhost as a secure
context, so Secure cookies are stored on http://localhost.
"""

from starlette.responses import Response

from app.records import TokenPair

ACCESS_COOKIE = "__Host-access"
REFRESH_COOKIE = "__Host-refresh"
CSRF_COOKIE = "__Host-csrf"
ENROLL_COOKIE = "__Host-enroll"
CHALLENGE_COOKIE = "__Host-challenge"


def set_session_cookies(
    response: Response,
    pair: TokenPair,
    *,
    access_max_age: int,
    refresh_max_age: int,
) -> None:
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=pair.access_token,
        max_age=access_max_age,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=pair.refresh_token,
        max_age=refresh_max_age,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def set_ticket_cookie(response: Response, key: str, value: str, max_age: int) -> None:
    response.set_cookie(
        key=key,
        value=value,
        max_age=max_age,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def _delete_host_cookie(response: Response, key: str, *, httponly: bool) -> None:
    response.delete_cookie(
        key=key,
        path="/",
        secure=True,
        httponly=httponly,
        samesite="lax",
    )


def clear_ticket_cookies(response: Response) -> None:
    _delete_host_cookie(response, ENROLL_COOKIE, httponly=True)
    _delete_host_cookie(response, CHALLENGE_COOKIE, httponly=True)


def clear_session_cookies(response: Response) -> None:
    # secure=True is required so the browser matches the __Host- cookie.
    response.delete_cookie(
        key=ACCESS_COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def set_csrf_cookie(response: Response, token: str, max_age: int = 8 * 60 * 60) -> None:
    response.set_cookie(
        key=CSRF_COOKIE,
        value=token,
        max_age=max_age,
        httponly=False,
        secure=True,
        samesite="lax",
        path="/",
    )
