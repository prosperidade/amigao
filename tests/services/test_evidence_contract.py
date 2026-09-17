"""Contract tests: absence, versions and legacy provenance are different axes."""

import pytest
from pydantic import ValidationError

from app.schemas.evidence import EvidenceObject, Knowledge
from app.schemas.stage_output import SourceRef


@pytest.mark.parametrize("payload", [
    {"state": "ausencia_verificada_no_escopo"},
    {"state": "nao_localizado_no_material"},
    {"state": "nao_aplicavel"},
])
def test_knowledge_requires_recoverable_support(payload):
    with pytest.raises(ValidationError):
        Knowledge.model_validate(payload)


def test_agent_output_is_never_primary():
    with pytest.raises(ValidationError):
        EvidenceObject(id="x", version=1, kind="fonte_primaria", origin="auditor")
    with pytest.raises(ValidationError):
        SourceRef(tipo="auditor", primary=True, evidence_id="x", evidence_version=1)


def test_risk_requires_applicability():
    with pytest.raises(ValidationError):
        EvidenceObject(id="x", version=1, kind="conclusao", origin="diagnostico",
                       statement="GEO ausente implica risco", conclusion_class="risco")
