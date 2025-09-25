"""Async engine. Alembic does not import this module."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.problems import ProblemError

settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionFactory() as session:
        try:
            yield session
        except ProblemError as exc:
            # Keep audit rows for expected failures. Roll back partial 500s.
            if exc.status >= 500:
                await session.rollback()
            else:
                await session.commit()
            raise
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
