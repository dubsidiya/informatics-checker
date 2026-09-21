from __future__ import annotations

import base64
import io
import json
import ssl
import time
import urllib.error
import urllib.request
import zipfile
from typing import Any, Sequence
from urllib.parse import urlencode

from checker.config import Config, get_config
from checker.runner import (
    MAX_FILE_KIB,
    MAX_MEMORY_KIB,
    MAX_PROCESSES,
    ExecutionRequest,
    ExecutionResult,
    RunnerError,
    clip_output,
    cpu_limit,
    normalize_stdin,
    parse_traceback,
)
from checker.sandbox import DATA_ROOT, LAUNCHER, TRACER

STATUS_IN_QUEUE = 1
STATUS_PROCESSING = 2
STATUS_ACCEPTED = 3
STATUS_WRONG_ANSWER = 4
STATUS_TLE = 5
STATUS_COMPILATION = 6
STATUS_RE_SIG = 7
STATUS_RE_NZ = 8
STATUS_RE_OTHER = 9
STATUS_RE_INTERNAL = 10
STATUS_RE_EXEC_FORMAT = 11
STATUS_RE_RESTRICTED = 12
STATUS_INTERNAL = 13
STATUS_EXEC_FORMAT = 14


class Judge0Runner:
    def __init__(self, cfg: Config | None = None, opener=None):
        self.cfg = cfg or get_config()
        self._opener = opener

    def run_many(self, requests: Sequence[ExecutionRequest]) -> list[ExecutionResult]:
        if not requests:
            return []
        if len(requests) > 6:
            raise RunnerError("Слишком много тестов в одном запуске.")
        payload = [self._submission(item) for item in requests]
        tokens = self._create_batch(payload)
        raw = self._poll_batch(tokens)
        return [self._to_result(item) for item in raw]

    def trace(self, request: ExecutionRequest) -> list[dict]:
        if request.files:
            return []
        tracer = TRACER.read_text(encoding="utf-8")
        archive = _zip_bytes(
            {
                "student.py": (
                    request.source if request.source.endswith("\n") else request.source + "\n"
                ).encode("utf-8")
            }
        )
        submission = self._base_submission(
            tracer,
            request.stdin,
            min(1.5, request.timeout_seconds),
            additional_files=archive,
        )
        tokens = self._create_batch([submission])
        raw = self._poll_batch(tokens)
        result = self._to_result(raw[0])
        if result.timed_out or result.returncode != 0:
            return []
        try:
            payload = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            return []
        return payload if isinstance(payload, list) else []

    def ready(self) -> tuple[bool, str]:
        try:
            info = self._request("GET", f"/languages/{self.cfg.judge0_language_id}")
        except RunnerError as exc:
            return False, str(exc)
        name = str(info.get("name") or "")
        if self.cfg.judge0_language_name and name and name != self.cfg.judge0_language_name:
            return False, f"Ожидали {self.cfg.judge0_language_name}, получили {name}."
        return True, name or "ok"

    def _submission(self, item: ExecutionRequest) -> dict[str, Any]:
        source = item.source if item.source.endswith("\n") else item.source + "\n"
        extra: dict[str, bytes] = {}
        code = source
        if item.files:
            names = _fixture_names(item.files)
            extra["student.py"] = source.encode("utf-8")
            extra.update(names)
            code = LAUNCHER.format(canonical=next(iter(names)))
        archive = _zip_bytes(extra) if extra else None
        return self._base_submission(code, item.stdin, item.timeout_seconds, additional_files=archive)

    def _base_submission(
        self,
        source: str,
        stdin: str,
        timeout: float,
        additional_files: bytes | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "language_id": self.cfg.judge0_language_id,
            "source_code": _b64(source),
            "stdin": _b64(normalize_stdin(stdin)),
            "cpu_time_limit": cpu_limit(timeout),
            "cpu_extra_time": 0,
            "wall_time_limit": max(1.0, float(timeout)),
            "memory_limit": MAX_MEMORY_KIB,
            "max_processes_and_or_threads": MAX_PROCESSES,
            "enable_per_process_and_thread_time_limit": False,
            "enable_per_process_and_thread_memory_limit": False,
            "max_file_size": MAX_FILE_KIB,
            "redirect_stderr_to_stdout": False,
            "enable_network": False,
            "number_of_runs": 1,
        }
        if additional_files:
            body["additional_files"] = base64.b64encode(additional_files).decode("ascii")
        return body

    def _create_batch(self, submissions: list[dict[str, Any]]) -> list[str]:
        data = self._request("POST", "/submissions/batch?base64_encoded=true", {"submissions": submissions})
        items = data if isinstance(data, list) else data.get("submissions") if isinstance(data, dict) else None
        if not isinstance(items, list) or len(items) != len(submissions):
            raise RunnerError("Проверяющая система неверно приняла пачку тестов.")
        tokens = []
        for item in items:
            token = (item or {}).get("token")
            if not token:
                raise RunnerError("Проверяющая система не выдала token.")
            tokens.append(str(token))
        return tokens

    def _poll_batch(self, tokens: list[str]) -> list[dict[str, Any]]:
        deadline = time.monotonic() + self.cfg.judge0_result_timeout
        query = urlencode(
            {
                "tokens": ",".join(tokens),
                "base64_encoded": "true",
                "fields": "token,stdout,stderr,compile_output,message,exit_code,exit_signal,status_id",
            }
        )
        last: list[dict[str, Any]] | None = None
        while time.monotonic() < deadline:
            data = self._request("GET", f"/submissions/batch?{query}")
            rows = data.get("submissions") if isinstance(data, dict) else data
            if not isinstance(rows, list) or len(rows) != len(tokens):
                raise RunnerError("Проверяющая система неверно вернула результаты.")
            last = [item or {} for item in rows]
            if all(int(item.get("status_id") or 0) not in {STATUS_IN_QUEUE, STATUS_PROCESSING, 0} for item in last):
                return last
            time.sleep(self.cfg.judge0_poll_interval)
        raise RunnerError("Истёк срок ожидания проверяющей системы.")

    def _to_result(self, item: dict[str, Any]) -> ExecutionResult:
        status = int(item.get("status_id") or 0)
        stdout = clip_output(_decode_field(item.get("stdout")))
        stderr = clip_output(
            _decode_field(item.get("stderr"))
            or _decode_field(item.get("compile_output"))
            or _decode_field(item.get("message"))
        )
        if status in {STATUS_IN_QUEUE, STATUS_PROCESSING}:
            raise RunnerError("Проверяющая система не завершила работу.")
        if status in {STATUS_COMPILATION, STATUS_INTERNAL, STATUS_EXEC_FORMAT} or status not in {
            STATUS_ACCEPTED,
            STATUS_WRONG_ANSWER,
            STATUS_TLE,
            STATUS_RE_SIG,
            STATUS_RE_NZ,
            STATUS_RE_OTHER,
            STATUS_RE_INTERNAL,
            STATUS_RE_EXEC_FORMAT,
            STATUS_RE_RESTRICTED,
        }:
            raise RunnerError("Проверяющая система недоступна.")
        timed_out = status == STATUS_TLE
        returncode = int(item.get("exit_code") or (0 if status in {STATUS_ACCEPTED, STATUS_WRONG_ANSWER} else -1))
        if timed_out:
            returncode = -1
        error_type, error_line, error_message = parse_traceback(stderr)
        if timed_out:
            error_type = "TimeoutError"
            error_message = "Программа не уложилась во время."
        return ExecutionResult(
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
            timed_out=timed_out,
            error_type=error_type,
            error_line=error_line,
            error_message=error_message,
        )

    def _request(self, method: str, path: str, payload: dict | None = None) -> Any:
        url = self.cfg.judge0_url
        if not url:
            raise RunnerError("Не задан JUDGE0_URL.")
        if url.startswith("http://") and self.cfg.is_production:
            raise RunnerError("JUDGE0_URL должен быть HTTPS.")
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {
            "Accept": "application/json",
            self.cfg.judge0_auth_header: self.cfg.judge0_auth_token,
        }
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url + path, data=body, headers=headers, method=method)
        try:
            if self._opener:
                with self._opener.open(req, timeout=self.cfg.judge0_http_timeout) as resp:
                    raw = resp.read()
                    status = getattr(resp, "status", 200)
            else:
                context = ssl.create_default_context()
                with urllib.request.urlopen(req, timeout=self.cfg.judge0_http_timeout, context=context) as resp:
                    raw = resp.read()
                    status = getattr(resp, "status", 200)
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise RunnerError("Нет доступа к проверяющей системе.") from exc
            if exc.code in {429, 503}:
                raise RunnerError("Сервис проверки перегружен.") from exc
            if exc.code in {400, 422}:
                raise RunnerError("Некорректный запрос к проверяющей системе.") from exc
            raise RunnerError("Проверяющая система недоступна.") from exc
        except urllib.error.URLError as exc:
            raise RunnerError("Нет связи с проверяющим сервисом.") from exc
        if status >= 400:
            raise RunnerError("Проверяющая система недоступна.")
        try:
            return json.loads(raw.decode("utf-8") or "null")
        except json.JSONDecodeError as exc:
            raise RunnerError("Проверяющая система ответила не JSON.") from exc


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _decode_field(value: object) -> str:
    if not value:
        return ""
    raw = str(value)
    try:
        return base64.b64decode(raw).decode("utf-8", errors="replace")
    except Exception:
        return raw


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
    return buf.getvalue()


def _fixture_names(files: Sequence[str]) -> dict[str, bytes]:
    mapping: dict[str, bytes] = {}
    canonical = None
    for rel in files:
        src = (DATA_ROOT / rel).resolve()
        if DATA_ROOT.resolve() not in src.parents and src != DATA_ROOT.resolve():
            raise RunnerError("Файл задачи вне каталога data.")
        if not src.is_file():
            raise RunnerError("Файл задачи не найден.")
        data = src.read_bytes()
        mapping[src.name] = data
        mapping["17.txt"] = data
        mapping["9.txt"] = data
        mapping[src.stem + ".txt"] = data
        canonical = src.name
    if not canonical:
        raise RunnerError("У задачи нет файла.")
    return mapping
