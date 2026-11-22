from __future__ import annotations

import os
from typing import Sequence

from checker.runner import ExecutionRequest, ExecutionResult, Runner
from checker.sandbox import run_student, run_trace


class LocalRunner:
    """Run each case in its own sandboxed interpreter.

    Production grades one case at a time to keep one request cheap. The test
    suite grades thousands of reference solutions and mutants, so it sets
    ``CHECKER_RUNNER_PARALLEL`` to use a small pool; results keep their order.
    """

    def __init__(self, workers: int | None = None) -> None:
        if workers is None:
            try:
                workers = int(os.environ.get("CHECKER_RUNNER_PARALLEL", "0") or 0)
            except ValueError:
                workers = 0
        self.workers = max(0, workers)

    def run_many(self, requests: Sequence[ExecutionRequest]) -> list[ExecutionResult]:
        if self.workers > 1 and len(requests) > 1:
            return self._run_parallel(requests)
        return self._run_serial(requests)

    def _run_parallel(self, requests: Sequence[ExecutionRequest]) -> list[ExecutionResult]:
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=min(self.workers, len(requests))) as pool:
            return list(pool.map(self._run_one, requests))

    def _run_one(self, item: ExecutionRequest) -> ExecutionResult:
        raw = run_student(
            item.source,
            item.stdin,
            timeout=item.timeout_seconds,
            files=list(item.files),
        )
        return ExecutionResult(
            stdout=raw.stdout,
            stderr=raw.stderr,
            returncode=raw.returncode,
            timed_out=raw.timed_out,
            error_type=raw.error_type,
            error_line=raw.error_line,
            error_message=raw.error_message,
        )

    def _run_serial(self, requests: Sequence[ExecutionRequest]) -> list[ExecutionResult]:
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
            result = self._run_one(item)
            results.append(result)
            if result.timed_out:
                stop = True
        return results

    def trace(self, request: ExecutionRequest) -> list[dict]:
        if request.files:
            return []
        return run_trace(request.source, request.stdin, timeout=min(1.5, request.timeout_seconds))


def default_local_runner() -> Runner:
    return LocalRunner()
