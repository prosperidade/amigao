"""ADR-034 — a esfera vem do ÓRGÃO do passivo, nunca da UF do imóvel.

O caso que motivou a regra é o processo 15: uma fazenda em Goiás com autos do
IBAMA (federal) E notificação da SEMAD/GO (estadual). Derivar a esfera do estado
faria o sistema responder a auto federal com norma estadual — errado de um jeito
que passa despercebido, porque o texto sai plausível.
"""

import pytest

from app.services.esfera import esfera_do_orgao


class TestEsferaDoOrgao:
    @pytest.mark.parametrize(
        "orgao",
        [
            "IBAMA",
            "Superintendência do IBAMA em Goiás",
            "INSTITUTO BRASILEIRO DO MEIO AMBIENTE E DOS RECURSOS NATURAIS RENOVÁVEIS",
            "MINISTÉRIO DO MEIO AMBIENTE - MMA",
            "ICMBio",
            "INCRA",
        ],
    )
    def test_orgao_federal(self, orgao):
        assert esfera_do_orgao(orgao) == "federal"

    @pytest.mark.parametrize(
        "orgao",
        [
            "SEMAD",
            "SEMAD/GO",
            "Secretaria de Estado de Meio Ambiente e Desenvolvimento Sustentável",
            "IMASUL",
            "SEMA-MT",
            "CETESB",
        ],
    )
    def test_orgao_estadual(self, orgao):
        assert esfera_do_orgao(orgao) == "estadual"

    def test_orgao_municipal(self):
        assert esfera_do_orgao("Secretaria Municipal de Meio Ambiente") == "municipal"

    def test_ibama_go_nao_vira_estadual_pela_uf_colada(self):
        """"IBAMA-GO" tem sigla de UF no nome — e continua FEDERAL.

        É a regra inteira em um caso: o órgão nomeado vence a pista geográfica.
        """
        assert esfera_do_orgao("IBAMA-GO-EQ.TÉCNICA") == "federal"
        assert esfera_do_orgao("Superintendência do IBAMA em Goiás") == "federal"

    @pytest.mark.parametrize("valor", [None, "", "   ", "Fazenda São Jorge", "Goiás"])
    def test_sem_orgao_reconhecivel_devolve_none(self, valor):
        """`None` é resposta legítima: não saber ≠ chutar 'estadual porque é GO'."""
        assert esfera_do_orgao(valor) is None

    def test_sigla_curta_nao_casa_dentro_de_palavra(self):
        """'ima'/'ana' não podem casar dentro de 'estimativa'/'Paraná'."""
        assert esfera_do_orgao("estimativa de área") is None
        assert esfera_do_orgao("imóvel no Paraná") is None


class TestDoisPassivosDuasEsferas:
    """O caso real: no MESMO caso, cada passivo com a sua esfera."""

    def test_ibama_e_semad_no_mesmo_caso(self):
        auto_ibama = (
            "MINISTÉRIO DO MEIO AMBIENTE - MMA\n"
            "INSTITUTO BRASILEIRO DO MEIO AMBIENTE E DOS RECURSOS NATURAIS RENOVÁVEIS - IBAMA\n"
            "Documento: 484341/D (Auto de Infração)"
        )
        notificacao_semad = (
            "A retificação culminou na emissão da Notificação GO-NOT-2024-001985 "
            "pela SEMAD, cujo prazo de 180 dias já venceu"
        )
        assert esfera_do_orgao(auto_ibama) == "federal"
        assert esfera_do_orgao(notificacao_semad) == "estadual"
        # E os dois convivem — nenhuma UF decide por eles.
        assert esfera_do_orgao(auto_ibama) != esfera_do_orgao(notificacao_semad)
