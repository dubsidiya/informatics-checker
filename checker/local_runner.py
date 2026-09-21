from __future__ import annotations

from typing import Sequence

from checker.runner import ExecutionRequest, ExecutionResult, Runner
from checker.sandbox import run_student, run_trace


class LocalRunner:
    def run_many(self, requests: Sequence[ExecutionRequest]) -> list[ExecutionResult]:
        results: list[ExecutionResult] = []
        stop = False
        for item in requests:
            if stop:
                results.append(
                    ExecutionResult(
                        stdout="",
                        stderr="",
                        returncode=-1,
                        timed_out=True,
                        error_type="TimeoutError",
                        error_message="Проверка остановлена: предыдущий тест не уложился во время.",
                    )
                )
                continue
            raw = run_student(
                item.source,
                item.stdin,
                timeout=item.timeout_seconds,
                files=list(item.files),
            )
            results.append(
                ExecutionResult(
                    stdout=raw.stdout,
                    stderr=raw.stderr,
                    returncode=raw.returncode,
                    timed_out=raw.timed_out,
                    error_type=raw.error_type,
                    error_line=raw.error_line,
                    error_message=raw.error_message,
                )
            )
            if raw.timed_out:
                stop = True
        return results

    def trace(self, request: ExecutionRequest) -> list[dict]:
        if request.files:
            return []
        return run_trace(request.source, request.stdin, timeout=min(1.5, request.timeout_seconds))


def default_local_runner() -> Runner:
    return LocalRunner()
