from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1 import auth, clients, processes, documents, properties, tasks, threads
from app.api.websockets import router as websocket_router
from app.api.middleware import RequestContextMiddleware

# Inicializar logging estruturado ao subir a aplicação
setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
)

# Middlewares (ordem importa: Context antes de CORS)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://172.31.32.1:3000", "http://127.0.0.1:3000"],
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
    return {"status": "ok", "version": settings.VERSION}
