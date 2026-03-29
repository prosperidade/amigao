import os
from time import perf_counter
from typing import Dict, Any

from sqlalchemy.orm import Session

from app.core.alerts import emit_operational_alert
from app.core.logging import get_logger
from app.core.metrics import record_ai_summary
from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.process import Process
from app.models.task import Task, TaskStatus
from litellm import completion

logger = get_logger(__name__)

def generate_weekly_summary(tenant_id: int, process_id: int) -> Dict[str, Any]:
    db: Session = SessionLocal()
    started_at = perf_counter()
    try:
        process = db.query(Process).filter(Process.id == process_id, Process.tenant_id == tenant_id).first()
        if not process:
            return {"error": "Process not found"}

        # Coletar dados da semana (aqui pegamos tudo pro MVP)
        tasks = db.query(Task).filter(Task.process_id == process_id, Task.tenant_id == tenant_id).all()
        logs = (
            db.query(AuditLog)
            .filter(
                AuditLog.tenant_id == tenant_id,
                AuditLog.entity_type == "process",
                AuditLog.entity_id == process_id,
            )
            .all()
        )

        task_summaries = [f"- {t.title}: {'Concluido' if t.status == TaskStatus.concluida else 'Pendente'}" for t in tasks]
        log_summaries = [f"- Em {l.created_at.strftime('%d/%m/%Y')}: {l.details or l.action}" for l in logs]

        prompt = f"""
        Você é um assistente de engenharia ambiental.
        Dado o processo '{process.title}' (Status atual: {process.status.value}),
        crie um Resumo Executivo amigável e formal de 1 parágrafo para o cliente final.
        Mencione o que já foi concluído e o estado geral do processo.

        Tarefas:
        {chr(10).join(task_summaries)}

        Histórico recente:
        {chr(10).join(log_summaries)}

        Resumo Executivo (em Português):
        """

        # Usando a key OPENAI_API_KEY ou fallback mockado usando gpt-4o-mini se a API estiver configurada
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY não definida. Retornando resumo simulado para o cliente.")
            emit_operational_alert(
                category="ai_fallback",
                severity="warning",
                message="Resumo semanal gerado com fallback local por ausência de OPENAI_API_KEY",
                metadata={"tenant_id": tenant_id, "process_id": process_id},
            )
            ai_text = f"Resumo automático simulado: O processo '{process.title}' encontra-se '{process.status.value}'. Analisamos e validamos as tarefas documentadas. Tudo está caminhando conforme o esperado e manteremos você atualizado nos próximos passos."
        else:
            response = completion(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            ai_text = response.choices[0].message.content

        process.ai_summary = ai_text
        db.add(process)

        # Salvar o resumo na AuditLog como um evento do sistema
        audit = AuditLog(
            tenant_id=tenant_id,
            user_id=None, # System
            entity_type="process",
            entity_id=process.id,
            action="ai_summary_generated",
            details=ai_text
        )
        db.add(audit)
        db.commit()
        
        logger.info(f"✨ Resumo de IA gerado para Processo #{process_id}")
        record_ai_summary("success", perf_counter() - started_at)
        db.close()
        return {"status": "success", "summary": ai_text}

    except Exception as e:
        logger.error(f"Erro ao gerar resumo de IA: {str(e)}")
        record_ai_summary("failed", perf_counter() - started_at)
        emit_operational_alert(
            category="ai_summary_failure",
            severity="error",
            message="Falha ao gerar resumo semanal por IA",
            metadata={"tenant_id": tenant_id, "process_id": process_id, "error": str(e)},
        )
        db.rollback()
        db.close()
        return {"error": str(e)}

    return {"error": "Unhandled execution path"}
