"""Crawlers de legislacao ambiental — DOU, DOEs estaduais, IBAMA."""

# Importar para registrar via @register_crawler
from app.services.crawlers.dou_crawler import DOUCrawler  # noqa: F401
from app.services.crawlers.doe_crawler import DOECrawler  # noqa: F401
from app.services.crawlers.ibama_crawler import IBAMACrawler  # noqa: F401
