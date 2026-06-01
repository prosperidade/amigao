"""Regressão (2026-06-01) — respostas 500 carregam cabeçalhos CORS.

Sem o handler global de exceções, um 500 propaga até o ServerErrorMiddleware
(acima do CORSMiddleware) e a resposta sai SEM `Access-Control-Allow-Origin`.
O navegador então reporta "bloqueado por CORS", mascarando o erro real (foi o
caso do `/threads` em produção). Este teste prova que o 500 volta COM os
cabeçalhos CORS e o corpo/erro reais — desmascarando o erro.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import _unhandled_exception_handler


def _app_with_handler() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_exception_handler(Exception, _unhandled_exception_handler)

    @app.get("/boom")
    def boom():  # noqa: ANN202
        raise RuntimeError("falha não tratada de propósito")

    return app


def test_unhandled_500_carries_cors_headers():
    origins = settings.cors_origins_list
    origin = "*" if "*" in origins else (origins[0] if origins else "http://localhost:3000")

    client = TestClient(_app_with_handler(), raise_server_exceptions=False)
    r = client.get("/boom", headers={"Origin": origin})

    assert r.status_code == 500
    # O cabeçalho CORS DEVE estar presente para o navegador não mascarar como CORS.
    assert r.headers.get("access-control-allow-origin"), (
        "resposta 500 sem Access-Control-Allow-Origin — o browser mascararia como erro de CORS"
    )
    # E o corpo traz o erro real + request_id para rastrear no log.
    body = r.json()
    assert body["detail"] == "Internal Server Error"
    assert "request_id" in body


def test_normal_request_still_has_cors():
    """Sanidade: requisição OK continua com CORS normal (não regredimos o caminho feliz)."""
    origins = settings.cors_origins_list
    origin = "*" if "*" in origins else (origins[0] if origins else "http://localhost:3000")

    app = _app_with_handler()

    @app.get("/ok")
    def ok():  # noqa: ANN202
        return {"status": "ok"}

    client = TestClient(app)
    r = client.get("/ok", headers={"Origin": origin})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin")
