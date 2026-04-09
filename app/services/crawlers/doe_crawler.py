"""
DOECrawler — Diarios Oficiais Estaduais (27 UFs).

Cada estado tem portal proprio. Este crawler centraliza a logica com
configuracao por UF: URL base, seletores CSS, padrao de busca.

Estrategia: acessar portais de DOE ou APIs de transparencia de cada estado,
buscar por palavras-chave ambientais, filtrar e retornar documentos relevantes.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import httpx

from app.services.crawlers.base_crawler import BaseCrawler, CrawledDocument, register_crawler

logger = logging.getLogger(__name__)


# Configuracao por UF — URL do DOE e orgao ambiental principal
UF_CONFIG: dict[str, dict] = {
    "AC": {"agency": "IMAC",    "doe_name": "Diario Oficial do Acre"},
    "AL": {"agency": "IMA-AL",  "doe_name": "Diario Oficial de Alagoas"},
    "AM": {"agency": "IPAAM",   "doe_name": "Diario Oficial do Amazonas"},
    "AP": {"agency": "SEMA-AP", "doe_name": "Diario Oficial do Amapa"},
    "BA": {"agency": "INEMA",   "doe_name": "Diario Oficial da Bahia"},
    "CE": {"agency": "SEMACE",  "doe_name": "Diario Oficial do Ceara"},
    "DF": {"agency": "IBRAM",   "doe_name": "Diario Oficial do DF"},
    "ES": {"agency": "IEMA",    "doe_name": "Diario Oficial do Espirito Santo"},
    "GO": {"agency": "SEMAD-GO","doe_name": "Diario Oficial de Goias"},
    "MA": {"agency": "SEMA-MA", "doe_name": "Diario Oficial do Maranhao"},
    "MG": {"agency": "SEMAD-MG","doe_name": "Diario Oficial de Minas Gerais"},
    "MS": {"agency": "IMASUL",  "doe_name": "Diario Oficial do Mato Grosso do Sul"},
    "MT": {"agency": "SEMA-MT", "doe_name": "Diario Oficial do Mato Grosso"},
    "PA": {"agency": "SEMAS-PA","doe_name": "Diario Oficial do Para"},
    "PB": {"agency": "SUDEMA",  "doe_name": "Diario Oficial da Paraiba"},
    "PE": {"agency": "CPRH",    "doe_name": "Diario Oficial de Pernambuco"},
    "PI": {"agency": "SEMAR-PI","doe_name": "Diario Oficial do Piaui"},
    "PR": {"agency": "IAT-PR",  "doe_name": "Diario Oficial do Parana"},
    "RJ": {"agency": "INEA",    "doe_name": "Diario Oficial do Rio de Janeiro"},
    "RN": {"agency": "IDEMA",   "doe_name": "Diario Oficial do Rio Grande do Norte"},
    "RO": {"agency": "SEDAM-RO","doe_name": "Diario Oficial de Rondonia"},
    "RR": {"agency": "FEMARH",  "doe_name": "Diario Oficial de Roraima"},
    "RS": {"agency": "FEPAM",   "doe_name": "Diario Oficial do Rio Grande do Sul"},
    "SC": {"agency": "IMA-SC",  "doe_name": "Diario Oficial de Santa Catarina"},
    "SE": {"agency": "ADEMA",   "doe_name": "Diario Oficial de Sergipe"},
    "SP": {"agency": "CETESB",  "doe_name": "Diario Oficial de Sao Paulo"},
    "TO": {"agency": "NATURATINS", "doe_name": "Diario Oficial do Tocantins"},
}

# API agregadora de diarios oficiais (querido diario — projeto aberto)
QUERIDO_DIARIO_API = "https://queridodiario.ok.org.br/api/gazettes"


@register_crawler
class DOECrawler(BaseCrawler):
    """Crawler de Diarios Oficiais Estaduais (27 UFs)."""

    name = "doe"
    description = "Diarios Oficiais Estaduais — publicacoes ambientais de todos os 27 estados"

    def __init__(self, target_date: Optional[date] = None, ufs: Optional[list[str]] = None):
        self.target_date = target_date or (date.today() - timedelta(days=1))
        self.ufs = ufs or list(UF_CONFIG.keys())

    def crawl(self) -> list[CrawledDocument]:
        """Busca publicacoes ambientais nos DOEs de todos os estados configurados."""
        all_docs: list[CrawledDocument] = []

        for uf in self.ufs:
            try:
                docs = self._crawl_uf(uf)
                all_docs.extend(docs)
            except Exception as exc:
                logger.warning("DOE crawler falhou para %s: %s", uf, exc)

        logger.info("DOE crawler: %d documentos totais de %d UFs para %s",
                     len(all_docs), len(self.ufs), self.target_date)
        return all_docs

    def _crawl_uf(self, uf: str) -> list[CrawledDocument]:
        """Crawl DOE de um estado especifico via Querido Diario API."""
        config = UF_CONFIG.get(uf, {})
        agency = config.get("agency", f"SEMA-{uf}")
        docs: list[CrawledDocument] = []

        # Buscar via Querido Diario API (agregador aberto de diarios oficiais)
        terms = ["meio ambiente", "ambiental", "licenciamento", "embargo", agency.lower()]

        for term in terms:
            try:
                response = httpx.get(
                    QUERIDO_DIARIO_API,
                    params={
                        "territory_id": self._get_territory_id(uf),
                        "published_since": self.target_date.isoformat(),
                        "published_until": self.target_date.isoformat(),
                        "querystring": term,
                        "size": 10,
                    },
                    headers={"User-Agent": "Amigao-Meio-Ambiente/1.0"},
                    timeout=30.0,
                )

                if response.status_code != 200:
                    continue

                data = response.json()
                gazettes = data.get("gazettes", [])

                for gazette in gazettes:
                    excerpts = gazette.get("excerpts", [])
                    content = "\n\n".join(excerpts) if excerpts else gazette.get("content", "")

                    if not content or not self.is_relevant(content):
                        continue

                    pub_date = None
                    date_str = gazette.get("date", "")
                    if date_str:
                        try:
                            pub_date = date.fromisoformat(date_str[:10])
                        except ValueError:
                            pub_date = self.target_date

                    docs.append(CrawledDocument(
                        title=f"{config.get('doe_name', f'DOE-{uf}')} — {gazette.get('edition', '')} ({date_str})",
                        identifier=f"DOE-{uf}-{gazette.get('edition', '')}-{date_str}",
                        content=content,
                        source_url=gazette.get("url", f"https://queridodiario.ok.org.br/{uf}"),
                        published_date=pub_date,
                        uf=uf,
                        scope="estadual",
                        agency=agency,
                        source_type="portaria",  # sera refinado pelo conteudo
                        keywords=[term],
                    ))

            except httpx.TimeoutException:
                logger.debug("DOE timeout para %s/%s", uf, term)
            except Exception as exc:
                logger.debug("DOE request falhou %s/%s: %s", uf, term, exc)

        return docs

    def _get_territory_id(self, uf: str) -> str:
        """Retorna territory_id do Querido Diario para a capital do estado."""
        # Codigos IBGE das capitais (usado pelo Querido Diario)
        capitals: dict[str, str] = {
            "AC": "1200401", "AL": "2704302", "AM": "1302603", "AP": "1600303",
            "BA": "2927408", "CE": "2304400", "DF": "5300108", "ES": "3205309",
            "GO": "5208707", "MA": "2111300", "MG": "3106200", "MS": "5002704",
            "MT": "5103403", "PA": "1501402", "PB": "2507507", "PE": "2611606",
            "PI": "2211001", "PR": "4106902", "RJ": "3304557", "RN": "2408102",
            "RO": "1100205", "RR": "1400100", "RS": "4314902", "SC": "4205407",
            "SE": "2800308", "SP": "3550308", "TO": "1721000",
        }
        return capitals.get(uf, "")
