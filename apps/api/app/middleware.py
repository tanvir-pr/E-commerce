"""Request id and double-submit CSRF. Added as pure ASGI middleware."""

import json
import re
from typing import Any
from uuid import uuid4

import structlog

from app.problems import PROBLEM_CSRF, ProblemError, problem_payload
from app.security.cookies import CSRF_COOKIE
from app.security.tokens import tokens_match

_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9._:-]{1,128}")


def _headers(scope: dict[str, Any]) -> dict[str, str]:
    found: dict[str, str] = {}
    for key, value in scope.get("headers", []):
        found[key.decode("latin-1").lower()] = value.decode("latin-1")
    return found


def _cookies(header: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in header.split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        parsed[name.strip()] = value.strip()
    return parsed


def _request_id(raw: str | None) -> str:
    if raw and _REQUEST_ID_RE.fullmatch(raw):
        return raw
    return str(uuid4())


class RequestContextMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = _headers(scope)
        request_id = _request_id(headers.get("x-request-id"))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        log = structlog.get_logger()
        status_code = 500

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                response_headers = list(message.get("headers") or [])
                response_headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = response_headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
            log.info(
                "request_completed",
                method=scope.get("method"),
                path=scope.get("path"),
                status=status_code,
            )
        except Exception:
            log.error(
                "request_failed",
                method=scope.get("method"),
                path=scope.get("path"),
                error_type="unhandled",
            )
            raise
        finally:
            structlog.contextvars.clear_contextvars()


class CSRFMiddleware:
    """Require X-CSRF-Token to match the CSRF cookie on unsafe methods.

    GET /api/v1/auth/csrf is safe and is the call that issues the cookie.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http" or scope.get("method") not in _UNSAFE:
            await self.app(scope, receive, send)
            return

        headers = _headers(scope)
        cookies = _cookies(headers.get("cookie", ""))
        cookie = cookies.get(CSRF_COOKIE, "")
        header = headers.get("x-csrf-token", "")
        if cookie and header and tokens_match(cookie, header):
            await self.app(scope, receive, send)
            return

        from app.logging_config import current_request_id

        problem = ProblemError(
            403,
            "Forbidden",
            "CSRF token missing or invalid.",
            PROBLEM_CSRF,
        )
        body = json.dumps(problem_payload(problem, current_request_id())).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/problem+json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
