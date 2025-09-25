"""Staff administration payloads."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

PermissionName = Literal["support", "warehouse", "moderation"]


class StaffCreateIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    permissions: list[PermissionName] = Field(default_factory=list)


class StaffOut(BaseModel):
    id: UUID
    email: str
    permissions: list[str]


class StaffPermissionsIn(BaseModel):
    permissions: list[PermissionName]


class StaffPermissionsOut(BaseModel):
    user_id: UUID
    permissions: list[str]


class AuditEventOut(BaseModel):
    id: UUID
    actor_id: UUID | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: UUID | None
    created_at: datetime


class AuditListOut(BaseModel):
    events: list[AuditEventOut]


class QueueOut(BaseModel):
    status: Literal["empty"]
