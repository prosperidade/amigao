"""Vocabulário da ontologia v1, sem equivalência entre parte, papel e efeito."""
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.evidence import Contract


class EspecieDocumental(StrEnum):
    certidao_matricula = "certidao_matricula"
    escritura_publica = "escritura_publica"
    contrato_particular = "contrato_particular"
    contrato_servico_documental = "contrato_servico_documental"
    documento_pessoal = "documento_pessoal"
    comprovante_situacao_cadastral_cpf = "comprovante_situacao_cadastral_cpf"
    documento_representacao = "documento_representacao"
    car = "car"
    ccir = "ccir"
    itr = "itr"
    sigef = "sigef"
    rat = "rat"
    peca_orgao = "peca_orgao"
    arquivo_geoespacial = "arquivo_geoespacial"
    indeterminada = "indeterminada"


class PapelParticipacao(StrEnum):
    adquirente = "adquirente"
    transmitente = "transmitente"
    titular_direito = "titular_direito"
    representante = "representante"
    inventariante = "inventariante"
    herdeiro = "herdeiro"
    meeiro = "meeiro"
    credor = "credor"
    devedor = "devedor"
    confrontante = "confrontante"
    declarante = "declarante"
    indeterminado = "indeterminado"


class ParteExtraida(Contract):
    chave: str = Field(min_length=1)
    nome: str = Field(min_length=1)
    natureza: Literal["pf", "pj", "indeterminada", "espolio"]
    identificador: str | None = None
    tipo_identificador: Literal["cpf", "cnpj", "oab"] | None = None
    falecido_chave: str | None = None
    inventario: str | None = None
    trecho: str = Field(min_length=1)
    posicao_inicio: int | None = Field(default=None, ge=0, description="Offset global start no extracted_text, caracteres Unicode, base zero")
    posicao_fim: int | None = Field(default=None, ge=0, description="Offset global end exclusivo no extracted_text")

    @model_validator(mode="after")
    def identidade(self):
        if self.natureza == "espolio" and (not self.falecido_chave or self.identificador):
            raise ValueError("Espólio exige falecido e não recebe CPF/CNPJ próprio")
        if self.natureza == "pj" and self.tipo_identificador in {"cpf", "oab"}:
            raise ValueError("Identificador pessoal de representante não identifica PJ")
        if self.natureza == "pf" and self.tipo_identificador == "cnpj":
            raise ValueError("CNPJ não identifica pessoa física")
        if bool(self.identificador) != bool(self.tipo_identificador):
            raise ValueError("Identificador exige tipo e valor juntos")
        return self


class ParticipacaoExtraida(Contract):
    parte_chave: str
    papel: PapelParticipacao
    ato_rotulo: str | None = None
    representado_chave: str | None = None
    alcance: str | None = None
    inicio: date | None = None
    fim: date | None = None
    fracao: Decimal | None = Field(default=None, gt=0, le=1)
    trecho: str = Field(min_length=1)
    posicao_inicio: int | None = Field(default=None, ge=0, description="Offset global start no extracted_text, caracteres Unicode, base zero")
    posicao_fim: int | None = Field(default=None, ge=0, description="Offset global end exclusivo no extracted_text")
    estado_confirmacao: Literal["declarado", "confirmado"] = "declarado"


class AtoExtraido(Contract):
    rotulo: str | None = None
    matricula: str | None = None
    serventia: str | None = None
    cns: str | None = None
    especie: Literal["registro", "averbacao", "outra"]
    natureza: str = Field(min_length=1)
    data_ato: date | None = None
    ordem: int = Field(ge=0)
    trecho: str = Field(min_length=1)
    posicao_inicio: int | None = Field(default=None, ge=0, description="Offset global start no extracted_text, caracteres Unicode, base zero")
    posicao_fim: int | None = Field(default=None, ge=0, description="Offset global end exclusivo no extracted_text")
    altera_rotulo: str | None = None
    relacao: Literal["baixa", "aditivo", "retificacao", "cancelamento"] | None = None


class ObservacaoExtraida(Contract):
    predicado: str = Field(min_length=1)
    valor: str | int | float | list | dict | None
    unidade: str | None = None
    trecho: str = Field(min_length=1)
    posicao_inicio: int | None = Field(default=None, ge=0, description="Offset global start no extracted_text, caracteres Unicode, base zero")
    posicao_fim: int | None = Field(default=None, ge=0, description="Offset global end exclusivo no extracted_text")
    sujeito: str | None = None
    ato_rotulo: str | None = None


class ContratoExtraido(Contract):
    """Proposta documental, inclusive quando não há destino no cadastro."""
    contratante: list[str] = Field(default_factory=list, description="Chaves das partes contratantes")
    contratado: list[str] = Field(default_factory=list, description="Chaves das partes contratadas")
    objeto: str | None = None
    representacao_declarada: list[ParticipacaoExtraida] = Field(default_factory=list)
    referencia_processo_judicial: list[str] = Field(default_factory=list)
    trecho: str = Field(min_length=1)
    posicao_inicio: int | None = Field(default=None, ge=0, description="Offset global start no extracted_text, caracteres Unicode, base zero")
    posicao_fim: int | None = Field(default=None, ge=0, description="Offset global end exclusivo no extracted_text")

    @model_validator(mode="after")
    def representacoes(self):
        if any(p.papel not in {"representante", "inventariante"} for p in self.representacao_declarada):
            raise ValueError("Representação contratual exige papel representante ou inventariante")
        return self


class FalecimentoDeclarado(Contract):
    """Adendo proposto da Ontologia v1; suficiência documental PENDENTE-ISIS."""
    predicado: Literal["falecimento_declarado"] = "falecimento_declarado"
    sujeito: str = Field(min_length=1, description="Chave da pessoa em partes[]")
    ano: int | None = Field(default=None, ge=1800, le=9999)
    data: date | None = None
    fonte: Literal["receita_federal"] = "receita_federal"
    data_consulta: date | None = None
    trecho: str = Field(min_length=1)
    posicao_inicio: int | None = Field(default=None, ge=0, description="Offset global start no extracted_text, caracteres Unicode, base zero")
    posicao_fim: int | None = Field(default=None, ge=0, description="Offset global end exclusivo no extracted_text")

    @model_validator(mode="after")
    def limite_da_fonte(self):
        if self.data is not None:
            raise ValueError("Comprovante da Receita não sustenta data exata de falecimento; preserve somente o ano informado")
        return self


class EntradaExtraida(Contract):
    partes: list[ParteExtraida] = Field(default_factory=list)
    participacoes: list[ParticipacaoExtraida] = Field(default_factory=list)
    atos: list[AtoExtraido] = Field(default_factory=list)
    observacoes: list[ObservacaoExtraida] = Field(default_factory=list)
    limites: list[str] = Field(default_factory=list)
    contratos: list[ContratoExtraido] = Field(default_factory=list)
    falecimentos_declarados: list[FalecimentoDeclarado] = Field(default_factory=list)

    @property
    def todas_participacoes(self):
        return [*self.participacoes, *(p for c in self.contratos for p in c.representacao_declarada)]

    @model_validator(mode="after")
    def referencias_partes(self):
        partes = {p.chave: p for p in self.partes}
        if len(partes) != len(self.partes):
            raise ValueError("Chave de parte duplicada no documento")
        for declaracao in self.falecimentos_declarados:
            if declaracao.sujeito not in partes or partes[declaracao.sujeito].natureza != "pf":
                raise ValueError("Falecimento declarado exige sujeito pessoa física, não espólio")
        for contrato in self.contratos:
            for chave in [*contrato.contratante, *contrato.contratado]:
                if chave not in partes:
                    raise ValueError("Parte contratual sem identidade extraída")
        for parte in self.partes:
            if parte.natureza == "espolio" and (
                    parte.falecido_chave not in partes or partes[parte.falecido_chave].natureza != "pf"):
                raise ValueError("Espólio exige referência à pessoa física falecida")
        for participacao in self.todas_participacoes:
            if participacao.parte_chave not in partes:
                raise ValueError("Participação sem parte extraída")
            if participacao.representado_chave and participacao.representado_chave not in partes:
                raise ValueError("Representado sem parte extraída")
        if any(o.predicado == "falecimento_declarado" for o in self.observacoes):
            raise ValueError("Use falecimentos_declarados para respeitar o schema e os limites da fonte")
        return self
