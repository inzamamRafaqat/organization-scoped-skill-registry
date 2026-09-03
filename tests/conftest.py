"""Pytest configuration, database fixtures, and test HTTP client."""
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from sqlalchemy import event

# Set test environment
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["ENVIRONMENT"] = "testing"

from app.db.base import Base
from app.api.deps import get_db
from app.db.seed import seed_fixtures
from app.main import app

# In-memory test engine with foreign keys enabled
test_engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a clean database schema and session for every individual test."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        await seed_fixtures(session)
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Test async HTTP client with database dependency overridden to test session."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


# Fixture headers for ABC Construction (org_abc)
@pytest.fixture
def abc_owner_headers():
    return {
        "X-Organization-Id": "org_abc",
        "X-User-Id": "alice_owner",
        "X-User-Role": "owner",
    }


@pytest.fixture
def abc_member_headers():
    return {
        "X-Organization-Id": "org_abc",
        "X-User-Id": "bob_member",
        "X-User-Role": "member",
    }


# Fixture headers for XYZ Builders (org_xyz)
@pytest.fixture
def xyz_owner_headers():
    return {
        "X-Organization-Id": "org_xyz",
        "X-User-Id": "carol_owner",
        "X-User-Role": "owner",
    }


@pytest.fixture
def xyz_member_headers():
    return {
        "X-Organization-Id": "org_xyz",
        "X-User-Id": "dan_member",
        "X-User-Role": "member",
    }
