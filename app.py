from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import defaultdict, deque
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from checker.grade import grade_solution
from checker.problems import get_problem, list_summaries
from checker.store import (
    clean_student_name,
    get_attempt,
    latest_attempt,
    list_attempts,
    record_attempt,
    summarize,
)

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8765"))
TEACHER_PIN = os.environ.get("TEACHER_PIN", "159753pupil")
TEACHER_TOKEN = hashlib.sha256(f"checker::{TEACHER_PIN}".encode("utf-8")).hexdigest()

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

    def _cookies(self) -> dict[str, str]:
        raw = self.headers.get("Cookie", "")
        jar = SimpleCookie()
        try:
            jar.load(raw)
        except Exception:
            return {}
        return {key: morsel.value for key, morsel in jar.items()}

    def _is_teacher(self) -> bool:
        return self._cookies().get("teacher") == TEACHER_TOKEN

    def _set_teacher_cookie(self, value: str, max_age: int) -> None:
        flags = "HttpOnly; Path=/; SameSite=Lax"
        if os.environ.get("RENDER"):
            flags += "; Secure"
        self.send_header("Set-Cookie", f"teacher={value}; Max-Age={max_age}; {flags}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if path == "/":
            self._send_file(WEB / "index.html", "text/html; charset=utf-8")
            return
        if path == "/teacher":
            self._send_file(WEB / "teacher.html", "text/html; charset=utf-8")
            return
        if path in {"/health", "/api/health"}:
            self._send_json({"ok": True})
            return
        if path == "/api/problems":
            self._send_json(list_summaries())
            return
        if path.startswith("/api/problems/") and path.endswith("/file"):
            problem_id = path.removeprefix("/api/problems/").removesuffix("/file").strip("/")
            try:
                problem = get_problem(problem_id)
            except KeyError:
                self._send_json({"detail": "Задача не найдена"}, 404)
                return
            if not problem.files:
                self._send_json({"detail": "К задаче нет файла"}, 404)
                return
            file_path = (ROOT / "data" / problem.files[0]).resolve()
            data_root = (ROOT / "data").resolve()
            if data_root not in file_path.parents or not file_path.is_file():
                self._send_json({"detail": "Файл не найден"}, 404)
                return
            data = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{file_path.name}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path.startswith("/api/problems/"):
            problem_id = path.removeprefix("/api/problems/").strip("/")
            try:
                self._send_json(get_problem(problem_id).public_dict())
            except KeyError:
                self._send_json({"detail": "Задача не найдена"}, 404)
            return
        if path == "/api/teacher/me":
            self._send_json({"ok": self._is_teacher()})
            return
        if path == "/api/teacher/summary":
            if not self._is_teacher():
                self._send_json({"detail": "Нужен вход учителя"}, 401)
                return
            self._send_json(summarize())
            return
        if path == "/api/teacher/attempts":
            if not self._is_teacher():
                self._send_json({"detail": "Нужен вход учителя"}, 401)
                return
            student = (query.get("student") or [""])[0]
            problem_id = (query.get("problem_id") or [""])[0]
            self._send_json(list_attempts(student=student, problem_id=problem_id))
            return
        if path.startswith("/api/teacher/attempts/"):
            if not self._is_teacher():
                self._send_json({"detail": "Нужен вход учителя"}, 401)
                return
            raw_id = path.removeprefix("/api/teacher/attempts/").strip("/")
            try:
                attempt = get_attempt(int(raw_id))
            except ValueError:
                attempt = None
            if not attempt:
                self._send_json({"detail": "Попытка не найдена"}, 404)
                return
            self._send_json(attempt)
            return
        if path == "/api/teacher/latest":
            if not self._is_teacher():
                self._send_json({"detail": "Нужен вход учителя"}, 401)
                return
            student = (query.get("student") or [""])[0]
            problem_id = (query.get("problem_id") or [""])[0]
            attempt = latest_attempt(student, problem_id) if student and problem_id else None
            if not attempt:
                self._send_json({"detail": "Попыток нет"}, 404)
                return
            self._send_json(attempt)
            return
        if path.startswith("/static/"):
            name = path.removeprefix("/static/")
            file_path = (WEB / name).resolve()
            if WEB.resolve() not in file_path.parents and file_path != WEB.resolve():
                self.send_error(404)
                return
            if not file_path.is_file():
                self.send_error(404)
                return
            content_type = {
                ".css": "text/css; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".html": "text/html; charset=utf-8",
            }.get(file_path.suffix, "application/octet-stream")
            self._send_file(file_path, content_type)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        length = int(self.headers.get("Content-Length", "0"))
        if length > 200_000:
            self._send_json({"detail": "Слишком большой запрос"}, 413)
            return
        raw = self.rfile.read(length)

        if path == "/api/teacher/login":
            try:
                payload = json.loads(raw.decode("utf-8"))
                pin = payload.get("pin", "")
            except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                self._send_json({"detail": "Некорректный запрос"}, 400)
                return
            if pin != TEACHER_PIN:
                self._send_json({"detail": "Неверный пин"}, 403)
                return
            self._send_json({"ok": True}, cookie=TEACHER_TOKEN)
            return

        if path == "/api/teacher/logout":
            self._send_json({"ok": True}, cookie="", cookie_age=0)
            return

        if path != "/api/check":
            self.send_error(404)
            return
        if not _allow(self._client_ip()):
            self._send_json({"detail": "Слишком много попыток. Подожди минуту."}, 429)
            return
        try:
            payload = json.loads(raw.decode("utf-8"))
            problem_id = payload["problem_id"]
            code = payload.get("code", "")
            student = clean_student_name(payload.get("student", ""))
            if not isinstance(code, str) or len(code) > 80_000:
                raise ValueError("bad code")
            result = grade_solution(get_problem(problem_id), code)
        except KeyError:
            self._send_json({"detail": "Задача не найдена"}, 404)
            return
        except (json.JSONDecodeError, TypeError, ValueError, UnicodeDecodeError):
            self._send_json({"detail": "Некорректный запрос"}, 400)
            return
        record_attempt(
            student=student,
            problem_id=problem_id,
            status=result.status,
            passed=result.passed,
            total=result.total,
            message=result.message,
            code=code,
        )
        payload_out = result.to_dict()
        payload_out["student"] = student
        self._send_json(payload_out)

    def _send_json(self, payload: dict | list, status: int = 200, cookie: str | None = None, cookie_age: int = 60 * 60 * 12) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if cookie is not None:
            self._set_teacher_cookie(cookie, cookie_age)
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
