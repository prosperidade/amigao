"""ADR-071. Qualificação determinística, limitada ao material e à data informada."""
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal

from app.services.observacao_registral import Observacao, aplicar_alteracoes, derivar_vigencia
from app.services.taxonomia_documental import SUPORTE


@dataclass(frozen=True)
class IdentidadeAto:
    documento_id: int
    matricula: str
    serventia: str
    rotulo: str


@dataclass
class AtoMaterial:
    identidade: IdentidadeAto
    natureza: str
    data_ato: date | None
    ordem: int
    alvo: IdentidadeAto | None = None
    relacao: str | None = None
    prazo: str | None = None
    transmitentes: dict[str, Decimal] = field(default_factory=dict)
    adquirentes: dict[str, Decimal] = field(default_factory=dict)


def avaliar_material(*, especie, atos, data_referencia, cobertura_completa=False,
                     data_certidao=None, saldo_inicial=None):
    """Completeness is an explicit caller premise, never inferred from max(ordem)."""
    gaps = []
    escopos = {(a.identidade.serventia, a.identidade.matricula) for a in atos}
    if len(escopos) > 1:
        raise ValueError("Avaliação exige uma matrícula por serventia; use avaliar_matriculas")
    if especie != "certidao_matricula":
        gaps.append("certidao_adequada: escritura e contrato não comprovam estado registral atual")
    if not cobertura_completa or data_certidao is None or data_certidao < data_referencia:
        gaps.append("cobertura_da_certidao_na_data_de_referencia")
    identities = [a.identidade for a in atos]
    if len(set(identities)) != len(identities):
        gaps.append("identidade_de_ato_ambigua")
    by_identity = {a.identidade: a for a in atos}
    obs_by_identity = {}
    for act in atos:
        attrs = {"ato": act.identidade.rotulo, "documento_id": act.identidade.documento_id,
            "matricula": act.identidade.matricula, "serventia": act.identidade.serventia,
            "data_ato": act.data_ato.isoformat() if act.data_ato else None, "prazo": act.prazo}
        obs_by_identity[act.identidade] = Observacao(act.natureza, attrs, act.ordem)
        if act.data_ato is None:
            gaps.append(f"data_do_ato:{act.identidade.rotulo}")
    links = []
    for act in atos:
        if not act.relacao:
            continue
        if act.alvo is None or act.alvo not in by_identity:
            gaps.append(f"vinculo_explicito:{act.identidade.rotulo}")
            continue
        if act.alvo == act.identidade:
            gaps.append(f"ciclo_de_ato:{act.identidade.rotulo}")
            continue
        target = by_identity[act.alvo]
        if act.data_ato is None or target.data_ato is None or act.data_ato < target.data_ato:
            gaps.append(f"cronologia_da_relacao:{act.identidade.rotulo}")
            continue
        if (act.alvo.serventia, act.alvo.matricula) != (act.identidade.serventia, act.identidade.matricula):
            gaps.append(f"referencia_em_outra_inscricao:{act.identidade.rotulo}")
            continue
        links.append({"origem": asdict(act.identidade), "destino": asdict(act.alvo), "tipo": act.relacao})
        if act.data_ato > data_referencia:
            continue
        # Reuse legacy derivation only inside a completely delimited pair.
        original = obs_by_identity[act.alvo]
        event = Observacao("baixa" if act.relacao in {"baixa", "cancelamento"} else "aditivo",
            {"ato": act.identidade.rotulo, "altera_ato": target.identidade.rotulo}, act.ordem)
        aplicar_alteracoes([original, event])
    derivar_vigencia(list(obs_by_identity.values()), data_referencia=data_referencia)
    balances = dict(saldo_inicial or {})
    transfers = [a for a in atos if a.natureza in {"compra_venda", "doacao", "partilha", "sucessao"}]
    if saldo_inicial is None:
        gaps.append("ato_intermediario_ou_origem_da_cadeia")
    for act in sorted(transfers, key=lambda a: (a.data_ato or date.min, a.ordem)):
        if act.data_ato is None or act.data_ato > data_referencia:
            continue
        sent, received = act.transmitentes, act.adquirentes
        if not sent or not received or sum(sent.values()) != sum(received.values()):
            gaps.append(f"fracao_ou_participacao:{act.identidade.rotulo}")
            continue
        if any(v <= 0 or v > 1 for v in received.values()) or any(
                v <= 0 or v > 1 or balances.get(p, Decimal(0)) < v for p, v in sent.items()):
            gaps.append(f"continuidade_dominial:{act.identidade.rotulo}")
            continue
        for person, fraction in sent.items():
            balances[person] -= fraction
        for person, fraction in received.items():
            balances[person] = balances.get(person, Decimal(0)) + fraction
    return {"metodo": "cartorario", "versao": "071.1", "suporte": SUPORTE[especie],
        "situacoes": [{"ato": asdict(identity), "situacao": obs.vigencia or "indeterminado"}
                      for identity, obs in obs_by_identity.items()], "relacoes": links,
        "estado_titularidade": "nao_determinado" if gaps else "vigente_segundo_o_material",
        "participacoes_derivadas": {} if gaps else {p: str(v) for p, v in balances.items() if v > 0},
        "lacunas": sorted(set(gaps)),
        "regras_ins003": {"estado": "capacidade_insuficiente", "motivo": "174 condições aguardam tradução e homologação"}}


def avaliar_matriculas(*, atos, data_referencia, contexto_por_matricula=None):
    """Same registry header does not join balances, acts or ownership of four entries."""
    grupos = {}
    for ato in atos:
        key = (ato.identidade.serventia, ato.identidade.matricula)
        grupos.setdefault(key, []).append(ato)
    results = []
    for key, grupo in sorted(grupos.items()):
        contexto = (contexto_por_matricula or {}).get(key, {})
        results.append({"serventia": key[0], "matricula": key[1],
            "documentos": sorted({a.identidade.documento_id for a in grupo}),
            **avaliar_material(atos=grupo, data_referencia=data_referencia,
                especie=contexto.get("especie", "indeterminada"),
                cobertura_completa=contexto.get("cobertura_completa", False),
                data_certidao=contexto.get("data_certidao"), saldo_inicial=contexto.get("saldo_inicial"))})
    return results


def qualificar_representacao(*, especie, alcance, inicio, fim, representado, data_referencia):
    """A declared role survives in every species; exercising powers needs its basis."""
    lacunas = []
    if especie != "documento_representacao":
        lacunas.append("documento_de_nomeacao_ou_poderes")
    if not representado:
        lacunas.append("identidade_da_parte_representada")
    if not alcance:
        lacunas.append("alcance_dos_poderes")
    if inicio is None or fim is None:
        lacunas.append("validade_da_representacao")
    elif data_referencia is not None and not inicio <= data_referencia <= fim:
        lacunas.append("representacao_fora_do_intervalo_documentado")
    if data_referencia is None:
        lacunas.append("data_de_referencia_nao_determinada")
    return {"estado_confirmacao": "declarado", "poderes_na_data":
        "nao_determinado" if lacunas else "documentados_aguardando_revisao", "lacunas": lacunas}
