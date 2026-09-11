from __future__ import annotations

import ast
import re

from checker.models import SyntaxIssue

RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"expected ':'"), "После if, for, while, def или else нужно поставить двоеточие."),
    (re.compile(r"expected 'except'"), "После try должен быть блок except или finally."),
    (re.compile(r"unmatched|never closed|was never closed", re.I), "Скобка не закрыта. Посчитай открывающие и закрывающие скобки."),
    (re.compile(r"unindent|expected an indented block", re.I), "После двоеточия нужна новая строка с отступом (обычно 4 пробела)."),
    (re.compile(r"unexpected indent", re.I), "Лишний отступ. Выровняй строку как соседние команды этого блока."),
    (re.compile(r"unexpected EOF|unexpected end of file", re.I), "Программа оборвалась: не закрыта скобка, кавычка или блок."),
    (re.compile(r"invalid character", re.I), "Посторонний символ. Часто это русская буква вместо латинской или «умная» кавычка."),
    (re.compile(r"unterminated string", re.I), "Строка не закрыта кавычкой."),
    (re.compile(r"Maybe you forgot a comma", re.I), "Похоже, между значениями пропущена запятая."),
    (re.compile(r"cannot assign to", re.I), "Слева от = должно быть имя переменной, а не выражение."),
    (re.compile(r"invalid syntax", re.I), "Синтаксическая ошибка. Смотри строку выше: чаще всего скобки, запятая или двоеточие."),
]


def explain_syntax(source: str) -> SyntaxIssue | None:
    try:
        ast.parse(source)
    except SyntaxError as exc:
        raw = exc.msg or "Неверный синтаксис"
        explanation = _translate(raw)
        snippet = _snippet(source, exc.lineno, exc.offset)
        if exc.text and "=" in exc.text and re.search(r"\bif\b.*=[^=]", exc.text):
            explanation = "В условии if нужно сравнение ==, а не присваивание =."
        return SyntaxIssue(
            line=exc.lineno,
            column=exc.offset,
            message=raw,
            explanation=explanation,
            snippet=snippet,
        )
    except ValueError as exc:
        return SyntaxIssue(
            line=None,
            column=None,
            message=str(exc),
            explanation="В коде есть недопустимый символ. Проверь кавычки и копипасту из Word.",
            snippet="",
        )
    return None


def _translate(message: str) -> str:
    for pattern, text in RULES:
        if pattern.search(message):
            return text
    return f"Синтаксическая ошибка: {message}"


def _snippet(source: str, line: int | None, column: int | None) -> str:
    if not line:
        return ""
    lines = source.splitlines()
    if line < 1 or line > len(lines):
        return ""
    code = lines[line - 1]
    caret = ""
    if column and column > 0:
        caret = "\n" + " " * (column - 1) + "^"
    return f"{line}| {code}{caret}"
