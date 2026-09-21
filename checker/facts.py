from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from checker.models import Problem, TestResult


@dataclass
class ModCheck:
    modulus: int
    equals_zero: bool | None
    line: int | None = None


@dataclass
class CodeFacts:
    source: str
    tree: ast.AST | None
    has_print: bool = False
    print_value_counts: list[int] = field(default_factory=list)
    print_inside_loop: bool = False
    constant_prints: list[str] = field(default_factory=list)
    has_input: bool = False
    input_count: int = 0
    has_int: bool = False
    has_map: bool = False
    has_split: bool = False
    has_open: bool = False
    has_loop: bool = False
    has_range: bool = False
    range_literals: list[tuple[int, int, int | None]] = field(default_factory=list)
    moduli: set[int] = field(default_factory=set)
    mod_checks: list[ModCheck] = field(default_factory=list)
    divisor_lists: list[list[int]] = field(default_factory=list)
    uses_combinations: bool = False
    uses_permutations: bool = False
    nested_fors: bool = False
    consecutive_pair: bool = False
    window3: bool = False
    pair_bool: str | None = None
    uses_min: bool = False
    uses_max: bool = False
    uses_abs: bool = False
    uses_set: bool = False
    uses_bin: bool = False
    uses_gcd: bool = False
    reverse_slice: bool = False
    has_lower: bool = False
    true_div: bool = False
    floor_div: bool = False
    bit_and: bool = False
    string_repeat: bool = False
    raw_input_add: bool = False
    vowels_cyrillic: bool = False
    vowels_latin_only: bool = False
    last_digit_mod: bool = False
    last_digit_without_abs: bool = False
    avg_of_positives: bool = False
    abs_sum: bool = False
    hardcoded_loop: bool = False
    has_if: bool = False
    names: set[str] = field(default_factory=set)


@dataclass
class Outcome:
    first: TestResult
    got: str
    expected: str
    got_tokens: list[str]
    exp_tokens: list[str]
    empty: bool
    format_only: bool
    count_ok: bool | None = None
    value_ok: bool | None = None
    count_more: bool | None = None
    count_less: bool | None = None
    off_by_one: bool = False
    sign_only: bool = False
    doubled: bool = False


def extract_facts(source: str) -> CodeFacts:
    source = source.replace("\r\n", "\n")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return CodeFacts(source=source, tree=None)

    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    facts = CodeFacts(
        source=source,
        tree=tree,
        has_print=any(_called(node, "print") for node in calls),
        has_input=any(_called(node, "input") for node in calls),
        input_count=sum(1 for node in calls if _called(node, "input")),
        has_int=any(_called(node, "int") for node in calls),
        has_map=any(_called(node, "map") for node in calls),
        has_split=any(
            isinstance(node.func, ast.Attribute) and node.func.attr == "split" for node in calls
        ),
        has_open=any(_called(node, "open") for node in calls),
        has_loop=any(isinstance(node, (ast.For, ast.While)) for node in ast.walk(tree)),
        has_range=any(_called(node, "range") for node in calls),
        uses_combinations="combinations" in source,
        uses_permutations="permutations" in source,
        uses_min=any(_called(node, "min") for node in calls),
        uses_max=any(_called(node, "max") for node in calls),
        uses_abs=any(_called(node, "abs") for node in calls),
        uses_set=any(_called(node, "set") for node in calls) or "set(" in source,
        uses_bin="bin(" in source,
        uses_gcd="gcd" in source,
        reverse_slice="[::-1]" in source or "reversed(" in source,
        has_lower=".lower(" in source or ".casefold(" in source,
        last_digit_mod="% 10" in source or "%10" in source,
        names={node.id for node in ast.walk(tree) if isinstance(node, ast.Name)},
    )

    facts.print_value_counts = [
        len(node.args) for node in calls if _called(node, "print")
    ]
    facts.print_inside_loop = _print_inside_loop(tree)
    facts.constant_prints = _constant_prints(tree)
    facts.range_literals = _range_literals(tree)
    facts.moduli, facts.mod_checks, facts.divisor_lists = _mod_data(tree, source)
    facts.nested_fors = _nested_fors(tree)
    facts.consecutive_pair = bool(
        re.search(r"\[\s*\w+\s*[+-]\s*1\s*\]|zip\s*\([^)]+\[\s*1\s*:", source)
    )
    facts.window3 = bool(re.search(r"\[\s*\w+\s*[+-]\s*2\s*\]", source))
    facts.pair_bool = _pair_bool(tree)
    facts.true_div = any(isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) for node in ast.walk(tree))
    facts.floor_div = any(isinstance(node, ast.BinOp) and isinstance(node.op, ast.FloorDiv) for node in ast.walk(tree))
    facts.bit_and = any(isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitAnd) for node in ast.walk(tree))
    facts.string_repeat = any(isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult) for node in ast.walk(tree))
    facts.raw_input_add = _raw_input_add(tree)
    facts.vowels_cyrillic = bool(re.search(r"[аеёиоуыэюя]", source, re.I))
    facts.vowels_latin_only = bool(re.search(r"[aeiou]", source, re.I)) and not facts.vowels_cyrillic
    facts.last_digit_without_abs = facts.last_digit_mod and not facts.uses_abs
    facts.avg_of_positives = bool(re.search(r">\s*0", source)) and ("sum(" in source or "/" in source)
    facts.abs_sum = bool(re.search(r"abs\s*\([^)]+\)\s*\+\s*abs\s*\(", source))
    facts.has_if = any(isinstance(node, ast.If) for node in ast.walk(tree))
    facts.hardcoded_loop = (
        facts.has_print and not facts.has_loop and not facts.has_range
        and not facts.has_open and not facts.has_if
    )
    return facts


def extract_outcome(tests: list[TestResult]) -> Outcome | None:
    failing = [item for item in tests if item.verdict != "OK"]
    if not failing:
        return None
    first = failing[0]
    if first.hidden:
        expected = ""
        got = "" if not (first.got or "").strip() else "x"
    else:
        got = first.got or ""
        expected = first.expected or ""
    got_tokens = _tokens(got)
    exp_tokens = _tokens(expected)
    outcome = Outcome(
        first=first,
        got=got,
        expected=expected,
        got_tokens=got_tokens,
        exp_tokens=exp_tokens,
        empty=not got.strip(),
        format_only=_format_only(got, expected),
    )
    if len(got_tokens) == 2 and len(exp_tokens) == 2:
        outcome.count_ok = got_tokens[0] == exp_tokens[0]
        outcome.value_ok = got_tokens[1] == exp_tokens[1]
        left, right = _int_or_none(got_tokens[0]), _int_or_none(exp_tokens[0])
        if left is not None and right is not None and left != right:
            outcome.count_more = left > right
            outcome.count_less = left < right
        else:
            outcome.count_more = False
            outcome.count_less = False
    if len(got_tokens) == 1 and len(exp_tokens) == 1:
        a, b = _int_or_none(got_tokens[0]), _int_or_none(exp_tokens[0])
        if a is not None and b is not None:
            outcome.off_by_one = abs(a - b) == 1
            outcome.sign_only = a == -b and a != b
            outcome.doubled = b != 0 and (a == 2 * b or b == 2 * a)
    return outcome


def parse_div_filters(statement: str) -> tuple[list[int], list[int]]:
    must_not = _numbers_after(r"не\s+дел(?:ится|ятся)\s+на\s+([\d,\sи]+)", statement)
    rest = re.sub(r"не\s+дел(?:ится|ятся)\s+на\s+[\d,\sи]+", " ", statement)
    must = _numbers_after(r"дел(?:ится|ятся|ящихся|иться)\s+на\s+([\d,\sи]+)", rest)
    must += _numbers_after(r"кратн[а-яё]*\s+(\d+)", statement)
    must += [int(x) for x in re.findall(r"или\s+на\s+(\d+)", rest)]
    return _unique_keep(must), _unique_keep(must_not)


def closed_range_bounds(statement: str) -> tuple[int, int] | None:
    match = re.search(r"\[(\d+)\s*[;,]\s*(\d+)\]", statement)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def example_outputs(problem: Problem) -> list[str]:
    return [item.stdout.strip() for item in problem.examples if item.stdout.strip()]


def _called(node: ast.Call, name: str) -> bool:
    return isinstance(node.func, ast.Name) and node.func.id == name


def _print_inside_loop(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and _called(child, "print"):
                    return True
    return False


def _constant_prints(tree: ast.AST) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _called(node, "print") and node.args):
            continue
        values = []
        ok = True
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, str, float)):
                values.append(str(arg.value))
            else:
                ok = False
                break
        if ok:
            found.append(" ".join(values))
    return found


def _range_literals(tree: ast.AST) -> list[tuple[int, int, int | None]]:
    found: list[tuple[int, int, int | None]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _called(node, "range") and len(node.args) >= 2):
            continue
        start, stop = node.args[0], node.args[1]
        if (
            isinstance(start, ast.Constant)
            and isinstance(stop, ast.Constant)
            and isinstance(start.value, int)
            and isinstance(stop.value, int)
        ):
            found.append((start.value, stop.value, getattr(node, "lineno", None)))
    return found


def _mod_data(tree: ast.AST, source: str) -> tuple[set[int], list[ModCheck], list[list[int]]]:
    moduli: set[int] = set()
    checks: list[ModCheck] = []
    lists: list[list[int]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            if isinstance(node.right, ast.Constant) and isinstance(node.right.value, int):
                moduli.add(node.right.value)
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            values = []
            for elt in node.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, int):
                    values.append(elt.value)
                else:
                    values = []
                    break
            if values and all(2 <= item <= 200 for item in values):
                lists.append(values)
                moduli.update(values)
        if isinstance(node, ast.Compare):
            check = _mod_compare(node)
            if check:
                checks.append(check)
                moduli.add(check.modulus)

    for raw in re.findall(r"%\s*(\d+)", source):
        moduli.add(int(raw))
    return moduli, checks, lists


def _mod_compare(node: ast.Compare) -> ModCheck | None:
    if len(node.ops) != 1 or len(node.comparators) != 1:
        return None
    op = node.ops[0]
    other = node.comparators[0]
    left = node.left
    modulus = _modulus_of(left)
    zero_side = other
    if modulus is None:
        modulus = _modulus_of(other)
        zero_side = left
    if modulus is None:
        return None
    if not (isinstance(zero_side, ast.Constant) and zero_side.value == 0):
        return None
    equals: bool | None
    if isinstance(op, ast.Eq):
        equals = True
    elif isinstance(op, ast.NotEq):
        equals = False
    else:
        equals = None
    return ModCheck(modulus=modulus, equals_zero=equals, line=getattr(node, "lineno", None))


def _modulus_of(node: ast.AST) -> int | None:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        if isinstance(node.right, ast.Constant) and isinstance(node.right.value, int):
            return node.right.value
    return None


def _nested_fors(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        for child in ast.walk(node):
            if child is node:
                continue
            if isinstance(child, ast.For) and _iterates_index_space(node) and _iterates_index_space(child):
                return True
    return False


def _iterates_index_space(node: ast.For) -> bool:
    text = ast.dump(node.iter)
    return "range" in text or "Name" in text


def _pair_bool(tree: ast.AST) -> str | None:
    found_and = False
    found_or = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.BoolOp) or len(node.values) < 2:
            continue
        compares = [item for item in node.values if isinstance(item, ast.Compare)]
        if len(compares) < 2:
            continue
        if isinstance(node.op, ast.And):
            found_and = True
        elif isinstance(node.op, ast.Or):
            found_or = True
    if found_and and not found_or:
        return "and"
    if found_or and not found_and:
        return "or"
    return None


def _raw_input_add(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            if _is_input(node.left) or _is_input(node.right):
                return True
    return False


def _is_input(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _called(node, "input")


def _tokens(text: str) -> list[str]:
    return " ".join(text.replace(",", " ").replace(";", " ").split()).split()


def _format_only(got: str, expected: str) -> bool:
    if got.strip() == expected.strip():
        return False
    compact_got = " ".join(got.split())
    compact_exp = " ".join(expected.split())
    if compact_got == compact_exp or got.strip().lower() == expected.strip().lower():
        return True
    got_tokens = _tokens(got)
    exp_tokens = _tokens(expected)
    return bool(got_tokens) and got_tokens == exp_tokens


def _int_or_none(text: str) -> int | None:
    try:
        return int(text)
    except ValueError:
        return None


def _numbers_after(pattern: str, text: str) -> list[int]:
    found: list[int] = []
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        found.extend(int(raw) for raw in re.findall(r"\d+", match.group(1)))
    return found


def _unique_keep(items: list[int]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for item in items:
        if item >= 2 and item not in seen:
            seen.add(item)
            result.append(item)
    return result
