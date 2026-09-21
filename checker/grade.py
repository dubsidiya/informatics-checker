from __future__ import annotations

from checker.explain import attach_explanation
from checker.logic import build_hints, same_answer, to_trace_steps
from checker.models import GradeResult, Problem, TestResult
from checker.runner import ExecutionRequest, RunnerError, get_runner
from checker.safety import find_forbidden
from checker.syntax import explain_syntax


def grade_solution(problem: Problem, source: str, *, runner=None) -> GradeResult:
    source = source.replace("\r\n", "\n")
    if not source.strip():
        return attach_explanation(
            problem,
            GradeResult(
                status="syntax",
                message="Пустой файл: напиши программу и нажми «Проверить».",
                passed=0,
                total=len(problem.tests),
            ),
            source,
        )

    syntax = explain_syntax(source)
    if syntax:
        return attach_explanation(
            problem,
            GradeResult(
                status="syntax",
                message="Синтаксическая ошибка: программа даже не запустилась.",
                passed=0,
                total=len(problem.tests),
                syntax=syntax,
            ),
            source,
        )

    allow_open = bool(problem.files) or any(case.file for case in problem.tests)
    blocked = find_forbidden(source, allow_open=allow_open)
    if blocked:
        return attach_explanation(
            problem,
            GradeResult(
                status="syntax",
                message="Программа отклонена: есть запрещённые конструкции.",
                passed=0,
                total=len(problem.tests),
                syntax=blocked,
            ),
            source,
        )

    active = runner or get_runner()
    requests = []
    for case in problem.tests:
        files = tuple(problem.files_for(case))
        timeout = 4.0 if files else 1.5
        if any(tag in problem.tags for tag in ("ege8", "ege16", "ege23", "ege25")):
            timeout = max(timeout, 3.0)
        if "ege9" in problem.tags:
            timeout = max(timeout, 4.0)
        requests.append(
            ExecutionRequest(
                source=source,
                stdin=case.stdin,
                timeout_seconds=timeout,
                files=files,
            )
        )
    runs = active.run_many(requests)
    if len(runs) != len(problem.tests):
        raise RunnerError("Проверяющая система вернула неполный набор тестов.")

    tests = []
    for index, (case, run) in enumerate(zip(problem.tests, runs)):
        files = problem.files_for(case)
        shown_in = f"[файл {files[0].rsplit('/', 1)[-1]}]" if files else case.stdin
        if run.timed_out:
            tests.append(
                TestResult(
                    index=index,
                    hidden=case.hidden,
                    verdict="TLE",
                    stdin=shown_in,
                    expected=case.stdout,
                    got=run.stdout,
                    error=run.error_message,
                    error_type="TimeoutError",
                )
            )
            continue
        if run.returncode != 0:
            tests.append(
                TestResult(
                    index=index,
                    hidden=case.hidden,
                    verdict="RE",
                    stdin=shown_in,
                    expected=case.stdout,
                    got=run.stdout,
                    error=run.error_message or run.stderr.strip(),
                    error_type=run.error_type or "RuntimeError",
                    error_line=run.error_line,
                )
            )
            continue
        verdict = "OK" if same_answer(run.stdout, case.stdout) else "WA"
        tests.append(
            TestResult(
                index=index,
                hidden=case.hidden,
                verdict=verdict,
                stdin=shown_in,
                expected=case.stdout,
                got=run.stdout,
            )
        )
    passed = sum(1 for item in tests if item.verdict == "OK")
    first_fail = next((item for item in tests if item.verdict != "OK"), None)

    if first_fail is None:
        return attach_explanation(
            problem,
            GradeResult(
                status="ok",
                message="Все тесты пройдены. Решение принимается.",
                passed=passed,
                total=len(tests),
                tests=tests,
            ),
            source,
        )

    hint_tests = _student_hint_tests(tests)
    hints = build_hints(source, problem, hint_tests)
    trace = []
    if first_fail.verdict in {"WA", "RE"} and not first_fail.hidden:
        fail_case = problem.tests[first_fail.index]
        fail_files = problem.files_for(fail_case)
        if not fail_files:
            try:
                events = active.trace(
                    ExecutionRequest(
                        source=source,
                        stdin=first_fail.stdin,
                        timeout_seconds=1.5,
                    )
                )
            except RunnerError:
                events = []
            trace = to_trace_steps(events)

    if first_fail.verdict == "RE":
        message = f"Программа упала на тесте {first_fail.index + 1}."
    elif first_fail.verdict == "TLE":
        message = f"Тест {first_fail.index + 1} не уложился во время."
    else:
        message = f"Неверный ответ на тесте {first_fail.index + 1}."

    return attach_explanation(
        problem,
        GradeResult(
            status="fail",
            message=message,
            passed=passed,
            total=len(tests),
            tests=tests,
            hints=hints,
            trace=trace,
            first_fail_index=first_fail.index,
        ),
        source,
    )


def _student_hint_tests(tests: list[TestResult]) -> list[TestResult]:
    cleaned: list[TestResult] = []
    for item in tests:
        if not item.hidden:
            cleaned.append(item)
            continue
        cleaned.append(
            TestResult(
                index=item.index,
                hidden=True,
                verdict=item.verdict,
                stdin="",
                expected="",
                got="" if not (item.got or "").strip() else "[скрытый вывод]",
                error="",
                error_type=item.error_type if item.verdict == "RE" else "",
                error_line=item.error_line if item.verdict == "RE" else None,
            )
        )
    return cleaned
