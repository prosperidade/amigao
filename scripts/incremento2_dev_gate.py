"""Servidor do percurso real em dev; recebe textos MCP apenas em memória/DB dev.

Sem mocks de LLM, sem arquivos de texto, HAR, screenshots ou traces de payload.
O canal de preparação é loopback; as ações do caso usam API autenticada na UI.
"""
# Environment isolation must precede imports that instantiate settings/engines.
# ruff: noqa: E402
import hashlib
import json
import os
import re
import socket
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from uuid import uuid4

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT.parent / ".env")
# Luna is André's decision; Terra only for the comparative measurement he authorized (21/09/2026).
MODEL = os.environ.get("INC2_MODEL", "gpt-5.6-luna")
assert MODEL in {"gpt-5.6-luna", "gpt-5.6-terra"}, "Gate model outside the authorized measurement"
os.environ.update(POSTGRES_SERVER="127.0.0.1", POSTGRES_PORT=os.environ["HOST_DB_PORT"], DATABASE_URL="",
    ENVIRONMENT="development",
    AI_TIMEOUT_SECONDS="180", AI_EXTRATOR_MODEL=MODEL, AI_EXTRATOR_ALLOW_FALLBACK="false",
    REDIS_URL="redis://127.0.0.1:6379/15", LOG_LEVEL="CRITICAL", ALERT_WEBHOOK_URL="",
    GEMINI_API_KEY="", ANTHROPIC_API_KEY="",
    OPENAI_API_BASE="https://api.openai.com/v1", OPENAI_BASE_URL="https://api.openai.com/v1")
os.environ.pop("MIGRATE_DATABASE_URL", None)

from sqlalchemy.engine import make_url

from app.core.config import settings
from app.core.model_matrix import resolve_agent_models

# Preserve André's model decision. Fail before opening the server.
models = resolve_agent_models("extrator", settings)
assert len(models) == 1 and not settings.AI_EXTRATOR_ALLOW_FALLBACK and models[0][0] == MODEL and models[0][1], (
    "Gate requires the measured model alone, with credentials")
assert all(name in {MODEL, "gemini/gemini-3.7-flash"} for name, _ in models), (
    "Gate allows only the approved Gemini 3.7 Flash fallback")

target = make_url(settings.SQLALCHEMY_DATABASE_URI)
assert (target.host, target.port, target.database, target.username) == ("127.0.0.1", 15432, "amigao_db", "postgres")

import uvicorn
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.celery_app import celery_app
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.main import app
from app.models.client import Client
from app.models.document import Document, DocumentSource, OcrStatus
from app.models.process import Process
from app.models.property import Property
from app.models.tenant import Tenant
from app.models.user import User

celery_app.conf.update(task_always_eager=True, task_eager_propagates=True,
    task_store_eager_result=False, broker_url="memory://", result_backend="cache+memory://")
state = {"cases": {}, "documents": {}}
buffers = {}


class Control(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        data = json.dumps(state).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        try:
            with SessionLocal() as db:
                if self.path == "/setup":
                    assert "tenant" not in state
                    suffix = uuid4().hex[:10]
                    tenant = Tenant(name=f"Incremento 2 gate {suffix}")
                    db.add(tenant)
                    db.flush()
                    email = f"inc2-{suffix}@example.com"
                    user = User(tenant_id=tenant.id, email=email, full_name="Gate Incremento 2",
                        hashed_password=get_password_hash("GateIncremento2!2026"), is_active=True)
                    db.add(user)
                    db.flush()
                    state.update(tenant=tenant.id, user=user.id, email=email)
                    for data in body["cases"]:
                        client = Client(tenant_id=tenant.id, full_name=data["name"], client_type=data["type"], cpf_cnpj=data["document"])
                        db.add(client)
                        db.flush()
                        prop = Property(tenant_id=tenant.id, client_id=client.id, name=f"Caso real {data['origin']}", state="GO")
                        db.add(prop)
                        db.flush()
                        case = Process(tenant_id=tenant.id, client_id=client.id, property_id=prop.id,
                            title=f"Gate Inc2 caso {data['origin']}", process_type="car", macroetapa="entrada_demanda",
                            opened_at=datetime.now(UTC))
                        db.add(case)
                        db.flush()
                        state["cases"][str(data["origin"])] = case.id
                    db.commit()
                elif self.path == "/source":
                    key = body["id"]
                    if body.get("first"):
                        buffers[key] = []
                    buffers[key].append(body["text"])
                    if body.get("last"):
                        text = "".join(buffers.pop(key))
                        assert hashlib.sha256(text.encode()).hexdigest() == body["text_sha256"]
                        doc = Document(tenant_id=state["tenant"], process_id=None,
                            original_file_name=body["original_file_name"], filename=body["original_file_name"],
                            content_type=body["content_type"], checksum_sha256=body["checksum_sha256"],
                            extracted_text=text, document_type=body["document_type"], ocr_status=OcrStatus.done,
                            source=DocumentSource.integration, storage_provider="mcp_read_only",
                            storage_key=f"mcp-read/{state['tenant']}/{key}", uploaded_by_user_id=state["user"])
                        db.add(doc)
                        db.commit()
                        state["documents"][str(key)] = {"id": doc.id, "case": state["cases"][str(body["process_id"])],
                            "sha256": body["text_sha256"]}
                else:
                    raise ValueError("Unknown preparation operation")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
        except Exception as exc:
            # Never print SQL parameters or Pydantic input values from source text.
            self.send_response(422)
            self.end_headers()
            self.wfile.write(json.dumps({"error_type": type(exc).__name__}).encode())


def main():
    if os.getenv("INC2_RESUME_TENANT"):
        tenant_id = int(os.environ["INC2_RESUME_TENANT"])
        with SessionLocal() as db:
            tenant = db.get(Tenant, tenant_id)
            assert tenant and tenant.name.startswith("Incremento 2 gate ")
            user = db.query(User).filter_by(tenant_id=tenant_id).one()
            state.update(tenant=tenant_id, user=user.id, email=user.email)
            for case in db.query(Process).filter_by(tenant_id=tenant_id):
                state["cases"][case.title.removeprefix("Gate Inc2 caso ")] = case.id
            receipt_text = (ROOT / "docs/auditoria/GATE_INCREMENTO2.md").read_text(encoding="utf-8")
            expected = {m[0]: (int(m[1]), int(m[2]), m[3]) for m in re.findall(
                r"\| (\d+) \| (\d+) \| (\d+) \| `([a-f0-9]{64})`", receipt_text)}
            for doc in db.query(Document).filter_by(tenant_id=tenant_id):
                assert doc.storage_key.startswith(f"mcp-read/{tenant_id}/")
                origin = doc.storage_key.rsplit("/", 1)[1]
                actual = (len(doc.extracted_text), len(doc.extracted_text.encode()), hashlib.sha256(doc.extracted_text.encode()).hexdigest())
                assert actual == expected[origin], "Dev source differs from MCP receipt"
                state["documents"][origin] = {"id": doc.id, "case": doc.process_id,
                    "sha256": hashlib.sha256(doc.extracted_text.encode()).hexdigest()}
    if os.getenv("INC2_RESUME_TENANT"):
        assert set(state["documents"]) <= {"546", "547", "548", "549", "550", "551", "557", "558", "559"}
    dist = ROOT / "frontend/dist"
    assert (dist / "index.html").exists()
    app.mount("/assets", StaticFiles(directory=dist / "assets"))
    def index():
        return FileResponse(dist / "index.html")
    for route in ("/login", "/dashboard", "/processes/{process_id}", "/processes/{process_id}/documentos-observacoes"):
        app.add_api_route(route, index, include_in_schema=False)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    state["url"] = f"http://127.0.0.1:{sock.getsockname()[1]}"
    server = uvicorn.Server(uvicorn.Config(app, log_level="critical", access_log=False))
    Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True).start()
    control = HTTPServer(("127.0.0.1", 0), Control)
    print(json.dumps({"control_port": control.server_port, "api": state["url"], "db": "127.0.0.1:15432/amigao_db",
                      "model": MODEL}), flush=True)
    control.serve_forever()


if __name__ == "__main__":
    main()
