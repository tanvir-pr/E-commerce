"""Deny-by-default authorization. Routes declare a role and, for staff, a permission."""

from dataclasses import dataclass
from uuid import UUID

from app.problems import PROBLEM_FORBIDDEN, PROBLEM_VALIDATION, ProblemError

STAFF_PERMISSIONS = frozenset({"support", "warehouse", "moderation"})


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    roles: frozenset[str]
    permissions: frozenset[str]
    totp_enabled: bool


@dataclass(frozen=True)
class Access:
    """Required role, and the staff permission when the route is staff work.

    An empty role set is denied. Super admins pass a staff permission check only
    when super_admin is one of the allowed roles.
    """

    roles: frozenset[str]
    permission: str | None = None
    require_totp: bool = False


def decide(actor: Actor, access: Access) -> bool:
    if not access.roles:
        return False
    if not actor.roles.intersection(access.roles):
        return False
    if access.require_totp and not actor.totp_enabled:
        return False
    if access.permission is None:
        return True
    if "super_admin" in actor.roles:
        return True
    return access.permission in actor.permissions


def authorize(actor: Actor, access: Access) -> None:
    if decide(actor, access):
        return
    raise ProblemError(
        403,
        "Forbidden",
        "You do not have access to this resource.",
        PROBLEM_FORBIDDEN,
    )


def require_self(actor_id: UUID, target_id: UUID) -> None:
    """Ownership check for any route that names another user."""
    if actor_id != target_id:
        raise ProblemError(
            403,
            "Forbidden",
            "You do not have access to this resource.",
            PROBLEM_FORBIDDEN,
        )


def parse_permissions(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        if value not in STAFF_PERMISSIONS:
            raise ProblemError(
                422,
                "Validation error",
                "One or more fields are invalid.",
                PROBLEM_VALIDATION,
                errors=[{"field": "permissions", "message": "Unknown staff permission."}],
            )
        if value not in cleaned:
            cleaned.append(value)
    return cleaned
