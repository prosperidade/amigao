from app.workers.agent_tasks import (  # noqa: F401
    acompanhamento_check_all,
    run_agent,
    run_agent_chain,
    vigia_all_tenants,
    vigia_scheduled_check,
)
from app.workers.knowledge_indexer import (  # noqa: F401
    index_arbitrary_text_task,
    index_legislation_document_task,
    reindex_all_legislation,
)
from app.workers.ocr_tasks import ocr_then_extract  # noqa: F401
from app.workers.tasks import (
    generate_ai_weekly_summary,
    generate_pdf_report,
    log_document_uploaded,
    notify_document_uploaded,
    notify_process_status_changed,
    send_email_notification,
    test_job,
)
from app.workers.waitlist_tasks import (  # noqa: F401
    send_welcome_email,
    sync_resend_audience,
)
from app.workers.webhook_tasks import send_webhook_alert  # noqa: F401
