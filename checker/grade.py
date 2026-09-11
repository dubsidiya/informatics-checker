from __future__ import annotations

from checker.logic import build_hints, same_answer, to_trace_steps
from checker.models import GradeResult, Problem, TestResult
from checker.sandbox import run_student, run_trace
from checker.safety import find_forbidden
from checker.syntax import explain_syntax


def grade_solution(problem: Problem, source: str) -> GradeResult:
    source = source.replace("\r\n", "\n")
    if not source.strip():
        return GradeResult(
            status="syntax",
            message="Пустой файл: напиши программу и нажми «Проверить».",
            passed=0,
            total=len(problem.tests),
        )

    syntax = explain_syntax(source)
    if syntax:
        return GradeResult(
            status="syntax",
            message="Синтаксическая ошибка: программа даже не запустилась.",
            passed=0,
            total=len(problem.tests),
            syntax=syntax,
        )

    blocked = find_forbidden(source)
    if blocked:
        return GradeResult(
            status="syntax",
            message="Программа отклонена: есть запрещённые конструкции.",
            passed=0,
            total=len(problem.tests),
            syntax=blocked,
        )

    tests = [_run_test(source, index, case) for index, case in enumerate(problem.tests)]
    passed = sum(1 for item in tests if item.verdict == "OK")
    first_fail = next((item for item in tests if item.verdict != "OK"), None)

    if first_fail is None:
        return GradeResult(
            status="ok",
            message="Все тесты пройдены. Решение принимается.",
            passed=passed,
            total=len(tests),
            tests=tests,
        )

    hints = build_hints(source, problem, tests)
    trace = []
    if first_fail.verdict in {"WA", "RE"}:
        trace = to_trace_steps(run_trace(source, first_fail.stdin))

    if first_fail.verdict == "RE":
        message = f"Программа упала на тесте {first_fail.index + 1}."
    elif first_fail.verdict == "TLE":
        message = f"Тест {first_fail.index + 1} не уложился во время."
    else:
        message = f"Неверный ответ на тесте {first_fail.index + 1}."

    return GradeResult(
        status="fail",
        message=message,
        passed=passed,
        total=len(tests),
        tests=tests,
        hints=hints,
        trace=trace,
        first_fail_index=first_fail.index,
    )


def _run_test(source: str, index: int, case) -> TestResult:
    result = run_student(source, case.stdin)
    if result.timed_out:
        return TestResult(
            index=index,
            hidden=case.hidden,
            verdict="TLE",
            stdin=case.stdin,
            expected=case.stdout,
            got=result.stdout,
            error=result.error_message,
            error_type="TimeoutError",
        )
    if result.returncode != 0:
        return TestResult(
            index=index,
            hidden=case.hidden,
            verdict="RE",
            stdin=case.stdin,
            expected=case.stdout,
            got=result.stdout,
            error=result.error_message or result.stderr.strip(),
            error_type=result.error_type or "RuntimeError",
            error_line=result.error_line,
        )
    verdict = "OK" if same_answer(result.stdout, case.stdout) else "WA"
    return TestResult(
        index=index,
        hidden=case.hidden,
        verdict=verdict,
        stdin=case.stdin,
        expected=case.stdout,
        got=result.stdout,
    )
