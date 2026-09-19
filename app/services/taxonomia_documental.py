"""Espécie limita suporte; revisão humana não aumenta autoridade documental."""
import unicodedata

from app.schemas.entrada_semantica import EspecieDocumental

FAMILIAS = {
    "certidao_matricula": "registral", "escritura_publica": "registral",
    "contrato_particular": "contratual", "contrato_servico_documental": "contratual",
    "documento_pessoal": "pessoal", "documento_representacao": "pessoal",
    "comprovante_situacao_cadastral_cpf": "cadastral",
    "car": "cadastral", "ccir": "cadastral", "itr": "cadastral", "sigef": "cadastral",
    "rat": "cadastral", "peca_orgao": "cadastral", "arquivo_geoespacial": "geoespacial",
}
SUPORTE = {
    "certidao_matricula": "Atos reproduzidos na certidão, limitados à identidade, cobertura e data do material.",
    "escritura_publica": "Declarações e negócio formalizado; não comprova registro nem titularidade atual.",
    "contrato_particular": "Obrigações e declarações entre partes; não comprova registro nem titularidade atual.",
    "contrato_servico_documental": "Contratação de serviço; não comprova domínio ou regularidade do imóvel.",
    "documento_pessoal": "Identidade da pessoa documentada; não comprova poderes de representação.",
    "comprovante_situacao_cadastral_cpf": "Situação cadastral na data da consulta e falecimento declarado com ano; não sustenta data exata, causa, sucessão ou inventário. Suficiência no gate PENDENTE-ISIS.",
    "documento_representacao": "Poderes expressos, no alcance e intervalo documentados; não comprova domínio.",
    "car": "Declaração cadastral ambiental; não comprova domínio ou regularidade.",
    "ccir": "Informação cadastral rural; não comprova domínio.",
    "itr": "Declaração fiscal; não comprova domínio.",
    "sigef": "Informação de certificação no material; não comprova domínio.",
    "rat": "Análise do órgão no escopo e data expressos; não substitui certidão registral.",
    "peca_orgao": "Conteúdo do ato ou consulta identificados; ausência exige consulta preservada.",
    "arquivo_geoespacial": "Arquivo espacial recebido; medição depende do motor geométrico (ADR-072).",
    "indeterminada": "Espécie não determinada; exige revisão antes de atribuir suporte.",
}


def destino_consolidavel(especie, predicado):
    """A destination cannot grant a document authority its species lacks."""
    return {
        ("car", "car_area_ha"): ("property", "area_grafica_ha"),
        ("certidao_matricula", "area_documental_ha"): ("matricula", "area_ha"),
    }.get((especie, predicado))


def propor_especie(texto, tipo_original=None):
    head = unicodedata.normalize("NFKD", (texto or "")[:2500]).encode("ascii", "ignore").decode().lower()
    if "receita federal" in head and any(marker in head for marker in (
            "titular falecido", "cadastro de pessoas fisicas", "situacao cadastral no cpf")):
        return EspecieDocumental.comprovante_situacao_cadastral_cpf
    markers = [
        ("planta topografica", "arquivo_geoespacial"),
        ("auto de infracao", "peca_orgao"),
        ("escritura publica", "escritura_publica"),
        ("contrato de prestacao de servicos", "contrato_servico_documental"),
        ("contrato de servicos", "contrato_servico_documental"),
        ("contrato particular", "contrato_particular"),
        ("instrumento particular", "contrato_particular"),
        ("termo de inventariante", "documento_representacao"),
        ("termo de compromisso de inventariante", "documento_representacao"),
        ("certidao do inventario", "documento_representacao"),
        ("procuracao", "documento_representacao"),
        ("certidao de inteiro teor", "certidao_matricula"),
        ("certidao eletronica de inteiro teor da matricula", "certidao_matricula"),
        ("certidao de matricula", "certidao_matricula"),
    ]
    for marker, value in markers:
        if marker in head:
            return EspecieDocumental(value)
    aliases = {"rg_cpf": "documento_pessoal", "cpf_cnpj": "documento_pessoal",
        "contrato_servico": "contrato_servico_documental",
        "doc_pessoal": "documento_pessoal", "endereco": "documento_pessoal",
        "geoespacial": "arquivo_geoespacial", "kml_sigef": "arquivo_geoespacial",
        "auto_infracao": "peca_orgao", "certidao_embargo": "peca_orgao"}
    value = aliases.get(tipo_original, tipo_original)
    return EspecieDocumental(value) if value in EspecieDocumental._value2member_map_ else EspecieDocumental.indeterminada
