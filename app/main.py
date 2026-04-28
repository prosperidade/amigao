import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.api.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from app.api.v1 import (
    agents,
    ai,
    auth,
    checklists,
    clients,
    contracts,
    dashboard,
    decisions,
    documents,
    dossier,
    intake,
    knowledge,
    legislation,
    legislation_alerts,
    processes,
    properties,
    proposals,
    tasks,
    threads,
    workflows,
)
from app.api.websockets import manager as websocket_manager
from app.api.websockets import router as websocket_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.metrics import metrics_response
from app.core.rate_limit import limiter
from app.core.security import warm_up_security
from app.db.session import SessionLocal
from app.services.storage import get_storage_service

logger = logging.getLogger(__name__)


def _warm_up_runtime_dependencies() -> None:
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Banco indisponível durante warm-up: %s", exc)

    try:
        warm_up_security()
    except Exception as exc:
        logger.warning("Falha no warm-up de segurança: %s", exc)

    try:
        get_storage_service()
    except Exception as exc:
        logger.warning("Falha no warm-up do storage: %s", exc)

    _check_ai_provider_contracts()


def _check_ai_provider_contracts() -> None:
    """Valida contratos de providers de IA declarados em settings.

    Sprint -1 Tarefa A: Sprint O definiu Gemini como default do agente legislacao.
    Se a flag está ligada mas GEMINI_API_KEY não existe, o fallback cai para OpenAI
    silenciosamente (bug detectado na auditoria 2026-04-23).
    """
    if settings.LEGISLATION_USE_GEMINI_DEFAULT and not settings.GEMINI_API_KEY.strip():
        logger.warning(
            "[startup] Sprint O contract violated: LEGISLATION_USE_GEMINI_DEFAULT=True "
            "but GEMINI_API_KEY is empty. Legislation agent will fall back to OpenAI."
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    _warm_up_runtime_dependencies()
    try:
        await websocket_manager.connect_redis()
    except Exception as exc:
        logger.warning("Redis indisponível no startup do WebSocket: %s", exc)
    try:
        yield
    finally:
        await websocket_manager.close_redis()

# Inicializar logging estruturado ao subir a aplicação
setup_logging()

_is_dev = settings.ENVIRONMENT == "development"

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if _is_dev else None,
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Middlewares (ordem importa: Security → Context → CORS)
# Starlette executa na ordem inversa do registro: CORS → Context → Security
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-Id",
        "X-Auth-Profile",
        "X-Tenant-Id",
        "Accept",
    ],
)

# Rotas
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Autenticação"])
app.include_router(clients.router, prefix=f"{settings.API_V1_STR}/clients", tags=["Clientes"])
app.include_router(processes.router, prefix=f"{settings.API_V1_STR}/processes", tags=["Processos"])
app.include_router(documents.router, prefix=f"{settings.API_V1_STR}/documents", tags=["Documentos"])
app.include_router(properties.router, prefix=f"{settings.API_V1_STR}/properties", tags=["Propriedades Rurais"])
app.include_router(tasks.router, prefix=f"{settings.API_V1_STR}/tasks", tags=["Tarefas e Kanban"])
app.include_router(threads.router, prefix=f"{settings.API_V1_STR}/threads", tags=["Comunicação"])
app.include_router(intake.router, prefix=f"{settings.API_V1_STR}/intake", tags=["Intake / Entrada de Demanda"])
app.include_router(checklists.router, prefix=f"{settings.API_V1_STR}/processes", tags=["Checklists Documentais"])
app.include_router(workflows.router, prefix=f"{settings.API_V1_STR}/workflows", tags=["Trilha Regulatória"])
app.include_router(workflows.process_router, prefix=f"{settings.API_V1_STR}/processes", tags=["Trilha Regulatória"])
app.include_router(dossier.router, prefix=f"{settings.API_V1_STR}/processes", tags=["Dossiê Técnico"])
app.include_router(decisions.router, prefix=f"{settings.API_V1_STR}/processes", tags=["Decisões do Caso"])
app.include_router(proposals.router, prefix=f"{settings.API_V1_STR}/proposals", tags=["Propostas Comerciais"])
app.include_router(contracts.router, prefix=f"{settings.API_V1_STR}/contracts", tags=["Contratos"])
app.include_router(ai.router, prefix=f"{settings.API_V1_STR}", tags=["IA"])
app.include_router(agents.router, prefix=f"{settings.API_V1_STR}/agents", tags=["Agentes IA"])
app.include_router(dashboard.router, prefix=f"{settings.API_V1_STR}/dashboard", tags=["Dashboard"])
app.include_router(legislation.router, prefix=f"{settings.API_V1_STR}/legislation", tags=["Base Legislativa"])
app.include_router(legislation_alerts.router, prefix=f"{settings.API_V1_STR}/legislation", tags=["Alertas Legislativos"])
app.include_router(knowledge.router, prefix=f"{settings.API_V1_STR}/knowledge", tags=["Knowledge Catalog (RAG)"])
app.include_router(websocket_router, tags=["Tempo Real"])


@app.get("/")
def root():
    return {"message": f"Bem-vindo à API do {settings.PROJECT_NAME}"}


@app.get("/health")
def health_check():
    return {"status": "ok", "version": settings.VERSION, "service": settings.SERVICE_NAME}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return metrics_response()
