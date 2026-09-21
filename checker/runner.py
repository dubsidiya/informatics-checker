from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol, Sequence


MAX_OUTPUT = 80_000
MAX_MEMORY_KIB = 262_144
MAX_FILE_KIB = 1954
MAX_PROCESSES = 8


class RunnerError(Exception):
    """Infrastructure failure: do not treat as a student verdict."""


@dataclass(frozen=True)
class ExecutionRequest:
    source: str
    stdin: str
    timeout_seconds: float
    files: tuple[str, ...] = ()
    trace: bool = False


@dataclass
class ExecutionResult:
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool
    error_type: str = ""
    error_line: int | None = None
    error_message: str = ""
    events: list[dict] = field(default_factory=list)


class Runner(Protocol):
    def run_many(self, requests: Sequence[ExecutionRequest]) -> list[ExecutionResult]:
        ...

    def trace(self, request: ExecutionRequest) -> list[dict]:
        ...


def clip_output(text: str | None) -> str:
    raw = text or ""
    if len(raw) <= MAX_OUTPUT:
        return raw
    return raw[:MAX_OUTPUT] + "\n…"


def normalize_stdin(stdin: str) -> str:
    if stdin == "" or stdin.endswith("\n"):
        return stdin
    return stdin + "\n"


def cpu_limit(timeout_seconds: float) -> int:
    return max(2, int(timeout_seconds) + 1)


def parse_traceback(stderr: str) -> tuple[str, int | None, str]:
    if not (stderr or "").strip():
        return "", None, ""

    lines = [line.rstrip("\n") for line in stderr.splitlines()]
    error_type = ""
    error_line: int | None = None
    message = ""

    for line in lines:
        stripped = line.strip()
        student_hit = "student.py" in stripped or "script.py" in stripped or "/box/" in stripped
        if stripped.startswith("File ") and ", line " in stripped:
            if student_hit or error_line is None:
                try:
                    after = stripped.split(", line ", 1)[1]
                    number = after.split(",", 1)[0].split()[0]
                    parsed = int(number)
                    if student_hit or error_line is None:
                        error_line = parsed
                except (IndexError, ValueError):
                    pass
        if ":" in stripped and stripped.split(":", 1)[0].endswith("Error"):
            error_type, _, rest = stripped.partition(":")
            error_type = error_type.strip()
            message = rest.strip()
        elif stripped.endswith("Error") and " " not in stripped:
            error_type = stripped

    if not message:
        message = lines[-1].strip()
    if error_type and not re.fullmatch(r"[A-Za-z_]+Error", error_type):
        error_type = ""
    return error_type, error_line, message


_RUNNER: Runner | None = None


def get_runner() -> Runner:
    global _RUNNER
    if _RUNNER is not None:
        return _RUNNER
    from checker.config import get_config
    from checker.judge0 import Judge0Runner
    from checker.local_runner import LocalRunner

    cfg = get_config()
    if cfg.runner_kind == "local":
        _RUNNER = LocalRunner()
    else:
        _RUNNER = Judge0Runner(cfg)
    return _RUNNER


def set_runner(runner: Runner | None) -> None:
    global _RUNNER
    _RUNNER = runner
