import io
from datetime import datetime
from typing import Any, Dict

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.document import Document, OcrStatus
from app.models.tenant import Tenant
from app.models.process import Process
from app.models.task import Task, TaskStatus
from app.services.storage import StorageService, get_storage_service

logger = get_logger(__name__)


def _format_date(value: datetime | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "N/A"


def _safe_text(value: Any) -> str:
    if value is None:
        return "N/A"
    return str(value)


class VisitReportPDF(FPDF):
    def __init__(
        self,
        tenant_name: str,
        process_name: str,
        generated_at: str,
        logo_bytes: Any = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.tenant_name = tenant_name
        self.process_name = process_name
        self.generated_at = generated_at
        self.logo_bytes = logo_bytes
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(15, 16, 15)

    @property
    def content_width(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def section_title(self, title: str):
        self.set_fill_color(236, 253, 245)
        self.set_text_color(6, 95, 70)
        self.set_font("Helvetica", "B", 11)
        self.cell(0, 9, title, border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L", fill=True)
        self.set_text_color(33, 37, 41)
        self.ln(2)

    def info_row(self, label: str, value: Any):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(self.content_width, 7, f"{label}: {_safe_text(value)}")

    def paragraph(self, text: str):
        self.set_font("Helvetica", "", 10)
        self.multi_cell(self.content_width, 6, text)
        self.ln(1)

    def header(self):
        self.set_draw_color(209, 213, 219)
        self.set_font("Helvetica", "B", 16)

        if self.logo_bytes:
            try:
                self.image(self.logo_bytes, x=15, y=11, w=24, h=24, keep_aspect_ratio=True)
            except Exception as e:
                logger.error(f"Erro ao embutir logo no PDF: {e}")

        left_offset = 32 if self.logo_bytes else 0
        if self.logo_bytes:
            self.cell(left_offset)

        self.cell(0, 8, "Relatorio de Visita Tecnica", border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        if self.logo_bytes:
            self.cell(left_offset)

        self.set_font("Helvetica", "", 11)
        self.set_text_color(75, 85, 99)
        self.cell(0, 6, self.tenant_name, border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        if self.logo_bytes:
            self.cell(left_offset)

        self.set_font("Helvetica", "I", 10)
        self.cell(0, 6, f"Processo: {self.process_name}", border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        if self.logo_bytes:
            self.cell(left_offset)
        self.cell(0, 6, f"Gerado em: {self.generated_at}", border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        self.set_text_color(33, 37, 41)
        self.ln(6)
        self.line(15, self.get_y(), 195, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(107, 114, 128)
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}}", border=0, new_x=XPos.RIGHT, new_y=YPos.TOP, align="C")


def _load_tenant_logo(storage: StorageService, tenant_id: int) -> bytes:
    for extension in ("png", "jpg", "jpeg"):
        logo_key = f"tenant_{tenant_id}/logo.{extension}"
        logo_bytes = storage.download_bytes(logo_key)
        if logo_bytes:
            return logo_bytes
    return b""

def generate_process_visit_report(tenant_id: int, process_id: int) -> Dict[str, Any]:
    db: Session = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        process = db.query(Process).filter(Process.id == process_id, Process.tenant_id == tenant_id).first()
        
        if not process:
            logger.error(f"Process {process_id} not found for PDF generation.")
            return {"error": "Process not found"}

        tasks = db.query(Task).filter(Task.process_id == process_id, Task.tenant_id == tenant_id).all()

        # Busca Logo no MinIO
        storage = get_storage_service()
        logo_bytes = _load_tenant_logo(storage, tenant_id)

        total_tasks = len(tasks)
        done_tasks = sum(1 for task in tasks if task.status == TaskStatus.concluida)
        generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")

        pdf = VisitReportPDF(
            tenant_name=tenant.name if tenant else "Empresa",
            process_name=process.title,
            generated_at=generated_at,
            logo_bytes=io.BytesIO(logo_bytes) if logo_bytes else None
        )
        pdf.alias_nb_pages()
        pdf.add_page()
        
        pdf.section_title("Resumo do Processo")
        pdf.info_row("Cliente", process.client.full_name if process.client else "N/A")
        pdf.info_row("Status atual", process.status.value.upper())
        pdf.info_row("Tipo de processo", process.process_type)
        pdf.info_row("Imovel associado", f"#{process.property_id}" if process.property_id else "Nao vinculado")
        pdf.info_row("Prioridade", process.priority.value.upper() if process.priority else "N/A")
        pdf.info_row("Criado em", _format_date(process.created_at))
        pdf.info_row("Prazo", _format_date(process.due_date))
        pdf.info_row("Protocolo externo", process.external_protocol_number or "Nao informado")
        pdf.info_row("Orgao de destino", process.destination_agency or "Nao informado")
        pdf.info_row("Tarefas concluidas", f"{done_tasks}/{total_tasks}")

        if process.description:
            pdf.ln(2)
            pdf.section_title("Descricao")
            pdf.paragraph(process.description)

        if process.ai_summary:
            pdf.section_title("Resumo Executivo")
            pdf.paragraph(process.ai_summary)

        pdf.section_title("Checklist de Campo")
        if tasks:
            for idx, task in enumerate(tasks, start=1):
                status_text = "[OK]" if task.status == TaskStatus.concluida else "[PENDENTE]"
                due_date = _format_date(task.due_date)
                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(0, 7, f"{idx}. {status_text} {task.title}", border=0, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                pdf.set_font("Helvetica", "", 9)
                pdf.multi_cell(
                    pdf.content_width,
                    6,
                    f"Prazo: {due_date} | Prioridade: {task.priority.value.upper()} | Status: {task.status.value}",
                )
                if task.description:
                    pdf.multi_cell(pdf.content_width, 6, f"Observacoes: {task.description}")
                pdf.ln(2)
        else:
            pdf.paragraph("Nenhuma tarefa de campo foi registrada para este processo ate o momento.")

        pdf.section_title("Fechamento")
        pdf.paragraph(
            "Documento gerado automaticamente pelo motor do Amigao do Meio Ambiente para consolidacao do atendimento tecnico."
        )

        # O retorno do FPDF pode variar entre str e bytearray conforme a versão.
        raw_output = pdf.output()
        pdf_bytes = raw_output.encode("latin1") if isinstance(raw_output, str) else bytes(raw_output)

        # Upload to MinIO
        storage = get_storage_service()
        filename = f"Relatorio_Visita_{process.id}.pdf"
        
        upload_result = storage.upload_bytes(
            content=pdf_bytes,
            filename=filename,
            content_type="application/pdf",
            tenant_id=tenant_id,
            process_id=process_id
        )

        doc = Document(
            tenant_id=tenant_id,
            process_id=process_id,
            client_id=process.client_id,
            filename=filename,
            original_file_name=filename,
            storage_key=upload_result["storage_key"],
            s3_key=upload_result["storage_key"],
            content_type="application/pdf",
            mime_type="application/pdf",
            extension="pdf",
            file_size_bytes=upload_result["file_size_bytes"],
            size=upload_result["file_size_bytes"],
            checksum_sha256=upload_result["checksum_sha256"],
            document_type="relatorio_visita",
            document_category="relatorio",
            ocr_status=OcrStatus.not_required,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        logger.info(f"Relatorio PDF gerado com sucesso: {filename}")
        db.close()
        return {"status": "success", "document_id": doc.id}

    except Exception as e:
        logger.error(f"Erro ao gerar PDF do processo {process_id}: {str(e)}")
        db.rollback()
        db.close()
        return {"error": str(e)}

    return {"error": "Unhandled execution path"}
