"""Roles and staff permissions. Permissions are support, warehouse, and moderation."""

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.ids import new_id


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    role_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True
    )


class StaffPermission(Base):
    __tablename__ = "staff_permissions"
    __table_args__ = (
        CheckConstraint(
            "permission IN ('support', 'warehouse', 'moderation')",
            name="ck_staff_permission",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    permission: Mapped[str] = mapped_column(String(32), primary_key=True)
