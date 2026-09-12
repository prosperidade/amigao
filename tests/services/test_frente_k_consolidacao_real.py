"""Frente K — a consolidação grava o que as decisões aceitas mandam.

Cada teste aqui nasceu de uma linha medida no gate E2E de 12/09 sobre os 6
documentos reais da ELODI (texto de produção, docs 546–551), com a pilha de pé
e a consultora decidindo TUDO — que é o gesto que nenhum gate anterior tinha
feito. O resultado dessa medição, antes destes consertos:

    POST /processes/1/consolidar → 500
    113 linhas aceitas, 0 gravadas, nenhuma palavra para a consultora

Depois: 37 campos gravados, `area_total` = 2180,3923 = a soma exata das quatro
matrículas, 19 das 20 decisões em "Gravado na base", e as 118 linhas com
desfecho declarado (nenhuma sem motivo).

Os quatro defeitos, um por bloco abaixo:

1. `state` — o CAR escreve "Goiás" e a coluna é `String(2)`: `DataError` no
   flush derrubava a consolidação INTEIRA;
2. o socorro do endpoint lia `current_user.tenant_id` numa sessão já
   envenenada e morria antes de socorrer (`PendingRollbackError`), trocando a
   frase explicativa por "Internal Server Error";
3. `rl_declarada_ha` (área, número) pousava em `rl_status` (estado);
4. as decisões de `gravames` e `titularidade` não continham a linha que grava
   (`onus_gravames`, `proprietarios`) — a consultora decidia, a decisão virava
   "decidida", e a coluna continuava vazia.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import get_password_hash
from app.models.client import Client, ClientStatus, ClientType
from app.models.document import Document, OcrStatus
from app.models.extracted_field_staging import ExtractedFieldStaging, ExtractedFieldStatus
from app.models.process import DemandType, Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User
from app.services.reconciliation_decisions import build_decisions
from app.services.staging_consolidation import (
    _coerce_uf,
    consolidate_process,
    decidir_decisao_agrupada,
)

_SEQ = {"n": 0}
_SENHA = "FrenteK-2026!"


def _seed(db_session, *, client_type=ClientType.pj):
    _SEQ["n"] += 1
    n = _SEQ["n"]
    tenant = Tenant(name=f"Frente K {n}")
    db_session.add(tenant)
    db_session.flush()
    user = User(tenant_id=tenant.id, email=f"frentek.user{n}@example.com", full_name="Consultora",
                hashed_password=get_password_hash(_SENHA), is_active=True, is_superuser=True)
    db_session.add(user)
    db_session.flush()
    cli = Client(tenant_id=tenant.id, full_name="ELODI AGROPECUARIA",
                 email=f"frentek{n}@example.com", client_type=client_type,
                 status=ClientStatus.active)
    db_session.add(cli)
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda Retiro dos Olhos Dagua")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="car", status=ProcessStatus.triagem,
                   demand_type=DemandType.car)
    db_session.add(proc)
    db_session.flush()
    return tenant, proc, prop, cli


def _login(client, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", data={"username": email, "password": _SENHA})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _doc(db_session, tenant, proc, doc_type):
    _SEQ["n"] += 1
    d = Document(tenant_id=tenant.id, process_id=proc.id,
                 original_file_name=f"{doc_type}.pdf", filename=f"{doc_type}.pdf",
                 content_type="application/pdf",
                 storage_key=f"frentek/{tenant.id}/{_SEQ['n']}",
                 document_type=doc_type, ocr_status=OcrStatus.done)
    db_session.add(d)
    db_session.flush()
    return d


def _linha(db_session, tenant, proc, doc, *, field_name, valor, entidade=None, alvo=None,
           hint=None, tipo_obs=None, atributos=None, unidade=None,
           status=ExtractedFieldStatus.pendente, aceita=False, field_value=None):
    fv = field_value if field_value is not None else {"value": valor}
    if unidade:
        fv["unidade"] = unidade
    row = ExtractedFieldStaging(
        tenant_id=tenant.id, process_id=proc.id, document_id=doc.id,
        field_name=field_name, field_value=fv,
        status=ExtractedFieldStatus.aceito if aceita else status,
        decided_value={"value": valor} if aceita else None,
        decided_at=datetime.now(UTC) if aceita else None,
        target_entity=entidade, target_field=alvo, matricula_hint=hint,
        source_doc_type=doc.document_type, tipo_observacao=tipo_obs, atributos=atributos,
    )
    db_session.add(row)
    db_session.flush()
    return row


# ---------------------------------------------------------------------------
# 1. "Goiás" não derruba a consolidação — e vira "GO"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "entrada,esperado",
    [("Goiás", "GO"), ("goias", "GO"), ("GO", "GO"), ("go", "GO"),
     ("Mato Grosso do Sul", "MS"), ("São Paulo", "SP"),
     ("XX", None), ("Estado de Goiás", None), ("", None)],
)
def test_uf_por_extenso_vira_sigla(entrada, esperado):
    """A tabela é fechada: ou casa com uma das 27 UFs, ou não é UF."""
    assert _coerce_uf(entrada) == esperado


def test_car_com_uf_por_extenso_grava_a_sigla_e_os_demais_campos(db_session):
    """O `DataError` que devolvia 500 e não gravava NADA.

    Medido no gate: `UPDATE properties SET state='Goiás'` numa coluna
    `character varying(2)` levantava `StringDataRightTruncation` no flush, e
    com ele iam embora os outros campos do MESMO update (`app_area_ha`,
    `area_documental_ha`, `modulos_fiscais`) e todo o resto da passagem.
    """
    tenant, proc, prop, _cli = _seed(db_session)
    car = _doc(db_session, tenant, proc, "car")
    _linha(db_session, tenant, proc, car, field_name="uf", valor="Goiás",
           entidade="imovel", alvo="state", aceita=True)
    _linha(db_session, tenant, proc, car, field_name="municipio",
           valor="Alto Paraíso de Goiás", entidade="imovel", alvo="municipality", aceita=True)
    _linha(db_session, tenant, proc, car, field_name="app_declarada_ha", valor="90,4225",
           entidade="imovel", alvo="app_area_ha", unidade="ha", aceita=True)
    db_session.commit()

    res = consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id)

    db_session.refresh(prop)
    assert prop.state == "GO"
    assert prop.municipality == "Alto Paraíso de Goiás"
    assert prop.app_area_ha == pytest.approx(90.4225)
    assert res["campos_gravados"] == 3


def test_uf_irreconhecivel_recusa_a_linha_e_grava_o_resto(db_session):
    """Radar não cancela o voo: a linha ruim sai por `ignorados`, com motivo, e
    as outras gravam. O contrário — o que acontecia — é a consultora clicar em
    "Gravar na base", ver 500, e perder as 112 linhas boas junto com a ruim."""
    tenant, proc, prop, _cli = _seed(db_session)
    car = _doc(db_session, tenant, proc, "car")
    _linha(db_session, tenant, proc, car, field_name="uf", valor="Estado de Goiás",
           entidade="imovel", alvo="state", aceita=True)
    _linha(db_session, tenant, proc, car, field_name="numero_car", valor="GO-5200605-82E5",
           entidade="imovel", alvo="car_code", aceita=True)
    db_session.commit()

    res = consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id)

    db_session.refresh(prop)
    assert prop.state is None
    assert prop.car_code == "GO-5200605-82E5"
    assert res["campos_gravados"] == 1
    assert any("state" in m for m in res["ignorados"]), res["ignorados"]


def test_valor_maior_que_a_coluna_e_recusa_de_uma_linha_so(db_session):
    """O guard de tamanho é geral, não um remendo para `state`.

    `client_representatives.papel` é `String(50)`. Um valor de 80 caracteres
    tem de sair por `ignorados` dizendo o tamanho — nunca chegar ao flush.
    """
    tenant, proc, _prop, cli = _seed(db_session)
    cnh = _doc(db_session, tenant, proc, "rg_cpf")
    _linha(db_session, tenant, proc, cnh, field_name="nome", valor="JOEL CENCI",
           entidade="representante", alvo="full_name", aceita=True)
    _linha(db_session, tenant, proc, cnh, field_name="papel", valor="S" * 80,
           entidade="representante", alvo="papel", aceita=True)
    db_session.commit()

    res = consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id)

    assert res["representante_atualizado"] is True
    motivo = next((m for m in res["ignorados"] if ".papel:" in m), None)
    assert motivo is not None, res["ignorados"]
    assert "80" in motivo and "50" in motivo, motivo


# ---------------------------------------------------------------------------
# 2. o socorro do endpoint não pode morrer antes de socorrer
# ---------------------------------------------------------------------------

def test_falha_na_consolidacao_devolve_a_frase_e_nao_internal_server_error(
    client, db_session, monkeypatch
):
    """`PendingRollbackError` no bloco `except`, medido no gate.

    O endpoint capturava a falha e chamava `registrar_falha_consolidacao(...,
    tenant_id=current_user.tenant_id, ...)`. Esse acesso a atributo disparava
    um lazy-load numa sessão cuja transação já tinha sido desfeita pelo erro —
    e o socorro explodia antes de registrar a auditoria ou devolver a
    explicação. A consultora recebia "Internal Server Error".
    """
    from app.api.v1 import processes as processes_api

    tenant, proc, _prop, _cli = _seed(db_session)
    db_session.commit()

    def _explode_envenenando_a_sessao(db, **_kw):
        # Reproduz a forma real: o erro vem do banco e deixa a transação
        # abortada — é isso que torna qualquer lazy-load subsequente fatal.
        with contextlib.suppress(Exception):
            db.execute(text("SELECT 1/0"))
        raise SQLAlchemyError("falha simulada no flush")

    monkeypatch.setattr(processes_api, "consolidate_process", _explode_envenenando_a_sessao,
                        raising=False)
    monkeypatch.setattr(
        "app.services.staging_consolidation.consolidate_process",
        _explode_envenenando_a_sessao,
    )

    email = db_session.query(User).filter_by(tenant_id=tenant.id).one().email
    h = _login(client, email)
    r = client.post(f"/api/v1/processes/{proc.id}/consolidar", json={}, headers=h)
    assert r.status_code == 500
    detalhe = r.json().get("detail", "")
    assert "NADA foi gravado" in detalhe, detalhe
    assert detalhe != "Internal Server Error"


# ---------------------------------------------------------------------------
# 3. área de RL é número e vai para coluna de número
# ---------------------------------------------------------------------------

def test_rl_declarada_do_car_grava_area_e_nao_status(db_session):
    """437,7632 é uma ÁREA. `rl_status` é `averbada|proposta|pendente|
    cancelada`. Antes o Hub exibia "Reserva Legal: 437,7632" como se fosse o
    estado da RL, e a ponte matrícula→imóvel disputava a mesma coluna."""
    tenant, proc, prop, _cli = _seed(db_session)
    car = _doc(db_session, tenant, proc, "car")
    _linha(db_session, tenant, proc, car, field_name="rl_declarada_ha", valor="437,7632",
           entidade="imovel", alvo="rl_area_ha", unidade="ha", aceita=True)
    db_session.commit()

    consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id)

    db_session.refresh(prop)
    assert prop.rl_area_ha == pytest.approx(437.7632)
    assert prop.rl_status is None


# ---------------------------------------------------------------------------
# 4. a decisão contém a linha que grava
# ---------------------------------------------------------------------------

def _matricula_3181_com_gravame(db_session):
    """A 3.181 como a extração real a produz: a certidão, os atos de gravame
    (sem destino individual — ADR-065) e a linha AGREGADA de ônus, que é quem
    escreve `matricula.onus_gravames`."""
    tenant, proc, prop, _cli = _seed(db_session)
    cert = _doc(db_session, tenant, proc, "matricula")
    _linha(db_session, tenant, proc, cert, field_name="numero_matricula", valor="3181",
           entidade="matricula", alvo="numero_matricula", hint="3181")
    _linha(db_session, tenant, proc, cert, field_name="observacao",
           valor="R-06 · Alienação fiduciária · 15/03/2021", hint="3181",
           tipo_obs="alienacao_fiduciaria",
           atributos={"ato": "R-06", "vigencia": "vigente"},
           field_value={"value": "R-06 · Alienação fiduciária · 15/03/2021",
                        "sem_destino": True,
                        "sem_destino_motivo": "gravame — entra na base pela linha de ônus"})
    _linha(db_session, tenant, proc, cert, field_name="onus",
           valor=[{"tipo": "Alienação fiduciária", "ato": "R-06"}],
           entidade="matricula", alvo="onus_gravames", hint="3181")
    _linha(db_session, tenant, proc, cert, field_name="proprietarios",
           valor="KARINA SANTAROSA CLEMENTE",
           entidade="matricula", alvo="proprietarios", hint="3181")
    _linha(db_session, tenant, proc, cert, field_name="observacao",
           valor="R-11 · Compra e venda · 12/03/2013", hint="3181",
           tipo_obs="compra_venda",
           atributos={"ato": "R-11", "adquirentes": ["KARINA SANTAROSA CLEMENTE"]},
           field_value={"value": "R-11 · Compra e venda · 12/03/2013", "sem_destino": True})
    db_session.commit()
    return tenant, proc, prop


def test_decisao_de_gravames_contem_a_linha_que_grava(db_session):
    tenant, proc, _prop = _matricula_3181_com_gravame(db_session)
    linhas = db_session.query(ExtractedFieldStaging).filter_by(process_id=proc.id).all()

    decisoes = {d.chave: d for d in build_decisions(linhas).decisoes}
    gravames = decisoes[("matricula", "3181", "gravames")]

    alvos = {
        r.target_field for r in linhas if r.id in gravames.staging_ids
    }
    assert "onus_gravames" in alvos, "a decisão de gravames não contém a linha que grava"
    # e a linha agregada aparece como evidência legível, não como "ato indeterminado"
    agregada = next(e for e in gravames.evidencias if e.campo == "ônus vigentes (o que vai para a base)")
    assert "1 vigente(s)" in str(agregada.valor_normalizado)


def test_decisao_de_titularidade_contem_proprietarios_e_o_mostra(db_session):
    """Membro que grava e não aparece seria escrita silenciosa: a consultora
    aceitaria "Titularidade" e um valor que ela nunca viu entraria na base."""
    tenant, proc, _prop = _matricula_3181_com_gravame(db_session)
    linhas = db_session.query(ExtractedFieldStaging).filter_by(process_id=proc.id).all()

    titularidade = next(d for d in build_decisions(linhas).decisoes
                        if d.chave == ("matricula", "3181", "titularidade"))
    alvos = {r.target_field for r in linhas if r.id in titularidade.staging_ids}
    assert "proprietarios" in alvos
    assert any(e.campo == "proprietários (como o documento lista)"
               for e in titularidade.evidencias)


def test_aceitar_gravames_e_titularidade_grava_de_verdade(db_session):
    """O fecho da Parte 1: decidir o FATO na tela põe o valor na base.

    Antes, `matricula.onus_gravames` e `matricula.proprietarios` só entravam
    por um segundo clique numa linha solta que a tela não liga ao mesmo fato —
    e a decisão ficava "decidida" para sempre.
    """
    tenant, proc, prop = _matricula_3181_com_gravame(db_session)

    for aspecto in ("composicao", "gravames", "titularidade"):
        decidir_decisao_agrupada(
            db_session, tenant_id=tenant.id, process_id=proc.id,
            chave=("matricula", "3181", aspecto), acao="aceitar",
        )
    consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id)

    db_session.refresh(prop)
    mat = next(m for m in prop.matriculas if m.numero_matricula == "3181")
    assert mat.onus_gravames, "gravames aceito e a coluna continuou vazia"
    assert mat.proprietarios, "titularidade aceita e a coluna continuou vazia"

    linhas = db_session.query(ExtractedFieldStaging).filter_by(process_id=proc.id).all()
    estados = {d.chave[2]: d.estado for d in build_decisions(linhas).decisoes}
    assert estados["gravames"] == "gravada", estados
    assert estados["titularidade"] == "gravada", estados


def test_decisao_sem_membro_que_pousa_fica_decidida_nao_gravada(db_session):
    """"Gravada" sem nada gravado seria a mentira ao contrário.

    Matrícula cujos gravames estão todos baixados não produz linha agregada:
    a decisão existe, é decidida, e não escreve — e é isso que ela deve dizer.
    """
    tenant, proc, _prop, _cli = _seed(db_session)
    cert = _doc(db_session, tenant, proc, "matricula")
    _linha(db_session, tenant, proc, cert, field_name="observacao",
           valor="R-06 · Hipoteca · baixada por AV.08", hint="3181", tipo_obs="hipoteca",
           atributos={"ato": "R-06", "vigencia": "baixado"},
           field_value={"value": "R-06 · Hipoteca · baixada por AV.08", "sem_destino": True})
    db_session.commit()

    decidir_decisao_agrupada(db_session, tenant_id=tenant.id, process_id=proc.id,
                             chave=("matricula", "3181", "gravames"), acao="aceitar")
    consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id)

    linhas = db_session.query(ExtractedFieldStaging).filter_by(process_id=proc.id).all()
    gravames = next(d for d in build_decisions(linhas).decisoes if d.chave[2] == "gravames")
    assert gravames.estado == "decidida"


# ---------------------------------------------------------------------------
# 5. o CAR não acusa ausência de matrícula que a certidão cria na mesma passagem
# ---------------------------------------------------------------------------

def test_matricula_criada_pela_certidao_nao_e_declarada_ausente_pelo_car(db_session):
    """A ordem era o defeito: o julgamento "esta matrícula existe?" rodava
    ANTES dos grupos, e a certidão criava a 3.181 poucas linhas depois. A
    resposta mandava a consultora cadastrar à mão o que o sistema acabara de
    cadastrar sozinho."""
    tenant, proc, prop, _cli = _seed(db_session)
    car = _doc(db_session, tenant, proc, "car")
    cert = _doc(db_session, tenant, proc, "matricula")
    _linha(db_session, tenant, proc, car, field_name="matricula_listada",
           valor={"numero": "3181"}, entidade="matricula", hint="3181", aceita=True)
    _linha(db_session, tenant, proc, cert, field_name="numero_matricula", valor="3181",
           entidade="matricula", alvo="numero_matricula", hint="3181", aceita=True)
    db_session.commit()

    res = consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id)

    assert res["matriculas_criadas"] == 1
    assert not [m for m in res["ignorados"] if "não está cadastrada" in m], res["ignorados"]
    # e a linha do CAR fica carimbada: ela confirmou o vínculo
    listada = db_session.query(ExtractedFieldStaging).filter_by(
        process_id=proc.id, field_name="matricula_listada").one()
    assert listada.consolidated_at is not None


def test_area_total_do_imovel_e_a_soma_das_matriculas(db_session):
    """O sintoma próprio do gate: `area_total_matriculas = 0.0` com matrícula
    criada. A área só entra quando a decisão `area` pousa `matricula.area_ha`."""
    tenant, proc, prop, _cli = _seed(db_session)
    cert_a = _doc(db_session, tenant, proc, "matricula")
    cert_b = _doc(db_session, tenant, proc, "matricula")
    for doc, numero, area in ((cert_a, "3181", "926,3654"), (cert_b, "3313", "725,4663")):
        _linha(db_session, tenant, proc, doc, field_name="numero_matricula", valor=numero,
               entidade="matricula", alvo="numero_matricula", hint=numero, aceita=True)
        _linha(db_session, tenant, proc, doc, field_name="area_registrada_ha", valor=area,
               entidade="matricula", alvo="area_ha", hint=numero, unidade="ha", aceita=True)
    db_session.commit()

    res = consolidate_process(db_session, tenant_id=tenant.id, process_id=proc.id)

    db_session.refresh(prop)
    assert res["area_total_matriculas"] == pytest.approx(1651.8317)
    assert prop.area_total_matriculas() == pytest.approx(926.3654 + 725.4663)


# ---------------------------------------------------------------------------
# 6. caso sem macroetapa não é mais um beco sem saída
# ---------------------------------------------------------------------------

def test_caso_sem_macroetapa_nasce_na_entrada_e_ganha_checklists(db_session):
    """O self-healing recusava justamente o caso que mais precisava dele.

    Medido no gate de navegador (12/09): processo criado fora do intake nasce
    com `macroetapa` NULA. O painel dizia "Etapa não iniciada (sem checklist)",
    não havia botão de avançar (não há próxima etapa a partir do nada) e
    NENHUM gesto da interface iniciava a etapa. A tela nomeava o problema e não
    oferecia a saída — e o backfill lazy que existe para curar caso legado saía
    por um `return False` na primeira linha.
    """
    from app.models.macroetapa import Macroetapa, MacroetapaChecklist
    from app.services.macroetapa_engine import ensure_macroetapa_checklists

    tenant, proc, _prop, _cli = _seed(db_session)
    proc.macroetapa = None
    db_session.flush()

    criou = ensure_macroetapa_checklists(db_session, proc, tenant.id)
    db_session.flush()

    assert criou is True
    assert proc.macroetapa == Macroetapa.entrada_demanda.value
    checklists = (
        db_session.query(MacroetapaChecklist)
        .filter(MacroetapaChecklist.process_id == proc.id)
        .all()
    )
    assert len(checklists) == len(Macroetapa)

    # Idempotente: a segunda passagem não cria nada nem mexe na etapa.
    assert ensure_macroetapa_checklists(db_session, proc, tenant.id) is False
    assert proc.macroetapa == Macroetapa.entrada_demanda.value
