"""Identidade pela ocorrência ancorada, independente da ordem da resposta LLM."""
import re
import unicodedata

from app.schemas.evidence import canonical_hash


def localizar_trecho(texto, trecho, inicio=None):
    if inicio is not None:
        if texto[inicio:inicio + len(trecho)] != trecho:
            raise ValueError("Posição não corresponde ao trecho literal")
        return inicio
    pos = texto.find(trecho)
    if pos < 0:
        raise ValueError("Trecho extraído não existe no texto versionado")
    if texto.find(trecho, pos + 1) >= 0:
        raise ValueError("Trecho repetido exige posição explícita; primeira ocorrência não vence")
    return pos


def normalizar_conteudo(value):
    """Only typographic equality; never infer equivalent parties or legal effects."""
    if isinstance(value, str):
        value = re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()
        return re.sub(r"R\$\s*(?=\d)", "R$", value)
    if isinstance(value, list):
        return [normalizar_conteudo(x) for x in value]
    if isinstance(value, dict):
        return {k: normalizar_conteudo(v) for k, v in value.items() if k not in {"trecho", "posicao_inicio"}}
    return value


def identidade_observacao(documento_id, documento_versao, classificacao_versao, tipo, item, inicio, fim):
    # Source positions distinguish genuine repeated assertions. The value is not
    # identity: a corrected reading versions the same observation.
    key = [tipo, item.get("predicado"), item.get("sujeito"), item.get("chave"), item.get("parte_chave"),
           item.get("papel"), item.get("serventia"), item.get("matricula"), item.get("rotulo"), inicio, fim]
    return f"obs:{documento_id}:{documento_versao}:{classificacao_versao}:{canonical_hash(key)[:24]}"
