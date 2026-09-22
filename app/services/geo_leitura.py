"""Leitura determinística de KMZ/KML em feições (ADR-072 §2–§3). Sem banco, sem LLM.

Devolve coordenadas como WKT em lon/lat WGS84 (EPSG:4326, por especificação KML
2.2); validade topológica e área ficam com o PostGIS em ``geometria.py``.
Qualquer problema vira ``GeoFalha`` com código — nunca lista vazia silenciosa.
"""
from __future__ import annotations

import io
import math
import zipfile
from dataclasses import dataclass, field

from lxml import etree

METODO_LEITURA_VERSAO = "072.1"
CRS_KML = "EPSG:4326 (por especificação KML 2.2)"
SRID_KML = 4326

MAX_ARQUIVO_BYTES = 20 * 1024 * 1024
MAX_DESCOMPACTADO_BYTES = 50 * 1024 * 1024
MAX_RAZAO_COMPRESSAO = 100
MAX_MEMBROS = 500

FORMATOS_LIDOS = ("kmz", "kml")


class GeoFalha(Exception):
    def __init__(self, codigo: str, detalhe: str):
        self.codigo = codigo
        self.detalhe = detalhe
        super().__init__(f"{codigo}: {detalhe}")


@dataclass(frozen=True)
class FeicaoLida:
    ordem: int
    identificador_interno: str
    nome: str | None
    tipo: str  # poligono | multipoligono | linha | ponto
    wkt: str
    aneis_internos: int = 0
    aneis_fechados_pelo_leitor: int = 0


@dataclass
class LeituraGeo:
    formato: str
    membro_lido: str | None
    feicoes: list[FeicaoLida]
    inventario: dict = field(default_factory=dict)


def _local(el) -> str:
    return etree.QName(el).localname if isinstance(el.tag, str) else ""


def _filhos(el, nome):
    return [c for c in el if _local(c) == nome]


def _descendentes(el, nome):
    return [c for c in el.iter() if _local(c) == nome]


def _texto(el, nome) -> str | None:
    for c in _filhos(el, nome):
        if c.text and c.text.strip():
            return c.text.strip()
    return None


def _coordenadas(texto: str | None, contexto: str) -> list[tuple[float, float]]:
    if not texto or not texto.strip():
        raise GeoFalha("coordenada_invalida", f"{contexto}: sem coordenadas")
    pontos = []
    for tupla in texto.split():
        partes = tupla.split(",")
        if len(partes) < 2:
            raise GeoFalha("coordenada_invalida", f"{contexto}: tupla sem lon,lat")
        try:
            lon, lat = float(partes[0]), float(partes[1])
        except ValueError:
            raise GeoFalha("coordenada_invalida", f"{contexto}: número inválido") from None
        if not (math.isfinite(lon) and math.isfinite(lat)) or abs(lon) > 180 or abs(lat) > 90:
            raise GeoFalha("coordenada_invalida", f"{contexto}: fora de lon ±180 / lat ±90")
        pontos.append((lon, lat))  # altitude descartada (ADR-072 §3)
    return pontos


def _num(v: float) -> str:
    return repr(float(v))


def _anel(ring, contexto) -> tuple[str, bool]:
    pts = _coordenadas(_texto(ring, "coordinates"), contexto)
    fechado_agora = pts[0] != pts[-1]
    if fechado_agora:
        pts.append(pts[0])
    if len(pts) < 4:
        raise GeoFalha("coordenada_invalida", f"{contexto}: anel com menos de 3 vértices distintos")
    return "(" + ", ".join(f"{_num(x)} {_num(y)}" for x, y in pts) + ")", fechado_agora


def _poligono(el, contexto) -> tuple[str, int, int]:
    """(corpo WKT sem prefixo, anéis internos, anéis fechados pelo leitor)."""
    externos = _filhos(el, "outerBoundaryIs")
    if len(externos) != 1:
        raise GeoFalha("coordenada_invalida", f"{contexto}: polígono sem um único contorno externo")
    aneis, fechados = [], 0
    rings = _filhos(externos[0], "LinearRing")
    if len(rings) != 1:
        raise GeoFalha("coordenada_invalida", f"{contexto}: contorno externo sem um único LinearRing")
    corpo, f = _anel(rings[0], contexto)
    aneis.append(corpo)
    fechados += f
    # KML permite vários LinearRing num innerBoundaryIs; cada um é um vazio.
    for i, interno in enumerate(_filhos(el, "innerBoundaryIs")):
        for j, ring in enumerate(_filhos(interno, "LinearRing")):
            corpo, f = _anel(ring, f"{contexto} vazio {i + 1}.{j + 1}")
            aneis.append(corpo)
            fechados += f
    return "(" + ", ".join(aneis) + ")", len(aneis) - 1, fechados


def _geometrias(el, contexto):
    """Achata MultiGeometry: polígonos juntos (multipolígono), linhas/pontos separados."""
    nome = _local(el)
    if nome == "Polygon":
        return [("Polygon", el, contexto)]
    if nome in ("LineString", "Point"):
        return [(nome, el, contexto)]
    if nome == "MultiGeometry":
        itens = []
        for i, filho in enumerate(c for c in el if isinstance(c.tag, str)):
            itens.extend(_geometrias(filho, f"{contexto}/g{i + 1}"))
        return itens
    return []


def _feicoes_do_placemark(pm, caminho, ordem_inicial) -> list[FeicaoLida]:
    nome = _texto(pm, "name")
    ident = caminho + (f"#id={pm.get('id')}" if pm.get("id") else "")
    geoms = []
    for filho in pm:
        if isinstance(filho.tag, str):
            geoms.extend(_geometrias(filho, ident))
    poligonos = [g for g in geoms if g[0] == "Polygon"]
    outros = [g for g in geoms if g[0] != "Polygon"]
    feicoes, ordem = [], ordem_inicial
    if poligonos:
        partes = [_poligono(el, ctx) for _, el, ctx in poligonos]
        internos = sum(p[1] for p in partes)
        fechados = sum(p[2] for p in partes)
        if len(partes) == 1:
            wkt, tipo = f"POLYGON {partes[0][0]}", "poligono"
        else:
            wkt, tipo = "MULTIPOLYGON (" + ", ".join(p[0] for p in partes) + ")", "multipoligono"
        feicoes.append(FeicaoLida(ordem, ident, nome, tipo, wkt, internos, fechados))
        ordem += 1
    for tipo_kml, el, ctx in outros:
        pts = _coordenadas(_texto(el, "coordinates"), ctx)
        if tipo_kml == "Point":
            wkt, tipo = f"POINT ({_num(pts[0][0])} {_num(pts[0][1])})", "ponto"
        else:
            if len(pts) < 2:
                raise GeoFalha("coordenada_invalida", f"{ctx}: linha com menos de 2 vértices")
            wkt, tipo = "LINESTRING (" + ", ".join(f"{_num(x)} {_num(y)}" for x, y in pts) + ")", "linha"
        feicoes.append(FeicaoLida(ordem, ctx, nome, tipo, wkt))
        ordem += 1
    return feicoes


def ler_kml(dados: bytes) -> list[FeicaoLida]:
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False,
                             remove_comments=True, load_dtd=False)
    try:
        raiz = etree.fromstring(dados, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise GeoFalha("kml_invalido", f"XML ilegível: {exc.msg}") from None
    if _local(raiz) != "kml":
        raise GeoFalha("kml_invalido", f"raiz <{_local(raiz)}> não é <kml>")
    feicoes: list[FeicaoLida] = []
    placemarks = _descendentes(raiz, "Placemark")
    for i, pm in enumerate(placemarks):
        ancestrais = [_local(a) for a in reversed(list(pm.iterancestors())) if _local(a) in ("Document", "Folder")]
        caminho = "/".join(ancestrais + [f"Placemark[{i + 1}]"])
        feicoes.extend(_feicoes_do_placemark(pm, caminho, len(feicoes) + 1))
    if not feicoes:
        raise GeoFalha("sem_feicao", f"{len(placemarks)} Placemark(s), nenhum com geometria")
    return feicoes


def _abrir_kmz(dados: bytes) -> tuple[str, bytes, dict]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(dados))
    except (zipfile.BadZipFile, OSError, ValueError):
        raise GeoFalha("zip_invalido", "KMZ não é um ZIP legível") from None
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        if len(infos) > MAX_MEMBROS:
            raise GeoFalha("limite_excedido", f"{len(infos)} membros (máximo {MAX_MEMBROS})")
        total = sum(i.file_size for i in infos)
        if total > MAX_DESCOMPACTADO_BYTES:
            raise GeoFalha("limite_excedido", f"{total} bytes descompactados (máximo {MAX_DESCOMPACTADO_BYTES})")
        if total > max(len(dados), 1) * MAX_RAZAO_COMPRESSAO:
            raise GeoFalha("limite_excedido", f"razão de compressão acima de {MAX_RAZAO_COMPRESSAO}")
        inventario = {"membros": [{"nome": i.filename, "bytes": i.file_size} for i in infos]}
        kmls = [i for i in infos if i.filename.lower().endswith(".kml")]
        raiz_doc = [i for i in kmls if i.filename.lower() == "doc.kml"]
        if raiz_doc:
            alvo = raiz_doc[0]
        elif len(kmls) == 1:
            alvo = kmls[0]
        elif not kmls:
            raise GeoFalha("kml_ausente", "KMZ sem arquivo .kml")
        else:
            raise GeoFalha("kml_ambiguo", f"{len(kmls)} arquivos .kml e nenhum doc.kml na raiz")
        with zf.open(alvo) as fh:
            conteudo = fh.read(MAX_DESCOMPACTADO_BYTES + 1)
        if len(conteudo) > MAX_DESCOMPACTADO_BYTES:
            raise GeoFalha("limite_excedido", "KML interno acima do limite")
        return alvo.filename, conteudo, inventario


def ler_arquivo(dados: bytes, formato: str) -> LeituraGeo:
    formato = (formato or "").lower()
    if formato not in FORMATOS_LIDOS:
        raise GeoFalha("formato_nao_suportado", f"formato '{formato or '?'}' ainda não é lido (só KMZ e KML)")
    if not dados:
        raise GeoFalha("arquivo_ausente", "arquivo sem bytes")
    if len(dados) > MAX_ARQUIVO_BYTES:
        raise GeoFalha("limite_excedido", f"{len(dados)} bytes (máximo {MAX_ARQUIVO_BYTES})")
    if formato == "kmz":
        membro, kml, inventario = _abrir_kmz(dados)
    else:
        membro, kml, inventario = None, dados, {"membros": []}
    feicoes = ler_kml(kml)
    inventario["feicoes"] = [{"ordem": f.ordem, "tipo": f.tipo, "aneis_fechados_pelo_leitor": f.aneis_fechados_pelo_leitor}
                             for f in feicoes]
    return LeituraGeo(formato=formato, membro_lido=membro, feicoes=feicoes, inventario=inventario)
