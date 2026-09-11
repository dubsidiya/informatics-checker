from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict, deque
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

from checker.grade import grade_solution
from checker.problems import get_problem, list_summaries

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8765"))

_RATE_LOCK = threading.Lock()
_HITS: dict[str, deque[float]] = defaultdict(deque)
RATE_LIMIT = 30
RATE_WINDOW = 60.0


def _allow(ip: str) -> bool:
    now = time.time()
    with _RATE_LOCK:
        bucket = _HITS[ip]
        while bucket and now - bucket[0] > RATE_WINDOW:
            bucket.popleft()
        if len(bucket) >= RATE_LIMIT:
            return False
        bucket.append(now)
        return True


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def log_message(self, format, *args):
        print(f"{self.address_string()} {args[0]}")

    def _client_ip(self) -> str:
        forwarded = self.headers.get("CF-Connecting-IP") or self.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client_address[0]

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_file(WEB / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path in {"/health", "/api/health"}:
            self._send_json({"ok": True})
            return
        if parsed.path == "/api/problems":
            self._send_json(list_summaries())
            return
        if parsed.path.startswith("/api/problems/"):
            problem_id = parsed.path.removeprefix("/api/problems/").strip("/")
            try:
                self._send_json(get_problem(problem_id).public_dict())
            except KeyError:
                self._send_json({"detail": "Задача не найдена"}, 404)
            return
        if parsed.path.startswith("/static/"):
            name = parsed.path.removeprefix("/static/")
            path = (WEB / name).resolve()
            if WEB.resolve() not in path.parents and path != WEB.resolve():
                self.send_error(404)
                return
            if not path.is_file():
                self.send_error(404)
                return
            content_type = {
                ".css": "text/css; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".html": "text/html; charset=utf-8",
            }.get(path.suffix, "application/octet-stream")
            self._send_file(path, content_type)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/check":
            self.send_error(404)
            return
        if not _allow(self._client_ip()):
            self._send_json({"detail": "Слишком много попыток. Подожди минуту."}, 429)
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            problem_id = payload["problem_id"]
            code = payload.get("code", "")
            if not isinstance(code, str) or len(code) > 80_000:
                raise ValueError("bad code")
            result = grade_solution(get_problem(problem_id), code)
        except KeyError:
            self._send_json({"detail": "Задача не найдена"}, 404)
            return
        except (json.JSONDecodeError, TypeError, ValueError):
            self._send_json({"detail": "Некорректный запрос"}, 400)
            return
        self._send_json(result.to_dict())

    def _send_json(self, payload: dict | list, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Проверяльщик: http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
