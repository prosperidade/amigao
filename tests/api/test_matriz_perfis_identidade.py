"""
MATRIZ DE PERFIS DE IDENTIDADE — P1 a P7 (gate de ENT-001 / ENT-002 / DATA-001).

Por que uma matriz e não um teste por defeito: identidade não falha em um ponto,
falha em COMBINAÇÃO (PF×PJ × com/sem documento pessoal × um/dois representantes
× mesmo documento no mesmo/outro tenant). Um teste de fixture única prova que o
caso do relatório parou de falhar e não diz nada sobre os outros seis.

Cada perfil percorre o CAMINHO REAL, não um staging fabricado à mão:

    extração (`build_staging_fields`) → staging → aceite → `consolidate_process`

É isso que dá valor ao "não regrediu": a rota do documento pessoal é decidida
pelo código sob teste, não pelo fixture.

Origem dos dados: casos Valéria Ruiz (PF) e ELODI Agropecuária (PJ) da spec
Isis v0.1 §4.1-4.2 — os dois que a spec manda virar regressão permanente.

A tabela dos 7 perfis sai no fim (`test_zz_tabela_da_matriz`); rodar com `-s`.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.client_representative import ClientRepresentative
from app.models.document import Document
from app.models.extracted_field_staging import (
    ExtractedFieldStaging,
    ExtractedFieldStatus,
)
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User
from app.services.ficha01_extraction import (
    build_staging_fields,
    titular_tipo_do_processo,
)
from app.services.staging_consolidation import consolidate_process

# Dados dos casos reais da spec.
CNPJ_ELODI = "29.091.958/0001-17"
RAZAO_ELODI = "ELODI Agropecuaria Ltda."
CPF_JOEL = "123.456.789-09"
CPF_MARIA = "987.654.321-00"
CPF_VALERIA = "529.982.247-25"

# Acumulador da tabela do relatório: cada perfil deposita sua linha.
LINHAS_MATRIZ: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Cenário
# ---------------------------------------------------------------------------

def _tenant(db, nome: str) -> Tenant:
    t = Tenant(name=nome)
    db.add(t)
    db.flush()
    return t


def _user(db, tenant: Tenant, email: str) -> User:
    u = User(email=email, full_name="Consultora",
             hashed_password=get_password_hash("x12345"),
             tenant_id=tenant.id, is_active=True, is_superuser=True)
    db.add(u)
    db.flush()
    return u


def _caso(db, tenant: Tenant, *, tipo: str, documento: Optional[str],
          full_name: str, legal_name: Optional[str] = None):
    """Cliente + imóvel + processo — o mínimo para consolidar."""
    selos = {"cpf_cnpj": documento, "full_name": full_name, "legal_name": legal_name}
    cli = Client(
        tenant_id=tenant.id, full_name=full_name, legal_name=legal_name,
        cpf_cnpj=documento, email=f"c{tenant.id}.{full_name[:4]}@ex.com",
        client_type=ClientType.pj if tipo == "pj" else ClientType.pf,
        status=ClientStatus.active,
        # Cadastro digitado pela consultora já nasce validado por humano. É o
        # que faz o guard de reconciliação valer no P2 e no P3.
        field_sources={k: "human_validated" for k, v in selos.items() if v},
    )
    db.add(cli)
    db.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda Retiro")
    db.add(prop)
    db.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="regularizacao",
                   status=ProcessStatus.triagem)
    db.add(proc)
    db.flush()
    return cli, prop, proc


def _extrair_e_aceitar(db, tenant: Tenant, proc: Process, doc_type: str,
                       parsed: dict, *, document_id: Optional[int] = None) -> int:
    """Roda a EXTRAÇÃO real e deixa as linhas aceitas. Devolve nº de preparados.

    `titular_tipo` sai de `titular_tipo_do_processo` — a mesma função que a
    produção usa. Nenhum perfil informa o destino à mão.
    """
    titular_tipo = titular_tipo_do_processo(db, tenant.id, proc.id)
    campos = build_staging_fields(doc_type, parsed, titular_tipo=titular_tipo)
    for f in campos:
        db.add(ExtractedFieldStaging(
            tenant_id=tenant.id, process_id=proc.id, document_id=document_id,
            source_doc_type=doc_type, field_name=f.field_name,
            field_value=f.field_value, confidence=f.confidence,
            target_entity=f.target_entity, target_field=f.target_field,
            matricula_hint=f.matricula_hint,
            status=ExtractedFieldStatus.aceito,
            decided_value=f.field_value,
            created_by_agent="extrator",
        ))
    db.flush()
    return len(campos)


def _cnh(nome: str, cpf: str) -> dict:
    """JSON que a extração de `rg_cpf` devolve para uma CNH."""
    return {"nome": nome, "cpf": cpf, "data_nascimento": "1975-03-12"}


def _representantes(db, cli: Client) -> list[ClientRepresentative]:
    return (
        db.query(ClientRepresentative)
        .filter(ClientRepresentative.client_id == cli.id,
                ClientRepresentative.deleted_at.is_(None))
        .order_by(ClientRepresentative.id.asc())
        .all()
    )


def _registra(perfil: str, descricao: str, preparados: int, persistidos: int,
              identidade: str, esperado: str) -> None:
    LINHAS_MATRIZ.append({
        "perfil": perfil, "descricao": descricao, "preparados": preparados,
        "persistidos": persistidos, "identidade": identidade, "esperado": esperado,
    })


def _login(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login",
                    data={"username": email, "password": "x12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# P1 — PF com documento pessoal do PRÓPRIO titular
# ---------------------------------------------------------------------------

def test_p1_pf_documento_do_proprio_titular(db_session):
    """Caso Valéria: em PF o documento pessoal É do titular.

    Comportamento anterior preservado — o conserto do P3 não pode custar este.
    """
    t = _tenant(db_session, "P1")
    cli, _, proc = _caso(db_session, t, tipo="pf", documento=None,
                         full_name="Valeria Ruiz")
    prep = _extrair_e_aceitar(db_session, t, proc, "rg_cpf",
                              _cnh("Valeria Ruiz", CPF_VALERIA))
    res = consolidate_process(db_session, tenant_id=t.id, process_id=proc.id)
    db_session.refresh(cli)

    assert cli.cpf_cnpj == CPF_VALERIA, "documento do titular PF tem de pousar no titular"
    assert _representantes(db_session, cli) == [], "PF não gera representante"
    _registra("P1", "PF - documento pessoal do proprio titular", prep,
              res["campos_gravados"], f"PF cpf={cli.cpf_cnpj}",
              "CPF do titular gravado no cliente")


# ---------------------------------------------------------------------------
# P2 — PF cujo documento diverge do cadastro já validado
# ---------------------------------------------------------------------------

def test_p2_pf_documento_diverge_do_cadastro(db_session):
    """Nome do documento ≠ nome digitado e já validado → RECONCILIAÇÃO."""
    t = _tenant(db_session, "P2")
    cli, _, proc = _caso(db_session, t, tipo="pf", documento=CPF_VALERIA,
                         full_name="Valeria Ruiz")
    prep = _extrair_e_aceitar(db_session, t, proc, "rg_cpf",
                              _cnh("Valeria Ruiz Da Silva", CPF_VALERIA))
    res = consolidate_process(db_session, tenant_id=t.id, process_id=proc.id)
    db_session.refresh(cli)

    assert cli.full_name == "Valeria Ruiz", "nome já validado não é sobrescrito"
    assert any(r["field"] == "full_name" for r in res["reconciliacoes"]), \
        "divergência tem de voltar como reconciliação visível"
    _registra("P2", "PF - documento diverge do cadastro validado", prep,
              res["campos_gravados"], f"PF nome={cli.full_name!r} (preservado)",
              "divergencia vira reconciliacao, nao sobrescrita")


# ---------------------------------------------------------------------------
# P3 — PJ + CNH de representante   ← o defeito ENT-001
# ---------------------------------------------------------------------------

def test_p3_pj_com_cnh_de_representante(db_session):
    """O caso ELODI. A CNH do Joel NÃO pode virar o documento da empresa.

    Era aqui que `cpf_cnpj` do Client PJ passava de CNPJ a CPF com
    `consolidated_at` carimbado — dado errado com selo de verificado.
    """
    t = _tenant(db_session, "P3")
    cli, _, proc = _caso(db_session, t, tipo="pj", documento=CNPJ_ELODI,
                         full_name="ELODI", legal_name=RAZAO_ELODI)
    prep = _extrair_e_aceitar(db_session, t, proc, "rg_cpf",
                              _cnh("Joel Cenci", CPF_JOEL))
    res = consolidate_process(db_session, tenant_id=t.id, process_id=proc.id)
    db_session.refresh(cli)

    # 1. O titular continua sendo a empresa.
    assert cli.cpf_cnpj == CNPJ_ELODI, \
        f"P3 REGREDIU: cpf_cnpj do Client PJ virou {cli.cpf_cnpj!r}"
    assert cli.legal_name == RAZAO_ELODI, "razão social preservada (DATA-001)"
    assert cli.full_name == "ELODI", "nome do titular não vira o do representante"

    # 2. O representante existe, com o CPF da pessoa física.
    reps = _representantes(db_session, cli)
    assert len(reps) == 1, f"esperado 1 representante, vieram {len(reps)}"
    assert reps[0].cpf == CPF_JOEL
    assert reps[0].full_name == "Joel Cenci"
    assert res["representantes_criados"] == 1

    _registra("P3", "PJ - CNH de representante (caso ELODI)", prep,
              res["campos_gravados"],
              f"PJ cnpj={cli.cpf_cnpj} repr={reps[0].full_name}/{reps[0].cpf}",
              "CNPJ intacto + representante criado")


def test_p3b_staging_legado_nao_escreve_no_titular(db_session):
    """Defesa em profundidade: linha de documento pessoal que JÁ ESTÁ no banco
    apontando para `cliente` (staging gravado pela versão anterior) também não
    pousa no titular PJ. A porta da escrita não confia em quem a chama.
    """
    t = _tenant(db_session, "P3b")
    cli, _, proc = _caso(db_session, t, tipo="pj", documento=CNPJ_ELODI,
                         full_name="ELODI", legal_name=RAZAO_ELODI)
    # Exatamente o que a extração antiga produzia: target_entity="cliente".
    db_session.add(ExtractedFieldStaging(
        tenant_id=t.id, process_id=proc.id, source_doc_type="rg_cpf",
        field_name="cpf", field_value={"value": CPF_JOEL},
        target_entity="cliente", target_field="document",
        status=ExtractedFieldStatus.aceito, decided_value={"value": CPF_JOEL},
        created_by_agent="extrator",
    ))
    db_session.flush()
    consolidate_process(db_session, tenant_id=t.id, process_id=proc.id)
    db_session.refresh(cli)

    assert cli.cpf_cnpj == CNPJ_ELODI, "linha legada não pode sobrescrever o CNPJ"
    reps = _representantes(db_session, cli)
    assert len(reps) == 1 and reps[0].cpf == CPF_JOEL, \
        "o valor é redirecionado para o representante, não descartado"


# ---------------------------------------------------------------------------
# P4 — PJ sem documento pessoal (DATA-001)
# ---------------------------------------------------------------------------

def test_p4_pj_sem_documento_pessoal(client: TestClient, db_session):
    """CNPJ e razão social sobrevivem ao cadastro e APARECEM na API.

    A causa do "aba Dados com CNPJ vazio" não era a gravação: era o schema, que
    não tinha `legal_name` e descartava o campo no POST em silêncio.
    """
    t = _tenant(db_session, "P4")
    _user(db_session, t, "p4@ex.com")
    db_session.commit()
    h = _login(client, "p4@ex.com")

    r = client.post("/api/v1/clients/", headers=h, json={
        "full_name": "ELODI", "legal_name": RAZAO_ELODI,
        "cpf_cnpj": CNPJ_ELODI, "client_type": "pj",
    })
    assert r.status_code == 201, r.text
    criado = r.json()
    assert criado["legal_name"] == RAZAO_ELODI, "razão social descartada na criação"
    assert criado["cpf_cnpj"] == CNPJ_ELODI

    lido = client.get(f"/api/v1/clients/{criado['id']}", headers=h).json()
    assert lido["legal_name"] == RAZAO_ELODI, "razão social não volta na leitura"
    assert lido["representatives"] == [], "PJ sem representante: lista vazia"

    hub = client.get(f"/api/v1/clients/{criado['id']}/summary", headers=h).json()
    assert hub["header"]["legal_name"] == RAZAO_ELODI, "Hub não mostra a razão social"
    assert hub["header"]["cpf_cnpj"] == CNPJ_ELODI

    _registra("P4", "PJ - sem documento pessoal (so cadastro)", 2, 2,
              f"PJ cnpj={lido['cpf_cnpj']} razao={lido['legal_name']!r}",
              "CNPJ e razao social em todas as telas")


# ---------------------------------------------------------------------------
# P5 — PJ com DOIS representantes
# ---------------------------------------------------------------------------

def test_p5_pj_com_dois_representantes(db_session):
    """Duas CNHs = duas pessoas. A segunda não sobrescreve a primeira, e
    nenhuma das duas encosta no titular.
    """
    t = _tenant(db_session, "P5")
    cli, _, proc = _caso(db_session, t, tipo="pj", documento=CNPJ_ELODI,
                         full_name="ELODI", legal_name=RAZAO_ELODI)
    docs = []
    for i in (1, 2):
        d = Document(tenant_id=t.id, process_id=proc.id,
                     original_file_name=f"cnh{i}.pdf", filename=f"cnh{i}.pdf",
                     content_type="application/pdf",
                     storage_key=f"tenant_{t.id}/cnh{i}.pdf", document_type="rg_cpf")
        db_session.add(d)
        docs.append(d)
    db_session.flush()

    prep = _extrair_e_aceitar(db_session, t, proc, "rg_cpf",
                              _cnh("Joel Cenci", CPF_JOEL), document_id=docs[0].id)
    prep += _extrair_e_aceitar(db_session, t, proc, "rg_cpf",
                               _cnh("Maria Cenci", CPF_MARIA), document_id=docs[1].id)
    res = consolidate_process(db_session, tenant_id=t.id, process_id=proc.id)
    db_session.refresh(cli)

    reps = _representantes(db_session, cli)
    assert cli.cpf_cnpj == CNPJ_ELODI, "titular intocado com dois representantes"
    assert len(reps) == 2, f"esperados 2 representantes, vieram {len(reps)}"
    assert {r.cpf for r in reps} == {CPF_JOEL, CPF_MARIA}
    _registra("P5", "PJ - dois documentos pessoais", prep, res["campos_gravados"],
              f"PJ cnpj={cli.cpf_cnpj} {len(reps)} representantes",
              "dois representantes, titular intocado")


# ---------------------------------------------------------------------------
# P6 — mesmo CNPJ duas vezes no tenant   ← o defeito ENT-002
# ---------------------------------------------------------------------------

def test_p6_mesmo_cnpj_duas_vezes_no_tenant(client: TestClient, db_session):
    """Segundo cadastro do mesmo CNPJ é BLOQUEADO e a resposta aponta o
    existente. Inclusive com pontuação diferente — identidade é dígito.
    """
    t = _tenant(db_session, "P6")
    _user(db_session, t, "p6@ex.com")
    db_session.commit()
    h = _login(client, "p6@ex.com")

    r1 = client.post("/api/v1/clients/", headers=h, json={
        "full_name": "ELODI", "legal_name": RAZAO_ELODI,
        "cpf_cnpj": CNPJ_ELODI, "client_type": "pj"})
    assert r1.status_code == 201, r1.text
    primeiro = r1.json()["id"]

    # Mesma pessoa, nome diferente e SEM pontuação: era assim que o duplicado
    # entrava — comparação de string crua não casa "29.091.958/0001-17" com
    # "29091958000117".
    r2 = client.post("/api/v1/clients/", headers=h, json={
        "full_name": "Joel Cenci ELODI", "cpf_cnpj": "29091958000117",
        "client_type": "pj"})
    assert r2.status_code == 409, \
        f"duplicata não foi bloqueada: {r2.status_code} {r2.text}"
    det = r2.json()["detail"]
    assert det["client_id"] == primeiro, "o bloqueio tem de APONTAR o cadastro a reutilizar"

    # E a busca prévia oferece a reutilização antes de digitar o resto.
    look = client.get("/api/v1/clients/lookup/documento",
                      params={"documento": "29091958000117"}, headers=h)
    assert look.status_code == 200 and look.json()["id"] == primeiro

    total = db_session.query(Client).filter(Client.tenant_id == t.id).count()
    assert total == 1, f"tenant ficou com {total} cadastros para o mesmo CNPJ"
    _registra("P6", "PJ - mesmo CNPJ 2x no tenant", 2, 1,
              f"1 cadastro (#{primeiro}), 2a tentativa 409",
              "duplicata bloqueada com reutilizacao oferecida")


def test_p6b_banco_recusa_duplicata_por_baixo_da_api(db_session):
    """A unicidade é do BANCO, não só da rota: qualquer caminho de escrita
    esbarra nela (worker, script, import). Sem isto ENT-002 seria convenção de
    camada — e convenção não é constraint.
    """
    t = _tenant(db_session, "P6b")
    db_session.add(Client(tenant_id=t.id, full_name="ELODI", cpf_cnpj=CNPJ_ELODI,
                          client_type=ClientType.pj, email="a@ex.com"))
    db_session.flush()
    db_session.add(Client(tenant_id=t.id, full_name="Outro nome",
                          cpf_cnpj="29091958000117",
                          client_type=ClientType.pj, email="b@ex.com"))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


# ---------------------------------------------------------------------------
# P7 — mesmo documento em tenants distintos
# ---------------------------------------------------------------------------

def test_p7_mesmo_documento_em_tenants_distintos(db_session):
    """Unicidade é POR TENANT. O mesmo produtor pode ser cliente de duas
    consultorias — índice global quebraria o Princípio 4.
    """
    t1 = _tenant(db_session, "P7-A")
    t2 = _tenant(db_session, "P7-B")
    db_session.add(Client(tenant_id=t1.id, full_name="ELODI", cpf_cnpj=CNPJ_ELODI,
                          client_type=ClientType.pj, email="t1@ex.com"))
    db_session.add(Client(tenant_id=t2.id, full_name="ELODI", cpf_cnpj=CNPJ_ELODI,
                          client_type=ClientType.pj, email="t2@ex.com"))
    db_session.flush()   # não pode levantar

    achados = (
        db_session.query(Client)
        .filter(Client.cpf_cnpj == CNPJ_ELODI,
                Client.tenant_id.in_([t1.id, t2.id]))
        .count()
    )
    assert achados == 2, "o mesmo documento tem de coexistir em tenants distintos"
    _registra("P7", "mesmo documento em 2 tenants", 2, 2,
              "1 cadastro em cada tenant",
              "permitido - unicidade e por tenant")


# ---------------------------------------------------------------------------
# Tabela do relatório
# ---------------------------------------------------------------------------

def test_zz_tabela_da_matriz():
    """Renderiza a matriz. Roda por último; `pytest -s` mostra a tabela."""
    if not LINHAS_MATRIZ:
        pytest.skip("nenhum perfil rodou nesta seleção")
    largura = 116
    print("\n\nMATRIZ DE PERFIS DE IDENTIDADE - P1 a P7")
    print("=" * largura)
    print(f"{'PERFIL':<7}{'CENARIO':<44}{'PREP':>5}{'PERS':>5}  "
          f"{'IDENTIDADE FINAL DO CLIENT':<50}")
    print("-" * largura)
    for linha in sorted(LINHAS_MATRIZ, key=lambda x: x["perfil"]):
        print(f"{linha['perfil']:<7}{linha['descricao']:<44}"
              f"{linha['preparados']:>5}{linha['persistidos']:>5}  "
              f"{linha['identidade']:<50}")
    print("=" * largura)
    for linha in sorted(LINHAS_MATRIZ, key=lambda x: x["perfil"]):
        print(f"  {linha['perfil']} - esperado: {linha['esperado']}")
    print()
