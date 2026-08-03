"""O insumo da Rota (E5): diagnóstico fundamentado + ações triadas (ADR-038).

Até aqui a Rota era desenhada a partir de ``process.initial_diagnosis`` — o
**pré-diagnóstico por regras do intake**, escrito no minuto 1 do caso e nunca
reescrito (``app/models/process.py`` chama a coluna pelo nome). Ou seja: a rota
saía do que o CLIENTE CONTOU, não do que o SISTEMA APUROU. Tudo que a consultora
construiu da E2 à E4 — achados confirmados, divergências reconciliadas, ações
refinadas — passava ao largo.

A Ficha 07 já mandava o contrário (§8.1 "desenhada pela Legislação a partir do
**diagnóstico fundamentado**"; §5 E4 "Ações: refinadas e finais" → E5 "a aba
Ações assume a forma de rota"). Foi a implementação que divergiu.

QUEM DIRIGE A ROTA — a hierarquia (nota 1 do André)
════════════════════════════════════════════════════
Não inventamos heurística: o domínio JÁ sabia quais achados mudam a rota. O
campo ``muda_rota_regulatoria`` existe no catálogo (default por código de
alerta, curadoria da Isis) e na ``RegulatoryIssue`` (override do caso), e era
escrito pelo ``AuditorImovelAgent`` sem que ninguém o lesse para decidir nada.

Três camadas, da mais forte para a mais fraca:

1. **Decisão humana sobre o caso** (``ProcessIssueDecision``) — ``fora_escopo``
   e ``ignorar_justificado`` são declarações explícitas de "isto não entra
   neste trabalho". Vencem tudo. É o Princípio 1.
2. **Override do caso** (``RegulatoryIssue.muda_rota_regulatoria``) — decisão
   sobre AQUELE achado naquele imóvel; vence o default.
3. **Default do catálogo** (``RegulatoryIssueCatalog.muda_rota_regulatoria``).

Achado que NÃO dirige a rota **não some**: vai como contexto secundário, para o
agente não perder o quadro do caso. Só não vira passo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.acao import Acao, AcaoTipoTriagem
from app.models.process import Process
from app.models.regulatory import (
    DecisaoConsultor,
    RegulatoryDiagnosis,
    RegulatoryIssue,
    RegulatoryIssueCatalog,
)

logger = get_logger(__name__)

__all__ = [
    "AchadoDaRota",
    "ContextoRota",
    "DiagnosticoNaoFundamentado",
    "montar_contexto_rota",
]

# Decisões humanas que TIRAM o achado da rota, por mais grave que ele seja.
_DECISOES_QUE_EXCLUEM = frozenset({
    DecisaoConsultor.fora_escopo,
    DecisaoConsultor.ignorar_justificado,
})

# A ação "refinada/validada pelo consultor" é a que passou pela triagem sem ser
# descartada. `pendente` = a IA propôs e ninguém olhou; `dispensada` = o
# consultor disse não. Nenhuma das duas dirige rota.
_TRIAGENS_VALIDAS = frozenset({AcaoTipoTriagem.tarefa, AcaoTipoTriagem.escopo})


class DiagnosticoNaoFundamentado(RuntimeError):
    """Não há diagnóstico assinado para este caso — a rota não pode ser traçada.

    Erro de FLUXO, não de sistema: a mensagem vai inteira para a tela do
    consultor, dizendo qual é o próximo movimento dele.
    """


@dataclass
class AchadoDaRota:
    """Um achado do imóvel, já resolvido quanto a dirigir (ou não) a rota."""

    issue: RegulatoryIssue
    dirige_rota: bool
    # De onde saiu a decisão — vai para o log e para a auditoria, nunca some.
    motivo: str
    decisao_consultor: Optional[DecisaoConsultor] = None

    @property
    def ref(self) -> str:
        """Rótulo estável que o LLM cita para declarar a origem de um passo."""
        return f"ACHADO-{self.issue.id}"

    def linha(self) -> str:
        codigo = self.issue.codigo_alerta or "(sem código)"
        severidade = self.issue.severity.value if self.issue.severity else "—"
        # A descrição legível do achado vive no payload — o auditor a grava lá
        # (`auditor_imovel._persist_issues`); a tabela não tem coluna própria.
        payload = self.issue.payload if isinstance(self.issue.payload, dict) else {}
        descricao = str(payload.get("descricao") or "").strip() or codigo
        impacto = str(payload.get("impacto") or "").strip()
        decisao = (
            f" · decisão do consultor: {self.decisao_consultor.value}"
            if self.decisao_consultor else ""
        )
        linha = f"[{self.ref}] {codigo} (severidade {severidade}){decisao} — {descricao}"
        return f"{linha} | impacto: {impacto}" if impacto else linha


@dataclass
class ContextoRota:
    """Tudo que a Legislação precisa saber para desenhar a rota deste caso."""

    diagnosis: RegulatoryDiagnosis
    achados_dirigem: list[AchadoDaRota] = field(default_factory=list)
    achados_contexto: list[AchadoDaRota] = field(default_factory=list)
    acoes: list[Acao] = field(default_factory=list)
    # `initial_diagnosis` rebaixado: entra rotulado, nunca como fundamento.
    relato_cliente: Optional[str] = None

    def refs_validas(self) -> set[str]:
        """As referências que um passo PODE citar como origem.

        Só o que existe de verdade neste caso. Referência fora desta lista é
        alucinação e é descartada na materialização — a rota prefere passo sem
        origem a passo com origem inventada.
        """
        return (
            {a.ref for a in self.achados_dirigem}
            | {f"ACAO-{a.id}" for a in self.acoes}
        )

    def resolver_ref(self, ref: Any) -> tuple[Optional[int], Optional[int]]:
        """``"ACHADO-12"`` → ``(12, None)``; ``"ACAO-7"`` → ``(None, 7)``.

        Devolve ``(None, None)`` para qualquer coisa que não case com um achado
        ou ação REAIS deste caso.
        """
        texto = str(ref or "").strip().upper()
        if texto not in self.refs_validas():
            return None, None
        prefixo, _, numero = texto.partition("-")
        try:
            ident = int(numero)
        except ValueError:
            return None, None
        return (ident, None) if prefixo == "ACHADO" else (None, ident)

    def bloco_prompt(self) -> str:
        """O contexto fundamentado, em texto, para o prompt da Legislação."""
        partes: list[str] = [
            "DIAGNÓSTICO FUNDAMENTADO DESTE CASO "
            f"(versão {self.diagnosis.version}, assinado pelo consultor).",
            "Esta é a base da rota. Desenhe os passos para resolver ESTES achados "
            "e executar ESTAS ações — não um roteiro genérico da demanda.",
            "",
        ]

        afirmacoes = self._afirmacoes_com_fonte()
        if afirmacoes:
            partes.append("O QUE O DIAGNÓSTICO AFIRMA (cada item com sua fonte):")
            partes.extend(f"- {linha}" for linha in afirmacoes)
            partes.append("")

        if self.achados_dirigem:
            partes.append(
                "ACHADOS QUE DIRIGEM A ROTA (cada um precisa de passo que o enderece):"
            )
            partes.extend(f"- {a.linha()}" for a in self.achados_dirigem)
            partes.append("")

        if self.acoes:
            partes.append("AÇÕES JÁ TRIADAS PELO CONSULTOR (a rota as ordena e fundamenta):")
            for acao in self.acoes:
                triagem = acao.tipo_triagem.value if acao.tipo_triagem else "—"
                partes.append(f"- [ACAO-{acao.id}] ({triagem}) {acao.titulo}")
            partes.append("")

        if self.achados_contexto:
            partes.append(
                "CONTEXTO SECUNDÁRIO — achados do imóvel que NÃO dirigem a rota "
                "(o consultor os excluiu, ou o catálogo diz que não mudam o "
                "caminho). Servem para você entender o quadro; NÃO gere passo "
                "para eles:"
            )
            partes.extend(f"- {a.linha()}" for a in self.achados_contexto)
            partes.append("")

        if self.relato_cliente:
            partes.append(
                "RELATO DO CLIENTE — NÃO CONFERIDO (pré-diagnóstico automático do "
                "intake, anterior a qualquer apuração). Use no máximo para "
                "entender a intenção; NUNCA como fundamento de passo, prazo ou "
                "norma:"
            )
            partes.append(self.relato_cliente.strip())
            partes.append("")

        partes.append(
            "PROVENIÊNCIA OBRIGATÓRIA: cada etapa que você propuser deve trazer "
            '"origem_refs": lista com os rótulos entre colchetes acima que a '
            'originaram (ex.: ["ACHADO-12", "ACAO-7"]). Use SOMENTE rótulos que '
            "aparecem acima. Se um passo é de rito e não nasce de achado nem de "
            "ação, devolva a lista vazia — inventar um rótulo é pior que não ter."
        )
        return "\n".join(partes)

    def _afirmacoes_com_fonte(self) -> list[str]:
        """Lê ``content["afirmacoes"]`` (contrato #70) — texto + fontes."""
        conteudo = self.diagnosis.content if isinstance(self.diagnosis.content, dict) else {}
        linhas: list[str] = []
        for item in (conteudo.get("afirmacoes") or [])[:40]:
            if not isinstance(item, dict):
                continue
            texto = (item.get("texto") or "").strip()
            if not texto:
                continue
            fontes = item.get("fontes") or []
            rotulos = [
                str(f.get("descricao") or f.get("tipo") or "").strip()
                for f in fontes if isinstance(f, dict)
            ]
            rotulos = [r for r in rotulos if r]
            sufixo = f" (fonte: {'; '.join(rotulos)})" if rotulos else " (sem fonte declarada)"
            linhas.append(f"{texto}{sufixo}")
        return linhas


# ---------------------------------------------------------------------------
# Montagem
# ---------------------------------------------------------------------------

def _diagnostico_fundamentado(
    db: Session, tenant_id: int, process_id: int
) -> RegulatoryDiagnosis:
    """A versão mais recente ASSINADA. Sem ela não há rota (guard do ADR-038)."""
    assinado = (
        db.query(RegulatoryDiagnosis)
        .filter(
            RegulatoryDiagnosis.tenant_id == tenant_id,
            RegulatoryDiagnosis.process_id == process_id,
            RegulatoryDiagnosis.validated_at.isnot(None),
        )
        .order_by(RegulatoryDiagnosis.version.desc())
        .first()
    )
    if assinado is not None:
        return assinado

    # Distingue os dois "nãos" — a diferença muda o próximo movimento dele.
    existe_rascunho = (
        db.query(RegulatoryDiagnosis.id)
        .filter(
            RegulatoryDiagnosis.tenant_id == tenant_id,
            RegulatoryDiagnosis.process_id == process_id,
        )
        .first()
        is not None
    )
    if existe_rascunho:
        raise DiagnosticoNaoFundamentado(
            "O diagnóstico deste caso existe mas ainda não foi assinado. "
            "Assine-o na Visão geral antes de traçar a rota — a rota é peça "
            "formal e não pode nascer de leitura não validada."
        )
    raise DiagnosticoNaoFundamentado(
        "Este caso ainda não tem diagnóstico. Rode os agentes do Diagnóstico "
        "Técnico e assine o resultado antes de traçar a rota — sem isso a rota "
        "sairia do relato do cliente, não do que foi apurado."
    )


def _classificar_achados(
    db: Session, tenant_id: int, process: Process
) -> tuple[list[AchadoDaRota], list[AchadoDaRota]]:
    """Separa os achados do imóvel entre "dirige a rota" e "contexto"."""
    from app.models.regulatory import ProcessIssueDecision  # noqa: PLC0415

    if not process.property_id:
        return [], []

    issues = (
        db.query(RegulatoryIssue)
        .filter(
            RegulatoryIssue.tenant_id == tenant_id,
            RegulatoryIssue.property_id == process.property_id,
        )
        .all()
    )
    if not issues:
        return [], []

    catalogo = {
        c.codigo_alerta: c
        for c in db.query(RegulatoryIssueCatalog).all()
    }
    decisoes = {
        d.issue_id: d
        for d in db.query(ProcessIssueDecision).filter(
            ProcessIssueDecision.tenant_id == tenant_id,
            ProcessIssueDecision.process_id == process.id,
        )
    }

    dirigem: list[AchadoDaRota] = []
    contexto: list[AchadoDaRota] = []

    for issue in issues:
        decisao_row = decisoes.get(issue.id)
        decisao = decisao_row.decisao if decisao_row else None

        # 1) decisão humana sobre o caso vence tudo
        if decisao in _DECISOES_QUE_EXCLUEM:
            contexto.append(AchadoDaRota(
                issue=issue, dirige_rota=False,
                motivo=f"decisão do consultor: {decisao.value}",
                decisao_consultor=decisao,
            ))
            continue

        # 2) override do caso vence o default do catálogo
        override = issue.muda_rota_regulatoria
        if override is not None:
            dirige, motivo = bool(override), "override no achado deste imóvel"
        else:
            entrada = catalogo.get(issue.codigo_alerta or "")
            if entrada is None:
                # Só chega aqui o achado LEGADO, sem `codigo_alerta` — a coluna é
                # nullable por retrocompat (pré-PROMPT_5) e o banco tem FK para o
                # catálogo, então código inventado não entra. Sem taxonomia não dá
                # para afirmar que dirige a rota: entra como contexto, nomeado.
                dirige, motivo = False, "achado sem código de alerta (registro legado)"
            else:
                dirige = bool(entrada.muda_rota_regulatoria)
                motivo = "default do catálogo"

        alvo = dirigem if dirige else contexto
        alvo.append(AchadoDaRota(
            issue=issue, dirige_rota=dirige, motivo=motivo, decisao_consultor=decisao,
        ))

    return dirigem, contexto


def _acoes_triadas(db: Session, tenant_id: int, process_id: int) -> list[Acao]:
    """As ações que o consultor manteve — `tarefa` e `escopo` (nota do André)."""
    return (
        db.query(Acao)
        .filter(
            Acao.tenant_id == tenant_id,
            Acao.process_id == process_id,
            Acao.tipo_triagem.in_(list(_TRIAGENS_VALIDAS)),
        )
        .order_by(Acao.id)
        .all()
    )


def montar_contexto_rota(
    db: Session, *, process: Process, tenant_id: int
) -> ContextoRota:
    """Reúne o insumo fundamentado da rota. Levanta ``DiagnosticoNaoFundamentado``.

    Não toca no banco para escrever — é leitura pura, e o caller decide o que
    fazer com o bloqueio.
    """
    diagnosis = _diagnostico_fundamentado(db, tenant_id, process.id)
    dirigem, contexto = _classificar_achados(db, tenant_id, process)
    acoes = _acoes_triadas(db, tenant_id, process.id)

    logger.info(
        "rota_contexto_montado",
        extra={
            "process_id": process.id,
            "tenant_id": tenant_id,
            "diagnosis_version": diagnosis.version,
            "achados_dirigem": len(dirigem),
            "achados_contexto": len(contexto),
            "acoes_triadas": len(acoes),
        },
    )
    return ContextoRota(
        diagnosis=diagnosis,
        achados_dirigem=dirigem,
        achados_contexto=contexto,
        acoes=acoes,
        relato_cliente=(process.initial_diagnosis or "").strip() or None,
    )

# ---------------------------------------------------------------------------
# Reconciliação — sinaliza, nunca regenera sozinha (nota 2 do André)
# ---------------------------------------------------------------------------

def fundamento_mudou_desde_a_rota(
    db: Session, *, process: Process, tenant_id: int
) -> Optional[str]:
    """A rota deste caso ficou para trás do diagnóstico? Frase pronta ou ``None``.

    Um achado pode passar a dirigir a rota DEPOIS de ela ter sido traçada —
    chegou documento novo, o consultor mudou a decisão, o override virou. A
    tentação é regenerar; a regra é não.

    Regenerar sozinha apagaria trabalho humano (classificação, ordem, passos
    manuais) por causa de um evento que o consultor talvez nem tenha visto. Aqui
    só se OLHA: se há achado que dirige a rota e nenhum passo aponta para ele, a
    tela ganha "a rota pode estar desatualizada — regenerar?" e quem decide é
    quem assina.

    Leitura pura — não escreve, não muda status, não enfileira nada.
    """
    from app.models.rota import Rota  # noqa: PLC0415

    rotas = (
        db.query(Rota)
        .filter(Rota.tenant_id == tenant_id, Rota.process_id == process.id)
        .all()
    )
    if not rotas or not any(r.passos for r in rotas):
        return None  # sem rota não há o que estar desatualizado

    try:
        dirigem, _contexto = _classificar_achados(db, tenant_id, process)
    except Exception as exc:  # noqa: BLE001 — sinal informativo nunca derruba a tela
        logger.warning("rota: falha ao conferir o fundamento: %s", exc)
        return None
    if not dirigem:
        return None

    enderecados = {
        p.origem_issue_id
        for r in rotas for p in r.passos
        if p.origem_issue_id is not None
    }
    orfaos = [a for a in dirigem if a.issue.id not in enderecados]
    if not orfaos:
        return None

    # Passo antigo (anterior ao ADR-038) não tem proveniência: sem isso, TODO
    # achado pareceria órfão e o aviso apareceria sempre, para todo caso — o
    # tipo de alarme que se aprende a ignorar. Se nenhum passo tem origem, a
    # rota é de antes do carimbo e não dá para afirmar que ficou para trás.
    if not enderecados:
        return None

    quantos = len(orfaos)
    exemplo = orfaos[0].issue.codigo_alerta or "achado sem código"
    plural = "achado que dirige a rota não está" if quantos == 1 else              "achados que dirigem a rota não estão"
    return (
        f"{quantos} {plural} endereçado por nenhum passo (ex.: {exemplo}). "
        "A rota pode estar desatualizada — regenerar? Nada foi alterado."
    )
