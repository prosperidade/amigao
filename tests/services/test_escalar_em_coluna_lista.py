"""Escalar nu pousando em coluna JSON de lista — a classe do `proprietarios`.

Caso 15, 21/07: o CCIR extrai `detentor` como ESCALAR de texto e o mapeamento o
roteia para `Matricula.proprietarios`, que é coluna de LISTA. A string nua foi
gravada; quem leu fez ``lista.extend("Leonardo Ribeiro")`` — que NÃO levanta
erro, itera os CARACTERES — e o estouro só apareceu dois módulos adiante, no
``p.get("cpf")`` do auto de infração, com `'str' object has no attribute 'get'`.

Estes testes cobrem a cadeia inteira, nas três camadas em que ela foi fechada:
a porta única (normalizador), a escrita (recusa/embrulho) e a leitura tolerante
do que JÁ está gravado torto em produção.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.matricula import Matricula
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.services.auto_infracao_extraction import check_autuado_diverge_titular
from app.services.inconsistency_matrix import (
    fit_json_container,
    normalize_list_of_dicts,
)
from app.services.staging_consolidation import consolidate_process

_SEQ = {"n": 0}


# ---------------------------------------------------------------------------
# Porta única — normalização (leitura) e encaixe (escrita)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "entrada, esperado",
    [
        ("Leonardo Ribeiro", [{"nome": "Leonardo Ribeiro"}]),
        (None, []),
        ("", []),
        ("   ", []),
        ({"nome": "A", "cpf": "1"}, [{"nome": "A", "cpf": "1"}]),
        ([{"nome": "A"}], [{"nome": "A"}]),
        ([{"nome": "A"}, "B", None, ""], [{"nome": "A"}, {"nome": "B"}]),
        (["X", "Y"], [{"nome": "X"}, {"nome": "Y"}]),
    ],
)
def test_normalize_list_of_dicts_cobre_o_legado_torto(entrada, esperado):
    assert normalize_list_of_dicts(entrada, item_key="nome") == esperado


def test_normalize_nunca_devolve_algo_que_itere_caracteres():
    """O coração do bug: o resultado tem que ser seguro para `.get()` item a item."""
    for item in normalize_list_of_dicts("Leonardo Ribeiro"):
        assert isinstance(item, dict)
        item.get("cpf")  # não levanta — era exatamente aqui que estourava


def test_fit_embrulha_escalar_em_coluna_de_lista_conhecida():
    valor, erro = fit_json_container("Leonardo Ribeiro", list, "proprietarios")
    assert erro is None
    assert valor == [{"nome": "Leonardo Ribeiro"}]


def test_fit_recusa_escalar_em_coluna_sem_shape_conhecido():
    """Sem shape conhecido não se adivinha: recusa ALTO em vez de gravar nu."""
    valor, erro = fit_json_container("qualquer", list, "scope_items")
    assert valor is None
    assert "escalar em coluna de lista" in erro


def test_fit_recusa_escalar_em_coluna_de_dict():
    valor, erro = fit_json_container("qualquer", dict, "field_sources")
    assert valor is None
    assert "escalar em coluna de dict" in erro


def test_fit_nao_mexe_em_coluna_escalar_nem_em_lista_ja_correta():
    assert fit_json_container("Cartorio X", None, "cartorio") == ("Cartorio X", None)
    ja_certo = [{"nome": "A", "cpf": "1"}]
    assert fit_json_container(ja_certo, list, "proprietarios") == (ja_certo, None)


# ---------------------------------------------------------------------------
# Consumidor final — o ponto onde o erro DE FATO apareceu
# ---------------------------------------------------------------------------

def test_check_autuado_nao_quebra_com_proprietarios_string():
    """Reprodução direta do crash em produção (AIJob 972/973)."""
    nota = check_autuado_diverge_titular(
        "Fulano de Tal", "12345678900", matricula_proprietarios="Leonardo Ribeiro"
    )
    assert nota is not None and "difere do titular" in nota


def test_check_autuado_reconhece_titular_vindo_de_string_legada():
    """Não basta não quebrar: o nome tem que voltar a CONTAR.

    Com a lista corrompida em caracteres, nenhum nome casava nunca — o sistema
    reportaria divergência de titularidade mesmo quando o autuado É o titular.
    """
    assert check_autuado_diverge_titular(
        "Leonardo Ribeiro", None, matricula_proprietarios="Leonardo Ribeiro"
    ) is None


# ---------------------------------------------------------------------------
# Cadeia inteira contra o banco: CCIR escalar → consolidação → leitura
# ---------------------------------------------------------------------------

def _seed(db_session):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"Escalar {n}")
    db_session.add(tenant)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email=f"esc{n}@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda Sao Jorge")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="car", status=ProcessStatus.triagem,
                   demand_type=DemandType.car)
    db_session.add(proc)
    db_session.flush()
    return tenant, proc, prop


def _doc(db_session, tenant, proc, doc_type):
    _SEQ["n"] += 1
    d = Document(tenant_id=tenant.id, process_id=proc.id,
                 original_file_name="d.pdf", filename="d.pdf",
                 content_type="application/pdf",
                 storage_key=f"esc/{tenant.id}/{_SEQ['n']}",
                 document_type=doc_type, ocr_status=OcrStatus.done)
    db_session.add(d)
    db_session.flush()
    return d


def _aceito(db_session, tenant, proc, doc, campo, valor, alvo, *, hint=None):
    row = ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name=campo, field_value={"value": valor},
        status=ExtractedFieldStatus.aceito, decided_value={"value": valor},
        decided_at=datetime.now(UTC),
        target_entity="matricula", target_field=alvo,
        matricula_hint=hint, source_doc_type=doc.document_type,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_detentor_escalar_do_ccir_nunca_grava_string_nua(db_session):
    """A cadeia do caso 15, ponta a ponta: o CCIR não corrompe mais a coluna."""
    tenant, proc, prop = _seed(db_session)

    cert = _doc(db_session, tenant, proc, "matricula")
    _aceito(db_session, tenant, proc, cert, "numero_matricula", "2923",
            "numero_matricula", hint="2923")

    ccir = _doc(db_session, tenant, proc, "ccir")
    _aceito(db_session, tenant, proc, ccir, "detentor", "Leonardo Ribeiro",
            "proprietarios", hint="2923")
    db_session.commit()

    consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id, user_id=None)

    db_session.expire_all()
    mat = (
        db_session.query(Matricula)
        .filter(Matricula.property_id == prop.id, Matricula.numero_matricula == "2923")
        .first()
    )
    assert mat is not None
    assert mat.proprietarios == [{"nome": "Leonardo Ribeiro"}], (
        "escalar tem que pousar no shape da coluna, nunca como string nua"
    )

    # E o que foi gravado é seguro para o consumidor que quebrava.
    for p in normalize_list_of_dicts(mat.proprietarios):
        assert isinstance(p, dict)


def test_leitura_tolera_string_nua_ja_gravada_no_legado(db_session):
    """As 2 matrículas de produção estão assim HOJE — o fix de leitura as cobre
    até o reparo do dado rodar pelo rito."""
    tenant, proc, prop = _seed(db_session)
    mat = Matricula(tenant_id=tenant.id, property_id=prop.id,
                    numero_matricula="2923", proprietarios="Leonardo Ribeiro")
    db_session.add(mat)
    db_session.commit()
    db_session.expire_all()

    lido = db_session.query(Matricula).filter(Matricula.id == mat.id).first()
    assert lido.proprietarios == "Leonardo Ribeiro"  # o legado continua lá

    acumulado: list[dict] = []
    acumulado.extend(normalize_list_of_dicts(lido.proprietarios, item_key="nome"))
    assert acumulado == [{"nome": "Leonardo Ribeiro"}]
    assert check_autuado_diverge_titular(
        "Outro Nome", None, matricula_proprietarios=acumulado
    ) is not None
