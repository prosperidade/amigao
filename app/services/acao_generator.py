"""Geração de ``Acao`` a partir do diagnóstico (Ficha 07 §2).

Cada **ação de remediação** do diagnóstico vira uma ``Acao`` com
``tipo_triagem="pendente"`` (aguardando triagem do consultor). A fonte vem do
contrato #70 (``SourceRef``): cada risco carrega ``sources``; cada afirmação
``categoria="acao"`` carrega ``fontes``. Nunca inventar fonte — sem fonte
identificável, injeta uma ``SourceRef`` ``sem_fonte`` (honestidade explícita).

**Idempotência** (Ficha 07 §2): a ``dedupe_key`` é derivada de
``process + passivo + título`` — estável entre versões do diagnóstico. Regerar
não duplica; só cria o que ainda não existe.

**Não altera o passivo**: a ação só REFERENCIA o passivo via ``vinculo_passivo``
(JSON solto, sem FK). Nada aqui escreve em ``RegulatoryIssue``/achado.
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.acao import Acao, AcaoOrigem, AcaoStatus, AcaoTipoTriagem
from app.models.extracted_field_staging import (
    ExtractedFieldStaging,
    ExtractedFieldStatus,
)
from app.models.process import Process
from app.models.regulatory import RegulatoryDiagnosis

logger = get_logger(__name__)


def _dedupe_key(process_id: int, passivo_desc: str, titulo: str) -> str:
    """Chave estável por (processo, passivo, título). Cabe em String(120)."""
    raw = f"{passivo_desc.strip().lower()}|{titulo.strip().lower()}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]
    return f"p{process_id}:{digest}"


def _normalize_fontes(raw_fontes: Any, *, passivo_desc: str) -> list[dict[str, Any]]:
    """Normaliza a lista de fontes para o shape #70 (``SourceRef``).

    Tolerante: dicts válidos passam; entradas inválidas viram ``sem_fonte``.
    Lista vazia → uma ``SourceRef`` ``sem_fonte`` (nunca silenciar)."""
    # Import local pra evitar acoplar o módulo de schemas no import-time.
    from app.schemas.stage_output import SourceRef

    out: list[dict[str, Any]] = []
    if isinstance(raw_fontes, list):
        for item in raw_fontes:
            if not isinstance(item, dict):
                continue
            try:
                out.append(SourceRef(**item).model_dump())
            except Exception:
                # Fonte malformada — preserva o que dá como descrição, marca honesta.
                out.append(
                    SourceRef(
                        tipo="sem_fonte",
                        sem_fonte=True,
                        descricao=str(item)[:200],
                    ).model_dump()
                )
    if not out:
        out.append(
            SourceRef(
                tipo="sem_fonte",
                sem_fonte=True,
                descricao=f"Ação derivada de: {passivo_desc[:160]}" if passivo_desc else None,
            ).model_dump()
        )
    return out


def _iter_acoes_de_remediacao(content: dict[str, Any], diag_id: int):
    """Extrai (titulo, passivo_desc, fontes, vinculo) das ações do diagnóstico.

    Duas origens, ambas com fonte #70:
    - ``riscos[*].proximo_passo`` (ou ``mitigacao_sugerida`` legado) — o passivo
      é o próprio risco; fonte = ``risco.sources``.
    - ``afirmacoes[*]`` com ``categoria="acao"`` — fonte = ``afirmacao.fontes``.
    """
    riscos = content.get("riscos") if isinstance(content, dict) else None
    if isinstance(riscos, list):
        for idx, risco in enumerate(riscos):
            if not isinstance(risco, dict):
                continue
            titulo = (risco.get("proximo_passo") or risco.get("mitigacao_sugerida") or "").strip()
            if not titulo:
                continue
            passivo_desc = (
                risco.get("risco_identificado") or risco.get("descricao") or ""
            ).strip()
            yield {
                "titulo": titulo,
                "passivo_desc": passivo_desc,
                "fontes": risco.get("sources"),
                "vinculo": {
                    "tipo": "risco",
                    "ref": f"diag{diag_id}:risco:{idx}",
                    "descricao": passivo_desc or None,
                },
            }

    afirmacoes = content.get("afirmacoes") if isinstance(content, dict) else None
    if isinstance(afirmacoes, list):
        for idx, af in enumerate(afirmacoes):
            if not isinstance(af, dict):
                continue
            if af.get("categoria") != "acao":
                continue
            titulo = (af.get("texto") or "").strip()
            if not titulo:
                continue
            yield {
                "titulo": titulo,
                "passivo_desc": titulo,
                "fontes": af.get("fontes"),
                "vinculo": {
                    "tipo": "afirmacao",
                    "ref": f"diag{diag_id}:afirmacao:{idx}",
                    "descricao": titulo[:160],
                },
            }


def latest_diagnosis(db: Session, *, process_id: int, tenant_id: int) -> RegulatoryDiagnosis | None:
    """Versão mais recente do diagnóstico do processo (ou None)."""
    return (
        db.query(RegulatoryDiagnosis)
        .filter(
            RegulatoryDiagnosis.process_id == process_id,
            RegulatoryDiagnosis.tenant_id == tenant_id,
        )
        .order_by(RegulatoryDiagnosis.version.desc())
        .first()
    )


def generate_acoes_from_diagnosis(
    db: Session,
    *,
    process: Process,
    tenant_id: int,
) -> tuple[list[Acao], int, int | None]:
    """Gera ações ``pendente`` a partir do diagnóstico mais recente do processo.

    Idempotente: pula o que já existe (por ``dedupe_key``). Não comita — o
    caller decide a transação. Retorna ``(criadas, puladas, versao_diagnostico)``.
    """
    diag = latest_diagnosis(db, process_id=process.id, tenant_id=tenant_id)
    if diag is None:
        return [], 0, None

    content = diag.content if isinstance(diag.content, dict) else {}

    # Chaves já existentes deste processo — evita 1 query por candidato.
    existing_keys = {
        row[0]
        for row in db.query(Acao.dedupe_key)
        .filter(
            Acao.tenant_id == tenant_id,
            Acao.process_id == process.id,
            Acao.dedupe_key.isnot(None),
        )
        .all()
    }

    created: list[Acao] = []
    skipped = 0
    seen_this_run: set[str] = set()

    for item in _iter_acoes_de_remediacao(content, diag.id):
        key = _dedupe_key(process.id, item["passivo_desc"], item["titulo"])
        if key in existing_keys or key in seen_this_run:
            skipped += 1
            continue
        seen_this_run.add(key)

        acao = Acao(
            tenant_id=tenant_id,
            process_id=process.id,
            titulo=item["titulo"],
            origem=AcaoOrigem.diagnostico,
            origem_descricao=item["passivo_desc"] or None,
            origem_fontes=_normalize_fontes(item["fontes"], passivo_desc=item["passivo_desc"]),
            vinculo_passivo=item["vinculo"],
            status=AcaoStatus.a_fazer,
            tipo_triagem=AcaoTipoTriagem.pendente,
            dedupe_key=key,
        )
        db.add(acao)
        created.append(acao)

    if created:
        db.flush()
        logger.info(
            "acoes_generated",
            extra={
                "process_id": process.id,
                "tenant_id": tenant_id,
                "diagnosis_version": diag.version,
                "acoes_created": len(created),
                "acoes_skipped": skipped,
            },
        )

    return created, skipped, diag.version


# ---------------------------------------------------------------------------
# Ações nascidas da CONSOLIDAÇÃO (divergência não resolvida — decisão Isis opção b)
# ---------------------------------------------------------------------------

def _dedupe_key_divergencia(process_id: int, entity: str, hint: str | None, field: str) -> str:
    """Chave estável por (processo, destino da divergência). Cabe em String(120)."""
    raw = f"{entity}|{hint or ''}|{field}".strip().lower()
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]
    return f"p{process_id}:divg:{digest}"


def _scalar(row: ExtractedFieldStaging) -> Any:
    fv = row.field_value
    return fv.get("value") if isinstance(fv, dict) and "value" in fv else fv


def generate_acoes_from_divergencias(
    db: Session,
    *,
    process: Process,
    tenant_id: int,
) -> tuple[list[Acao], int]:
    """Gera uma ``Acao`` ``pendente`` por divergência de transcrição NÃO resolvida.

    Consolidação parcial (decisão Isis, opção b): o divergente não bloqueia — os
    consistentes já gravaram; cada divergência pendente vira trabalho rastreável.
    Só ``divergente_transcricao`` (``divergente_fundo`` tem caminho próprio na
    matriz — não duplicar). Fonte = os valores concorrentes e seus documentos
    (Princípio 11; ``SourceRef``). Idempotente por ``dedupe_key``. Não comita.
    """
    from app.schemas.stage_output import SourceRef  # noqa: PLC0415

    rows = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process.id,
            ExtractedFieldStaging.status == ExtractedFieldStatus.divergente_transcricao,
        )
        .order_by(ExtractedFieldStaging.id.asc())
        .all()
    )
    if not rows:
        return [], 0

    # Agrupa por DESTINO: fontes concorrentes do mesmo campo → UMA ação.
    grupos: dict[tuple, list[ExtractedFieldStaging]] = {}
    for r in rows:
        key = ((r.target_entity or "").lower(), r.matricula_hint, r.target_field or r.field_name)
        grupos.setdefault(key, []).append(r)

    existing_keys = {
        row[0]
        for row in db.query(Acao.dedupe_key)
        .filter(
            Acao.tenant_id == tenant_id,
            Acao.process_id == process.id,
            Acao.dedupe_key.isnot(None),
        )
        .all()
    }

    created: list[Acao] = []
    # Guard intra-run (mesmo padrão do generate_acoes_from_diagnosis): o sha1
    # truncado é derivado de string com separador ingênuo — dois destinos
    # distintos podem colidir na MESMA execução e estourar uq_acoes_tenant_dedupe
    # no flush, derrubando a consolidação inteira.
    seen_this_run: set[str] = set()
    for (entity, hint, field), group in grupos.items():
        key = _dedupe_key_divergencia(process.id, entity, hint, field)
        if key in existing_keys or key in seen_this_run:
            continue
        seen_this_run.add(key)

        fontes: list[dict[str, Any]] = []
        partes: list[str] = []
        for g in group:
            valor = _scalar(g)
            doc = g.source_doc_type or "—"
            fontes.append(
                SourceRef(
                    tipo="documento",
                    ref=f"staging:{g.id}",
                    descricao=doc,
                    valor=str(valor) if valor is not None else None,
                ).model_dump()
            )
            partes.append(f"{doc}={valor}")
        if not fontes:
            fontes = [SourceRef(tipo="sem_fonte", sem_fonte=True).model_dump()]

        hint_txt = f" (matrícula {hint})" if hint else ""
        titulo = f"Resolver divergência de {field}{hint_txt}"
        origem_descricao = ("Divergência: " + " vs ".join(partes)) if partes else None

        acao = Acao(
            tenant_id=tenant_id,
            process_id=process.id,
            titulo=titulo,
            origem=AcaoOrigem.consolidacao,
            origem_descricao=(origem_descricao or None) and origem_descricao[:255],
            origem_fontes=fontes,
            vinculo_passivo={
                "tipo": "divergencia",
                "ref": f"staging:{group[0].id}",
                "descricao": origem_descricao,
            },
            status=AcaoStatus.a_fazer,
            tipo_triagem=AcaoTipoTriagem.pendente,
            dedupe_key=key,
        )
        db.add(acao)
        created.append(acao)

    if created:
        db.flush()
        logger.info(
            "acoes_from_divergencias",
            extra={
                "process_id": process.id,
                "tenant_id": tenant_id,
                "acoes_created": len(created),
            },
        )

    return created, len(created)


# ---------------------------------------------------------------------------
# Ação nascida do SELO "Correto, pendente de oficialização" (Ficha 07 §3.4/§9)
# ---------------------------------------------------------------------------

# Rótulos pt-BR dos campos seláveis (título da ação e UI). Fallback: o nome cru.
FIELD_LABELS: dict[str, str] = {
    # Matrícula
    "numero_matricula": "Nº da matrícula",
    "cartorio": "Cartório",
    "registro_livro_folha_ficha": "Registro (livro/folha/ficha)",
    "codigo_incra_sncr": "Código INCRA/SNCR",
    "nirf_cib": "NIRF/CIB",
    "area_ha": "Área da matrícula (ha)",
    "denominacao_imovel": "Denominação do imóvel",
    "geo_certificacao_codigo": "Nº SIGEF (certificação)",
    "geo_certificacao_status": "Status da certificação SIGEF",
    "averbacao_app": "Averbação de APP",
    "averbacao_rl": "Averbação de Reserva Legal",
    "onus_gravames": "Ônus e gravames",
    "proprietarios": "Proprietários",
    # Imóvel
    "registry_number": "Matrícula (imóvel)",
    "car_code": "Nº CAR",
    "car_status": "Status do CAR",
    "ccir": "CCIR",
    "nirf": "NIRF",
    "total_area_ha": "Área total (ha)",
    "area_documental_ha": "Área documental (ha)",
    "area_grafica_ha": "Área gráfica (ha)",
    "app_area_ha": "Área de APP (ha)",
    "rl_status": "Situação da Reserva Legal",
    "municipality": "Município",
    "state": "UF",
    "biome": "Bioma",
    "tipologia": "Tipologia",
    # Cliente
    "full_name": "Nome completo",
    "legal_name": "Razão social",
    "cpf_cnpj": "CPF/CNPJ",
    "email": "E-mail",
    "phone": "Telefone",
    "secondary_phone": "Telefone secundário",
    "birth_date": "Data de nascimento",
}


def field_label(field: str) -> str:
    return FIELD_LABELS.get(field, field)


def _dedupe_key_oficializacao(process_id: int, entity: str, entity_id: int, field: str) -> str:
    """Chave estável por DESTINO do selo — nunca por valor/estado do selo.

    Oscilar pendente→validado→pendente reusa a MESMA chave: a ação não duplica
    e, se o consultor a dispensou, a linha dispensada (mesma chave) bloqueia a
    recriação — o sistema não desfaz triagem humana (Ficha 07 §9)."""
    raw = f"{entity}|{entity_id}|{field}".strip().lower()
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]
    return f"p{process_id}:ofic:{digest}"


def generate_acao_oficializacao(
    db: Session,
    *,
    process: Process,
    tenant_id: int,
    entity: str,
    entity_id: int,
    field: str,
) -> tuple[Acao | None, bool]:
    """Cria a ação "Atualização de arquivos oficiais — {campo}" ao selar
    ``pendente_oficializacao`` (Ficha 07 §9). 1 ação POR CAMPO.

    Idempotente por ``dedupe_key`` (destino, não valor): existente — em qualquer
    triagem, inclusive ``dispensada`` — bloqueia. Não comita — o caller decide a
    transação. Retorna ``(acao_ou_None, criada)``."""
    from app.schemas.stage_output import SourceRef  # noqa: PLC0415

    key = _dedupe_key_oficializacao(process.id, entity, entity_id, field)
    exists = (
        db.query(Acao.id)
        .filter(Acao.tenant_id == tenant_id, Acao.dedupe_key == key)
        .first()
    )
    if exists is not None:
        return None, False

    rotulo = field_label(field)
    acao = Acao(
        tenant_id=tenant_id,
        process_id=process.id,
        titulo=f"Atualização de arquivos oficiais — {rotulo}",
        origem=AcaoOrigem.oficializacao,
        origem_descricao=(
            f"Campo '{rotulo}' selado como 'Correto, pendente de oficialização'"
        ),
        origem_fontes=[
            SourceRef(
                tipo="atendimento",
                ref=f"selo:{entity}:{entity_id}:{field}",
                descricao="Selo aplicado pelo consultor no dossiê do processo",
            ).model_dump()
        ],
        vinculo_passivo={
            "tipo": "oficializacao",
            "ref": f"{entity}:{entity_id}:{field}",
            "descricao": f"Verdade técnica ainda não oficializada: {rotulo}",
        },
        status=AcaoStatus.a_fazer,
        tipo_triagem=AcaoTipoTriagem.pendente,
        dedupe_key=key,
    )
    db.add(acao)
    db.flush()
    logger.info(
        "acao_oficializacao_created",
        extra={
            "process_id": process.id,
            "tenant_id": tenant_id,
            "entity": entity,
            "entity_id": entity_id,
            "field": field,
        },
    )
    return acao, True
