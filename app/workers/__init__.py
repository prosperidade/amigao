from app.workers.tasks import (
    generate_ai_weekly_summary,
    generate_pdf_report,
    log_document_uploaded,
    notify_document_uploaded,
    notify_process_status_changed,
    send_email_notification,
    test_job,
)
from app.workers.agent_tasks import (  # noqa: F401
    run_agent,
    run_agent_chain,
    vigia_scheduled_check,
    vigia_all_tenants,
    acompanhamento_check_all,
)
from app.workers.webhook_tasks import send_webhook_alert  # noqa: F401
from app.workers.knowledge_indexer import (  # noqa: F401
    index_arbitrary_text_task,
    index_legislation_document_task,
    reindex_all_legislation,
)
