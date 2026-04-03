"""
Shared test fixtures — PostgreSQL via Testcontainers.

A real PostgreSQL container is spun up once per session.  Each test function
runs inside a transaction that is rolled back at the end, ensuring full
isolation without the overhead of recreating the database.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from testcontainers.postgres import PostgresContainer

from app import models as model_registry  # noqa: F401  — registers all models
from app.api import websockets
from app.api.deps import get_db
from app.main import app
from app.models.base import Base


@pytest.fixture(scope="session")
def _pg_container():
    """Start a PostgreSQL container once for the entire test session."""
    with PostgresContainer("postgis/postgis:15-3.3", driver="psycopg2") as pg:
        yield pg


@pytest.fixture(scope="session")
def db_engine(_pg_container):
    """Create engine + schema on the session-scoped Postgres container."""
    url = _pg_container.get_connection_url()
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))

    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Function-scoped session wrapped in a transaction that rolls back."""
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient wired to the transactional db_session."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    async def fake_connect_redis():
        return None

    original_connect_redis = websockets.manager.connect_redis
    app.dependency_overrides[get_db] = override_get_db
    websockets.manager.connect_redis = fake_connect_redis

    with TestClient(app) as c:
        yield c

    websockets.manager.connect_redis = original_connect_redis
    app.dependency_overrides.clear()
