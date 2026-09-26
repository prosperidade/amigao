"""Redator pré-contratação (ADR-074 §2): relatório preliminar e especificação de escopo.

Montados da Rota validada e da execução do motor jurídico que a gerou. Determinístico:
cada afirmação nasce com evidência por ID (dispositivo, observação, documento, avaliação,
passo) e passa por ``evidencia.exigir`` antes de gravar. Sem contrato (decisão 5); a peça
técnica definitiva e o checklist de TR são pós-contratação (decisão 10).

Método: ``app/skills/redator/relatorio_preliminar_escopo/SKILL.md`` (manifesto da cadeia).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.comercial import RedacaoComercial
from app.models.evidence import EvidenceVersion
from app.models.motor_juridico import AvaliacaoRegra, CienciaAlerta, ExecucaoMotor, Regra, RegraVersao
from app.models.process import Process
from app.models.rota import Rota, RotaPasso, RotaPassoClassificacao, RotaPassoStatus
from app.models.zona_normativa import Dispositivo
from app.services.comercial import ComercialError
from app.services.comercial import base as base_mod
from app.services.comercial import evidencia as ev
from app.services.motor_juridico.linguagem import ROTULOS

logger = get_logger(__name__)

LIMITES_RELATORIO = [
    "Relatório preliminar: descreve o que os autos e a Rota validada sustentam; não é a peça técnica "
    "contratada nem parecer jurídico.",
    "A situação dos autos vem do retrato de fatos do motor jurídico (ADR-073 §3); o que não está no "
    "vocabulário do motor não aparece aqui.",
    "\"Não consta nos autos\" é fato sobre os autos, não sobre o imóvel.",
]
LIMITES_ESCOPO = [
    "Não inclui a peça técnica definitiva (laudo, memorial, requerimento): ela é elaborada depois da "
    "contratação, quando fizer parte do serviço contratado.",
    "Não é contrato: a peça comercial oficial nasce da proposta aceita.",
]


@dataclass
class Contexto:
    process: Process
    rotas: list[Rota]
    execucao: ExecucaoMotor | None
    avaliacoes: dict[int, AvaliacaoRegra] = field(default_factory=dict)
    rule_ids: dict[int, str] = field(default_factory=dict)  # regra_versao_id → rule_id
    descricoes: dict[int, str] = field(default_factory=dict)  # regra_versao_id → descrição
    dispositivos: dict[int, Dispositivo] = field(default_factory=dict)
    fontes_primarias: dict[int, list[int]] = field(default_factory=dict)  # documento → evidence ids
    ciencias: dict[int, CienciaAlerta] = field(default_factory=dict)  # avaliação → ciência


def _contexto(db: Session, *, process: Process, tenant_id: int) -> Contexto:
    rotas = base_mod.rotas_validadas(db, tenant_id, process.id)
    if not rotas:
        raise ComercialError("Rota validada ausente: feche a Rota Regulatória (E5) antes do relatório "
                             "preliminar e do escopo.")
    passos = [p for r in rotas for p in list(r.passos) + list(r.passos_removidos)]
    av_ids = {p.origem_avaliacao_id for p in passos if p.origem_avaliacao_id}
    avs = {a.id: a for a in db.query(AvaliacaoRegra).filter(AvaliacaoRegra.id.in_(av_ids),
                                                             AvaliacaoRegra.tenant_id == tenant_id)} if av_ids else {}
    # Situação, achados, alertas e lacunas vêm da execução MAIS RECENTE do caso — a mesma que o
    # `fechar` da Rota exige com ciência. A que gerou os passos pode ser anterior (medido no #25 de
    # dev: passos da execução 4, ciência do alerta na 5); cada passo segue citando a própria avaliação.
    from app.services.motor_juridico.avaliador import ultima_execucao  # noqa: PLC0415

    execucao = ultima_execucao(db, process_id=process.id, tenant_id=tenant_id)
    if execucao is not None:
        for a in db.query(AvaliacaoRegra).filter(AvaliacaoRegra.execucao_id == execucao.id,
                                                 AvaliacaoRegra.tenant_id == tenant_id):
            avs[a.id] = a
    ctx = Contexto(process=process, rotas=rotas, execucao=execucao, avaliacoes=avs)
    rv_ids = {a.regra_versao_id for a in avs.values()}
    if rv_ids:
        for rv_id, rule_id, descricao in (db.query(RegraVersao.id, Regra.rule_id, RegraVersao.descricao)
                                          .join(Regra, Regra.id == RegraVersao.regra_id)
                                          .filter(RegraVersao.id.in_(rv_ids))):
            ctx.rule_ids[rv_id], ctx.descricoes[rv_id] = rule_id, descricao
    disp_ids = ({p.fundamento_dispositivo_id for p in passos if p.fundamento_dispositivo_id}
                | {a.fundamento_dispositivo_id for a in avs.values() if a.fundamento_dispositivo_id})
    if disp_ids:
        ctx.dispositivos = {d.id: d for d in db.query(Dispositivo).filter(Dispositivo.id.in_(disp_ids))}
    doc_ids = {d for a in avs.values() for fato in (a.entradas or {}).values() if fato
               for d in (fato.get("origem") or {}).get("documentos", [])}
    if doc_ids:
        for ev_id, doc_id in (db.query(EvidenceVersion.id, EvidenceVersion.source_document_id)
                              .filter(EvidenceVersion.tenant_id == tenant_id,
                                      EvidenceVersion.process_id == process.id,
                                      EvidenceVersion.kind == "fonte_primaria",
                                      EvidenceVersion.source_document_id.in_(doc_ids))
                              .order_by(EvidenceVersion.id)):
            ctx.fontes_primarias.setdefault(doc_id, []).append(ev_id)
    if avs:
        ctx.ciencias = {c.avaliacao_id: c for c in db.query(CienciaAlerta).filter(
            CienciaAlerta.avaliacao_id.in_(list(avs)), CienciaAlerta.tenant_id == tenant_id)}
    if execucao is not None:
        # #289: a ciência dada numa execução de mesmo conteúdo vale para a mais recente.
        from app.services.motor_juridico.avaliador import ciencias_vigentes  # noqa: PLC0415

        ctx.ciencias.update(ciencias_vigentes(db, execucao_id=execucao.id, tenant_id=tenant_id))
    return ctx


# ---------------------------------------------------------------------------
# Evidências
# ---------------------------------------------------------------------------

def _ev_fato(ctx: Contexto, fato: dict | None) -> list[dict]:
    """Documentos (e suas fontes primárias) e observações que sustentam um fato do retrato."""
    if not fato:
        return []
    origem = fato.get("origem") or {}
    out = []
    for doc in origem.get("documentos", []):
        out.append(ev.ref("documento", doc, f"documento #{doc}"))
        out += [ev.ref("fonte_primaria", e, f"fonte primária do documento #{doc}")
                for e in ctx.fontes_primarias.get(doc, [])]
    out += [ev.ref("observacao", o, f"observação #{o}") for o in origem.get("observacoes", [])]
    return out


def _ev_avaliacao(ctx: Contexto, av: AvaliacaoRegra) -> list[dict]:
    rule = ctx.rule_ids.get(av.regra_versao_id, f"regra_versao {av.regra_versao_id}")
    out = [ev.ref("avaliacao_regra", av.id, f"{rule}: {av.estado}")]
    if av.fundamento_dispositivo_id:
        d = ctx.dispositivos.get(av.fundamento_dispositivo_id)
        out.append(ev.ref("dispositivo", av.fundamento_dispositivo_id, d.caminho if d else "dispositivo"))
        out.append(ev.ref("fonte_versao", av.fundamento_fonte_versao_id, "versão da fonte do fundamento"))
    for fato in (av.entradas or {}).values():
        out += _ev_fato(ctx, fato)
    return out


def _ev_passo(ctx: Contexto, passo: RotaPasso) -> list[dict]:
    out = [ev.ref("rota_passo", passo.id, f"passo {passo.id} da Rota {passo.rota_id}")]
    if passo.fundamento_dispositivo_id:
        d = ctx.dispositivos.get(passo.fundamento_dispositivo_id)
        out.append(ev.ref("dispositivo", passo.fundamento_dispositivo_id, d.caminho if d else "dispositivo"))
        out.append(ev.ref("fonte_versao", passo.fundamento_fonte_versao_id, "versão da fonte do fundamento"))
    av = ctx.avaliacoes.get(passo.origem_avaliacao_id) if passo.origem_avaliacao_id else None
    if av is not None:
        out += _ev_avaliacao(ctx, av)
    return out


def _fundamento_texto(ctx: Contexto, passo: RotaPasso) -> str | None:
    d = ctx.dispositivos.get(passo.fundamento_dispositivo_id) if passo.fundamento_dispositivo_id else None
    return d.caminho if d else None


def _lendo(ctx: Contexto, chave: str) -> list[AvaliacaoRegra]:
    return [a for a in ctx.avaliacoes.values()
            if ctx.execucao and a.execucao_id == ctx.execucao.id and chave in (a.entradas or {})]


# ---------------------------------------------------------------------------
# Seções
# ---------------------------------------------------------------------------

def _frase_fato(chave: str, fato: dict) -> str | None:
    v = fato.get("valor")
    if chave == "caso.uf":
        return f"UF do imóvel no cadastro do caso: {v}."
    if chave == "car.no_dossie":
        return "Consta CAR nos autos." if v else "Não consta CAR nos autos."
    if chave == "ccir.no_dossie":
        return "Consta CCIR nos autos." if v else "Não consta CCIR nos autos."
    if chave == "dominio.matriculas_no_dossie":
        return (f"Constam {v} certidão(ões) de matrícula nos autos." if v
                else "Não consta certidão de matrícula nos autos.")
    if chave == "imovel.natureza":
        origem = fato.get("origem") or {}
        base = "declarada na abertura do caso" if origem.get("declaracao_abertura") else "CAR nos autos"
        return f"Natureza do imóvel: {v} ({base})."
    if chave == "titular.falecimento_declarado":
        return "Falecimento do titular declarado em documento dos autos." if v else None
    return None


def _situacao(ctx: Contexto) -> tuple[list[dict], list[dict]]:
    """Fatos determinados viram afirmação; desconhecidos viram lacuna."""
    if ctx.execucao is None:
        return [], []
    afirmacoes, lacunas = [], []
    ex_ref = ev.ref("execucao_motor", ctx.execucao.id,
                    f"execução do motor #{ctx.execucao.id} (referência {ctx.execucao.data_referencia})")
    for chave in sorted(ctx.execucao.fatos or {}):
        fato = ctx.execucao.fatos[chave]
        leitoras = [ev.ref("avaliacao_regra", a.id, ctx.rule_ids.get(a.regra_versao_id, "regra"))
                    for a in _lendo(ctx, chave)]
        if fato.get("estado") == "determinado":
            frase = _frase_fato(chave, fato)
            if frase:
                afirmacoes.append(ev.afirmacao(f"situacao:{chave}", frase, [ex_ref, *_ev_fato(ctx, fato), *leitoras]))
        else:
            lacunas.append(ev.afirmacao(
                f"lacuna:fato:{chave}",
                f"Não determinado nos autos: {ROTULOS.get(chave, chave)}.",
                [ex_ref, *leitoras]))
    return afirmacoes, lacunas


def _achados_alertas_lacunas(ctx: Contexto) -> tuple[list[dict], list[dict], list[dict]]:
    achados, alertas, lacunas = [], [], []
    for av in sorted(ctx.avaliacoes.values(), key=lambda a: a.id):
        if ctx.execucao is None or av.execucao_id != ctx.execucao.id:
            continue
        rule = ctx.rule_ids.get(av.regra_versao_id, "regra")
        descricao = ctx.descricoes.get(av.regra_versao_id, "")
        if av.estado == "aplicavel_disparou":
            fundamento = (ctx.dispositivos[av.fundamento_dispositivo_id].caminho
                          if av.fundamento_dispositivo_id in ctx.dispositivos
                          else f"fundamento não resolvido ({av.fundamento_razao})")
            achados.append(ev.afirmacao(f"achado:{av.id}", f"{rule} disparou — {descricao} Fundamento: {fundamento}.",
                                        _ev_avaliacao(ctx, av)))
            for efeito in (av.consequencia or {}).get("efeitos", []):
                if efeito.get("tipo") != "alerta_critico":
                    continue
                ciencia = ctx.ciencias.get(av.id)
                if ciencia:
                    alertas.append(ev.afirmacao(
                        f"alerta:{av.id}",
                        f"Alerta crítico de {rule}: {efeito.get('titulo') or descricao}. Ciência registrada em "
                        f"{ciencia.registrada_em:%d/%m/%Y}: {ciencia.justificativa}",
                        [*_ev_avaliacao(ctx, av), ev.ref("ciencia_alerta", ciencia.id, "ciência do alerta")]))
                else:
                    alertas.append(ev.afirmacao(
                        f"alerta:{av.id}",
                        f"Alerta crítico de {rule} sem ciência registrada: {efeito.get('titulo') or descricao}.",
                        _ev_avaliacao(ctx, av)))
        elif av.estado == "indeterminado":
            faltam = ", ".join(ROTULOS.get(f, f) for f in (av.faltantes or [])) or "dado não identificado"
            lacunas.append(ev.afirmacao(f"lacuna:regra:{av.id}", f"{rule} não pôde decidir: falta {faltam}.",
                                        _ev_avaliacao(ctx, av)))
        elif av.estado == "erro_execucao":
            lacunas.append(ev.afirmacao(f"lacuna:erro:{av.id}", f"{rule} falhou na execução; resultado não usado.",
                                        [ev.ref("avaliacao_regra", av.id, f"{rule}: erro_execucao")]))
    return achados, alertas, lacunas


def _passos_validados(ctx: Contexto) -> list[RotaPasso]:
    return [p for r in ctx.rotas for p in r.passos if p.status == RotaPassoStatus.validado]


def _classe(p: RotaPasso) -> str:
    return "item de proposta" if p.classificacao == RotaPassoClassificacao.item_proposta else "orientação"


def _texto_passo(ctx: Contexto, p: RotaPasso, prefixo: str) -> str:
    partes = [f"{prefixo}: {p.titulo}."]
    fundamento = _fundamento_texto(ctx, p)
    partes.append(f"Fundamento: {fundamento}." if fundamento
                  else "Sem fundamento normativo por ID; passo validado pelo consultor.")
    if p.orgao:
        partes.append(f"Órgão: {p.orgao}.")
    if p.prazo_estimado_dias:
        partes.append(f"Prazo estimado: {p.prazo_estimado_dias} dias ({p.prazo_fonte or 'estimativa'}).")
    return " ".join(partes)


def _lacunas_de_fundamento(ctx: Contexto) -> list[dict]:
    return [ev.afirmacao(f"lacuna:passo:{p.id}",
                         f"Passo validado sem fundamento resolvido por ID: \"{p.titulo}\" ({_classe(p)}).",
                         [ev.ref("rota_passo", p.id, f"passo {p.id}")])
            for p in _passos_validados(ctx) if not p.fundamento_dispositivo_id]


def _premissas(db: Session, ctx: Contexto, diag: dict) -> list[dict]:
    out = []
    for r in ctx.rotas:
        quando = f" em {r.validated_at:%d/%m/%Y}" if r.validated_at else ""
        out.append(ev.afirmacao(f"premissa:rota:{r.id}", f"Rota {r.id} validada pelo consultor{quando}.",
                                [ev.ref("rota", r.id, f"Rota {r.id}")]))
    if ctx.execucao is not None:
        out.append(ev.afirmacao(
            "premissa:execucao",
            f"Avaliação do motor jurídico na data de referência {ctx.execucao.data_referencia:%d/%m/%Y}, "
            f"conjunto de regras #{ctx.execucao.conjunto_id}.",
            [ev.ref("execucao_motor", ctx.execucao.id, f"execução #{ctx.execucao.id}")]))
    em_revisao = [c for c in diag["conclusoes"] if c["revisao"] is None and not c["invalida"]]
    if em_revisao:
        out.append(ev.afirmacao(
            "premissa:diagnostico",
            f"{len(em_revisao)} conclusão(ões) do diagnóstico em revisão: registradas como ressalva, "
            "não usadas como premissa do escopo.",
            [ev.ref("conclusao", c["id"], c["objeto"]) for c in em_revisao]))
    return out


def montar(db: Session, *, process: Process, tenant_id: int) -> tuple[Contexto, dict, dict, dict]:
    """(contexto, relatório, escopo, estado do diagnóstico) — sem gravar."""
    ctx = _contexto(db, process=process, tenant_id=tenant_id)
    diag = base_mod.base_diagnostico(db, tenant_id, process.id)
    situacao, lacunas_fato = _situacao(ctx)
    achados, alertas, lacunas_regra = _achados_alertas_lacunas(ctx)
    validados = _passos_validados(ctx)
    caminho = [ev.afirmacao(f"caminho:{p.id}", _texto_passo(ctx, p, f"Passo validado ({_classe(p)})"),
                            _ev_passo(ctx, p)) for p in validados]
    relatorio = {"secoes": [
        {"chave": "situacao", "titulo": "Situação dos autos", "afirmacoes": situacao},
        {"chave": "achados", "titulo": "Achados do motor jurídico", "afirmacoes": achados},
        {"chave": "alertas", "titulo": "Alertas críticos", "afirmacoes": alertas},
        {"chave": "lacunas", "titulo": "Lacunas", "afirmacoes": lacunas_fato + lacunas_regra + _lacunas_de_fundamento(ctx)},
        {"chave": "caminho", "titulo": "Caminho validado", "afirmacoes": caminho},
    ], "limites": LIMITES_RELATORIO}

    incluidos = [p for p in validados if p.classificacao == RotaPassoClassificacao.item_proposta]
    orientacoes = [p for p in validados if p.classificacao == RotaPassoClassificacao.direcao]
    removidos = [p for r in ctx.rotas for p in r.passos_removidos]
    escopo = {"secoes": [
        {"chave": "incluido", "titulo": "O que será feito",
         "afirmacoes": [ev.afirmacao(f"escopo:{p.id}", _texto_passo(ctx, p, "Será executado"), _ev_passo(ctx, p))
                        for p in incluidos]},
        {"chave": "orientacoes", "titulo": "Orientações (não cobradas)",
         "afirmacoes": [ev.afirmacao(f"orientacao:{p.id}", _texto_passo(ctx, p, "Orientação ao cliente"),
                                     _ev_passo(ctx, p)) for p in orientacoes]},
        {"chave": "fora", "titulo": "Fora do escopo",
         "afirmacoes": [ev.afirmacao(f"fora:{p.id}",
                                     f"Fora do escopo: {p.titulo}. Motivo: {base_mod.motivo_remocao(db, p)}.",
                                     [ev.ref("rota_passo", p.id, f"passo {p.id} removido")]) for p in removidos]},
        {"chave": "premissas", "titulo": "Premissas", "afirmacoes": _premissas(db, ctx, diag)},
    ], "limites": LIMITES_ESCOPO}
    if not incluidos:
        raise ComercialError("A Rota validada não tem passo validado classificado como item de proposta: "
                             "não há escopo a especificar.")
    return ctx, relatorio, escopo, diag


def _gravar(db: Session, *, tenant_id: int, process_id: int, tipo: str, conteudo: dict, base: dict,
            rota_id: int | None, execucao_id: int | None, user_id: int | None) -> RedacaoComercial:
    anterior = base_mod.ultima_redacao(db, tenant_id, process_id, tipo)
    agora = datetime.now(UTC)
    if anterior is not None and anterior.superada_em is None:
        anterior.superada_em = agora
    r = RedacaoComercial(tenant_id=tenant_id, process_id=process_id, tipo=tipo,
                         versao=(anterior.versao + 1) if anterior else 1, rota_id=rota_id,
                         execucao_motor_id=execucao_id, conteudo=conteudo, base=base,
                         base_hash=base_mod.hash_base(base), criado_por_id=user_id, created_at=agora)
    db.add(r)
    db.flush()
    return r


def gerar(db: Session, *, process: Process, tenant_id: int, user_id: int | None
          ) -> tuple[RedacaoComercial, RedacaoComercial]:
    """Gera (e grava) relatório preliminar e especificação de escopo como versões novas."""
    from app.services.evidence import lock_case  # noqa: PLC0415
    from app.services.motor_juridico.avaliador import ultima_execucao  # noqa: PLC0415

    lock_case(db, tenant_id, process.id)
    ctx, relatorio, escopo, _ = montar(db, process=process, tenant_id=tenant_id)
    ev.exigir(db, relatorio["secoes"] + escopo["secoes"], tenant_id=tenant_id, process_id=process.id)
    ultima = ultima_execucao(db, process_id=process.id, tenant_id=tenant_id)
    base = base_mod.base_redacao(db, tenant_id, process.id, ultima.id if ultima else None)
    rota_id = ctx.rotas[0].id if len(ctx.rotas) == 1 else None
    execucao_id = ctx.execucao.id if ctx.execucao else None
    rel = _gravar(db, tenant_id=tenant_id, process_id=process.id, tipo="relatorio_preliminar", conteudo=relatorio,
                  base=base, rota_id=rota_id, execucao_id=execucao_id, user_id=user_id)
    esc = _gravar(db, tenant_id=tenant_id, process_id=process.id, tipo="especificacao_escopo", conteudo=escopo,
                  base=base, rota_id=rota_id, execucao_id=execucao_id, user_id=user_id)
    logger.info("comercial_redacao_gerada", extra={"process_id": process.id, "tenant_id": tenant_id,
                                                   "relatorio_id": rel.id, "escopo_id": esc.id})
    return rel, esc
