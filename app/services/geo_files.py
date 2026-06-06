"""
geo_files — detecção de arquivos GEOESPACIAIS (geometria, não documento).

Contexto (fix/intake-geo-routing, 2026-06-05): no intake, o upload de um `.kml`
caía no pipeline de OCR de PDF (`ocr_then_extract`) e estourava uma cascata de
erros técnicos na cara do consultor — pypdf devolvia 0 chars, o Gemini recusava
com ``400 Unsupported MIME type: application/octet-stream`` e o fallback de
rasterização falhava. KML/KMZ/SHP/GeoJSON/GPX são **geometria**: descrevem
polígonos do imóvel, não texto a ser transcrito. O pipeline de OCR nunca deveria
recebê-los.

Este módulo só **detecta e roteia**. O consumo real desses arquivos (parser →
``Property.geom`` → PostGIS) é o gap **D1** (próxima frente geo) e NÃO é feito
aqui. Por enquanto o arquivo é aceito, fica no storage vinculado ao
processo/imóvel, e a UI comunica honestamente "armazenado — processamento de
geometria em breve".
"""

from __future__ import annotations

import io
import logging
import zipfile
from typing import Optional

logger = logging.getLogger(__name__)

# document_type canônico aplicado a um arquivo geoespacial roteado para fora do
# OCR. Mapeia para a categoria "espaciais" via document_categories.normalize_category.
GEOSPATIAL_DOCUMENT_TYPE = "geoespacial"

# Mensagem honesta exibida ao consultor enquanto o consumo geoespacial (D1) não
# existe. Sem stack técnico — o arquivo está salvo, só não há leitura de texto.
GEOSPATIAL_STORED_MESSAGE = "Armazenado — processamento de geometria em breve."

# Extensões que SEMPRE são geometria (vetor geoespacial), nunca documento de texto.
# .zip fica fora desta lista de propósito: um .zip pode ser shapefile OU qualquer
# outra coisa; só dá pra saber inspecionando o conteúdo (zip_contains_shapefile).
GEOSPATIAL_EXTENSIONS: frozenset[str] = frozenset({
    "kml", "kmz", "shp", "shx", "dbf", "prj", "geojson", "gpx",
})

# Membros típicos de um shapefile dentro de um .zip. A presença de um `.shp`
# (com seus companheiros .shx/.dbf) caracteriza o pacote como geoespacial.
_SHAPEFILE_MEMBER_EXTS: frozenset[str] = frozenset({"shp", "shx", "dbf", "prj"})

# MIME types geoespaciais conhecidos. Na prática o navegador costuma mandar
# ``application/octet-stream`` para esses arquivos (daí a detecção por extensão
# ser a fonte primária), mas alguns clientes mandam o MIME correto.
GEOSPATIAL_MIME_TYPES: frozenset[str] = frozenset({
    "application/vnd.google-earth.kml+xml",
    "application/vnd.google-earth.kmz",
    "application/geo+json",
    "application/gpx+xml",
    "application/x-shapefile",
    "application/x-esri-shape",
    "application/octet-stream+shapefile",
})


def extension_of(filename: Optional[str]) -> str:
    """Extensão normalizada (minúscula, sem ponto). '' quando não há extensão."""
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower().strip()


def is_geospatial(filename: Optional[str], mime_type: Optional[str] = None) -> bool:
    """True se o arquivo é geometria geoespacial pela extensão OU pelo MIME.

    Não inspeciona bytes — `.zip` contendo shapefile é detectado por
    ``zip_contains_shapefile`` (precisa do conteúdo, disponível só no worker).
    """
    ext = extension_of(filename)
    if ext in GEOSPATIAL_EXTENSIONS:
        return True
    return bool(mime_type and mime_type.strip().lower() in GEOSPATIAL_MIME_TYPES)


def zip_contains_shapefile(data: bytes) -> bool:
    """True se o .zip contém um shapefile (membro .shp), inspecionando os nomes.

    Defensivo: bytes que não são um zip válido → False (não é geoespacial por
    esta via). Nunca levanta — falha de leitura vira "não é shapefile".
    """
    if not data:
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            members = zf.namelist()
    except (zipfile.BadZipFile, OSError, ValueError) as exc:
        logger.debug("geo_files.zip_contains_shapefile: zip inválido: %s", exc)
        return False
    return any(extension_of(name) in _SHAPEFILE_MEMBER_EXTS for name in members)
