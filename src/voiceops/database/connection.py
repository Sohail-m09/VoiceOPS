
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from voiceops.config import get_settings

settings = get_settings()

if not settings.database_url:
    raise RuntimeError("DATABASE_URL is missing from configuration.")


engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def close_db() -> None:
    await engine.dispose()
