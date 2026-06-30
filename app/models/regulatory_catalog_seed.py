"""Seed inicial do ``regulatory_issue_catalog`` (PROMPT_5 Onda A).

Único source-of-truth do seed inicial. Usado por:
- ``alembic/versions/c1b2d3e4f5a7_prompt5_remodelar_regulatory_issue.py``
  (migration que cria a tabela e popula).
- ``tests/models/conftest.py`` (testes que usam ``create_all`` precisam
  popular o catálogo manualmente).

Origem da taxonomia: skill ``app/skills/auditor_imovel/
analise_divergencias_documentais/SKILL.md`` v1.1.0 (validada pela sócia).
Marcadores ``📄`` / ``🛰️`` / ``🔌`` → factibilidade
``documental`` / ``geoespacial`` / ``consulta_externa``.

**Catálogo evolutivo:** adicionar um novo código aqui (e via migration de
data ou INSERT direto em produção) NÃO exige migration de schema.
"""

from __future__ import annotations

from typing import Any

# Cada entrada: (codigo_alerta, familia, descricao_curta, factibilidade,
#                severity_base, muda_rota, muda_escopo, docs_cruzados_default)
REGULATORY_ISSUE_CATALOG_SEED: list[tuple[str, str, str, str, str, bool, bool, list[str]]] = [
    # --- Identificacao (📄) ---
    ("IDENT_NOME_IMOVEL_DIVERGENTE", "identificacao",
     "Nome do imóvel difere entre documentos",
     "documental", "atencao", False, True, ["Matricula", "CAR"]),
    ("IDENT_MUNICIPIO_LOCALIZACAO_DIVERGENTE", "identificacao",
     "Município/localização não batem entre documentos",
     "documental", "alto", True, True, ["Matricula", "CAR"]),
    ("IDENT_MATRICULAS_MULTIPLAS_NAO_CLARAS", "identificacao",
     "Múltiplas matrículas sem composição clara",
     "documental", "alto", True, True, ["Matricula"]),

    # --- Titularidade (todas 📄) ---
    ("TIT_PROP_MATRICULA_X_CAR", "titularidade",
     "Proprietário do CAR diverge da matrícula",
     "documental", "alto", True, True, ["Matricula", "CAR"]),
    ("TIT_PROP_MATRICULA_X_CCIR", "titularidade",
     "Titular do CCIR diverge da matrícula",
     "documental", "alto", True, True, ["Matricula", "CCIR"]),
    ("TIT_CPF_CNPJ_DIVERGENTE", "titularidade",
     "Nome parecido, CPF/CNPJ divergente ou ausente",
     "documental", "alto", True, True, ["Matricula", "CAR", "CCIR"]),
    ("TIT_PF_X_PJ_OPERACAO", "titularidade",
     "Imóvel em PF e operação em PJ (ou vice-versa)",
     "documental", "alto", True, True, ["Matricula", "Licenca"]),
    ("TIT_ESPOLIO_INVENTARIO", "titularidade",
     "Matrícula em nome de falecido / herdeiros não regularizados",
     "documental", "alto", True, True, ["Matricula"]),
    ("TIT_ARRENDATARIO_POSSEIRO_CONFUNDIDO", "titularidade",
     "Cliente explora mas não é proprietário registral",
     "documental", "alto", True, True, ["Matricula", "ContratoArrendamento"]),

    # --- Area (todas 📄) — aplicar régua de área ---
    ("AREA_MATRICULA_X_CAR", "area",
     "Área matrícula vs CAR diverge",
     "documental", "atencao", False, True, ["Matricula", "CAR"]),
    ("AREA_MATRICULA_X_GEO", "area",
     "Área matrícula vs GEO/SIGEF diverge",
     "documental", "alto", False, True, ["Matricula", "GEO"]),
    ("AREA_CAR_X_GEO", "area",
     "Área CAR vs GEO/SIGEF diverge",
     "documental", "alto", False, True, ["CAR", "GEO"]),
    ("AREA_CAR_X_CCIR", "area",
     "Área CAR vs CCIR diverge",
     "documental", "atencao", False, True, ["CAR", "CCIR"]),
    ("AREA_CAR_X_ITR_CIB", "area",
     "Área CAR vs ITR/CIB diverge",
     "documental", "atencao", False, True, ["CAR", "ITR"]),
    ("AREA_SOMA_MATRICULAS_X_CAR", "area",
     "Soma de múltiplas matrículas vs área CAR diverge",
     "documental", "alto", False, True, ["Matricula", "CAR"]),
    # Extensões naturais — pares usados pelo property_audit que a skill não
    # nomeou explicitamente (catálogo evolutivo aceita extensão sem migration).
    ("AREA_MATRICULA_X_CCIR", "area",
     "Área matrícula vs CCIR diverge",
     "documental", "atencao", False, True, ["Matricula", "CCIR"]),
    ("AREA_MATRICULA_X_ITR", "area",
     "Área matrícula vs ITR diverge",
     "documental", "atencao", False, True, ["Matricula", "ITR"]),

    # --- GEO/INCRA (todas 📄) ---
    ("GEO_AUSENTE", "geo_incra",
     "Matrícula sem GEO certificado pelo INCRA",
     "documental", "alto", True, True, ["Matricula"]),
    ("GEO_CERTIFICADO_NAO_AVERBADO", "geo_incra",
     "GEO existe mas não consta averbado na matrícula",
     "documental", "alto", True, True, ["Matricula", "GEO"]),
    ("SIGEF_TITULAR_ANTIGO", "geo_incra",
     "SIGEF mostra antigo proprietário (cadeia dominial)",
     "documental", "alto", False, True, ["SIGEF", "Matricula"]),
    ("SIGEF_NOME_IMOVEL_DIVERGENTE_MATRICULA", "geo_incra",
     "SIGEF com nome de imóvel divergente da matrícula",
     "documental", "atencao", False, True, ["SIGEF", "Matricula"]),
    ("SIGEF_REGISTRO_CARTORIO_NAO_CONFIRMADO", "geo_incra",
     "GEO certificado sem averbação cartorial (insegurança registral)",
     "documental", "alto", True, True, ["SIGEF", "Matricula"]),

    # --- CAR (1🛰️ + 2📄) ---
    ("CAR_LOCALIZACAO_DIVERGENTE_REALIDADE", "car",
     "CAR deslocado da realidade",
     "geoespacial", "critico", True, True, ["CAR", "GEO"]),
    ("CAR_ANTERIOR_AO_GEO_REQUER_RETIFICACAO", "car",
     "CAR feito antes do GEO (datas)",
     "documental", "alto", True, True, ["CAR", "GEO"]),
    ("CAR_MATRICULA_NAO_RASTREAVEL", "car",
     "CAR não informa/rastreia a matrícula",
     "documental", "alto", False, True, ["CAR", "Matricula"]),

    # --- Geoespacial (todas 🛰️) ---
    ("GEO_POLIGONO_DESLOCADO_CAR", "geoespacial",
     "Polígono GEO deslocado do CAR",
     "geoespacial", "critico", True, True, ["CAR", "GEO"]),
    ("GEO_SOBREPOSICAO_TERCEIRO", "geoespacial",
     "Sobreposição com terceiro (sempre crítico)",
     "geoespacial", "critico", True, True, ["CAR", "Matricula"]),
    ("GEO_CONFRONTANTES_DIVERGENTES", "geoespacial",
     "Confrontantes divergentes entre fontes",
     "geoespacial", "alto", False, True, ["CAR", "Matricula"]),
    ("GEO_ERRO_DATUM_FUSO_PROJECAO", "geoespacial",
     "Erro de datum/fuso/projeção (reprocessar arquivo antes de concluir)",
     "geoespacial", "atencao", False, True, ["CAR", "GEO"]),

    # --- Ambiental ---
    ("RL_MATRICULA_DIVERGENTE_RL_CAR", "ambiental",
     "RL averbada vs RL declarada no CAR diverge",
     "documental", "alto", True, True, ["Matricula", "CAR"]),
    ("RL_CAR_X_REALIDADE", "ambiental",
     "RL declarada não existe na imagem",
     "geoespacial", "critico", True, True, ["CAR", "Imagem"]),
    ("RL_INSUFICIENTE", "ambiental",
     "Percentual de RL aparenta insuficiente vs norma do bioma (H19)",
     "documental", "alto", True, True, ["CAR"]),
    ("APP_OMITIDA", "ambiental",
     "APP omitida no CAR",
     "geoespacial", "alto", True, True, ["CAR", "Imagem"]),
    ("APP_OCUPADA", "ambiental",
     "APP ocupada (passivo)",
     "geoespacial", "alto", True, True, ["CAR", "Imagem"]),
    ("AREA_CONSOLIDADA_DUVIDOSA", "ambiental",
     "Área consolidada duvidosa",
     "geoespacial", "alto", True, True, ["CAR", "Imagem"]),
    ("SUPRESSAO_SEM_AUTORIZACAO_APARENTE", "ambiental",
     "Supressão de vegetação sem autorização aparente",
     "geoespacial", "critico", True, True, ["CAR", "Imagem"]),
    ("VEGETACAO_NATIVA_SUBDECLARADA", "ambiental",
     "Vegetação nativa subdeclarada (oportunidade PSA/carbono)",
     "geoespacial", "atencao", False, True, ["CAR", "Imagem"]),

    # --- Fiscal / Cadastral (📄) ---
    ("CCIR_TITULAR_DESATUALIZADO", "fiscal",
     "CCIR com titular desatualizado",
     "documental", "alto", False, True, ["CCIR", "Matricula"]),
    ("CCIR_EXERCICIO_ANTERIOR", "fiscal",
     "CCIR de exercício anterior",
     "documental", "atencao", False, True, ["CCIR"]),
    ("ITR_CIB_DIVERGENTE", "fiscal",
     "ITR/CIB divergente entre fontes",
     "documental", "atencao", False, True, ["ITR", "CAR"]),
    ("ONUS_GARANTIA_BANCARIA", "fiscal",
     "Ônus / hipoteca / alienação / penhora na matrícula",
     "documental", "alto", True, True, ["Matricula"]),

    # --- Validade documental (📄) ---
    ("DOCUMENTO_DESATUALIZADO_OU_VENCIDO", "validade_documental",
     "Documento desatualizado ou vencido (matrícula > 30 dias é alerta operacional)",
     "documental", "atencao", False, True, []),
    ("DOCUMENTO_AUSENTE", "validade_documental",
     "Documento essencial ausente",
     "documental", "atencao", False, True, []),
    ("OUTRO_GENERICO", "validade_documental",
     "Achado sem código específico (catch-all; usar com parcimônia)",
     "documental", "atencao", False, False, []),

    # --- Restrição / risco ---
    ("EMBARGO_NAO_INFORMADO", "restricao_risco",
     "Embargo (IBAMA) não informado",
     "consulta_externa", "critico", True, True, []),
    ("AUTO_INFRACAO_PASSIVO", "restricao_risco",
     "Auto de infração / passivo regulatório",
     "consulta_externa", "alto", True, True, []),
    ("RESTRICAO_TERRITORIAL_NAO_INFORMADA", "restricao_risco",
     "Restrição territorial (UC/APA/TI/quilombola) não informada",
     "geoespacial", "alto", True, True, ["CAR"]),

    # --- Licenciamento (🔌) ---
    ("LICENCA_OUTORGA_AUSENTE_VENCIDA", "licenciamento",
     "Licença / outorga ausente ou vencida",
     "consulta_externa", "alto", True, True, []),

    # --- Interno do sistema (não da sócia) ---
    # APOSENTADO (ADR-020): "verificação espacial pendente" virou NOTA DERIVADA na
    # leitura (GET /properties/{id}/diagnosis-notes quando geom IS NULL) — não é
    # mais emitida como RegulatoryIssue. A entrada PERMANECE no catálogo só para a
    # FK das linhas legadas continuar válida até a limpeza retroativa (Parte 2);
    # nada mais cria issues com este código. Quando D1 popular geom, os achados
    # espaciais REAIS terão códigos próprios.
    ("VERIFICACAO_ESPACIAL_PENDENTE", "geoespacial",
     "Verificação espacial não pôde ser executada (Property.geom ausente) — APOSENTADO (ADR-020)",
     "geoespacial", "informativo", False, False, []),
]


def seed_rows_as_dicts() -> list[dict[str, Any]]:
    """Materializa o seed como ``list[dict]`` pronto para ``op.bulk_insert``
    ou ``session.bulk_insert_mappings``."""
    return [
        dict(
            codigo_alerta=row[0],
            familia=row[1],
            descricao_curta=row[2],
            factibilidade=row[3],
            severity_base=row[4],
            muda_rota_regulatoria=row[5],
            muda_escopo_preco_prazo=row[6],
            documentos_cruzados_default=row[7],
        )
        for row in REGULATORY_ISSUE_CATALOG_SEED
    ]


def seed_catalog(session: Any) -> int:
    """Popula ``regulatory_issue_catalog`` se estiver vazio. Idempotente —
    seguro chamar em testes que reusam DB. Retorna número de linhas inseridas
    (0 se já estava populado)."""
    from app.models.regulatory import RegulatoryIssueCatalog  # noqa: PLC0415

    count = session.query(RegulatoryIssueCatalog).count()
    if count > 0:
        return 0
    for row in seed_rows_as_dicts():
        session.add(RegulatoryIssueCatalog(**row))
    session.flush()
    return len(REGULATORY_ISSUE_CATALOG_SEED)
