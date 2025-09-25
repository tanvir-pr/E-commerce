"""Verification and refresh-token persistence."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ids import new_id
from app.models.token import EmailVerificationToken, RefreshToken
from app.records import RefreshRecord, VerificationRecord


def _verification(row: EmailVerificationToken) -> VerificationRecord:
    return VerificationRecord(
        id=row.id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        expires_at=row.expires_at,
        used_at=row.used_at,
    )


def _refresh(row: RefreshToken) -> RefreshRecord:
    return RefreshRecord(
        id=row.id,
        user_id=row.user_id,
        family_id=row.family_id,
        token_hash=row.token_hash,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        replaced_by_id=row.replaced_by_id,
        created_at=row.created_at,
    )


class VerificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id: UUID, token_hash: str, expires_at: datetime) -> VerificationRecord:
        row = EmailVerificationToken(
            id=new_id(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(row)
        await self.session.flush()
        return _verification(row)

    async def get_by_hash(self, token_hash: str) -> VerificationRecord | None:
        row = await self.session.scalar(
            select(EmailVerificationToken).where(EmailVerificationToken.token_hash == token_hash)
        )
        if row is None:
            return None
        return _verification(row)

    async def mark_used(self, token_id: UUID, when: datetime) -> bool:
        row = await self.session.get(EmailVerificationToken, token_id)
        if row is None or row.used_at is not None or row.expires_at <= when:
            return False
        row.used_at = when
        await self.session.flush()
        return True


class RefreshRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, record: RefreshRecord) -> None:
        self.session.add(
            RefreshToken(
                id=record.id,
                user_id=record.user_id,
                family_id=record.family_id,
                token_hash=record.token_hash,
                expires_at=record.expires_at,
                revoked_at=record.revoked_at,
                replaced_by_id=record.replaced_by_id,
                created_at=record.created_at,
            )
        )
        await self.session.flush()

    async def get_by_hash(self, token_hash: str) -> RefreshRecord | None:
        row = await self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        if row is None:
            return None
        return _refresh(row)

    async def mark_replaced(self, token_id: UUID, new_id: UUID, when: datetime) -> None:
        row = await self.session.get(RefreshToken, token_id)
        if row is None:
            return
        row.replaced_by_id = new_id
        row.revoked_at = when
        await self.session.flush()

    async def revoke_family(self, family_id: UUID, when: datetime) -> None:
        rows = (
            await self.session.scalars(
                select(RefreshToken).where(RefreshToken.family_id == family_id)
            )
        ).all()
        for row in rows:
            if row.revoked_at is None:
                row.revoked_at = when
        await self.session.flush()

    async def list_for_user(self, user_id: UUID) -> list[RefreshRecord]:
        rows = (
            await self.session.scalars(select(RefreshToken).where(RefreshToken.user_id == user_id))
        ).all()
        return [_refresh(row) for row in rows]

    async def revoke_all_for_user(self, user_id: UUID, when: datetime) -> None:
        rows = (
            await self.session.scalars(select(RefreshToken).where(RefreshToken.user_id == user_id))
        ).all()
        for row in rows:
            if row.revoked_at is None:
                row.revoked_at = when
        await self.session.flush()
