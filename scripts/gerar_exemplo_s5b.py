"""Gera exemplos FICTÍCIOS de proposta e contrato Mirante (S5-B) — evidência.

Exercita os builders reais (``build_proposta``/``build_contrato`` + validações +
guard de placeholder + render) com dados 100% fictícios e escreve o texto
renderizado em ``docs/templates/exemplos/``. ZERO PII real.

Uso:  python scripts/gerar_exemplo_s5b.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from app.models.proposal import ProposalStatus
from app.services.mirante_documents import (
    build_contrato,
    build_proposta,
    render_contrato_text,
    render_proposta_text,
)

FIXED_DATE = datetime(2026, 7, 19, tzinfo=UTC)


def _fake_context():
    tenant = SimpleNamespace(id=1, settings={
        "issuer": {
            "razao_social": "Mirante Consultoria Ambiental Ltda.",
            "cnpj": "00.000.000/0001-00",
            "endereco": "Rua Exemplo, 000 — Município Exemplo/UF",
            "responsavel_tecnico": {
                "nome": "Eng. Fictícia de Exemplo",
                "titulo": "Engenheira Agrônoma",
                "crea": "CREA-XX 000000/D",
            },
            "banco": {
                "nome": "Banco Exemplo (000)", "agencia": "0000", "conta": "00000-0",
                "titular": "Mirante Consultoria Ambiental Ltda.", "pix": "00.000.000/0001-00",
            },
            "condicoes": {"foro": "Comarca de Município Exemplo/UF", "multa_percentual": "10%"},
        }
    })
    client = SimpleNamespace(id=1, full_name="Cliente Exemplo", cpf_cnpj="000.000.000-00",
                             client_type=SimpleNamespace(value="pf"))
    mat = SimpleNamespace(id=1, numero_matricula="0.000", is_vigente=True)
    prop = SimpleNamespace(
        id=1, name="Fazenda Exemplo", municipality="Município Exemplo", state="UF",
        total_area_ha=349.9022, tipologia="Pecuária extensiva", registry_number="0.000",
        matriculas_vigentes=lambda: [mat],
        area_total_matriculas=lambda: 349.9022,
    )
    process = SimpleNamespace(id=1, property_id=1, title="Regularização Fazenda Exemplo",
                             demand_type=SimpleNamespace(value="car"))
    scope_items = [
        {"description": "Diagnóstico ambiental do imóvel", "detail":
         "Levantamento documental e análise da situação regulatória.",
         "total": 600.0, "rota_passo_id": 101, "norma_ref": "Lei 12.651/2012", "prazo_dias": 15},
        {"description": "Regularização do Cadastro Ambiental Rural (CAR)", "detail":
         "Retificação e adequação do CAR no SICAR.",
         "total": 600.0, "rota_passo_id": 102, "norma_ref": "IN SICAR", "prazo_dias": 15},
    ]
    proposal = SimpleNamespace(
        id=42, tenant_id=1, client_id=1, process_id=1, title="Proposta — Fazenda Exemplo",
        scope_items=scope_items, total_value=1200.0, validity_days=30,
        payment_terms="50% na assinatura e 50% na entrega.",
        payment_installments=[
            {"numero": 1, "vencimento": "Na assinatura", "valor": 600.0},
            {"numero": 2, "vencimento": "Na entrega", "valor": 600.0},
        ],
        status=ProposalStatus.accepted,
    )

    class FakeDB:
        _by_name = {"Tenant": tenant, "Client": client, "Process": process, "Property": prop}

        def query(self, model):
            obj = self._by_name.get(getattr(model, "__name__", ""))
            return SimpleNamespace(filter=lambda *a, **k: SimpleNamespace(first=lambda: obj))

    return FakeDB(), proposal


def main() -> None:
    db, proposal = _fake_context()
    out = Path(__file__).resolve().parents[1] / "docs" / "templates" / "exemplos"
    out.mkdir(parents=True, exist_ok=True)

    prop_doc = build_proposta(db, proposal, data=FIXED_DATE)
    (out / "EXEMPLO_PROPOSTA.txt").write_text(render_proposta_text(prop_doc), encoding="utf-8")

    ctr_doc = build_contrato(db, proposal, data=FIXED_DATE)
    (out / "EXEMPLO_CONTRATO.txt").write_text(render_contrato_text(ctr_doc), encoding="utf-8")

    print("Exemplos gerados em", out)


if __name__ == "__main__":
    main()
