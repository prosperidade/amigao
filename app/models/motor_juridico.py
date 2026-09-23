"""Motor jurídico — regra como dado versionado (ADR-073, tabelas do ADR-070 §10).

- `Regra` — identidade estável. A chave de origem inclui matriz e versão da
  planilha: há IDs que colidem entre matrizes (REG-GOV-001/002/003).
- `RegraVersao` — tradução formal de uma regra da planilha: aplicabilidade,
  condição em linguagem restrita, consequência, fundamento. CONTEÚDO imutável
  (gatilho no banco); só o estado de homologação muda, por serviço.
- `ConjuntoRegras` / `ConjuntoRegrasItem` — o que está publicado e ativo. Um ativo
  por escopo (base global ou tenant). Rollback = reativar o anterior.
- `ExecucaoMotor` — uma avaliação de um caso: retrato de fatos + conjunto + data.
- `AvaliacaoRegra` — append-only, uma linha por regra avaliada, com os seis estados.
- `CienciaAlerta` — append-only; alerta crítico exige ciência com justificativa
  (v02 da Ísis: não impede avanço, mas não passa sem registro).
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.sql import func

from app.models.base import Base

ESTADOS_REGRA = ("rascunho", "homologada", "nao_formalizavel")
ESTADOS_CONJUNTO = ("rascunho", "publicado", "ativo", "inativo")
ESTADOS_AVALIACAO = (
    "nao_aplicavel", "aplicavel_disparou", "aplicavel_nao_disparou", "indeterminado",
    "conflito", "erro_execucao",
)


def _in(col: str, valores: tuple[str, ...]) -> str:
    return f"{col} IN ({', '.join(repr(v) for v in valores)})"


class Regra(Base):
    __tablename__ = "regra"

    id = Column(Integer, primary_key=True)
    # "1:v05:REG-BR-CAR-001" — matriz : versão da planilha : ID da Ísis.
    chave_origem = Column(String(120), nullable=False)
    rule_id = Column(String(60), nullable=False)
    matriz = Column(String(20), nullable=False)
    eixo = Column(String(80), nullable=True)
    familia = Column(String(80), nullable=True)
    # ADR-073 §11: camada do tenant só ACRESCENTA regra; NULL = base global.
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("chave_origem", "tenant_id", name="uq_regra_chave_tenant"),
        Index("ix_regra_tenant_id", "tenant_id"),
        # UNIQUE com tenant NULL não barra duplicata na base global.
        Index("uq_regra_chave_base", "chave_origem", unique=True, postgresql_where="tenant_id IS NULL"),
    )


class RegraVersao(Base):
    __tablename__ = "regra_versao"

    id = Column(Integer, primary_key=True)
    regra_id = Column(Integer, ForeignKey("regra.id", ondelete="RESTRICT"), nullable=False)
    versao = Column(Integer, nullable=False)
    estado = Column(String(20), nullable=False, server_default="rascunho")
    motivo_nao_formalizavel = Column(Text, nullable=True)
    descricao = Column(Text, nullable=False)
    mensagem = Column(Text, nullable=True)
    # {"ufs": [...]|null, "esferas": [...]|null, "objetivos": [...]|null}
    aplicabilidade = Column(JSONB, nullable=False)
    # Árvore da linguagem restrita (motor_juridico.linguagem). Nunca código.
    condicao = Column(JSONB, nullable=True)
    # {"tipo": passo_rota|coleta|alerta_critico, "titulo", "descricao", "orgao", "fase", ...}
    consequencia = Column(JSONB, nullable=False)
    # {"fonte": <identidade>, "artigo", "paragrafo", "origem_dispositivo",
    #  "chave_planilha", "dispositivo_planilha"}
    fundamento = Column(JSONB, nullable=True)
    severidade = Column(String(20), nullable=True)
    # Decisão profissional preservada por papel (Q-ISIS-07: não achatar em booleano).
    decisao_profissional = Column(JSONB, nullable=True)
    # {"arquivo", "sha256", "aba", "linha", "versao_planilha", "texto_condicao", "texto_resultado"}
    origem = Column(JSONB, nullable=False)
    hash_conteudo = Column(String(64), nullable=False)
    homologada_por_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    homologada_em = Column(DateTime(timezone=True), nullable=True)
    nota_homologacao = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("regra_id", "versao", name="uq_regra_versao_numero"),
        UniqueConstraint("regra_id", "hash_conteudo", name="uq_regra_versao_hash"),
        CheckConstraint(_in("estado", ESTADOS_REGRA), name="ck_regra_versao_estado"),
        CheckConstraint(
            "estado <> 'nao_formalizavel' OR (motivo_nao_formalizavel IS NOT NULL AND condicao IS NULL)",
            name="ck_regra_versao_nao_formalizavel_tem_motivo",
        ),
        CheckConstraint(
            "estado <> 'homologada' OR (homologada_por_id IS NOT NULL AND homologada_em IS NOT NULL "
            "AND condicao IS NOT NULL)",
            name="ck_regra_versao_homologada_tem_autor",
        ),
        Index("ix_regra_versao_regra_id", "regra_id"),
        Index("ix_regra_versao_homologada_por_id", "homologada_por_id"),
    )


class ConjuntoRegras(Base):
    __tablename__ = "conjunto_regras"

    id = Column(Integer, primary_key=True)
    nome = Column(String(120), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True)
    estado = Column(String(20), nullable=False, server_default="rascunho")
    publicado_por_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    publicado_em = Column(DateTime(timezone=True), nullable=True)
    ativado_em = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint(_in("estado", ESTADOS_CONJUNTO), name="ck_conjunto_regras_estado"),
        CheckConstraint(
            "estado = 'rascunho' OR (publicado_por_id IS NOT NULL AND publicado_em IS NOT NULL)",
            name="ck_conjunto_regras_publicado_tem_autor",
        ),
        # Um conjunto ativo por escopo: base (tenant NULL) ou cada tenant.
        Index("uq_conjunto_regras_ativo_base", "estado", unique=True,
              postgresql_where="estado = 'ativo' AND tenant_id IS NULL"),
        Index("uq_conjunto_regras_ativo_tenant", "tenant_id", unique=True,
              postgresql_where="estado = 'ativo' AND tenant_id IS NOT NULL"),
        Index("ix_conjunto_regras_tenant_id", "tenant_id"),
        Index("ix_conjunto_regras_publicado_por_id", "publicado_por_id"),
    )


class ConjuntoRegrasItem(Base):
    __tablename__ = "conjunto_regras_item"

    id = Column(Integer, primary_key=True)
    conjunto_id = Column(Integer, ForeignKey("conjunto_regras.id", ondelete="RESTRICT"), nullable=False)
    regra_versao_id = Column(Integer, ForeignKey("regra_versao.id", ondelete="RESTRICT"), nullable=False)

    __table_args__ = (
        UniqueConstraint("conjunto_id", "regra_versao_id", name="uq_conjunto_regras_item"),
        Index("ix_conjunto_regras_item_regra_versao_id", "regra_versao_id"),
    )


class ExecucaoMotor(Base):
    __tablename__ = "execucao_motor"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    process_id = Column(Integer, ForeignKey("processes.id", ondelete="RESTRICT"), nullable=False)
    # Base global + camada do tenant (que só acrescenta — ADR-073 §11).
    conjunto_id = Column(Integer, ForeignKey("conjunto_regras.id", ondelete="RESTRICT"), nullable=False)
    conjunto_tenant_id = Column(Integer, ForeignKey("conjunto_regras.id", ondelete="RESTRICT"), nullable=True)
    data_referencia = Column(Date, nullable=False)
    # Retrato dos fatos do caso: {nome: {valor, estado, origem, revisao}}.
    fatos = Column(JSONB, nullable=False)
    fatos_hash = Column(String(64), nullable=False)
    iniciado_por_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_execucao_motor_caso", "tenant_id", "process_id"),
        Index("ix_execucao_motor_process_id", "process_id"),
        Index("ix_execucao_motor_conjunto_id", "conjunto_id"),
        Index("ix_execucao_motor_conjunto_tenant_id", "conjunto_tenant_id"),
        Index("ix_execucao_motor_iniciado_por_id", "iniciado_por_id"),
    )


class AvaliacaoRegra(Base):
    __tablename__ = "avaliacao_regra"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    execucao_id = Column(Integer, ForeignKey("execucao_motor.id", ondelete="RESTRICT"), nullable=False)
    regra_versao_id = Column(Integer, ForeignKey("regra_versao.id", ondelete="RESTRICT"), nullable=False)
    estado = Column(String(30), nullable=False)
    # Fatos que faltaram para decidir (indeterminado) e os que entraram.
    faltantes = Column(ARRAY(String(80)), nullable=True)
    entradas = Column(JSONB, nullable=True)
    consequencia = Column(JSONB, nullable=True)
    # Fundamento resolvido por identidade (ADR-073 §6), ou a razão de não ter resolvido.
    fundamento_fonte_versao_id = Column(
        Integer, ForeignKey("fonte_normativa_versao.id", ondelete="RESTRICT"), nullable=True
    )
    fundamento_dispositivo_id = Column(Integer, ForeignKey("dispositivo.id", ondelete="RESTRICT"), nullable=True)
    fundamento_caminho = Column(String(300), nullable=True)
    fundamento_razao = Column(String(40), nullable=True)
    detalhe_erro = Column(Text, nullable=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("execucao_id", "regra_versao_id", name="uq_avaliacao_regra_execucao"),
        CheckConstraint(_in("estado", ESTADOS_AVALIACAO), name="ck_avaliacao_regra_estado"),
        CheckConstraint(
            "(fundamento_dispositivo_id IS NULL) = (fundamento_fonte_versao_id IS NULL)",
            name="ck_avaliacao_regra_fundamento_par",
        ),
        CheckConstraint(
            "estado <> 'erro_execucao' OR detalhe_erro IS NOT NULL", name="ck_avaliacao_regra_erro_tem_detalhe"
        ),
        Index("ix_avaliacao_regra_execucao", "tenant_id", "execucao_id"),
        Index("ix_avaliacao_regra_execucao_id", "execucao_id"),
        Index("ix_avaliacao_regra_regra_versao_id", "regra_versao_id"),
        Index("ix_avaliacao_regra_fonte_versao_id", "fundamento_fonte_versao_id"),
        Index("ix_avaliacao_regra_dispositivo_id", "fundamento_dispositivo_id"),
    )


class CienciaAlerta(Base):
    __tablename__ = "ciencia_alerta"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)
    avaliacao_id = Column(Integer, ForeignKey("avaliacao_regra.id", ondelete="RESTRICT"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    justificativa = Column(Text, nullable=False)
    registrada_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_ciencia_alerta_tenant_id", "tenant_id"),
        UniqueConstraint("avaliacao_id", name="uq_ciencia_alerta_avaliacao"),
        CheckConstraint("length(trim(justificativa)) > 0", name="ck_ciencia_alerta_justificativa"),
        Index("ix_ciencia_alerta_user_id", "user_id"),
    )
