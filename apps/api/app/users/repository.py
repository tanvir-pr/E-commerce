"""User persistence."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import utc_now
from app.ids import new_id
from app.models.role import Role, StaffPermission, UserRole
from app.models.user import User
from app.problems import DuplicateEmailError, DuplicatePhoneError, RoleMissingError
from app.records import UserRecord


def _to_record(user: User) -> UserRecord:
    return UserRecord(
        id=user.id,
        email=user.email,
        password_hash=user.password_hash,
        email_verified_at=user.email_verified_at,
        roles=[],
        name=user.name,
        phone=user.phone,
        phone_verified_at=user.phone_verified_at,
        totp_secret_ciphertext=user.totp_secret_ciphertext,
        totp_pending_ciphertext=user.totp_pending_ciphertext,
        totp_confirmed_at=user.totp_confirmed_at,
        deleted_at=user.deleted_at,
    )


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> UserRecord | None:
        user = await self.session.scalar(select(User).where(User.email == email))
        if user is None:
            return None
        return _to_record(user)

    async def get_by_id(self, user_id: UUID) -> UserRecord | None:
        user = await self.session.get(User, user_id)
        if user is None:
            return None
        return _to_record(user)

    async def get_by_phone(self, phone: str) -> UserRecord | None:
        user = await self.session.scalar(
            select(User).where(User.phone == phone, User.deleted_at.is_(None))
        )
        if user is None:
            return None
        return _to_record(user)

    async def add(self, email: str, password_hash: str) -> UserRecord:
        now = utc_now()
        user = User(
            id=new_id(),
            email=email,
            password_hash=password_hash,
            created_at=now,
            updated_at=now,
        )
        self.session.add(user)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicateEmailError from exc
        return _to_record(user)

    async def add_phone_user(
        self, phone: str, password_hash: str, name: str, when: datetime
    ) -> UserRecord:
        user = User(
            id=new_id(),
            email=None,
            password_hash=password_hash,
            phone=phone,
            phone_verified_at=when,
            name=name,
            created_at=when,
            updated_at=when,
        )
        self.session.add(user)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise DuplicatePhoneError from exc
        return _to_record(user)

    async def assign_role(self, user_id: UUID, role_name: str) -> None:
        role = await self.session.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            raise RoleMissingError(role_name)
        self.session.add(UserRole(user_id=user_id, role_id=role.id))
        await self.session.flush()

    async def list_roles(self, user_id: UUID) -> list[str]:
        stmt = (
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.name)
        )
        return list(await self.session.scalars(stmt))

    async def list_permissions(self, user_id: UUID) -> list[str]:
        stmt = (
            select(StaffPermission.permission)
            .where(StaffPermission.user_id == user_id)
            .order_by(StaffPermission.permission)
        )
        return list(await self.session.scalars(stmt))

    async def replace_permissions(self, user_id: UUID, permissions: list[str]) -> None:
        await self.session.execute(
            delete(StaffPermission).where(StaffPermission.user_id == user_id)
        )
        for name in permissions:
            self.session.add(StaffPermission(user_id=user_id, permission=name))
        await self.session.flush()

    async def mark_email_verified(self, user_id: UUID, when: datetime) -> None:
        user = await self.session.get(User, user_id)
        if user is None:
            return
        user.email_verified_at = when
        user.updated_at = when
        await self.session.flush()

    async def update_name(self, user_id: UUID, name: str, when: datetime) -> None:
        user = await self.session.get(User, user_id)
        if user is None:
            return
        user.name = name
        user.updated_at = when
        await self.session.flush()

    async def set_password_hash(self, user_id: UUID, password_hash: str, when: datetime) -> None:
        user = await self.session.get(User, user_id)
        if user is None:
            return
        user.password_hash = password_hash
        user.updated_at = when
        await self.session.flush()

    async def set_totp_pending(self, user_id: UUID, ciphertext: str) -> None:
        user = await self.session.get(User, user_id)
        if user is None:
            return
        user.totp_pending_ciphertext = ciphertext
        user.updated_at = utc_now()
        await self.session.flush()

    async def confirm_totp(self, user_id: UUID, ciphertext: str, when: datetime) -> None:
        user = await self.session.get(User, user_id)
        if user is None:
            return
        user.totp_secret_ciphertext = ciphertext
        user.totp_pending_ciphertext = None
        user.totp_confirmed_at = when
        user.updated_at = when
        await self.session.flush()

    async def clear_totp(self, user_id: UUID) -> None:
        user = await self.session.get(User, user_id)
        if user is None:
            return
        user.totp_secret_ciphertext = None
        user.totp_pending_ciphertext = None
        user.totp_confirmed_at = None
        user.updated_at = utc_now()
        await self.session.flush()

    async def mark_deleted(self, user_id: UUID, when: datetime) -> None:
        user = await self.session.get(User, user_id)
        if user is None:
            return
        user.deleted_at = when
        user.updated_at = when
        await self.session.flush()
