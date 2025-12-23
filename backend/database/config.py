from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base

from backend.config.settings import settings

# Base class for all ORM models
Base = declarative_base()

# Async SQLAlchemy engine with production-safe pooling
engine = create_async_engine(
    settings.async_database_url,
    echo=False,              # NEVER enable in production
    pool_size=10,            # base connection pool size
    max_overflow=20,         # extra connections under load
    pool_timeout=30,         # seconds to wait for a connection
    pool_recycle=1800,       # recycle connections every 30 min
    pool_pre_ping=True,      # validate connections before use
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Dependency for FastAPI routes
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
