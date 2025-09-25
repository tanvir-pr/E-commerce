"""Append-only audit writer. There is no update or delete method."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import utc_now
from app.ids import new_id
from app.models.audit import AuditLog
from app.models.user import User
from app.records import AuditEntry


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        *,
        actor_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: UUID | None,
        metadata: dict[str, Any],
        request_id: str | None,
    ) -> None:
        self.session.add(
            AuditLog(
                id=new_id(),
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                meta=metadata,
                request_id=request_id,
                created_at=utc_now(),
            )
        )
        await self.session.flush()


class AuditQuery:
    """Read recent events. This class does not update or delete rows."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_recent(self, limit: int = 50) -> list[AuditEntry]:
        stmt = (
            select(AuditLog, User.email)
            .outerjoin(User, User.id == AuditLog.actor_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).all()
        entries: list[AuditEntry] = []
        for log_row, email in rows:
            entries.append(
                AuditEntry(
                    id=log_row.id,
                    actor_id=log_row.actor_id,
                    actor_email=email,
                    action=log_row.action,
                    entity_type=log_row.entity_type,
                    entity_id=log_row.entity_id,
                    created_at=log_row.created_at,
                )
            )
        return entries


class AuditService:
    def __init__(self, repository: AuditRepository) -> None:
        self.repository = repository

    async def record(
        self,
        *,
        actor_id: UUID | None,
        action: str,
        entity_type: str,
        entity_id: UUID | None,
        metadata: dict[str, Any],
        request_id: str | None,
    ) -> None:
        await self.repository.add(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
            request_id=request_id,
        )
