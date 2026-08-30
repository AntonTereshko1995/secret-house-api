from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from config import settings
from db.database import engine
from db.models.base import Base
import db.models  # noqa: F401 — register all models before create_all
from logger import setup_logger
from routers import admin, bookings, gifts, promocodes

setup_logger()

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def _run_sql_migrations() -> None:
    """Execute all *.sql files in migrations/ in filename order. Each file is
    idempotent (IF NOT EXISTS guards), so re-running on restart is safe."""
    sql_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    if not sql_files:
        return
    async with engine.begin() as conn:
        for path in sql_files:
            await conn.execute(text(path.read_text()))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _run_sql_migrations()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Secret House API",
    description="REST API for the Secret House web booking form",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(bookings.router, prefix="/api/bookings", tags=["bookings"])
app.include_router(promocodes.router, prefix="/api/promocodes", tags=["promocodes"])
app.include_router(gifts.router, prefix="/api/gifts", tags=["gifts"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}
