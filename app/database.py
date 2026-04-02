from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


# Create the async engine.
# connect_args is only needed for SQLite to allow the same connection to be
# used across threads (FastAPI runs in a threadpool for sync code, but we use
# async throughout, so this is a safety net).
_connect_args = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all tables on startup (dev convenience).

    In production you should rely on Alembic migrations instead, but this
    ensures the schema exists when running locally without running migrations
    first.
    """
    # Import models here so Base.metadata is populated before create_all.
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
