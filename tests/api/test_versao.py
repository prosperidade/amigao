"""Identificação da versão em execução — /health e /api/v1/versao.

Prova colhida em tela (rodapé da conferência) só vale se disser de qual commit
e de qual ambiente veio.
"""

from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.main import app

cliente = TestClient(app)


def test_versao_expoe_commit_e_ambiente(monkeypatch):
    monkeypatch.setattr(settings, "GIT_COMMIT", "3c0e3697abcdef")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    r = cliente.get(f"{settings.API_V1_STR}/versao")
    assert r.status_code == 200
    assert r.json() == {"commit": "3c0e3697abcdef", "ambiente": "production"}


def test_versao_sem_commit_diz_null_nunca_inventa(monkeypatch):
    monkeypatch.setattr(settings, "GIT_COMMIT", "")
    r = cliente.get(f"{settings.API_V1_STR}/versao")
    assert r.json()["commit"] is None


def test_versao_nao_exige_sessao():
    # Sem Authorization: o rodapé tem de aparecer mesmo com o token expirado.
    assert cliente.get(f"{settings.API_V1_STR}/versao").status_code == 200


def test_health_carrega_a_mesma_identificacao(monkeypatch):
    monkeypatch.setattr(settings, "GIT_COMMIT", "abc123")
    corpo = cliente.get("/health").json()
    assert corpo["status"] == "ok"
    assert corpo["commit"] == "abc123"
    assert corpo["ambiente"] == settings.ENVIRONMENT


def test_commit_vem_do_render_git_commit(monkeypatch):
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "feedbeef")
    assert Settings().GIT_COMMIT == "feedbeef"
