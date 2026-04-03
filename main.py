from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import auth, notes, invites, collab


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Run startup and shutdown logic around the application lifetime."""
    # Startup: ensure all tables exist (dev convenience; use Alembic in prod).
    await init_db()
    yield
    # Shutdown: nothing to clean up for SQLite/aiosqlite.


app = FastAPI(
    title="Hush Personal Diary — Shared Notes API",
    description=(
        "Backend for Hush's shared-notes feature. "
        "Private diary entries are AES-256-GCM encrypted on-device and never sent here."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router)
app.include_router(notes.router)
app.include_router(invites.router)
app.include_router(collab.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/", tags=["health"])
async def health_check() -> dict:
    """Simple liveness probe."""
    return {"status": "ok", "service": "hush-backend"}
