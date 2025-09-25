"""In-memory stand-ins for the auth ports."""

from datetime import datetime
from typing import Any
from uuid import UUID

from app.ids import new_id
from app.problems import DuplicateEmailError, DuplicatePhoneError
from app.records import (
    PhoneChallengeRecord,
    RecoveryCodeRecord,
    RefreshRecord,
    ResetRecord,
    UserRecord,
    VerificationRecord,
)


class FakeUsers:
    def __init__(self) -> None:
        self.by_email: dict[str, UserRecord] = {}
        self.by_id: dict[UUID, UserRecord] = {}
        self.by_phone: dict[str, UserRecord] = {}

    async def get_by_email(self, email: str) -> UserRecord | None:
        return self.by_email.get(email.lower())

    async def get_by_id(self, user_id: UUID) -> UserRecord | None:
        return self.by_id.get(user_id)

    async def get_by_phone(self, phone: str) -> UserRecord | None:
        user = self.by_phone.get(phone)
        if user is None or user.deleted_at is not None:
            return None
        return user

    async def add(self, email: str, password_hash: str) -> UserRecord:
        key = email.lower()
        if key in self.by_email:
            raise DuplicateEmailError
        user = UserRecord(
            id=new_id(),
            email=key,
            password_hash=password_hash,
            email_verified_at=None,
            roles=[],
        )
        self.by_email[key] = user
        self.by_id[user.id] = user
        return user

    async def add_phone_user(
        self, phone: str, password_hash: str, name: str, when: datetime
    ) -> UserRecord:
        if phone in self.by_phone and self.by_phone[phone].deleted_at is None:
            raise DuplicatePhoneError
        user = UserRecord(
            id=new_id(),
            email=None,
            password_hash=password_hash,
            email_verified_at=None,
            roles=[],
            name=name,
            phone=phone,
            phone_verified_at=when,
        )
        self.by_id[user.id] = user
        self.by_phone[phone] = user
        return user

    async def assign_role(self, user_id: UUID, role_name: str) -> None:
        user = self.by_id[user_id]
        if role_name not in user.roles:
            user.roles.append(role_name)

    async def list_roles(self, user_id: UUID) -> list[str]:
        user = self.by_id.get(user_id)
        if user is None:
            return []
        return list(user.roles)

    async def list_permissions(self, user_id: UUID) -> list[str]:
        user = self.by_id.get(user_id)
        if user is None:
            return []
        return list(user.permissions)

    async def replace_permissions(self, user_id: UUID, permissions: list[str]) -> None:
        self.by_id[user_id].permissions = list(permissions)

    async def mark_email_verified(self, user_id: UUID, when: datetime) -> None:
        self.by_id[user_id].email_verified_at = when

    async def update_name(self, user_id: UUID, name: str, when: datetime) -> None:
        user = self.by_id[user_id]
        user.name = name
        del when

    async def set_password_hash(self, user_id: UUID, password_hash: str, when: datetime) -> None:
        self.by_id[user_id].password_hash = password_hash
        del when

    async def set_totp_pending(self, user_id: UUID, ciphertext: str) -> None:
        self.by_id[user_id].totp_pending_ciphertext = ciphertext

    async def confirm_totp(self, user_id: UUID, ciphertext: str, when: datetime) -> None:
        user = self.by_id[user_id]
        user.totp_secret_ciphertext = ciphertext
        user.totp_pending_ciphertext = None
        user.totp_confirmed_at = when

    async def clear_totp(self, user_id: UUID) -> None:
        user = self.by_id[user_id]
        user.totp_secret_ciphertext = None
        user.totp_pending_ciphertext = None
        user.totp_confirmed_at = None

    async def mark_deleted(self, user_id: UUID, when: datetime) -> None:
        user = self.by_id[user_id]
        user.deleted_at = when
        if user.phone and self.by_phone.get(user.phone) is user:
            del self.by_phone[user.phone]


class FakeVerifications:
    def __init__(self) -> None:
        self.rows: list[VerificationRecord] = []

    async def add(self, user_id: UUID, token_hash: str, expires_at: datetime) -> VerificationRecord:
        row = VerificationRecord(
            id=new_id(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            used_at=None,
        )
        self.rows.append(row)
        return row

    async def get_by_hash(self, token_hash: str) -> VerificationRecord | None:
        for row in self.rows:
            if row.token_hash == token_hash:
                return row
        return None

    async def mark_used(self, token_id: UUID, when: datetime) -> bool:
        for row in self.rows:
            if row.id != token_id:
                continue
            if row.used_at is not None or row.expires_at <= when:
                return False
            row.used_at = when
            return True
        return False


class FakeRefreshes:
    def __init__(self) -> None:
        self.rows: list[RefreshRecord] = []

    async def add(self, record: RefreshRecord) -> None:
        self.rows.append(record)

    async def get_by_hash(self, token_hash: str) -> RefreshRecord | None:
        for row in self.rows:
            if row.token_hash == token_hash:
                return row
        return None

    async def mark_replaced(self, token_id: UUID, new_id: UUID, when: datetime) -> None:
        for row in self.rows:
            if row.id == token_id:
                row.replaced_by_id = new_id
                row.revoked_at = when

    async def revoke_family(self, family_id: UUID, when: datetime) -> None:
        for row in self.rows:
            if row.family_id == family_id and row.revoked_at is None:
                row.revoked_at = when

    async def list_for_user(self, user_id: UUID) -> list[RefreshRecord]:
        return [row for row in self.rows if row.user_id == user_id]

    async def revoke_all_for_user(self, user_id: UUID, when: datetime) -> None:
        for row in self.rows:
            if row.user_id == user_id and row.revoked_at is None:
                row.revoked_at = when


class FakeAudit:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

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
        self.rows.append(
            {
                "actor_id": actor_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "metadata": metadata,
                "request_id": request_id,
            }
        )


class FakeMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []
        self.resets: list[tuple[str, str]] = []
        self.invites: list[tuple[str, str]] = []

    async def send_verification(self, email: str, token: str) -> None:
        self.sent.append((email, token))

    async def send_password_reset(self, email: str, token: str) -> None:
        self.resets.append((email, token))

    async def send_staff_invite(self, email: str, token: str) -> None:
        self.invites.append((email, token))


class FakeLimiter:
    def __init__(self) -> None:
        self.hits: list[tuple[str, tuple[str, ...]]] = []

    async def check(self, ip: str, email: str) -> None:
        del ip, email

    async def hit(self, scope: str, *parts: str) -> None:
        self.hits.append((scope, parts))


class FakeOpaqueTokens:
    def __init__(self) -> None:
        self.rows: list[ResetRecord] = []

    async def add(self, user_id: UUID, token_hash: str, expires_at: datetime) -> ResetRecord:
        row = ResetRecord(
            id=new_id(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            used_at=None,
        )
        self.rows.append(row)
        return row

    async def get_by_hash(self, token_hash: str) -> ResetRecord | None:
        for row in self.rows:
            if row.token_hash == token_hash:
                return row
        return None

    async def mark_used(self, token_id: UUID, when: datetime) -> bool:
        for row in self.rows:
            if row.id != token_id:
                continue
            if row.used_at is not None or row.expires_at <= when:
                return False
            row.used_at = when
            return True
        return False


class FakeRecovery:
    def __init__(self) -> None:
        self.rows: list[RecoveryCodeRecord] = []

    async def replace(self, user_id: UUID, code_hashes: list[str], when: datetime) -> None:
        await self.delete_all(user_id)
        for digest in code_hashes:
            self.rows.append(
                RecoveryCodeRecord(id=new_id(), user_id=user_id, code_hash=digest, used_at=None)
            )
        del when

    async def use_matching(self, user_id: UUID, code_hash: str, when: datetime) -> bool:
        for row in self.rows:
            if row.user_id == user_id and row.code_hash == code_hash and row.used_at is None:
                row.used_at = when
                return True
        return False

    async def delete_all(self, user_id: UUID) -> None:
        self.rows = [row for row in self.rows if row.user_id != user_id]


class FakePhoneChallenges:
    def __init__(self) -> None:
        self.rows: list[PhoneChallengeRecord] = []

    async def add(
        self,
        phone: str,
        password_hash: str,
        name: str,
        code_hash: str,
        expires_at: datetime,
    ) -> PhoneChallengeRecord:
        row = PhoneChallengeRecord(
            id=new_id(),
            phone=phone,
            password_hash=password_hash,
            name=name,
            code_hash=code_hash,
            expires_at=expires_at,
            attempts=0,
            used_at=None,
        )
        self.rows.append(row)
        return row

    async def latest_open(self, phone: str, now: datetime) -> PhoneChallengeRecord | None:
        open_rows = [
            row
            for row in self.rows
            if row.phone == phone and row.used_at is None and row.expires_at > now
        ]
        if not open_rows:
            return None
        return open_rows[-1]

    async def increment_attempts(self, challenge_id: UUID) -> int:
        for row in self.rows:
            if row.id == challenge_id:
                row.attempts += 1
                return row.attempts
        return 0

    async def mark_used(self, challenge_id: UUID, when: datetime) -> bool:
        for row in self.rows:
            if row.id != challenge_id:
                continue
            if row.used_at is not None or row.expires_at <= when:
                return False
            row.used_at = when
            return True
        return False


class FakeSms:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    async def send_otp(self, phone: str, code: str) -> None:
        self.sent.append((phone, code))
