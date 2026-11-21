"""Notice when a solo solution skips the shorter method from the lesson.

Output checks stay in the tests. A different algorithm with the same answers
is accepted. The lecture method is only a shorter-way note, and EGE tasks
are outside this check.
"""

from __future__ import annotations

import ast

from checker.facts import extract_facts
from checker.models import Problem


def lecture_gap(problem: Problem, source: str) -> tuple[str, str, str] | None:
    if _is_ege(problem):
        return None
    check = _CHECKS.get(problem.id)
    if check is None:
        return None
    facts = extract_facts(source)
    return check(facts.source, facts.tree)


def _is_ege(problem: Problem) -> bool:
    topic = problem.topic or ""
    if topic.startswith("ЕГЭ"):
        return True
    return any(str(tag).startswith("ege") for tag in problem.tags)


def _sum_until_zero(source: str, tree: ast.AST | None) -> tuple[str, str, str] | None:
    compact = source.replace(" ", "")
    if "while" in source and "!=" in source and "0" in source and "+=" in source and _input_count(tree) >= 2:
        return None
    return (
        "На лекции сумму читают циклом до нуля",
        "Числа идут по одному, пока не введут 0. Ноль не прибавляют.",
        "Напиши так: `x = int(input())`, `s = 0`, `while x != 0:`, внутри `s += x` и снова `x = int(input())`, после цикла `print(s)`.",
    )


def _product_until_zero(source: str, tree: ast.AST | None) -> tuple[str, str, str] | None:
    compact = source.replace(" ", "")
    if (
        "while" in source
        and "!=" in source
        and "*=" in source
        and "=1" in compact
        and _input_count(tree) >= 2
    ):
        return None
    return (
        "На лекции произведение копят с единицы",
        "Числа читают до нуля и умножают. Ноль в произведение не входит, поэтому накопитель в начале равен 1.",
        "Напиши `p = 1` и `while x != 0:`, внутри `p *= x` и снова `x = int(input())`, после цикла `print(p)`.",
    )


def _divisors_from_two(source: str, tree: ast.AST | None) -> tuple[str, str, str] | None:
    if _pair_to_root(source, tree):
        return None
    return (
        "Делители ищут от 2 до корня",
        "Полный цикл до самого числа на лекции был только чтобы увидеть делители. В решении проверяют делители до корня и сразу берут пару.",
        "Напиши список `[x]`, затем `for i in range(2, int(x ** 0.5) + 1):`. Если `x % i == 0`, добавь `i` и `x // i`. Напечатай `sorted(set(список))` по одному в строке.",
    )


def _keep_evens(source: str, tree: ast.AST | None) -> tuple[str, str, str] | None:
    compact = source.replace(" ", "")
    even = "%2==0" in compact or "not(x%2)" in compact
    if "filter(" in source and even:
        return None
    return (
        "На лекции чётные отбирает filter",
        "Сначала функция говорит, чётное ли число, затем filter оставляет только такие.",
        "Напиши `def f(x):` с `return True` при `x % 2 == 0`, иначе `return False`, и `print(*filter(f, map(int, input().split())))`.",
    )


def _prime_factors(source: str, tree: ast.AST | None) -> tuple[str, str, str] | None:
    compact = source.replace(" ", "")
    sqrt = "**0.5" in compact or "sqrt" in source
    flag = "m==0" in compact or "m=0" in compact
    if "while" in source and sqrt and "//=" in compact and _has_break(tree) and (_has_for_else(tree) or flag):
        return None
    return (
        "На лекции множители ищет factorize до корня",
        "Делитель перебирают до корня числа. Нашли — делят и начинают сначала. Не нашли — число само простой множитель.",
        "Напиши `while` и `for i in range(2, int(x ** 0.5) + 1):`. Если `x % i == 0`, сделай `a.append(i)`, `x //= i` и `break`. В `else` этого for верни `a + [x]`.",
    )


def _all_divisors(source: str, tree: ast.AST | None) -> tuple[str, str, str] | None:
    compact = source.replace(" ", "")
    if _pair_to_root(source, tree) and ("[1," in compact or "[1]" in compact or ",1," in compact or "l=[1" in compact):
        return None
    return (
        "Делители ищут от 2 до корня",
        "Цикл от 1 до x на лекции показывал, что такое делитель. В решении список начинают с 1 и x, а проверяют только числа до корня.",
        "Напиши `l = [1, x]` и `for i in range(2, int(x ** 0.5) + 1):`. Если `x % i == 0`, добавь `i` и `x // i`. Напечатай `sorted(set(l))`.",
    )


def _pair_to_root(source: str, tree: ast.AST | None) -> bool:
    compact = source.replace(" ", "")
    root = "**0.5" in compact or "sqrt(" in source
    pair = "x//i" in compact or "x// i" in source.replace(" ", "")
    return _has_for(tree) and "range(2," in compact and root and "%" in source and "==0" in compact and pair


def _input_count(tree: ast.AST | None) -> int:
    if tree is None:
        return 0
    return sum(1 for node in ast.walk(tree) if _is_input(node))


def _is_input(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "input"


def _has_for(tree: ast.AST | None) -> bool:
    return tree is not None and any(isinstance(node, ast.For) for node in ast.walk(tree))


def _has_break(tree: ast.AST | None) -> bool:
    return tree is not None and any(isinstance(node, ast.Break) for node in ast.walk(tree))


def _has_for_else(tree: ast.AST | None) -> bool:
    return tree is not None and any(isinstance(node, ast.For) and bool(node.orelse) for node in ast.walk(tree))


_CHECKS = {
    "sum-until-zero": _sum_until_zero,
    "product-until-zero": _product_until_zero,
    "divisors-from-two": _divisors_from_two,
    "keep-evens": _keep_evens,
    "prime-factors": _prime_factors,
    "all-divisors": _all_divisors,
}
