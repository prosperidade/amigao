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
        return {k: normalizar_conteudo(v) for k, v in value.items() if k not in {"trecho", "posicao_inicio", "posicao_fim"}}
    return value


def resolver_ancora_literal(texto, trecho, inicio=None, fim=None):
    """Recover only whitespace layout; persist the exact original source span.

    No case, punctuation, number or word correction. Repeated occurrences still
    require an explicit position. The raw LLM response remains in the job audit.
    """
    if fim is not None:
        if inicio is None or not 0 <= inicio < fim <= len(texto):
            raise ValueError("Intervalo de ancora invalido")
        literal = texto[inicio:fim]
        if literal != trecho and re.sub(r"\s+", " ", literal).strip() != re.sub(r"\s+", " ", trecho).strip():
            raise ValueError("Offsets nao correspondem ao trecho literal")
        return literal, inicio
    if trecho in texto:
        pos = localizar_trecho(texto, trecho, inicio)
        return trecho, pos
    tokens = trecho.split()
    if not tokens:
        raise ValueError("Trecho sem conteúdo literal")
    pattern = re.compile(r"\s+".join(re.escape(token) for token in tokens))
    match = pattern.match(texto, inicio) if inicio is not None else pattern.search(texto)
    if match is None:
        raise ValueError("Trecho extraído não existe no texto versionado")
    if inicio is None and pattern.search(texto, match.start() + 1) is not None:
        raise ValueError("Trecho repetido exige posição explícita; primeira ocorrência não vence")
    return texto[match.start():match.end()], match.start()


def identidade_observacao(documento_id, documento_versao, classificacao_versao, tipo, item, inicio, fim):
    # Source positions distinguish genuine repeated assertions. The value is not
    # identity: a corrected reading versions the same observation.
    key = [tipo, item.get("predicado"), item.get("sujeito"), item.get("chave"), item.get("parte_chave"),
           item.get("papel"), item.get("serventia"), item.get("matricula"), item.get("rotulo"), inicio, fim]
    return f"obs:{documento_id}:{documento_versao}:{classificacao_versao}:{canonical_hash(key)[:24]}"
