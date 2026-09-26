"""Apoio de teste: o orçamento aprovado de um caso pelo caminho real (ADR-074/ADR-081).

Desde a #284 a proposta de um caso só nasce do orçamento aprovado e atual. Testes que precisam
de uma proposta montam aqui o que o consultor faria: método padrão do tenant → relatório e escopo
gerados da Rota assinada → escopo aprovado → orçamento gerado → orçamento aprovado. Nada de
atalho no banco: são os mesmos serviços que a API chama.
"""

from __future__ import annotations

from decimal import Decimal

from app.models.comercial import Orcamento, OrcamentoMetodo
from app.services.comercial import orcamento as orcamento_mod
from app.services.comercial import redator as redator_mod


def orcamento_aprovado(db, *, process, user_id: int, valor_hora: str = "150.00",
                       horas_padrao: str = "4") -> Orcamento:
    """Orçamento aprovado e atual para ``process`` (que precisa de Rota assinada com item de proposta).

    Com os padrões, cada passo cobrado vale 4 h × R$ 150 = R$ 600.
    """
    tenant_id = process.tenant_id
    if not db.query(OrcamentoMetodo).filter(OrcamentoMetodo.tenant_id == tenant_id,
                                            OrcamentoMetodo.padrao.is_(True)).first():
        orcamento_mod.criar_versao_metodo(db, tenant_id=tenant_id, user_id=user_id, codigo="hora_tecnica",
                                          nome="Hora técnica", unidade="hora",
                                          valor_unitario=Decimal(valor_hora),
                                          quantidade_padrao=Decimal(horas_padrao), rule_ids=[], padrao=True)
    _, escopo = redator_mod.gerar(db, process=process, tenant_id=tenant_id, user_id=user_id)
    orcamento_mod.revisar(db, escopo, user_id=user_id, acao="aprovar", justificativa="escopo conferido (teste)")
    o = orcamento_mod.gerar(db, process=process, tenant_id=tenant_id, user_id=user_id)
    orcamento_mod.revisar(db, o, user_id=user_id, acao="aprovar", justificativa="preços conferidos (teste)")
    db.flush()
    return o
