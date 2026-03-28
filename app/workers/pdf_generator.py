import os
import io
import tempfile
import hashlib
from typing import List, Dict, Any
from fpdf import FPDF
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.tenant import Tenant
from app.models.process import Process
from app.models.task import Task
from app.models.document import Document
from app.services.storage import StorageService
from app.core.logging import get_logger

logger = get_logger(__name__)

class VisitReportPDF(FPDF):
    def __init__(self, tenant_name: str, process_name: str, logo_bytes: Any = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant_name = tenant_name
        self.process_name = process_name
        self.logo_bytes = logo_bytes

    def header(self):
        # Arial bold 15
        self.set_font("Arial", "B", 15)
        
        # Inserir Logo se existir
        if self.logo_bytes:
            # FPDF2 aceita imagens como BytesIO, porém abordagens de arquivo temp são mais universais
            import io
            try:
                self.image(self.logo_bytes, 10, 8, 33)
                self.cell(40) # Mover para direita para não sobrepor a logo
            except Exception as e:
                logger.error(f"Erro ao embutir logo no PDF: {e}")

        # Title
        self.cell(0, 10, f"Relatorio de Campo - {self.tenant_name}", 0, 1, "C" if not self.logo_bytes else "L")
        
        if self.logo_bytes:
            self.cell(40)
        
        self.set_font("Arial", "I", 12)
        self.cell(0, 10, f"Processo: {self.process_name}", 0, 1, "C" if not self.logo_bytes else "L")
        self.ln(15 if self.logo_bytes else 10)

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}}", 0, 0, "C")

def generate_process_visit_report(tenant_id: int, process_id: int) -> Dict[str, Any]:
    db: Session = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        process = db.query(Process).filter(Process.id == process_id, Process.tenant_id == tenant_id).first()
        
        if not process:
            logger.error(f"Process {process_id} not found for PDF generation.")
            return {"error": "Process not found"}

        tasks = db.query(Task).filter(Task.process_id == process_id).all()

        # Busca Logo no MinIO
        storage = StorageService()
        logo_key = f"tenant_{tenant_id}/logo.png"
        logo_bytes = storage.download_bytes(logo_key)

        pdf = VisitReportPDF(
            tenant_name=tenant.name if tenant else "Empresa",
            process_name=process.name,
            logo_bytes=io.BytesIO(logo_bytes) if logo_bytes else None
        )
        pdf.alias_nb_pages()
        pdf.add_page()
        
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Informacoes do Processo:", 0, 1)
        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 10, f"Status Atual: {process.status.upper()}", 0, 1)
        pdf.cell(0, 10, f"Imovel Associado: #{process.property_id or 'N/A'}", 0, 1)
        pdf.cell(0, 10, f"Criado em: {process.created_at.strftime('%d/%m/%Y')}", 0, 1)
        pdf.ln(10)

        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Historico de Tarefas de Campo (Checklist):", 0, 1)
        pdf.set_font("Arial", "", 10)
        
        for idx, task in enumerate(tasks, start=1):
            status_text = "[ OK ]" if task.status == "done" else "[ Pendente ]"
            pdf.cell(0, 8, f"{idx}. {status_text} {task.title}", 0, 1)

        pdf.ln(10)
        pdf.set_font("Arial", "I", 9)
        pdf.cell(0, 10, "Documento gerado automaticamente pelo motor do Amigao do Meio Ambiente.", 0, 1, "C")

        # Save to bytes
        pdf_bytes = pdf.output(dest="S").encode("latin1")

        # Upload to MinIO
        storage = StorageService()
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
            filename=filename,
            storage_key=upload_result["storage_key"],
            content_type="application/pdf",
            size=len(pdf_bytes),
            checksum_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            metadata_json={"source": "auto_generated", "type": "visit_report"},
            status="verified"
        )
        db.add(doc)
        db.commit()

        logger.info(f"Relatorio PDF gerado com sucesso: {filename}")
        db.close()
        return {"status": "success", "document_id": doc.id}

    except Exception as e:
        logger.error(f"Erro ao gerar PDF do processo {process_id}: {str(e)}")
        db.rollback()
        db.close()
        return {"error": str(e)}

    return {"error": "Unhandled execution path"}
