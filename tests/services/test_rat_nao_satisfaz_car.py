"""RAT é contexto/histórico — nunca o CAR (decisão da Isis, 26/07).

O RAT (Relatório de Análise Técnica) é o parecer do órgão **sobre** o CAR, numa
data. Ele traz área vetorizada, pendências e situação — informação valiosa, e
justamente por isso tentadora: parece completo o bastante para "valer como CAR".
Não vale. O documento oficial do cadastro é o recibo/demonstrativo; o RAT é uma
fotografia de uma análise que pode já estar superada.

Este teste é um guard de REGRESSÃO de domínio: se alguém, olhando a riqueza do
RAT, incluí-lo em `doc_types` do requisito `car`, o caso passa a parecer completo
sem o documento que o órgão realmente exige.
"""

from app.services.requisito_documental import REQUISITOS_POR_KEY


def test_rat_nao_esta_entre_os_doc_types_do_car():
    car = REQUISITOS_POR_KEY["car"]
    assert "rat" not in car.doc_types, (
        "RAT entrou como documento do CAR — é parecer sobre o CAR, não o CAR. "
        "Ver Ficha 08 §2 e ADR-031."
    )


def test_rat_nao_e_equivalente_de_nenhum_requisito():
    """Equivalência é a outra porta pela qual o RAT poderia entrar."""
    for key, req in REQUISITOS_POR_KEY.items():
        assert "rat" not in (req.equivalentes or frozenset()), (
            f"RAT virou equivalente do requisito '{key}'"
        )


def test_car_continua_aceitando_o_recibo_oficial():
    """Controle positivo: fechar a porta do RAT não pode fechar a do recibo."""
    car = REQUISITOS_POR_KEY["car"]
    assert "car" in car.doc_types
    assert "recibo_car" in car.doc_types
