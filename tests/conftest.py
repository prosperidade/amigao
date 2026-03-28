import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, MetaData, Table, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import websockets
from app.main import app
from app.api.deps import get_db
from app.models.base import Base
from app import models as model_registry  # noqa: F401

# Setup an in-memory SQLite database for testing, or use a test postgres db
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session")
def db_engine():
    stub_metadata = MetaData()
    Table("properties", stub_metadata, Column("id", Integer, primary_key=True))
    stub_metadata.create_all(bind=engine)

    tables = [table for table in Base.metadata.sorted_tables if table.name != "properties"]
    Base.metadata.create_all(bind=engine, tables=tables)
    yield engine
    Base.metadata.drop_all(bind=engine, tables=list(reversed(tables)))
    stub_metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session):
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
