import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.middleware import RequestContextMiddleware
from app.api.v1 import (
    ai,
    auth,
    checklists,
    clients,
    contracts,
    dashboard,
    documents,
    dossier,
    intake,
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

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    lifespan=lifespan,
)

# Middlewares (ordem importa: Context antes de CORS)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
app.include_router(proposals.router, prefix=f"{settings.API_V1_STR}/proposals", tags=["Propostas Comerciais"])
app.include_router(contracts.router, prefix=f"{settings.API_V1_STR}/contracts", tags=["Contratos"])
app.include_router(ai.router, prefix=f"{settings.API_V1_STR}", tags=["IA"])
app.include_router(dashboard.router, prefix=f"{settings.API_V1_STR}/dashboard", tags=["Dashboard"])
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
