"""Documento anexado não pode sumir da conta enquanto o OCR não classifica.

Validação 02/08: a consultora subiu o CAR na E3, re-rodou o agente, e a
Conferência continuou dizendo que o CAR faltava. O arquivo estava lá, visível na
aba Documentos.

A causa não era o upload nem o agente: `avaliar_requisitos` agrupa os documentos
por ``document_type``, e ``document_type`` só é preenchido DEPOIS que o OCR roda
e a classificação por conteúdo acerta. Antes disso o documento não caía em
requisito nenhum — era descartado em silêncio no laço de agrupamento — e o
requisito ficava AUSENTE. Isso quebra a promessa que o próprio módulo faz
(P12: "o consultor nunca vê 'ausente' com o documento visível na tela").

Duas saídas, ambas cobertas aqui:

* quando o consultor anexou o arquivo CONTRA um item do checklist, o vínculo já
  declara a que requisito ele serve — isso vale sem esperar o OCR;
* quando nem assim dá para encaixar, o documento volta NOMEADO em
  `documentos_sem_requisito`, para a tela poder dizer que ele existe.
"""

from __future__ import annotations

import itertools

import pytest

from app.models.checklist_template import ProcessChecklist
from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.macroetapa import Macroetapa
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant
from app.services.requisito_documental import (
    RequisitoStatus,
    avaliar_requisitos,
    documentos_sem_requisito,
)


@pytest.fixture
def caso(db_session):
    tenant = Tenant(name="CAR sem classificação")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(
        tenant_id=tenant.id, full_name="Titular", email=f"c{tenant.id}@example.com",
        client_type=ClientType.pf, status=ClientStatus.active,
    )
    db_session.add(cli)
    db_session.flush()
    proc = Process(
        tenant_id=tenant.id, client_id=cli.id, title="Caso da validação",
        process_type="car", status=ProcessStatus.triagem,
        macroetapa=Macroetapa.coleta_documental.value,
    )
    db_session.add(proc)
    db_session.flush()
    return db_session, tenant, proc


def _checklist_com_item_car(db, tenant, proc, item_id: str = "car") -> None:
    db.add(ProcessChecklist(
        tenant_id=tenant.id,
        process_id=proc.id,
        items=[{
            "id": item_id, "label": "CAR", "doc_type": "car",
            "category": "ambiental", "required": True, "status": "pending",
        }],
    ))
    db.flush()


_seq = itertools.count(1)


def _documento(db, tenant, proc, **kwargs) -> Document:
    nome = kwargs.pop("filename", "recibo-car.pdf")
    doc = Document(
        tenant_id=tenant.id,
        process_id=proc.id,
        client_id=proc.client_id,
        filename=nome,
        original_file_name=nome,
        content_type="application/pdf",
        # `storage_key` é UNIQUE — cada documento do teste precisa da sua.
        storage_key=f"t{tenant.id}/p{proc.id}/{next(_seq)}-{nome}",
        **kwargs,
    )
    db.add(doc)
    db.flush()
    return doc


# ---------------------------------------------------------------------------
# O bug relatado
# ---------------------------------------------------------------------------

def test_car_anexado_ao_item_do_checklist_nao_fica_ausente_sem_ocr(caso) -> None:
    """O caso exato da validação: CAR na base, tipo ainda nulo, OCR rodando."""
    db, tenant, proc = caso
    _checklist_com_item_car(db, tenant, proc)
    _documento(db, tenant, proc, document_type=None,
               checklist_item_id="car", ocr_status=OcrStatus.processing)

    car = avaliar_requisitos(db, proc.id, tenant.id)["car"]

    assert car.status is not RequisitoStatus.AUSENTE, (
        "o CAR está anexado e visível na tela — dizer 'não recebido' é a queixa "
        "de 02/08 e viola o P12 declarado no módulo"
    )
    assert car.tem_documento
    assert "não recebido" not in car.detalhe


def test_documento_sem_tipo_e_sem_vinculo_nao_some_calado(caso) -> None:
    """Não dá para adivinhar o requisito — mas dá para dizer que o arquivo existe."""
    db, tenant, proc = caso
    doc = _documento(db, tenant, proc, filename="scan-sem-nome.pdf",
                     document_type=None, ocr_status=OcrStatus.pending)

    orfaos = documentos_sem_requisito(db, proc.id, tenant.id)

    assert [d.id for d in orfaos] == [doc.id]


# ---------------------------------------------------------------------------
# Não afrouxar o que já era verdade
# ---------------------------------------------------------------------------

def test_tipo_classificado_continua_mandando(caso) -> None:
    """Controle: com `document_type` preenchido nada depende do checklist."""
    db, tenant, proc = caso
    _documento(db, tenant, proc, document_type="car", ocr_status=OcrStatus.processing)

    car = avaliar_requisitos(db, proc.id, tenant.id)["car"]

    assert car.status is RequisitoStatus.RECEBIDO_EM_PROCESSAMENTO
    assert documentos_sem_requisito(db, proc.id, tenant.id) == []


def test_vinculo_a_item_fora_dos_6_nao_inventa_requisito(caso) -> None:
    """Item de checklist que não é um dos 6 não pode satisfazer requisito nenhum.

    O vínculo honra a intenção declarada; não é um curinga. Um arquivo anexado
    ao item "fotos da área" continua sem casa entre os obrigatórios — e por isso
    aparece na lista de não classificados, em vez de virar CAR por conveniência.
    """
    db, tenant, proc = caso
    db.add(ProcessChecklist(
        tenant_id=tenant.id, process_id=proc.id,
        items=[{"id": "fotos", "label": "Fotos da área", "doc_type": "fotos",
                "category": "tecnico", "required": True, "status": "pending"}],
    ))
    db.flush()
    doc = _documento(db, tenant, proc, filename="fotos.pdf", document_type=None,
                     checklist_item_id="fotos", ocr_status=OcrStatus.done)

    resultados = avaliar_requisitos(db, proc.id, tenant.id)

    assert all(r.status is RequisitoStatus.AUSENTE for r in resultados.values())
    assert [d.id for d in documentos_sem_requisito(db, proc.id, tenant.id)] == [doc.id]


def test_caso_sem_documento_algum_segue_ausente(caso) -> None:
    """Controle negativo: a correção não pode fabricar documento onde não há."""
    db, tenant, proc = caso
    _checklist_com_item_car(db, tenant, proc)

    car = avaliar_requisitos(db, proc.id, tenant.id)["car"]

    assert car.status is RequisitoStatus.AUSENTE
    assert car.pendente is True
