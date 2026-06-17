"""
Ficha 01 / FASE 2 — extração ESTRUTURADA por tipo de documento → staging.

O Extrator preenche `ExtractedFieldStaging` (agentes propõem; consultor decide na
fase 4). Cada campo extraído vira UMA linha de staging com `field_name`,
`field_value` (JSON: valor + unidade), `confidence`, `source_doc_type`,
`target_entity`/`target_field`, `matricula_hint`, `created_by_agent="extrator"`,
`ai_job_id`, `status=pendente`.

NÃO grava na base real (Client/Property/Matricula) — só staging. NÃO altera o
shape de `AIJob.extracted_fields` (continua vindo do `document_extractor`); este
módulo é uma extração ADICIONAL, com 1 chamada LLM dedicada por documento.

Tipos canônicos (Ficha 01 §5.1-5.7 + Ficha 02 §8 para o RAT):
  rg_cpf, endereco, car, ccir, matricula, itr, sigef, rat (+ outro = fallback).

NOMENCLATURA RAT (Ficha 02 §8): `rat` = RELATÓRIO DE ANÁLISE TÉCNICA do CAR
(emitido pelo órgão ao analisar o CAR). "Retificação" é um ATO, não um documento
— não existe doc_type para ela.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


# Lista canônica de doc_types do intake (ordem de especificidade na classificação).
CANONICAL_DOC_TYPES: list[str] = [
    "rg_cpf",
    "endereco",
    "car",
    "ccir",
    "matricula",
    "itr",
    "sigef",
    "rat",
    "outro",
]

_SPECIFIC_DOC_TYPES = {t for t in CANONICAL_DOC_TYPES if t != "outro"}


# ---------------------------------------------------------------------------
# Classificação por conteúdo (rule-based, sem LLM)
# ---------------------------------------------------------------------------
# ORDEM DE DECISÃO DETERMINÍSTICA — "o tipo é do DOCUMENTO, não de uma menção
# interna". Cada documento é identificado pelo seu CABEÇALHO/identidade própria,
# que vence menções a outros sistemas no corpo:
#   1. rat       — "relatório de análise técnica" (parecer do órgão)
#   2. matricula — certidão de registro: "inteiro teor", "oficial registrador",
#                  "registro de imóveis". Vem ANTES de sigef/ccir/itr porque a
#                  certidão CITA georref/CCIR/CAR no corpo (cadeia/averbações) e
#                  não pode ser sequestrada por esses termos.
#   3. car       — "recibo de inscrição ... CAR"
#   4. ccir / 5. itr / 6. sigef — identidades próprias (memorial/certificação)
#   7. rg_cpf / 8. endereco
# Caso real #11: a "Certidão de Inteiro Teor da Matrícula 6776" caía em `sigef`
# porque continha "memorial descritivo" (seção de georref embutida) e `sigef`
# vinha antes de `matricula`. Corrigido com a precedência + marcadores fortes.
# NÃO usar "matrícula nº" como gatilho de `matricula`: um memorial SIGEF cita o
# número da matrícula — gatilho fraco roubaria a classificação.
_CLASSIFY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("rat", (
        "relatorio de analise tecnica", "relatório de análise técnica",
        "analise tecnica do car", "análise técnica do car", "go-rat", "rat-",
    )),
    ("matricula", (
        # Marcadores ÚNICOS da certidão de registro. NÃO incluir "registro de
        # imóveis"/"cartório de registro": um recibo CAR lista matrículas com
        # "Cartório de Registro de Imóveis de X" no corpo e seria roubado.
        "inteiro teor", "oficial registrador", "oficial substituta",
        "certidao de matricula", "certidão de matrícula",
        "livro no 2", "livro nº 2",
    )),
    ("car", (
        "recibo de inscricao", "recibo de inscrição", "cadastro ambiental rural",
        "registro no car", "sicar",
    )),
    ("ccir", (
        "ccir", "certificado de cadastro de imovel rural",
        "certificado de cadastro de imóvel rural",
    )),
    ("itr", (
        "imposto sobre a propriedade territorial rural", "nirf", " vtn",
        "valor da terra nua", "documento de informacao e apuracao do itr",
    )),
    ("sigef", (
        "sigef", "memorial descritivo", "georreferenciamento", "georreferenciado",
        "vertices", "vértices", "certificacao do imovel", "certificação do imóvel",
    )),
    ("rg_cpf", (
        "registro geral", "carteira de identidade", "cedula de identidade",
        "cédula de identidade", "carteira nacional de habilitacao",
        "carteira nacional de habilitação", "republica federativa do brasil",
    )),
    ("endereco", (
        "comprovante de endereco", "comprovante de endereço", "conta de energia",
        "fatura de energia", "conta de agua", "logradouro",
    )),
]


def classify_doc_type(text: str, current: Optional[str] = None) -> str:
    """Classifica o doc_type por conteúdo.

    Respeita ``current`` quando já é um tipo específico conhecido (não sobrescreve
    classificação humana/intake). Só "outro"/None/desconhecido dispara a heurística
    de conteúdo. Sem match → mantém ``current`` ou "outro".
    """
    cur = (current or "").strip().lower()
    if cur in _SPECIFIC_DOC_TYPES:
        return cur

    low = (text or "").lower()
    for dt, keywords in _CLASSIFY_RULES:
        if any(kw in low for kw in keywords):
            return dt
    return cur or "outro"


# ---------------------------------------------------------------------------
# Mapa de extração por tipo (Ficha 01)
# ---------------------------------------------------------------------------

@dataclass
class StagingField:
    """Uma linha de staging antes de persistir."""

    field_name: str
    field_value: dict[str, Any]
    confidence: Optional[str]
    target_entity: Optional[str]
    target_field: Optional[str]
    matricula_hint: Optional[str] = None


@dataclass
class _FieldSpec:
    json_key: str
    field_name: str
    target_entity: str
    target_field: str
    unidade: Optional[str] = None


# Specs escalares por tipo. Listas (car.matriculas, rat.pendencias) têm
# tratamento próprio em ``build_staging_fields``.
_FIELD_SPECS: dict[str, list[_FieldSpec]] = {
    "rg_cpf": [
        _FieldSpec("nome", "nome", "cliente", "full_name"),
        _FieldSpec("cpf", "cpf", "cliente", "document"),
        _FieldSpec("data_nascimento", "data_nascimento", "cliente", "birth_date"),
    ],
    "endereco": [
        _FieldSpec("endereco_correspondencia", "endereco_correspondencia", "cliente", "address"),
    ],
    "car": [
        _FieldSpec("numero_car", "numero_car", "imovel", "car_code"),
        _FieldSpec("area_declarada_ha", "area_declarada_ha", "imovel", "total_area_ha", "ha"),
        _FieldSpec("municipio", "municipio", "imovel", "municipality"),
        _FieldSpec("uf", "uf", "imovel", "state"),
        _FieldSpec("app_declarada_ha", "app_declarada_ha", "imovel", "app_area_ha", "ha"),
        _FieldSpec("rl_declarada_ha", "rl_declarada_ha", "imovel", "rl_status", "ha"),
        _FieldSpec("status_car", "status_car", "imovel", "car_status"),
    ],
    "ccir": [
        _FieldSpec("codigo_sncr_incra", "codigo_sncr_incra", "matricula", "codigo_incra_sncr"),
        _FieldSpec("area_ha", "area_ha", "matricula", "area_ha", "ha"),
        _FieldSpec("detentor", "detentor", "matricula", "proprietarios"),
        _FieldSpec("municipio", "municipio", "imovel", "municipality"),
        _FieldSpec("denominacao", "denominacao", "matricula", "denominacao_imovel"),
    ],
    "matricula": [
        _FieldSpec("numero_matricula", "numero_matricula", "matricula", "numero_matricula"),
        _FieldSpec("registro_livro_folha", "registro_livro_folha", "matricula", "registro_livro_folha_ficha"),
        _FieldSpec("cartorio", "cartorio", "matricula", "cartorio"),
        _FieldSpec("area_registrada_ha", "area_registrada_ha", "matricula", "area_ha", "ha"),
        _FieldSpec("denominacao", "denominacao", "matricula", "denominacao_imovel"),
        _FieldSpec("denominacao_anterior", "denominacao_anterior", "matricula", "denominacao_imovel"),
        _FieldSpec("averbacao_app", "averbacao_app", "matricula", "averbacao_app"),
        _FieldSpec("averbacao_rl", "averbacao_rl", "matricula", "averbacao_rl"),
        _FieldSpec("numero_geo", "numero_geo", "matricula", "geo_certificacao_codigo"),
        _FieldSpec("codigo_certificacao", "codigo_certificacao", "matricula", "geo_certificacao_codigo"),
        _FieldSpec("onus", "onus", "matricula", "onus_gravames"),
    ],
    "itr": [
        _FieldSpec("nirf_cib", "nirf_cib", "matricula", "nirf_cib"),
        _FieldSpec("area_declarada_ha", "area_declarada_ha", "matricula", "area_ha", "ha"),
        _FieldSpec("vtn", "vtn", "matricula", "vtn", "BRL"),
        _FieldSpec("municipio", "municipio", "imovel", "municipality"),
        _FieldSpec("nome_imovel", "nome_imovel", "matricula", "denominacao_imovel"),
        _FieldSpec("codigo_incra", "codigo_incra", "matricula", "codigo_incra_sncr"),
        # numero_car declarado no ITR — usado pela matriz (car_presenca: CAR
        # existente mas ausente no ITR → inconsistente, "atualizar ITR/DIAC").
        _FieldSpec("numero_car", "numero_car", "imovel", "car_code"),
    ],
    "sigef": [
        _FieldSpec("area_georreferenciada_ha", "area_georreferenciada_ha", "matricula", "area_ha", "ha"),
        _FieldSpec("coordenadas_perimetro_resumo", "coordenadas_perimetro_resumo", "matricula", "geo_certificacao_codigo"),
        _FieldSpec("codigo_certificacao", "codigo_certificacao", "matricula", "geo_certificacao_codigo"),
        _FieldSpec("status_certificacao", "status_certificacao", "matricula", "geo_certificacao_status"),
        _FieldSpec("denominacao", "denominacao", "matricula", "denominacao_imovel"),
        _FieldSpec("proprietario", "proprietario", "matricula", "proprietarios"),
    ],
    "rat": [
        _FieldSpec("numero_car", "numero_car", "imovel", "car_code"),
        _FieldSpec("protocolo", "protocolo", "imovel", "rat_protocolo"),
        _FieldSpec("data_emissao", "data_emissao", "imovel", "rat_data_emissao"),
        _FieldSpec("situacao", "situacao", "imovel", "car_status"),
        _FieldSpec("area_vetorizada_ha", "area_vetorizada_ha", "imovel", "area_grafica_ha", "ha"),
        _FieldSpec("modulos_fiscais", "modulos_fiscais", "imovel", "modulos_fiscais", "módulos"),
    ],
}

# Tipos cujos campos referenciam uma matrícula → todas as linhas herdam o hint.
_HINT_FROM_KEY: dict[str, str] = {
    "matricula": "numero_matricula",
    "ccir": "numero_matricula",
    "itr": "numero_matricula",
    "sigef": "numero_matricula",
}


# Esqueletos de extração por tipo (prompt-based JSON, mesmo padrão do
# document_extractor). `{text}` é substituído pelo texto do documento.
_STAGING_PROMPTS: dict[str, str] = {
    "rg_cpf": """Extraia os dados de identificação desta pessoa (RG / CPF / CNH).
Retorne APENAS JSON. Campos ausentes = null.
{"nome": null, "cpf": null, "data_nascimento": null, "confidence": {}}
TEXTO:
{text}""",
    "endereco": """Extraia o endereço de correspondência deste comprovante.
Retorne APENAS JSON. Campos ausentes = null.
{"endereco_correspondencia": null, "confidence": {}}
TEXTO:
{text}""",
    "car": """Este é o RECIBO DE INSCRIÇÃO no CAR (Cadastro Ambiental Rural).
Extraia os campos e a LISTA DE MATRÍCULAS citadas no recibo. Retorne APENAS JSON.
Campos ausentes = null; listas vazias = [].
{
  "numero_car": null,
  "area_declarada_ha": null,
  "municipio": null,
  "uf": null,
  "app_declarada_ha": null,
  "rl_declarada_ha": null,
  "status_car": null,
  "matriculas": [{"numero": null, "data": null, "livro_folha": null, "cartorio": null}],
  "confidence": {}
}
TEXTO:
{text}""",
    "ccir": """Extraia os campos deste CCIR (Certificado de Cadastro de Imóvel Rural).
Retorne APENAS JSON. Campos ausentes = null.
{"codigo_sncr_incra": null, "area_ha": null, "detentor": null, "municipio": null,
 "denominacao": null, "numero_matricula": null, "confidence": {}}
TEXTO:
{text}""",
    "matricula": """Esta é uma CERTIDÃO DE MATRÍCULA / Registro de Imóveis. Extraia.
Procure em TODO o texto (a matrícula tem várias seções: abertura, registros R-,
averbações AV-). Retorne APENAS JSON. Campos ausentes = null.
Instruções de completude:
- "denominacao": o nome ATUAL do imóvel. Se a matrícula menciona nome ANTERIOR/
  histórico (ex.: "anteriormente denominada X", outra denominação na cadeia),
  inclua-o em "denominacao_anterior".
- "proprietarios": cadeia de titulares (lista [{"nome","cpf"}]).
- "onus": descreva CADA gravame (hipoteca/penhor/alienação) com TIPO, CREDOR e
  VALOR quando constarem (ex.: "Hipoteca (R.05) - credor Banco X - R$ 1.000.000").
- "averbacao_rl"/"averbacao_app": área e referência da averbação (ex.: matrícula
  de origem da RL).
- "codigo_certificacao": código do georreferenciamento (SIGEF/INCRA), se houver,
  SEM texto de vértice grudado.
{
  "numero_matricula": null,
  "registro_livro_folha": null,
  "cartorio": null,
  "area_registrada_ha": null,
  "denominacao": null,
  "denominacao_anterior": null,
  "proprietarios": [{"nome": null, "cpf": null}],
  "averbacao_app": null,
  "averbacao_rl": null,
  "numero_geo": null,
  "codigo_certificacao": null,
  "onus": null,
  "confidence": {}
}
TEXTO:
{text}""",
    "itr": """Extraia os campos deste ITR (Imposto Territorial Rural / DIAT/DITR).
Retorne APENAS JSON. Campos ausentes = null.
{"nirf_cib": null, "area_declarada_ha": null, "vtn": null, "municipio": null,
 "nome_imovel": null, "codigo_incra": null, "numero_car": null, "numero_matricula": null,
 "confidence": {}}
TEXTO:
{text}""",
    "sigef": """Extraia os campos deste memorial/certidão SIGEF (georreferenciamento).
Coordenadas/perímetro: resuma (não liste todos os vértices). Retorne APENAS JSON.
{"area_georreferenciada_ha": null, "coordenadas_perimetro_resumo": null,
 "codigo_certificacao": null, "status_certificacao": null, "denominacao": null,
 "proprietario": null, "numero_matricula": null, "confidence": {}}
TEXTO:
{text}""",
    "rat": """Este é o RELATÓRIO DE ANÁLISE TÉCNICA (RAT) do CAR, emitido pelo órgão.
Extraia os campos e a LISTA DE PENDÊNCIAS estruturada — as pendências são o insumo
central do diagnóstico. Retorne APENAS JSON. Campos ausentes = null; listas = [].
{
  "numero_car": null,
  "protocolo": null,
  "data_emissao": null,
  "situacao": null,
  "area_vetorizada_ha": null,
  "modulos_fiscais": null,
  "pendencias": [
    {"categoria": null, "detalhamento": null, "recomendacao": null,
     "atendimento": null, "coordenadas": null}
  ],
  "confidence": {}
}
TEXTO:
{text}""",
}


def _conf_for(parsed: dict[str, Any], key: str) -> Optional[str]:
    conf = parsed.get("confidence")
    if isinstance(conf, dict):
        val = conf.get(key)
        if isinstance(val, str):
            return val
    return None


def _is_empty(value: Any) -> bool:
    return value in (None, "", [], {}) or (isinstance(value, str) and not value.strip())


def _unwrap_llm_value(value: Any) -> tuple[Any, Optional[str]]:
    """Desembrulha campos que o LLM às vezes devolve como objeto, não escalar.

    Caso #12 (vazamento do dict): em vez de ``"area_ha": 349.9022`` o modelo
    devolveu ``"area_ha": {"value": 349.9022, "confidence": "high"}``. Sem
    desembrulhar, o dict era persistido cru em ``field_value.value`` e em
    ``matricula_hint`` (via ``str(dict)``) — e a vírgula do repr do dict virava
    a "fazenda de 3,5 milhões de ha" no parse de área. Aqui devolvemos o escalar
    interno + a confiança embutida (quando houver).

    Só desembrulha o "envelope" ``{value, confidence?}``; dicts estruturais
    legítimos (item de matrícula, pendência) passam intactos.
    """
    if isinstance(value, dict) and "value" in value:
        inner_keys = set(value.keys())
        if inner_keys <= {"value", "confidence"}:
            return value.get("value"), value.get("confidence")
    return value, None


def _value_key(value: Any) -> str:
    """Chave normalizada de um valor extraído, para deduplicação (4c).

    Escalares: string normalizada (trim + minúsculas). Listas/dicts: JSON
    ordenado e estável."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return re.sub(r"\s+", " ", str(value).strip().lower())


def build_staging_fields(doc_type: str, parsed: dict[str, Any]) -> list[StagingField]:
    """Mapeia o JSON extraído → linhas de staging (sem persistir).

    Pula campos vazios. Trata listas especiais (car.matriculas → 1 linha por
    matrícula com `matricula_hint`; rat.pendencias → `pendencias_rat`).
    """
    if not isinstance(parsed, dict):
        return []

    from app.services.field_validators import check_format  # noqa: PLC0415
    from app.services.inconsistency_matrix import _clean_matricula_hint  # noqa: PLC0415

    rows: list[StagingField] = []
    seen_keys: set[tuple[Any, ...]] = set()  # dedup intra-doc (campo+hint+valor)
    hint_key = _HINT_FROM_KEY.get(doc_type)
    raw_hint = parsed.get(hint_key) if hint_key else None
    raw_hint, _ = _unwrap_llm_value(raw_hint)
    # Caso #12 item B: extrai só o número da matrícula (regex) — sem dict, sem
    # anotação ("R-01", "(2 de 3)"), sem prefixo ("MATR. 2.923" → "2923").
    doc_hint = _clean_matricula_hint(raw_hint)

    for spec in _FIELD_SPECS.get(doc_type, []):
        value = parsed.get(spec.json_key)
        # Caso #12: desembrulha envelope {value, confidence} que o LLM às vezes
        # devolve — senão o dict é persistido cru (vira "3,5 milhões de ha").
        value, embedded_conf = _unwrap_llm_value(value)
        if _is_empty(value):
            continue
        # 4c — dedup no MESMO doc: campo+hint+valor repetido vira 1 linha.
        dedup_key = (spec.field_name, doc_hint, _value_key(value))
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        fv: dict[str, Any] = {"value": value}
        if spec.unidade:
            fv["unidade"] = spec.unidade
        confidence = _conf_for(parsed, spec.json_key) or embedded_conf
        # 4b — validação de formato: fora do esperado → rebaixa + marca p/ revisão,
        # SEM tocar no valor bruto (preservado em fv["value"]).
        fmt_ok = check_format(spec.field_name, value)
        if fmt_ok is False:
            fv["format_ok"] = False
            confidence = "low"
        rows.append(StagingField(
            field_name=spec.field_name,
            field_value=fv,
            confidence=confidence,
            target_entity=spec.target_entity,
            target_field=spec.target_field,
            matricula_hint=doc_hint,
        ))

    # CAR: lista de matrículas citadas no recibo → 1 linha por item (hint = nº).
    if doc_type == "car":
        for item in parsed.get("matriculas") or []:
            if not isinstance(item, dict) or _is_empty(item):
                continue
            numero, _ = _unwrap_llm_value(item.get("numero"))
            rows.append(StagingField(
                field_name="matricula_listada",
                field_value={"value": item},
                confidence=_conf_for(parsed, "matriculas"),
                target_entity="matricula",
                target_field="numero_matricula",
                matricula_hint=_clean_matricula_hint(numero),
            ))

    # RAT: pendências estruturadas → insumo central do diagnóstico (Fase 3).
    if doc_type == "rat":
        pendencias = parsed.get("pendencias")
        if pendencias and not _is_empty(pendencias):
            rows.append(StagingField(
                field_name="pendencias_rat",
                field_value={"value": pendencias},
                confidence=_conf_for(parsed, "pendencias"),
                target_entity="imovel",
                target_field="regulatory_issues",
                matricula_hint=None,
            ))

    return rows


# ---------------------------------------------------------------------------
# Extração (LLM) + persistência no staging
# ---------------------------------------------------------------------------

@dataclass
class StagingResult:
    doc_type: str
    rows_written: int
    fields: list[StagingField] = field(default_factory=list)
    skipped_reason: Optional[str] = None


def _extract_structured(text: str, doc_type: str) -> Optional[dict[str, Any]]:
    """Roda 1 chamada LLM com o esqueleto do tipo e devolve o JSON parseado."""
    prompt_template = _STAGING_PROMPTS.get(doc_type)
    if prompt_template is None:
        return None
    if not settings.ai_configured or not (text or "").strip():
        return None

    from app.core.ai_gateway import AIGatewayError, complete  # noqa: PLC0415

    system = (
        "Voce e um especialista em documentos fundiarios e ambientais brasileiros. "
        "Extraia os campos solicitados e retorne APENAS JSON valido. "
        "Para cada campo extraido inclua a confianca em \"confidence\": "
        "\"high\" | \"medium\" | \"low\". "
        # Item 1 (Isis 16/06): preservar o numero verbatim — quem converte e o sistema.
        "Numeros e areas: copie como STRING literal, EXATAMENTE como aparece no "
        "documento, preservando os separadores brasileiros (ex.: a area \"1.010,7113\" "
        "deve sair como \"1.010,7113\", nunca 1.0107113 nem 1010.7113). NUNCA converta "
        "o numero voce mesmo (a virgula e decimal, o ponto e milhar). Vale para "
        "area_*_ha, vtn e modulos_fiscais."
    )
    prompt = prompt_template.replace("{text}", text[: settings.EXTRACTOR_MAX_CHARS])
    try:
        response = complete(prompt, system=system)
    except AIGatewayError as exc:
        logger.warning("ficha01_extraction: LLM falhou doc_type=%s: %s", doc_type, exc.message)
        return None
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("ficha01_extraction: erro inesperado doc_type=%s: %s", doc_type, exc)
        return None
    return _parse_json(response.content)


def extract_and_stage(
    *,
    text: str,
    doc_type: str,
    tenant_id: int,
    db_session,
    process_id: Optional[int] = None,
    document_id: Optional[int] = None,
    ai_job_id: Optional[int] = None,
    created_by_agent: str = "extrator",
) -> StagingResult:
    """Extrai campos estruturados do documento e grava linhas em ExtractedFieldStaging.

    Best-effort: qualquer falha (LLM, parse) resulta em 0 linhas, sem derrubar o
    chamador. NÃO grava na base real — só staging. `doc_type` já deve estar
    classificado (use ``classify_doc_type`` antes).
    """
    from app.models.extracted_field_staging import (  # noqa: PLC0415
        ExtractedFieldStaging,
        ExtractedFieldStatus,
    )

    dt = (doc_type or "outro").lower()
    if dt not in _STAGING_PROMPTS:
        return StagingResult(doc_type=dt, rows_written=0, skipped_reason="tipo sem schema de staging")

    parsed = _extract_structured(text, dt)
    if not parsed:
        return StagingResult(doc_type=dt, rows_written=0, skipped_reason="extração vazia/falha")

    fields = build_staging_fields(dt, parsed)

    # 4c — dedup na persistência: não recriar linha já existente (mesma fonte +
    # campo + hint + valor). Resolve a triplicação de re-extrações. Valores
    # DIFERENTES da mesma fonte são mantidos (divergência interna → insumo matriz).
    scope = db_session.query(ExtractedFieldStaging).filter(
        ExtractedFieldStaging.tenant_id == tenant_id,
        ExtractedFieldStaging.source_doc_type == dt,
    )
    if process_id is not None:
        scope = scope.filter(ExtractedFieldStaging.process_id == process_id)
    elif document_id is not None:
        scope = scope.filter(ExtractedFieldStaging.document_id == document_id)
    seen: set[tuple[Any, ...]] = set()
    for existing in scope.all():
        ev = existing.field_value.get("value") if isinstance(existing.field_value, dict) else existing.field_value
        seen.add((existing.field_name, existing.matricula_hint, _value_key(ev)))

    written = 0
    for f in fields:
        key = (f.field_name, f.matricula_hint, _value_key(f.field_value.get("value")))
        if key in seen:
            continue
        seen.add(key)
        db_session.add(ExtractedFieldStaging(
            tenant_id=tenant_id,
            process_id=process_id,
            document_id=document_id,
            source_doc_type=dt,
            field_name=f.field_name,
            field_value=f.field_value,
            confidence=f.confidence,
            target_entity=f.target_entity,
            target_field=f.target_field,
            matricula_hint=f.matricula_hint,
            status=ExtractedFieldStatus.pendente,
            created_by_agent=created_by_agent,
            ai_job_id=ai_job_id,
        ))
        written += 1
    db_session.flush()

    logger.info(
        "ficha01_extraction: staging doc_type=%s document_id=%s process_id=%s rows=%d (dedup: %d→%d)",
        dt, document_id, process_id, written, len(fields), written,
    )
    return StagingResult(doc_type=dt, rows_written=written, fields=fields)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json(content: str) -> Optional[dict[str, Any]]:
    content = (content or "").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    start = content.find("{")
    end = content.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(content[start:end])
        except json.JSONDecodeError:
            pass
    return None
