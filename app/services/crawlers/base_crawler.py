"""
BaseCrawler — ABC para crawlers de legislacao ambiental.

Cada crawler concreto implementa `crawl()` e retorna lista de `CrawledDocument`.
"""

from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CrawledDocument:
    """Documento legislativo encontrado por um crawler."""
    title: str
    identifier: str  # "IN IBAMA 01/2026", "Lei 12.651/2012"
    content: str  # texto completo
    source_url: str
    published_date: Optional[date] = None
    uf: Optional[str] = None  # None = federal
    scope: str = "federal"  # federal/estadual/municipal
    agency: str = ""  # IBAMA, SEMA-MT, etc.
    source_type: str = "lei"  # lei/decreto/resolucao/instrucao_normativa/portaria
    keywords: list[str] = field(default_factory=list)
    demand_types: list[str] = field(default_factory=list)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()


class BaseCrawler(ABC):
    """Base para crawlers de fontes legislativas."""

    name: str = "base"
    description: str = ""

    # Palavras-chave ambientais para filtrar conteudo relevante
    ENVIRONMENTAL_KEYWORDS = [
        "meio ambiente", "ambiental", "florestal", "codigo florestal",
        "licenciamento", "licenca ambiental", "car ", "sicar",
        "ibama", "icmbio", "conama", "sema", "iema", "ief",
        "recurso hidrico", "outorga", "embargo", "desmatamento",
        "app ", "reserva legal", "area protegida", "unidade de conservacao",
        "fauna", "flora", "prad", "compensacao ambiental",
        "agrotoxic", "residuo", "saneamento", "poluicao",
        "mineracao", "barragem", "seguranca de barragens",
    ]

    def is_relevant(self, text: str) -> bool:
        """Verifica se o texto contem palavras-chave ambientais."""
        lower = text.lower()
        return any(kw in lower for kw in self.ENVIRONMENTAL_KEYWORDS)

    @abstractmethod
    def crawl(self) -> list[CrawledDocument]:
        """Executa o crawling e retorna documentos encontrados."""
        ...

    def safe_crawl(self) -> list[CrawledDocument]:
        """Wrapper com tratamento de erro para crawl()."""
        try:
            docs = self.crawl()
            logger.info("crawler '%s': %d documentos encontrados", self.name, len(docs))
            return docs
        except Exception as exc:
            logger.exception("crawler '%s' falhou: %s", self.name, exc)
            return []


# Registry de crawlers
_CRAWLER_REGISTRY: dict[str, type[BaseCrawler]] = {}


def register_crawler(cls: type[BaseCrawler]) -> type[BaseCrawler]:
    """Decorator para registrar um crawler."""
    _CRAWLER_REGISTRY[cls.name] = cls
    return cls


def get_crawler(name: str) -> BaseCrawler:
    """Instancia um crawler pelo nome."""
    cls = _CRAWLER_REGISTRY.get(name)
    if not cls:
        raise ValueError(f"Crawler '{name}' nao registrado. Disponiveis: {list(_CRAWLER_REGISTRY.keys())}")
    return cls()


def list_crawlers() -> list[str]:
    """Lista nomes de crawlers registrados."""
    return list(_CRAWLER_REGISTRY.keys())
