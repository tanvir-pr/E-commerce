"""API shapes for the current user. Secrets are never returned.

email_verified_at and phone_verified_at are read-only. ProfilePatch accepts name only.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.records import UserRecord


class MeOut(BaseModel):
    id: UUID
    email: str | None
    email_verified_at: datetime | None
    phone: str | None
    phone_verified_at: datetime | None
    name: str | None
    roles: list[str]
    totp_enabled: bool


class ProfilePatch(BaseModel):
    name: str = Field(min_length=1, max_length=200)


def to_me(user: UserRecord) -> MeOut:
    return MeOut(
        id=user.id,
        email=user.email,
        email_verified_at=user.email_verified_at,
        phone=user.phone,
        phone_verified_at=user.phone_verified_at,
        name=user.name,
        roles=list(user.roles),
        totp_enabled=user.totp_confirmed_at is not None,
    )
