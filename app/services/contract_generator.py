"""
Contract Generator — Sprint 4

Preenche templates de contrato com dados reais do processo/cliente/proposta
e gera PDF usando fpdf2.
"""

from __future__ import annotations
import io
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.contract_template import ContractTemplate
from app.models.proposal import Proposal
from app.models.process import Process
from app.models.client import Client
from app.models.property import Property

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Substituição de variáveis no template
# ---------------------------------------------------------------------------

def fill_contract_template(
    db: Session,
    contract: Contract,
) -> str:
    """
    Substitui variáveis {{...}} no template com dados reais do contrato.
    Retorna o texto preenchido.
    """
    template = db.query(ContractTemplate).filter(ContractTemplate.id == contract.template_id).first()
    if not template:
        return "[Erro: template não encontrado]"

    raw = template.content_template

    # Dados da empresa (tenant) — valores padrão se não configurados
    raw = raw.replace("{{empresa.nome}}", "Amigão do Meio Ambiente")
    raw = raw.replace("{{empresa.cnpj}}", "00.000.000/0001-00")
    raw = raw.replace("{{empresa.municipio}}", "")

    # Dados do cliente
    client = db.query(Client).filter(Client.id == contract.client_id).first()
    if client:
        raw = raw.replace("{{cliente.nome}}", client.full_name or "")
        raw = raw.replace("{{cliente.cpf_cnpj}}", client.cpf_cnpj or "")
        raw = raw.replace("{{cliente.email}}", client.email or "")
        raw = raw.replace("{{cliente.telefone}}", client.phone or "")
    else:
        for v in ["{{cliente.nome}}", "{{cliente.cpf_cnpj}}", "{{cliente.email}}", "{{cliente.telefone}}"]:
            raw = raw.replace(v, "")

    # Dados do imóvel
    prop: Optional[Property] = None
    if contract.process_id:
        process = db.query(Process).filter(Process.id == contract.process_id).first()
        if process and process.property_id:
            prop = db.query(Property).filter(Property.id == process.property_id).first()

    if prop:
        raw = raw.replace("{{imovel.nome}}", prop.name or "")
        raw = raw.replace("{{imovel.matricula}}", prop.registry_number or "—")
        raw = raw.replace("{{imovel.municipio}}", prop.municipality or "")
        raw = raw.replace("{{imovel.uf}}", prop.state or "")
        raw = raw.replace("{{imovel.area_ha}}", str(prop.total_area_ha) if prop.total_area_ha else "—")
        raw = raw.replace("{{imovel.car}}", prop.car_code or "—")
    else:
        for v in ["{{imovel.nome}}", "{{imovel.matricula}}", "{{imovel.municipio}}",
                  "{{imovel.uf}}", "{{imovel.area_ha}}", "{{imovel.car}}"]:
            raw = raw.replace(v, "—")

    # Dados da proposta
    proposal: Optional[Proposal] = None
    if contract.proposal_id:
        proposal = db.query(Proposal).filter(Proposal.id == contract.proposal_id).first()

    if proposal:
        scope_text = _format_scope(proposal.scope_items or [])
        raw = raw.replace("{{proposta.escopo}}", scope_text)
        raw = raw.replace("{{proposta.valor_total}}", _fmt_currency(proposal.total_value))
        raw = raw.replace("{{proposta.condicoes_pagamento}}", proposal.payment_terms or "A combinar")
        raw = raw.replace("{{proposta.prazo_dias}}", str(proposal.validity_days or 30))
        raw = raw.replace("{{proposta.notas}}", proposal.notes or "")
    else:
        for v in ["{{proposta.escopo}}", "{{proposta.valor_total}}", "{{proposta.condicoes_pagamento}}",
                  "{{proposta.prazo_dias}}", "{{proposta.notas}}"]:
            raw = raw.replace(v, "—")

    # Data de emissão
    hoje = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    raw = raw.replace("{{contrato.data_emissao}}", hoje)

    return raw


def render_pdf(contract: Contract, filled_content: str) -> bytes:
    """
    Gera PDF a partir do conteúdo preenchido usando fpdf2.
    Retorna os bytes do PDF.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        logger.error("fpdf2 não está instalado. Execute: pip install fpdf2")
        raise

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Cabeçalho
    pdf.set_font("Helvetica", style="B", size=14)
    pdf.set_text_color(30, 120, 60)
    pdf.cell(0, 10, "AMIGÃO DO MEIO AMBIENTE", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", style="", size=9)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 6, "Consultoria e Regularização Ambiental", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Linha separadora
    pdf.set_draw_color(30, 120, 60)
    pdf.set_line_width(0.5)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
    pdf.ln(6)

    # Título do contrato
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 8, contract.title.upper(), align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Corpo do contrato
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(40, 40, 40)

    for line in filled_content.split("\n"):
        line = line.strip()
        # Títulos em negrito (linhas em CAPS ou que terminam com ':')
        if line.isupper() and len(line) > 4:
            pdf.set_font("Helvetica", style="B", size=10)
            pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", size=10)
        elif line.endswith(":") and len(line) < 60:
            pdf.set_font("Helvetica", style="B", size=10)
            pdf.cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", size=10)
        elif line == "":
            pdf.ln(3)
        else:
            pdf.multi_cell(0, 5.5, line)

    # Rodapé
    pdf.ln(8)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", size=8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, f"Documento gerado em {datetime.now(timezone.utc).strftime('%d/%m/%Y às %H:%M')} UTC — Amigão do Meio Ambiente",
             align="C", new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())


def find_template_for_demand(db: Session, tenant_id: int, demand_type: Optional[str]) -> Optional[ContractTemplate]:
    """Busca o melhor template disponível para o tipo de demanda."""
    from sqlalchemy import or_
    query = (
        db.query(ContractTemplate)
        .filter(
            ContractTemplate.is_active == True,
            or_(
                ContractTemplate.tenant_id == tenant_id,
                ContractTemplate.tenant_id == None,
            ),
        )
    )
    if demand_type:
        # Prefer exact match
        exact = query.filter(ContractTemplate.demand_type == demand_type).order_by(
            ContractTemplate.tenant_id.desc().nullslast()
        ).first()
        if exact:
            return exact
    # Fallback: genérico (demand_type IS NULL)
    return query.filter(ContractTemplate.demand_type == None).order_by(
        ContractTemplate.tenant_id.desc().nullslast()
    ).first()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_scope(scope_items: list) -> str:
    if not scope_items:
        return "Conforme acordado."
    lines = []
    for i, item in enumerate(scope_items, start=1):
        desc = item.get("description", "")
        total = item.get("total", 0)
        if total:
            lines.append(f"  {i}. {desc} — R$ {_fmt_currency(total)}")
        else:
            lines.append(f"  {i}. {desc}")
    return "\n".join(lines)


def _fmt_currency(value) -> str:
    if value is None:
        return "A combinar"
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(value)
