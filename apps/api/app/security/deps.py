"""Access-cookie identity. Staff routes add require_access on top."""

from collections.abc import Awaitable, Callable

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.problems import PROBLEM_UNAUTHORIZED, InvalidAccessToken, ProblemError
from app.records import UserRecord
from app.security.cookies import ACCESS_COOKIE
from app.security.policy import Access, Actor, authorize
from app.security.tokens import decode_access_token
from app.session import get_session
from app.users.repository import UserRepository


async def get_profile(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> UserRecord:
    raw = request.cookies.get(ACCESS_COOKIE)
    if not raw:
        raise _unauthorized()
    try:
        user_id = decode_access_token(raw, get_settings().secret_key)
    except InvalidAccessToken:
        raise _unauthorized() from None
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if user is None or user.deleted_at is not None:
        raise _unauthorized()
    user.roles = await repo.list_roles(user_id)
    user.permissions = await repo.list_permissions(user_id)
    return user


def require_access(access: Access) -> Callable[..., Awaitable[UserRecord]]:
    async def dependency(user: UserRecord = Depends(get_profile)) -> UserRecord:
        authorize(
            Actor(
                user_id=user.id,
                roles=frozenset(user.roles),
                permissions=frozenset(user.permissions),
                totp_enabled=user.totp_confirmed_at is not None,
            ),
            access,
        )
        return user

    return dependency


def _unauthorized() -> ProblemError:
    return ProblemError(401, "Unauthorized", "Authentication required.", PROBLEM_UNAUTHORIZED)
