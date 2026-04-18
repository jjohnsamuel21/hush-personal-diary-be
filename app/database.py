import ssl

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


# Create the async engine.
_connect_args: dict = {}
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
elif settings.database_url.startswith("postgresql"):
    # asyncpg requires ssl via connect_args, not URL query params.
    # Supabase's session pooler uses a self-signed intermediate cert, so we
    # require encryption but skip chain verification (standard for Supabase pooler).
    _ssl_ctx = ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = ssl.CERT_NONE
    _connect_args = {"ssl": _ssl_ctx}

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
