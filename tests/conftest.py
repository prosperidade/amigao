"""
Shared test fixtures — PostgreSQL via Testcontainers.

A real PostgreSQL container is spun up once per session.  Each test function
runs inside a transaction that is rolled back at the end, ensuring full
isolation without the overhead of recreating the database.
"""

import os
import sys

# Windows + Docker Desktop: o SDK Python (docker 7.x) usado pelo Testcontainers
# não respeita o `docker context` ativo — cai no pipe default `npipe:////./pipe/docker_engine`.
# Sem essa variável, em Windows o SDK tenta `dockerDesktopLinuxEngine` que retorna 500
# por mismatch de API version com Docker Desktop 4.46. Setar antes de qualquer import
# que carregue `docker` ou `testcontainers`.
if sys.platform == "win32":
    os.environ.setdefault("DOCKER_HOST", "npipe:////./pipe/docker_engine")

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
    """Start a PostgreSQL container once for the entire test session.

    Usamos a imagem customizada do projeto (`amigao_do_meio_ambiente-db`)
    construída via `docker/db/Dockerfile`, que parte de postgis/postgis:15-3.3
    e adiciona o `postgresql-15-pgvector`. É a mesma imagem que roda em dev
    via docker-compose.

    Build local exigido: `docker compose build db` (ou um `docker compose up
    -d --build db` qualquer no histórico do projeto). Em CI: passo dedicado
    de build da imagem antes do pytest.

    Fallback: se a imagem customizada não estiver presente, cai pra
    `pgvector/pgvector:pg15` (oficial do pgvector). Ela tem pgvector mas
    NÃO tem postgis — alguns testes que dependem de postgis vão falhar.
    """
    import docker as _docker_sdk  # noqa: PLC0415

    image = "amigao_do_meio_ambiente-db:latest"
    try:
        _docker_sdk.from_env().images.get(image)
    except Exception:
        image = "pgvector/pgvector:pg15"

    with PostgresContainer(image, driver="psycopg2") as pg:
        yield pg


@pytest.fixture(scope="session")
def db_engine(_pg_container):
    """Create engine + schema on the session-scoped Postgres container.

    Habilita extensões postgis e pgvector antes do create_all. Tabela
    knowledge_catalog tem coluna `embedding vector(768)` que requer pgvector.
    """
    url = _pg_container.get_connection_url()
    engine = create_engine(url, pool_pre_ping=True)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

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


@pytest.fixture(autouse=True)
def _reset_slowapi_limiter():
    """Reseta o storage in-memory do slowapi antes de cada teste.

    slowapi.Limiter() sem storage_uri usa MemoryStorage (in-process), que
    acumula contadores ao longo da suite e provoca 429 em testes que de
    outra forma passariam (state-leakage entre testes). Reset no setup
    deixa cada teste começar do zero — testes que precisam estourar o
    limite (ex.: `test_signup_rate_limit_blocks_after_10`) continuam
    funcionando, pois fazem todas as chamadas dentro do mesmo teste.
    """
    from app.core.rate_limit import limiter
    try:
        limiter.reset()
    except Exception:  # noqa: BLE001 — alguns backends não expõem reset
        pass
    yield
