"""A cadeia OCR → extrator entrega o caso, e falha de agente não some.

Medido em produção em 22/09/2026 (casos #23 e #25): dez OCRs gravados e ZERO
extrações. Três buracos em fila, cada um mudo:
  1. `_dispatch_extrator` mandava `process_id=None`; `authorize` respondia 404;
  2. o 404 virava `{"status": "failed"}` sem log — nada em lugar nenhum;
  3. a imagem de produção não carregava a ontologia, então o manifesto do
     extrator saía `capacidade_insuficiente` antes de ler qualquer documento.
"""

import logging
import re
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

import pytest
from fastapi import HTTPException

from app.services.agent_capabilities import capability_manifest
from app.workers import agent_tasks, ocr_tasks

RAIZ = Path(__file__).resolve().parents[1]


class FakeRunAgent:
    def __init__(self):
        self.chamadas = []

    def delay(self, **kw):
        self.chamadas.append(kw)
        return type("T", (), {"id": "task-1"})()


class FakeDoc:
    def __init__(self, process_id):
        self.id = 546
        self.process_id = process_id
        self.storage_key = "k"
        self.document_type = "matricula"


class FakeRequest:
    id = "req-1"


class FakeTask:
    request = FakeRequest()

    def retry(self, **kw):  # pragma: no cover - só o caminho 409 usaria
        raise AssertionError("retry inesperado")


def test_extrator_recebe_o_caso_do_documento():
    run_agent = FakeRunAgent()
    ocr_tasks._dispatch_extrator(run_agent, FakeDoc(23), None, 1, 1)
    assert run_agent.chamadas == [{
        "agent_name": "extrator", "tenant_id": 1, "user_id": 1, "process_id": 23,
        "metadata": {"document_id": 546, "storage_key": "k",
                     "document_type": "matricula", "intake_draft_id": None},
    }]


def test_documento_sem_caso_nao_enfileira_e_diz_por_que(caplog):
    run_agent = FakeRunAgent()
    with caplog.at_level(logging.WARNING):
        ocr_tasks._dispatch_extrator(run_agent, FakeDoc(None), 7, 1, 1)
    assert run_agent.chamadas == []
    assert "sem caso" in caplog.text


def test_falha_de_agente_em_fila_vai_para_o_log(monkeypatch, caplog):
    def recusa(*a, **k):
        raise HTTPException(404, "Caso não encontrado")

    monkeypatch.setattr("app.services.connected_agents.start_execution", recusa)
    with caplog.at_level(logging.ERROR):
        r = agent_tasks._connected_task(FakeTask(), 1, 1, process_id=None, name="extrator")
    assert r == {"status": "failed", "error": "Caso não encontrado"}
    assert "extrator" in caplog.text and "Caso não encontrado" in caplog.text
    assert any(rec.levelno >= logging.ERROR for rec in caplog.records)


def _ignorado_no_build(caminho: str) -> bool:
    """Simula o .dockerignore: última regra que casa decide (como no Docker)."""
    regras = [linha.strip() for linha in (RAIZ / ".dockerignore").read_text(encoding="utf-8").splitlines()
              if linha.strip() and not linha.lstrip().startswith("#")]
    partes = PurePosixPath(caminho).parts
    prefixos = ["/".join(partes[:i]) for i in range(1, len(partes) + 1)]
    decisao = False
    for regra in regras:
        negada = regra.startswith("!")
        padrao = regra[1:] if negada else regra
        if any(fnmatch(prefixo, padrao) for prefixo in prefixos):
            decisao = not negada
    return decisao


def test_imagem_de_producao_carrega_o_que_o_manifesto_exige():
    """Todo arquivo fora de `app/` que o manifesto exige tem de CHEGAR na imagem.

    Duas metades, e a segunda foi a que faltou em 22/09: o `Dockerfile` copiava
    a ontologia, mas o `.dockerignore` excluía `docs` inteiro, então não havia o
    que copiar e o extrator seguiu em "capacidade_insuficiente" em produção.
    Conferir só o COPY dava verde com a imagem errada (dívida #268).
    """
    manifesto = capability_manifest("extrator", {})
    assert manifesto["status"] == "available", manifesto["missing"]

    exigidos = ["docs/arquitetura/ONTOLOGIA_REGENTE_v1.md"]
    dockerfile = (RAIZ / "Dockerfile").read_text(encoding="utf-8")
    copiados = re.findall(r"^COPY\s+(\S+)", dockerfile, re.MULTILINE)
    for alvo in exigidos:
        assert alvo in copiados, f"{alvo} não é copiado pelo Dockerfile"
        assert not _ignorado_no_build(alvo), f"{alvo} é excluído pelo .dockerignore"


@pytest.mark.parametrize("familia", ["registral", "cadastral", "pessoal",
                                     "geoespacial", "contratual", "cartorario"])
def test_manifesto_aplica_a_skill_de_cada_familia(familia):
    aplicadas = {a["name"] for a in capability_manifest("extrator", {})["applied"]}
    assert f"extrator/{familia}" in aplicadas
