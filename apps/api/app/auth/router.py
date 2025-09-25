"""HTTP adapter for auth. Rules live in AuthService and PhoneService."""

import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.repository import AuditRepository, AuditService
from app.auth.mailer import ArqMailer, ArqSms
from app.auth.phone_service import PhoneService
from app.auth.repository import RefreshRepository, VerificationRepository
from app.auth.schemas import (
    AuthConfigOut,
    CsrfOut,
    ForgotIn,
    LoginIn,
    LoginOut,
    MessageOut,
    PhoneConfirmIn,
    PhoneLoginIn,
    PhoneStartIn,
    RegisterIn,
    ResetIn,
    SecondFactorIn,
    SessionOut,
    SessionsOut,
    TotpConfirmOut,
    TotpSetupOut,
    VerifyIn,
)
from app.auth.service import (
    DISABLE_MESSAGE,
    ENABLE_MESSAGE,
    INVITE_DONE,
    LOGIN_STEP_MESSAGE,
    RESET_DONE,
    AuthService,
)
from app.auth.token_stores import (
    InviteRepository,
    PhoneChallengeRepository,
    RecoveryRepository,
    ResetRepository,
)
from app.config import Settings, get_settings
from app.logging_config import current_request_id
from app.problems import PROBLEM_INTERNAL, PROBLEM_UNAUTHORIZED, InvalidAccessToken, ProblemError
from app.records import (
    LOGIN_MESSAGE,
    LOGOUT_EVERYWHERE_MESSAGE,
    LOGOUT_MESSAGE,
    PHONE_CONFIRMED_MESSAGE,
    REFRESH_MESSAGE,
    RESET_MESSAGE,
    VERIFY_MESSAGE,
    LoginResult,
    TokenPair,
    UserRecord,
)
from app.security.cookies import (
    ACCESS_COOKIE,
    CHALLENGE_COOKIE,
    ENROLL_COOKIE,
    REFRESH_COOKIE,
    clear_session_cookies,
    clear_ticket_cookies,
    set_csrf_cookie,
    set_session_cookies,
    set_ticket_cookie,
)
from app.security.deps import get_profile
from app.security.rate_limit import RedisRateLimiter
from app.security.tokens import decode_access_token, decode_ticket
from app.session import get_session
from app.users.repository import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:64]
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def get_redis(request: Request) -> Redis:
    client: Redis = request.app.state.redis
    return client


def _service(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    request: Request,
) -> AuthService:
    return AuthService(
        users=UserRepository(session),
        verifications=VerificationRepository(session),
        refreshes=RefreshRepository(session),
        audit=AuditService(AuditRepository(session)),
        mailer=ArqMailer(request.app.state.arq),
        limiter=RedisRateLimiter(
            redis,
            limit=settings.login_rate_limit,
            window_seconds=settings.login_rate_window_seconds,
        ),
        secret=settings.secret_key,
        breach_mode=settings.breach_check,
        access_minutes=settings.access_token_minutes,
        refresh_days=settings.refresh_token_days,
        verification_minutes=settings.verification_minutes,
        recovery=RecoveryRepository(session),
        resets=ResetRepository(session),
        invites=InviteRepository(session),
        reset_limiter=RedisRateLimiter(
            redis,
            limit=settings.reset_rate_limit,
            window_seconds=settings.reset_rate_window_seconds,
            detail="Too many reset attempts. Try again later.",
        ),
        totp_key=settings.totp_encryption_key,
        ticket_minutes=settings.ticket_minutes,
        reset_minutes=settings.reset_token_minutes,
        invite_hours=settings.staff_invite_hours,
    )


def _phone_service(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    request: Request,
) -> PhoneService:
    return PhoneService(
        users=UserRepository(session),
        challenges=PhoneChallengeRepository(session),
        sms=ArqSms(request.app.state.arq),
        limiter=RedisRateLimiter(
            redis,
            limit=settings.phone_rate_limit,
            window_seconds=settings.phone_rate_window_seconds,
            detail="Too many attempts. Try again later.",
        ),
        audit=AuditService(AuditRepository(session)),
        breach_mode=settings.breach_check,
        otp_minutes=settings.phone_otp_minutes,
        max_attempts=settings.phone_otp_max_attempts,
    )


async def _commit(session: AsyncSession) -> None:
    await session.commit()


def _apply_session(response: Response, pair: TokenPair, settings: Settings) -> None:
    set_session_cookies(
        response,
        pair,
        access_max_age=settings.access_token_minutes * 60,
        refresh_max_age=settings.refresh_token_days * 24 * 60 * 60,
    )


def _apply_login(response: Response, result: LoginResult, settings: Settings) -> LoginOut:
    if result.next_step == "session" and result.tokens is not None:
        clear_ticket_cookies(response)
        _apply_session(response, result.tokens, settings)
    elif result.ticket is not None and result.next_step in {"enroll", "challenge"}:
        clear_session_cookies(response)
        clear_ticket_cookies(response)
        key = ENROLL_COOKIE if result.next_step == "enroll" else CHALLENGE_COOKIE
        set_ticket_cookie(response, key, result.ticket, settings.ticket_minutes * 60)
    else:
        raise ProblemError(500, "Internal Server Error", "Something went wrong.", PROBLEM_INTERNAL)
    return LoginOut(message=LOGIN_STEP_MESSAGE[result.next_step], next=result.next_step)


def _unauthorized() -> ProblemError:
    return ProblemError(401, "Unauthorized", "Authentication required.", PROBLEM_UNAUTHORIZED)


def _totp_subject(request: Request, settings: Settings) -> tuple[UUID, bool]:
    access = request.cookies.get(ACCESS_COOKIE)
    if access:
        try:
            return decode_access_token(access, settings.secret_key), False
        except InvalidAccessToken:
            pass
    enroll = request.cookies.get(ENROLL_COOKIE)
    if enroll:
        try:
            return decode_ticket(enroll, settings.secret_key, "enroll"), True
        except InvalidAccessToken:
            pass
    raise _unauthorized()


async def _limit_totp(redis: Redis, settings: Settings, request: Request, user_id: UUID) -> None:
    limiter = RedisRateLimiter(
        redis,
        limit=settings.totp_rate_limit,
        window_seconds=settings.totp_rate_window_seconds,
        detail="Too many attempts. Try again later.",
    )
    await limiter.hit("totp", _client_ip(request), str(user_id))


@router.get("/config", response_model=AuthConfigOut)
async def auth_config(settings: Settings = Depends(get_settings)) -> AuthConfigOut:
    return AuthConfigOut(phone_registration_enabled=settings.phone_registration_enabled)


@router.get("/csrf", response_model=CsrfOut)
async def issue_csrf(response: Response) -> CsrfOut:
    token = secrets.token_urlsafe(32)
    set_csrf_cookie(response, token)
    return CsrfOut(token=token)


@router.post("/register", status_code=201, response_model=MessageOut)
async def register(
    body: RegisterIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> MessageOut:
    outcome = await _service(session, redis, settings, request).register(
        body.email,
        body.password,
        current_request_id(),
        before_mail=lambda: _commit(session),
    )
    await _commit(session)
    return MessageOut(message=outcome.message)


@router.post("/verify-email", response_model=MessageOut)
async def verify_email(
    body: VerifyIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> MessageOut:
    await _service(session, redis, settings, request).verify_email(body.token, current_request_id())
    await _commit(session)
    return MessageOut(message=VERIFY_MESSAGE)


@router.post("/login", response_model=LoginOut)
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> LoginOut:
    result = await _service(session, redis, settings, request).login(
        body.email,
        body.password,
        _client_ip(request),
        current_request_id(),
    )
    await _commit(session)
    return _apply_login(response, result, settings)


@router.post("/login/phone", response_model=LoginOut)
async def login_phone(
    body: PhoneLoginIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> LoginOut:
    result = await _service(session, redis, settings, request).login_phone(
        body.phone,
        body.password,
        _client_ip(request),
        current_request_id(),
        enabled=settings.phone_registration_enabled,
    )
    await _commit(session)
    return _apply_login(response, result, settings)


@router.post("/refresh", response_model=MessageOut)
async def refresh(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> MessageOut:
    pair = await _service(session, redis, settings, request).refresh(
        request.cookies.get(REFRESH_COOKIE),
        current_request_id(),
    )
    await _commit(session)
    _apply_session(response, pair, settings)
    return MessageOut(message=REFRESH_MESSAGE)


@router.post("/logout", response_model=MessageOut)
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> MessageOut:
    await _service(session, redis, settings, request).logout(
        request.cookies.get(REFRESH_COOKIE),
        current_request_id(),
    )
    await _commit(session)
    clear_session_cookies(response)
    clear_ticket_cookies(response)
    return MessageOut(message=LOGOUT_MESSAGE)


@router.post("/logout-everywhere", response_model=MessageOut)
async def logout_everywhere(
    request: Request,
    response: Response,
    current: UserRecord = Depends(get_profile),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> MessageOut:
    await _service(session, redis, settings, request).logout_everywhere(
        current.id,
        current_request_id(),
    )
    await _commit(session)
    clear_session_cookies(response)
    clear_ticket_cookies(response)
    return MessageOut(message=LOGOUT_EVERYWHERE_MESSAGE)


@router.get("/sessions", response_model=SessionsOut)
async def sessions(
    request: Request,
    current: UserRecord = Depends(get_profile),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> SessionsOut:
    rows = await _service(session, redis, settings, request).list_sessions(
        current.id,
        request.cookies.get(REFRESH_COOKIE),
    )
    return SessionsOut(
        sessions=[
            SessionOut(
                family_id=row.family_id,
                created_at=row.created_at,
                expires_at=row.expires_at,
                current=row.current,
            )
            for row in rows
        ]
    )


@router.post("/forgot-password", response_model=MessageOut)
async def forgot_password(
    body: ForgotIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> MessageOut:
    message = await _service(session, redis, settings, request).request_password_reset(
        body.email,
        _client_ip(request),
        current_request_id(),
        before_mail=lambda: _commit(session),
    )
    await _commit(session)
    return MessageOut(message=message or RESET_MESSAGE)


@router.post("/reset-password", response_model=MessageOut)
async def reset_password(
    body: ResetIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> MessageOut:
    await _service(session, redis, settings, request).reset_password(
        body.token,
        body.password,
        current_request_id(),
    )
    await _commit(session)
    return MessageOut(message=RESET_DONE)


@router.post("/accept-invite", response_model=MessageOut)
async def accept_invite(
    body: ResetIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> MessageOut:
    await _service(session, redis, settings, request).accept_invite(
        body.token,
        body.password,
        current_request_id(),
    )
    await _commit(session)
    return MessageOut(message=INVITE_DONE)


@router.post("/phone/start", response_model=MessageOut)
async def phone_start(
    body: PhoneStartIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> MessageOut:
    message = await _phone_service(session, redis, settings, request).start(
        body.phone,
        body.password,
        body.name,
        _client_ip(request),
        enabled=settings.phone_registration_enabled,
        before_send=lambda: _commit(session),
    )
    await _commit(session)
    return MessageOut(message=message)


@router.post("/phone/confirm", response_model=MessageOut)
async def phone_confirm(
    body: PhoneConfirmIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> MessageOut:
    message = await _phone_service(session, redis, settings, request).confirm(
        body.phone,
        body.code,
        current_request_id(),
        enabled=settings.phone_registration_enabled,
    )
    await _commit(session)
    return MessageOut(message=message or PHONE_CONFIRMED_MESSAGE)


@router.post("/totp/setup", response_model=TotpSetupOut)
async def totp_setup(
    request: Request,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> TotpSetupOut:
    user_id, _issue = _totp_subject(request, settings)
    await _limit_totp(redis, settings, request, user_id)
    started = await _service(session, redis, settings, request).start_totp_setup(user_id)
    await _commit(session)
    return TotpSetupOut(
        otpauth_uri=started.otpauth_uri, secret=started.secret, qr_svg=started.qr_svg
    )


@router.post("/totp/confirm", response_model=TotpConfirmOut)
async def totp_confirm(
    body: SecondFactorIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> TotpConfirmOut:
    user_id, issue_session = _totp_subject(request, settings)
    await _limit_totp(redis, settings, request, user_id)
    confirmed = await _service(session, redis, settings, request).confirm_totp(
        user_id,
        body.code,
        current_request_id(),
        issue_session=issue_session,
    )
    await _commit(session)
    if confirmed.tokens is not None:
        clear_ticket_cookies(response)
        _apply_session(response, confirmed.tokens, settings)
    return TotpConfirmOut(message=ENABLE_MESSAGE, recovery_codes=confirmed.recovery_codes)


@router.post("/totp/challenge", response_model=LoginOut)
async def totp_challenge(
    body: SecondFactorIn,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> LoginOut:
    raw = request.cookies.get(CHALLENGE_COOKIE)
    if not raw:
        raise _unauthorized()
    try:
        user_id = decode_ticket(raw, settings.secret_key, "challenge")
    except InvalidAccessToken:
        raise _unauthorized() from None
    await _limit_totp(redis, settings, request, user_id)
    pair = await _service(session, redis, settings, request).finish_challenge(
        user_id,
        body.code,
        current_request_id(),
    )
    await _commit(session)
    clear_ticket_cookies(response)
    _apply_session(response, pair, settings)
    return LoginOut(message=LOGIN_MESSAGE, next="session")


@router.post("/totp/disable", response_model=MessageOut)
async def totp_disable(
    body: SecondFactorIn,
    request: Request,
    current: UserRecord = Depends(get_profile),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> MessageOut:
    await _limit_totp(redis, settings, request, current.id)
    await _service(session, redis, settings, request).disable_totp(
        current.id,
        body.code,
        current_request_id(),
    )
    await _commit(session)
    return MessageOut(message=DISABLE_MESSAGE)
