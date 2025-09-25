"""Hashed single-use tokens: password reset, staff invite, recovery, phone OTP."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ids import new_id
from app.models.security import (
    PasswordResetToken,
    PhoneOtpChallenge,
    RecoveryCode,
    StaffInviteToken,
)
from app.records import PhoneChallengeRecord, ResetRecord


class ResetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id: UUID, token_hash: str, expires_at: datetime) -> ResetRecord:
        row = PasswordResetToken(
            id=new_id(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(row)
        await self.session.flush()
        return _reset(row)

    async def get_by_hash(self, token_hash: str) -> ResetRecord | None:
        row = await self.session.scalar(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
        )
        if row is None:
            return None
        return _reset(row)

    async def mark_used(self, token_id: UUID, when: datetime) -> bool:
        row = await self.session.get(PasswordResetToken, token_id)
        if row is None or row.used_at is not None or row.expires_at <= when:
            return False
        row.used_at = when
        await self.session.flush()
        return True


class InviteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id: UUID, token_hash: str, expires_at: datetime) -> ResetRecord:
        row = StaffInviteToken(
            id=new_id(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(row)
        await self.session.flush()
        return ResetRecord(
            id=row.id,
            user_id=row.user_id,
            token_hash=row.token_hash,
            expires_at=row.expires_at,
            used_at=row.used_at,
        )

    async def get_by_hash(self, token_hash: str) -> ResetRecord | None:
        row = await self.session.scalar(
            select(StaffInviteToken).where(StaffInviteToken.token_hash == token_hash)
        )
        if row is None:
            return None
        return ResetRecord(
            id=row.id,
            user_id=row.user_id,
            token_hash=row.token_hash,
            expires_at=row.expires_at,
            used_at=row.used_at,
        )

    async def mark_used(self, token_id: UUID, when: datetime) -> bool:
        row = await self.session.get(StaffInviteToken, token_id)
        if row is None or row.used_at is not None or row.expires_at <= when:
            return False
        row.used_at = when
        await self.session.flush()
        return True


class RecoveryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace(self, user_id: UUID, code_hashes: list[str], when: datetime) -> None:
        await self.delete_all(user_id)
        for digest in code_hashes:
            self.session.add(
                RecoveryCode(
                    id=new_id(),
                    user_id=user_id,
                    code_hash=digest,
                    created_at=when,
                )
            )
        await self.session.flush()

    async def use_matching(self, user_id: UUID, code_hash: str, when: datetime) -> bool:
        row = await self.session.scalar(
            select(RecoveryCode).where(
                RecoveryCode.user_id == user_id,
                RecoveryCode.code_hash == code_hash,
                RecoveryCode.used_at.is_(None),
            )
        )
        if row is None:
            return False
        row.used_at = when
        await self.session.flush()
        return True

    async def delete_all(self, user_id: UUID) -> None:
        await self.session.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user_id))
        await self.session.flush()


class PhoneChallengeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        phone: str,
        password_hash: str,
        name: str,
        code_hash: str,
        expires_at: datetime,
    ) -> PhoneChallengeRecord:
        row = PhoneOtpChallenge(
            id=new_id(),
            phone=phone,
            password_hash=password_hash,
            name=name,
            code_hash=code_hash,
            expires_at=expires_at,
            attempts=0,
        )
        self.session.add(row)
        await self.session.flush()
        return _phone(row)

    async def latest_open(self, phone: str, now: datetime) -> PhoneChallengeRecord | None:
        row = await self.session.scalar(
            select(PhoneOtpChallenge)
            .where(
                PhoneOtpChallenge.phone == phone,
                PhoneOtpChallenge.used_at.is_(None),
                PhoneOtpChallenge.expires_at > now,
            )
            .order_by(PhoneOtpChallenge.created_at.desc())
            .limit(1)
        )
        if row is None:
            return None
        return _phone(row)

    async def increment_attempts(self, challenge_id: UUID) -> int:
        row = await self.session.get(PhoneOtpChallenge, challenge_id)
        if row is None:
            return 0
        row.attempts += 1
        await self.session.flush()
        return row.attempts

    async def mark_used(self, challenge_id: UUID, when: datetime) -> bool:
        row = await self.session.get(PhoneOtpChallenge, challenge_id)
        if row is None or row.used_at is not None or row.expires_at <= when:
            return False
        row.used_at = when
        await self.session.flush()
        return True


def _reset(row: PasswordResetToken) -> ResetRecord:
    return ResetRecord(
        id=row.id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        expires_at=row.expires_at,
        used_at=row.used_at,
    )


def _phone(row: PhoneOtpChallenge) -> PhoneChallengeRecord:
    return PhoneChallengeRecord(
        id=row.id,
        phone=row.phone,
        password_hash=row.password_hash,
        name=row.name,
        code_hash=row.code_hash,
        expires_at=row.expires_at,
        attempts=row.attempts,
        used_at=row.used_at,
    )
