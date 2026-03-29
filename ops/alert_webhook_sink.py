import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class AlertWebhookHandler(BaseHTTPRequestHandler):
    output_path: Path

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

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            payload = {"raw_body": raw_body.decode("utf-8", errors="replace")}

        entry = {
            "received_at": datetime.now(timezone.utc).isoformat(),
            "path": self.path,
            "headers": {key: value for key, value in self.headers.items()},
            "payload": payload,
        }

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with self.output_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._write_json(202, {"status": "accepted"})

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
    args = parser.parse_args()

    AlertWebhookHandler.output_path = Path(args.output).resolve()
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
