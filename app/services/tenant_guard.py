"""Guarda de integridade de tenant nas RELAÇÕES recebidas do cliente.

O ADR-001 decidiu isolamento **lógico**: não há RLS, não há FK composta
`(tenant_id, id)`. A única barreira é a aplicação — e ela existia só pela
metade. `BaseRepository` injeta o `tenant_id` da linha que está sendo criada
(`base.py:61`) e filtra a entidade que está sendo buscada
(`BaseRepository.get_or_404`, `base.py:51-56`), mas **nada olhava as FKs que
vêm no payload**: um `POST /processes` com `client_id` de outro tenant gravava
sem reclamar.

Este módulo generaliza um padrão que **já existia no repositório**, aplicado
num lugar só:

    # app/api/v1/credentials.py:78-85 (antes desta frente, o único ponto correto)
    # Tenant isolation: o cliente precisa ser do mesmo tenant.
    client = db.query(ClientModel).filter(
        ClientModel.id == payload.client_id,
        ClientModel.tenant_id == current_user.tenant_id,
    ).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")

Não é padrão novo — é o de `credentials.py` mais o de
`BaseRepository.get_or_404`, extraídos para um ponto único e reusados.

Por que **não** vive no `BaseRepository`: metade dos endpoints que precisam
dele não passa por repositório nenhum. Existem repos para client, document,
matricula, process, property, staging e task; **não existem** para proposal,
contract, credential, thread, acao, rota e regulatory — esses montam o ORM
direto no router. A guarda tem de ser chamável dos dois lados, então é função
livre, sem `Depends` e sem herança.

**404, nunca 403** (decisão do André, 2026-08-10). Um 403 confirma que a
entidade existe e transforma o endpoint num oráculo de enumeração: o atacante
varre ids e aprende o mapa do outro tenant sem ler um byte de dado. "Não
existe para você" é a semântica correta — e é a que `get_or_404` e
`credentials.py` já praticavam.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.acao import Acao
from app.models.base import Base
from app.models.client import Client
from app.models.communication import CommunicationThread
from app.models.contract import Contract
from app.models.document import Document
from app.models.matricula import Matricula
from app.models.process import Process
from app.models.property import Property
from app.models.proposal import Proposal
from app.models.rota import Rota
from app.models.task import Task
from app.models.user import User

ModelT = TypeVar("ModelT", bound=Base)


# Rótulo em português para a mensagem de 404. O texto que o consultor lê nunca
# diz "cross-tenant" nem "id inválido" — do lado dele, aquilo simplesmente não
# existe, que é a verdade do ponto de vista do tenant dele.
_RELACOES: dict[str, tuple[type[Base], str]] = {
    "client_id": (Client, "Cliente"),
    "process_id": (Process, "Caso"),
    "property_id": (Property, "Imóvel"),
    "proposal_id": (Proposal, "Proposta"),
    "contract_id": (Contract, "Contrato"),
    "document_id": (Document, "Documento"),
    "matricula_id": (Matricula, "Matrícula"),
    "rota_id": (Rota, "Rota"),
    "acao_id": (Acao, "Ação"),
    "thread_id": (CommunicationThread, "Conversa"),
    "task_id": (Task, "Tarefa"),
    "responsible_user_id": (User, "Usuário responsável"),
    "assigned_to_user_id": (User, "Usuário responsável"),
    # `created_by_user_id` NÃO entra: é carimbado pelo servidor a partir do
    # usuário autenticado, nunca aceito do payload. Validá-lo seria uma query
    # para confirmar que o próprio requisitante existe no próprio tenant.
}


def exigir_do_tenant(
    db: Session,
    model: type[ModelT],
    entity_id: Optional[int],
    tenant_id: int,
    *,
    rotulo: Optional[str] = None,
) -> Optional[ModelT]:
    """Resolve `entity_id` **dentro do tenant** ou levanta 404.

    `entity_id=None` devolve `None` sem consultar o banco: FK opcional ausente
    é ausência legítima, não violação. Quem exige presença é o schema.

    Devolve a entidade carregada — quem chama costuma precisar dela logo em
    seguida, e devolver evita uma segunda query pelo mesmo id (era assim que
    `contracts.py` acabava com cinco `query(Process).filter(Process.id == …)`
    espalhados pelo arquivo).
    """
    if entity_id is None:
        return None

    obj = (
        db.query(model)
        .filter(model.id == entity_id, model.tenant_id == tenant_id)  # type: ignore[attr-defined]
        .first()
    )
    if obj is None:
        nome = rotulo or getattr(model, "__name__", "Registro")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{nome} não encontrado.",
        )
    return obj


def exigir_do_tenant_ou_global(
    db: Session,
    model: type[ModelT],
    entity_id: Optional[int],
    tenant_id: int,
    *,
    rotulo: Optional[str] = None,
) -> Optional[ModelT]:
    """Variante para entidades de **tenancy dual**: `tenant_id IS NULL` significa
    "compartilhada por todos" e é legítima.

    Só três modelos têm esse desenho hoje, e todos por decisão registrada:
    `ContractTemplate` e `PromptTemplate` (o global é o default do produto; o do
    tenant é o override do white-label) e `knowledge_catalog` (ADR-001, corpus
    legislativo compartilhado).

    O ponto que esta função protege é sutil e escapou da leitura original da
    auditoria: `ContractTemplate.tenant_id` ser nullable NÃO significa que
    qualquer template serve. Um template **privado de outro tenant** continua
    sendo dado alheio — e num contrato ele viraria o texto da peça assinada.
    Global passa; do vizinho, não.
    """
    if entity_id is None:
        return None

    obj = (
        db.query(model)
        .filter(
            model.id == entity_id,  # type: ignore[attr-defined]
            or_(
                model.tenant_id == tenant_id,  # type: ignore[attr-defined]
                model.tenant_id.is_(None),  # type: ignore[attr-defined]
            ),
        )
        .first()
    )
    if obj is None:
        nome = rotulo or getattr(model, "__name__", "Registro")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{nome} não encontrado.",
        )
    return obj


def exigir_relacoes_do_tenant(
    db: Session,
    tenant_id: int,
    dados: dict[str, Any],
    *,
    apenas: Optional[Iterable[str]] = None,
) -> None:
    """Valida **toda** FK conhecida presente em `dados`.

    Uma chamada por endpoint de escrita, logo depois do `model_dump()`:

        exigir_relacoes_do_tenant(db, current_user.tenant_id, process_in.model_dump())

    Percorre `_RELACOES` em vez de exigir que cada endpoint liste seus campos.
    A escolha é deliberada: a classe de bug que esta frente conserta nasceu de
    endpoints que **esqueceram** de validar. Uma guarda que também depende de
    alguém lembrar de listar o campo reintroduz o mesmo modo de falha uma
    camada acima. Campo novo num schema que já esteja no catálogo passa a ser
    validado sem que ninguém encoste aqui.

    `apenas` restringe a checagem a um subconjunto — para quem já resolveu
    parte das relações por outro caminho (o `process_id` que veio do path e já
    passou por `get_scoped_or_404`, por exemplo) e não quer pagar a query duas
    vezes.
    """
    campos = _RELACOES.keys() if apenas is None else apenas
    for campo in campos:
        if campo not in dados:
            continue
        valor = dados.get(campo)
        if valor is None:
            continue
        model, rotulo = _RELACOES[campo]
        exigir_do_tenant(db, model, valor, tenant_id, rotulo=rotulo)
