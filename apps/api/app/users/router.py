"""Current user. Requires the access cookie. /me is always the token subject."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.repository import AuditRepository, AuditService
from app.auth.repository import RefreshRepository
from app.auth.schemas import MessageOut
from app.logging_config import current_request_id
from app.records import DELETE_MESSAGE, UserRecord
from app.security.cookies import clear_session_cookies, clear_ticket_cookies
from app.security.deps import get_profile
from app.session import get_session
from app.users.repository import UserRepository
from app.users.schemas import MeOut, ProfilePatch, to_me
from app.users.service import UserService

router = APIRouter(prefix="/users", tags=["users"])


def _users(session: AsyncSession) -> UserService:
    return UserService(UserRepository(session))


@router.get("/me", response_model=MeOut)
async def me(current: UserRecord = Depends(get_profile)) -> MeOut:
    return to_me(current)


@router.patch("/me", response_model=MeOut)
async def patch_me(
    body: ProfilePatch,
    current: UserRecord = Depends(get_profile),
    session: AsyncSession = Depends(get_session),
) -> MeOut:
    updated = await _users(session).update_name(current.id, body.name)
    await session.commit()
    return to_me(updated)


@router.get("/me/export", response_model=MeOut)
async def export_me(
    response: Response,
    current: UserRecord = Depends(get_profile),
) -> MeOut:
    response.headers["Content-Disposition"] = 'attachment; filename="account.json"'
    return to_me(current)


@router.delete("/me", response_model=MessageOut)
async def delete_me(
    response: Response,
    current: UserRecord = Depends(get_profile),
    session: AsyncSession = Depends(get_session),
) -> MessageOut:
    await _users(session).delete_me(
        current.id,
        RefreshRepository(session),
        AuditService(AuditRepository(session)),
        current_request_id(),
    )
    await session.commit()
    clear_session_cookies(response)
    clear_ticket_cookies(response)
    return MessageOut(message=DELETE_MESSAGE)
