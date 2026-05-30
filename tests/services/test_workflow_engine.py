from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.workflow_engine import TemplateNotFoundError, apply_workflow_template


def test_apply_workflow_template_raises_when_template_missing():
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value.order_by.return_value.first.return_value = None

    with pytest.raises(TemplateNotFoundError) as exc:
        apply_workflow_template(
            db=db,
            process_id=999,
            tenant_id=1,
            demand_type="sobreposicao",
            created_by_user_id=1,
        )

    assert "sobreposicao" in str(exc.value)
    assert "WorkflowTemplate" in str(exc.value)
