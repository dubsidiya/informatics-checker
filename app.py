from __future__ import annotations

import json
import os
import shutil
import threading
import time
import traceback
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from checker.auth import cookie_flags, hash_token, pin_fingerprint, verify_pin
from checker.backup import restore_sqlite, sqlite_backup
from checker.config import get_config, reset_config
from checker.explain import deepen_explanation
from checker.grade import grade_solution
from checker.http_security import RateLimiter, client_ip, origin_allowed, parse_content_length
from checker.observability import bump, log_event, new_request_id, snapshot
from checker.problems import get_problem, list_summaries
from checker.runner import RunnerError
from checker.store import (
    create_student_session,
    create_teacher_session,
    export_attempts,
    export_backup_json,
    export_csv,
    get_attempt,
    get_student_session,
    get_teacher_session,
    import_journal,
    init_store,
    restore_backup_json,
    latest_attempt,
    list_attempts,
    live_exam,
    problem_attempt_count,
    probe_write,
    record_attempt,
    revoke_student_session,
    revoke_teacher_session,
    start_exam,
    student_progress,
    summarize,
    update_exam,
)
from checker.topics import list_topic_cards

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
_RATE = RateLimiter()
_GRADE_GATE: threading.BoundedSemaphore | None = None


def _gate() -> threading.BoundedSemaphore:
    global _GRADE_GATE
    if _GRADE_GATE is None:
        _GRADE_GATE = threading.BoundedSemaphore(get_config().grade_concurrency)
    return _GRADE_GATE


def _teacher_pin() -> str:
    cfg = get_config()
    return cfg.teacher_pin or ""


def _pin_ok(pin: str) -> bool:
    cfg = get_config()
    if cfg.teacher_pin_hash:
        return verify_pin(pin, cfg.teacher_pin_hash)
    if cfg.teacher_pin and not cfg.is_production:
        return pin == cfg.teacher_pin
    return False


def _fingerprint() -> str:
    cfg = get_config()
    secret = cfg.teacher_pin_hash or cfg.teacher_pin or "unset"
    return pin_fingerprint(secret)


class BoundedThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, addr, handler, thread_limit: int = 32):
        super().__init__(addr, handler)
        self._sema = threading.BoundedSemaphore(thread_limit)

    def process_request(self, request, client_address):
        if not self._sema.acquire(blocking=False):
            try:
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            except OSError:
                pass
            try:
                request.close()
            except OSError:
                pass
            bump("http_503")
            return
        self.RequestHandlerClass(request, client_address, self, _release=self._sema.release)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, _release=None, **kwargs):
        self._release = _release
        self._headers_sent = False
        self.request_id = new_request_id()
        super().__init__(*args, directory=str(WEB), **kwargs)

    def finish(self) -> None:
        try:
            super().finish()
        finally:
            if self._release:
                self._release()
                self._release = None

    def log_message(self, format, *args):
        return

    def _cfg(self):
        return get_config()

    def _client_ip(self) -> str:
        return client_ip(
            self.client_address[0],
            self.headers.get("X-Forwarded-For"),
            self._cfg().trusted_proxy_cidrs,
        )

    def _loopback(self) -> bool:
        return self.client_address[0] in {"127.0.0.1", "::1"}

    def _cookies(self) -> dict[str, str]:
        raw = self.headers.get("Cookie", "")
        jar = SimpleCookie()
        try:
            jar.load(raw)
        except Exception:
            return {}
        return {key: morsel.value for key, morsel in jar.items()}

    def _teacher(self) -> dict | None:
        return get_teacher_session(self._cookies().get("teacher", ""), _fingerprint())

    def _student(self) -> dict | None:
        return get_student_session(self._cookies().get("student", ""))

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
        self.send_header("X-Request-Id", self.request_id)

    def _set_cookie(self, name: str, value: str, max_age: int, httponly: bool = True) -> None:
        secure = self._cfg().is_production or bool(os.environ.get("RENDER"))
        self.send_header(
            "Set-Cookie",
            f"{name}={value}; {cookie_flags(secure=secure, max_age=max_age, httponly=httponly)}",
        )

    def _origin_ok(self, method: str) -> bool:
        return origin_allowed(
            self.headers.get("Origin", ""),
            self.headers.get("Referer", ""),
            self.headers.get("Host", ""),
            self._cfg().public_origin,
            loopback=self._loopback(),
            method=method,
        )

    def _csrf_ok(self, expected_hash: str) -> bool:
        got = self.headers.get("X-CSRF-Token", "")
        return bool(got) and hash_token(got) == expected_hash

    def do_HEAD(self) -> None:
        self._dispatch("HEAD")

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        start = time.monotonic()
        bump("requests")
        try:
            if method in {"GET", "HEAD"}:
                self._route_get(method)
            else:
                self._route_post()
        except Exception:
            traceback.print_exc()
            if not self._headers_sent:
                self._send_json({"detail": "Внутренняя ошибка проверяльщика.", "code": "internal"}, 500)
        finally:
            log_event(
                "http",
                request_id=self.request_id,
                method=method,
                path=urlparse(self.path).path,
                ms=int((time.monotonic() - start) * 1000),
            )

    def _route_get(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if path == "/":
            self._send_file(WEB / "index.html", "text/html; charset=utf-8", method)
            return
        if path == "/teacher":
            self._send_file(WEB / "teacher.html", "text/html; charset=utf-8", method)
            return
        if path in {"/favicon.svg", "/favicon.ico"}:
            icon = WEB / "favicon.svg"
            if icon.is_file():
                self._send_file(icon, "image/svg+xml", method)
                return
        if path in {"/livez"}:
            self._send_json({"ok": True}, head=method == "HEAD")
            return
        if path in {"/health", "/api/health", "/readyz"}:
            ok, detail = self._ready()
            payload = {"ok": ok, "detail": detail, "counters": snapshot()}
            self._send_json(payload, 200 if ok else 503, head=method == "HEAD")
            return
        if path == "/api/problems":
            self._send_json(list_summaries(), head=method == "HEAD")
            return
        if path == "/api/topics":
            self._send_json(list_topic_cards(), head=method == "HEAD")
            return
        if path == "/api/progress":
            if not _RATE.allow(f"progress:{self._client_ip()}", self._cfg().progress_limit):
                bump("http_429")
                self._send_json({"detail": "Слишком много запросов. Подожди минуту."}, 429, head=method == "HEAD")
                return
            session = self._student()
            if not session:
                self._send_json({"detail": "Сначала укажи имя."}, 401, head=method == "HEAD")
                return
            self._send_json(student_progress(session["student"], student_id=session["student_id"]), head=method == "HEAD")
            return
        if path == "/api/student/me":
            session = self._student()
            if not session:
                self._send_json({"ok": False}, head=method == "HEAD")
                return
            exam = live_exam(session["student_id"])
            progress = student_progress(session["student"], student_id=session["student_id"])
            self._send_json({"ok": True, "student": session["student"], "exam": exam, "progress": progress}, head=method == "HEAD")
            return
        if path.startswith("/api/problems/") and path.endswith("/file"):
            problem_id = path.removeprefix("/api/problems/").removesuffix("/file").strip("/")
            try:
                problem = get_problem(problem_id)
            except KeyError:
                self._send_json({"detail": "Задача не найдена"}, 404, head=method == "HEAD")
                return
            if not problem.files:
                self._send_json({"detail": "К задаче нет файла"}, 404, head=method == "HEAD")
                return
            file_path = (ROOT / "data" / problem.files[0]).resolve()
            data_root = (ROOT / "data").resolve()
            if data_root not in file_path.parents or not file_path.is_file():
                self._send_json({"detail": "Файл не найден"}, 404, head=method == "HEAD")
                return
            data = file_path.read_bytes()
            self.send_response(200)
            self._headers_sent = True
            self._security_headers()
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{file_path.name}"')
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if method != "HEAD":
                self.wfile.write(data)
            return
        if path.startswith("/api/problems/"):
            problem_id = path.removeprefix("/api/problems/").strip("/")
            try:
                self._send_json(get_problem(problem_id).public_dict(), head=method == "HEAD")
            except KeyError:
                self._send_json({"detail": "Задача не найдена"}, 404, head=method == "HEAD")
            return
        if path == "/api/teacher/me":
            teacher = self._teacher()
            self._send_json({"ok": bool(teacher)}, head=method == "HEAD")
            return
        if path == "/api/teacher/summary":
            if method == "HEAD":
                if not self._teacher():
                    self._send_json({"detail": "Нужен вход учителя"}, 401, head=True)
                    return
                self._send_json({"ok": True}, head=True)
                return
            if not self._teacher():
                self._send_json({"detail": "Нужен вход учителя"}, 401)
                return
            self._send_json(summarize())
            return
        if path == "/api/teacher/attempts":
            if not self._teacher():
                self._send_json({"detail": "Нужен вход учителя"}, 401, head=method == "HEAD")
                return
            student = (query.get("student") or [""])[0]
            problem_id = (query.get("problem_id") or [""])[0]
            self._send_json(list_attempts(student=student, problem_id=problem_id), head=method == "HEAD")
            return
        if path.startswith("/api/teacher/attempts/"):
            if not self._teacher():
                self._send_json({"detail": "Нужен вход учителя"}, 401, head=method == "HEAD")
                return
            raw_id = path.removeprefix("/api/teacher/attempts/").strip("/")
            try:
                attempt = get_attempt(int(raw_id))
            except ValueError:
                attempt = None
            if not attempt:
                self._send_json({"detail": "Попытка не найдена"}, 404, head=method == "HEAD")
                return
            self._send_json(attempt, head=method == "HEAD")
            return
        if path == "/api/teacher/latest":
            if not self._teacher():
                self._send_json({"detail": "Нужен вход учителя"}, 401, head=method == "HEAD")
                return
            student = (query.get("student") or [""])[0]
            problem_id = (query.get("problem_id") or [""])[0]
            attempt = latest_attempt(student, problem_id) if student and problem_id else None
            if not attempt:
                self._send_json({"detail": "Попыток нет"}, 404, head=method == "HEAD")
                return
            self._send_json(attempt, head=method == "HEAD")
            return
        if path.startswith("/static/") or path.startswith("/vendor/"):
            # /static/ is an alias for the web root; /vendor/ maps to /web/vendor.
            rel = path.removeprefix("/static/") if path.startswith("/static/") else path.removeprefix("/")
            # Reject any traversal attempts before resolving.
            if ".." in rel.split("/"):
                self._send_json({"detail": "Страница не найдена"}, 404, head=method == "HEAD")
                return
            file_path = (WEB / rel).resolve()
            if WEB.resolve() not in file_path.parents and file_path != WEB.resolve():
                self._send_json({"detail": "Страница не найдена"}, 404, head=method == "HEAD")
                return
            if not file_path.is_file():
                self._send_json({"detail": "Страница не найдена"}, 404, head=method == "HEAD")
                return
            content_type = {
                ".css": "text/css; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".html": "text/html; charset=utf-8",
                ".svg": "image/svg+xml",
                ".map": "application/json",
            }.get(file_path.suffix, "application/octet-stream")
            self._send_file(file_path, content_type, method)
            return
        self._send_json({"detail": "Страница не найдена"}, 404, head=method == "HEAD")

    def _route_post(self) -> None:
        if not self._origin_ok("POST"):
            self._send_json({"detail": "Некорректный запрос"}, 403)
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if (self.headers.get("Transfer-Encoding") or "").strip():
            self._send_json({"detail": "Некорректный запрос"}, 400)
            return
        length = parse_content_length(self.headers.get("Content-Length"))
        if length is None:
            self._send_json({"detail": "Некорректный запрос"}, 400)
            return
        max_len = {
            "/api/teacher/import": 8_000_000,
            "/api/teacher/restore.json": 8_000_000,
            "/api/teacher/restore.sqlite3": 32_000_000,
            "/api/check": 96_000,
            "/api/teacher/login": 8_192,
            "/api/student/session": 8_192,
            "/api/exam": 8_192,
        }.get(path, 8_192)
        if length > max_len:
            self._send_json({"detail": "Слишком большой запрос"}, 413)
            return
        raw = self.rfile.read(length) if length else b""
        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if path == "/api/teacher/restore.sqlite3":
            allowed_type = content_type in {"", "application/octet-stream", "application/vnd.sqlite3"}
        else:
            allowed_type = content_type in {"", "application/json"}
        if path not in {"/api/teacher/logout", "/api/student/logout"} and not allowed_type:
            if length:
                self._send_json({"detail": "Некорректный запрос"}, 400)
                return

        if path == "/api/teacher/login":
            if not _RATE.allow(f"login:{self._client_ip()}", self._cfg().login_limit):
                bump("http_429")
                self._send_json({"detail": "Слишком много попыток входа. Подожди минуту."}, 429)
                return
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
                pin = payload.get("pin", "")
            except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                self._send_json({"detail": "Некорректный запрос"}, 400)
                return
            if not isinstance(pin, str) or not _pin_ok(pin):
                self._send_json({"detail": "Неверный пин"}, 403)
                return
            session = create_teacher_session(_fingerprint(), self._cfg().session_hours)
            self._send_json(
                {"ok": True, "csrf": session["csrf"]},
                cookies=[
                    ("teacher", session["token"], True),
                    ("teacher_csrf", session["csrf"], False),
                ],
            )
            return

        if path == "/api/teacher/logout":
            token = self._cookies().get("teacher", "")
            if token:
                revoke_teacher_session(token)
            self._send_json(
                {"ok": True},
                cookies=[("teacher", "", True), ("teacher_csrf", "", False)],
                cookie_age=0,
            )
            return

        if path == "/api/student/session":
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
                raw_name = payload.get("student", "")
            except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                self._send_json({"detail": "Некорректный запрос"}, 400)
                return
            if not isinstance(raw_name, str) or not raw_name.strip():
                self._send_json({"detail": "Напиши своё имя сверху, чтобы учитель увидел работу."}, 400)
                return
            session = create_student_session(raw_name, self._cfg().session_hours)
            self._send_json(
                {"ok": True, "student": session["student"], "csrf": session["csrf"]},
                cookies=[
                    ("student", session["token"], True),
                    ("student_csrf", session["csrf"], False),
                ],
            )
            return

        if path == "/api/student/logout":
            token = self._cookies().get("student", "")
            if token:
                revoke_student_session(token)
            self._send_json(
                {"ok": True},
                cookies=[("student", "", True), ("student_csrf", "", False)],
                cookie_age=0,
            )
            return

        if path == "/api/teacher/import":
            teacher = self._teacher()
            if not teacher:
                self._send_json({"detail": "Нужен вход учителя"}, 401)
                return
            if not self._csrf_ok(teacher["csrf_hash"]):
                self._send_json({"detail": "Нужен вход учителя"}, 403)
                return
            try:
                payload = json.loads(raw.decode("utf-8"))
                kind = payload.get("format", "csv")
                text = payload.get("text", "")
            except (json.JSONDecodeError, TypeError, UnicodeDecodeError):
                self._send_json({"detail": "Некорректный запрос"}, 400)
                return
            if not isinstance(text, str) or not isinstance(kind, str):
                self._send_json({"detail": "Некорректный запрос"}, 400)
                return
            result = import_journal(text, kind)
            self._send_json({"ok": True, **result})
            return

        if path == "/api/teacher/restore.json":
            teacher = self._teacher()
            if not teacher:
                self._send_json({"detail": "Нужен вход учителя"}, 401)
                return
            if not self._csrf_ok(teacher["csrf_hash"]):
                self._send_json({"detail": "Нужен вход учителя"}, 403)
                return
            try:
                payload = json.loads(raw.decode("utf-8"))
                result = restore_backup_json(payload)
            except (json.JSONDecodeError, TypeError, UnicodeDecodeError, ValueError):
                self._send_json({"detail": "Некорректный журнал"}, 400)
                return
            self._send_json({"ok": True, **result})
            return

        if path == "/api/teacher/restore.sqlite3":
            teacher = self._teacher()
            if not teacher:
                self._send_json({"detail": "Нужен вход учителя"}, 401)
                return
            if not self._csrf_ok(teacher["csrf_hash"]):
                self._send_json({"detail": "Нужен вход учителя"}, 403)
                return
            tmp = ROOT / "data" / f"restore-{self.request_id}.sqlite3"
            try:
                tmp.write_bytes(raw)
                restore_sqlite(tmp)
            except Exception:
                traceback.print_exc()
                self._send_json({"detail": "Не удалось восстановить базу"}, 400)
                return
            finally:
                tmp.unlink(missing_ok=True)
            self._send_json({"ok": True})
            return

        if path in {"/api/teacher/export.csv", "/api/teacher/export.json", "/api/teacher/backup.sqlite3", "/api/teacher/backup.json"}:
            teacher = self._teacher()
            if not teacher:
                self._send_json({"detail": "Нужен вход учителя"}, 401)
                return
            if not self._csrf_ok(teacher["csrf_hash"]):
                self._send_json({"detail": "Нужен вход учителя"}, 403)
                return
            if path.endswith("export.csv"):
                body = export_csv().encode("utf-8")
                self._send_bytes(body, "text/csv; charset=utf-8", "attempts.csv")
                return
            if path.endswith("export.json") or path.endswith("backup.json"):
                payload = export_backup_json() if path.endswith("backup.json") else export_attempts(include_code=path.endswith("backup.json"))
                if path.endswith("export.json"):
                    payload = export_attempts(include_code=False)
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                name = "backup.json" if path.endswith("backup.json") else "attempts.json"
                self._send_bytes(body, "application/json; charset=utf-8", name)
                return
            tmp = ROOT / "data" / f"backup-{self.request_id}.sqlite3"
            try:
                sqlite_backup(tmp)
                body = tmp.read_bytes()
            finally:
                tmp.unlink(missing_ok=True)
            self._send_bytes(body, "application/vnd.sqlite3", "checker.sqlite3")
            return

        if path == "/api/exam":
            if not _RATE.allow(f"exam:{self._client_ip()}", self._cfg().exam_limit):
                bump("http_429")
                self._send_json({"detail": "Слишком много запросов. Подожди минуту."}, 429)
                return
            session = self._student()
            if not session:
                self._send_json({"detail": "Напиши своё имя сверху, чтобы учитель увидел работу."}, 401)
                return
            if not self._csrf_ok(session["csrf_hash"]):
                self._send_json({"detail": "Обнови страницу и попробуй ещё раз."}, 403)
                return
            try:
                payload = json.loads(raw.decode("utf-8") or "{}")
                action = str(payload.get("action", "")).strip()
            except (json.JSONDecodeError, TypeError, UnicodeDecodeError, AttributeError):
                self._send_json({"detail": "Некорректный запрос"}, 400)
                return
            if action == "start":
                topic = payload.get("topic", "")
                if not isinstance(topic, str) or not topic.strip():
                    self._send_json({"detail": "Выбери тему"}, 400)
                    return
                self._send_json(start_exam(session["student"], topic.strip(), student_id=session["student_id"]))
                return
            if action in {"progress", "finish", "leave", "skip"}:
                status = {"progress": "live", "finish": "done", "leave": "left", "skip": "live"}[action]
                exam = update_exam(
                    session["student"],
                    status=status,
                    student_id=session["student_id"],
                    skip_problem=str(payload.get("problem_id") or "") if action == "skip" else None,
                )
                if not exam:
                    self._send_json({"detail": "Экзамен не начат"}, 404)
                    return
                self._send_json(exam)
                return
            self._send_json({"detail": "Некорректный запрос"}, 400)
            return

        if path != "/api/check":
            self._send_json({"detail": "Страница не найдена"}, 404)
            return
        if not _RATE.allow(self._client_ip(), self._cfg().rate_limit):
            bump("http_429")
            self._send_json({"detail": "Слишком много попыток. Подожди минуту."}, 429)
            return
        session = self._student()
        if not session:
            self._send_json({"detail": "Напиши своё имя сверху, чтобы учитель увидел работу."}, 401)
            return
        if not self._csrf_ok(session["csrf_hash"]):
            self._send_json({"detail": "Обнови страницу и попробуй ещё раз."}, 403)
            return
        if not _RATE.allow(f"name:{session['student'].casefold()}", self._cfg().name_limit):
            bump("http_429")
            self._send_json({"detail": "Слишком много попыток с этим именем. Подожди минуту."}, 429)
            return
        try:
            payload = json.loads(raw.decode("utf-8"))
            problem_id = payload["problem_id"]
            code = payload.get("code", "")
            if not isinstance(code, str) or len(code) > 80_000:
                raise ValueError("bad code")
            problem = get_problem(problem_id)
            tries = problem_attempt_count(session["student"], problem_id, student_id=session["student_id"]) + 1
            acquired = _gate().acquire(timeout=self._cfg().grade_queue_timeout)
            if not acquired:
                bump("http_503")
                self._send_json({"detail": "Проверяльщик сейчас занят. Подожди несколько секунд."}, 503)
                return
            try:
                result = grade_solution(problem, code)
            finally:
                _gate().release()
            deepen_explanation(problem, result, tries)
        except KeyError:
            self._send_json({"detail": "Задача не найдена"}, 404)
            return
        except RunnerError:
            bump("runner_fail")
            bump("http_503")
            self._send_json({"detail": "Проверяльщик временно недоступен. Попробуй ещё раз через минуту."}, 503)
            return
        except (json.JSONDecodeError, TypeError, ValueError, UnicodeDecodeError):
            self._send_json({"detail": "Некорректный запрос"}, 400)
            return
        except Exception:
            traceback.print_exc()
            self._send_json({"detail": "Проверяльщик не смог запустить эту программу. Попробуй ещё раз."}, 500)
            return
        try:
            record_attempt(
                student=session["student"],
                problem_id=problem_id,
                status=result.status,
                passed=result.passed,
                total=result.total,
                message=result.message,
                code=code,
                student_id=session["student_id"],
                student_session_id=session["session_id"],
            )
        except Exception:
            traceback.print_exc()
            bump("store_fail")
            bump("http_503")
            self._send_json({"detail": "Решение проверено, но журнал не записался. Попробуй ещё раз."}, 503)
            return
        bump("grade_ok" if result.status == "ok" else "grade_fail")
        payload_out = result.to_dict()
        payload_out["student"] = session["student"]
        if result.status == "ok":
            update_exam(session["student"], student_id=session["student_id"], status="live")
        self._send_json(payload_out)

    def _ready(self) -> tuple[bool, str]:
        try:
            init_store()
            list_summaries()
            probe_write()
            cfg = self._cfg()
            if cfg.is_production and cfg.runner_kind == "judge0":
                from checker.judge0 import Judge0Runner

                ok, detail = Judge0Runner(cfg).ready()
                if not ok:
                    return False, detail
            usage = shutil.disk_usage(str(cfg.db_path.parent))
            if usage.free < cfg.disk_free_mb * 1024 * 1024:
                return False, "Мало места на диске"
        except Exception:
            return False, "Сервис не готов"
        return True, "ok"

    def _send_json(
        self,
        payload: dict | list,
        status: int = 200,
        cookie: tuple[str, str] | None = None,
        cookies: list[tuple[str, str, bool]] | None = None,
        cookie_age: int | None = None,
        head: bool = False,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._headers_sent = True
        self._security_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        age = cookie_age if cookie_age is not None else 60 * 60 * self._cfg().session_hours
        items = list(cookies or [])
        if cookie is not None:
            items.append((cookie[0], cookie[1], True))
        for name, value, httponly in items:
            self._set_cookie(name, value, age, httponly=httponly)
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _send_bytes(self, body: bytes, content_type: str, filename: str) -> None:
        self.send_response(200)
        self._headers_sent = True
        self._security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str, method: str = "GET") -> None:
        data = path.read_bytes()
        self.send_response(200)
        self._headers_sent = True
        self._security_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if method != "HEAD":
            self.wfile.write(data)


def main() -> None:
    reset_config()
    cfg = get_config()
    if cfg.is_production:
        cfg.require_teacher_secret()
        cfg.require_runner()
    init_store()
    server = BoundedThreadingHTTPServer((cfg.host, cfg.port), Handler, cfg.http_threads)
    print(f"Проверяльщик: http://{cfg.host}:{cfg.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
