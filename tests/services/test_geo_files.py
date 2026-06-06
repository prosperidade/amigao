"""Testes do detector de arquivos geoespaciais (fix/intake-geo-routing).

Cobre o roteamento que mantém KML/KMZ/SHP/GeoJSON/GPX (geometria) fora do
pipeline de OCR de PDF — a causa do upload de .kml estourar
"Unsupported MIME type: application/octet-stream" em produção.
"""

import io
import zipfile

import pytest

from app.services.geo_files import (
    GEOSPATIAL_DOCUMENT_TYPE,
    extension_of,
    is_geospatial,
    zip_contains_shapefile,
)


@pytest.mark.parametrize(
    "filename",
    [
        "imovel.kml",
        "IMOVEL.KML",
        "area.kmz",
        "talhao.shp",
        "talhao.shx",
        "talhao.dbf",
        "talhao.prj",
        "poligono.geojson",
        "trilha.gpx",
        "caminho/com/pasta/fazenda.kml",
    ],
)
def test_is_geospatial_por_extensao(filename):
    # MIME que o navegador costuma mandar para esses arquivos.
    assert is_geospatial(filename, "application/octet-stream") is True


@pytest.mark.parametrize(
    "filename",
    ["matricula.pdf", "car.PDF", "foto.jpg", "planilha.xlsx", "doc.docx", "semponto", ""],
)
def test_nao_geospatial(filename):
    assert is_geospatial(filename, "application/pdf") is False


def test_is_geospatial_por_mime_mesmo_sem_extensao_conhecida():
    assert is_geospatial("arquivo.bin", "application/vnd.google-earth.kml+xml") is True


def test_extension_of():
    assert extension_of("a.KML") == "kml"
    assert extension_of("sem_extensao") == ""
    assert extension_of(None) == ""
    assert extension_of("a.b.geojson") == "geojson"


def test_document_type_canonico():
    assert GEOSPATIAL_DOCUMENT_TYPE == "geoespacial"


def _make_zip(names: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for n in names:
            zf.writestr(n, b"x")
    return buf.getvalue()


def test_zip_com_shapefile():
    data = _make_zip(["talhao.shp", "talhao.shx", "talhao.dbf", "talhao.prj"])
    assert zip_contains_shapefile(data) is True


def test_zip_sem_shapefile():
    data = _make_zip(["relatorio.pdf", "leiame.txt"])
    assert zip_contains_shapefile(data) is False


def test_zip_invalido_nao_explode():
    assert zip_contains_shapefile(b"isto nao e um zip") is False
    assert zip_contains_shapefile(b"") is False
