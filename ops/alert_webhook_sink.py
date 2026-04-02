import argparse
import hashlib
import hmac
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class AlertWebhookHandler(BaseHTTPRequestHandler):
    output_path: Path
    expected_auth_header: str = ""
    expected_auth_token: str = ""
    signing_secret: str = ""

    def _write_json(self, status_code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._write_json(200, {"status": "ok"})
            return
        self._write_json(404, {"status": "not_found"})

    def _validate_request(self, raw_body: bytes) -> tuple[int | None, dict]:
        auth_enabled = bool(self.expected_auth_header and self.expected_auth_token)
        signature_enabled = bool(self.signing_secret)
        validation = {
            "auth_enabled": auth_enabled,
            "auth_ok": True,
            "signature_enabled": signature_enabled,
            "signature_ok": True,
        }

        if auth_enabled:
            received_token = self.headers.get(self.expected_auth_header, "")
            validation["auth_ok"] = hmac.compare_digest(received_token, self.expected_auth_token)
            if not validation["auth_ok"]:
                return 401, validation

        if signature_enabled:
            expected_signature = "sha256=" + hmac.new(
                self.signing_secret.encode("utf-8"),
                raw_body,
                hashlib.sha256,
            ).hexdigest()
            received_signature = self.headers.get("X-Amigao-Signature-256", "")
            validation["received_signature"] = received_signature
            validation["signature_ok"] = hmac.compare_digest(received_signature, expected_signature)
            if not validation["signature_ok"]:
                return 401, validation

        return None, validation

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {"raw_body": raw_body.decode("utf-8", errors="replace")}

        error_status, validation = self._validate_request(raw_body)
        status_code = error_status or 202

        entry = {
            "received_at": datetime.now(timezone.utc).isoformat(),
            "path": self.path,
            "status_code": status_code,
            "headers": {key: value for key, value in self.headers.items()},
            "validation": validation,
            "payload": payload,
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

        if error_status:
            self._write_json(error_status, {"status": "rejected", "validation": validation})
            return

        self._write_json(202, {"status": "accepted", "validation": validation})

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Recebe webhooks de alerta e persiste em JSONL.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8011)
    parser.add_argument(
        "--output",
        default="ops/runtime/alert-webhook-capture.jsonl",
        help="Arquivo JSONL onde cada webhook recebido sera persistido.",
    )
    parser.add_argument("--auth-header", default="", help="Header esperado para autenticacao do webhook.")
    parser.add_argument("--auth-token", default="", help="Valor esperado no header de autenticacao.")
    parser.add_argument(
        "--signing-secret",
        default="",
        help="Segredo opcional para validar a assinatura HMAC SHA-256 do corpo.",
    )
    args = parser.parse_args()

    AlertWebhookHandler.output_path = Path(args.output).resolve()
    AlertWebhookHandler.expected_auth_header = args.auth_header.strip()
    AlertWebhookHandler.expected_auth_token = args.auth_token.strip()
    AlertWebhookHandler.signing_secret = args.signing_secret.strip()
    server = ThreadingHTTPServer((args.host, args.port), AlertWebhookHandler)
    print(
        f"Webhook sink ouvindo em http://{args.host}:{args.port} "
        f"e persistindo em {AlertWebhookHandler.output_path}"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
