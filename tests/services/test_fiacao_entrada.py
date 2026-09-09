"""Fiação da entrada — o dado que chegava e não pousava.

Os quatro casos vêm da Entrega 2 da confirmação de 09/09
(`docs/auditoria/CONFIRMACAO_ENTRADA_2026-09-09.md`), linha "INSUFICIENTE —
material existe, ligação falta". Valores literais medidos nos documentos da
ELODI (docs 546 e 549), não exemplos inventados.
"""

from __future__ import annotations

from app.services.ficha01_extraction import build_staging_fields
from app.services.field_validators import check_format

# Trecho VERBATIM do doc 546 (recibo do CAR) — as duas áreas no mesmo parágrafo,
# e os módulos fiscais que estavam no texto e ninguém pedia.
TEXTO_546 = (
    "Módulos Fiscais: 31,1547 Código do Produtor. "
    "Foi detectada uma diferença entre a área do imóvel rural declarada conforme "
    "documentação comprobatória de propriedade/posse/concessão [2180.3923 hectares] "
    "e a área do imóvel rural identificada em representação gráfica "
    "[2.180,8267 hectares]."
)

# Trecho VERBATIM do doc 549 (matrícula 3.673) — R-13/R.15 e a AV.02 da RL.
TEXTO_549 = (
    "R-13 MAT. 3.673 - ADQUIRENTE: Nascente Agro-industrial Ltda, CNPJ "
    "25.078.411/0001-20, ALEXANDRE AUGUSTO CLEMENTE, CPF 251.076.678-30, e "
    "KARINA SANTAROSA CLEMENTE, CPF 270.654.448-13. "
    "R.15 MAT. 3.673 - ELODI AGROPECUÁRIA, CNPJ 29.091.958/0001-17. "
    "AV.02 MAT. 3.673 -(Averbação referente a Av.09 Mat. 2007 e Av. 04 Mat. 3.669)- "
    "Procede-se a averbação da Reserva Legal desta Matricula em conjunto com as "
    "Matriculas nº 1.224 e 1.225, com a área total de 492,9252ha, não inferior a "
    "20% do total da propriedade."
)


class TestProprietariosPousam:
    """O JSON trazia os quatro titulares; faltava a entrada em `_FIELD_SPECS`."""

    JSON_549 = {
        "proprietarios": [
            {"nome": "Nascente Agro-industrial Ltda", "cpf": "25.078.411/0001-20"},
            {"nome": "ALEXANDRE AUGUSTO CLEMENTE", "cpf": "251.076.678-30"},
            {"nome": "KARINA SANTAROSA CLEMENTE", "cpf": "270.654.448-13"},
            {"nome": "ELODI AGROPECUÁRIA", "cpf": "29.091.958/0001-17"},
        ],
        "confidence": {"proprietarios": "high"},
    }

    def _linha(self):
        rows = build_staging_fields("matricula", self.JSON_549, texto=TEXTO_549)
        return next(r for r in rows if r.field_name == "proprietarios")

    def test_cadeia_de_titulares_vira_linha_com_destino(self):
        linha = self._linha()
        assert (linha.target_entity, linha.target_field) == ("matricula", "proprietarios")
        assert len(linha.field_value["value"]) == 4

    def test_uma_linha_para_a_matricula_inteira_nao_uma_por_titular(self):
        """Quatro linhas disputariam a MESMA coluna da MESMA matrícula: a primeira
        gravaria e as outras três virariam reconciliação falsa. É a diferença
        para `car.matriculas`, onde cada item tem hint (e linha) próprios."""
        rows = build_staging_fields("matricula", self.JSON_549, texto=TEXTO_549)
        assert sum(1 for r in rows if r.field_name == "proprietarios") == 1

    def test_cada_titular_ancorado_folha_a_folha(self):
        """Âncora informativa do composto (fronteira do ADR-064): 4 nomes + 4
        CPFs = 8 folhas, todas presentes no texto do documento."""
        ancora = self._linha().field_value["ancora"]
        assert ancora["escopo"] == "composto"
        assert (ancora["ancoradas"], ancora["verificaveis"]) == (8, 8)
        assert ancora["sem_ancora"] == []

    def test_titular_que_nao_esta_no_documento_aparece_como_folha_sem_ancora(self):
        poluido = {"proprietarios": [
            {"nome": "ELODI AGROPECUÁRIA", "cpf": "29.091.958/0001-17"},
            {"nome": "FULANO QUE NAO ESTA NO TEXTO", "cpf": "111.222.333-44"},
        ]}
        rows = build_staging_fields("matricula", poluido, texto=TEXTO_549)
        ancora = next(r for r in rows if r.field_name == "proprietarios").field_value["ancora"]
        assert ancora["ancoradas"] == 2 and ancora["verificaveis"] == 4
        assert len(ancora["sem_ancora"]) == 2


class TestAverbacaoRLTemGavetaPropria:
    """A AV.02 (492,9252 ha) que nenhuma execução tinha capturado."""

    def test_rl_vai_para_averbacao_rl_e_nao_para_app(self):
        parsed = {
            "averbacao_rl": {"area": "492,9252", "referencia": "AV.02"},
            "averbacao_app": None,
            "confidence": {"averbacao_rl": "high"},
        }
        rows = build_staging_fields("matricula", parsed, texto=TEXTO_549)
        campos = {r.field_name: r for r in rows}
        assert "averbacao_app" not in campos
        assert campos["averbacao_rl"].target_field == "averbacao_rl"
        assert campos["averbacao_rl"].field_value["value"]["area"] == "492,9252"


class TestCARDeixaDeColapsarAsAreas:
    """DATA-002 parcial: a área documental tinha texto, tinha coluna, e não tinha slot."""

    PARSED = {
        "area_declarada_ha": "2.180,8267",
        "area_documental_ha": "2180.3923",
        "modulos_fiscais": "31,1547",
        "confidence": {"area_declarada_ha": "high", "area_documental_ha": "high",
                       "modulos_fiscais": "high"},
    }

    def test_as_duas_areas_do_car_viram_duas_linhas_com_destinos_distintos(self):
        rows = build_staging_fields("car", self.PARSED, texto=TEXTO_546)
        destinos = {r.field_name: (r.target_entity, r.target_field) for r in rows}
        assert destinos["area_declarada_ha"] == ("imovel", "total_area_ha")
        assert destinos["area_documental_ha"] == ("imovel", "area_documental_ha")

    def test_area_documental_ancora_no_paragrafo_da_diferenca(self):
        rows = build_staging_fields("car", self.PARSED, texto=TEXTO_546)
        linha = next(r for r in rows if r.field_name == "area_documental_ha")
        assert "2180.3923" in linha.field_value["ancora"]["trecho"]

    def test_modulos_fiscais_pousa_no_imovel(self):
        rows = build_staging_fields("car", self.PARSED, texto=TEXTO_546)
        linha = next(r for r in rows if r.field_name == "modulos_fiscais")
        assert (linha.target_entity, linha.target_field) == ("imovel", "modulos_fiscais")
        assert linha.field_value["unidade"] == "módulos"

    def test_area_documental_passa_pela_faixa_de_plausibilidade(self):
        """Mesmo validador da área declarada (ADR-064, contenção 3)."""
        assert check_format("area_documental_ha", "2180.3923") is True
        assert check_format("area_documental_ha", "218039.23") is False

    def test_campo_novo_sem_fonte_no_texto_nao_ganha_destino(self):
        """A regra de fiação: todo campo novo passa pela âncora do #152."""
        rows = build_staging_fields(
            "car", {"modulos_fiscais": "99,9999"}, texto=TEXTO_546,
        )
        linha = next(r for r in rows if r.field_name == "modulos_fiscais")
        assert (linha.target_entity, linha.target_field) == (None, None)
        assert linha.field_value["sem_ancora"] is True
