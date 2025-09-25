"""RFC 9457 problem details."""

from typing import Any

PROBLEM_VALIDATION = "https://store.local/problems/validation-error"
PROBLEM_CREDENTIALS = "https://store.local/problems/invalid-credentials"
PROBLEM_UNAUTHORIZED = "https://store.local/problems/unauthorized"
PROBLEM_SESSION = "https://store.local/problems/invalid-session"
PROBLEM_VERIFY = "https://store.local/problems/invalid-verification-token"
PROBLEM_CSRF = "https://store.local/problems/csrf"
PROBLEM_RATE_LIMIT = "https://store.local/problems/rate-limited"
PROBLEM_INTERNAL = "https://store.local/problems/internal"
PROBLEM_FORBIDDEN = "https://store.local/problems/forbidden"
PROBLEM_PHONE_DISABLED = "https://store.local/problems/phone-registration-disabled"
PROBLEM_SECOND_FACTOR = "https://store.local/problems/invalid-second-factor"
PROBLEM_RESET = "https://store.local/problems/invalid-reset-token"
PROBLEM_NOT_FOUND = "https://store.local/problems/not-found"
PROBLEM_CONFLICT = "https://store.local/problems/conflict"


class ProblemError(Exception):
    def __init__(
        self,
        status: int,
        title: str,
        detail: str,
        type_: str,
        errors: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.title = title
        self.detail = detail
        self.type_ = type_
        self.errors = errors or []


class DuplicateEmailError(Exception):
    """Raised when a concurrent insert hits the unique email constraint."""


class RoleMissingError(Exception):
    def __init__(self, role_name: str) -> None:
        super().__init__(role_name)
        self.role_name = role_name


class InvalidAccessToken(Exception):
    pass


class DuplicatePhoneError(Exception):
    """Raised when a phone number is already registered."""


def problem_payload(problem: ProblemError, request_id: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": problem.type_,
        "title": problem.title,
        "status": problem.status,
        "detail": problem.detail,
        "request_id": request_id,
    }
    if problem.errors:
        payload["errors"] = problem.errors
    return payload
