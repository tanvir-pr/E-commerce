"""Read and update the signed-in account. Identity comes from the access token."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from app.clock import utc_now
from app.ports import AuditWriter, RefreshStore, UserStore
from app.problems import PROBLEM_UNAUTHORIZED, PROBLEM_VALIDATION, ProblemError
from app.records import UserRecord


class UserService:
    def __init__(self, users: UserStore, clock: Callable[[], datetime] = utc_now) -> None:
        self.users = users
        self.clock = clock

    async def get_me(self, user_id: UUID) -> UserRecord | None:
        user = await self.users.get_by_id(user_id)
        if user is None or user.deleted_at is not None:
            return None
        user.roles = await self.users.list_roles(user_id)
        user.permissions = await self.users.list_permissions(user_id)
        return user

    async def update_name(self, user_id: UUID, name: str) -> UserRecord:
        cleaned = name.strip()
        if not cleaned or len(cleaned) > 200:
            raise ProblemError(
                422,
                "Validation error",
                "One or more fields are invalid.",
                PROBLEM_VALIDATION,
                errors=[{"field": "name", "message": "Enter a name."}],
            )
        await self.users.update_name(user_id, cleaned, self.clock())
        user = await self.get_me(user_id)
        if user is None:
            raise ProblemError(
                401, "Unauthorized", "Authentication required.", PROBLEM_UNAUTHORIZED
            )
        return user

    async def delete_me(
        self,
        user_id: UUID,
        refreshes: RefreshStore,
        audit: AuditWriter,
        request_id: str | None,
    ) -> None:
        when = self.clock()
        await self.users.mark_deleted(user_id, when)
        await refreshes.revoke_all_for_user(user_id, when)
        await audit.record(
            actor_id=user_id,
            action="account_deletion_requested",
            entity_type="user",
            entity_id=user_id,
            metadata={"erasure": "incomplete"},
            request_id=request_id,
        )
