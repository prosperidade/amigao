"""
IBAMACrawler — Normativas do IBAMA (instrucoes normativas, portarias, resolucoes).

Fonte: ibama.gov.br/legislacao
Frequencia: semanal.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import httpx

from app.services.crawlers.base_crawler import BaseCrawler, CrawledDocument, register_crawler

logger = logging.getLogger(__name__)

IBAMA_LEGISLATION_URL = "https://www.ibama.gov.br/legislacao"
IBAMA_SEARCH_URL = "https://www.ibama.gov.br/component/finder/"


@register_crawler
class IBAMACrawler(BaseCrawler):
    """Crawler de normativas do IBAMA."""

    name = "ibama"
    description = "IBAMA — instrucoes normativas, portarias e resolucoes"

    def __init__(self, days_back: int = 7):
        self.since_date = date.today() - timedelta(days=days_back)

    def crawl(self) -> list[CrawledDocument]:
        """Busca normativas recentes do IBAMA."""
        docs: list[CrawledDocument] = []

        search_terms = [
            "instrucao normativa",
            "portaria",
            "resolucao",
            "nota tecnica",
        ]

        for term in search_terms:
            try:
                found = self._search(term)
                docs.extend(found)
            except Exception as exc:
                logger.warning("IBAMA search falhou para '%s': %s", term, exc)

        # Deduplicar por URL
        seen: set[str] = set()
        unique: list[CrawledDocument] = []
        for doc in docs:
            if doc.source_url not in seen:
                seen.add(doc.source_url)
                unique.append(doc)

        logger.info("IBAMA crawler: %d normativas encontradas desde %s", len(unique), self.since_date)
        return unique

    def _search(self, term: str) -> list[CrawledDocument]:
        """Busca um tipo de normativa no site do IBAMA."""
        docs: list[CrawledDocument] = []

        try:
            response = httpx.get(
                IBAMA_LEGISLATION_URL,
                params={"q": term},
                headers={"User-Agent": "Amigao-Meio-Ambiente/1.0 (monitoramento-legislativo)"},
                timeout=30.0,
                follow_redirects=True,
            )

            if response.status_code != 200:
                return docs

            return self._parse_html(response.text, term)

        except httpx.TimeoutException:
            logger.warning("IBAMA timeout para '%s'", term)
        except Exception as exc:
            logger.warning("IBAMA request falhou: %s", exc)

        return docs

    def _parse_html(self, html: str, term: str) -> list[CrawledDocument]:
        """Parseia resultados HTML do IBAMA."""
        docs: list[CrawledDocument] = []

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")

            # Buscar links de normativas (seletores podem variar)
            for link in soup.select("a[href*='legislacao'], a[href*='normativa'], a[href*='portaria']"):
                title = link.get_text(strip=True)
                href = link.get("href", "")

                if not title or len(title) < 10:
                    continue

                if not self.is_relevant(title):
                    continue

                if href and not href.startswith("http"):
                    href = f"https://www.ibama.gov.br{href}"

                # Tentar obter conteudo da pagina
                content = title  # fallback
                try:
                    page = httpx.get(
                        href,
                        headers={"User-Agent": "Amigao-Meio-Ambiente/1.0"},
                        timeout=15.0,
                        follow_redirects=True,
                    )
                    if page.status_code == 200:
                        page_soup = BeautifulSoup(page.text, "lxml")
                        article = page_soup.select_one("article, .item-page, .content, main")
                        if article:
                            content = article.get_text(separator="\n", strip=True)
                except Exception:
                    pass  # usar titulo como content

                source_type = "instrucao_normativa" if "instrucao" in title.lower() else (
                    "portaria" if "portaria" in title.lower() else (
                        "resolucao" if "resolucao" in title.lower() else "nota_tecnica"
                    )
                )

                docs.append(CrawledDocument(
                    title=title[:200],
                    identifier=title[:100],
                    content=content,
                    source_url=href,
                    published_date=None,  # dificil extrair do HTML generico
                    uf=None,
                    scope="federal",
                    agency="IBAMA",
                    source_type=source_type,
                    keywords=[term],
                ))

        except ImportError:
            logger.warning("beautifulsoup4 nao instalado — IBAMA crawler desabilitado")

        return docs[:10]  # limitar por busca
