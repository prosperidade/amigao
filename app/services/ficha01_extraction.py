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
  rg_cpf, endereco, car, ccir, matricula, itr, sigef, rat,
  planta_topografica, memorial_descritivo, auto_infracao, certidao_embargo
  (+ outro = fallback).

NOMENCLATURA RAT (Ficha 02 §8): `rat` = RELATÓRIO DE ANÁLISE TÉCNICA do CAR
(emitido pelo órgão ao analisar o CAR). "Retificação" é um ATO, não um documento
— não existe doc_type para ela.

Fase 1 (N1, classificador honesto): `planta_topografica` e `memorial_descritivo`
são peças TÉCNICAS de apoio — não têm `_FIELD_SPECS` (não alimentam staging
cadastral) nem entram no allowlist de criação de `Matricula`
(`staging_consolidation._MATRICULA_CREATOR_DOC_TYPES`). `auto_infracao` é o
MESMO tipo já usado pelo pipeline legado (`document_extractor.py`) — reusado
aqui só para o classificador por conteúdo reconhecer; a extração rica de auto
de infração como fato de passivo (N2) vive em `app/services/auto_infracao_extraction.py`,
fora do staging cadastral (sem hint de matrícula).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from app.core.config import settings
from app.services.area_registral import (
    entorno_do_valor,
    normalizar_area_registral,
)
from app.services.extraction_window import JanelaResultado, fatiar, mesclar
from app.services.observacao_registral import (
    MOTIVO_AREA_DE_OUTRO_OBJETO,
    MOTIVO_GRAVAME,
    MOTIVO_SEM_CASA,
    MOTIVO_SUBSTITUIDA,
    TIPOS_GRAVAME,
    Observacao,
    aplicar_alteracoes,
    area_de_outro_objeto,
    derivar_vigencia,
    destino_de,
    observacoes_de,
    onus_vigentes,
    rotulo_humano,
    ultimo_por_destino,
)
from app.services.text_anchor import Ancora, TextoIndexado, ancorar_composto

logger = logging.getLogger(__name__)


# Lista canônica de doc_types do intake (ordem de especificidade na classificação).
# Fase 1 (N1, classificador honesto): planta_topografica/memorial_descritivo NÃO
# alimentam staging cadastral nem criam Matricula (sem _FIELD_SPECS abaixo; guard
# fantasma em staging_consolidation.py já os exclui do allowlist de criação).
# auto_infracao é o MESMO tipo do pipeline legado (document_extractor.py) —
# reusado, não duplicado; aqui só ganha entrada no classificador por conteúdo.
CANONICAL_DOC_TYPES: list[str] = [
    "rg_cpf",
    "endereco",
    "car",
    "ccir",
    "matricula",
    "itr",
    "sigef",
    "rat",
    "planta_topografica",
    "memorial_descritivo",
    "auto_infracao",
    "certidao_embargo",
    # `contrato` (26/07, caso 15): peça contratual do caso — NÃO alimenta staging
    # cadastral (sem `_FIELD_SPECS`). Existe para que um contrato pare de ser
    # classificado como certificação/ficha e ter seus termos lidos como dados do
    # imóvel — foi assim que "Plano de Recuperação de Área Degradada (PRAD)"
    # virou denominação de imóvel no processo 15.
    "contrato",
    "outro",
]

_SPECIFIC_DOC_TYPES = {t for t in CANONICAL_DOC_TYPES if t != "outro"}


# ---------------------------------------------------------------------------
# Classificação por conteúdo (rule-based, sem LLM)
# ---------------------------------------------------------------------------
# ORDEM DE DECISÃO DETERMINÍSTICA — "o tipo é do DOCUMENTO, não de uma menção
# interna". Cada documento é identificado pelo seu CABEÇALHO/identidade própria,
# que vence menções a outros sistemas no corpo:
#   1. rat                 — "relatório de análise técnica" (parecer do órgão)
#   2. auto_infracao / 3. certidao_embargo — cabeçalho de órgão fiscalizador,
#                  identidade forte e inconfundível; vêm cedo de propósito.
#   4. planta_topografica / 5. memorial_descritivo — peças técnicas de desenho/
#                  descrição de perímetro. Vêm ANTES de ccir/sigef porque costumam
#                  CITAR esses sistemas em legenda ("CCIR nº...") sem SER um CCIR
#                  ou uma certificação SIGEF (caso 13, docs 228/230: planta lida
#                  como `ccir` pela menção fraca — a causa raiz que este item fecha).
#   6. matricula — certidão de registro: "inteiro teor", "oficial registrador",
#                  "registro de imóveis". Vem ANTES de sigef/ccir/itr porque a
#                  certidão CITA georref/CCIR/CAR no corpo (cadeia/averbações) e
#                  não pode ser sequestrada por esses termos.
#   7. car       — "recibo de inscrição ... CAR"
#   8. ccir / 9. itr / 10. sigef — identidades próprias (memorial/certificação)
#   11. rg_cpf / 12. endereco
# Caso real #11: a "Certidão de Inteiro Teor da Matrícula 6776" caía em `sigef`
# porque continha "memorial descritivo" (seção de georref embutida) e `sigef`
# vinha antes de `matricula`. Corrigido com a precedência + marcadores fortes.
# NÃO usar "matrícula nº" como gatilho de `matricula`: um memorial SIGEF cita o
# número da matrícula — gatilho fraco roubaria a classificação.
# Um "gatilho" é `str` (basta conter) ou `tuple[str, ...]` (precisa conter TODOS).
# A forma composta nasceu do caso 15: marcador isolado é fraco demais para
# identificar documento — ver `sigef` abaixo.
_Gatilho = "str | tuple[str, ...]"

_CLASSIFY_RULES: list[tuple[str, tuple[Any, ...]]] = [
    # ── Identidade FORTE do SIGEF (26/07, caso 15) ────────────────────────────
    # Vem no topo porque um memorial do Sigef CITA CCIR/matrícula no corpo e era
    # sequestrado por `ccir` (doc 322 real: "Memorial descritivo certificado.pdf",
    # cabeçalho INCRA/Sigef, classificado como CCIR). Só marcadores compostos e
    # inconfundíveis entram aqui — nada que um CCIR ou uma certidão possa ter.
    ("sigef", (
        "gerado automaticamente pelo sigef",
        ("memorial descritivo", "sigef"),
        ("memorial descritivo", "instituto nacional de colonizacao"),
        ("memorial descritivo", "instituto nacional de colonização"),
    )),
    # ── Contrato ──────────────────────────────────────────────────────────────
    # Antes de qualquer ficha cadastral: um contrato de prestação de serviço
    # ambiental fala de georreferenciamento, PRAD e imóvel o tempo todo. No caso
    # 15 o "Contrato BIOTA PRAD" (doc 329) casou `sigef` só por conter
    # "georreferenc" — e a ficha do SIGEF leu "Plano de Recuperação de Área
    # Degradada (PRAD)" como DENOMINAÇÃO DO IMÓVEL. Documento inteiro lido como
    # se fosse outro.
    ("contrato", (
        "contrato de prestacao de servicos", "contrato de prestação de serviços",
        "contrato particular", "instrumento particular de contrato",
        ("contratada", "contratante", "clausula"),
        ("contratada", "contratante", "cláusula"),
        ("obrigacoes das partes", "contratada"),
        ("obrigações das partes", "contratada"),
    )),
    ("rat", (
        "relatorio de analise tecnica", "relatório de análise técnica",
        "analise tecnica do car", "análise técnica do car", "go-rat", "rat-",
    )),
    # Fase 1 (N1) — auto de infração / certidão de embargo têm identidade MUITO
    # forte (cabeçalho de órgão fiscalizador) — vêm cedo, antes de qualquer
    # marcador fraco de documento cadastral.
    ("auto_infracao", (
        "auto de infracao", "auto de infração", "auto de constatacao",
        "auto de constatação", "notificacao de autuacao", "notificação de autuação",
    )),
    ("certidao_embargo", (
        "certidao de embargo", "certidão de embargo",
        "certidao de existencia de embargo", "certidão de existência de embargo",
        "termo de embargo",
    )),
    # Fase 1 (N1) — planta/memorial são peças TÉCNICAS de desenho/descrição de
    # perímetro, não certificações. Precisam vir ANTES de ccir/sigef porque
    # costumam CITAR esses sistemas em legenda/referência (ex.: "CCIR nº ..."
    # dentro da planta) sem SER um CCIR ou uma certificação SIGEF — caso real
    # caso 13 (doc 228/230): planta lida como `ccir` por essa menção fraca.
    ("planta_topografica", (
        "planta topografica", "planta topográfica", "planta de situacao",
        "planta de situação", "planta cadastral", "levantamento topografico",
        "levantamento topográfico", "norte magnetico", "norte magnético",
        "escala grafica", "escala gráfica",
    )),
    ("memorial_descritivo", (
        "memorial descritivo do imovel", "memorial descritivo do imóvel",
        "memorial descritivo de imovel rural", "memorial descritivo de imóvel rural",
        "perimetro do imovel denominado", "perímetro do imóvel denominado",
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
    # SIGEF "fraco" — o que sobra depois da identidade forte lá em cima. Perdeu
    # `georreferenciamento`/`georreferenciado` e `memorial descritivo` nus: os
    # três aparecem em contrato, parecer e certidão sem que o documento SEJA uma
    # certificação. O que ficou só ocorre em peça de georreferenciamento de fato.
    ("sigef", (
        "sigef", "vertices", "vértices",
        "certificacao do imovel", "certificação do imóvel",
        "codigo da certificacao", "código da certificação",
        ("memorial descritivo", "azimute"),
        ("georreferenciamento", "vertice"),
        ("georreferenciamento", "vértice"),
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
        if any(_gatilho_bate(kw, low) for kw in keywords):
            return dt
    return cur or "outro"


def _gatilho_bate(gatilho: Any, texto_low: str) -> bool:
    """`str` → basta conter. `tuple` → precisa conter TODOS os termos.

    O composto existe porque marcador isolado identifica mal: "georreferenciamento"
    aparece em contrato, "memorial descritivo" aparece em certidão. Exigir a
    co-ocorrência é o que separa "o documento FALA de X" de "o documento É X".
    """
    if isinstance(gatilho, tuple):
        return all(termo in texto_low for termo in gatilho)
    return gatilho in texto_low


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
    # Frente E (ADR-065) — O QUE o valor é, antes de ONDE ele pousa. `None` em
    # tudo que não vem de ato registral: campo de cabeçalho não é observação.
    tipo_observacao: Optional[str] = None
    atributos: Optional[dict[str, Any]] = None


@dataclass
class _FieldSpec:
    json_key: str
    field_name: str
    target_entity: str
    target_field: str
    unidade: Optional[str] = None


# ── ENT-001: de QUEM é o documento pessoal ──────────────────────────────────
# `rg_cpf` (RG/CPF/CNH) prova a identidade de uma PESSOA FÍSICA. Isso não diz
# de quem: num caso de cliente PF é do próprio titular; num caso de cliente PJ
# não pode ser do titular (o titular é o CNPJ) — é do representante. Mapear
# `rg_cpf` cegamente para "cliente" foi o que fez a CNH do Joel sobrescrever o
# CNPJ da ELODI com o CPF dele, com carimbo de consolidado (spec Isis §4.2.3).
DOC_PESSOAL_TYPES = {"rg_cpf"}

ENTIDADE_CLIENTE = "cliente"
ENTIDADE_REPRESENTANTE = "representante"

# Nomes de coluna diferem entre as duas entidades: no Client o documento é
# `cpf_cnpj` (via alias "document"); no representante é `cpf`, e nunca há CNPJ.
_REPRESENTANTE_TARGET_FIELD = {
    "full_name": "full_name",
    "document": "cpf",
    "birth_date": "birth_date",
}


def rota_documento_pessoal(titular_tipo: Optional[str]) -> Optional[str]:
    """Entidade de destino de um documento pessoal, dado o tipo do titular.

    - titular PF  → "cliente" (o documento é do próprio titular).
    - titular PJ  → "representante" (não há outra pessoa física possível no caso).
    - desconhecido → None: a linha fica SEM destino e vira pendência explícita
      para o consultor na Conferência. Ambíguo nunca escreve — a regra é a mesma
      do guard fantasma da matrícula.
    """
    t = (titular_tipo or "").strip().lower()
    if t == "pf":
        return ENTIDADE_CLIENTE
    if t == "pj":
        return ENTIDADE_REPRESENTANTE
    return None


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
        # Frente K — a RL declarada é ÁREA (número em ha), não ESTADO. Apontava
        # para `rl_status` e o Hub mostrava "Reserva Legal: 437,7632" onde o
        # vocabulário é `averbada|proposta|pendente|cancelada`; a ponte
        # matrícula→imóvel escrevia 'averbada' na MESMA coluna. Duas naturezas
        # não cabem numa coluna: `rl_area_ha` é o destino do número.
        _FieldSpec("rl_declarada_ha", "rl_declarada_ha", "imovel", "rl_area_ha", "ha"),
        _FieldSpec("status_car", "status_car", "imovel", "car_status"),
        # Fiação (09/09), DATA-002 parcial — o recibo do CAR declara DUAS áreas
        # no mesmo parágrafo ("Foi detectada uma diferença entre a área ...
        # declarada conforme documentação comprobatória [2180.3923 hectares] e a
        # área ... identificada em representação gráfica [2.180,8267 hectares]").
        # O esqueleto tinha UM slot: a gráfica entrava em `total_area_ha` e a
        # documental não tinha para onde ir — a informação mais importante do
        # parágrafo, a de que existe diferença, morria na entrada.
        # `imovel.area_documental_ha` existe desde sempre e estava NULL.
        _FieldSpec("area_documental_ha", "area_documental_ha", "imovel", "area_documental_ha", "ha"),
        # Fiação (09/09) — "Módulos Fiscais: 31,1547" está no texto do recibo,
        # `properties.modulos_fiscais` existe (#200, decide porte e as exceções do
        # Código Florestal), e o prompt do CAR nunca pediu o campo. O RAT já
        # pedia; o CAR, que quase todo caso tem, não.
        _FieldSpec("modulos_fiscais", "modulos_fiscais", "imovel", "modulos_fiscais", "módulos"),
    ],
    "ccir": [
        # Item 7 (#74-restante) — número do CCIR: a consultora LOCALIZA o
        # documento por ele. Coluna PRÓPRIA em matrícula (per-lote, uma fazenda
        # tem um CCIR por lote); distinto do codigo_sncr_incra (Código do Imóvel
        # no SNCR) e do imovel.ccir depreciado por ambiguidade (N1 item 5).
        _FieldSpec("numero_ccir", "numero_ccir", "matricula", "numero_ccir"),
        _FieldSpec("codigo_sncr_incra", "codigo_sncr_incra", "matricula", "codigo_incra_sncr"),
        _FieldSpec("area_ha", "area_ha", "matricula", "area_ha", "ha"),
        _FieldSpec("detentor", "detentor", "matricula", "proprietarios"),
        _FieldSpec("municipio", "municipio", "imovel", "municipality"),
        _FieldSpec("denominacao", "denominacao", "matricula", "denominacao_imovel"),
        # Fase 0 (gap-analysis Ficha 07, item 8) — CCIR é documento ANUAL; o
        # exercício alimenta o emissor determinístico CCIR_EXERCICIO_ANTERIOR
        # (app/services/property_audit.py).
        _FieldSpec("exercicio", "exercicio", "matricula", "exercicio_ccir"),
    ],
    "matricula": [
        _FieldSpec("numero_matricula", "numero_matricula", "matricula", "numero_matricula"),
        _FieldSpec("registro_livro_folha", "registro_livro_folha", "matricula", "registro_livro_folha_ficha"),
        _FieldSpec("cartorio", "cartorio", "matricula", "cartorio"),
        _FieldSpec("area_registrada_ha", "area_registrada_ha", "matricula", "area_ha", "ha"),
        _FieldSpec("denominacao", "denominacao", "matricula", "denominacao_imovel"),
        # Cadeia (#60): nome ANTERIOR e registro de ORIGEM ganham coluna própria —
        # antes `denominacao_anterior` caía em `denominacao_imovel` e competia com
        # a denominação atual (poluição). São sinais da detecção de cadeia.
        _FieldSpec("denominacao_anterior", "denominacao_anterior", "matricula", "denominacao_anterior"),
        _FieldSpec("registro_anterior", "registro_anterior", "matricula", "registro_anterior"),
        _FieldSpec("averbacao_app", "averbacao_app", "matricula", "averbacao_app"),
        _FieldSpec("averbacao_rl", "averbacao_rl", "matricula", "averbacao_rl"),
        _FieldSpec("numero_geo", "numero_geo", "matricula", "geo_certificacao_codigo"),
        _FieldSpec("codigo_certificacao", "codigo_certificacao", "matricula", "geo_certificacao_codigo"),
        # NIRF/CIB na CERTIDAO (cascata da Isis, degrau 1 — 20/07): o mesmo
        # identificador da Receita aparece repetido nos registros/hipotecas da
        # matricula. Sem extrair aqui, `Matricula.nirf_cib` nasce SEMPRE NULL e o
        # degrau mais forte da vinculacao ITR->matricula fica morto, com a cascata
        # comecando silenciosamente no degrau 2 (INCRA). Ficha 08 secao 4.
        _FieldSpec("nirf_cib", "nirf_cib", "matricula", "nirf_cib"),
        _FieldSpec("onus", "onus", "matricula", "onus_gravames"),
        # Fiação (09/09) — a cadeia de titulares CHEGAVA e não pousava: o prompt
        # já pedia `proprietarios`, o JSON do doc 549 devolvia os quatro (Nascente,
        # Alexandre, Karina, ELODI), `Matricula.proprietarios` existia, e a falta
        # DESTA LINHA jogava tudo fora — 0 linhas de staging. `sigef` mapeava
        # `proprietario`; a certidão de matrícula, que é a fonte registral do
        # titular (ADR-062), não mapeava nada.
        #
        # UMA linha com a lista inteira, não uma por titular: os quatro são da
        # MESMA matrícula e disputariam a MESMA coluna. Quatro linhas fariam a
        # primeira gravar e as outras três virarem reconciliação falsa
        # (`field_sources` já marcado + `_values_differ`). É a diferença para
        # `car.matriculas`, onde cada item tem `matricula_hint` PRÓPRIO e portanto
        # linha de destino própria.
        _FieldSpec("proprietarios", "proprietarios", "matricula", "proprietarios"),
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
Instruções de completude — esclarecem os campos AMBÍGUOS; preencha TODOS os
campos do JSON abaixo que constarem no texto, inclusive os não citados aqui.
- "area_declarada_ha": a área total do imóvel rural no recibo.
- "app_declarada_ha": a área de APP (Área de Preservação Permanente) declarada.
- "rl_declarada_ha": a área de Reserva Legal declarada.
- "area_documental_ha": SÓ quando o recibo aponta DUAS áreas diferentes para o
  mesmo imóvel — copie aqui a área "conforme documentação comprobatória de
  propriedade/posse/concessão". A outra (a de "representação gráfica") continua
  em "area_declarada_ha". Se o recibo traz uma área só, responda null aqui.
- "modulos_fiscais": o número de módulos fiscais do imóvel, quando constar
  (ex.: "Módulos Fiscais: 31,1547"). Não é área em hectares.
{
  "numero_car": null,
  "area_declarada_ha": null,
  "area_documental_ha": null,
  "municipio": null,
  "uf": null,
  "app_declarada_ha": null,
  "rl_declarada_ha": null,
  "modulos_fiscais": null,
  "status_car": null,
  "matriculas": [{"numero": null, "data": null, "livro_folha": null, "cartorio": null}],
  "confidence": {}
}
TEXTO:
{text}""",
    "ccir": """Extraia os campos deste CCIR (Certificado de Cadastro de Imóvel Rural).
Retorne APENAS JSON. Campos ausentes = null.
- "numero_ccir": o NÚMERO DO CCIR (identifica ESTE certificado; é por ele que a
  consultora LOCALIZA o documento). NÃO confundir com "codigo_sncr_incra" (o
  Código do Imóvel Rural no SNCR/INCRA, formato 000.000.000.000-0).
{"numero_ccir": null, "codigo_sncr_incra": null, "area_ha": null, "detentor": null,
 "municipio": null, "denominacao": null, "numero_matricula": null, "confidence": {}}
TEXTO:
{text}""",
    "matricula": """Esta é uma CERTIDÃO DE MATRÍCULA / Registro de Imóveis. Extraia.
Procure em TODO o texto (a matrícula tem várias seções: abertura, registros R-,
averbações AV-). Retorne APENAS JSON. Campos ausentes = null.
Instruções de completude — esclarecem os campos AMBÍGUOS; preencha TODOS os
campos do JSON abaixo que constarem no texto, inclusive os não citados aqui.
- "denominacao": o nome ATUAL do imóvel. Se a matrícula menciona nome ANTERIOR/
  histórico (ex.: "anteriormente denominada X", outra denominação na cadeia),
  inclua-o em "denominacao_anterior".
- "registro_anterior": o registro/matrícula de ORIGEM citado na abertura ou na
  cadeia desta matrícula (ex.: "havido por... R-01 da matrícula 2.923",
  "transcrição anterior nº 4.655", "oriunda da matrícula 2609"). Copie o número
  da matrícula/transcrição anterior, sem o "R-01/AV-" (ex.: "2.923"). Se não
  houver menção a registro anterior, null.
- "proprietarios": cadeia de titulares (lista [{"nome","cpf"}]).
- "area_registrada_ha": a área do IMÓVEL, a que abre a matrícula ("com área de
  X"). NÃO é a área de reserva legal, de APP, de arrendamento nem de parte
  vendida — essas são áreas de ATOS e vão em "atos", com o tipo delas. Se a
  abertura da matrícula não estiver neste trecho, responda null.
- "atos": a lista dos ATOS desta matrícula — cada registro ("R-11") e cada
  averbação ("AV.02") vira UM item, na ordem em que aparecem no texto. Diga o
  que cada ato É em "tipo", usando EXATAMENTE um destes rótulos:
  area_registrada, reserva_legal, app, georreferenciamento, compra_venda,
  sucessao, inventario, adjudicacao, formal_partilha,
  compromisso_compra_venda, arrendamento, servidao, usufruto, hipoteca,
  alienacao_fiduciaria, penhora, baixa, aditivo. Se o ato não for nenhum
  deles, use "nao_classificado" — nunca force um rótulo que não descreva o ato.
  Campos de cada item:
  · "ato": o rótulo como está no documento ("AV.02", "R-11", "R.15");
  · "data_ato": a DATA DESTE ato (registro/averbação), como escrita — não a
    data de um ato diferente que ele cite;
  · "area_ha": a área que o ato cita, copiada literalmente, quando houver;
  · "valor": o valor em dinheiro do ato, quando houver;
  · "partes": as pessoas ou instituições do ato (credor, arrendatário,
    servidão, usufruto) — copie os nomes como estão;
  · "adquirentes" / "transmitentes": em atos que TRANSFEREM titularidade
    (compra_venda, sucessao, inventario, adjudicacao, formal_partilha) — quem
    recebeu e quem transmitiu o imóvel NESTE ato, quando o texto distingue
    os dois lados ("foi adquirido por X ... por compra feita a Y" →
    adquirentes=["X"], transmitentes=["Y"]). Não preencha se o texto não
    distinguir claramente quem compra de quem vende.
  · "prazo": prazo ou vigência escritos no ato ("15 anos", "01/01/2013 a
    01/01/2028");
  · "altera_ato": quando o ato BAIXA, cancela, rescinde, quita, adita ou
    retifica outro ato DESTA MESMA MATRÍCULA, o rótulo do ato citado
    ("AV.03"). CUIDADO: não confundir com a referência de arquivamento que
    abre muitas averbações ("Averbação referente a AV.XX Mat. YYYY") — essa
    aponta para OUTRA matrícula (a anterior, na cadeia dominial) e não é
    alteração nenhuma; "altera_ato" é só quando o TEXTO DO ATO (não o
    cabeçalho) diz que ele baixa/cancela/adita/retifica algo;
  · "descricao": em uma frase, o que o ato diz.
  Reserva Legal é "reserva_legal", nunca "app". Arrendamento é "arrendamento",
  nunca "app" e nunca "reserva_legal". Preço de compra e venda é
  "compra_venda", não "hipoteca". Alienação fiduciária é
  "alienacao_fiduciaria", não "hipoteca" — e o credor é o que estiver escrito
  NAQUELE ato. Baixa de hipoteca, quitação de dívida e rescisão de
  arrendamento são "baixa", e IMPORTAM: registre cada uma, com o ato que ela
  baixa em "altera_ato".
- "codigo_certificacao": código do georreferenciamento (SIGEF/INCRA), se houver,
  SEM texto de vértice grudado.
- "nirf_cib": o NIRF/CIB DESTE imóvel na Receita Federal — 8 dígitos, no
  formato X.XXX.XXX-X. Costuma aparecer REPETIDO ao longo dos registros e
  averbações ("NIRF n°...", "CIB n°...", "na Receita Federal sob o nº ...").
  NÃO é o código do INCRA/SNCR (13 dígitos, 000.000.000.000-0) e NÃO é o
  código de um imóvel CONFRONTANTE citado na descrição de limites ("cravado
  na confrontação da Fazenda X, Código INCRA nº ..." descreve o VIZINHO).
  Copie o número exatamente como está no texto; se não houver, null.
{
  "numero_matricula": null,
  "registro_livro_folha": null,
  "cartorio": null,
  "area_registrada_ha": null,
  "denominacao": null,
  "denominacao_anterior": null,
  "registro_anterior": null,
  "proprietarios": [{"nome": null, "cpf": null}],
  "atos": [{"ato": null, "tipo": null, "data_ato": null, "area_ha": null,
            "valor": null, "partes": [], "adquirentes": [], "transmitentes": [],
            "prazo": null, "altera_ato": null, "descricao": null}],
  "numero_geo": null,
  "codigo_certificacao": null,
  "nirf_cib": null,
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


# ── N4 (09/09) — o documento que chegou vazio e ninguém foi avisado ────────
# Doc 551, a CNH-e do representante da ELODI: `ocr_status='done'`, 444 chars de
# boilerplate de assinatura digital ("QR-CODE … Medida Provisória nº 2200-2/2001
# … SENATRAN"), nenhum nome, nenhum CPF, 0 linhas de staging — e a nota na tela
# dizia "tipo sem schema de staging". A causa é OUTRA: o OCR não leu a CNH (PDF
# com o conteúdo em imagem). Motivo errado manda a consultora para o lugar
# errado: um pede mapeamento de tipo, o outro pede reprocessar o OCR.
#
# O sinal é a AUSÊNCIA DE NÚMERO LONGO num texto curto. Todo documento cadastral
# desta base carrega ao menos uma sequência de 6+ dígitos (CPF, matrícula, CAR,
# CCIR, NIRF, área): o RG da Valéria tem 849 chars e traz "2715425388"; a CNH-e
# tem 444 chars e o número mais longo é "2001". Os dois critérios juntos, porque
# nenhum sozinho basta — um texto longo sem número longo pode ser um parecer.
OCR_TEXTO_MINIMO_CHARS = 600
# Um número de 6+ dígitos CORRIDOS, ou um CPF/CNPJ formatado. Sem colar grupos
# separados antes de medir: "Medida Provisória nº 2200-2/2001" viraria "220022001"
# e a CNH-e vazia passaria por documento legível — foi o primeiro desenho e ele
# falhou no próprio caso que motivou a regra.
_SINAL_DE_DADO_RE = re.compile(
    r"\d{6,}"
    r"|\d{3}\.\d{3}\.\d{3}-\d{2}"
    r"|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
)

MOTIVO_OCR_ILEGIVEL = (
    "OCR não extraiu texto legível deste documento (provável PDF de imagem) — "
    "reprocessar o OCR; sem texto não há o que extrair"
)


def texto_sem_conteudo_legivel(texto: Optional[str]) -> bool:
    """True quando o OCR devolveu texto, mas texto que não carrega dado nenhum."""
    limpo = (texto or "").strip()
    if not limpo:
        return True
    if len(limpo) >= OCR_TEXTO_MINIMO_CHARS:
        return False
    return _SINAL_DE_DADO_RE.search(limpo) is None


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


# Campos numéricos (têm unidade) cujo valor "349.9022" e "349,9022" são o MESMO
# dado em formatos diferentes — devem deduplicar como um só (2a).
def _numeric_dedup_key(value: Any) -> Optional[str]:
    """Chave numérica canônica: o ÚLTIMO separador é o decimal; ignora milhar e
    unidade. "349.9022", "349,9022" e "349,9022 ha" → a mesma chave."""
    if isinstance(value, (dict, list)):
        return None
    s = re.sub(r"[^\d.,]", "", str(value))
    if not re.search(r"\d", s):
        return None
    last = max(s.rfind("."), s.rfind(","))
    if last >= 0:
        intp = re.sub(r"[.,]", "", s[:last])
        decp = re.sub(r"[^\d]", "", s[last + 1:])
        s = f"{intp}.{decp}" if decp else intp
    try:
        return f"num:{round(float(s), 6)}"
    except ValueError:
        return None


# Campos que esperam um CÓDIGO (UUID/identificador). O LLM às vezes preenche com
# frase/título quando não acha o valor ("Certidão de Embargo", "Coordenadas não
# disponíveis", "Plano de Recuperação (PRAD)", "Área embargada em…") — é lixo, não
# vira staging (2b).
_CODE_FIELDS = {
    "codigo_certificacao", "numero_geo", "codigo_sncr_incra",
    "codigo_incra", "numero_car", "nirf_cib",
}


def _is_garbage_for_code(value: Any) -> bool:
    """True se ``value`` é frase/título (lixo do LLM) num campo que espera código."""
    if isinstance(value, (dict, list)):
        return False
    s = str(value).strip()
    if not s:
        return False
    from app.services.inconsistency_matrix import _is_doc_title  # noqa: PLC0415
    if _is_doc_title(s):
        return True
    words = s.split()
    if len(words) >= 4:
        # frase longa SEM nenhum token que pareça código (alfanumérico com dígito) = lixo
        has_code_token = any(
            len(w) >= 6 and any(c.isdigit() for c in w) and re.fullmatch(r"[0-9A-Za-z./\-]+", w)
            for w in words
        )
        return not has_code_token
    return False


# Campos-LISTA que descrevem um conjunto (pendências, ônus): não devem virar N
# linhas de staging — colapsam em 1 por (campo, matrícula), mesmo que re-extrações
# produzam listas ligeiramente diferentes (2c).
_LIST_COLLAPSE_FIELDS = {"pendencias_rat", "onus", "proprietarios"}

# Campos de IDENTIDADE do imóvel: quem é a fazenda e de quem ela é. Errar aqui
# não é ruído — renomeia o imóvel na base e contamina o diagnóstico. No caso 15 a
# denominação do imóvel virou "Plano de Recuperação de Área Degradada (PRAD)"
# porque um contrato foi lido com a ficha do SIGEF.
_IDENTITY_FIELDS = {"denominacao", "proprietario", "detentor", "proprietarios"}

# Marcadores que provam que o documento É a fonte legítima de identidade do seu
# tipo. Tipo fora do mapa não é checado (a ficha dele já é a própria identidade).
_IDENTITY_EVIDENCE: dict[str, tuple[str, ...]] = {
    "sigef": (
        "sigef", "certificacao", "certificação", "vertice", "vértice",
        "memorial descritivo", "incra",
    ),
    "ccir": (
        "ccir", "certificado de cadastro de imovel rural",
        "certificado de cadastro de imóvel rural",
    ),
}


def _pode_declarar_identidade(doc_type: str, texto: Optional[str]) -> bool:
    """O documento tem lastro para declarar denominação/proprietário do imóvel?

    Rede de segurança independente do classificador (26/07): mesmo que um tipo
    seja atribuído por engano — por regra, por LLM ou pela mão de alguém — a
    identidade do imóvel só sai de documento que carrega a marca do seu próprio
    tipo. Sem o texto em mãos, não bloqueia (não é papel deste guard adivinhar).
    """
    marcas = _IDENTITY_EVIDENCE.get(doc_type)
    if not marcas or not texto:
        return True
    low = texto.lower()
    return any(m in low for m in marcas)


def _dedup_token(field_name: str, value: Any, unidade: Optional[str]) -> str:
    """Token de valor para a chave de dedup, ciente do tipo do campo (2a/2c)."""
    if field_name in _LIST_COLLAPSE_FIELDS:
        return "__list__"               # 1 linha por (campo, hint)
    if unidade:                          # campo numérico → normaliza formato
        nk = _numeric_dedup_key(value)
        if nk is not None:
            return nk
    return _value_key(value)


# ── Contenção 1 (ADR-064) — âncora no texto ────────────────────────────────
# Sentinela de "o valor não está no documento". Distinta de `None`, que aqui
# significa "não há como julgar" (sem texto em mãos, ou valor curto demais para
# a busca provar coisa alguma) — as duas respostas levam a caminhos opostos e
# colapsá-las num só `None` reintroduziria o silêncio que esta frente mata.
_SEM_ANCORA = object()

MOTIVO_SEM_ANCORA = (
    "valor sem âncora no documento — não foi encontrado no texto lido; "
    "não é gravado na base sem conferência"
)


def _ancorar(
    fv: dict[str, Any], value: Any, indice: Optional[TextoIndexado]
) -> Any:
    """Escreve a âncora em ``fv`` e diz se o valor pode entrar no staging.

    Devolve a :class:`Ancora` quando achou, ``None`` quando não há o que julgar,
    e :data:`_SEM_ANCORA` quando o valor NÃO está no documento — único caso que
    barra a linha.

    Sem ``texto`` em mãos não bloqueia nada: é a mesma regra do guard de
    identidade (`_pode_declarar_identidade`) — não é papel deste guard adivinhar.
    """
    if indice is None:
        return None
    if isinstance(value, (dict, list)):
        # Fronteira declarada (ADR-064): valor composto é descrição redigida
        # pelo modelo, não literal do documento. Ancoramos as folhas e
        # informamos a cobertura; barrar aqui apagaria o material da frente
        # seguinte (tipo de observação e temporalidade de ato).
        fv["ancora"] = ancorar_composto(value, indice)
        return None
    if not indice.valor_e_verificavel(value):
        fv["ancora"] = {"escopo": "nao_verificavel"}
        return None
    ancora = indice.buscar(value)
    if ancora is None:
        return _SEM_ANCORA
    fv["ancora"] = ancora.as_dict()
    return ancora


def _linha_sem_ancora(
    spec: _FieldSpec, value: Any, doc_hint: Optional[str], fv: dict[str, Any]
) -> StagingField:
    """A linha explícita do valor que não existe no documento.

    Sem destino (`target_entity`/`target_field` nulos): não pousa na base nem
    que alguém aceite — mesma regra do documento pessoal ambíguo (ENT-001).
    Fica visível na Conferência com o motivo escrito, porque "nada some sem
    dizer" (P12) vale principalmente para o que o sistema decidiu não usar.
    """
    logger.warning(
        "ficha01_extraction: %s SEM ÂNCORA no documento (não entra na base): %r",
        spec.field_name, value,
    )
    novo: dict[str, Any] = {"value": value, "sem_ancora": True, "motivo": MOTIVO_SEM_ANCORA}
    for chave in ("unidade", "fatia"):
        if chave in fv:
            novo[chave] = fv[chave]
    return StagingField(
        field_name=spec.field_name,
        field_value=novo,
        confidence="low",
        target_entity=None,
        target_field=None,
        matricula_hint=doc_hint,
    )


def _normalizar_area(
    fv: dict[str, Any], value: Any, texto: Optional[str], ancora: Any
) -> None:
    """Contenção 3 (ADR-064) — decodifica `hectares,ares.centiares` por REGRA.

    O bruto continua em ``fv["value"]`` (Item 1 da Isis: quem converte é o
    sistema, e o literal do documento nunca é reescrito); o normalizado entra ao
    lado, com o método. Quando a âncora localizou o número, o entorno é lido
    para achar o extenso — a verificação que estava a duas linhas do valor e
    ninguém lia.
    """
    entorno = entorno_do_valor(texto, ancora.pos) if isinstance(ancora, Ancora) else None
    area = normalizar_area_registral(value, entorno)
    if area is None:
        return
    fv["normalizado_ha"] = area.valor_ha
    fv["metodo_normalizacao"] = area.metodo
    if area.extenso_confere is not None:
        fv["extenso_confere"] = area.extenso_confere
        fv["extenso_ha"] = area.extenso_ha
    logger.info(
        "ficha01_extraction: área registral %r → %s ha (%s, extenso=%s)",
        value, area.valor_ha, area.metodo, area.extenso_confere,
    )


def _linhas_de_observacoes(
    observacoes: list[Observacao], indice: Optional[TextoIndexado],
    doc_hint: Optional[str], confidence: Optional[str],
    data_referencia: Optional[date] = None,
) -> list[StagingField]:
    """Atos tipados → linhas de staging, com o destino resolvido POR TIPO.

    Uma linha por ato. O destino sai do mapa enumerado
    (``observacao_registral.DESTINO_POR_TIPO``); quando o tipo não tem coluna, a
    linha nasce SEM destino e com o motivo escrito — visível na Conferência,
    nunca forçada numa gaveta alheia. É o oposto do que acontecia com a AV.10 do
    doc 548, um arrendamento de 50 ha que virava `averbacao_app`.

    Os gravames não recebem destino individual: `matricula.onus_gravames` é UMA
    coluna de texto, e N linhas disputando a mesma coluna produziriam
    reconciliação falsa (a primeira grava, as outras divergem). Eles entram
    numa linha `onus` agregada, composta só dos que o documento NÃO declara
    baixados.

    Frente F (ADR-066): antes de resolver destino, o grafo de alterações
    (baixa/aditivo → `baixado_por`/`retificado_por`) e a vigência derivada
    (`atributos["vigencia"]`) são calculados — por regra, nunca pelo LLM.

    Frente J (item 7): a orquestração (`extract_and_stage`) passa a
    `data_referencia` do PROCESSO (`opened_at`, com `created_at` como
    fallback — `data_referencia_do_processo`), nunca `date.today()`. Sem
    referência explícita, um prazo com termo final fica `indeterminado`
    (não é comparado com o relógio da máquina); os fatos (`data_ato`,
    `prazo`, `altera_ato`) ficam persistidos e quem consultar depois com a
    data do caso rederiva sem reextrair. Item 4: `ultimo_por_destino` já não
    promove ato `baixado` à coluna (a RL baixada não grava `averbacao_rl`).
    """
    aplicar_alteracoes(observacoes)
    derivar_vigencia(observacoes, data_referencia=data_referencia)
    escolhidos = ultimo_por_destino(observacoes)

    rows: list[StagingField] = []
    for obs in observacoes:
        fv: dict[str, Any] = {"value": obs.resumo()}
        if indice is not None:
            # Composto: âncora informa a cobertura, não barra (ADR-064). É assim
            # que "credor Banco do Brasil" numa alienação do Itaú aparece como
            # folha sem âncora, em vez de seguir como afirmação silenciosa.
            fv["ancora"] = ancorar_composto(obs.atributos, indice)
        destino = destino_de(obs)
        target_entity: Optional[str] = None
        target_field: Optional[str] = None
        if destino is not None and escolhidos.get(destino) is obs:
            target_entity, target_field = destino
        elif destino is not None:
            fv["sem_destino"] = True
            fv["sem_destino_motivo"] = MOTIVO_SUBSTITUIDA.format(
                ato=escolhidos[destino].ato or "outro ato desta matrícula"
            )
        elif obs.tipo in TIPOS_GRAVAME:
            fv["sem_destino"] = True
            fv["sem_destino_motivo"] = MOTIVO_GRAVAME
        else:
            fv["sem_destino"] = True
            fv["sem_destino_motivo"] = MOTIVO_SEM_CASA
        rows.append(StagingField(
            field_name=target_field or "observacao",
            field_value=fv,
            confidence=confidence,
            target_entity=target_entity,
            target_field=target_field,
            matricula_hint=doc_hint,
            tipo_observacao=obs.tipo,
            atributos=obs.atributos or None,
        ))

    vigentes = onus_vigentes(observacoes)
    if vigentes:
        fv_onus: dict[str, Any] = {"value": vigentes}
        if indice is not None:
            fv_onus["ancora"] = ancorar_composto(vigentes, indice)
        rows.append(StagingField(
            field_name="onus",
            field_value=fv_onus,
            confidence=confidence,
            target_entity="matricula",
            target_field="onus_gravames",
            matricula_hint=doc_hint,
        ))
    logger.info(
        "ficha01_extraction: %d observações tipadas (%d com destino, %d gravames vigentes)",
        len(observacoes), sum(1 for r in rows if r.target_field), len(vigentes),
    )
    return rows


def build_staging_fields(
    doc_type: str, parsed: dict[str, Any], *, texto: Optional[str] = None,
    titular_tipo: Optional[str] = None, janela: Optional[JanelaResultado] = None,
    data_referencia: Optional[date] = None,
) -> list[StagingField]:
    """Mapeia o JSON extraído → linhas de staging (sem persistir).

    Pula campos vazios. Trata listas especiais (car.matriculas → 1 linha por
    matrícula com `matricula_hint`; rat.pendencias → `pendencias_rat`).

    ``texto`` (opcional) é o conteúdo lido do documento. Quando fornecido, ativa o
    guard de identidade: denominação/proprietário só saem de documento que prova
    ser do tipo declarado (ver `_pode_declarar_identidade`).

    ``titular_tipo`` ("pf" | "pj" | None) roteia o DOCUMENTO PESSOAL (ENT-001):
    em caso PJ ele descreve o representante, não o titular. Sem essa informação
    a linha sai sem destino — pendência, nunca escrita no cliente.

    ``janela`` (ADR-064, contenção 2) traz de qual fatia do documento cada
    campo veio — vai para o ``field_value`` como rastro da leitura.
    """
    if not isinstance(parsed, dict):
        return []

    identidade_ok = _pode_declarar_identidade(doc_type, texto)
    # Índice de busca do documento: montado UMA vez e reusado por todos os
    # campos (contenção 1). Sem texto, o gate de âncora não roda.
    indice = TextoIndexado(texto) if texto else None

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

    # ── Frente E (ADR-065) — os atos da matrícula, tipados ──────────────────
    # Vêm ANTES do loop de campos porque duas decisões do loop dependem deles:
    # qual destino já está ocupado por uma observação, e se a área candidata a
    # área do imóvel é, na verdade, área de outro objeto (#221).
    observacoes = observacoes_de(parsed.get("atos")) if doc_type == "matricula" else []
    linhas_obs = (
        _linhas_de_observacoes(
            observacoes, indice, doc_hint, _conf_for(parsed, "atos"), data_referencia
        )
        if observacoes else []
    )
    destinos_ocupados = {
        (linha.target_entity, linha.target_field) for linha in linhas_obs
        if linha.target_entity and linha.target_field
    }

    for spec in _FIELD_SPECS.get(doc_type, []):
        value = parsed.get(spec.json_key)
        # Caso #12: desembrulha envelope {value, confidence} que o LLM às vezes
        # devolve — senão o dict é persistido cru (vira "3,5 milhões de ha").
        value, embedded_conf = _unwrap_llm_value(value)
        if _is_empty(value):
            continue
        # Frente E — a chave ANTIGA (`averbacao_rl`, `averbacao_app`, `onus`)
        # continua no spec para JSON legado, mas se a observação tipada já
        # ocupou o destino ela vence: o ato sabe o que é, a gaveta não.
        if (spec.target_entity, spec.target_field) in destinos_ocupados:
            logger.info(
                "ficha01_extraction: %s ignorado — destino %s.%s já preenchido por "
                "observação tipada", spec.field_name, spec.target_entity, spec.target_field,
            )
            continue
        # 2b — campo de código recebendo frase/título (lixo do LLM): descarta.
        # Guard de identidade (26/07): documento sem a marca do próprio tipo não
        # nomeia o imóvel nem o dono. WARNING de propósito — é sinal de
        # classificação errada a montante, não ruído esperado.
        if not identidade_ok and spec.field_name in _IDENTITY_FIELDS:
            logger.warning(
                "ficha01_extraction: %s ignorado — documento classificado '%s' nao "
                "apresenta marcas desse tipo (identidade nao confiavel): %r",
                spec.field_name, doc_type, value,
            )
            continue
        if spec.field_name in _CODE_FIELDS and _is_garbage_for_code(value):
            logger.info("ficha01_extraction: descartado lixo em %s: %r", spec.field_name, value)
            continue
        # 2a/2c/4c — dedup no MESMO doc: campo+hint+valor (numérico normaliza
        # formato; campo-lista colapsa) repetido vira 1 linha.
        dedup_key = (spec.field_name, doc_hint, _dedup_token(spec.field_name, value, spec.unidade))
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        fv: dict[str, Any] = {"value": value}
        if spec.unidade:
            fv["unidade"] = spec.unidade
        confidence = _conf_for(parsed, spec.json_key) or embedded_conf
        if janela is not None and spec.json_key in janela.origem:
            fv["fatia"] = janela.origem[spec.json_key]

        # ── Contenção 1 (ADR-064) — o valor está mesmo no documento? ────────
        ancora = _ancorar(fv, value, indice)
        if ancora is _SEM_ANCORA:
            rows.append(_linha_sem_ancora(spec, value, doc_hint, fv))
            continue

        # ── Contenção 3 (ADR-064) — número registral por regra ──────────────
        if spec.unidade == "ha":
            _normalizar_area(fv, value, texto, ancora)
            if fv.get("extenso_confere") is False:
                # O extenso do próprio documento discorda da regra: não há como
                # afirmar a área. Rebaixa e manda para revisão, sem escolher.
                confidence = "low"

        # 4b — validação de formato: fora do esperado → rebaixa + marca p/ revisão,
        # SEM tocar no valor bruto (preservado em fv["value"]).
        fmt_ok = check_format(spec.field_name, value)
        if fmt_ok is False:
            fv["format_ok"] = False
            confidence = "low"
        # ENT-001 — documento pessoal só sabe onde pousar depois de saber de
        # quem ele é. Fora desse caso o destino segue o spec, intocado.
        target_entity, target_field = spec.target_entity, spec.target_field
        # Frente E (#221) — forma certa, significado errado: `185,85.60` é a
        # área da RELOCAÇÃO DA RESERVA LEGAL (doc 547, Av.03), tem âncora, passa
        # no formato e normaliza bem. Se o mesmo número é a área de um ato de
        # RL/APP/arrendamento/servidão, ele não é a área do imóvel — e a linha
        # fica visível, sem destino, em vez de gravar 185,856 ha numa matrícula
        # de 926 ha.
        if spec.field_name == "area_registrada_ha" and observacoes:
            dona = area_de_outro_objeto(observacoes, value)
            if dona is not None:
                fv["sem_destino"] = True
                fv["sem_destino_motivo"] = MOTIVO_AREA_DE_OUTRO_OBJETO.format(
                    tipo=rotulo_humano(dona.tipo), ato=dona.ato or "ato sem rótulo",
                )
                logger.warning(
                    "ficha01_extraction: area_registrada_ha %r é área de %s (%s) — "
                    "linha sem destino", value, dona.tipo, dona.ato,
                )
                target_entity = target_field = None
                confidence = "low"
        if doc_type in DOC_PESSOAL_TYPES:
            target_entity = rota_documento_pessoal(titular_tipo)
            if target_entity == ENTIDADE_REPRESENTANTE:
                target_field = _REPRESENTANTE_TARGET_FIELD.get(spec.target_field)
            elif target_entity is None:
                target_field = None
            if target_entity is not None and target_field is None:
                continue
        rows.append(StagingField(
            field_name=spec.field_name,
            field_value=fv,
            confidence=confidence,
            target_entity=target_entity,
            target_field=target_field,
            matricula_hint=doc_hint,
        ))

    rows.extend(linhas_obs)

    # CAR: lista de matrículas citadas no recibo → 1 linha por item (hint = nº).
    if doc_type == "car":
        for item in parsed.get("matriculas") or []:
            if not isinstance(item, dict) or _is_empty(item):
                continue
            numero, _ = _unwrap_llm_value(item.get("numero"))
            fv_item: dict[str, Any] = {"value": item}
            if indice is not None:
                fv_item["ancora"] = ancorar_composto(item, indice)
            rows.append(StagingField(
                field_name="matricula_listada",
                field_value=fv_item,
                confidence=_conf_for(parsed, "matriculas"),
                target_entity="matricula",
                target_field="numero_matricula",
                matricula_hint=_clean_matricula_hint(numero),
            ))

    # RAT: pendências estruturadas → insumo central do diagnóstico (Fase 3).
    if doc_type == "rat":
        pendencias = parsed.get("pendencias")
        if pendencias and not _is_empty(pendencias):
            fv_pend: dict[str, Any] = {"value": pendencias}
            if indice is not None:
                fv_pend["ancora"] = ancorar_composto(pendencias, indice)
            rows.append(StagingField(
                field_name="pendencias_rat",
                field_value=fv_pend,
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
    # ADR-064, contenção 2 — quanto do documento foi efetivamente lido, e em
    # quantas fatias. Vai para o resultado do agente (e daí para o `AIJob`):
    # cobertura parcial deixa de ser invisível.
    janela: Optional[dict[str, Any]] = None
    # ADR-064, contenção 1 — linhas barradas por não existirem no texto.
    sem_ancora: list[str] = field(default_factory=list)


_SYSTEM_STAGING = (
    "Voce e um especialista em documentos fundiarios e ambientais brasileiros. "
    "Extraia os campos solicitados e retorne APENAS JSON valido. "
    "Para cada campo extraido inclua a confianca em \"confidence\": "
    "\"high\" | \"medium\" | \"low\". "
    # Item 1 (Isis 16/06): preservar o numero verbatim — quem converte e o sistema.
    "Numeros e areas: copie como STRING literal, EXATAMENTE como aparece no "
    "documento, preservando os separadores brasileiros (ex.: a area \"1.010,7113\" "
    "deve sair como \"1.010,7113\", nunca 1.0107113 nem 1010.7113). NUNCA converta "
    "o numero voce mesmo (a virgula e decimal, o ponto e milhar). Vale para "
    "area_*_ha, vtn e modulos_fiscais. "
    # ADR-064, contencao 1 — o achado N1: o `nirf_cib` "6.442.022-1" gravado na
    # matricula 3.673 nao existia no documento; era o EXEMPLO escrito no proprio
    # prompt. A regra de ancora barra isso depois; aqui a instrucao evita produzi-lo.
    "TODO valor deve ser COPIADO do texto recebido. Se o campo nao estiver no "
    "texto, responda null — nunca preencha com um exemplo, com um valor de outro "
    "documento, nem com um numero inventado. "
    # ADR-064, contencao 2 — o texto chega em pedacos sequenciais de documentos
    # longos; o modelo nao deve deduzir o que estaria fora do pedaco.
    "O texto pode ser um TRECHO de um documento maior: responda apenas sobre o "
    "que estiver neste trecho."
)


def _validador_de_formato(doc_type: str):
    """Fecha `check_format` sobre o mapa json_key → field_name deste tipo.

    A mesclagem entre fatias (contenção 2) precisa julgar candidatos pelo campo
    de STAGING, mas o JSON do LLM vem com a chave do prompt. Sem essa tradução a
    validação de formato não teria como ser consultada — e é ela que separa o
    NIRF do imóvel do código SNCR do confrontante no doc 547.
    """
    from app.services.field_validators import check_format  # noqa: PLC0415

    mapa = {s.json_key: s.field_name for s in _FIELD_SPECS.get(doc_type, [])}

    def validar(json_key: str, value: Any) -> Optional[bool]:
        field_name = mapa.get(json_key)
        return check_format(field_name, value) if field_name else None

    return validar


def _extract_structured(
    text: str,
    doc_type: str,
    *,
    on_llm_response=None,
) -> tuple[Optional[dict[str, Any]], Optional[JanelaResultado]]:
    """Extrai o JSON do documento INTEIRO e devolve (parsed, janela).

    ADR-064 contenção 2 — o documento é percorrido em fatias sequenciais com
    sobreposição (uma só fatia quando ele cabe, que é o caso da maioria), e os
    JSONs das fatias são mesclados por regra em ``extraction_window.mesclar``.
    Antes, `text[:EXTRACTOR_MAX_CHARS]` cortava em 30.000 chars e o resto do
    documento simplesmente não existia para o extrator.

    ADR-064 contenção 4 — ``on_llm_response(response, rotulo)`` recebe CADA
    resposta do gateway, para que o ``AIJob`` do extrator passe a guardar
    `raw_output`, modelo, provider, tokens e custo (hoje todos nulos).

    Fatia que falha no gateway não derruba as outras: perder um pedaço é melhor
    que perder o documento, e a cobertura efetiva fica registrada na janela.
    """
    prompt_template = _STAGING_PROMPTS.get(doc_type)
    if prompt_template is None:
        return None, None
    if not settings.ai_configured or not (text or "").strip():
        return None, None

    from app.core.ai_gateway import AIGatewayError, complete  # noqa: PLC0415

    fatias = fatiar(
        text,
        chunk_chars=settings.EXTRACTOR_CHUNK_CHARS,
        overlap_chars=settings.EXTRACTOR_CHUNK_OVERLAP_CHARS,
        max_chunks=settings.EXTRACTOR_MAX_CHUNKS,
    )
    por_fatia: list[tuple[Any, dict[str, Any]]] = []
    # Achado Codex 10/09 — cobertura declarada não pode assumir que a última
    # fatia PLANEJADA foi lida; só o que passou por aqui com sucesso conta.
    falhas: list[dict[str, Any]] = []
    for fatia in fatias:
        prompt = prompt_template.replace("{text}", text[fatia.inicio: fatia.fim])
        try:
            response = complete(prompt, system=_SYSTEM_STAGING)
        except AIGatewayError as exc:
            logger.warning(
                "ficha01_extraction: LLM falhou doc_type=%s %s: %s",
                doc_type, fatia.rotulo, exc.message,
            )
            falhas.append({
                "indice": fatia.indice, "inicio": fatia.inicio, "fim": fatia.fim,
                "erro": exc.message,
            })
            continue
        except Exception as exc:  # pragma: no cover - defensivo
            logger.warning(
                "ficha01_extraction: erro inesperado doc_type=%s %s: %s",
                doc_type, fatia.rotulo, exc,
            )
            falhas.append({
                "indice": fatia.indice, "inicio": fatia.inicio, "fim": fatia.fim,
                "erro": str(exc),
            })
            continue
        if on_llm_response is not None:
            try:
                on_llm_response(response, f"staging:{doc_type}:{fatia.rotulo}")
            except Exception as exc:  # pragma: no cover - auditoria nunca derruba
                logger.warning("ficha01_extraction: falha ao registrar chamada LLM: %s", exc)
        parsed = _parse_json(response.content)
        if parsed:
            por_fatia.append((fatia, parsed))
        else:
            logger.warning(
                "ficha01_extraction: resposta não é JSON válido doc_type=%s %s",
                doc_type, fatia.rotulo,
            )
            falhas.append({
                "indice": fatia.indice, "inicio": fatia.inicio, "fim": fatia.fim,
                "erro": "resposta do LLM não é JSON válido",
            })

    if not por_fatia:
        return None, None

    janela = mesclar(por_fatia, validar=_validador_de_formato(doc_type))
    janela.fatias = fatias
    janela.total_chars = len(text)
    # A última fatia PROCESSADA COM SUCESSO, não a última planejada — se ela
    # falhar, `por_fatia` já não a inclui e a cobertura para de mentir.
    janela.cobertura_chars = por_fatia[-1][0].fim
    janela.falhas = falhas
    janela.completa = not falhas
    janela.truncado = janela.cobertura_chars < janela.total_chars
    if not janela.completa:
        logger.warning(
            "ficha01_extraction: %d fatia(s) falharam doc_type=%s — cobertura declarada %d/%d",
            len(falhas), doc_type, janela.cobertura_chars, janela.total_chars,
        )
    if janela.truncado:
        logger.warning(
            "ficha01_extraction: teto de fatias atingido doc_type=%s — lidos %d de %d chars",
            doc_type, janela.cobertura_chars, janela.total_chars,
        )
    logger.info(
        "ficha01_extraction: janela doc_type=%s fatias=%d cobertura=%d/%d completa=%s",
        doc_type, len(fatias), janela.cobertura_chars, janela.total_chars, janela.completa,
    )
    return janela.parsed, janela


def titular_tipo_do_processo(db_session, tenant_id: int,
                             process_id: Optional[int]) -> Optional[str]:
    """"pf" | "pj" do titular do caso, ou None quando não dá para saber.

    None é resposta legítima e frequente (documento subido antes de o caso ter
    cliente). Quem chama trata como ambiguidade — não como PF por omissão, que
    era justamente o default cego.
    """
    if not process_id:
        return None
    from app.models.client import Client  # noqa: PLC0415
    from app.models.process import Process  # noqa: PLC0415

    row = (
        db_session.query(Client.client_type)
        .join(Process, Process.client_id == Client.id)
        .filter(Process.id == process_id, Process.tenant_id == tenant_id)
        .first()
    )
    if not row or row[0] is None:
        return None
    tipo = row[0]
    return getattr(tipo, "value", tipo)


def data_referencia_do_processo(
    db_session, tenant_id: int, process_id: Optional[int]
) -> Optional[date]:
    """Data estável do caso para regras temporais; nunca depende do relógio atual."""
    if process_id is None:
        return None
    from app.models.process import Process  # noqa: PLC0415

    processo = (
        db_session.query(Process)
        .filter(Process.id == process_id, Process.tenant_id == tenant_id)
        .first()
    )
    if processo is None:
        return None
    marco = processo.opened_at or processo.created_at
    return marco.date() if marco is not None else None


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
    on_llm_response=None,
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

    parsed, janela = _extract_structured(text, dt, on_llm_response=on_llm_response)
    if not parsed:
        return StagingResult(doc_type=dt, rows_written=0, skipped_reason="extração vazia/falha")

    # `texto=` liga o guard de identidade: o próprio conteúdo do documento é a
    # prova de que ele pode nomear o imóvel/dono (26/07, caso 15).
    # `titular_tipo=` liga o roteamento do documento pessoal (ENT-001).
    fields = build_staging_fields(
        dt, parsed, texto=text,
        titular_tipo=titular_tipo_do_processo(db_session, tenant_id, process_id),
        janela=janela,
        data_referencia=data_referencia_do_processo(db_session, tenant_id, process_id),
    )

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
        fv = existing.field_value if isinstance(existing.field_value, dict) else {}
        ev = fv.get("value", existing.field_value)
        seen.add((existing.field_name, existing.matricula_hint,
                  _dedup_token(existing.field_name, ev, fv.get("unidade"))))

    written = 0
    for f in fields:
        key = (f.field_name, f.matricula_hint,
               _dedup_token(f.field_name, f.field_value.get("value"), f.field_value.get("unidade")))
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
            tipo_observacao=f.tipo_observacao,
            atributos=f.atributos,
            status=ExtractedFieldStatus.pendente,
            created_by_agent=created_by_agent,
            ai_job_id=ai_job_id,
        ))
        written += 1
    db_session.flush()

    # DOC-001 (Frente H) — extração é um degrau da escada do documento;
    # gatilho automático (sem autor humano), só quando algo de fato pousou.
    # Tenant explícito no filtro (achado do code review): `.get()` por PK nua
    # deixaria um `document_id` de outro tenant escrever no `audit_log`
    # DAQUELE tenant (`registrar_transicao_se_mudou` usa `document.tenant_id`).
    if written > 0 and document_id is not None:
        from app.models.document import Document  # noqa: PLC0415
        from app.services.document_lifecycle import registrar_transicao_se_mudou  # noqa: PLC0415

        doc_para_sincronizar = (
            db_session.query(Document)
            .filter(Document.id == document_id, Document.tenant_id == tenant_id)
            .first()
        )
        if doc_para_sincronizar is not None:
            registrar_transicao_se_mudou(db_session, doc_para_sincronizar, user_id=None)

    sem_ancora = [
        f.field_name for f in fields
        if isinstance(f.field_value, dict) and f.field_value.get("sem_ancora")
    ]
    logger.info(
        "ficha01_extraction: staging doc_type=%s document_id=%s process_id=%s rows=%d "
        "(dedup: %d→%d, sem âncora: %d)",
        dt, document_id, process_id, written, len(fields), written, len(sem_ancora),
    )
    return StagingResult(
        doc_type=dt, rows_written=written, fields=fields,
        janela=janela.resumo() if janela is not None else None,
        sem_ancora=sem_ancora,
    )


# ---------------------------------------------------------------------------
# Saneamento RETROATIVO do staging já gravado (mesma regra do #81, aplicada a
# linhas que entraram ANTES da limpeza-na-origem). Idempotente.
# ---------------------------------------------------------------------------

@dataclass
class SaneamentoResult:
    """Resumo de um saneamento retroativo (antes×depois + o que saiu)."""

    process_id: Optional[int]
    rows_before: int
    rows_after: int
    garbage_removed: int = 0       # 2b — lixo em campo de código
    duplicates_removed: int = 0    # 2a — duplicata de formato (escalares)
    lists_collapsed: int = 0       # 2c — lista repetida colapsada
    decisions_preserved: int = 0   # lixo/duplicata que carregava decisão do consultor
    removed_ids: list[int] = field(default_factory=list)
    details: list[str] = field(default_factory=list)

    @property
    def total_removed(self) -> int:
        return self.garbage_removed + self.duplicates_removed + self.lists_collapsed


def _staging_value_unidade(row) -> tuple[Any, Optional[str]]:
    """Reconstrói (value, unidade) de uma linha de staging — mesmo shape que o
    dedup da origem (``field_value = {"value": ..., "unidade": ...}``)."""
    fv = row.field_value if isinstance(row.field_value, dict) else {}
    value = fv.get("value", row.field_value)
    unidade = fv.get("unidade") if isinstance(fv, dict) else None
    return value, unidade


def _is_consultor_decided(row, status_enum) -> bool:
    """True se a linha carrega uma DECISÃO explícita do consultor (aceito/rejeitado).

    ``consistente``/``divergente_*`` são propostas da matriz (re-deriváveis), não
    decisões — podem ser deduplicadas. ``pendente`` idem."""
    return row.status in (status_enum.aceito, status_enum.rejeitado)


def _pick_canonical(grp: list, *, is_list: bool, status_enum) -> Any:
    """Escolhe a linha canônica de um grupo de redundantes.

    Preferência (maior vence): decisão do consultor > 'aceito' sobre 'rejeitado' >
    (lista: mais itens) > (escalar: formato BR com vírgula) > menor id (mais antiga).
    Pôr a decidida como sobrevivente PRESERVA a decisão sem precisar transferi-la."""
    def score(r) -> tuple:
        decided = 1 if _is_consultor_decided(r, status_enum) else 0
        accepted = 1 if r.status == status_enum.aceito else 0
        value, _ = _staging_value_unidade(r)
        richness = len(value) if (is_list and isinstance(value, list)) else 0
        br = 1 if (not is_list and isinstance(value, str) and "," in value) else 0
        return (decided, accepted, richness, br, -(r.id or 0))
    return max(grp, key=score)


def sanear_staging_process(
    db_session,
    *,
    tenant_id: int,
    process_id: int,
    dry_run: bool = False,
) -> SaneamentoResult:
    """Aplica a regra de limpeza do #81 ao staging JÁ existente de um processo.

    A limpeza-na-origem (``build_staging_fields``/``extract_and_stage``) só vale
    para extrações novas; este saneamento sana o que entrou antes. Três regras,
    todas reusando os helpers da origem (sem nova heurística):

    - 2b LIXO em campo de código: ``field_name`` em :data:`_CODE_FIELDS` e
      :func:`_is_garbage_for_code` → remove (não é código). PRESERVA a linha se
      o consultor já decidiu sobre ela (não apagamos decisão sem necessidade).
    - 2a DUPLICATA DE FORMATO: linhas escalares que normalizam para o MESMO
      número ("349.9022"≡"349,9022") por (fonte, campo, hint) → mantém 1.
    - 2c LISTA REPETIDA: ``pendencias_rat``/``onus`` (:data:`_LIST_COLLAPSE_FIELDS`)
      → 1 linha por (fonte, campo, hint).

    A chave de agrupamento (fonte, campo, hint, token) usa o MESMO
    :func:`_dedup_token` da origem, então valores genuinamente diferentes (token
    distinto) NUNCA são fundidos — divergências reais seguem como insumo da matriz.
    Idempotente: rodar 2× não remove nada na 2ª passada.
    """
    from app.models.extracted_field_staging import (  # noqa: PLC0415
        ExtractedFieldStaging,
        ExtractedFieldStatus,
    )

    rows = (
        db_session.query(ExtractedFieldStaging)
        .filter(
            ExtractedFieldStaging.tenant_id == tenant_id,
            ExtractedFieldStaging.process_id == process_id,
        )
        .order_by(ExtractedFieldStaging.id.asc())
        .all()
    )
    result = SaneamentoResult(
        process_id=process_id, rows_before=len(rows), rows_after=len(rows),
    )

    to_delete: list[Any] = []
    survivors: list[Any] = []

    # ── 2b — lixo em campo de código ────────────────────────────────────────
    for row in rows:
        value, _ = _staging_value_unidade(row)
        if row.field_name in _CODE_FIELDS and _is_garbage_for_code(value):
            if _is_consultor_decided(row, ExtractedFieldStatus):
                result.decisions_preserved += 1
                result.details.append(
                    f"id={row.id} lixo em {row.field_name} PRESERVADO "
                    f"(decisão do consultor: {row.status.value})"
                )
                survivors.append(row)
                continue
            to_delete.append(row)
            result.garbage_removed += 1
            result.details.append(f"id={row.id} lixo removido em {row.field_name}: {value!r}")
        else:
            survivors.append(row)

    # ── 2a/2c — duplicata de formato + lista repetida ───────────────────────
    groups: dict[tuple, list[Any]] = {}
    for row in survivors:
        value, unidade = _staging_value_unidade(row)
        token = _dedup_token(row.field_name, value, unidade)
        key = (row.source_doc_type, row.field_name, row.matricula_hint, token)
        groups.setdefault(key, []).append(row)

    for key, grp in groups.items():
        if len(grp) <= 1:
            continue
        is_list = key[1] in _LIST_COLLAPSE_FIELDS
        winner = _pick_canonical(grp, is_list=is_list, status_enum=ExtractedFieldStatus)
        for row in grp:
            if row is winner:
                continue
            if _is_consultor_decided(row, ExtractedFieldStatus):
                result.decisions_preserved += 1
            to_delete.append(row)
            if is_list:
                result.lists_collapsed += 1
            else:
                result.duplicates_removed += 1
            result.details.append(
                f"id={row.id} redundante de {row.field_name} "
                f"(canônica id={winner.id}) removido"
                + (" [colapso de lista]" if is_list else " [duplicata de formato]")
            )

    if not dry_run:
        for row in to_delete:
            db_session.delete(row)
        db_session.flush()

    result.removed_ids = [r.id for r in to_delete]
    result.rows_after = result.rows_before - len(to_delete)

    logger.info(
        "sanear_staging: process_id=%s before=%d after=%d (lixo=%d, formato=%d, "
        "lista=%d, decisões_preservadas=%d, dry_run=%s)",
        process_id, result.rows_before, result.rows_after, result.garbage_removed,
        result.duplicates_removed, result.lists_collapsed, result.decisions_preserved,
        dry_run,
    )
    return result


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
