"""
Database connection and session management for PenangLens.
Uses SQLAlchemy async with asyncpg driver for PostgreSQL.
Falls back to SQLite for local development if DATABASE_URL is not set.
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Connection URL
# ---------------------------------------------------------------------------
# Priority: DATABASE_URL env var → fallback to local SQLite
_raw_url = os.getenv("DATABASE_URL", "")

if _raw_url:
    # Azure PostgreSQL: convert postgres:// → postgresql+asyncpg://
    if _raw_url.startswith("postgres://"):
        DATABASE_URL = _raw_url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif _raw_url.startswith("postgresql://"):
        DATABASE_URL = _raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    else:
        DATABASE_URL = _raw_url
else:
    # Fallback: local SQLite (great for development without Azure)
    DATABASE_URL = "sqlite+aiosqlite:///./penanglens.db"

print(f"📦 Database: {'PostgreSQL (Azure)' if 'asyncpg' in DATABASE_URL else 'SQLite (local)'}")

# ---------------------------------------------------------------------------
# Engine & Session Factory
# ---------------------------------------------------------------------------
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    **({"pool_size": 5, "max_overflow": 10} if "asyncpg" in DATABASE_URL else {}),
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# ---------------------------------------------------------------------------
# Base Model
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Dependency for FastAPI endpoints
# ---------------------------------------------------------------------------
async def get_db() -> AsyncSession:
    """Yield a database session, auto-close after request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Init: Create all tables on startup
# ---------------------------------------------------------------------------
async def init_db():
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        from src.db_models import User, Itinerary, ScanHistory  # noqa
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables ready.")
