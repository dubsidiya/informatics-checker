from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from checker.runner import clip_output, cpu_limit, normalize_stdin, parse_traceback

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

LIMIT_WRAPPER = """\
import os
import sys

try:
    import resource
    cpu = int(sys.argv[1])
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2_000_000, 2_000_000))
    resource.setrlimit(resource.RLIMIT_NPROC, (8, 8))
    try:
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    except (ValueError, OSError):
        pass
except Exception:
    pass
os.execv(sys.executable, [sys.executable, "-I", sys.argv[2]])
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
        shutil.copyfile(src, work / "9.txt")
        shutil.copyfile(src, work / (src.stem + ".txt"))
        canonical = src.name
    return canonical


def _kill_group(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except ProcessLookupError:
        return
    except OSError:
        try:
            proc.kill()
        except OSError:
            return


def _run_command(command: list[str], stdin: str, timeout: float, cwd: str) -> RunResult:
    kwargs: dict = {
        "input": stdin.encode("utf-8"),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "cwd": cwd,
        "env": LIMITED_ENV,
    }
    if os.name == "posix":
        kwargs["start_new_session"] = True
    try:
        completed = subprocess.run(command, timeout=timeout, **kwargs)
        stdout = clip_output(completed.stdout.decode("utf-8", errors="replace"))
        stderr = clip_output(completed.stderr.decode("utf-8", errors="replace"))
        error_type, error_line, error_message = parse_traceback(stderr)
        return RunResult(
            stdout=stdout,
            stderr=stderr,
            returncode=completed.returncode,
            timed_out=False,
            error_type=error_type,
            error_line=error_line,
            error_message=error_message,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return RunResult(
            stdout=clip_output(stdout),
            stderr=clip_output(stderr),
            returncode=-1,
            timed_out=True,
            error_type="TimeoutError",
            error_message="Программа не уложилась во время — возможно, бесконечный цикл или слишком тяжёлый перебор.",
        )


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
        wrapper = work / "_limits.py"
        wrapper.write_text(LIMIT_WRAPPER, encoding="utf-8")
        canonical = _prepare_files(work, files or [])
        if canonical:
            (work / "_launcher.py").write_text(LAUNCHER.format(canonical=canonical), encoding="utf-8")
            target = str(work / "_launcher.py")
        else:
            target = str(student)
        command = [sys.executable, str(wrapper), str(cpu_limit(timeout)), target]
        return _run_command(command, normalize_stdin(stdin), timeout, str(work))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def run_trace(source: str, stdin: str, timeout: float = 1.5, files: list[str] | None = None) -> list[dict]:
    if files:
        return []
    work = Path(tempfile.mkdtemp(prefix="trc_"))
    try:
        student = work / "student.py"
        student.write_text(source if source.endswith("\n") else source + "\n", encoding="utf-8")
        wrapper = work / "_limits.py"
        wrapper.write_text(LIMIT_WRAPPER, encoding="utf-8")
        command = [sys.executable, str(wrapper), str(cpu_limit(timeout)), str(TRACER)]
        completed = _run_command(command, normalize_stdin(stdin), timeout, str(work))
        if completed.returncode != 0 or completed.timed_out:
            return []
        try:
            payload = json.loads(completed.stdout or "[]")
        except json.JSONDecodeError:
            return []
        return payload if isinstance(payload, list) else []
    finally:
        shutil.rmtree(work, ignore_errors=True)
