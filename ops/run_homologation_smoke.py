from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import time
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.process import Process
from ops.provision_homologation_tenant import main as provision_main


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa smoke real de homologacao: login, mudanca de status, upload de documento, auditoria e metricas."
    )
    parser.add_argument("--api-base-url", default="http://localhost:8000")
    parser.add_argument("--internal-email", required=True)
    parser.add_argument("--portal-email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--tenant-name", default="Homologacao Documentos SMTP")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=2.0)
    return parser.parse_args()


def _provision_context(args: argparse.Namespace) -> dict:
    original_argv = sys.argv[:]
    try:
        sys.argv = [
            "provision_homologation_tenant.py",
            "--tenant-name",
            args.tenant_name,
            "--internal-email",
            args.internal_email,
            "--portal-email",
            args.portal_email,
            "--password",
            args.password,
        ]
        from io import StringIO
        import contextlib

        buffer = StringIO()
        with contextlib.redirect_stdout(buffer):
            exit_code = provision_main()
        if exit_code != 0:
            raise RuntimeError("Falha ao provisionar tenant controlado.")
        return json.loads(buffer.getvalue().strip())
    finally:
        sys.argv = original_argv


def _login(client: httpx.Client, api_base_url: str, *, email: str, password: str) -> str:
    response = client.post(
        f"{api_base_url}/api/v1/auth/login",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _create_process(client: httpx.Client, api_base_url: str, *, token: str, client_id: int, stamp: str) -> dict:
    response = client.post(
        f"{api_base_url}/api/v1/processes/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": f"Smoke Homologacao {stamp}",
            "process_type": "licenciamento",
            "client_id": client_id,
            "description": "Processo criado automaticamente pelo smoke operacional.",
            "status": "lead",
            "priority": "media",
            "urgency": "normal",
        },
    )
    response.raise_for_status()
    return response.json()


def _change_process_status(client: httpx.Client, api_base_url: str, *, token: str, process_id: int) -> dict:
    response = client.post(
        f"{api_base_url}/api/v1/processes/{process_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "triagem"},
    )
    response.raise_for_status()
    return response.json()


def _upload_document(client: httpx.Client, api_base_url: str, *, token: str, process_id: int, stamp: str) -> dict:
    upload_response = client.post(
        f"{api_base_url}/api/v1/documents/upload-url",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "process_id": process_id,
            "filename": f"smoke-homologacao-{stamp}.pdf",
            "content_type": "application/pdf",
        },
    )
    upload_response.raise_for_status()
    upload_payload = upload_response.json()

    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog>>endobj\n"
        b"trailer<</Root 1 0 R>>\n"
        b"%%EOF"
    )
    put_response = client.put(
        upload_payload["upload_url"],
        content=pdf_bytes,
        headers={"Content-Type": "application/pdf"},
        timeout=60.0,
    )
    put_response.raise_for_status()

    confirm_response = client.post(
        f"{api_base_url}/api/v1/documents/confirm-upload",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "process_id": process_id,
            "storage_key": upload_payload["storage_key"],
            "filename": f"smoke-homologacao-{stamp}.pdf",
            "content_type": "application/pdf",
            "file_size_bytes": len(pdf_bytes),
            "document_type": "comprovante",
            "document_category": "ambiental",
        },
    )
    confirm_response.raise_for_status()
    return confirm_response.json()


def _find_process_audits(process_id: int) -> list[AuditLog]:
    db = SessionLocal()
    try:
        return (
            db.query(AuditLog)
            .filter(AuditLog.entity_type == "process", AuditLog.entity_id == process_id)
            .order_by(AuditLog.created_at.desc())
            .all()
        )
    finally:
        db.close()


def _find_document_audits(document_id: int) -> list[AuditLog]:
    db = SessionLocal()
    try:
        return (
            db.query(AuditLog)
            .filter(AuditLog.entity_type == "document", AuditLog.entity_id == document_id)
            .order_by(AuditLog.created_at.desc())
            .all()
        )
    finally:
        db.close()


def _find_document(document_id: int) -> Document | None:
    db = SessionLocal()
    try:
        return db.query(Document).filter(Document.id == document_id).first()
    finally:
        db.close()


def _find_process(process_id: int) -> Process | None:
    db = SessionLocal()
    try:
        return db.query(Process).filter(Process.id == process_id).first()
    finally:
        db.close()


def _wait_for_audit(
    *,
    finder,
    entity_id: int,
    expected_action: str,
    timeout_seconds: float,
    poll_interval_seconds: float,
) -> list[AuditLog]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        rows = finder(entity_id)
        if any(row.action == expected_action for row in rows):
            return rows
        time.sleep(poll_interval_seconds)
    raise TimeoutError(f"Timeout aguardando auditoria '{expected_action}' para entity_id={entity_id}.")


def _extract_metric_lines(metrics_text: str) -> dict[str, list[str]]:
    patterns = {
        "notify_process_status_changed": 'amigao_celery_tasks_total{service="worker",task_name="workers.notify_process_status_changed",state="success"}',
        "notify_document_uploaded": 'amigao_celery_tasks_total{service="worker",task_name="workers.notify_document_uploaded",state="success"}',
        "email_delivery_success": 'amigao_email_delivery_total{service="worker",result="success"}',
        "document_upload_success": 'amigao_document_uploads_total{service="api",source="client_portal",result="success"}',
    }
    results: dict[str, list[str]] = {}
    for key, pattern in patterns.items():
        results[key] = [line for line in metrics_text.splitlines() if pattern in line]
    return results


def main() -> int:
    args = _parse_args()
    context = _provision_context(args)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        health = client.get(f"{args.api_base_url}/health")
        health.raise_for_status()

        internal_token = _login(client, args.api_base_url, email=args.internal_email, password=args.password)
        portal_token = _login(client, args.api_base_url, email=args.portal_email, password=args.password)

        created_process = _create_process(
            client,
            args.api_base_url,
            token=internal_token,
            client_id=context["client_id"],
            stamp=stamp,
        )
        updated_process = _change_process_status(
            client,
            args.api_base_url,
            token=internal_token,
            process_id=created_process["id"],
        )
        confirmed_document = _upload_document(
            client,
            args.api_base_url,
            token=portal_token,
            process_id=created_process["id"],
            stamp=stamp,
        )

        process_audits = _wait_for_audit(
            finder=_find_process_audits,
            entity_id=created_process["id"],
            expected_action="notification_process_status_changed",
            timeout_seconds=args.timeout_seconds,
            poll_interval_seconds=args.poll_interval_seconds,
        )
        document_audits = _wait_for_audit(
            finder=_find_document_audits,
            entity_id=confirmed_document["id"],
            expected_action="notification_document_uploaded",
            timeout_seconds=args.timeout_seconds,
            poll_interval_seconds=args.poll_interval_seconds,
        )

        metrics_response = client.get(f"{args.api_base_url}/metrics")
        metrics_response.raise_for_status()
        metric_lines = _extract_metric_lines(metrics_response.text)

    process_row = _find_process(created_process["id"])
    document_row = _find_document(confirmed_document["id"])

    result = {
        "tenant": {
            "id": context["tenant_id"],
            "name": context["tenant_name"],
        },
        "logins": {
            "internal": bool(internal_token),
            "portal": bool(portal_token),
        },
        "process": {
            "id": created_process["id"],
            "title": created_process["title"],
            "status_after_update": updated_process["status"],
            "db_status": process_row.status.value if process_row and process_row.status else None,
            "audit_actions": [row.action for row in process_audits],
        },
        "document": {
            "id": confirmed_document["id"],
            "storage_key": confirmed_document["storage_key"],
            "db_storage_key": document_row.storage_key if document_row else None,
            "audit_actions": [row.action for row in document_audits],
        },
        "metrics": metric_lines,
    }

    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
