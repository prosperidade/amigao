"""Regressão do guard ``seen_this_run`` em ``generate_acoes_from_divergencias``.

Gap medido no diagnóstico do Sprint 3: a ``dedupe_key`` da divergência deriva de
``f"{entity}|{hint}|{field}"`` com separador ingênuo — dois DESTINOS distintos
podem colidir na mesma string (ex.: ``hint="a|b", field="c"`` × ``hint="a",
field="b|c"``). Sem o guard intra-run, os dois ``Acao`` entravam no MESMO flush
com a mesma chave e ``uq_acoes_tenant_dedupe`` derrubava a consolidação inteira.
"""

from app.core.security import get_password_hash
from app.models.acao import Acao
from app.models.client import Client, ClientStatus, ClientType
from app.models.extracted_field_staging import (
    ExtractedFieldStaging,
    ExtractedFieldStatus,
)
from app.models.process import Process, ProcessStatus
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User
from app.services.acao_generator import generate_acoes_from_divergencias


def _setup(db_session):
    tenant = Tenant(name="Divg Tenant")
    db_session.add(tenant)
    db_session.flush()
    user = User(email="divg@example.com", full_name="C",
                hashed_password=get_password_hash("x12345"),
                tenant_id=tenant.id, is_active=True)
    cli = Client(tenant_id=tenant.id, full_name="Cliente", email="divg.c@example.com",
                 client_type=ClientType.pf, status=ClientStatus.active)
    db_session.add_all([user, cli])
    db_session.flush()
    prop = Property(tenant_id=tenant.id, client_id=cli.id, name="Fazenda")
    db_session.add(prop)
    db_session.flush()
    proc = Process(tenant_id=tenant.id, client_id=cli.id, property_id=prop.id,
                   title="Caso", process_type="prad", status=ProcessStatus.triagem)
    db_session.add(proc)
    db_session.flush()
    return tenant, proc


def _div(tenant_id, process_id, *, hint, field):
    return ExtractedFieldStaging(
        tenant_id=tenant_id, process_id=process_id, source_doc_type="matricula",
        field_name=field, field_value={"value": "123"},
        status=ExtractedFieldStatus.divergente_transcricao,
        target_entity="matricula", target_field=field, matricula_hint=hint,
        created_by_agent="extrator",
    )


def test_colisao_de_dedupe_key_intra_run_nao_estoura_constraint(db_session, monkeypatch):
    """Destinos distintos com dedupe_key colidente → 1 ação, sem IntegrityError.

    A colisão é FORÇADA aqui, em vez de construída com nomes de campo
    sintéticos. O teste original explorava o separador ingênuo do `sha1`:
    `("a|b", "c")` e `("a", "b|c")` produzem a mesma string `"matricula|a|b|c"`.
    Essa instância deixou de ser alcançável em 06/08 — divergência sobre campo
    sem destino na base não vira mais Ação (o caso `vtn`), e `c`/`b|c` não são
    colunas de `matriculas`.

    O guard continua necessário e continua coberto: a colisão do separador era
    só a forma mais FÁCIL de provocá-la; o `sha1` truncado em 24 hex pode
    colidir sozinho, e aí o `IntegrityError` derrubaria a consolidação inteira
    no flush. Forçar a chave isola o que o teste realmente vigia — dois destinos
    legítimos que resolvem para a mesma chave dão UMA ação, não uma exceção.
    """
    from app.services import acao_generator

    tenant, proc = _setup(db_session)
    # Dois destinos REAIS e distintos (colunas de `matriculas`, matrículas
    # diferentes) — o que a consolidação encontra em campo.
    db_session.add_all([
        _div(tenant.id, proc.id, hint="4.698", field="area_ha"),
        _div(tenant.id, proc.id, hint="6.776", field="cartorio"),
    ])
    db_session.flush()

    monkeypatch.setattr(
        acao_generator, "_dedupe_key_divergencia",
        lambda process_id, entity, hint, field: f"p{process_id}:divg:colisao",
    )

    _created, n = generate_acoes_from_divergencias(db_session, process=proc, tenant_id=tenant.id)
    db_session.commit()  # sem o guard, o flush do commit estourava a UNIQUE

    assert n == 1
    keys = [a.dedupe_key for a in db_session.query(Acao).filter(Acao.process_id == proc.id)]
    assert len(keys) == len(set(keys)) == 1


def test_divergencia_sem_destino_na_base_nao_vira_acao(db_session):
    """O caso `vtn` (Ação id 49, produção): trabalho que ninguém pode fazer.

    Campo sem coluna e fora da allowlist não gera Ação — nenhuma escolha de
    fonte mudaria o resultado. Campo com destino no MESMO lote continua gerando,
    para a correção não virar um novo sumiço.
    """
    tenant, proc = _setup(db_session)
    db_session.add_all([
        _div(tenant.id, proc.id, hint="2.923", field="vtn"),
        _div(tenant.id, proc.id, hint="2.923", field="area_ha"),
    ])
    db_session.flush()

    _created, n = generate_acoes_from_divergencias(db_session, process=proc, tenant_id=tenant.id)
    db_session.commit()

    assert n == 1
    titulos = [a.titulo for a in db_session.query(Acao).filter(Acao.process_id == proc.id)]
    assert not any("vtn" in t.lower() for t in titulos), titulos


def test_idempotencia_entre_runs_preservada(db_session):
    tenant, proc = _setup(db_session)
    db_session.add(_div(tenant.id, proc.id, hint="4.698", field="area_ha"))
    db_session.flush()

    _, n1 = generate_acoes_from_divergencias(db_session, process=proc, tenant_id=tenant.id)
    db_session.commit()
    _, n2 = generate_acoes_from_divergencias(db_session, process=proc, tenant_id=tenant.id)
    db_session.commit()

    assert n1 == 1
    assert n2 == 0


def test_normalize_fontes_tolerante_a_entrada_malformada():
    """Fonte malformada vira ``sem_fonte`` legível; lista vazia nunca silencia."""
    from app.services.acao_generator import _normalize_fontes

    out = _normalize_fontes(
        [{"tipo": "documento", "ref": "doc:1"}, {"tipo": "tipo_inexistente"}, "string solta"],
        passivo_desc="Área diverge",
    )
    assert out[0]["tipo"] == "documento"
    assert out[1]["tipo"] == "sem_fonte" and out[1]["sem_fonte"] is True

    vazio = _normalize_fontes([], passivo_desc="Área diverge")
    assert len(vazio) == 1
    assert vazio[0]["tipo"] == "sem_fonte"
    assert "Área diverge" in (vazio[0]["descricao"] or "")
