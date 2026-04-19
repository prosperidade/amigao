"""
Categorias de documento canônicas do Regente Cam2 (CAM2IH-010).

Mapeia as categorias legadas usadas no banco (fundiario, ambiental, pessoal,
geoespacial) para as 6 categorias Regente:
  - fundiarios
  - ambientais
  - fiscais_rurais
  - societarios
  - espaciais
  - relatorios_gerados

Este módulo é namespace puro (sem banco) — usado por APIs/UI para apresentar
uma taxonomia consistente sem migrar dados existentes.
"""

from __future__ import annotations

# Categorias Regente canônicas (6)
REGENTE_CATEGORIES = (
    "fundiarios",
    "ambientais",
    "fiscais_rurais",
    "societarios",
    "espaciais",
    "relatorios_gerados",
)

REGENTE_CATEGORY_LABELS: dict[str, str] = {
    "fundiarios":          "Fundiários",
    "ambientais":          "Ambientais",
    "fiscais_rurais":      "Fiscais/Rurais",
    "societarios":         "Societários",
    "espaciais":           "Espaciais (KML/SIGEF)",
    "relatorios_gerados":  "Relatórios gerados",
}

# Aliases legados → Regente
_LEGACY_TO_REGENTE: dict[str, str] = {
    "fundiario":    "fundiarios",
    "ambiental":    "ambientais",
    "geoespacial":  "espaciais",
    "pessoal":      "societarios",       # RG/CPF de pessoa → societários/pessoais
    "fiscal":       "fiscais_rurais",
    "rural":        "fiscais_rurais",
    "relatorio":    "relatorios_gerados",
    # tipos específicos → categoria
    "matricula":    "fundiarios",
    "ccir":         "fiscais_rurais",     # CCIR é fiscal rural
    "caf":          "fiscais_rurais",
    "car":          "ambientais",
    "doc_pessoal":  "societarios",
    "kml":          "espaciais",
    "sigef":        "espaciais",
    "mapa":         "espaciais",
    "laudo":        "ambientais",
    "contrato_societario": "societarios",
}


def normalize_category(legacy: str | None) -> str | None:
    """Retorna a categoria Regente canônica para um valor legado.

    Se `legacy` já é uma categoria Regente, retorna como está.
    Se é alias conhecido, traduz.
    Se não mapeia, retorna None (UI mostra "outras").
    """
    if not legacy:
        return None
    v = legacy.strip().lower()
    if v in REGENTE_CATEGORIES:
        return v
    return _LEGACY_TO_REGENTE.get(v)


def category_label(category: str | None) -> str:
    """Retorna label legível pt-BR da categoria."""
    if not category:
        return "Sem categoria"
    normalized = normalize_category(category) or category
    return REGENTE_CATEGORY_LABELS.get(normalized, category.replace("_", " ").title())
