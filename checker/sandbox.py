from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TRACER = ROOT / "tracer.py"

LIMITED_ENV = {
    "PATH": str(Path(sys.executable).parent),
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUNBUFFERED": "1",
    "HOME": tempfile.gettempdir(),
    "TMPDIR": tempfile.gettempdir(),
}


@dataclass
class RunResult:
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool
    error_type: str = ""
    error_line: int | None = None
    error_message: str = ""


def _apply_limits() -> None:
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
        resource.setrlimit(resource.RLIMIT_FSIZE, (2_000_000, 2_000_000))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        try:
            resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        except (ValueError, OSError):
            pass
    except Exception:
        return


def _write_source(source: str) -> str:
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix="student_",
        delete=False,
        encoding="utf-8",
    )
    with handle:
        handle.write(source)
        if not source.endswith("\n"):
            handle.write("\n")
    return handle.name


def run_student(
    source: str,
    stdin: str,
    timeout: float = 1.5,
) -> RunResult:
    path = _write_source(source)
    try:
        completed = subprocess.run(
            [sys.executable, "-I", path],
            input=stdin if stdin.endswith("\n") or stdin == "" else stdin + "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=LIMITED_ENV,
            cwd=tempfile.gettempdir(),
            preexec_fn=_apply_limits if os.name == "posix" else None,
        )
        error_type, error_line, error_message = parse_traceback(completed.stderr)
        return RunResult(
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
            timed_out=False,
            error_type=error_type,
            error_line=error_line,
            error_message=error_message,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return RunResult(
            stdout=stdout,
            stderr=stderr,
            returncode=-1,
            timed_out=True,
            error_type="TimeoutError",
            error_message="Программа не уложилась в 1.5 секунды — возможно, бесконечный цикл.",
        )
    finally:
        Path(path).unlink(missing_ok=True)


def run_trace(source: str, stdin: str, timeout: float = 1.5) -> list[dict]:
    path = _write_source(source)
    try:
        completed = subprocess.run(
            [sys.executable, "-I", str(TRACER), path],
            input=stdin if stdin.endswith("\n") or stdin == "" else stdin + "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=LIMITED_ENV,
            cwd=tempfile.gettempdir(),
            preexec_fn=_apply_limits if os.name == "posix" else None,
        )
        if completed.returncode != 0:
            return []
        try:
            payload = json.loads(completed.stdout or "[]")
        except json.JSONDecodeError:
            return []
        if isinstance(payload, list):
            return payload
        return []
    except subprocess.TimeoutExpired:
        return []
    finally:
        Path(path).unlink(missing_ok=True)


def parse_traceback(stderr: str) -> tuple[str, int | None, str]:
    if not stderr.strip():
        return "", None, ""

    lines = [line.rstrip("\n") for line in stderr.splitlines()]
    error_type = ""
    error_line: int | None = None
    message = ""

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("File ") and ", line " in stripped:
            try:
                after = stripped.split(", line ", 1)[1]
                number = after.split(",", 1)[0].split()[0]
                error_line = int(number)
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
    return error_type, error_line, message
