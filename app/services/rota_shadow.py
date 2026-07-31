"""Rota regulatória SOMBREADA + biblioteca qualificada (ADR-033).

**A decisão de domínio** (Isis, 26/07): no piloto, a Análise Legal **deixa de
propor rota**. Ela não sequencia etapas, não estima prazos e não diz por onde o
caso anda — porque a rota é conhecimento de consultora, construído com o órgão,
com o histórico do caso e com o que se sabe da mesa do analista. Uma rota gerada
com aparência de resposta pronta convida a ser seguida, e uma rota errada custa
prazo perdido, não um retrabalho de tela.

O que a Análise Legal passa a ser: **biblioteca qualificada**. Ela localiza as
normas aplicáveis e as apresenta **ao pé da letra**, com fonte, alcance declarado
(esfera/UF) e a data em que a vigência foi conferida. Fundamentação achada — não
caminho recomendado.

**Sombreada, não desligada:** o agente continua rodando e o output continua
persistido inteiro em ``AIJob.result``. O que muda é o que a API **serve**: os
campos prescritivos não saem para a tela. Assim a decisão é reversível (é uma
flag), o material fica para avaliação, e não existe a possibilidade de a rota
"vazar" para a UI por descuido de um componente — o dado simplesmente não chega.

**Rota-E5 é OUTRA entidade.** ``Rota``/``RotaPasso`` (ADR-021, ADR-028) são o
serviço contratado, construído pela consultora e base da proposta. Nada aqui os
toca. O que este módulo sombreia é a SUGESTÃO de caminho que o agente emitia
dentro do enquadramento — objetos diferentes, com o mesmo nome infeliz.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

__all__ = [
    "MODO_SHADOW",
    "MODO_ATIVA",
    "ROTULO_SHADOW",
    "rota_mode",
    "apply_shadow",
    "build_fundamentacao",
]

MODO_SHADOW = "shadow"
MODO_ATIVA = "ativa"

ROTULO_SHADOW = (
    "fundamentação localizada — a rota é decisão do consultor"
)

# Campos PRESCRITIVOS do enquadramento: sequenciam o caso, estimam prazo ou
# recomendam conduta. São exatamente os que o modo sombra não serve.
_CAMPOS_PRESCRITIVOS = (
    "caminho_regulatorio",
    "etapas",
    "prazos_estimados",
    "prazos_legais",
    "recomendacoes",
    "documentos_necessarios",
)

# Chave em `tenants.settings` que sobrescreve o default global por tenant.
_TENANT_SETTING = "rota_regulatoria_mode"


def rota_mode(db: Session, tenant_id: Optional[int]) -> str:
    """Modo da rota regulatória para o tenant: ``shadow`` (default) ou ``ativa``.

    Precedência: ``tenants.settings['rota_regulatoria_mode']`` → default global
    (``settings.ROTA_REGULATORIA_MODE``). O piloto roda em ``shadow``; um tenant
    que já opere com rota automática pode ser destravado sem deploy.
    """
    from app.core.config import settings as app_settings  # noqa: PLC0415

    default = (getattr(app_settings, "ROTA_REGULATORIA_MODE", MODO_SHADOW) or MODO_SHADOW).strip().lower()
    if tenant_id is None:
        return default
    try:
        from app.models.tenant import Tenant  # noqa: PLC0415

        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        conf = getattr(tenant, "settings", None) if tenant else None
        if isinstance(conf, dict):
            valor = str(conf.get(_TENANT_SETTING) or "").strip().lower()
            if valor in (MODO_SHADOW, MODO_ATIVA):
                return valor
    except Exception as exc:  # noqa: BLE001
        # Falha ao ler configuração NÃO pode destravar a rota: o default do
        # piloto é o comportamento conservador, e é ele que vale na dúvida.
        logger.warning("rota_shadow: falha ao ler settings do tenant %s: %s", tenant_id, exc)
    return default


def apply_shadow(
    db: Session, result: Any, *, tenant_id: Optional[int], agent_name: Optional[str]
) -> Any:
    """Aplica o modo sombra ao `result` de um job de legislação, na LEITURA.

    Não muda nada no banco: recebe o dict persistido e devolve a versão servível.
    Job de outro agente, modo ``ativa`` ou payload inesperado passam intactos.
    """
    if agent_name != "legislacao" or not isinstance(result, dict):
        return result
    if rota_mode(db, tenant_id) != MODO_SHADOW:
        return result

    servivel = {k: v for k, v in result.items() if k not in _CAMPOS_PRESCRITIVOS}
    servivel["rota_shadow"] = True
    servivel["rota_shadow_rotulo"] = ROTULO_SHADOW
    fundamentacao = build_fundamentacao(db, result, tenant_id=tenant_id)
    servivel["fundamentacao"] = fundamentacao
    # Honestidade de cobertura (item 10, sugestão da Isis 30/07): biblioteca
    # vazia é resposta honesta, mas MUDA. A tela mostrava um bloco em branco e o
    # consultor não sabia distinguir "não há norma aplicável" de "minha base não
    # cobre este órgão". Agora a lacuna é declarada.
    if not fundamentacao:
        servivel["cobertura_nota"] = (
            "Nenhuma norma localizada no corpus para este caso. Isso NÃO significa "
            "que não exista fundamentação aplicável — a base pode não cobrir o "
            "órgão/esfera exigidos. Confira na fonte oficial antes de usar."
        )
    return servivel


def build_fundamentacao(
    db: Session, result: dict[str, Any], *, tenant_id: Optional[int] = None
) -> list[dict[str, Any]]:
    """As normas localizadas, ao pé da letra, com fonte e alcance declarado.

    Cada item traz:

    * ``identificador``/``titulo``/``secao`` — como a norma se identifica;
    * ``trecho`` — o TEXTO da norma, literal, do próprio corpus (não paráfrase);
    * ``jurisdicao``/``uf``/``esfera`` — o alcance, declarado e não deduzido;
    * ``vigencia_conferida_em`` — quando o corpus verificou essa norma pela
      última vez (item 12). A honestidade estrutural: o sistema não afirma "está
      vigente", afirma "conferi nesta data" — que é o que ele de fato sabe;
    * ``fonte`` — ``SourceRef`` apontando o chunk, para a UI abrir no ponto.

    Sem `chunks_referenced` no job devolve ``[]``: biblioteca vazia é resposta
    honesta ("não localizei fundamentação"), muito melhor que citar norma de
    memória do modelo.
    """
    chunks = result.get("chunks_referenced")
    if not isinstance(chunks, list) or not chunks:
        return []

    ids = [c.get("id") for c in chunks if isinstance(c, dict) and c.get("id")]
    detalhes = _carregar_chunks(db, ids)

    out: list[dict[str, Any]] = []
    for c in chunks:
        if not isinstance(c, dict):
            continue
        det = detalhes.get(c.get("id")) or {}
        identificador = det.get("identifier") or c.get("identifier")
        titulo = det.get("title") or c.get("title")
        secao = det.get("section") or c.get("section")
        jurisdicao = det.get("jurisdiction")
        out.append({
            "chunk_id": c.get("id"),
            "identificador": identificador,
            "titulo": titulo,
            "secao": secao,
            "trecho": det.get("chunk_text"),
            "jurisdicao": jurisdicao,
            "uf": det.get("uf"),
            "orgao": det.get("agency"),
            "esfera": _esfera_da_jurisdicao(jurisdicao),
            "vigencia_conferida_em": det.get("vigencia_conferida_em"),
            "fonte": {
                "tipo": "legislacao",
                "ref": str(c.get("id")) if c.get("id") is not None else None,
                "descricao": " — ".join(
                    p for p in (titulo or identificador, secao) if p
                ) or None,
                "confianca": "alta",
            },
        })
    return out


_JURISDICAO_PARA_ESFERA = {
    "federal": "federal",
    "nacional": "federal",
    "estadual": "estadual",
    "municipal": "municipal",
}


def _esfera_da_jurisdicao(jurisdicao: Optional[str]) -> Optional[str]:
    """Alcance DECLARADO pelo corpus. Desconhecido continua desconhecido."""
    if not jurisdicao:
        return None
    return _JURISDICAO_PARA_ESFERA.get(jurisdicao.strip().lower())


def _carregar_chunks(db: Session, ids: list[Any]) -> dict[Any, dict[str, Any]]:
    """Texto literal + metadados dos chunks, em UMA query (nunca N+1).

    ``vigencia_conferida_em`` sai do `LegislationDocument.updated_at` quando o
    chunk vem de um diploma (é quando o corpus tocou aquele texto pela última
    vez); sem esse vínculo, cai para a data de indexação do chunk.
    """
    if not ids:
        return {}
    from sqlalchemy import text as sql_text  # noqa: PLC0415

    rows = db.execute(
        sql_text(
            """
            SELECT kc.id, kc.chunk_text, kc.title, kc.section, kc.identifier,
                   kc.jurisdiction, kc.uf, kc.agency, kc.created_at,
                   ld.updated_at AS doc_updated_at
            FROM knowledge_catalog kc
            LEFT JOIN legislation_documents ld
              ON kc.source_ref = CONCAT('legislation_documents:', ld.id::text)
            WHERE kc.id = ANY(:ids)
            """
        ),
        {"ids": list(ids)},
    ).mappings().all()

    out: dict[Any, dict[str, Any]] = {}
    for r in rows:
        conferida = r.get("doc_updated_at") or r.get("created_at")
        out[r["id"]] = {
            "chunk_text": r.get("chunk_text"),
            "title": r.get("title"),
            "section": r.get("section"),
            "identifier": r.get("identifier"),
            "jurisdiction": r.get("jurisdiction"),
            "uf": r.get("uf"),
            "agency": r.get("agency"),
            "vigencia_conferida_em": conferida.isoformat() if conferida else None,
        }
    return out
