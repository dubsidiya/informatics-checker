from __future__ import annotations

from checker.models import Problem
from checker.problems import all_problems


class CatalogError(RuntimeError):
    pass


def _norm(text: str) -> str:
    return " ".join((text or "").split())


def validate_problem(problem: Problem) -> list[str]:
    errors: list[str] = []
    if not problem.tests:
        errors.append(f"{problem.id}: нет тестов")
        return errors
    hidden = [case for case in problem.tests if case.hidden]
    examples = {(_norm(item.stdin), _norm(item.stdout)) for item in problem.examples}
    if len(problem.tests) == 1 and problem.tests[0].hidden:
        oracle = (_norm(problem.tests[0].stdin), _norm(problem.tests[0].stdout))
        if oracle in examples and oracle[1]:
            errors.append(f"{problem.id}: единственный скрытый oracle совпадает с публичным примером")
    for item in problem.examples:
        for case in hidden:
            if _norm(item.stdout) and _norm(item.stdout) == _norm(case.stdout) and _norm(item.stdin) == _norm(case.stdin):
                if len(problem.tests) == 1:
                    errors.append(f"{problem.id}: пример повторяет единственный скрытый тест")
    return errors


def validate_catalog(problems: list[Problem] | None = None) -> list[str]:
    items = problems if problems is not None else all_problems()
    errors: list[str] = []
    for problem in items:
        errors.extend(validate_problem(problem))
    return errors


def main() -> None:
    errors = validate_catalog()
    if errors:
        raise SystemExit("\n".join(errors))
    print("catalog ok", len(all_problems()))


if __name__ == "__main__":
    main()
