"""Create the super admin from SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD.

Skips when that email already exists. Refuses when APP_ENV=production and the
password is still the example placeholder. Never prints the password.
"""

import asyncio
import sys

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.clock import utc_now
from app.config import get_settings
from app.ids import new_id
from app.logging_config import setup_logging
from app.models.role import Role, UserRole
from app.models.user import User
from app.security.passwords import hash_password, password_is_breached

PLACEHOLDER_SEED_PASSWORD = "replace-this-password"


class SeedRefused(Exception):
    """Raised when production seed settings are still the example values."""


def ensure_seed_allowed(app_env: str, password: str) -> None:
    if app_env == "production" and password == PLACEHOLDER_SEED_PASSWORD:
        raise SeedRefused(
            "Refusing to seed: APP_ENV=production and "
            "SEED_ADMIN_PASSWORD is the example placeholder."
        )


async def run() -> None:
    setup_logging()
    log = structlog.get_logger()
    settings = get_settings()
    try:
        ensure_seed_allowed(settings.app_env, settings.seed_admin_password)
    except SeedRefused as exc:
        log.error("seed_superadmin_refused")
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
    if not settings.seed_admin_email or "@" not in settings.seed_admin_email:
        print("SEED_ADMIN_EMAIL is required", file=sys.stderr)
        raise SystemExit(1)
    if len(settings.seed_admin_password) < 10:
        print("SEED_ADMIN_PASSWORD must be at least 10 characters", file=sys.stderr)
        raise SystemExit(1)
    if password_is_breached(settings.seed_admin_password, settings.breach_check):
        print("SEED_ADMIN_PASSWORD was rejected by the breach check", file=sys.stderr)
        raise SystemExit(1)

    engine = create_async_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    email = settings.seed_admin_email.strip().lower()
    try:
        async with factory() as session:
            existing = await session.scalar(select(User).where(User.email == email))
            if existing is not None:
                log.info("seed_superadmin_skipped", message="Super admin already exists")
                return
            now = utc_now()
            user = User(
                id=new_id(),
                email=email,
                password_hash=hash_password(settings.seed_admin_password),
                email_verified_at=now,
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            await session.flush()
            role = await session.scalar(select(Role).where(Role.name == "super_admin"))
            if role is None:
                print(
                    "super_admin role is missing. Run alembic upgrade head first.", file=sys.stderr
                )
                raise SystemExit(1)
            session.add(UserRole(user_id=user.id, role_id=role.id))
            await session.commit()
            log.info("seed_superadmin_created", message="Seeded super admin")
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
