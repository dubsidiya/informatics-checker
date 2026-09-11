from __future__ import annotations

import ast
import copy
from dataclasses import dataclass


@dataclass(frozen=True)
class Mutant:
    kind: str
    source: str
    note: str


FLIP_OPS = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.Gt,
    ast.Gt: ast.Lt,
    ast.LtE: ast.GtE,
    ast.GtE: ast.LtE,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}


def generate_mutants(source: str) -> list[Mutant]:
    source = source.replace("\r\n", "\n")
    found: list[Mutant] = []
    found.extend(_text_mutants(source))
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _unique(found)
    found.extend(_ast_mutants(tree))
    return _unique(found)


def _unique(items: list[Mutant]) -> list[Mutant]:
    seen: set[str] = set()
    result: list[Mutant] = []
    for item in items:
        if item.source in seen:
            continue
        seen.add(item.source)
        result.append(item)
    return result


def _dump(tree: ast.AST) -> str | None:
    try:
        ast.fix_missing_locations(tree)
        return ast.unparse(tree) + "\n"
    except Exception:
        return None


def _text_mutants(source: str) -> list[Mutant]:
    found: list[Mutant] = []
    pairs = [
        ("flip_and_or", " and ", " or ", "and/or"),
        ("flip_and_or", " or ", " and ", "and/or"),
        ("swap_minmax", "min(", "max(", "min/max"),
        ("swap_minmax", "max(", "min(", "min/max"),
        ("unwrap_abs", "abs(", "", "abs"),
        ("yes_no", "'YES'", "'NO'", "YES/NO"),
        ("yes_no", "'NO'", "'YES'", "YES/NO"),
        ("even_odd", "'EVEN'", "'ODD'", "EVEN/ODD"),
        ("even_odd", "'ODD'", "'EVEN'", "EVEN/ODD"),
        ("plus_minus", " + ", " - ", "+/-"),
        ("mod_floor", " % ", " // ", "% //"),
        ("n_plus_one", "n + 1", "n", "range end"),
        ("n_plus_one", "n+1", "n", "range end"),
        ("window", " + 1", " + 2", "i+1"),
        ("window", "+1]", "+2]", "i+1"),
    ]
    for kind, old, new, note in pairs:
        if old == "abs(":
            continue
        if old in source:
            found.append(Mutant(kind, source.replace(old, new, 1), note))
    if "abs(" in source:
        found.append(Mutant("unwrap_abs", source.replace("abs(", "(", 1), "abs"))
    if "print(" in source:
        found.append(Mutant("drop_print", source.replace("print(", "pass  # print(", 1), "no print"))
    if "[::-1]" in source:
        found.append(Mutant("drop_reverse", source.replace("[::-1]", "", 1), "reverse"))
    if ".lower()" in source:
        found.append(Mutant("drop_lower", source.replace(".lower()", "", 1), "lower"))
    if "[2:]" in source:
        found.append(Mutant("drop_bin_prefix", source.replace("[2:]", "", 1), "0b"))
    if "set(" in source:
        found.append(Mutant("drop_set", source.replace("set(", "(", 1), "set"))
    return found


def _ast_mutants(tree: ast.Module) -> list[Mutant]:
    found: list[Mutant] = []
    sites: list[tuple[str, ast.AST, ast.AST]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.BoolOp) and len(node.values) >= 2:
            flipped = copy.deepcopy(node)
            flipped.op = ast.Or() if isinstance(node.op, ast.And) else ast.And()
            sites.append(("flip_and_or", node, flipped))
        if isinstance(node, ast.Compare) and node.ops:
            op = node.ops[0]
            for src_t, dst_t in FLIP_OPS.items():
                if isinstance(op, src_t):
                    flipped = copy.deepcopy(node)
                    flipped.ops[0] = dst_t()
                    sites.append(("flip_compare", node, flipped))
                    break
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"min", "max"}:
                flipped = copy.deepcopy(node)
                flipped.func.id = "max" if node.func.id == "min" else "min"
                sites.append(("swap_minmax", node, flipped))
            if node.func.id == "abs" and node.args:
                sites.append(("unwrap_abs", node, copy.deepcopy(node.args[0])))
            if node.func.id == "print" and len(node.args) >= 2:
                dropped = copy.deepcopy(node)
                dropped.args = node.args[:1]
                sites.append(("drop_print_arg", node, dropped))
                swapped = copy.deepcopy(node)
                swapped.args[0], swapped.args[1] = swapped.args[1], swapped.args[0]
                sites.append(("swap_print_args", node, swapped))
            if node.func.id == "range" and len(node.args) >= 2:
                stop = node.args[1]
                if isinstance(stop, ast.BinOp) and isinstance(stop.op, ast.Add):
                    shorter = copy.deepcopy(node)
                    shorter.args[1] = copy.deepcopy(stop.left)
                    sites.append(("range_end", node, shorter))
                if isinstance(stop, ast.Constant) and isinstance(stop.value, int):
                    shorter = copy.deepcopy(node)
                    shorter.args[1] = ast.Constant(value=stop.value - 1)
                    sites.append(("range_end", node, shorter))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            sites.append(("drop_not", node, copy.deepcopy(node.operand)))
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            if 2 <= node.value <= 20000:
                plus = copy.deepcopy(node)
                plus.value = node.value + 1
                sites.append(("tweak_const", node, plus))
                minus = copy.deepcopy(node)
                minus.value = node.value - 1
                sites.append(("tweak_const", node, minus))
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Add):
                flipped = copy.deepcopy(node)
                flipped.op = ast.Sub()
                sites.append(("plus_minus", node, flipped))
            elif isinstance(node.op, ast.Sub):
                flipped = copy.deepcopy(node)
                flipped.op = ast.Add()
                sites.append(("plus_minus", node, flipped))
            elif isinstance(node.op, ast.FloorDiv):
                flipped = copy.deepcopy(node)
                flipped.op = ast.Div()
                sites.append(("floor_to_div", node, flipped))
            elif isinstance(node.op, ast.Mod) and isinstance(node.right, ast.Constant):
                if isinstance(node.right.value, int) and node.right.value not in {0, 1}:
                    alt = copy.deepcopy(node)
                    alt.right = ast.Constant(value=2 if node.right.value != 2 else 10)
                    sites.append(("change_mod", node, alt))
        if isinstance(node, (ast.List, ast.Tuple)) and 2 <= len(node.elts) <= 8:
            ints = [elt for elt in node.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, int)]
            if len(ints) == len(node.elts) and all(2 <= elt.value <= 200 for elt in ints):
                for index in range(len(node.elts)):
                    dropped = copy.deepcopy(node)
                    del dropped.elts[index]
                    sites.append(("drop_divisor", node, dropped))

    for kind, old, new in sites:
        mutant_tree = copy.deepcopy(tree)
        replaced = _replace(mutant_tree, old, new)
        if not replaced:
            continue
        text = _dump(mutant_tree)
        if text:
            found.append(Mutant(kind, text, kind))
    return found


def _replace(tree: ast.AST, old: ast.AST, new: ast.AST) -> bool:
    for parent in ast.walk(tree):
        for field, value in ast.iter_fields(parent):
            if value is old or _same_shape(value, old):
                setattr(parent, field, new)
                return True
            if isinstance(value, list):
                for index, item in enumerate(value):
                    if item is old or _same_shape(item, old):
                        value[index] = new
                        return True
    return False


def _same_shape(left: object, right: ast.AST) -> bool:
    if not isinstance(left, ast.AST):
        return False
    try:
        return ast.dump(left) == ast.dump(right)
    except Exception:
        return False
