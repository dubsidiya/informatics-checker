from __future__ import annotations

import ast
import re

from checker.models import Hint, Problem


def analyze_source(source: str, problem: Problem) -> list[Hint]:
    hints: list[Hint] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return hints

    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    has_input = any(_called(node, "input") for node in calls)
    has_print = any(_called(node, "print") for node in calls)
    has_int = any(_called(node, "int") for node in calls)
    has_map = any(_called(node, "map") for node in calls)
    has_split = any(
        isinstance(node.func, ast.Attribute) and node.func.attr == "split" for node in calls
    )

    if not has_print:
        hints.append(
            Hint(
                kind="logic",
                title="Нет вывода",
                detail="В программе нет print. Даже верный расчёт не увидит проверяющая система.",
            )
        )

    if not has_input and "integers_from_input" in problem.tags:
        hints.append(
            Hint(
                kind="logic",
                title="Ввод не читается",
                detail="Числа нужно брать из input(), а не записывать в код константой. Иначе тесты с другими данными провалятся.",
            )
        )

    if "integers_from_input" in problem.tags and has_input and not has_int and not has_map:
        line = _first_input_line(tree)
        hints.append(
            Hint(
                kind="logic",
                title="input() возвращает строку",
                detail="Без int(...) или map(int, ...) числа остаются текстом. Тогда 2 + 3 превращается в 23, а сравнения работают не как у чисел.",
                line=line,
            )
        )

    if _adds_raw_input(tree):
        hints.append(
            Hint(
                kind="logic",
                title="Складываются строки, не числа",
                detail="Выражение вроде input() + input() склеивает текст. Нужно сначала превратить каждое значение в int.",
                line=_first_input_line(tree),
            )
        )

    if "inclusive_n" in problem.tags:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _called(node, "range") and len(node.args) == 1:
                hints.append(
                    Hint(
                        kind="logic",
                        title="range(n) не включает n",
                        detail="range(n) даёт 0, 1, …, n-1. Для суммы от 1 до N нужен range(1, n + 1) или формула n * (n + 1) // 2.",
                        line=getattr(node, "lineno", None),
                    )
                )

    if "digits" in problem.tags and "while" not in _dump_names(tree) and not _iterates_string(tree):
        if has_int and not _has_modulo_10(tree):
            hints.append(
                Hint(
                    kind="logic",
                    title="Цифры числа не разбираются",
                    detail="Сумму цифр обычно считают циклом while n > 0: цифра = n % 10, затем n //= 10. Либо идут по строке: for digit in str(n).",
                )
            )

    if "sequence" in problem.tags and has_input and not has_split and "split" not in source:
        hints.append(
            Hint(
                kind="logic",
                title="Список, скорее всего, не разобран",
                detail="Несколько чисел в одной строке читают так: list(map(int, input().split())).",
            )
        )

    if _has_yes_no_problem(problem) and not re.search(r"YES|NO|Yes|No", source):
        hints.append(
            Hint(
                kind="format",
                title="Нужен ответ YES или NO",
                detail="Проверяющая система сравнивает вывод буква в букву. Печатай YES и NO заглавными буквами, без кавычек.",
            )
        )

    if "True" in names or any(
        isinstance(node, ast.While)
        and isinstance(node.test, ast.Constant)
        and node.test.value is True
        for node in ast.walk(tree)
    ):
        if not _has_break(tree):
            hints.append(
                Hint(
                    kind="runtime",
                    title="Возможен бесконечный цикл",
                    detail="while True без break не остановится. Проверяющая система оборвёт программу по времени.",
                )
            )

    return _unique(hints)


def _called(node: ast.Call, name: str) -> bool:
    return isinstance(node.func, ast.Name) and node.func.id == name


def _first_input_line(tree: ast.AST) -> int | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _called(node, "input"):
            return getattr(node, "lineno", None)
    return None


def _adds_raw_input(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            if _contains_raw_input(node.left) or _contains_raw_input(node.right):
                return True
    return False


def _contains_raw_input(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _called(node, "input")


def _dump_names(tree: ast.AST) -> set[str]:
    return {type(node).__name__.lower() for node in ast.walk(tree)}


def _iterates_string(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and _is_str_call(node.iter):
            return True
    return False


def _is_str_call(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "str"


def _has_modulo_10(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            if isinstance(node.right, ast.Constant) and node.right.value == 10:
                return True
    return False


def _has_break(tree: ast.AST) -> bool:
    return any(isinstance(node, ast.Break) for node in ast.walk(tree))


def _has_yes_no_problem(problem: Problem) -> bool:
    return "YES" in problem.output_format or "YES" in problem.statement


def _unique(hints: list[Hint]) -> list[Hint]:
    seen: set[tuple[str, str]] = set()
    result: list[Hint] = []
    for hint in hints:
        key = (hint.title, hint.detail)
        if key in seen:
            continue
        seen.add(key)
        result.append(hint)
    return result
