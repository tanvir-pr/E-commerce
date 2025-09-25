"""Staff and super-admin routes. Each route declares its role and permission."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.schemas import (
    AuditEventOut,
    AuditListOut,
    QueueOut,
    StaffCreateIn,
    StaffOut,
    StaffPermissionsIn,
    StaffPermissionsOut,
)
from app.admin.service import AdminService
from app.audit.repository import AuditQuery, AuditRepository, AuditService
from app.auth.mailer import ArqMailer
from app.auth.token_stores import InviteRepository
from app.config import Settings, get_settings
from app.logging_config import current_request_id
from app.records import UserRecord
from app.security.deps import require_access
from app.security.policy import Access
from app.session import get_session
from app.users.repository import UserRepository

router = APIRouter(prefix="/admin", tags=["admin"])

# Super admin only. No staff permission applies.
SUPER_ADMIN_ACCESS = Access(roles=frozenset({"super_admin"}), permission=None, require_totp=True)
# Staff permission "support". Warehouse staff do not pass.
SUPPORT_ACCESS = Access(
    roles=frozenset({"staff", "super_admin"}),
    permission="support",
    require_totp=True,
)
WAREHOUSE_ACCESS = Access(
    roles=frozenset({"staff", "super_admin"}),
    permission="warehouse",
    require_totp=True,
)


async def _commit(session: AsyncSession) -> None:
    await session.commit()


def _admin(session: AsyncSession, request: Request, settings: Settings) -> AdminService:
    return AdminService(
        users=UserRepository(session),
        invites=InviteRepository(session),
        audit=AuditService(AuditRepository(session)),
        mailer=ArqMailer(request.app.state.arq),
        invite_hours=settings.staff_invite_hours,
    )


@router.post("/staff", status_code=201, response_model=StaffOut)
async def create_staff(
    body: StaffCreateIn,
    request: Request,
    actor: UserRecord = Depends(require_access(SUPER_ADMIN_ACCESS)),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> StaffOut:
    created = await _admin(session, request, settings).create_staff(
        actor.id,
        body.email,
        body.name,
        list(body.permissions),
        current_request_id(),
        before_mail=lambda: _commit(session),
    )
    await _commit(session)
    return StaffOut(id=created.id, email=created.email, permissions=created.permissions)


@router.put("/staff/{user_id}/permissions", response_model=StaffPermissionsOut)
async def replace_staff_permissions(
    user_id: UUID,
    body: StaffPermissionsIn,
    request: Request,
    actor: UserRecord = Depends(require_access(SUPER_ADMIN_ACCESS)),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> StaffPermissionsOut:
    permissions = await _admin(session, request, settings).replace_permissions(
        actor.id,
        user_id,
        list(body.permissions),
        current_request_id(),
    )
    await _commit(session)
    return StaffPermissionsOut(user_id=user_id, permissions=permissions)


@router.get("/audit", response_model=AuditListOut)
async def recent_audit(
    limit: int = Query(default=50, ge=1, le=50),
    _actor: UserRecord = Depends(require_access(SUPER_ADMIN_ACCESS)),
    session: AsyncSession = Depends(get_session),
) -> AuditListOut:
    rows = await AuditQuery(session).list_recent(limit)
    return AuditListOut(
        events=[
            AuditEventOut(
                id=row.id,
                actor_id=row.actor_id,
                actor_email=row.actor_email,
                action=row.action,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )


@router.get("/support/queue", response_model=QueueOut)
async def support_queue(
    _actor: UserRecord = Depends(require_access(SUPPORT_ACCESS)),
) -> QueueOut:
    return QueueOut(status="empty")


@router.get("/warehouse/queue", response_model=QueueOut)
async def warehouse_queue(
    _actor: UserRecord = Depends(require_access(WAREHOUSE_ACCESS)),
) -> QueueOut:
    return QueueOut(status="empty")
