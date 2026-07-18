"""
Ficha 01 / FASE 4 — decisão do consultor + consolidação na base real.

Princípio: "agentes propõem (staging), consultor decide (Alertas), sistema grava
(base)". Tudo DETERMINÍSTICO (sem LLM). Nada é gravado sem decisão explícita do
consultor (status=aceito). Auditável.

- ``decide_field`` — aceitar / escolher_fonte / editar / rejeitar (1 campo).
- ``bulk_accept_consistentes`` — aceita em lote os status=consistente.
- ``consolidate_process`` — grava o staging aceito em Client/Property/Matricula.
  Idempotente; NÃO sobrescreve ``Property.total_area_ha`` (área = derivada da
  soma das matrículas, Ficha 01).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import Date, Float, Integer, Numeric, String
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.extracted_field_staging import (
    ExtractedFieldStaging,
    ExtractedFieldStatus,
)
from app.services.audit_hash import stamp_audit_hash
from app.services.inconsistency_matrix import (
    _clean_matricula_hint,
    _to_float_br,
    is_area_plausible,
    norm_compare,
    parse_area_ha,
)

logger = logging.getLogger(__name__)

# Colunas de área: convertidas pela porta ÚNICA parse_area_ha (BR/US/m² + dict).
_AREA_COLUMNS = {"area_ha", "app_area_ha", "area_grafica_ha", "area_documental_ha", "total_area_ha"}

_DIVERGENTES = {
    ExtractedFieldStatus.divergente_transcricao,
    ExtractedFieldStatus.divergente_fundo,
}


# ---------------------------------------------------------------------------
# Allowlist de colunas graváveis por entidade (+ aliases staging→coluna)
# ---------------------------------------------------------------------------
# total_area_ha NÃO está na lista do imóvel: a área do imóvel é derivada da soma
# das matrículas (Property.area_total_matriculas()) — nunca sobrescrita aqui.
_CLIENTE_FIELDS = {"full_name", "legal_name", "cpf_cnpj", "email", "phone", "secondary_phone", "birth_date"}
_CLIENTE_ALIAS = {"document": "cpf_cnpj", "address": None}

# rl_status entra na allowlist (antes era descartado: rl_declarada_ha → imovel.rl_status
# caía em `ignorados`, deixando o Hub com "—" em Reserva Legal). app_area_ha já estava.
_IMOVEL_FIELDS = {"car_code", "car_status", "municipality", "state", "app_area_ha",
                  "area_grafica_ha", "area_documental_ha", "biome", "ccir", "nirf",
                  "tipologia", "rl_status"}
_IMOVEL_ALIAS: dict[str, Optional[str]] = {}

_MATRICULA_FIELDS = {"numero_matricula", "cartorio", "registro_livro_folha_ficha",
                     "codigo_incra_sncr", "nirf_cib", "area_ha", "denominacao_imovel",
                     "geo_certificacao_codigo", "geo_certificacao_status",
                     "averbacao_app", "averbacao_rl", "onus_gravames", "proprietarios",
                     # Cadeia (#60): sinais registrais da linhagem gravam na matrícula.
                     "registro_anterior", "denominacao_anterior"}
_MATRICULA_ALIAS: dict[str, Optional[str]] = {}

# Guard fantasma (Sprint 4): só documentos que legitimamente DECLARAM matrícula
# criam Matricula nova na consolidação. `sigef` fica de fora da criação (só
# atualiza existente): foi o vetor real do caso 13 — certidão de embargo e
# contrato PRAD mal-classificados como `sigef` criaram a "matrícula" 492262
# (nº da certidão). Hint órfão fica no staging (ignorados) — o cadastro manual
# (POST /properties/{id}/matriculas) segue sendo a via legítima.
_MATRICULA_CREATOR_DOC_TYPES = {"matricula", "ccir", "itr", "car"}


def _raw_value(row: ExtractedFieldStaging) -> Any:
    """Valor efetivo da decisão: decided_value se houver, senão a fonte."""
    src = row.decided_value if row.decided_value is not None else row.field_value
    if isinstance(src, dict) and "value" in src:
        return src["value"]
    return src


def _stringify_structured(value: Any) -> str:
    """Serializa dict/list em texto legível para colunas textuais.

    O extrator às vezes stage valores estruturados (ex.: ``averbacao_app`` como
    ``{"area": ..., "referencia": ...}``); gravar um dict numa coluna ``Text``
    estoura o driver (``psycopg2: can't adapt type 'dict'``) e derruba a
    consolidação inteira. Degradar com elegância: vira "chave: valor · …"."""
    if isinstance(value, dict):
        return " · ".join(f"{k}: {_stringify_structured(v)}" for k, v in value.items())
    if isinstance(value, list):
        return "; ".join(_stringify_structured(v) for v in value)
    return str(value)


def _coerce(value: Any, column_type: Any, column_name: str = "", unidade: Any = None) -> Any:
    """Coage o valor para o tipo da coluna (área PT-BR → float, data → date).

    Área (``_AREA_COLUMNS``) passa pela porta ÚNICA ``parse_area_ha`` (lida BR,
    US, m² e dict) e por validação de ordem de grandeza: área implausível NÃO é
    gravada como fato (devolve None → vai para ``ignorados``)."""
    if value is None:
        return None
    if column_name in _AREA_COLUMNS:
        ha = parse_area_ha(value, unidade)
        if ha is not None and not is_area_plausible(ha):
            return None  # fora de escala — não grava como fato (Item 1)
        return ha
    if isinstance(column_type, (Float, Numeric)):
        return _to_float_br(value)
    if isinstance(column_type, Integer):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None
    if isinstance(column_type, Date):
        if isinstance(value, (date, datetime)):
            return value if isinstance(value, date) else value.date()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(str(value).strip(), fmt).date()
            except ValueError:
                continue
        return None
    # Coluna textual (String/Text) recebendo estrutura → serializa, nunca crasha.
    # (Colunas JSON portáveis NÃO são String → preservam o dict/list.)
    if isinstance(value, (dict, list)) and isinstance(column_type, String):
        return _stringify_structured(value)
    return value


# ---------------------------------------------------------------------------
# Seleção de fonte vencedora (multi-fonte → âncora SIGEF; Ficha 05)
# ---------------------------------------------------------------------------
_CONF_RANK = {"high": 3, "medium": 2, "low": 1}
# Campos cuja âncora, sem escolha explícita do consultor, é o SIGEF (Ficha 05).
_SIGEF_ANCHORED = {"area_ha", "denominacao_imovel"}


def _field_value_scalar(row: ExtractedFieldStaging) -> Any:
    fv = row.field_value
    return fv.get("value") if isinstance(fv, dict) and "value" in fv else fv


def _is_consultor_edit(row: ExtractedFieldStaging) -> bool:
    """Edição manual: decided_value diverge do field_value extraído (fonte=consultor)."""
    if not isinstance(row.decided_value, dict) or "value" not in row.decided_value:
        return False
    return _norm_cmp(row.decided_value.get("value")) != _norm_cmp(_field_value_scalar(row))


def _fonte_of(row: ExtractedFieldStaging) -> str:
    """Origem efetiva do valor: 'consultor' se editado, senão o doc de origem."""
    if _is_consultor_edit(row):
        return "consultor"
    return (row.source_doc_type or "—").lower()


def _pick_winner(rows: list[ExtractedFieldStaging], *, prefer_sigef: bool) -> ExtractedFieldStaging:
    """Vencedor do grupo (mesmo destino): edição do consultor > âncora SIGEF >
    confiança > menor id. ``escolher_fonte`` já rejeita irmãos, então grupos com
    >1 sobrevivente são campos consistentes (mesmo valor) — a âncora só fixa a
    proveniência."""
    def score(r: ExtractedFieldStaging) -> tuple:
        edited = _is_consultor_edit(r)
        sigef = (r.source_doc_type or "").lower() == "sigef"
        conf = _CONF_RANK.get((r.confidence or "").lower(), 0)
        return (1 if edited else 0, 1 if (prefer_sigef and sigef) else 0, conf, -(r.id or 0))
    return max(rows, key=score)


def _norm_cmp(value: Any) -> Any:
    """Normaliza p/ comparação de igualdade (string trim/lower; número como float)."""
    if isinstance(value, str):
        return value.strip().lower()
    return value


def _group_conflict_values(rows: list[ExtractedFieldStaging], target_field: str) -> list[Any]:
    """Valores DISTINTOS (normalizados) de um grupo de staging aceito (Sprint 4).

    A consolidação NUNCA escolhe silenciosamente entre dois valores completos
    conflitantes de documentos distintos — isso é decisão do consultor (Ficha
    §3.3: escolher fonte / digitar / criar ação). `_pick_winner` só desempata o
    que é o MESMO valor em fontes diferentes (proveniência), não conteúdo.
    Área normaliza pela porta única (349,9022 ≡ 349.9022 não é conflito).
    """
    seen: dict[str, Any] = {}
    for r in rows:
        v = _raw_value(r)
        if target_field in _AREA_COLUMNS:
            unidade = r.field_value.get("unidade") if isinstance(r.field_value, dict) else None
            parsed = parse_area_ha(v, unidade)
            key = f"ha:{round(parsed, 4)}" if parsed is not None else f"raw:{_norm_cmp(v)}"
        elif isinstance(v, (dict, list)):
            key = json.dumps(v, sort_keys=True, ensure_ascii=False, default=str)
        else:
            # Divergência de TEXTO usa a normalização da skill da Isis (casefold,
            # acentos, apóstrofos, pontuação, UF de município): "SÃO JOÃO
            # D'ALIANÇA" ≡ "São João D'aliança-GO" NÃO vira divergência/ação.
            key = f"s:{norm_compare(v, field=target_field)}"
        seen.setdefault(key, v)
    return list(seen.values())


def _values_differ(old: Any, new: Any) -> bool:
    """True se old≠new além de tolerância (float: ~0,01%; idempotência protegida)."""
    if old is None or new is None:
        return old is not new
    if isinstance(old, float) and isinstance(new, (int, float)):
        base = max(abs(old), abs(new), 1e-9)
        return abs(old - float(new)) / base > 1e-4
    return _norm_cmp(old) != _norm_cmp(new)


# ---------------------------------------------------------------------------
# Decisão por campo
# ---------------------------------------------------------------------------

def decide_field(
    db: Session, *, tenant_id: int, process_id: int, field_id: int,
    acao: str, valor: Any = None, fonte: Optional[str] = None, user_id: Optional[int] = None,
) -> ExtractedFieldStaging:
    row = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.id == field_id,
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Campo de staging não encontrado.")

    irmaos: list[int] = []
    if acao == "rejeitar":
        row.status = ExtractedFieldStatus.rejeitado
        row.decided_value = None
    elif acao == "editar":
        if valor is None:
            raise HTTPException(status_code=422, detail="'valor' é obrigatório na ação 'editar'.")
        row.status = ExtractedFieldStatus.aceito
        row.decided_value = {"value": valor}
    elif acao == "aceitar":
        # Gate: divergente_transcricao exige escolha ativa (escolher_fonte/editar).
        if row.status == ExtractedFieldStatus.divergente_transcricao:
            raise HTTPException(
                status_code=422,
                detail="Campo divergente (transcrição) exige 'escolher_fonte' ou 'editar', não 'aceitar'.",
            )
        # Captura ANTES de sobrescrever o status: divergente_fundo é aceito como
        # ACHADO (issue/escopo já roteado pela matriz) — sem gravação automática
        # de valor. (Bug: checar após `= aceito` tornava a condição sempre falsa.)
        era_divergente_fundo = row.status == ExtractedFieldStatus.divergente_fundo
        row.status = ExtractedFieldStatus.aceito
        row.decided_value = None if era_divergente_fundo else {"value": _raw_value(row)}
    elif acao == "escolher_fonte":
        row.status = ExtractedFieldStatus.aceito
        row.decided_value = {"value": _raw_value(row)}
        irmaos = _reject_siblings(db, tenant_id, process_id, row)
    elif acao == "criar_acao":
        # Fase 0 (gap-analysis Ficha 07, item 6) — 3º caminho EXPLÍCITO da
        # divergência (Ficha §3.3): o consultor escolhe "criar ação" agora,
        # em vez de deixar a Consolidação decidir por trás. Reusa o mesmo
        # gerador que já roda automaticamente na Consolidação — dedupe_key
        # garante idempotência (rodar aqui não duplica se rodar de novo
        # depois). O campo continua `divergente_transcricao`: a decisão do
        # consultor não é "resolver o valor", é "virar trabalho rastreável".
        if row.status != ExtractedFieldStatus.divergente_transcricao:
            raise HTTPException(
                status_code=422,
                detail="'criar_acao' só se aplica a campo divergente (transcrição).",
            )
        from app.models.process import Process  # noqa: PLC0415
        from app.services.acao_generator import (  # noqa: PLC0415
            generate_acoes_from_divergencias,
        )

        process_obj = (
            db.query(Process)
            .filter(Process.id == process_id, Process.tenant_id == tenant_id)
            .first()
        )
        if process_obj is None:
            raise HTTPException(status_code=404, detail="Processo não encontrado.")
        _acoes, acoes_criadas = generate_acoes_from_divergencias(
            db, process=process_obj, tenant_id=tenant_id
        )
        row.decided_by_user_id = user_id
        row.decided_at = datetime.now(UTC)
        db.flush()
        _audit(db, tenant_id, process_id, user_id, "staging_decidir", {
            "field_id": row.id, "acao": acao, "status": row.status.value,
            "target_entity": row.target_entity, "target_field": row.target_field,
            "matricula_hint": row.matricula_hint, "acoes_criadas": acoes_criadas,
            "staging_origin_ai_job_id": row.ai_job_id,
        })
        db.commit()
        return row
    else:
        raise HTTPException(status_code=422, detail=f"Ação desconhecida: {acao}")

    row.decided_by_user_id = user_id
    row.decided_at = datetime.now(UTC)
    db.flush()

    _audit(db, tenant_id, process_id, user_id, "staging_decidir", {
        "field_id": row.id, "acao": acao, "status": row.status.value,
        "target_entity": row.target_entity, "target_field": row.target_field,
        "matricula_hint": row.matricula_hint, "fonte": fonte,
        "irmaos_rejeitados": irmaos, "staging_origin_ai_job_id": row.ai_job_id,
    })
    db.commit()
    return row


def _reject_siblings(db: Session, tenant_id: int, process_id: int, row: ExtractedFieldStaging) -> list[int]:
    """Rejeita campos irmãos (mesmo destino) de outras fontes — 'escolher a fonte'."""
    q = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            ExtractedFieldStaging.id != row.id,
            ExtractedFieldStaging.target_entity == row.target_entity,
            ExtractedFieldStaging.target_field == row.target_field,
        )
    )
    if row.matricula_hint is None:
        q = q.filter(ExtractedFieldStaging.matricula_hint.is_(None))
    else:
        q = q.filter(ExtractedFieldStaging.matricula_hint == row.matricula_hint)

    rejeitados: list[int] = []
    for sib in q.all():
        if sib.status in (ExtractedFieldStatus.aceito,):
            continue
        sib.status = ExtractedFieldStatus.rejeitado
        rejeitados.append(sib.id)
    return rejeitados


def bulk_accept_consistentes(
    db: Session, *, tenant_id: int, process_id: int, user_id: Optional[int] = None,
) -> list[int]:
    """Aceita em lote TODOS os campos status=consistente. Divergentes NUNCA entram
    no lote (exigem escolha ativa)."""
    rows = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            ExtractedFieldStaging.status == ExtractedFieldStatus.consistente,
        )
        .all()
    )
    ids: list[int] = []
    now = datetime.now(UTC)
    for row in rows:
        row.status = ExtractedFieldStatus.aceito
        row.decided_value = {"value": _raw_value(row)}
        row.decided_by_user_id = user_id
        row.decided_at = now
        ids.append(row.id)
    db.flush()
    if ids:
        _audit(db, tenant_id, process_id, user_id, "staging_aceitar_consistentes",
               {"field_ids": ids, "count": len(ids)})
    db.commit()
    return ids


# ---------------------------------------------------------------------------
# Consolidação na base real
# ---------------------------------------------------------------------------

def consolidate_process(
    db: Session, *, tenant_id: int, process_id: int, user_id: Optional[int] = None,
) -> dict[str, Any]:
    from app.models.process import Process  # noqa: PLC0415

    process = (
        db.query(Process)
        .filter(Process.id == process_id, Process.tenant_id == tenant_id)
        .first()
    )
    if process is None:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")

    accepted = (
        db.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            ExtractedFieldStaging.status == ExtractedFieldStatus.aceito,
        )
        .order_by(ExtractedFieldStaging.id.asc())
        .all()
    )

    writes: list[dict[str, Any]] = []
    ignorados: list[str] = []
    reconciliacoes: list[dict[str, Any]] = []
    cliente_tocado = False
    imovel_tocado = False
    mat_criadas = 0
    mat_atualizadas = 0

    client = _load_client(db, tenant_id, process.client_id) if process.client_id else None
    prop = _load_property(db, tenant_id, process.property_id) if process.property_id else None

    # Agrupa por DESTINO (entidade, [hint], campo). Múltiplas fontes para o mesmo
    # destino → uma vencedora por âncora (Ficha 05). Achados (decided_value None =
    # divergente_fundo aceito como achado) NÃO gravam valor — só roteados na matriz.
    grupos: dict[tuple, list[ExtractedFieldStaging]] = {}
    matricula_estabelecida: set[str] = set()
    for row in accepted:
        entity = (row.target_entity or "").lower()
        if entity == "matricula" and row.field_name == "matricula_listada":
            if row.matricula_hint:
                matricula_estabelecida.add(row.matricula_hint)
            continue
        if row.decided_value is None:  # achado (divergente_fundo) — não grava valor
            continue
        if _raw_value(row) is None:
            continue
        key = ((entity, row.matricula_hint, row.target_field)
               if entity == "matricula" else (entity, row.target_field))
        grupos.setdefault(key, []).append(row)

    # cache de matrículas por hint (upsert idempotente). Miss com criação vetada
    # fica cacheado como None — um grupo posterior COM doc criador re-tenta.
    mat_cache: dict[str, tuple[Any, bool]] = {}

    def _ensure_matricula(hint: str, allow_create: bool = True):
        nonlocal mat_criadas, mat_atualizadas
        cached = mat_cache.get(hint)
        if cached is not None and (cached[0] is not None or not allow_create):
            return cached[0]
        primeira_vez = cached is None
        mat, created = _upsert_matricula(db, tenant_id, prop.id, hint, allow_create=allow_create)
        mat_cache[hint] = (mat, created)
        if mat is not None:
            if created:
                mat_criadas += 1
            elif primeira_vez:
                mat_atualizadas += 1
        return mat

    # matrícula citada no CAR mas sem campo próprio aceito ainda existe na base
    # (o CAR é doc criador — guard fantasma não se aplica aqui).
    for hint in matricula_estabelecida:
        if prop is not None:
            _ensure_matricula(hint)

    divergencias_devolvidas: list[dict[str, Any]] = []

    for key, rows in grupos.items():
        target_field = key[-1]
        winner = _pick_winner(rows, prefer_sigef=(target_field in _SIGEF_ANCHORED))
        entity = key[0]

        # ── Resolve o objeto de destino (guard fantasma para matrícula) ─────
        obj: Any = None
        allowed: set[str]
        alias: dict[str, Optional[str]]
        if entity == "cliente" and client is not None:
            obj, allowed, alias = client, _CLIENTE_FIELDS, _CLIENTE_ALIAS
        elif entity == "imovel" and prop is not None:
            obj, allowed, alias = prop, _IMOVEL_FIELDS, _IMOVEL_ALIAS
        elif entity == "matricula" and prop is not None:
            hint = winner.matricula_hint
            if not hint:
                ignorados.append(f"matricula sem matricula_hint: {target_field}")
                continue
            # Guard fantasma: hint vindo só de tipos que não declaram matrícula
            # (sigef, outro…) não CRIA matrícula — atualiza se já existir.
            allow_create = any(
                (r.source_doc_type or "").lower() in _MATRICULA_CREATOR_DOC_TYPES
                or _is_consultor_edit(r)
                for r in rows
            )
            obj = _ensure_matricula(hint, allow_create=allow_create)
            if obj is None:
                ignorados.append(
                    f"matricula {hint}.{target_field} (hint de '{(winner.source_doc_type or '—')}' "
                    "não cria matrícula — guard fantasma; cadastre-a manualmente se for real)"
                )
                continue
            allowed, alias = _MATRICULA_FIELDS, _MATRICULA_ALIAS
        else:
            ignorados.append(f"{entity or '—'}: sem destino (target_field={target_field})")
            continue

        # ── Coerência matriz×consolidação (Sprint 4 / caso 13) ──────────────
        # Dois valores completos conflitantes de docs distintos no MESMO destino
        # (ex.: 2 CCIRs na matrícula 2923) NÃO são desempatados aqui: voltam a
        # `divergente_transcricao` — a matriz/Conferência acusa e a divergência
        # vira Ação (generate_acoes_from_divergencias, logo abaixo). Duas saídas
        # NÃO passam pelo guard: edição explícita do consultor É decisão (vence
        # e grava); e destino JÁ consolidado (human_validated/pendente_oficializacao)
        # segue o caminho de RECONCILIAÇÃO da Ficha 05 dentro de _write_entity —
        # a decisão anterior do consultor não é rebaixada a divergência nova.
        col = alias.get(target_field, target_field) if target_field in alias else target_field
        fs_atual = dict(getattr(obj, "field_sources", None) or {})
        ja_consolidado = col is not None and fs_atual.get(col) in (
            "human_validated", "pendente_oficializacao"
        )
        if not _is_consultor_edit(winner) and not ja_consolidado:
            conflito = _group_conflict_values(rows, target_field)
            if len(conflito) > 1:
                for r in rows:
                    r.status = ExtractedFieldStatus.divergente_transcricao
                    r.decided_value = None
                divergencias_devolvidas.append({
                    "entity": entity, "matricula_hint": key[1] if len(key) == 3 else None,
                    "field": target_field, "valores": [_ser(v) for v in conflito],
                    "staging_ids": [r.id for r in rows],
                })
                continue

        value = _raw_value(winner)
        fonte = _fonte_of(winner)
        unidade = winner.field_value.get("unidade") if isinstance(winner.field_value, dict) else None
        wrote = _write_entity(obj, winner, value, fonte, unidade,
                              allowed, alias, writes, ignorados, reconciliacoes)
        if wrote and entity == "cliente":
            cliente_tocado = True
        elif wrote and entity == "imovel":
            imovel_tocado = True

    db.flush()

    # ── Consolidação PARCIAL (decisão Isis, opção b) ────────────────────────
    # Divergente de transcrição NÃO resolvido não bloqueia: os consistentes já
    # gravaram acima; cada divergência pendente vira uma Ação (rastreável, com
    # fonte). divergente_fundo tem caminho próprio (achado roteado pela matriz)
    # — não duplicar aqui. Idempotente via dedupe_key. NÃO grava valor.
    from app.services.acao_generator import generate_acoes_from_divergencias  # noqa: PLC0415

    acoes, acoes_criadas = generate_acoes_from_divergencias(
        db, process=process, tenant_id=tenant_id
    )

    # ── Ponte RL matrícula→imóvel (Princípio 11 — derivar com fonte) ────────
    # O Hub lê prop.rl_status; a RL pode chegar só como averbação na matrícula.
    # Se o imóvel não tem RL e ≥1 matrícula tem averbação de RL, derivamos
    # 'averbada' marcando a origem como derivada (não human_validated): é
    # transparente e o consultor pode corrigir. APP NÃO é derivada de texto
    # livre (averbacao_app→app_area_ha exigiria inventar um número).
    if prop is not None and not (prop.rl_status or "").strip():
        if any((m.averbacao_rl or "").strip() for m in prop.matriculas):
            prop.rl_status = "averbada"
            fs_prev = dict(getattr(prop, "field_sources", None) or {})
            prop.field_sources = {**fs_prev, "rl_status": "derived_matricula"}
            imovel_tocado = True
            db.flush()

    # ── Contrato da Conferência: rejeitar staging DESFAZ o efeito (forense Isis)
    # Matrícula materializada de staging depois rejeitada por completo é desativada
    # e SAI da soma; reaceitar reativa. Roda depois dos writes (a soma abaixo já
    # reflete). Só toca matrículas com hint na staging deste processo.
    mat_desativadas, mat_reativadas = _reconcile_matricula_activation(
        db, tenant_id, process_id, prop, accepted
    )

    area_total = prop.area_total_matriculas() if prop is not None else None

    if (writes or reconciliacoes or acoes_criadas or divergencias_devolvidas
            or mat_desativadas or mat_reativadas):
        _audit(db, tenant_id, process_id, user_id, "consolidar", {
            "process_id": process_id, "campos_gravados": len(writes),
            "matriculas_criadas": mat_criadas, "matriculas_atualizadas": mat_atualizadas,
            "matriculas_desativadas": mat_desativadas,
            "matriculas_reativadas": mat_reativadas,
            "acoes_criadas": acoes_criadas,
            "acoes": [{"id": a.id, "titulo": a.titulo} for a in acoes],
            "writes": writes, "reconciliacoes": reconciliacoes,
            "divergencias_devolvidas": divergencias_devolvidas,
        })
    db.commit()

    return {
        "process_id": process_id,
        "campos_gravados": len(writes),
        "matriculas_criadas": mat_criadas,
        "matriculas_atualizadas": mat_atualizadas,
        "cliente_atualizado": cliente_tocado,
        "imovel_atualizado": imovel_tocado,
        "area_total_matriculas": area_total,
        "area_total_nota": prop.nota_soma_matriculas() if prop is not None else None,
        "acoes_criadas": acoes_criadas,
        "matriculas_desativadas": mat_desativadas,
        "matriculas_reativadas": mat_reativadas,
        "writes": writes,
        "ignorados": ignorados,
        "reconciliacoes": reconciliacoes,
        "divergencias_devolvidas": divergencias_devolvidas,
    }


def _write_entity(
    obj: Any, row: ExtractedFieldStaging, value: Any, fonte: str, unidade: Any,
    allowed: set[str], alias: dict[str, Optional[str]],
    writes: list[dict[str, Any]], ignorados: list[str], reconciliacoes: list[dict[str, Any]],
) -> bool:
    """Grava 1 campo no objeto ORM (UPSERT versionado, Ficha 05).

    - allowlist + alias + coerção por tipo (área pela porta única).
    - RECONCILIAÇÃO: se o campo JÁ foi consolidado (human_validated) e o novo
      valor diverge, NÃO sobrescreve — devolve como reconciliação (vira alerta).
    - Idempotente: re-gravar o MESMO valor é no-op silencioso.
    - Audit por campo: anterior→novo + fonte (o AuditLog é o histórico/versão).
    """
    target = row.target_field or ""
    col = alias.get(target, target) if target in alias else target
    if col is None:
        ignorados.append(f"{row.target_entity}.{target} (sem coluna na base)")
        return False
    if col not in allowed or col not in obj.__table__.columns:
        ignorados.append(f"{row.target_entity}.{target}")
        return False

    coerced = _coerce(value, obj.__table__.columns[col].type, col, unidade)
    if coerced is None:
        ignorados.append(f"{row.target_entity}.{col} (valor incoercível/implausível)")
        return False

    old = getattr(obj, col, None)
    # Cliente, Imóvel e Matrícula têm field_sources (a Matrícula ganhou a coluna no
    # Sprint 3, com backfill das linhas legadas) — o fallback `old is not None` foi
    # aposentado. `pendente_oficializacao` também protege: é verdade técnica selada
    # pelo consultor (Ficha 07 §3.4); doc novo divergente vira reconciliação, não
    # sobrescrita silenciosa.
    fs_prev = dict(getattr(obj, "field_sources", None) or {})
    ja_consolidado = fs_prev.get(col) in ("human_validated", "pendente_oficializacao")

    if ja_consolidado and _values_differ(old, coerced):
        # Doc novo diverge de campo já gravado → NUNCA sobrescreve sozinho (Ficha 05).
        reconciliacoes.append({
            "entity": row.target_entity, "entity_id": getattr(obj, "id", None),
            "field": col, "anterior": _ser(old), "novo": _ser(coerced),
            "fonte": fonte, "staging_id": row.id,
        })
        return False

    if not _values_differ(old, coerced):
        # Idempotência: mesmo valor → reafirma proveniência mas não conta como write.
        if not ja_consolidado:
            obj.field_sources = {**fs_prev, col: "human_validated"}
        return False

    setattr(obj, col, coerced)
    obj.field_sources = {**fs_prev, col: "human_validated"}
    writes.append({
        "entity": row.target_entity, "entity_id": getattr(obj, "id", None),
        "field": col, "anterior": _ser(old), "novo": _ser(coerced),
        "fonte": fonte, "staging_id": row.id,
    })
    return True


def _ser(value: Any) -> Any:
    """Serializa valor p/ o audit (date → ISO)."""
    return value.isoformat() if isinstance(value, date) else value


def _reconcile_matricula_activation(
    db: Session, tenant_id: int, process_id: int, prop: Any,
    accepted: list[ExtractedFieldStaging],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Contrato da Conferência (forense caso Isis): REJEITAR staging DESFAZ o efeito.

    Uma matrícula materializada a partir de staging que DEPOIS foi rejeitada por
    completo (zero linhas aceitas para o seu hint) é DESATIVADA — sai da soma da
    área (``Property.area_total_matriculas``) sem ser apagada (reversível,
    auditável). Reaceitar a staging REATIVA (idempotente: a consolidação roda de
    novo a cada decisão). Só toca matrículas cujo número aparece como hint na
    staging DESTE processo — matrícula cadastrada à mão (sem staging) fica intata.
    """
    from app.models.matricula import Matricula  # noqa: PLC0415

    if prop is None:
        return [], []

    # Hints com ≥1 linha ACEITA agora (matrícula ainda tem dado consolidável).
    accepted_hints = {
        _clean_matricula_hint(r.matricula_hint)
        for r in accepted
        if (r.target_entity or "").lower() == "matricula" and r.matricula_hint
    }
    accepted_hints.discard(None)

    # Hints que EXISTEM na staging do processo (qualquer status) — só estes são
    # "derivados de staging"; distinguem matrícula de doc da cadastrada à mão.
    staging_hint_rows = (
        db.query(ExtractedFieldStaging.matricula_hint)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
            ExtractedFieldStaging.matricula_hint.isnot(None),
        )
        .distinct()
        .all()
    )
    staging_hints = {_clean_matricula_hint(h[0]) for h in staging_hint_rows}
    staging_hints.discard(None)

    desativadas: list[dict[str, Any]] = []
    reativadas: list[dict[str, Any]] = []
    mats = (
        db.query(Matricula)
        .filter(Matricula.tenant_id == tenant_id, Matricula.property_id == prop.id)
        .all()
    )
    for mat in mats:
        hint = _clean_matricula_hint(mat.numero_matricula)
        if hint is None or hint not in staging_hints:
            continue  # cadastro manual (sem staging) — não mexe
        tem_aceito = hint in accepted_hints
        if not tem_aceito and mat.deactivated_at is None:
            mat.deactivated_at = datetime.now(UTC)
            mat.deactivation_reason = "rejeitado_na_conferencia"
            desativadas.append({"matricula_id": mat.id, "numero": mat.numero_matricula,
                                 "area_ha": mat.area_ha})
        elif tem_aceito and mat.deactivated_at is not None:
            mat.deactivated_at = None
            mat.deactivation_reason = None
            reativadas.append({"matricula_id": mat.id, "numero": mat.numero_matricula,
                               "area_ha": mat.area_ha})
    if desativadas or reativadas:
        db.flush()
    return desativadas, reativadas


def _upsert_matricula(
    db: Session, tenant_id: int, property_id: int, hint: str, *, allow_create: bool = True,
):
    from app.models.matricula import Matricula  # noqa: PLC0415

    mat = (
        db.query(Matricula)
        .filter(
            Matricula.tenant_id == tenant_id,
            Matricula.property_id == property_id,
            Matricula.numero_matricula == hint,
        )
        .first()
    )
    if mat is not None:
        return mat, False
    if not allow_create:  # guard fantasma (Sprint 4) — ver _MATRICULA_CREATOR_DOC_TYPES
        return None, False
    # numero_matricula vem de staging ACEITO (hint) → proveniência explícita já
    # na criação; sem isso, um doc futuro com formatação diferente sobrescreveria.
    mat = Matricula(
        tenant_id=tenant_id, property_id=property_id, numero_matricula=hint,
        field_sources={"numero_matricula": "human_validated"},
    )
    db.add(mat)
    db.flush()
    return mat, True


def _load_client(db: Session, tenant_id: int, client_id: int):
    from app.models.client import Client  # noqa: PLC0415
    return db.query(Client).filter(Client.id == client_id, Client.tenant_id == tenant_id).first()


def _load_property(db: Session, tenant_id: int, property_id: int):
    from app.models.property import Property  # noqa: PLC0415
    return db.query(Property).filter(Property.id == property_id, Property.tenant_id == tenant_id).first()


def _audit(db: Session, tenant_id: int, process_id: int, user_id: Optional[int],
           action: str, details: dict[str, Any]) -> None:
    """AuditLog com hash chain SHA-256 (Princípio 2 — tudo auditável)."""
    log = AuditLog(
        tenant_id=tenant_id, user_id=user_id, entity_type="process",
        entity_id=process_id, action=action,
        details=json.dumps(details, ensure_ascii=False, default=str),
    )
    db.add(log)
    db.flush()
    stamp_audit_hash(db, log)
