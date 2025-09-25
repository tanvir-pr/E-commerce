"""FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from arq.connections import RedisSettings, create_pool
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.config import get_settings
from app.health import router as health_router
from app.logging_config import current_request_id, setup_logging
from app.middleware import CSRFMiddleware, RequestContextMiddleware
from app.problems import PROBLEM_INTERNAL, PROBLEM_VALIDATION, ProblemError, problem_payload
from app.security.totp import ensure_totp_key
from app.session import engine
from app.users.router import router as users_router

setup_logging()
log = structlog.get_logger()


def _validation_errors(exc: RequestValidationError) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for item in exc.errors():
        loc = item.get("loc", [])
        parts = [str(part) for part in loc if part not in {"body", "query", "path"}]
        field = ".".join(parts) if parts else "request"
        errors.append({"field": field, "message": str(item.get("msg", "Invalid value"))})
    return errors


def create_app() -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        ensure_totp_key(settings.totp_encryption_key)
        app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
        app.state.arq = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        log.info(
            "app_started",
            app_env=settings.app_env,
            breach_check=settings.breach_check,
            phone_registration_enabled=settings.phone_registration_enabled,
            sms_provider=settings.sms_provider,
        )
        yield
        await app.state.arq.close()
        await app.state.redis.aclose()
        await engine.dispose()

    app = FastAPI(title="Store API", version="0.2.0", lifespan=lifespan)

    @app.exception_handler(ProblemError)
    async def handle_problem(_request: Request, exc: ProblemError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=problem_payload(exc, current_request_id()),
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        problem = ProblemError(
            422,
            "Validation error",
            "One or more fields are invalid.",
            PROBLEM_VALIDATION,
            errors=_validation_errors(exc),
        )
        return JSONResponse(
            status_code=422,
            content=problem_payload(problem, current_request_id()),
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_error", error_type=type(exc).__name__)
        problem = ProblemError(
            500,
            "Internal Server Error",
            "Something went wrong.",
            PROBLEM_INTERNAL,
        )
        return JSONResponse(
            status_code=500,
            content=problem_payload(problem, current_request_id()),
            media_type="application/problem+json",
        )

    # Last added runs first: CORS, then request id, then CSRF.
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID", "Accept"],
    )

    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    return app


app = create_app()
