from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.metrics import metrics_response
from app.api.v1 import auth, clients, processes, documents, properties, tasks, threads
from app.api.websockets import manager as websocket_manager
from app.api.websockets import router as websocket_router
from app.api.middleware import RequestContextMiddleware

@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await websocket_manager.connect_redis()
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning("Redis indisponível no startup do WebSocket: %s", exc)
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
