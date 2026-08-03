"""Campo de imóvel com N matrículas: mostra as duas ou nenhuma — nunca inventa.

Regra de domínio dada pela consultora na validação de 02/08. Ela consolidou um
caso com duas matrículas e o imóvel exibiu "as duas matrículas sem dados". Ao
descrever o que esperava ver, fixou a forma: ``"349,9022 | 660,6561"`` — os
valores lado a lado — **ou** vazio quando há mais de uma e não dá para dizer.
O que não pode acontecer é o cabeçalho do imóvel escolher uma das matrículas
(a outra some sem aviso) ou fabricar um número novo.

`Property.agregar_das_matriculas` é a porta única dessa regra.
"""

from __future__ import annotations

import pytest

from app.models.property import Property


class _MatriculaFake:
    """Dublê leve: o helper só lê atributos, não toca no banco."""

    def __init__(self, **campos):
        self.deactivated_at = None
        self.vigencia = "vigente"
        self.numero_matricula = None
        self.cartorio = None
        self.area_ha = None
        self.codigo_incra_sncr = None
        for k, v in campos.items():
            setattr(self, k, v)


class _ImovelFake:
    """Imóvel sem ORM que empresta os métodos REAIS de ``Property``.

    Atribuir dublês direto em ``Property.matriculas`` não funciona: é uma
    relationship instrumentada e o SQLAlchemy exige instâncias mapeadas. Emprestar
    os métodos mantém o teste exercitando o código de produção — o que se troca é
    só o acesso ao banco.
    """

    matriculas_ativas = Property.matriculas_ativas
    matriculas_vigentes = Property.matriculas_vigentes
    agregar_das_matriculas = Property.agregar_das_matriculas

    def __init__(self, matriculas):
        self.matriculas = list(matriculas)


def _imovel(*matriculas) -> _ImovelFake:
    return _ImovelFake(matriculas)


# ---------------------------------------------------------------------------
# A forma que ela pediu
# ---------------------------------------------------------------------------

def test_duas_areas_saem_lado_a_lado_em_formato_br() -> None:
    """O caso concreto da validação: 349,9022 e 660,6561."""
    prop = _imovel(_MatriculaFake(area_ha=349.9022), _MatriculaFake(area_ha=660.6561))
    assert prop.agregar_das_matriculas("area_ha") == "349,9022 | 660,6561"


def test_valor_unico_quando_as_matriculas_concordam() -> None:
    """Concordância não vira lista — a repetição só polui a leitura."""
    prop = _imovel(
        _MatriculaFake(cartorio="CRI de Jataí"),
        _MatriculaFake(cartorio="CRI de Jataí"),
    )
    assert prop.agregar_das_matriculas("cartorio") == "CRI de Jataí"


def test_vazio_quando_nenhuma_matricula_tem_o_dado() -> None:
    prop = _imovel(_MatriculaFake(), _MatriculaFake())
    assert prop.agregar_das_matriculas("cartorio") is None


def test_nunca_escolhe_uma_matricula_quando_so_uma_tem_o_dado() -> None:
    """O valor solitário aparece — mas como o valor DELE, não como "o" do imóvel.

    Ficar só com "2923" quando a outra matrícula não tem número é aceitável
    (não há concorrente); o que a regra proíbe é DESCARTAR um valor existente
    para exibir o outro. O teste seguinte cobre esse caso.
    """
    prop = _imovel(_MatriculaFake(numero_matricula="2923"), _MatriculaFake())
    assert prop.agregar_das_matriculas("numero_matricula") == "2923"


def test_nenhum_valor_e_descartado_quando_ha_divergencia() -> None:
    prop = _imovel(
        _MatriculaFake(numero_matricula="2923"),
        _MatriculaFake(numero_matricula="4517"),
    )
    saida = prop.agregar_das_matriculas("numero_matricula")
    assert "2923" in saida and "4517" in saida


# ---------------------------------------------------------------------------
# Quem entra na agregação
# ---------------------------------------------------------------------------

def test_matricula_historica_nao_entra() -> None:
    """Ficha anterior da cadeia é linhagem, não estado atual (Dívida #60)."""
    prop = _imovel(
        _MatriculaFake(numero_matricula="4517"),
        _MatriculaFake(numero_matricula="2923", vigencia="historica"),
    )
    assert prop.agregar_das_matriculas("numero_matricula") == "4517"


def test_matricula_desativada_nao_entra() -> None:
    """Rejeitada na Conferência sai da vista sem ser apagada (forense Isis)."""
    from datetime import UTC, datetime

    prop = _imovel(
        _MatriculaFake(numero_matricula="4517"),
        _MatriculaFake(numero_matricula="2923", deactivated_at=datetime.now(UTC)),
    )
    assert prop.agregar_das_matriculas("numero_matricula") == "4517"


def test_imovel_sem_matricula_nao_quebra() -> None:
    assert _imovel().agregar_das_matriculas("numero_matricula") is None


# ---------------------------------------------------------------------------
# Higiene de formatação
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("valor", "esperado"),
    [(349.9022, "349,9022"), (100.0, "100"), (0.5, "0,5"), (1234.5678, "1234,5678")],
)
def test_float_sai_em_formato_br_sem_zeros_a_toa(valor: float, esperado: str) -> None:
    """A consultora lê e digita área com vírgula decimal."""
    assert _imovel(_MatriculaFake(area_ha=valor)).agregar_das_matriculas("area_ha") == esperado


def test_valores_repetidos_nao_duplicam_na_lista() -> None:
    prop = _imovel(
        _MatriculaFake(cartorio="CRI de Jataí"),
        _MatriculaFake(cartorio="CRI de Jataí"),
        _MatriculaFake(cartorio="CRI de Rio Verde"),
    )
    assert prop.agregar_das_matriculas("cartorio") == "CRI de Jataí | CRI de Rio Verde"


def test_string_em_branco_conta_como_ausente() -> None:
    prop = _imovel(_MatriculaFake(cartorio="   "), _MatriculaFake(cartorio="CRI de Jataí"))
    assert prop.agregar_das_matriculas("cartorio") == "CRI de Jataí"
