from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_ROOT = ROOT.parent / "data"
TRACER = ROOT / "tracer.py"

LIMITED_ENV = {
    "PATH": str(Path(sys.executable).parent),
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUNBUFFERED": "1",
    "HOME": tempfile.gettempdir(),
    "TMPDIR": tempfile.gettempdir(),
}

LAUNCHER = """\
import builtins
import runpy

_real_open = builtins.open
CANON = {canonical!r}

def open(file, mode="r", *args, **kwargs):
    mode = mode or "r"
    if any(flag in str(mode) for flag in "wa+"):
        raise PermissionError("запись в файл на проверяльщике запрещена")
    return _real_open(CANON, mode, *args, **kwargs)

builtins.open = open
runpy.run_path("student.py", run_name="__main__")
"""


@dataclass
class RunResult:
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool
    error_type: str = ""
    error_line: int | None = None
    error_message: str = ""


def _apply_limits(cpu_seconds: int = 2) -> None:
    try:
        import resource

        cpu = max(2, int(cpu_seconds))
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        resource.setrlimit(resource.RLIMIT_FSIZE, (2_000_000, 2_000_000))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        try:
            resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
        except (ValueError, OSError):
            pass
    except Exception:
        return


def _write_source(source: str, directory: Path | None = None) -> str:
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix="student_",
        delete=False,
        encoding="utf-8",
        dir=str(directory) if directory else None,
    )
    with handle:
        handle.write(source)
        if not source.endswith("\n"):
            handle.write("\n")
    return handle.name


def _prepare_files(work: Path, files: list[str]) -> str | None:
    canonical = None
    for rel in files:
        src = (DATA_ROOT / rel).resolve()
        if DATA_ROOT.resolve() not in src.parents and src != DATA_ROOT.resolve():
            continue
        if not src.is_file():
            continue
        dest = work / src.name
        shutil.copyfile(src, dest)
        shutil.copyfile(src, work / "17.txt")
        canonical = src.name
    return canonical


def _limits_fn(timeout: float):
    cpu = max(2, int(timeout) + 1)

    def inner() -> None:
        _apply_limits(cpu)

    return inner if os.name == "posix" else None


def run_student(
    source: str,
    stdin: str,
    timeout: float = 1.5,
    files: list[str] | None = None,
) -> RunResult:
    work = Path(tempfile.mkdtemp(prefix="chk_"))
    try:
        student = work / "student.py"
        student.write_text(source if source.endswith("\n") else source + "\n", encoding="utf-8")
        canonical = _prepare_files(work, files or [])
        if canonical:
            (work / "_launcher.py").write_text(LAUNCHER.format(canonical=canonical), encoding="utf-8")
            command = [sys.executable, "-I", str(work / "_launcher.py")]
        else:
            command = [sys.executable, "-I", str(student)]
        payload = stdin if stdin.endswith("\n") or stdin == "" else stdin + "\n"
        completed = subprocess.run(
            command,
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=LIMITED_ENV,
            cwd=str(work),
            preexec_fn=_limits_fn(timeout),
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
            error_message="Программа не уложилась во время — возможно, бесконечный цикл или слишком тяжёлый перебор.",
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_trace(source: str, stdin: str, timeout: float = 1.5, files: list[str] | None = None) -> list[dict]:
    if files:
        return []
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
            preexec_fn=_limits_fn(timeout),
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
        if stripped.startswith("File ") and ", line " in stripped and "student.py" in stripped:
            try:
                after = stripped.split(", line ", 1)[1]
                number = after.split(",", 1)[0].split()[0]
                error_line = int(number)
            except (IndexError, ValueError):
                pass
        elif stripped.startswith("File ") and ", line " in stripped and error_line is None:
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
