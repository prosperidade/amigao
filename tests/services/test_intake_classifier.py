"""
Testes do classificador de intake — cobertura dos 16 DemandType.

Garante que TODO valor do enum DemandType é classificável (tem regra em
_DEMAND_RULES) e que selecioná-lo diretamente (process_type) não levanta
KeyError. Regressão da adição da regra `prad` (16º tipo).
"""
import pytest

from app.models.process import DemandType
from app.services.intake_classifier import classify_demand, get_demand_rules


def test_todos_os_16_demand_types_tem_regra():
    """Cada valor do enum DemandType tem regra correspondente no classifier."""
    rules = get_demand_rules()
    faltando = [d.value for d in DemandType if d.value not in rules]
    assert faltando == [], f"demand_types sem regra: {faltando}"
    # Sanidade: são exatamente 16.
    assert len(list(DemandType)) == 16


@pytest.mark.parametrize("demand", list(DemandType))
def test_classify_aceita_cada_demand_type_via_process_type(demand: DemandType):
    """Selecionar o subtipo direto (process_type) classifica sem KeyError."""
    result = classify_demand(
        description="Demanda de teste para classificação.",
        process_type=demand.value,
    )
    assert result.demand_type == demand.value
    assert result.demand_label  # label não-vazio
    assert result.checklist_template_demand_type == demand.value
    # estrutura de regra completa
    assert isinstance(result.required_documents, list)
    assert isinstance(result.suggested_next_steps, list)
    assert isinstance(result.relevant_agencies, list)


def test_prad_e_distinto_de_compensacao():
    """`prad` ganhou regra própria (não cai mais no fallback nem em compensacao)."""
    rules = get_demand_rules()
    assert "prad" in rules
    assert rules["prad"]["label"] != rules["compensacao"]["label"]
    result = classify_demand(description="x", process_type="prad")
    assert result.demand_type == "prad"


def test_descricao_sem_match_cai_em_nao_identificado():
    """Sem keywords reconhecíveis, classifica como nao_identificado (sem erro)."""
    result = classify_demand(description="texto totalmente neutro zzz")
    assert result.demand_type in {d.value for d in DemandType}
