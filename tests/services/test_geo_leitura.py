"""Leitura determinística de KMZ/KML — funções puras (ADR-072 §2–§3).

Sem DB, sem LLM. Cada `GeoFalha` é verificada pelo código, não só pelo tipo da
exceção — é o código que a tela e `arquivo_geo.falha_codigo` mostram.
"""
from __future__ import annotations

import io
import zipfile

import pytest

from app.services import geo_leitura as g

KML_HEADER = '<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2">\n'
KML_FOOTER = "\n</kml>"


def _kml(body: str) -> bytes:
    return (KML_HEADER + body + KML_FOOTER).encode("utf-8")


def _kmz(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


RETANGULO = """<Document><Placemark><name>Area 1</name>
<Polygon><outerBoundaryIs><LinearRing><coordinates>
-49.4500,-16.3500,0 -49.4482,-16.3500,0 -49.4482,-16.3482,0 -49.4500,-16.3482,0 -49.4500,-16.3500,0
</coordinates></LinearRing></outerBoundaryIs></Polygon>
</Placemark></Document>"""


class TestLerKml:
    def test_poligono_simples(self):
        feicoes = g.ler_kml(_kml(RETANGULO))
        assert len(feicoes) == 1
        f = feicoes[0]
        assert f.tipo == "poligono"
        assert f.nome == "Area 1"
        assert f.wkt.startswith("POLYGON ((")
        assert f.aneis_internos == 0

    def test_anel_ja_fechado_nao_e_reaberto(self):
        # Coordenadas já terminam iguais ao primeiro ponto — o leitor não duplica.
        feicoes = g.ler_kml(_kml(RETANGULO))
        wkt = feicoes[0].wkt
        pontos = wkt[wkt.index("((") + 2 : wkt.index("))")].split(", ")
        assert pontos[0] == pontos[-1]
        assert feicoes[0].aneis_fechados_pelo_leitor == 0

    def test_anel_aberto_e_fechado_pelo_leitor(self):
        aberto = """<Document><Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>
        0,0,0 1,0,0 1,1,0 0,1,0
        </coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document>"""
        feicoes = g.ler_kml(_kml(aberto))
        assert feicoes[0].aneis_fechados_pelo_leitor == 1
        assert feicoes[0].wkt.count(",") == 4  # 5 pontos (fechado) → 4 vírgulas

    def test_multipoligono_por_multigeometry(self):
        multi = """<Document><Placemark><MultiGeometry>
        <Polygon><outerBoundaryIs><LinearRing><coordinates>0,0 1,0 1,1 0,1 0,0</coordinates></LinearRing></outerBoundaryIs></Polygon>
        <Polygon><outerBoundaryIs><LinearRing><coordinates>10,10 11,10 11,11 10,11 10,10</coordinates></LinearRing></outerBoundaryIs></Polygon>
        </MultiGeometry></Placemark></Document>"""
        feicoes = g.ler_kml(_kml(multi))
        assert len(feicoes) == 1
        assert feicoes[0].tipo == "multipoligono"
        assert feicoes[0].wkt.startswith("MULTIPOLYGON (((")

    def test_poligono_com_vazio_interno(self):
        com_vazio = """<Document><Placemark><Polygon>
        <outerBoundaryIs><LinearRing><coordinates>0,0 10,0 10,10 0,10 0,0</coordinates></LinearRing></outerBoundaryIs>
        <innerBoundaryIs><LinearRing><coordinates>2,2 4,2 4,4 2,4 2,2</coordinates></LinearRing></innerBoundaryIs>
        </Polygon></Placemark></Document>"""
        feicoes = g.ler_kml(_kml(com_vazio))
        assert feicoes[0].aneis_internos == 1
        # POLYGON ((externo...), (vazio...)) — dois anéis dentro de um único POLYGON.
        assert feicoes[0].wkt == (
            "POLYGON ((0.0 0.0, 10.0 0.0, 10.0 10.0, 0.0 10.0, 0.0 0.0), "
            "(2.0 2.0, 4.0 2.0, 4.0 4.0, 2.0 4.0, 2.0 2.0))"
        )

    def test_multiplas_feicoes_em_pastas_tem_identificador_com_caminho(self):
        doc = """<Document><Folder><name>F1</name>
        <Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>0,0 1,0 1,1 0,1 0,0</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
        </Folder>
        <Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>5,5 6,5 6,6 5,6 5,5</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
        </Document>"""
        feicoes = g.ler_kml(_kml(doc))
        assert len(feicoes) == 2
        assert "Folder" in feicoes[0].identificador_interno
        assert feicoes[0].ordem == 1 and feicoes[1].ordem == 2

    def test_ponto_e_linha_nao_sao_unidos_ao_poligono(self):
        doc = """<Document>
        <Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>0,0 1,0 1,1 0,1 0,0</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
        <Placemark><Point><coordinates>5,5,0</coordinates></Point></Placemark>
        <Placemark><LineString><coordinates>0,0 1,1 2,2</coordinates></LineString></Placemark>
        </Document>"""
        feicoes = g.ler_kml(_kml(doc))
        tipos = sorted(f.tipo for f in feicoes)
        assert tipos == ["linha", "poligono", "ponto"]

    def test_sem_placemark_com_geometria_e_falha(self):
        with pytest.raises(g.GeoFalha) as exc:
            g.ler_kml(_kml("<Document><Placemark><name>vazio</name></Placemark></Document>"))
        assert exc.value.codigo == "sem_feicao"

    def test_xml_invalido_e_falha(self):
        with pytest.raises(g.GeoFalha) as exc:
            g.ler_kml(b"isto nao e xml <<<")
        assert exc.value.codigo == "kml_invalido"

    def test_raiz_errada_e_falha(self):
        with pytest.raises(g.GeoFalha) as exc:
            g.ler_kml(b'<?xml version="1.0"?><notkml></notkml>')
        assert exc.value.codigo == "kml_invalido"

    @pytest.mark.parametrize("coords", ["200,10", "10,100", "abc,10", "10"])
    def test_coordenada_invalida(self, coords):
        doc = f"""<Document><Placemark><Polygon><outerBoundaryIs><LinearRing>
        <coordinates>{coords} 1,0 1,1 0,1</coordinates>
        </LinearRing></outerBoundaryIs></Polygon></Placemark></Document>"""
        with pytest.raises(g.GeoFalha) as exc:
            g.ler_kml(_kml(doc))
        assert exc.value.codigo == "coordenada_invalida"

    def test_polygon_sem_outer_boundary_e_falha(self):
        doc = "<Document><Placemark><Polygon></Polygon></Placemark></Document>"
        with pytest.raises(g.GeoFalha) as exc:
            g.ler_kml(_kml(doc))
        assert exc.value.codigo == "coordenada_invalida"

    def test_linha_com_um_ponto_e_falha(self):
        doc = "<Document><Placemark><LineString><coordinates>0,0</coordinates></LineString></Placemark></Document>"
        with pytest.raises(g.GeoFalha) as exc:
            g.ler_kml(_kml(doc))
        assert exc.value.codigo == "coordenada_invalida"

    def test_altitude_e_descartada(self):
        doc = """<Document><Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>
        0,0,850 1,0,900 1,1,850 0,1,800 0,0,850
        </coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark></Document>"""
        feicoes = g.ler_kml(_kml(doc))
        assert "850" not in feicoes[0].wkt and "900" not in feicoes[0].wkt


class TestAbrirKmz:
    def test_doc_kml_na_raiz_e_preferido(self):
        dados = _kmz({"doc.kml": _kml(RETANGULO), "outro.kml": _kml(RETANGULO)})
        leitura = g.ler_arquivo(dados, "kmz")
        assert leitura.membro_lido == "doc.kml"
        assert len(leitura.feicoes) == 1

    def test_kml_unico_sem_doc_kml(self):
        dados = _kmz({"qualquer_nome.kml": _kml(RETANGULO)})
        leitura = g.ler_arquivo(dados, "kmz")
        assert leitura.membro_lido == "qualquer_nome.kml"

    def test_ambiguo_sem_doc_kml_e_falha(self):
        dados = _kmz({"a.kml": _kml(RETANGULO), "b.kml": _kml(RETANGULO)})
        with pytest.raises(g.GeoFalha) as exc:
            g.ler_arquivo(dados, "kmz")
        assert exc.value.codigo == "kml_ambiguo"

    def test_sem_kml_e_falha(self):
        dados = _kmz({"leia.txt": b"nada aqui"})
        with pytest.raises(g.GeoFalha) as exc:
            g.ler_arquivo(dados, "kmz")
        assert exc.value.codigo == "kml_ausente"

    def test_zip_invalido_e_falha(self):
        with pytest.raises(g.GeoFalha) as exc:
            g.ler_arquivo(b"nao sou um zip", "kmz")
        assert exc.value.codigo == "zip_invalido"

    def test_limite_de_membros(self, monkeypatch):
        monkeypatch.setattr(g, "MAX_MEMBROS", 2)
        dados = _kmz({"doc.kml": _kml(RETANGULO), "a.txt": b"x", "b.txt": b"y"})
        with pytest.raises(g.GeoFalha) as exc:
            g.ler_arquivo(dados, "kmz")
        assert exc.value.codigo == "limite_excedido"

    def test_limite_de_descompactado(self, monkeypatch):
        monkeypatch.setattr(g, "MAX_DESCOMPACTADO_BYTES", 10)
        dados = _kmz({"doc.kml": _kml(RETANGULO)})
        with pytest.raises(g.GeoFalha) as exc:
            g.ler_arquivo(dados, "kmz")
        assert exc.value.codigo == "limite_excedido"


class TestLerArquivo:
    def test_formato_nao_suportado(self):
        with pytest.raises(g.GeoFalha) as exc:
            g.ler_arquivo(b"qualquer coisa", "shp")
        assert exc.value.codigo == "formato_nao_suportado"

    def test_arquivo_ausente(self):
        with pytest.raises(g.GeoFalha) as exc:
            g.ler_arquivo(b"", "kmz")
        assert exc.value.codigo == "arquivo_ausente"

    def test_limite_de_tamanho_do_arquivo(self, monkeypatch):
        monkeypatch.setattr(g, "MAX_ARQUIVO_BYTES", 10)
        with pytest.raises(g.GeoFalha) as exc:
            g.ler_arquivo(_kml(RETANGULO), "kml")
        assert exc.value.codigo == "limite_excedido"

    def test_kml_puro_sem_kmz(self):
        leitura = g.ler_arquivo(_kml(RETANGULO), "kml")
        assert leitura.formato == "kml"
        assert leitura.membro_lido is None
        assert len(leitura.feicoes) == 1

    def test_inventario_registra_feicoes(self):
        leitura = g.ler_arquivo(_kmz({"doc.kml": _kml(RETANGULO)}), "kmz")
        assert leitura.inventario["feicoes"][0]["tipo"] == "poligono"
        assert leitura.inventario["membros"][0]["nome"] == "doc.kml"
