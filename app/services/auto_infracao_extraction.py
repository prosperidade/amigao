"""Fase 1 (N2) — Auto de infração como FATO DE PASSIVO no diagnóstico.

Spec da Isis (verbatim, campos fechados — SEM situação processual/CADIN):
número do auto, órgão autuante, autuado (nome+CPF), data da autuação, tipo de
penalidade (multa/advertência), descrição da infração, enquadramento legal
(artigo+norma), coordenadas quando presentes na descrição, valor da multa,
data de vencimento.

Diferente de `ficha01_extraction.py`: os fatos daqui NÃO passam pelo staging
cadastral (`ExtractedFieldStaging`) — não têm hint de matrícula, não são
"campo do imóvel", são evidência de passivo consumida diretamente pelo
DiagnosticoAgent via `Afirmacao`+`SourceRef` (Princípio 11). Persistidos em
`AIJob.result["auto_infracao_fato"]` do job do extrator para o documento —
sem coluna nova (Fase 1 só tem migration para a dívida #48).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from app.core.config import settings
from app.services.inconsistency_matrix import normalize_list_of_dicts

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "Voce e um especialista em fiscalizacao ambiental brasileira. Extraia EXATAMENTE "
    "os campos abaixo de um Auto de Infracao ambiental. Nao invente dado ausente - "
    "use null. Retorne APENAS JSON valido."
)

_PROMPT_TEMPLATE = """Extraia os campos abaixo deste AUTO DE INFRAÇÃO ambiental. Campos de origem
tipica (podem variar por orgao): numero/orgao no cabecalho; autuado no campo 02/03;
data da autuacao no campo 24; descricao da infracao no campo 13 (texto livre);
enquadramento legal (artigo+norma) nos campos 14-16; valor da multa no campo 19;
data de vencimento no campo 25.
{
  "numero_auto": null,
  "orgao_autuante": null,
  "autuado_nome": null,
  "autuado_cpf": null,
  "data_autuacao": null,
  "tipo_penalidade": null,
  "descricao_infracao": null,
  "enquadramento_legal": null,
  "coordenadas": null,
  "valor_multa": null,
  "data_vencimento": null,
  "confidence": {}
}
TEXTO DO DOCUMENTO:
{text}"""


def _parse_json(raw: str) -> Optional[dict[str, Any]]:
    import json

    if not raw:
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("auto_infracao_extraction: JSON invalido do LLM")
        return None


# Par lat/long simples (graus decimais, com ou sem sinal) — item 7: "par
# lat-long se parseável" na descrição livre.
_LATLONG_RE = re.compile(
    r"(-?\d{1,3}[.,]\d+)\s*[,;/]\s*(-?\d{1,3}[.,]\d+)"
)


def parse_coordenadas(texto: Optional[str]) -> Optional[tuple[float, float]]:
    """Extrai um par lat/long do texto livre da descrição, quando parseável."""
    if not texto:
        return None
    m = _LATLONG_RE.search(texto)
    if not m:
        return None
    try:
        lat = float(m.group(1).replace(",", "."))
        lon = float(m.group(2).replace(",", "."))
    except ValueError:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return (lat, lon)


def extract_auto_infracao_fato(text: str) -> Optional[dict[str, Any]]:
    """Roda 1 chamada LLM com o esqueleto do auto de infração (spec da Isis).

    Best-effort: retorna None em qualquer falha (LLM indisponível, parse).
    """
    if not settings.ai_configured or not (text or "").strip():
        return None

    from app.core.ai_gateway import AIGatewayError, complete  # noqa: PLC0415

    prompt = _PROMPT_TEMPLATE.replace("{text}", text[: settings.EXTRACTOR_MAX_CHARS])
    try:
        response = complete(prompt, system=_SYSTEM_PROMPT)
    except AIGatewayError as exc:
        logger.warning("auto_infracao_extraction: LLM falhou: %s", exc.message)
        return None
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("auto_infracao_extraction: erro inesperado: %s", exc)
        return None

    parsed = _parse_json(response.content)
    if not parsed:
        return None

    # Coordenadas: texto livre + par lat/long parseado quando possível (item 7).
    coords_raw = parsed.get("coordenadas")
    parsed["coordenadas_latlong"] = parse_coordenadas(coords_raw) if coords_raw else None
    return parsed


# ---------------------------------------------------------------------------
# Item 8 — enquadramento legal → lookup no knowledge_catalog (mesmo caminho
# do citation_evaluator: extract_citations faz o parse regex).
# ---------------------------------------------------------------------------

def _digitos(valor: Any) -> str:
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


# Um número no texto: dígitos com separador de milhar opcional (ponto, espaço ou
# espaço não-quebrável — o Planalto usa os três). "6.514", "6 514", "12.651".
_RE_NUMERO = re.compile(r"\d[\d.   ]*\d|\d")

# O que vem ANTES de um número e prova que ele é dispositivo, não norma.
# "Art. 18" é o artigo 18; nenhuma lei se identifica por ele.
_RE_DISPOSITIVO = re.compile(
    r"(?:art(?:igo)?s?\.?|§{1,2}|inc(?:iso)?s?\.?|al[íi]neas?|par[áa]grafos?|"
    r"itens?|item|anexos?)\s*[ \s]*$",
    re.I,
)


def _numeros_de_norma(texto: str) -> set[str]:
    """Números presentes no texto que podem identificar uma NORMA.

    Devolve a forma só-dígitos de cada um. Dois cuidados que a versão anterior
    não tinha, e que são a diferença entre conferir identidade e chutar:

    1. **Token, não substring.** Antes, os dígitos de `identifier + title +
       chunk_text` viravam UMA string e a busca era por substring. Para o trecho
       `Decreto 6.514/2008 · "Art. 18. O descumprimento..."` isso dava
       `6514200818`, e então `"65142"` e `"142"` — que não são norma nenhuma ali
       — passavam por atravessar a fronteira entre lei, ano e artigo.

    2. **Dispositivo não é norma.** `"Art. 18"` fazia o guard confirmar uma
       citação à "norma 18". O número do artigo nunca identifica a norma que o
       contém.
    """
    achados: set[str] = set()
    for m in _RE_NUMERO.finditer(texto):
        antes = texto[max(0, m.start() - 24):m.start()]
        if _RE_DISPOSITIVO.search(antes):
            continue
        digitos = _digitos(m.group(0))
        if digitos:
            achados.add(digitos)
    return achados


def chunk_confere_com_a_norma(chunk: Any, numero: str, ano: int) -> bool:
    """O trecho recuperado É, de fato, a norma citada?

    A similaridade vetorial responde "parece com", não "é". Medido em produção
    (caso 15): a citação **"Art. 70 da Lei 9.605/98"** — lei FEDERAL — foi
    "localizada" no chunk 4838, que é o *"MT — Compêndio Regente NUC04: Núcleo de
    Licenciamento Ambiental"*, seção "Art. 70.", jurisdição estadual, UF **MT**.
    Casou pela string "Art. 70." e virou fonte clicável de um passivo federal em
    Goiás. Idem "IN IBAMA nº 14/2009" → chunk 19532, uma resolução de **MS**
    sobre comércio de iscas vivas.

    A conferência é de IDENTIDADE, não de parecença: o número da norma (e o ano,
    quando o corpus o carrega) tem de aparecer em `identifier`, `title` ou no
    próprio texto do trecho. Sem isso, "localizada" é uma afirmação falsa com
    aparência de rigor — a classe de erro mais cara aqui.
    """
    num = _digitos(numero)
    if not num:
        return False
    campos = " ".join(
        str(v or "") for v in (
            getattr(chunk, "identifier", None),
            getattr(chunk, "title", None),
            getattr(chunk, "chunk_text", None),
        )
    )
    # Comparação por TOKEN: o número da norma tem de aparecer inteiro, e não como
    # pedaço de uma sequência maior. Ver `_numeros_de_norma`.
    if num not in _numeros_de_norma(campos):
        return False
    # Ano confirma quando aparece; ausência não reprova (nem todo corpus o traz).
    ano_txt = str(ano)
    if ano_txt in campos or ano_txt[-2:] in campos:
        return True
    return True


# Quantos chunks de uma esfera o corpus precisa ter para que "não localizei"
# signifique "não existe na norma" e não "minha base é rasa aqui". Abaixo disso a
# resposta honesta é declarar a lacuna de COBERTURA (sugestão da Isis, 30/07).
_COBERTURA_MINIMA_CHUNKS = 500


def _cobertura_da_esfera(db_session, esfera: str) -> int:
    """Quantos chunks de legislação o corpus tem para esta esfera."""
    from sqlalchemy import text as sql_text  # noqa: PLC0415

    jurisdicoes = ("federal", "nacional") if esfera == "federal" else (esfera,)
    try:
        return int(
            db_session.execute(
                sql_text(
                    "SELECT count(*) FROM knowledge_catalog "
                    "WHERE source_type = 'legislation' AND jurisdiction = ANY(:j)"
                ),
                {"j": list(jurisdicoes)},
            ).scalar()
            or 0
        )
    except Exception as exc:  # pragma: no cover - defensivo
        logger.warning("auto_infracao_extraction: contagem de cobertura falhou: %s", exc)
        return _COBERTURA_MINIMA_CHUNKS  # na dúvida, não acusa lacuna que não sabe medir


def lookup_enquadramento(
    enquadramento_text: Optional[str],
    *,
    db_session,
    tenant_id: Optional[int] = None,
    esferas: Optional[list[str]] = None,
    orgao: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Para cada citação do enquadramento legal, procura a norma no corpus.

    Devolve, por citação: ``citacao``, ``localizada``, ``chunk_id``,
    ``dispositivo`` (o artigo/seção do trecho — item 9 da validação 30/07),
    ``identificador``/``titulo`` da norma achada e, quando for o caso,
    ``cobertura_insuficiente`` + ``motivo``.

    Três mudanças em relação à versão anterior, todas medidas no caso 15:

    1. **Escopo por esfera.** A busca era global; num corpus com 26.5k chunks
       estaduais contra 785 federais, citação federal afogava em compêndio de
       outro estado. Havendo esfera do caso (ADR-034), a busca é restrita a ela.
    2. **Conferência de identidade.** Similaridade responde "parece com"; agora
       o chunk só conta se carregar o NÚMERO da norma citada.
    3. **Honestidade de cobertura.** Quando a esfera exigida tem base rasa, a
       resposta deixa de ser "não localizada" (que sugere que a norma não
       existe) e passa a declarar que a BASE é insuficiente — com alerta interno
       para nós. Fundamentar com o que se tem, quando o que se tem é de outra
       esfera, produz texto plausível e errado.
    """
    if not (enquadramento_text or "").strip():
        return []

    from app.services.citation_evaluator import extract_citations  # noqa: PLC0415
    from app.services.knowledge_catalog import search  # noqa: PLC0415

    citations = extract_citations(enquadramento_text)
    if not citations:
        return [{"citacao": enquadramento_text.strip(), "localizada": False, "chunk_id": None}]

    jurisdicoes: Optional[list[str]] = None
    if esferas:
        mapa = {"federal": ["federal", "nacional"], "estadual": ["estadual"],
                "municipal": ["municipal"]}
        jurisdicoes = [j for e in esferas for j in mapa.get(e, [])] or None

    # Cobertura medida uma vez por esfera, não por citação.
    cobertura = {e: _cobertura_da_esfera(db_session, e) for e in (esferas or [])}
    esferas_rasas = [e for e, n in cobertura.items() if n < _COBERTURA_MINIMA_CHUNKS]

    results = []
    for cit in citations:
        try:
            hits = search(
                db_session, cit.raw, limit=5, tenant_id=tenant_id,
                source_type="legislation", jurisdiction=jurisdicoes,
                min_similarity=0.55,
            )
        except Exception as exc:  # pragma: no cover - defensivo (RAG indisponível)
            logger.warning("auto_infracao_extraction: lookup enquadramento falhou: %s", exc)
            hits = []

        confere = next(
            (h for h in hits if chunk_confere_com_a_norma(h, cit.numero, cit.ano)), None
        )
        if confere is not None:
            results.append({
                "citacao": cit.raw,
                "localizada": True,
                "chunk_id": confere.id,
                # Item 9 — citar o DISPOSITIVO, não só a norma inteira.
                "dispositivo": (confere.section or None),
                "identificador": confere.identifier,
                "titulo": confere.title,
                "jurisdicao": confere.jurisdiction,
                # Proveniência (#97) — a citação localizada diz de ONDE veio o
                # texto que a sustenta. É o único ponto do fluxo em que o chunk
                # é conhecido; adiante só há o texto livre do modelo.
                "fonte_origem": getattr(confere, "fonte_origem", None),
                "fonte_oficial": bool(getattr(confere, "fonte_oficial", False)),
            })
            continue

        # `cobertura_insuficiente` sai SEMPRE explícito: é um booleano em que o
        # consumidor ramifica, e ausência de chave é pior que `False` — obriga
        # todo leitor a adivinhar se "não veio" é "não" ou "não sei".
        item: dict[str, Any] = {
            "citacao": cit.raw, "localizada": False, "chunk_id": None,
            "cobertura_insuficiente": False,
        }
        if esferas_rasas:
            alvo = orgao or "/".join(esferas_rasas)
            item["cobertura_insuficiente"] = True
            item["motivo"] = (
                f"cobertura normativa insuficiente para {alvo} — base em atualização"
            )
            # Alerta INTERNO: é acionável para nós (ingerir corpus), não é
            # informação para o consultor resolver.
            logger.warning(
                "cobertura_normativa_insuficiente",
                extra={
                    "citacao": cit.raw, "orgao": orgao, "esferas": esferas,
                    "chunks_por_esfera": cobertura,
                },
            )
        else:
            item["motivo"] = "não localizada no corpus"
        results.append(item)
    return results


# ---------------------------------------------------------------------------
# Item 9 — cruzamento autuado × titular atual (nunca bloqueia).
# ---------------------------------------------------------------------------

def _digits(value: Optional[str]) -> str:
    return re.sub(r"\D", "", value or "")


def check_autuado_diverge_titular(
    autuado_nome: Optional[str],
    autuado_cpf: Optional[str],
    *,
    titular_nome: Optional[str] = None,
    titular_cpf: Optional[str] = None,
    matricula_proprietarios: Optional[list[dict[str, Any]]] = None,
) -> Optional[str]:
    """Compara o autuado do auto de infração contra o titular atual (Client
    do processo e/ou proprietários da Matrícula/CAR). Divergência vira NOTA
    informativa — nunca bloqueia (item 9)."""
    if not autuado_cpf and not autuado_nome:
        return None

    candidatos_cpf = {_digits(titular_cpf)} if titular_cpf else set()
    candidatos_nome = {(titular_nome or "").strip().lower()} if titular_nome else set()
    # Defesa em profundidade: a assinatura promete `list[dict]`, mas este é o
    # ponto onde o shape torto DE FATO estourou (caso 15). Uma nota informativa
    # sobre titular não pode derrubar o diagnóstico inteiro — item não-dict é
    # normalizado, não fatal.
    for p in normalize_list_of_dicts(matricula_proprietarios, item_key="nome"):
        if p.get("cpf"):
            candidatos_cpf.add(_digits(p["cpf"]))
        if p.get("nome"):
            candidatos_nome.add(str(p["nome"]).strip().lower())
    candidatos_cpf.discard("")
    candidatos_nome.discard("")

    autuado_cpf_d = _digits(autuado_cpf)
    autuado_nome_l = (autuado_nome or "").strip().lower()

    if autuado_cpf_d and candidatos_cpf:
        if autuado_cpf_d in candidatos_cpf:
            return None
        return (
            f"Autuado do auto de infração ({autuado_nome or autuado_cpf}) difere "
            "do titular atual do imóvel — confirmar se houve transferência "
            "de titularidade após a autuação."
        )
    if autuado_nome_l and candidatos_nome and autuado_nome_l not in candidatos_nome:
        return (
            f"Autuado do auto de infração ({autuado_nome}) difere do titular "
            "atual do imóvel — confirmar se houve transferência de "
            "titularidade após a autuação."
        )
    return None
