"""Super-admin staff creation and permission changes."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from uuid import UUID

from app.auth.service import normalize_email, staff_email_taken, unused_random_password
from app.clock import utc_now
from app.ports import AuditWriter, Mailer, OpaqueTokenStore, UserStore
from app.problems import PROBLEM_NOT_FOUND, DuplicateEmailError, ProblemError, RoleMissingError
from app.records import StaffResult
from app.security.policy import parse_permissions
from app.security.tokens import generate_opaque_token


class AdminService:
    def __init__(
        self,
        users: UserStore,
        invites: OpaqueTokenStore,
        audit: AuditWriter,
        mailer: Mailer,
        *,
        invite_hours: int = 24,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.users = users
        self.invites = invites
        self.audit = audit
        self.mailer = mailer
        self.invite_hours = invite_hours
        self.clock = clock

    async def create_staff(
        self,
        actor_id: UUID,
        email: str,
        name: str,
        permissions: list[str],
        request_id: str | None,
        before_mail: Callable[[], Awaitable[None]] | None = None,
    ) -> StaffResult:
        normalized = normalize_email(email)
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ProblemError(
                422,
                "Validation error",
                "One or more fields are invalid.",
                "https://store.local/problems/validation-error",
                errors=[{"field": "name", "message": "Enter a name."}],
            )
        cleaned = parse_permissions(permissions)
        try:
            user = await self.users.add(normalized, unused_random_password())
        except DuplicateEmailError:
            raise staff_email_taken() from None
        now = self.clock()
        await self.users.update_name(user.id, cleaned_name, now)
        try:
            await self.users.assign_role(user.id, "staff")
        except RoleMissingError as exc:
            raise ProblemError(
                500,
                "Internal Server Error",
                "Something went wrong.",
                "https://store.local/problems/internal",
            ) from exc
        await self.users.replace_permissions(user.id, cleaned)
        raw, digest = generate_opaque_token()
        await self.invites.add(user.id, digest, now + timedelta(hours=self.invite_hours))
        await self.audit.record(
            actor_id=actor_id,
            action="staff_created",
            entity_type="user",
            entity_id=user.id,
            metadata={"permissions": cleaned},
            request_id=request_id,
        )
        if before_mail is not None:
            await before_mail()
        await self.mailer.send_staff_invite(normalized, raw)
        return StaffResult(id=user.id, email=normalized, permissions=cleaned)

    async def replace_permissions(
        self,
        actor_id: UUID,
        user_id: UUID,
        permissions: list[str],
        request_id: str | None,
    ) -> list[str]:
        cleaned = parse_permissions(permissions)
        user = await self.users.get_by_id(user_id)
        if user is None or user.deleted_at is not None:
            raise _missing_staff()
        roles = await self.users.list_roles(user_id)
        if "staff" not in roles:
            raise _missing_staff()
        await self.users.replace_permissions(user_id, cleaned)
        await self.audit.record(
            actor_id=actor_id,
            action="staff_permissions_replaced",
            entity_type="user",
            entity_id=user_id,
            metadata={"permissions": cleaned},
            request_id=request_id,
        )
        return cleaned


def _missing_staff() -> ProblemError:
    return ProblemError(404, "Not Found", "Staff member not found.", PROBLEM_NOT_FOUND)
