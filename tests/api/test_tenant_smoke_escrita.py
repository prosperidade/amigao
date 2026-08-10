"""Teste de fumaça cross-tenant na ESCRITA — o gate anti-regressão da Frente 1.

A ADR-001 prometeu, em 2026-03-26, "lint automático que detecte query sem filtro"
e marcou o item como ❌ Pendente na própria tabela de status. Ficou pendente por
quatro meses e meio, e nesse intervalo nasceram os achados D1-D3/D7 da triagem
(PR #146): seis endpoints de escrita aceitando FK de outro tenant, e um deles
(`POST /contracts/{id}/assinar`) **gravando** `closed_at` em processo alheio.

Este arquivo é a dívida quitada — não como lint estático, e sim como fumaça
sobre o caminho real. A escolha está justificada em `MULTITENANT_LGPD.md`
(Camada 3): uma regra de `ruff` que procurasse `query()` sem filtro de tenant
teria falso positivo demais (busca global legítima no corpus legislativo,
agregação já escopada uma camada acima) e nenhum poder sobre o caso que
importa — a FK que **chega no corpo** e nunca é olhada.

**Sem este arquivo o conserto apodrece.** Cada endpoint novo que aceitar FK no
payload e esquecer a guarda cai aqui, e não em produção.

Contrato exercitado, para cada endpoint de escrita que aceita FK no corpo:

    tenant A autenticado + FK pertencente ao tenant B  →  404
    tenant A autenticado + FK pertencente ao tenant A  →  2xx  (não-regressão)

**404, nunca 403.** Um 403 confirmaria a existência da entidade e faria do
endpoint um oráculo de enumeração. Ver o bloco de decisão em
`app/services/tenant_guard.py`.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.contract import Contract, ContractStatus
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.proposal import Proposal
from app.models.tenant import Tenant
from app.models.user import User
from app.services.storage import StorageKeyInvalida, validar_storage_key


class _Mundo:
    """Um tenant completo: cliente, imóvel, processo, proposta — e o token dele."""

    def __init__(self, db_session, suffix: str) -> None:
        tenant = Tenant(name=f"Tenant {suffix}")
        db_session.add(tenant)
        db_session.flush()

        user = User(
            email=f"smoke-{suffix}@example.com",
            full_name=f"User {suffix}",
            hashed_password=get_password_hash("senha123"),
            tenant_id=tenant.id,
            is_active=True,
            is_superuser=False,
        )
        db_session.add(user)
        db_session.flush()

        cliente = Client(
            tenant_id=tenant.id,
            full_name=f"Cliente {suffix}",
            email=f"cliente-smoke-{suffix}@example.com",
            client_type=ClientType.pf,
            status=ClientStatus.active,
        )
        db_session.add(cliente)
        db_session.flush()

        imovel = Property(
            tenant_id=tenant.id,
            client_id=cliente.id,
            name=f"Fazenda {suffix}",
        )
        db_session.add(imovel)
        db_session.flush()

        processo = Process(
            tenant_id=tenant.id,
            client_id=cliente.id,
            property_id=imovel.id,
            title=f"Processo {suffix}",
            process_type="licenciamento",
            status=ProcessStatus.triagem,
        )
        db_session.add(processo)
        db_session.flush()

        proposta = Proposal(
            tenant_id=tenant.id,
            client_id=cliente.id,
            process_id=processo.id,
            title=f"Proposta {suffix}",
            created_by_user_id=user.id,
        )
        db_session.add(proposta)
        db_session.flush()

        self.tenant = tenant
        self.user = user
        self.cliente = cliente
        self.imovel = imovel
        self.processo = processo
        self.proposta = proposta
        self.headers = {
            "Authorization": "Bearer "
            + create_access_token(
                subject=user.id,
                tenant_id=tenant.id,
                expires_delta=timedelta(minutes=30),
            )
        }


@pytest.fixture()
def mundos(db_session):
    """Dois tenants completos e independentes: A (quem chama) e B (o alvo)."""
    a = _Mundo(db_session, "SmokeA")
    b = _Mundo(db_session, "SmokeB")
    db_session.commit()
    return a, b


# ---------------------------------------------------------------------------
# Criação com FK do outro tenant → 404
# ---------------------------------------------------------------------------

def test_processo_com_cliente_de_outro_tenant_404(client: TestClient, mundos):
    a, b = mundos
    r = client.post(
        "/api/v1/processes/",
        headers=a.headers,
        json={
            "title": "Processo com cliente alheio",
            "client_id": b.cliente.id,
            "process_type": "licenciamento",
            "status": "triagem",
        },
    )
    assert r.status_code == 404, r.text


def test_processo_com_imovel_de_outro_tenant_404(client: TestClient, mundos):
    a, b = mundos
    r = client.post(
        "/api/v1/processes/",
        headers=a.headers,
        json={
            "title": "Processo com imóvel alheio",
            "client_id": a.cliente.id,
            "property_id": b.imovel.id,
            "process_type": "licenciamento",
            "status": "triagem",
        },
    )
    assert r.status_code == 404, r.text


def test_processo_com_responsavel_de_outro_tenant_404(client: TestClient, mundos):
    a, b = mundos
    r = client.post(
        "/api/v1/processes/",
        headers=a.headers,
        json={
            "title": "Processo com responsável alheio",
            "client_id": a.cliente.id,
            "responsible_user_id": b.user.id,
            "process_type": "licenciamento",
            "status": "triagem",
        },
    )
    assert r.status_code == 404, r.text


def test_imovel_com_cliente_de_outro_tenant_404(client: TestClient, mundos):
    a, b = mundos
    r = client.post(
        "/api/v1/properties/",
        headers=a.headers,
        json={"client_id": b.cliente.id, "name": "Fazenda alheia"},
    )
    assert r.status_code == 404, r.text


def test_tarefa_com_processo_de_outro_tenant_404(client: TestClient, mundos):
    a, b = mundos
    r = client.post(
        "/api/v1/tasks/",
        headers=a.headers,
        json={"title": "Tarefa em caso alheio", "process_id": b.processo.id},
    )
    assert r.status_code == 404, r.text


def test_patch_tarefa_nao_reaponta_para_processo_de_outro_tenant(
    client: TestClient, mundos
):
    """PATCH também é escrita.

    `TaskUpdate` carrega `process_id`, `property_id`, `document_id` e
    `assigned_to_user_id`. Criar a tarefa limpa e depois repontá-la por PATCH
    seria o mesmo furo da criação, por outra porta.
    """
    a, b = mundos
    criada = client.post(
        "/api/v1/tasks/",
        headers=a.headers,
        json={"title": "Tarefa legítima", "process_id": a.processo.id},
    )
    assert criada.status_code == 200, criada.text

    r = client.patch(
        f"/api/v1/tasks/{criada.json()['id']}",
        headers=a.headers,
        json={"process_id": b.processo.id},
    )
    assert r.status_code == 404, r.text


def test_proposta_com_processo_de_outro_tenant_404(client: TestClient, mundos):
    a, b = mundos
    r = client.post(
        "/api/v1/proposals/",
        headers=a.headers,
        json={
            "client_id": a.cliente.id,
            "process_id": b.processo.id,
            "title": "Proposta em caso alheio",
        },
    )
    assert r.status_code == 404, r.text


def test_contrato_com_processo_de_outro_tenant_404(client: TestClient, mundos):
    a, b = mundos
    r = client.post(
        "/api/v1/contracts/",
        headers=a.headers,
        json={
            "client_id": a.cliente.id,
            "process_id": b.processo.id,
            "title": "Contrato em caso alheio",
        },
    )
    assert r.status_code == 404, r.text


def test_contrato_com_template_privado_de_outro_tenant_404(
    client: TestClient, db_session, mundos
):
    """Tenancy dual não é passe livre.

    `ContractTemplate.tenant_id` é nullable — `None` significa "template global
    do produto". Isso NÃO torna qualquer template aceitável: o template privado
    do vizinho viraria o texto de uma peça assinada. Global passa; do outro
    tenant, 404.
    """
    from app.models.contract_template import ContractTemplate

    template_de_b = ContractTemplate(
        tenant_id=b_tenant_id(mundos),
        name="Modelo privado de B",
        content_template="Contrato de {{cliente.nome}}",
        is_active=True,
    )
    db_session.add(template_de_b)
    db_session.commit()

    a, _ = mundos
    r = client.post(
        "/api/v1/contracts/",
        headers=a.headers,
        json={
            "client_id": a.cliente.id,
            "template_id": template_de_b.id,
            "title": "Contrato com modelo alheio",
        },
    )
    assert r.status_code == 404, r.text


def b_tenant_id(mundos) -> int:
    return mundos[1].tenant.id


def test_conversa_com_cliente_de_outro_tenant_404(client: TestClient, mundos):
    a, b = mundos
    r = client.post(
        "/api/v1/threads/",
        headers=a.headers,
        json={"title": "Conversa alheia", "channel": "email", "client_id": b.cliente.id},
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# Enqueue assíncrono com id do outro tenant → 404 (barreira antes da fila)
# ---------------------------------------------------------------------------

def test_agente_async_com_processo_de_outro_tenant_404(client: TestClient, mundos):
    a, b = mundos
    r = client.post(
        "/api/v1/agents/run-async",
        headers=a.headers,
        json={"agent_name": "vigia", "process_id": b.processo.id, "metadata": {}},
    )
    assert r.status_code == 404, r.text


def test_chain_async_com_processo_de_outro_tenant_404(client: TestClient, mundos):
    a, b = mundos
    r = client.post(
        "/api/v1/agents/chain-async",
        headers=a.headers,
        json={
            "chain_name": "diagnostico_completo",
            "process_id": b.processo.id,
            "metadata": {},
        },
    )
    assert r.status_code == 404, r.text


# ---------------------------------------------------------------------------
# D2 — o achado mais grave: assinatura que ESCREVE em processo alheio
# ---------------------------------------------------------------------------

def test_assinar_contrato_nao_fecha_processo_de_outro_tenant(
    client: TestClient, db_session, mundos
):
    """Contrato do tenant A apontando para processo de B: 404, e o `closed_at`
    de B permanece intocado.

    Este é o cenário que a triagem classificou como escrita cross-tenant (D2,
    `contracts.py:507`). A relação torta é criada **direto no banco**, de
    propósito: representa um contrato gravado ANTES desta frente, quando o
    `POST /contracts` ainda aceitava `process_id` alheio. O conserto tem de
    proteger o dado legado, não só barrar a entrada nova.
    """
    a, b = mundos

    contrato = Contract(
        tenant_id=a.tenant.id,
        client_id=a.cliente.id,
        process_id=b.processo.id,   # relação torta herdada
        title="Contrato com processo alheio",
        status=ContractStatus.sent,
        created_by_user_id=a.user.id,
    )
    db_session.add(contrato)
    db_session.commit()

    antes = db_session.query(Process).filter(Process.id == b.processo.id).one()
    assert antes.closed_at is None

    r = client.post(
        f"/api/v1/contracts/{contrato.id}/assinar",
        headers=a.headers,
        data={"signed_at": "2026-08-10"},
    )
    assert r.status_code == 404, r.text

    db_session.expire_all()
    depois = db_session.query(Process).filter(Process.id == b.processo.id).one()
    assert depois.closed_at is None, "closed_at do processo de outro tenant foi tocado"


# ---------------------------------------------------------------------------
# D3 — storage_key forjada
# ---------------------------------------------------------------------------

def test_confirm_upload_com_storage_key_de_outro_tenant_400(client: TestClient, mundos):
    a, b = mundos
    chave_de_b = f"tenant_{b.tenant.id}/process_{b.processo.id}/{'0' * 8}-0000-0000-0000-000000000000.pdf"
    r = client.post(
        "/api/v1/documents/confirm-upload",
        headers=a.headers,
        json={
            "process_id": a.processo.id,
            "storage_key": chave_de_b,
            "filename": "roubado.pdf",
            "content_type": "application/pdf",
            "file_size_bytes": 1024,
        },
    )
    assert r.status_code == 400, r.text


def test_confirm_upload_com_storage_key_de_outro_processo_400(client: TestClient, mundos):
    """Mesmo tenant, processo errado: a chave carrega o processo e ele é conferido."""
    a, _ = mundos
    outro = f"tenant_{a.tenant.id}/process_{a.processo.id + 999}/{'0' * 8}-0000-0000-0000-000000000000.pdf"
    r = client.post(
        "/api/v1/documents/confirm-upload",
        headers=a.headers,
        json={
            "process_id": a.processo.id,
            "storage_key": outro,
            "filename": "trocado.pdf",
            "content_type": "application/pdf",
            "file_size_bytes": 1024,
        },
    )
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# Formato da storage_key — unitário, sem banco
# ---------------------------------------------------------------------------

class TestFormatoStorageKey:
    """Formas que a chave pode assumir, e as que precisam ser recusadas.

    O caso `tenant_55` merece nota: uma checagem ingênua por
    `chave.startswith(f"tenant_{tenant_id}/")` já o pegaria, mas
    `startswith("tenant_5")` sem a barra aceitaria a chave do tenant 55 como
    sendo do tenant 5. O regex é ancorado nas duas pontas justamente por isso.
    """

    UUID = "f37cd83d-7871-41ae-932a-f8d7e144c944"

    @pytest.mark.parametrize("sufixo", ["", ".pdf", ".GEOJSON", ".m4a"])
    def test_aceita_chave_propria(self, sufixo):
        chave = f"tenant_5/process_9/{self.UUID}{sufixo}"
        assert validar_storage_key(chave, tenant_id=5, process_id=9) == chave

    @pytest.mark.parametrize(
        "chave",
        [
            "tenant_7/process_9/{u}.pdf",                       # outro tenant
            "tenant_55/process_9/{u}.pdf",                      # prefixo parecido
            "tenant_5/process_4/{u}.pdf",                       # outro processo
            "tenant_5/draft_9/{u}.pdf",                         # escopo trocado
            "tenant_5/process_9/../../tenant_7/process_1/{u}",  # traversal
            "tenant_5/process_9/{u}.pdf/extra",                 # segmento extra
            "../tenant_5/process_9/{u}.pdf",                    # prefixo antes
            "",                                                 # vazia
        ],
    )
    def test_recusa(self, chave):
        with pytest.raises(StorageKeyInvalida):
            validar_storage_key(
                chave.format(u=self.UUID), tenant_id=5, process_id=9
            )

    def test_draft_exige_escopo_draft(self):
        assert validar_storage_key(
            f"tenant_5/draft_9/{self.UUID}.pdf", tenant_id=5, draft_id=9
        )
        with pytest.raises(StorageKeyInvalida):
            validar_storage_key(
                f"tenant_5/process_9/{self.UUID}.pdf", tenant_id=5, draft_id=9
            )


# ---------------------------------------------------------------------------
# NÃO-REGRESSÃO — o caminho feliz do próprio tenant continua passando
# ---------------------------------------------------------------------------

def test_caminho_feliz_processo_do_proprio_tenant(client: TestClient, mundos):
    a, _ = mundos
    r = client.post(
        "/api/v1/processes/",
        headers=a.headers,
        json={
            "title": "Processo legítimo",
            "client_id": a.cliente.id,
            "property_id": a.imovel.id,
            "responsible_user_id": a.user.id,
            "process_type": "licenciamento",
            "status": "triagem",
        },
    )
    assert r.status_code == 201, r.text


def test_caminho_feliz_imovel_do_proprio_tenant(client: TestClient, mundos):
    a, _ = mundos
    r = client.post(
        "/api/v1/properties/",
        headers=a.headers,
        json={"client_id": a.cliente.id, "name": "Fazenda legítima"},
    )
    assert r.status_code == 200, r.text


def test_caminho_feliz_tarefa_do_proprio_tenant(client: TestClient, mundos):
    a, _ = mundos
    r = client.post(
        "/api/v1/tasks/",
        headers=a.headers,
        json={"title": "Tarefa legítima", "process_id": a.processo.id},
    )
    assert r.status_code == 200, r.text


def test_caminho_feliz_proposta_do_proprio_tenant(client: TestClient, mundos):
    a, _ = mundos
    r = client.post(
        "/api/v1/proposals/",
        headers=a.headers,
        json={
            "client_id": a.cliente.id,
            "process_id": a.processo.id,
            "title": "Proposta legítima",
        },
    )
    assert r.status_code == 201, r.text


def test_caminho_feliz_contrato_do_proprio_tenant(client: TestClient, mundos):
    a, _ = mundos
    r = client.post(
        "/api/v1/contracts/",
        headers=a.headers,
        json={
            "client_id": a.cliente.id,
            "process_id": a.processo.id,
            "proposal_id": a.proposta.id,
            "title": "Contrato legítimo",
        },
    )
    assert r.status_code == 201, r.text


def test_caminho_feliz_conversa_do_proprio_tenant(client: TestClient, mundos):
    a, _ = mundos
    r = client.post(
        "/api/v1/threads/",
        headers=a.headers,
        json={"title": "Conversa legítima", "channel": "email", "client_id": a.cliente.id},
    )
    assert r.status_code == 200, r.text
