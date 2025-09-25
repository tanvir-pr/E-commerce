"""Import models so Alembic and the ORM see every table."""

from app.models.audit import AuditLog
from app.models.role import Role, StaffPermission, UserRole
from app.models.security import (
    PasswordResetToken,
    PhoneOtpChallenge,
    RecoveryCode,
    StaffInviteToken,
)
from app.models.token import EmailVerificationToken, RefreshToken
from app.models.user import User

__all__ = [
    "AuditLog",
    "EmailVerificationToken",
    "PasswordResetToken",
    "PhoneOtpChallenge",
    "RecoveryCode",
    "RefreshToken",
    "Role",
    "StaffInviteToken",
    "StaffPermission",
    "User",
    "UserRole",
]
