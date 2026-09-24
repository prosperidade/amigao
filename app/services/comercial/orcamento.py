"""Orçamento derivado da Rota validada (ADR-074 §4–§5).

Um item por passo vivo, validado e ``item_proposta``. O método de cada item vem, nesta
ordem, da escolha do consultor para aquele passo, do método do tenant mapeado à regra que
originou o passo, ou do método padrão do tenant. Sem método padrão: recusa honesta — nunca
preço de código. Totais em ``Decimal``: quantidade × valor unitário, a centavos; o consultor
muda método e quantidade, nunca digita total.

Método: ``app/skills/orcamento/orcamento_da_rota/SKILL.md`` (manifesto da cadeia).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.audit_log import AuditLog
from app.models.comercial import Orcamento, OrcamentoEscolha, OrcamentoItem, OrcamentoMetodo, RedacaoComercial
from app.models.motor_juridico import AvaliacaoRegra, Regra, RegraVersao
from app.models.process import Process
from app.models.rota import RotaPasso, RotaPassoClassificacao, RotaPassoStatus
from app.models.zona_normativa import Dispositivo
from app.services.audit_hash import stamp_audit_hash
from app.services.comercial import ComercialError
from app.services.comercial import base as base_mod

logger = get_logger(__name__)

CENTAVO = Decimal("0.01")
_UNIDADE = {"hora": "h", "unidade": "un", "fixo": "×"}


def _brl(v: Decimal) -> str:
    inteiro, _, frac = f"{v.quantize(CENTAVO):.2f}".partition(".")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    return "R$ " + ".".join(grupos) + "," + frac


def _qtd(q: Decimal) -> str:
    return f"{q.normalize():f}".replace(".", ",")


def auditar(db: Session, *, tenant_id: int, user_id: int | None, entidade: str, entidade_id: int,
            acao: str, detalhe: str, novo: str | None = None) -> None:
    log = AuditLog(tenant_id=tenant_id, user_id=user_id, entity_type=entidade, entity_id=entidade_id,
                   action=acao, new_value=novo, details=detalhe)
    db.add(log)
    db.flush()
    stamp_audit_hash(db, log)


# ---------------------------------------------------------------------------
# Métodos e preços do tenant
# ---------------------------------------------------------------------------

def metodos_correntes(db: Session, tenant_id: int) -> dict[str, OrcamentoMetodo]:
    """A versão mais nova de cada código; inativos ficam de fora."""
    out: dict[str, OrcamentoMetodo] = {}
    for m in (db.query(OrcamentoMetodo).filter(OrcamentoMetodo.tenant_id == tenant_id)
              .order_by(OrcamentoMetodo.codigo, OrcamentoMetodo.versao)):
        out[m.codigo] = m
    return {c: m for c, m in out.items() if m.ativo}


def criar_versao_metodo(db: Session, *, tenant_id: int, user_id: int, codigo: str, nome: str, unidade: str,
                        valor_unitario: Decimal, quantidade_padrao: Decimal, rule_ids: list[str],
                        padrao: bool, ativo: bool = True) -> OrcamentoMetodo:
    """Cria o método ou a versão nova dele. Nada se edita no lugar: o item antigo guarda a foto."""
    codigo = codigo.strip()
    if not codigo:
        raise ComercialError("Código do método é obrigatório.")
    if unidade not in _UNIDADE:
        raise ComercialError(f"Unidade inválida: {unidade}. Use hora, fixo ou unidade.")
    if unidade == "fixo" and Decimal(quantidade_padrao) != 1:
        raise ComercialError("Método de valor fixo tem quantidade 1.")
    if padrao and ativo:
        outro = next((m for c, m in metodos_correntes(db, tenant_id).items() if m.padrao and c != codigo), None)
        if outro is not None:
            raise ComercialError(f"O método \"{outro.codigo}\" já é o padrão do tenant: crie a versão dele "
                                 "com padrão desligado antes.")
    anterior = (db.query(OrcamentoMetodo).filter(OrcamentoMetodo.tenant_id == tenant_id,
                                                 OrcamentoMetodo.codigo == codigo)
                .order_by(OrcamentoMetodo.versao.desc()).first())
    m = OrcamentoMetodo(tenant_id=tenant_id, codigo=codigo, versao=(anterior.versao + 1) if anterior else 1,
                        nome=nome.strip(), unidade=unidade, valor_unitario=Decimal(valor_unitario).quantize(CENTAVO),
                        quantidade_padrao=Decimal(quantidade_padrao), rule_ids=sorted(set(rule_ids)),
                        padrao=padrao, ativo=ativo, criado_por_id=user_id)
    db.add(m)
    db.flush()
    auditar(db, tenant_id=tenant_id, user_id=user_id, entidade="orcamento_metodo", entidade_id=m.id,
            acao="orcamento_metodo_versao", novo=f"{codigo} v{m.versao}",
            detalhe=f"{m.nome} · {m.unidade} · {_brl(m.valor_unitario)} · padrão={m.padrao} · ativo={m.ativo}")
    return m


# ---------------------------------------------------------------------------
# Geração
# ---------------------------------------------------------------------------

def _rule_id_do_passo(db: Session, passo: RotaPasso) -> str | None:
    if not passo.origem_avaliacao_id:
        return None
    return (db.query(Regra.rule_id)
            .join(RegraVersao, RegraVersao.regra_id == Regra.id)
            .join(AvaliacaoRegra, AvaliacaoRegra.regra_versao_id == RegraVersao.id)
            .filter(AvaliacaoRegra.id == passo.origem_avaliacao_id).scalar())


def _escolher_metodo(metodos: dict[str, OrcamentoMetodo], escolha: OrcamentoEscolha | None,
                     rule_id: str | None) -> tuple[OrcamentoMetodo, str]:
    if escolha is not None and escolha.metodo_codigo:
        m = metodos.get(escolha.metodo_codigo)
        if m is None:
            raise ComercialError(f"O método escolhido \"{escolha.metodo_codigo}\" não existe ou está inativo.")
        return m, "consultor"
    if rule_id:
        por_regra = [m for c, m in sorted(metodos.items()) if rule_id in (m.rule_ids or [])]
        if por_regra:
            return por_regra[0], "regra"
    padrao = [m for m in metodos.values() if m.padrao]
    if not padrao:
        raise ComercialError("O tenant não tem método padrão de orçamento: cadastre os métodos e preços "
                             "(um deles como padrão) antes de orçar.")
    return padrao[0], "padrao"


def _calculo(m: OrcamentoMetodo, q: Decimal, total: Decimal, qtd_consultor: bool) -> str:
    sufixo = " (quantidade do consultor)" if qtd_consultor else ""
    if m.unidade == "fixo":
        return f"valor fixo {_brl(m.valor_unitario)}{sufixo}"
    return f"{_qtd(q)} {_UNIDADE[m.unidade]} × {_brl(m.valor_unitario)} = {_brl(total)}{sufixo}"


def escopo_aprovado_atual(db: Session, tenant_id: int, process_id: int) -> RedacaoComercial:
    escopo = base_mod.ultima_redacao(db, tenant_id, process_id, "especificacao_escopo")
    if escopo is None:
        raise ComercialError("Especificação de escopo ausente: gere o relatório preliminar e o escopo a partir "
                             "da Rota validada.")
    if escopo.estado_revisao != "aprovada":
        raise ComercialError(f"A especificação de escopo v{escopo.versao} ainda não foi aprovada pelo consultor.")
    atual = base_mod.atualidade(db, escopo)
    if atual["estado"] != "vigente":
        raise ComercialError(f"A especificação de escopo v{escopo.versao} está desatualizada: "
                             + "; ".join(atual["motivos"]) + ". Gere o escopo de novo.")
    return escopo


def gerar(db: Session, *, process: Process, tenant_id: int, user_id: int | None) -> Orcamento:
    from app.services.evidence import lock_case  # noqa: PLC0415

    lock_case(db, tenant_id, process.id)
    escopo = escopo_aprovado_atual(db, tenant_id, process.id)
    rotas = base_mod.rotas_validadas(db, tenant_id, process.id)
    if not rotas:
        raise ComercialError("Rota validada ausente: o orçamento nasce da Rota.")
    metodos = metodos_correntes(db, tenant_id)
    if not metodos:
        raise ComercialError("O tenant não tem métodos de orçamento cadastrados.")
    escolhas = {e.rota_passo_id: e for e in db.query(OrcamentoEscolha).filter(
        OrcamentoEscolha.tenant_id == tenant_id, OrcamentoEscolha.process_id == process.id)}

    itens: list[OrcamentoItem] = []
    fora: list[dict] = []
    for rota in rotas:
        for p in rota.passos:
            if p.status != RotaPassoStatus.validado:
                continue
            if p.classificacao != RotaPassoClassificacao.item_proposta:
                fora.append({"rota_passo_id": p.id, "titulo": p.titulo, "motivo": "orientação (direção), não cobrada"})
                continue
            escolha = escolhas.get(p.id)
            metodo, origem = _escolher_metodo(metodos, escolha, _rule_id_do_passo(db, p))
            qtd_consultor = escolha is not None and escolha.quantidade is not None
            q = Decimal(1) if metodo.unidade == "fixo" else (
                Decimal(escolha.quantidade) if qtd_consultor else Decimal(metodo.quantidade_padrao))
            vu = Decimal(metodo.valor_unitario)
            total = (q * vu).quantize(CENTAVO, rounding=ROUND_HALF_UP)
            disp = db.get(Dispositivo, p.fundamento_dispositivo_id) if p.fundamento_dispositivo_id else None
            itens.append(OrcamentoItem(
                tenant_id=tenant_id, rota_passo_id=p.id, metodo_id=metodo.id, escolha=origem,
                ordem=len(itens) + 1, descricao=p.titulo,
                fundamento={"dispositivo_id": p.fundamento_dispositivo_id,
                            "fonte_versao_id": p.fundamento_fonte_versao_id,
                            "caminho": disp.caminho if disp else None,
                            "rule_id": _rule_id_do_passo(db, p)},
                unidade=metodo.unidade, quantidade=q, valor_unitario=vu, total=total,
                calculo=_calculo(metodo, q, total, qtd_consultor and metodo.unidade != "fixo")))
        for p in rota.passos_removidos:
            fora.append({"rota_passo_id": p.id, "titulo": p.titulo,
                         "motivo": f"removido da Rota: {base_mod.motivo_remocao(db, p)}"})
    if not itens:
        raise ComercialError("A Rota validada não tem passo validado classificado como item de proposta.")

    anterior = base_mod.ultimo_orcamento(db, tenant_id, process.id)
    agora = datetime.now(UTC)
    if anterior is not None and anterior.superada_em is None:
        anterior.superada_em = agora
    codigos = sorted({db.get(OrcamentoMetodo, i.metodo_id).codigo for i in itens})
    base = base_mod.base_orcamento(db, tenant_id, process.id, escopo, codigos)
    diag = base["diagnostico"]
    o = Orcamento(tenant_id=tenant_id, process_id=process.id, versao=(anterior.versao + 1) if anterior else 1,
                  rota_id=rotas[0].id if len(rotas) == 1 else None, escopo_id=escopo.id,
                  total=sum((i.total for i in itens), Decimal(0)), fora=fora,
                  ressalvas=base_mod.ressalvas_do_diagnostico(diag), base=base,
                  base_hash=base_mod.hash_base(base), criado_por_id=user_id, created_at=agora, itens=itens)
    db.add(o)
    db.flush()
    auditar(db, tenant_id=tenant_id, user_id=user_id, entidade="orcamento", entidade_id=o.id,
            acao="orcamento_gerado", novo=f"v{o.versao} · {_brl(o.total)}",
            detalhe=f"processo {process.id} · escopo v{escopo.versao} · itens {len(itens)} · fora {len(fora)}")
    logger.info("comercial_orcamento_gerado", extra={"process_id": process.id, "tenant_id": tenant_id,
                                                     "orcamento_id": o.id, "total": str(o.total)})
    return o


def escolher(db: Session, *, process: Process, tenant_id: int, user_id: int, rota_passo_id: int,
             metodo_codigo: str | None, quantidade: Decimal | None) -> OrcamentoEscolha:
    """A escolha do consultor para um passo; vale para esta e as próximas versões."""
    passo = (db.query(RotaPasso).filter(RotaPasso.id == rota_passo_id, RotaPasso.tenant_id == tenant_id,
                                        RotaPasso.deleted_at.is_(None)).first())
    if passo is None or passo.rota.process_id != process.id:
        raise LookupError("Passo não encontrado neste caso")
    if metodo_codigo is not None and metodo_codigo not in metodos_correntes(db, tenant_id):
        raise ComercialError(f"Método \"{metodo_codigo}\" não existe ou está inativo.")
    if quantidade is not None and Decimal(quantidade) <= 0:
        raise ComercialError("Quantidade precisa ser maior que zero.")
    e = (db.query(OrcamentoEscolha).filter(OrcamentoEscolha.tenant_id == tenant_id,
                                           OrcamentoEscolha.rota_passo_id == rota_passo_id).first())
    if e is None:
        e = OrcamentoEscolha(tenant_id=tenant_id, process_id=process.id, rota_passo_id=rota_passo_id,
                             autor_id=user_id)
        db.add(e)
    e.metodo_codigo, e.quantidade, e.autor_id = metodo_codigo, quantidade, user_id
    db.flush()
    auditar(db, tenant_id=tenant_id, user_id=user_id, entidade="orcamento_escolha", entidade_id=e.id,
            acao="orcamento_escolha", novo=f"{metodo_codigo or '—'} · {quantidade or '—'}",
            detalhe=f"processo {process.id} · passo {rota_passo_id}")
    return e


# ---------------------------------------------------------------------------
# Revisão (redação e orçamento)
# ---------------------------------------------------------------------------

def revisar(db: Session, artefato, *, user_id: int, acao: str, justificativa: str) -> None:
    """Aprovar ou rejeitar a versão vigente. Aprovar exige a versão ATUAL."""
    justificativa = (justificativa or "").strip()
    if acao not in ("aprovar", "rejeitar"):
        raise ComercialError("Ação de revisão: aprovar ou rejeitar.")
    if not justificativa:
        raise ComercialError("Revisão exige justificativa.")
    if artefato.superada_em is not None:
        raise ComercialError(f"A versão {artefato.versao} foi superada; revise a mais nova.")
    if acao == "aprovar":
        atual = base_mod.atualidade(db, artefato)
        if atual["estado"] != "vigente":
            raise ComercialError("Versão desatualizada não se aprova: " + "; ".join(atual["motivos"]))
    artefato.estado_revisao = "aprovada" if acao == "aprovar" else "rejeitada"
    artefato.revisado_por_id = user_id
    artefato.revisado_em = datetime.now(UTC)
    artefato.justificativa = justificativa
    db.flush()
    entidade = "orcamento" if isinstance(artefato, Orcamento) else "redacao_comercial"
    auditar(db, tenant_id=artefato.tenant_id, user_id=user_id, entidade=entidade, entidade_id=artefato.id,
            acao=f"{entidade}_{artefato.estado_revisao}", novo=artefato.estado_revisao,
            detalhe=f"v{artefato.versao} · {justificativa}")
