"""Fase 2 robusta (2026-06-06) — validação de FORMATO por campo extraído.

Princípio (item 4b): o valor bruto é SEMPRE preservado (revisão do consultor);
a validação só sinaliza. Valor fora do formato esperado → `confidence` rebaixada
para "low" e flag `format_ok=False` no `field_value`. Nunca descarta nem reescreve.

Motivador real (caso #11): o código SIGEF (`codigo_certificacao`) saiu com um
detalhe de vértice grudado ("029231.2.0006776-55 inicia-se no vértice ...") —
fullmatch do formato falha → rebaixa e marca para revisão, sem perder o bruto.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Optional

# Cada validador recebe o valor JÁ em string normalizada (strip) e devolve True
# se casa o formato esperado por INTEIRO (fullmatch) — assim "código + lixo
# grudado" reprova.
_RE = re.compile


def _fullmatch(pattern: re.Pattern[str]) -> Callable[[str], bool]:
    return lambda s: bool(pattern.fullmatch(s.strip()))


def _is_area_ha(s: str) -> bool:
    """Área plausível: número PT-BR positivo (ex.: '349,9022', '1.010,7113')."""
    from app.services.inconsistency_matrix import _to_float_br  # noqa: PLC0415

    v = _to_float_br(s)
    return v is not None and v > 0


# field_name (staging) → validador de formato. Onde não há entrada, não valida.
_FIELD_VALIDATORS: dict[str, Callable[[str], bool]] = {
    # Código Nacional de Matrícula / certificação SIGEF: 029231.2.0006776-55
    "codigo_certificacao": _fullmatch(_RE(r"\d{6}\.\d\.\d{7}-\d{2}")),
    "numero_geo": _fullmatch(_RE(r"\d{6}\.\d\.\d{7}-\d{2}")),
    # Recibo CAR: GO-5220009-3B9F4F19156B455D9EE371CAEF57623C (UF-IBGE-hash32)
    "numero_car": _fullmatch(_RE(r"[A-Za-z]{2}-\d{7}-[0-9A-Fa-f]{32}")),
    # Código SNCR/INCRA (CCIR/ITR): 13 dígitos em grupos, ex. 111.111.111.111-1
    "codigo_sncr_incra": _fullmatch(_RE(r"\d{3}\.\d{3}\.\d{3}\.\d{3}-\d")),
    "codigo_incra": _fullmatch(_RE(r"\d{3}\.\d{3}\.\d{3}\.\d{3}-\d")),
    # NIRF/CIB: 8 dígitos (com ou sem ponto/hífen)
    "nirf_cib": _fullmatch(_RE(r"\d{1,3}\.?\d{3}\.?\d{3}-?\d?")),
    # CPF / CNPJ
    "cpf": _fullmatch(_RE(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")),
    # Datas dd/mm/aaaa
    "data_nascimento": _fullmatch(_RE(r"\d{2}/\d{2}/\d{4}")),
    "data_emissao": _fullmatch(_RE(r"\d{2}/\d{2}/\d{4}")),
    # Áreas (ha)
    "area_registrada_ha": _is_area_ha,
    "area_declarada_ha": _is_area_ha,
    "area_ha": _is_area_ha,
    "area_georreferenciada_ha": _is_area_ha,
    "area_vetorizada_ha": _is_area_ha,
}


def check_format(field_name: str, value: Any) -> Optional[bool]:
    """True/False se há validador para o campo; None se não há (não valida).

    Só valida valores escalares (str/num). Listas/dicts (pendências, item de
    matrícula) não passam por aqui.
    """
    validator = _FIELD_VALIDATORS.get(field_name)
    if validator is None:
        return None
    if value is None or isinstance(value, (list, dict, bool)):
        return None
    try:
        return validator(str(value))
    except Exception:  # noqa: BLE001 — validador nunca derruba a extração
        return None
