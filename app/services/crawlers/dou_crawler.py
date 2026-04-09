"""
DOUCrawler — Diario Oficial da Uniao (federal).

Fonte: API publica do DOU via IMPRENSA NACIONAL (in.gov.br).
Busca publicacoes ambientais do dia anterior.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import httpx

from app.services.crawlers.base_crawler import BaseCrawler, CrawledDocument, register_crawler

logger = logging.getLogger(__name__)

# API publica do DOU
DOU_API_BASE = "https://www.in.gov.br/lexml/buscar"
DOU_CONTENT_URL = "https://www.in.gov.br/web/dou/-/"

# Termos de busca ambientais
SEARCH_TERMS = [
    "meio ambiente",
    "IBAMA",
    "ICMBio",
    "CONAMA",
    "licenciamento ambiental",
    "codigo florestal",
    "recurso hidrico",
    "outorga",
    "embargo ambiental",
    "fauna silvestre",
    "unidade conservacao",
    "agrotoxicos",
    "barragem",
]


@register_crawler
class DOUCrawler(BaseCrawler):
    """Crawler do Diario Oficial da Uniao (federal)."""

    name = "dou"
    description = "Diario Oficial da Uniao — publicacoes ambientais federais"

    def __init__(self, target_date: Optional[date] = None):
        self.target_date = target_date or (date.today() - timedelta(days=1))

    def crawl(self) -> list[CrawledDocument]:
        """Busca publicacoes ambientais no DOU da data alvo."""
        all_docs: list[CrawledDocument] = []
        seen_urls: set[str] = set()

        for term in SEARCH_TERMS:
            try:
                docs = self._search_term(term)
                for doc in docs:
                    if doc.source_url not in seen_urls:
                        seen_urls.add(doc.source_url)
                        all_docs.append(doc)
            except Exception as exc:
                logger.warning("DOU search falhou para '%s': %s", term, exc)
                continue

        logger.info("DOU crawler: %d documentos unicos para %s", len(all_docs), self.target_date)
        return all_docs

    def _search_term(self, term: str) -> list[CrawledDocument]:
        """Busca um termo especifico no DOU."""
        docs: list[CrawledDocument] = []

        try:
            response = httpx.get(
                DOU_API_BASE,
                params={
                    "q": term,
                    "exactDate": self.target_date.isoformat(),
                    "sortType": "Relevância",
                },
                headers={"User-Agent": "Amigao-Meio-Ambiente/1.0 (monitoramento-legislativo)"},
                timeout=30.0,
                follow_redirects=True,
            )

            if response.status_code != 200:
                logger.debug("DOU retornou %d para '%s'", response.status_code, term)
                return docs

            # Tentar parsear como JSON (API do DOU)
            try:
                data = response.json()
            except Exception:
                # Se nao e JSON, tentar parsear HTML
                return self._parse_html_results(response.text, term)

            items = data if isinstance(data, list) else data.get("items", data.get("results", []))

            for item in items[:10]:  # limitar a 10 por termo
                title = item.get("title", item.get("titulo", ""))
                url = item.get("url", item.get("urlTitle", ""))
                content = item.get("content", item.get("conteudo", ""))
                pub_date_str = item.get("pubDate", item.get("data", ""))

                if not title or not self.is_relevant(f"{title} {content}"):
                    continue

                # Determinar tipo de documento
                source_type = self._classify_source_type(title)

                pub_date = None
                if pub_date_str:
                    try:
                        pub_date = date.fromisoformat(pub_date_str[:10])
                    except ValueError:
                        pub_date = self.target_date

                if url and not url.startswith("http"):
                    url = f"{DOU_CONTENT_URL}{url}"

                docs.append(CrawledDocument(
                    title=title,
                    identifier=self._extract_identifier(title),
                    content=content or title,
                    source_url=url or f"https://www.in.gov.br/dou/{self.target_date}",
                    published_date=pub_date or self.target_date,
                    uf=None,  # federal
                    scope="federal",
                    agency=self._extract_agency(title),
                    source_type=source_type,
                    keywords=[term],
                ))

        except httpx.TimeoutException:
            logger.warning("DOU timeout para '%s'", term)
        except Exception as exc:
            logger.warning("DOU request falhou para '%s': %s", term, exc)

        return docs

    def _parse_html_results(self, html: str, term: str) -> list[CrawledDocument]:
        """Fallback: parsear resultados em HTML."""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            results = soup.select(".resultados-container .resultado")

            docs: list[CrawledDocument] = []
            for result in results[:10]:
                title_el = result.select_one(".titulo")
                content_el = result.select_one(".resumo")
                link_el = result.select_one("a")

                title = title_el.get_text(strip=True) if title_el else ""
                content = content_el.get_text(strip=True) if content_el else ""
                url = link_el.get("href", "") if link_el else ""

                if not title or not self.is_relevant(f"{title} {content}"):
                    continue

                if url and not url.startswith("http"):
                    url = f"https://www.in.gov.br{url}"

                docs.append(CrawledDocument(
                    title=title,
                    identifier=self._extract_identifier(title),
                    content=content or title,
                    source_url=url,
                    published_date=self.target_date,
                    scope="federal",
                    agency=self._extract_agency(title),
                    source_type=self._classify_source_type(title),
                    keywords=[term],
                ))
            return docs
        except ImportError:
            return []

    def _classify_source_type(self, title: str) -> str:
        lower = title.lower()
        if "instrucao normativa" in lower or "in " in lower:
            return "instrucao_normativa"
        if "portaria" in lower:
            return "portaria"
        if "resolucao" in lower:
            return "resolucao"
        if "decreto" in lower:
            return "decreto"
        if "lei " in lower:
            return "lei"
        return "portaria"

    def _extract_agency(self, title: str) -> str:
        lower = title.lower()
        if "ibama" in lower:
            return "IBAMA"
        if "icmbio" in lower:
            return "ICMBio"
        if "conama" in lower:
            return "CONAMA"
        if "mma" in lower or "ministerio do meio ambiente" in lower:
            return "MMA"
        if "ana " in lower or "agencia nacional de aguas" in lower:
            return "ANA"
        return "DOU"

    def _extract_identifier(self, title: str) -> str:
        """Tenta extrair identificador do titulo (ex: 'IN IBAMA 01/2026')."""
        # Simplificado — em producao usaria regex mais robusto
        return title[:80] if title else ""
