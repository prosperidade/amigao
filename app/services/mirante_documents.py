"""Geração de PROPOSTA e CONTRATO nos moldes Mirante (S5-B).

Consolida a geração das peças comerciais numa fonte ÚNICA e DETERMINÍSTICA
(nada de LLM inventando número): a proposta nasce da Rota validada + precificação
(S5-A), o contrato nasce da proposta ACEITA. Substitui o preenchimento textual do
gerador legado (``contract_generator.fill_contract_template``) para o caminho com
proposta — as validações de consistência exigem determinismo e bloqueio honesto.

Estruturas destiladas dos documentos reais da Mirante (ver
``docs/templates/PROPOSTA_MIRANTE.md`` e ``docs/templates/CONTRATO_MIRANTE.md``):

  PROPOSTA (6 seções): 1.Caracterização · 2.Objetivo · 3.O que será feito (passos
  da Rota, rastreáveis via ``rota_passo_id``) · 4.Entregáveis · 5.Investimento ·
  6.Condições Comerciais + assinatura do responsável técnico.

  CONTRATO (8 cláusulas): 1ª Objeto (bloco: imóvel+matrículas, serviços, valores)
  · 2ª Valor e Pagamento (parcelas + banco) · 3ª–8ª boilerplate parametrizado
  (obrigações, rescisão, vigência, disposições, foro + assinaturas/testemunhas).

VALIDAÇÕES DE CONSISTÊNCIA (a classe de erro real dos contratos manuais):
  1. soma dos valores dos serviços == total declarado da proposta;
  2. soma das parcelas == total do bloco (cláusula 2ª == cláusula 1ª);
  3. matrículas citadas existem e são VIGENTES no caso.
Violação = geração BLOQUEADA (``DocumentConsistencyError`` → HTTP 422).

GUARD de placeholder: nenhum ``{{...}}`` ou ``[12]`` sai no documento final
(``PlaceholderUnresolvedError``) — como acontecia nos contratos manuais.

IA propõe, humano decide: o gerado é RASCUNHO (``needs_human_validation=True``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.process import Process
from app.models.property import Property
from app.models.proposal import Proposal, ProposalStatus
from app.models.tenant import Tenant
from app.services.proposal_generator import PRICE_TABLE
from app.services.tenant_profile import (
    IssuerProfile,
    load_issuer_profile,
    missing_issuer_fields,
)

# ---------------------------------------------------------------------------
# Exceções — todas viram HTTP 422 no endpoint (bloqueio honesto)
# ---------------------------------------------------------------------------

class DocumentGenerationError(Exception):
    """Base — geração bloqueada com mensagem honesta para o consultor."""


class DocumentConsistencyError(DocumentGenerationError):
    """Uma das 3 validações de consistência falhou (dinheiro ou vigência)."""


class PlaceholderUnresolvedError(DocumentGenerationError):
    """Campo obrigatório ausente ou token não resolvido — nunca sai ``[12]``."""


_NAO_INFORMADO = "Não informado"


# ---------------------------------------------------------------------------
# Helpers de dinheiro (comparação em CENTAVOS — nunca compara float direto)
# ---------------------------------------------------------------------------

def _cents(v: Any) -> int:
    return int(round(float(v or 0) * 100))


def fmt_brl(v: Any) -> str:
    """Formata em R$ 1.234,56 (padrão brasileiro)."""
    if v is None:
        return "R$ 0,00"
    try:
        return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(v)


# ---------------------------------------------------------------------------
# Validações de consistência (puras — testadas isoladamente)
# ---------------------------------------------------------------------------

def validate_scope_totals(scope_items: list[dict], total_value: Optional[float]) -> float:
    """(1) soma dos valores dos serviços == total declarado da proposta.

    Retorna a soma. Bloqueia se o total declarado divergir da soma dos itens.
    Total declarado None é tolerado (a soma vira a fonte)."""
    soma = sum(float(it.get("total") or 0) for it in scope_items)
    if total_value is not None and _cents(soma) != _cents(total_value):
        raise DocumentConsistencyError(
            f"Inconsistência de valores: a soma dos serviços ({fmt_brl(soma)}) não "
            f"confere com o total declarado da proposta ({fmt_brl(total_value)}). "
            "Corrija os valores dos itens ou o total antes de gerar a peça."
        )
    return round(soma, 2)


def validate_installments(installments: list[dict], expected_total: float) -> float:
    """(2) soma das parcelas == total do bloco (cláusula 2ª == cláusula 1ª).

    Retorna a soma das parcelas. Bloqueia se divergir do total esperado."""
    soma = sum(float(p.get("valor") or 0) for p in installments)
    if _cents(soma) != _cents(expected_total):
        raise DocumentConsistencyError(
            f"Inconsistência de parcelas: a soma das parcelas ({fmt_brl(soma)}) não "
            f"confere com o total do bloco ({fmt_brl(expected_total)}). As parcelas "
            "da cláusula 2ª devem somar exatamente a tabela de valores da cláusula 1ª."
        )
    return round(soma, 2)


def validate_matriculas_vigentes(matriculas: list[Any]) -> None:
    """(3) matrículas citadas existem e são VIGENTES no caso.

    Bloqueia se não houver nenhuma matrícula vigente, ou se alguma matrícula
    citada estiver histórica/desativada (uma ficha superada não pode fundamentar
    o objeto do contrato)."""
    if not matriculas:
        raise DocumentConsistencyError(
            "Nenhuma matrícula vigente no imóvel: o contrato precisa citar ao menos "
            "uma matrícula vigente. Cadastre/valide a matrícula na Conferência antes "
            "de gerar o contrato."
        )
    nao_vigentes = [
        (getattr(m, "numero_matricula", None) or f"id={getattr(m, 'id', '?')}")
        for m in matriculas
        if not getattr(m, "is_vigente", False)
    ]
    if nao_vigentes:
        raise DocumentConsistencyError(
            "Matrícula(s) não vigente(s) citada(s) no contrato: "
            f"{', '.join(nao_vigentes)}. Uma ficha histórica/superada não pode "
            "fundamentar o objeto — cite apenas matrículas vigentes."
        )


# ---------------------------------------------------------------------------
# Guard de placeholder — nenhum {{...}} ou [12] no documento final
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{\{|\}\}|\[\d+\]")


def assert_resolved(text: str) -> None:
    """Bloqueia se sobrar token não resolvido (``{{...}}`` ou ``[12]``)."""
    hit = _PLACEHOLDER_RE.search(text)
    if hit:
        raise PlaceholderUnresolvedError(
            f"Documento com placeholder não resolvido ('{hit.group()}'): a geração "
            "foi bloqueada para não emitir uma peça com campo em branco. Complete os "
            "dados de origem (perfil do tenant, escopo ou valores)."
        )


# ---------------------------------------------------------------------------
# Estruturas dos documentos (dicts serializáveis → content_data da Saída)
# ---------------------------------------------------------------------------

@dataclass
class PropostaDoc:
    numero: str
    data: str
    tenant_razao_social: str
    tenant_cnpj: str
    cliente_nome: str
    imovel_nome: str
    caracterizacao: dict           # localizacao/area/uso_atual/situacao_fundiaria/historico/necessidade
    objetivo: str
    etapas: list[dict]             # [{ordem, titulo, descricao, rota_passo_id, norma_ref, prazo_dias}]
    entregaveis: list[str]
    investimento: dict             # {total, total_formatado, forma_pagamento, parcelas:[{numero,vencimento,valor,valor_formatado}]}
    condicoes: dict                # {prazo_execucao, validade, limitacoes_escopo}
    assinatura: dict               # {nome, titulo, crea, razao_social}

    def to_content_data(self) -> dict:
        return {
            "kind": "proposta_mirante",
            "numero": self.numero,
            "data": self.data,
            "tenant": {"razao_social": self.tenant_razao_social, "cnpj": self.tenant_cnpj},
            "cliente": self.cliente_nome,
            "imovel": self.imovel_nome,
            "caracterizacao": self.caracterizacao,
            "objetivo": self.objetivo,
            "etapas": self.etapas,
            "entregaveis": self.entregaveis,
            "investimento": self.investimento,
            "condicoes": self.condicoes,
            "assinatura": self.assinatura,
        }


@dataclass
class ContratoDoc:
    data_local: str
    contratada: dict               # {razao_social, cnpj, endereco}
    contratante: dict              # {nome, qualificacao, cpf_cnpj}
    bloco: dict                    # {imovel, matriculas:[str], servicos:[{numero,descricao,valor,valor_formatado}], total, total_formatado, parcelas:[...]}
    banco: dict                    # {nome, agencia, conta, titular, pix}
    condicoes: dict                # {foro, prazo_execucao, vigencia, multa_percentual, rescisao_notificacao_dias, bonus_malus:{ativo,percentual}}
    assinatura: dict               # {rt_nome, rt_titulo, rt_crea}

    def to_content_data(self) -> dict:
        return {
            "kind": "contrato_mirante",
            "data_local": self.data_local,
            "contratada": self.contratada,
            "contratante": self.contratante,
            "bloco": self.bloco,
            "banco": self.banco,
            "condicoes": self.condicoes,
            "assinatura": self.assinatura,
        }


# ---------------------------------------------------------------------------
# Carregamento de contexto do caso
# ---------------------------------------------------------------------------

def _demand_label(process: Optional[Process]) -> Optional[str]:
    if process is None or process.demand_type is None:
        return None
    dt = process.demand_type.value
    info = PRICE_TABLE.get(dt)
    return info["name"] if info else dt.replace("_", " ")


def _load_context(db: Session, proposal: Proposal) -> tuple[Tenant, Client, Optional[Process], Optional[Property]]:
    tenant = db.query(Tenant).filter(Tenant.id == proposal.tenant_id).first()
    client = db.query(Client).filter(Client.id == proposal.client_id).first()
    process: Optional[Process] = None
    prop: Optional[Property] = None
    if proposal.process_id:
        process = db.query(Process).filter(Process.id == proposal.process_id).first()
        if process and process.property_id:
            prop = db.query(Property).filter(Property.id == process.property_id).first()
    if tenant is None:
        raise PlaceholderUnresolvedError("Tenant da proposta não encontrado.")
    if client is None:
        raise PlaceholderUnresolvedError("Cliente da proposta não encontrado.")
    return tenant, client, process, prop


def _require_profile(tenant: Tenant) -> IssuerProfile:
    profile = load_issuer_profile(tenant)
    missing = missing_issuer_fields(profile)
    if missing:
        raise PlaceholderUnresolvedError(
            "Perfil do tenant incompleto — a peça não pode ser assinada sem: "
            + "; ".join(missing)
            + ". Complete os dados institucionais do tenant (Configurações) antes de gerar."
        )
    return profile


def _matriculas_vigentes(prop: Optional[Property]) -> list[Any]:
    if prop is None:
        return []
    fn = getattr(prop, "matriculas_vigentes", None)
    if callable(fn):
        return list(fn())
    # fallback tolerante a mocks: filtra por is_vigente
    return [m for m in getattr(prop, "matriculas", []) if getattr(m, "is_vigente", False)]


def _caracterizacao(prop: Optional[Property], process: Optional[Process], matriculas: list[Any]) -> dict:
    if prop is None:
        localizacao = area = uso = situacao = _NAO_INFORMADO
    else:
        muni, uf = (prop.municipality or "").strip(), (prop.state or "").strip()
        localizacao = " / ".join([p for p in (muni, uf) if p]) or _NAO_INFORMADO
        area_ha = None
        get_area = getattr(prop, "area_total_matriculas", None)
        if callable(get_area):
            area_ha = get_area()
        if not area_ha:
            area_ha = prop.total_area_ha
        area = f"{area_ha:.4f} ha".replace(".", ",") if area_ha else "Área não informada"
        uso = (prop.tipologia or "").strip() or _NAO_INFORMADO
        nums = [getattr(m, "numero_matricula", None) for m in matriculas]
        nums = [n for n in nums if n]
        if nums:
            situacao = "Matrícula(s) " + ", ".join(nums)
        elif prop.registry_number:
            situacao = f"Matrícula {prop.registry_number}"
        else:
            situacao = _NAO_INFORMADO
    necessidade = _NAO_INFORMADO
    if process is not None:
        necessidade = (_demand_label(process) or (process.title or "").strip() or _NAO_INFORMADO)
    return {
        "localizacao": localizacao,
        "area": area,
        "uso_atual": uso,
        "situacao_fundiaria": situacao,
        "historico": _NAO_INFORMADO,
        "necessidade": necessidade,
    }


def _synth_installments(installments: list[dict], total: float) -> list[dict]:
    """Parcelas estruturadas; vazio → uma parcela única à vista (soma trivial)."""
    if installments:
        return [
            {
                "numero": p.get("numero", i + 1),
                "vencimento": p.get("vencimento") or "A combinar",
                "valor": round(float(p.get("valor") or 0), 2),
                "valor_formatado": fmt_brl(p.get("valor")),
            }
            for i, p in enumerate(installments)
        ]
    return [{
        "numero": 1,
        "vencimento": "Na assinatura",
        "valor": round(float(total), 2),
        "valor_formatado": fmt_brl(total),
    }]


# ---------------------------------------------------------------------------
# BUILD — PROPOSTA (nasce da Rota + precificação; S5-A alimenta o escopo)
# ---------------------------------------------------------------------------

def build_proposta(db: Session, proposal: Proposal, *, data: Optional[datetime] = None) -> PropostaDoc:
    tenant, client, process, prop = _load_context(db, proposal)
    profile = _require_profile(tenant)

    scope_items = list(proposal.scope_items or [])
    if not scope_items:
        raise PlaceholderUnresolvedError(
            "Proposta sem itens de escopo: gere a partir da Rota validada (E5) antes "
            "de emitir a peça."
        )
    # (1) consistência de valores (também vale na proposta)
    soma = validate_scope_totals(scope_items, proposal.total_value)
    total = proposal.total_value if proposal.total_value is not None else soma

    matriculas = _matriculas_vigentes(prop)
    caracterizacao = _caracterizacao(prop, process, matriculas)

    imovel_nome = (prop.name if prop else None) or (process.title if process else None) or "Imóvel"
    demanda = _demand_label(process) or "regularização ambiental"
    objetivo = (
        f"Prestação de serviços de {demanda.lower()} referentes ao imóvel "
        f"{imovel_nome}, contemplando as etapas e entregáveis detalhados nesta proposta."
    )

    etapas: list[dict] = []
    entregaveis: list[str] = []
    prazo_max = 0
    for idx, it in enumerate(scope_items, start=1):
        titulo = (it.get("description") or "").strip() or f"Etapa {idx}"
        etapas.append({
            "ordem": idx,
            "titulo": titulo,
            "descricao": (it.get("detail") or "").strip() or titulo,
            "rota_passo_id": it.get("rota_passo_id"),
            "norma_ref": it.get("norma_ref"),
            "prazo_dias": it.get("prazo_dias"),
        })
        entregaveis.append(titulo)
        if it.get("prazo_dias"):
            prazo_max = max(prazo_max, int(it["prazo_dias"]))

    installments = _synth_installments(list(proposal.payment_installments or []), total)
    investimento = {
        "total": round(float(total), 2),
        "total_formatado": fmt_brl(total),
        "forma_pagamento": (proposal.payment_terms or "").strip() or "A combinar entre as partes.",
        "parcelas": installments,
    }

    validade_dias = proposal.validity_days or profile.validade_proposta_dias
    prazo_exec = profile.prazo_execucao or (f"{prazo_max} dias corridos" if prazo_max else "conforme cronograma acordado com o cliente")
    condicoes = {
        "prazo_execucao": prazo_exec,
        "validade": f"{validade_dias} dias a partir da data de emissão",
        "limitacoes_escopo": (
            "Não inclui taxas de órgãos públicos, custas cartorárias nem serviços de "
            "terceiros, salvo quando expressamente previsto no escopo acima."
        ),
    }

    now = data or datetime.now(UTC)
    return PropostaDoc(
        numero=f"PROP-{proposal.id:04d}/{now.year}",
        data=now.strftime("%d/%m/%Y"),
        tenant_razao_social=profile.razao_social,
        tenant_cnpj=profile.cnpj,
        cliente_nome=client.full_name or _NAO_INFORMADO,
        imovel_nome=imovel_nome,
        caracterizacao=caracterizacao,
        objetivo=objetivo,
        etapas=etapas,
        entregaveis=entregaveis,
        investimento=investimento,
        condicoes=condicoes,
        assinatura={
            "nome": profile.rt_nome,
            "titulo": profile.rt_titulo,
            "crea": profile.rt_crea,
            "razao_social": profile.razao_social,
        },
    )


# ---------------------------------------------------------------------------
# BUILD — CONTRATO (nasce da PROPOSTA ACEITA; bloco único; ADR-029)
# ---------------------------------------------------------------------------

def build_contrato(
    db: Session,
    proposal: Proposal,
    *,
    bonus_malus_ativo: Optional[bool] = None,
    data: Optional[datetime] = None,
) -> ContratoDoc:
    if proposal.status != ProposalStatus.accepted:
        raise DocumentGenerationError(
            "O contrato nasce de uma proposta ACEITA. Estado atual: "
            f"'{proposal.status.value}'. Registre o aceite da proposta antes de gerar "
            "o contrato."
        )
    tenant, client, process, prop = _load_context(db, proposal)
    profile = _require_profile(tenant)

    scope_items = list(proposal.scope_items or [])
    if not scope_items:
        raise PlaceholderUnresolvedError("Proposta aceita sem itens de escopo — não há objeto para o contrato.")

    # (3) matrículas vigentes — bloco único do processo corrente
    matriculas = _matriculas_vigentes(prop)
    validate_matriculas_vigentes(matriculas)
    matriculas_nums = [getattr(m, "numero_matricula", None) or f"(id {getattr(m, 'id', '?')})" for m in matriculas]

    # (1) serviços == total declarado (cláusula 1ª)
    soma_servicos = validate_scope_totals(scope_items, proposal.total_value)
    bloco_total = proposal.total_value if proposal.total_value is not None else soma_servicos

    servicos = []
    for i, it in enumerate(scope_items, start=1):
        servicos.append({
            "numero": i,
            "descricao": (it.get("description") or "").strip() or f"Serviço {i}",
            "rota_passo_id": it.get("rota_passo_id"),
            "valor": round(float(it.get("total") or 0), 2),
            "valor_formatado": fmt_brl(it.get("total")),
        })

    # (2) parcelas somam o total do bloco (cláusula 2ª == cláusula 1ª)
    installments = _synth_installments(list(proposal.payment_installments or []), bloco_total)
    validate_installments(installments, soma_servicos)

    imovel_nome = (prop.name if prop else None) or (process.title if process else None) or "Imóvel"
    bloco = {
        "imovel": imovel_nome,
        "matriculas": matriculas_nums,
        "servicos": servicos,
        "total": round(float(bloco_total), 2),
        "total_formatado": fmt_brl(bloco_total),
        "parcelas": installments,
    }

    bm_ativo = profile.bonus_malus.ativo if bonus_malus_ativo is None else bool(bonus_malus_ativo)
    now = data or datetime.now(UTC)
    prazo_max = max((int(it["prazo_dias"]) for it in scope_items if it.get("prazo_dias")), default=0)
    condicoes = {
        "foro": profile.foro,
        "prazo_execucao": profile.prazo_execucao or (f"{prazo_max} dias corridos" if prazo_max else "conforme cronograma acordado"),
        "vigencia": "até o integral cumprimento do objeto",
        "multa_percentual": profile.multa_percentual,
        "rescisao_notificacao_dias": profile.rescisao_notificacao_dias,
        "bonus_malus": {"ativo": bm_ativo, "percentual": profile.bonus_malus.percentual},
    }

    qualificacao = (
        "pessoa jurídica" if getattr(client, "client_type", None) and client.client_type.value == "pj"
        else "pessoa física"
    )
    return ContratoDoc(
        data_local=now.strftime("%d/%m/%Y"),
        contratada={"razao_social": profile.razao_social, "cnpj": profile.cnpj, "endereco": profile.endereco},
        contratante={
            "nome": client.full_name or _NAO_INFORMADO,
            "qualificacao": qualificacao,
            "cpf_cnpj": client.cpf_cnpj or _NAO_INFORMADO,
        },
        bloco=bloco,
        banco={
            "nome": profile.banco_nome,
            "agencia": profile.banco_agencia,
            "conta": profile.banco_conta,
            "titular": profile.banco_titular,
            "pix": profile.banco_pix or "—",
        },
        condicoes=condicoes,
        assinatura={"rt_nome": profile.rt_nome, "rt_titulo": profile.rt_titulo, "rt_crea": profile.rt_crea},
    )


# ---------------------------------------------------------------------------
# RENDER — texto plano (feed do PDF e do content da Saída) + guard
# ---------------------------------------------------------------------------

def render_proposta_text(doc: PropostaDoc) -> str:
    L: list[str] = []
    L.append(f"PROPOSTA TÉCNICA E COMERCIAL Nº {doc.numero}")
    L.append(f"{doc.tenant_razao_social} — CNPJ {doc.tenant_cnpj}")
    L.append(f"Data: {doc.data}")
    L.append(f"Cliente: {doc.cliente_nome}")
    L.append(f"Imóvel: {doc.imovel_nome}")
    L.append("")
    L.append("1. CARACTERIZAÇÃO DA PROPRIEDADE")
    c = doc.caracterizacao
    L.append(f"Localização: {c['localizacao']}")
    L.append(f"Área: {c['area']}")
    L.append(f"Uso atual: {c['uso_atual']}")
    L.append(f"Situação fundiária: {c['situacao_fundiaria']}")
    L.append(f"Histórico: {c['historico']}")
    L.append(f"Necessidade do cliente: {c['necessidade']}")
    L.append("")
    L.append("2. OBJETIVO")
    L.append(doc.objetivo)
    L.append("")
    L.append("3. O QUE SERÁ FEITO")
    for e in doc.etapas:
        L.append(f"  {e['ordem']}. {e['titulo']} — {e['descricao']}")
    L.append("")
    L.append("4. ENTREGÁVEIS")
    for ent in doc.entregaveis:
        L.append(f"  - {ent}")
    L.append("")
    L.append("5. INVESTIMENTO")
    L.append(f"Valor total: {doc.investimento['total_formatado']}")
    L.append(f"Forma de pagamento: {doc.investimento['forma_pagamento']}")
    for p in doc.investimento["parcelas"]:
        L.append(f"  Parcela {p['numero']} ({p['vencimento']}): {p['valor_formatado']}")
    L.append("")
    L.append("6. CONDIÇÕES COMERCIAIS")
    L.append(f"Prazo de execução: {doc.condicoes['prazo_execucao']}")
    L.append(f"Validade da proposta: {doc.condicoes['validade']}")
    L.append(f"Limitações de escopo: {doc.condicoes['limitacoes_escopo']}")
    L.append("")
    L.append("_______________________________________________")
    a = doc.assinatura
    L.append(a["nome"])
    L.append(a["titulo"])
    L.append(a["crea"])
    L.append(a["razao_social"])
    text = "\n".join(L)
    assert_resolved(text)
    return text


def _ordinal_clausula(n: int) -> str:
    return {1: "1ª", 2: "2ª", 3: "3ª", 4: "4ª", 5: "5ª", 6: "6ª", 7: "7ª", 8: "8ª"}.get(n, f"{n}ª")


def render_contrato_text(doc: ContratoDoc) -> str:
    L: list[str] = []
    L.append("CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE CONSULTORIA AMBIENTAL")
    L.append("")
    cd = doc.contratada
    L.append(f"CONTRATADA: {cd['razao_social']}, inscrita no CNPJ sob o nº {cd['cnpj']}, "
             f"com sede em {cd['endereco']}, doravante denominada CONTRATADA;")
    ct = doc.contratante
    L.append(f"CONTRATANTE: {ct['nome']} ({ct['qualificacao']}), inscrito(a) sob o nº "
             f"{ct['cpf_cnpj']}, doravante denominado(a) CONTRATANTE.")
    L.append("")
    # 1ª — Objeto
    L.append(f"CLÁUSULA {_ordinal_clausula(1)} — DO OBJETO")
    b = doc.bloco
    L.append(f"Imóvel: {b['imovel']} — Matrícula(s): {', '.join(b['matriculas'])}.")
    L.append("Serviços contratados:")
    for s in b["servicos"]:
        L.append(f"  {s['numero']}. {s['descricao']} — {s['valor_formatado']}")
    L.append(f"Total do bloco: {b['total_formatado']}")
    L.append("")
    # 2ª — Valor e pagamento
    L.append(f"CLÁUSULA {_ordinal_clausula(2)} — DO VALOR E DA FORMA DE PAGAMENTO")
    L.append(f"O valor total dos serviços é de {b['total_formatado']}, pago da seguinte forma:")
    for p in b["parcelas"]:
        L.append(f"  Parcela {p['numero']} ({p['vencimento']}): {p['valor_formatado']}")
    bk = doc.banco
    L.append("Dados para pagamento (CONTRATADA):")
    L.append(f"  Banco: {bk['nome']} | Agência: {bk['agencia']} | Conta: {bk['conta']}")
    L.append(f"  Titular: {bk['titular']} | PIX: {bk['pix']}")
    L.append("")
    # 3ª — Obrigações do contratante
    L.append(f"CLÁUSULA {_ordinal_clausula(3)} — DAS OBRIGAÇÕES DO CONTRATANTE")
    L.append("a) Fornecer documentos, informações e acessos necessários à execução;")
    L.append("b) Efetuar os pagamentos nas condições da Cláusula 2ª;")
    L.append("c) Comunicar alterações relevantes na situação do imóvel;")
    L.append("d) Arcar com taxas e custas de órgãos e cartórios, salvo previsão em contrário.")
    L.append("")
    # 4ª — Obrigações da contratada
    L.append(f"CLÁUSULA {_ordinal_clausula(4)} — DAS OBRIGAÇÕES DA CONTRATADA")
    L.append("a) Executar os serviços com zelo técnico e observância da legislação ambiental;")
    L.append("b) Manter o CONTRATANTE informado sobre o andamento;")
    L.append("c) Guardar sigilo sobre as informações do contrato;")
    L.append("d) Entregar os produtos nos prazos acordados, ressalvado atraso de terceiros.")
    L.append("")
    # 5ª — Rescisão
    cnd = doc.condicoes
    L.append(f"CLÁUSULA {_ordinal_clausula(5)} — DA RESCISÃO")
    L.append("a) Por acordo entre as partes, a qualquer tempo;")
    L.append(f"b) Por inadimplemento, mediante notificação prévia de {cnd['rescisao_notificacao_dias']} dias;")
    L.append(f"c) Na rescisão por culpa do CONTRATANTE, remuneração proporcional aos serviços "
             f"executados, acrescida de multa de {cnd['multa_percentual']} sobre o saldo.")
    L.append("")
    # 6ª — Vigência e prazo
    L.append(f"CLÁUSULA {_ordinal_clausula(6)} — DA VIGÊNCIA E DO PRAZO")
    L.append(f"Vigora a partir da assinatura e permanece {cnd['vigencia']}. Prazo estimado de "
             f"execução: {cnd['prazo_execucao']}, contado do recebimento da 1ª parcela e da documentação.")
    if cnd["bonus_malus"]["ativo"]:
        pct = cnd["bonus_malus"]["percentual"]
        L.append(f"Cláusula de desempenho (bônus/malus): bônus de até {pct}% por antecipação; "
                 f"malus de até {pct}% por atraso imputável exclusivamente à CONTRATADA.")
    L.append("")
    # 7ª — Disposições gerais
    L.append(f"CLÁUSULA {_ordinal_clausula(7)} — DAS DISPOSIÇÕES GERAIS")
    L.append("a) Este contrato representa o acordo integral entre as partes;")
    L.append("b) Alterações só valem por escrito e assinadas por ambas as partes;")
    L.append("c) A tolerância a descumprimento não implica novação nem renúncia;")
    L.append("d) As partes reconhecem a validade da assinatura eletrônica.")
    L.append("")
    # 8ª — Foro
    L.append(f"CLÁUSULA {_ordinal_clausula(8)} — DO FORO")
    L.append(f"Fica eleito o foro da {cnd['foro']} para dirimir controvérsias deste contrato.")
    L.append("")
    L.append(f"Local e data: {doc.data_local}.")
    L.append("")
    L.append("_______________________________________________")
    a = doc.assinatura
    L.append(f"CONTRATADA — {cd['razao_social']}")
    L.append(f"{a['rt_nome']} — {a['rt_titulo']} — {a['rt_crea']}")
    L.append("")
    L.append("_______________________________________________")
    L.append(f"CONTRATANTE — {ct['nome']}")
    L.append("")
    L.append("Testemunhas:")
    L.append("1. _______________________________  Nome:")
    L.append("2. _______________________________  Nome:")
    text = "\n".join(L)
    assert_resolved(text)
    return text


# ---------------------------------------------------------------------------
# RENDER — PDF (fpdf2; reaproveita a estética do gerador legado)
# ---------------------------------------------------------------------------

_LATIN1_MAP = {
    "—": "-", "–": "-", "’": "'", "‘": "'",
    "“": '"', "”": '"', "…": "...", "·": "-",
}


def _latin1_safe(text: str) -> str:
    for ch, repl in _LATIN1_MAP.items():
        text = text.replace(ch, repl)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def render_pdf(titulo: str, corpo: str, *, subtitulo: str = "Consultoria e Regularizacao Ambiental") -> bytes:
    """Renderiza o texto plano da peça em PDF (fpdf2). Cabeçalhos em CAPS viram
    negrito. Não engole erro de import (fpdf2 é dependência do projeto)."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    content_w = pdf.w - pdf.l_margin - pdf.r_margin

    pdf.set_font("Helvetica", style="B", size=13)
    pdf.set_text_color(30, 120, 60)
    pdf.cell(0, 9, _latin1_safe(titulo.upper()), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", style="", size=9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, _latin1_safe(subtitulo), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_draw_color(30, 120, 60)
    pdf.set_line_width(0.4)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + content_w, pdf.get_y())
    pdf.ln(5)

    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(35, 35, 35)
    for raw in corpo.split("\n"):
        line = _latin1_safe(raw.rstrip())
        pdf.set_x(pdf.l_margin)
        if line == "":
            pdf.ln(2.5)
        elif (line.isupper() and len(line) > 4) or line.endswith(":") and len(line) < 70:
            pdf.set_font("Helvetica", style="B", size=10)
            pdf.multi_cell(content_w, 6, line, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", size=10)
        else:
            pdf.multi_cell(content_w, 5.5, line, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
