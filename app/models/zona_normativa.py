"""Zona normativa — catálogo global de fontes (ADR-075 + adendos A1–A5).

Separação de eixos (Ontologia §10): autoridade da FONTE (`nivel_autoridade`),
estado de VALIDAÇÃO da versão (`status_validacao`) e autoridade do USUÁRIO que
valida (`PapelCuradoria`) são coisas diferentes e moram em lugares diferentes.

- `FonteNormativa` — o ato (ou documento não normativo) com identidade canônica.
  O nível é da fonte; o trecho herda por junção (ADR-070 §12).
- `FonteNormativaVersao` — o texto de uma redação, com status `bruto → proposto →
  validado`, vigência e hash do original (A5). Nova redação é versão nova, nunca
  sobrescrita.
- `FonteNormativaProveniencia` — de onde o texto veio: coletânea, páginas, URL
  impressa. O mesmo ato em duas coletâneas é UMA fonte com duas proveniências.
- `Dispositivo` (A1) — artigo/parágrafo endereçável; é a chave que a citação por ID
  confere. O trecho aponta para o dispositivo, não o contrário.
- `TrechoNormativo` — unidade de busca (vetor + tsvector). Só indexa.
- `InterpretacaoNorma` — liga a interpretação à norma/dispositivo que ela
  interpreta (emenda ao ADR-038 §6: anexada, não disputa vaga).
- `ValidacaoNorma` (A1) — evento append-only com hash chain própria do catálogo.
- `PapelCuradoria` (A2) — quem pode escrever/validar no catálogo, por área.
- `TarefaRevisaoNormativa` — fronteira ambígua, identidade não fechada, original
  divergente (A5), conflito material.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.knowledge_catalog import _Vector

NIVEIS_AUTORIDADE = (
    "norma", "interpretacao", "exigencia", "procedimento", "precedente", "radar",
    "nao_determinado",
)
STATUS_VALIDACAO = ("bruto", "proposto", "validado")


def _in(col: str, valores: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in valores)})"


class FonteNormativa(Base):
    __tablename__ = "fonte_normativa"

    id = Column(Integer, primary_key=True)
    # tipo|ente|orgao|numero|ano — `zona_normativa.identidade`, função única.
    identidade = Column(String(220), nullable=False, unique=True)
    identidade_determinada = Column(Boolean, nullable=False)
    tipo = Column(String(40), nullable=False)
    ente = Column(String(2), nullable=False)          # 'br' ou UF minúscula
    orgao = Column(String(40), nullable=False, server_default="")
    numero = Column(String(200), nullable=False, server_default="")
    ano = Column(Integer, nullable=True)
    esfera = Column(String(12), nullable=False)
    uf = Column(String(2), nullable=True)
    rotulo = Column(String(220), nullable=False)
    titulo = Column(Text, nullable=True)

    nivel_autoridade = Column(String(20), nullable=False, server_default="nao_determinado")
    # Qual regra classificou — parâmetro provisório sai declarado como tal.
    nivel_origem = Column(String(80), nullable=False)
    # Objetivos canônicos (DemandType). NULL = não declarado (sai marcado, não some).
    objetivos = Column(ARRAY(String(40)), nullable=True)
    objetivos_origem = Column(String(80), nullable=True)

    # A3 — só precedente pode ser privado de um tenant; o resto é global.
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(_in("nivel_autoridade", NIVEIS_AUTORIDADE), name="ck_fonte_nivel"),
        CheckConstraint("esfera IN ('federal','estadual','municipal')", name="ck_fonte_esfera"),
        CheckConstraint(
            "tenant_id IS NULL OR nivel_autoridade = 'precedente'", name="ck_fonte_so_precedente_privado"
        ),
        CheckConstraint(
            "nivel_autoridade <> 'precedente' OR tenant_id IS NOT NULL",
            name="ck_fonte_precedente_privado_por_padrao",
        ),
        Index("ix_fonte_normativa_nivel", "nivel_autoridade"),
        Index("ix_fonte_normativa_tenant_id", "tenant_id"),
        Index("ix_fonte_normativa_uf", "uf"),
    )


class FonteNormativaVersao(Base):
    __tablename__ = "fonte_normativa_versao"

    id = Column(Integer, primary_key=True)
    fonte_id = Column(Integer, ForeignKey("fonte_normativa.id", ondelete="RESTRICT"), nullable=False)
    status_validacao = Column(String(12), nullable=False, server_default="bruto")
    # Vigência da NORMA. `nao_determinada` NÃO é vigente: sai marcada e só entra
    # onde o uso aceita (ADR-075 §7).
    vigencia_estado = Column(String(16), nullable=False, server_default="nao_determinada")
    vigencia_inicio = Column(Date, nullable=True)
    vigencia_fim = Column(Date, nullable=True)
    texto = Column(Text, nullable=False)
    hash_texto = Column(String(64), nullable=False)
    # A5 — bytes originais (arquivo de onde o texto foi extraído) e onde estão.
    hash_original = Column(String(64), nullable=True)
    original_storage_key = Column(String(500), nullable=True)
    original_conferido_em = Column(DateTime(timezone=True), nullable=True)
    # Divergência do original bloqueia a versão para citação (zero tolerância).
    bloqueio_citacao = Column(String(40), nullable=True)
    substitui_versao_id = Column(
        Integer, ForeignKey("fonte_normativa_versao.id", ondelete="RESTRICT"), nullable=True
    )
    origem_ingestao = Column(String(40), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("fonte_id", "hash_texto", name="uq_versao_fonte_hash"),
        CheckConstraint(_in("status_validacao", STATUS_VALIDACAO), name="ck_versao_status"),
        CheckConstraint(
            "vigencia_estado IN ('determinada','nao_determinada')", name="ck_versao_vigencia_estado"
        ),
        CheckConstraint(
            "hash_texto ~ '^[0-9a-f]{64}$' AND (hash_original IS NULL OR hash_original ~ '^[0-9a-f]{64}$')",
            name="ck_versao_hashes",
        ),
        Index("ix_fonte_normativa_versao_fonte", "fonte_id"),
        Index("ix_fonte_normativa_versao_substitui_versao_id", "substitui_versao_id"),
    )


class FonteNormativaProveniencia(Base):
    __tablename__ = "fonte_normativa_proveniencia"

    id = Column(Integer, primary_key=True)
    fonte_versao_id = Column(
        Integer, ForeignKey("fonte_normativa_versao.id", ondelete="RESTRICT"), nullable=False
    )
    # Documento de origem: linha do legado (coletânea ou norma avulsa) ou, para as
    # 282 fichas SEMAD que só existem como chunks, o `source_ref` do catálogo.
    legislation_document_id = Column(
        Integer, ForeignKey("legislation_documents.id", ondelete="RESTRICT"), nullable=True
    )
    source_ref = Column(String(255), nullable=True)
    documento_origem_rotulo = Column(String(255), nullable=False)
    offset_inicio = Column(Integer, nullable=True)
    offset_fim = Column(Integer, nullable=True)
    pagina_inicio = Column(Integer, nullable=True)
    pagina_fim = Column(Integer, nullable=True)
    url_impressa = Column(Text, nullable=True)
    impresso_em = Column(String(20), nullable=True)
    sinal_fronteira = Column(String(30), nullable=False)
    motivos_revisao = Column(ARRAY(String(60)), nullable=True)
    trecho_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "legislation_document_id IS NOT NULL OR source_ref IS NOT NULL",
            name="ck_proveniencia_tem_origem",
        ),
        CheckConstraint(
            "sinal_fronteira IN ('impressao','cabecalho_formal','sem_sinal','documento_inteiro')",
            name="ck_proveniencia_sinal",
        ),
        Index("ix_proveniencia_versao", "fonte_versao_id"),
        Index("ix_proveniencia_doc", "legislation_document_id"),
    )


class Dispositivo(Base):
    """A1 — `caminho` completo e legível, único por versão."""

    __tablename__ = "dispositivo"

    id = Column(Integer, primary_key=True)
    fonte_versao_id = Column(
        Integer, ForeignKey("fonte_normativa_versao.id", ondelete="RESTRICT"), nullable=False
    )
    # "Lei 12.651/2012, art. 61-A, § 4º" — rótulo da fonte + caminho interno.
    caminho = Column(String(300), nullable=False)
    tipo = Column(String(20), nullable=False)          # preambulo | artigo | paragrafo | anexo
    artigo = Column(String(20), nullable=True)         # "61-A"
    paragrafo = Column(String(20), nullable=True)      # "4" | "unico"
    parent_id = Column(Integer, ForeignKey("dispositivo.id", ondelete="RESTRICT"), nullable=True)
    ordem = Column(Integer, nullable=False)
    texto = Column(Text, nullable=False)
    hash = Column(String(64), nullable=False)

    __table_args__ = (
        UniqueConstraint("fonte_versao_id", "caminho", name="uq_dispositivo_caminho"),
        CheckConstraint("tipo IN ('preambulo','artigo','paragrafo','anexo')", name="ck_dispositivo_tipo"),
        Index("ix_dispositivo_versao_artigo", "fonte_versao_id", "artigo"),
        Index("ix_dispositivo_parent_id", "parent_id"),
    )


class TrechoNormativo(Base):
    __tablename__ = "trecho_normativo"

    id = Column(BigInteger, primary_key=True)
    fonte_versao_id = Column(
        Integer, ForeignKey("fonte_normativa_versao.id", ondelete="RESTRICT"), nullable=False
    )
    dispositivo_id = Column(Integer, ForeignKey("dispositivo.id", ondelete="RESTRICT"), nullable=True)
    ordem = Column(Integer, nullable=False)
    # "Decreto 6.514/2008, art. 18" — entra no tsvector: número de norma e de
    # artigo são tokens exatos que o texto do dispositivo nem sempre repete.
    cabecalho = Column(String(300), nullable=False)
    texto = Column(Text, nullable=False)
    tokens = Column(Integer, nullable=False, server_default="0")
    tsv = Column(
        TSVECTOR,
        Computed("to_tsvector('portuguese'::regconfig, cabecalho || ' ' || texto)", persisted=True),
    )
    embedding = Column(_Vector(768), nullable=True)
    embedding_model = Column(String(100), nullable=True)
    content_hash = Column(String(64), nullable=False)
    # A3 — só trecho de precedente privado carrega tenant.
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True)

    __table_args__ = (
        UniqueConstraint("fonte_versao_id", "ordem", name="uq_trecho_versao_ordem"),
        Index("ix_trecho_normativo_versao", "fonte_versao_id"),
        # FK sem índice faz cada remoção do lado referido varrer esta tabela inteira.
        Index("ix_trecho_normativo_dispositivo_id", "dispositivo_id"),
        Index("ix_trecho_normativo_tenant_id", "tenant_id"),
        Index("ix_trecho_normativo_tsv", "tsv", postgresql_using="gin"),
    )


class InterpretacaoNorma(Base):
    __tablename__ = "interpretacao_norma"

    id = Column(Integer, primary_key=True)
    interpretacao_fonte_id = Column(
        Integer, ForeignKey("fonte_normativa.id", ondelete="RESTRICT"), nullable=False
    )
    norma_fonte_id = Column(Integer, ForeignKey("fonte_normativa.id", ondelete="RESTRICT"), nullable=False)
    artigo = Column(String(20), nullable=True)   # NULL = a norma como um todo
    citacao_literal = Column(Text, nullable=True)
    origem = Column(String(30), nullable=False)  # extraida_do_texto | curadoria
    status_validacao = Column(String(12), nullable=False, server_default="bruto")

    __table_args__ = (
        UniqueConstraint(
            "interpretacao_fonte_id", "norma_fonte_id", "artigo", name="uq_interpretacao_norma"
        ),
        CheckConstraint(_in("status_validacao", STATUS_VALIDACAO), name="ck_interp_status"),
        Index("ix_interpretacao_norma_alvo", "norma_fonte_id", "artigo"),
        Index("ix_interpretacao_norma_interpretacao_fonte_id", "interpretacao_fonte_id"),
    )


class ValidacaoNorma(Base):
    """A1 — evento append-only; hash chain própria do catálogo global."""

    __tablename__ = "validacao_norma"

    id = Column(Integer, primary_key=True)
    fonte_versao_id = Column(
        Integer, ForeignKey("fonte_normativa_versao.id", ondelete="RESTRICT"), nullable=False
    )
    acao = Column(String(30), nullable=False)        # propor | validar | devolver | bloquear
    status_de = Column(String(12), nullable=False)
    status_para = Column(String(12), nullable=False)
    validador_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    papel_na_curadoria = Column(String(60), nullable=False)
    area = Column(String(20), nullable=False)
    decisao = Column(String(20), nullable=False)     # aprovado | devolvido
    nota = Column(Text, nullable=False)
    hash_texto = Column(String(64), nullable=False)
    evidencias = Column(JSONB, nullable=True)        # URL oficial, vigência declarada, lote
    registrado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    hash_anterior = Column(String(64), nullable=True)
    hash_evento = Column(String(64), nullable=False, unique=True)

    __table_args__ = (
        CheckConstraint(_in("status_de", STATUS_VALIDACAO), name="ck_validacao_de"),
        CheckConstraint(_in("status_para", STATUS_VALIDACAO), name="ck_validacao_para"),
        CheckConstraint("decisao IN ('aprovado','devolvido')", name="ck_validacao_decisao"),
        CheckConstraint("length(trim(nota)) > 0", name="ck_validacao_nota"),
        Index("ix_validacao_norma_versao", "fonte_versao_id"),
        Index("ix_validacao_norma_validador_id", "validador_id"),
    )


class PapelCuradoria(Base):
    """A2 — papel delegável por área (decisão 2 do ADR-075). Não é pessoa."""

    __tablename__ = "papel_curadoria"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    papel = Column(String(60), nullable=False)   # validar_fonte_normativa | curar_corpus
    area = Column(String(20), nullable=False)    # '*' | 'federal' | UF maiúscula
    concedido_por_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    concedido_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    revogado_em = Column(DateTime(timezone=True), nullable=True)
    revogado_por_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    motivo = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "papel IN ('validar_fonte_normativa','curar_corpus')", name="ck_papel_curadoria_papel"
        ),
        Index("ix_papel_curadoria_user", "user_id"),
        Index("ix_papel_curadoria_concedido_por_id", "concedido_por_id"),
        Index("ix_papel_curadoria_revogado_por_id", "revogado_por_id"),
    )


class TarefaRevisaoNormativa(Base):
    __tablename__ = "tarefa_revisao_normativa"

    id = Column(Integer, primary_key=True)
    fonte_versao_id = Column(
        Integer, ForeignKey("fonte_normativa_versao.id", ondelete="RESTRICT"), nullable=True
    )
    legislation_document_id = Column(
        Integer, ForeignKey("legislation_documents.id", ondelete="RESTRICT"), nullable=True
    )
    tipo = Column(String(40), nullable=False)
    detalhe = Column(JSONB, nullable=False)
    aberta_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolvida_em = Column(DateTime(timezone=True), nullable=True)
    resolvida_por_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    resolucao = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('fronteira_ambigua','identidade_nao_determinada','original_divergente',"
            "'original_ausente','conflito_material','nivel_nao_determinado')",
            name="ck_tarefa_revisao_tipo",
        ),
        Index("ix_tarefa_revisao_aberta", "tipo", "resolvida_em"),
        Index("ix_tarefa_revisao_normativa_fonte_versao_id", "fonte_versao_id"),
        Index("ix_tarefa_revisao_normativa_legislation_document_id", "legislation_document_id"),
        Index("ix_tarefa_revisao_normativa_resolvida_por_id", "resolvida_por_id"),
    )
