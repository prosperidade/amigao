"""GATE da Frente H (ADR-068) — caso real ELODI (#23), fixture já vetada.

Reusa a MESMA fixture ELODI das Frentes E/F/G (`test_reconciliation_
decisions._elodi`, `extracted_text` real de produção medido nas frentes
anteriores) — não reinventa dado. Sem chamada a LLM nesta frente (STATE-001/
DOC-001/REV-001 são determinísticos); portanto "duas execuções onde houver
LLM" não se aplica — a evolução pendente→decidida→gravada é medida em duas
chamadas de `consolidate_process`, a mesma convenção de duas passagens que o
GATE da Frente G já usa (guard fantasma da matrícula).

Este teste É o gate: roda, imprime a tabela dos seis números lado a lado em
cada estágio (`pytest -s`) e afirma que eles batem (ou que a diferença é
explicada, caso do `macroetapa` que não existe nesta fixture sem
`MacroetapaChecklist`).
"""

from __future__ import annotations

from tests.services.test_reconciliation_decisions import _elodi

from app.models.checklist_template import ProcessChecklist
from app.models.document import Document
from app.services.checklist_engine import get_checklist_status, mark_item_received
from app.services.document_lifecycle import (
    derive_document_status,
    historico_transicoes,
    registrar_transicao_se_mudou,
)
from app.services.dossier import generate_dossier
from app.services.process_indicators import progresso_conferencia
from app.services.staging_consolidation import consolidate_process, decidir_decisao_agrupada


def _linha(rotulo, valor):
    print(f"  {rotulo:32s} {valor}")


def test_gate_frente_h_estado_unico_elodi(db_session):
    tenant, proc, prop, cli, rows = _elodi(db_session)

    # Checklist documental do processo (source #1/#6 do STATE-001) — a fixture
    # ELODI não cria um; o caso real tem. 3 itens: 1 recebido COM documento
    # (a matrícula 3181, que existe na fixture), 1 recebido SEM documento (o
    # achado da triagem) e 1 pendente.
    checklist = ProcessChecklist(
        tenant_id=tenant.id, process_id=proc.id,
        items=[
            {"id": "matricula_3181", "label": "Matrícula 3.181", "doc_type": "matricula",
             "category": "fundiario", "required": True, "status": "pending", "document_id": None},
            {"id": "ccir", "label": "CCIR", "doc_type": "ccir",
             "category": "fundiario", "required": True, "status": "pending", "document_id": None},
            {"id": "itr", "label": "ITR", "doc_type": "itr",
             "category": "fundiario", "required": False, "status": "pending", "document_id": None},
        ],
    )
    db_session.add(checklist)
    db_session.flush()
    mark_item_received(checklist, "matricula_3181", rows["certidao_3181"].document_id)
    mark_item_received(checklist, "ccir")  # SEM documento — marcação manual

    def tabela(momento: str):
        print(f"\n=== {momento} ===")
        cs = get_checklist_status(checklist)
        _linha("checklist (get_checklist_status)",
               f"{cs.received}/{cs.total_items} recebidos "
               f"({cs.received_without_document} sem doc) → {cs.completion_pct}%")

        pc = progresso_conferencia(db_session, tenant_id=tenant.id, process_id=proc.id)
        _linha("conferencia (progresso_conferencia)",
               f"{pc.decididas}/{pc.decisoes_total} decididas, {pc.gravadas} gravadas, "
               f"{pc.pendentes} pendentes")

        dossie = generate_dossier(db_session, proc.id, tenant.id)
        _linha("dossiê.checklist_summary", dossie.checklist_summary)
        _linha("dossiê.conferencia_summary", dossie.conferencia_summary)

        assert dossie.checklist_summary["completion_pct"] == cs.completion_pct
        assert dossie.checklist_summary["received_without_document"] == cs.received_without_document
        assert dossie.conferencia_summary == pc.to_dict()
        return pc

    print("\n" + "=" * 70)
    print("GATE FRENTE H — ELODI (#23) — os seis números, lado a lado")
    print("=" * 70)

    antes = tabela("ESTÁGIO 1 — staging recém-chegado, nada decidido")
    assert antes.decididas == 0
    assert antes.gravadas == 0

    # Decide a composição da 3181 (mesma decisão do GATE da Frente G).
    decidir_decisao_agrupada(
        db_session, tenant_id=tenant.id, process_id=proc.id,
        chave=("matricula", "3181", "composicao"), acao="aceitar", user_id=None,
    )
    meio = tabela("ESTÁGIO 2 — composição da 3181 DECIDIDA, ainda não gravada")
    assert meio.decididas == antes.decididas + 1
    assert meio.gravadas == antes.gravadas  # decidida != gravada (30/07 e 02/08)

    # Duas passagens de consolidação — mesma convenção do GATE da Frente G
    # (guard fantasma: a 1ª cria a matrícula pela certidão, a 2ª carimba o CAR).
    r1 = consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id, user_id=None)
    r2 = consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id, user_id=None)
    _linha("consolidação (resultado da chamada, passagem 1)", f"campos_gravados={r1['campos_gravados']}")
    _linha("consolidação (resultado da chamada, passagem 2)", f"campos_gravados={r2['campos_gravados']}")

    depois = tabela("ESTÁGIO 3 — composição da 3181 GRAVADA na base")
    assert depois.gravadas == meio.gravadas + 1
    assert depois.pendentes == meio.pendentes

    # DOC-001 — a certidão da 3181 (mat_3181) tem 1 linha de staging, agora
    # gravada/aceita. Sequência de transição do documento.
    doc_3181 = db_session.get(Document, rows["certidao_3181"].document_id)
    print("\n--- DOC-001: escada do documento (certidão da 3.181) ---")
    registrar_transicao_se_mudou(db_session, doc_3181, user_id=None)
    for t in historico_transicoes(db_session, doc_3181):
        _linha(f"{t.old_value} → {t.new_value}", f"autor={t.user_id} ação={t.action}")
    estado_final = derive_document_status(db_session, doc_3181)
    print(f"  estado atual derivado: {estado_final.value}")

    print("\n" + "=" * 70)
    print("Explicando divergências legítimas (Astra bloco C):")
    print("- checklist mede DOCUMENTOS do processo; conferência mede DECISÕES")
    print("  (fatos do domínio) — números diferentes, perguntas diferentes.")
    print("- 'consolidação' acima é o RESULTADO DE UMA CHAMADA (delta), não o")
    print("  total corrente — por isso a passagem 1 pode gravar 0 e a 2 gravar")
    print("  1 mesmo com só uma decisão aceita (guard fantasma da matrícula).")
    print("=" * 70)
