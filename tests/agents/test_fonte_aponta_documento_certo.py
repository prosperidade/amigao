"""Precisão de fonte: o chip abre o que o rótulo promete (validação Isis 30/07).

Reconstituição, com os documentos REAIS do caso 15. A consultora mapeou três
sintomas na mesma família:

* "diz auto 492262, abre 492263" (2x);
* "diz auto, abre pedido de prorrogação".

Medido no diagnóstico persistido em produção (``regulatory_diagnoses`` id 1):
a afirmação "Auto de infração 484341 (IBAMA): Destruir floresta…" carregava
``ref="325"`` — e o documento 325 é
``2007_484341D_484343D_Solicitação de Prorrogação de Prazo PRAD.pdf``.

Causa: 19 documentos do caso são tipados ``auto_infracao`` (ofício, notificação,
julgamento, PRAD, pedido de prorrogação, termo de embargo). O dedupe do #78
agrupa por número do auto e guarda ``document_ids`` — exatamente para
rastreabilidade — mas a afirmação usava o ``document_id`` SINGULAR, um membro
arbitrário do grupo, e o rotulava "Auto de infração <n>".

E os arquivos do caso citam DOIS autos no mesmo nome
(``2007_484341D_484343D_…``): sem checar o texto, nada distingue de qual auto a
peça é.
"""

from __future__ import annotations

import pytest

from app.agents.base import AgentContext
from app.agents.diagnostico import DiagnosticoAgent
from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.process import Process, ProcessStatus
from app.models.tenant import Tenant

# Nomes verbatim do caso 15 (produção).
_PRORROGACAO = "2007_484341D_484343D_Solicitação de Prorrogação de Prazo PRAD.pdf"
_AUTO = "2007_484341D_484343 D Auto de infração IBAMA 2007.pdf"


@pytest.fixture
def caso(db_session):
    tenant = Tenant(name="Fonte Certa")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="Leonardo Ribeiro",
                 email="fc@example.com", client_type=ClientType.pf,
                 status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, title="Caso 15",
                   process_type="car", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()

    def _doc(nome: str, texto: str) -> Document:
        d = Document(
            tenant_id=tenant.id, process_id=proc.id, original_file_name=nome,
            filename=nome, content_type="application/pdf",
            storage_key=f"fc/{tenant.id}/{nome}", document_type="auto_infracao",
            ocr_status=OcrStatus.done, extracted_text=texto,
        )
        db_session.add(d)
        db_session.flush()
        return d

    prorrogacao = _doc(_PRORROGACAO, "Solicitação de prorrogação de prazo do PRAD. Ref. AI 484341/D.")
    auto = _doc(_AUTO, "AUTO DE INFRAÇÃO Nº 484341/D — IBAMA. Destruir floresta de preservação permanente.")
    sem_numero = _doc("2011_Ofício 671 IBAMA.pdf", "Ofício sobre o andamento do processo administrativo.")
    db_session.flush()

    ctx = AgentContext(tenant_id=tenant.id, user_id=None, process_id=proc.id,
                       session=db_session, metadata={})
    return DiagnosticoAgent(ctx), prorrogacao, auto, sem_numero


def test_cada_documento_do_dossie_vira_uma_fonte_com_o_nome_do_arquivo(caso):
    agente, prorrogacao, auto, sem_numero = caso

    fato = {
        "numero_auto": "484341/D",
        "orgao_autuante": "IBAMA",
        "descricao_infracao": "Destruir floresta considerada de preservação permanente.",
        # O singular apontava para o pedido de prorrogação — o sintoma da Isis.
        "document_id": prorrogacao.id,
        "document_ids": [prorrogacao.id, auto.id, sem_numero.id],
    }
    fato["documentos"] = agente._documentos_do_auto(fato["document_ids"], fato["numero_auto"])

    afirmacoes = agente._build_afirmacoes_auto_infracao([fato])
    fontes = [f for f in afirmacoes[0].fontes if f.tipo == "documento"]

    # Todos os documentos do dossiê são alcançáveis — nenhum "escolhido" em silêncio.
    assert {f.ref for f in fontes} == {str(prorrogacao.id), str(auto.id), str(sem_numero.id)}

    por_ref = {f.ref: f for f in fontes}
    # O rótulo diz o que o clique abre: nome do arquivo, não "Auto de infração X".
    assert por_ref[str(prorrogacao.id)].descricao == _PRORROGACAO
    assert por_ref[str(auto.id)].descricao == _AUTO
    assert not any(f.descricao == "Auto de infração 484341/D" for f in fontes)


def test_documento_que_nao_carrega_o_numero_do_auto_entra_com_confianca_baixa(caso):
    agente, prorrogacao, auto, sem_numero = caso
    fato = {"numero_auto": "484341/D", "orgao_autuante": "IBAMA",
            "document_ids": [prorrogacao.id, auto.id, sem_numero.id]}
    docs = agente._documentos_do_auto(fato["document_ids"], fato["numero_auto"])
    por_id = {d["document_id"]: d for d in docs}

    # O auto e o pedido de prorrogação citam 484341 no texto → conferem.
    assert por_id[auto.id]["confere_numero"] is True
    assert por_id[prorrogacao.id]["confere_numero"] is True
    # O ofício não cita o número → é evidência relacionada, não prova do auto.
    assert por_id[sem_numero.id]["confere_numero"] is False

    fato["documentos"] = docs
    fontes = agente._build_afirmacoes_auto_infracao([fato])[0].fontes
    por_ref = {f.ref: f for f in fontes if f.tipo == "documento"}
    assert por_ref[str(auto.id)].confianca == "alta"
    assert por_ref[str(sem_numero.id)].confianca == "baixa"


def test_fonte_do_llm_que_cita_doc_vira_link_clicavel(caso):
    """Item 11 — 'com seta abre, sem seta não'.

    Em produção o LLM escreveu `"auto de infração 484341, IBAMA, doc. 326, 327"`
    e o chip nasceu com `ref=None`: o sistema sabia o documento, escrevia o
    número na tela e não deixava abrir.
    """
    agente, prorrogacao, auto, _sem_numero = caso

    fontes = agente._parse_item_fontes(
        f"auto de infração 484341, IBAMA, doc. {prorrogacao.id}, {auto.id}"
    )
    assert [f.ref for f in fontes] == [str(prorrogacao.id), str(auto.id)]
    assert all(f.tipo == "documento" for f in fontes)


def test_numero_que_nao_e_documento_do_caso_nao_vira_link(caso):
    """Fonte errada é pior que fonte ausente: id inexistente não vira seta."""
    agente, *_ = caso
    fontes = agente._parse_item_fontes("Lei 9.605/98, art. 70 — doc. 999999")
    assert all(f.ref is None for f in fontes)


def test_sem_fonte_continua_sem_fonte(caso):
    agente, *_ = caso
    fontes = agente._parse_item_fontes("sem fonte")
    assert fontes[0].sem_fonte is True
