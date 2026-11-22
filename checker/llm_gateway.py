from __future__ import annotations

"""Authenticated door in front of a local Ollama.

The checker on the server reaches this process through an SSH tunnel.
Ollama itself stays on 127.0.0.1 and is not exposed. Only /api/chat is
forwarded, so a caller cannot pull models or read the disk through us.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import URLError
from urllib.request import Request, urlopen


def gateway_token() -> str:
    return (os.environ.get("LLM_TOKEN") or os.environ.get("MIMO_TOKEN") or "").strip()


def ollama_chat_url() -> str:
    base = (os.environ.get("OLLAMA_URL") or "http://127.0.0.1:11434").rstrip("/")
    return base + "/api/chat"


def authorized(header: str | None, token: str) -> bool:
    if not token:
        return False
    expected = f"Bearer {token}"
    return header == expected


class GatewayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] != "/api/chat":
            self._send(404, {"detail": "Только /api/chat."})
            return
        token = gateway_token()
        if not authorized(self.headers.get("Authorization"), token):
            self._send(401, {"detail": "Нужен токен."})
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        if length <= 0 or length > 120_000:
            self._send(400, {"detail": "Плохое тело запроса."})
            return
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send(400, {"detail": "Нужен JSON."})
            return
        if not isinstance(payload, dict) or not isinstance(payload.get("messages"), list):
            self._send(400, {"detail": "Нужен список messages."})
            return
        payload["stream"] = False
        request = Request(
            ollama_chat_url(),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=45) as response:
                body = response.read()
                status = response.status
        except (URLError, TimeoutError, OSError):
            self._send(502, {"detail": "Ollama не ответила."})
            return
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] == "/health":
            self._send(200, {"ok": True})
            return
        self._send(404, {"detail": "Страница не найдена."})

    def log_message(self, fmt: str, *args) -> None:
        return

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(host: str = "127.0.0.1", port: int = 8788) -> None:
    if not gateway_token():
        raise SystemExit("Задай LLM_TOKEN, иначе шлюз никого не пустит.")
    httpd = ThreadingHTTPServer((host, port), GatewayHandler)
    print(f"mimo gateway on http://{host}:{port}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    bind = (os.environ.get("MIMO_BIND") or "127.0.0.1").strip() or "127.0.0.1"
    port = int((os.environ.get("MIMO_PORT") or "8788").strip())
    serve(bind, port)
