from __future__ import annotations

import ast

from checker.models import SyntaxIssue

BANNED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "socket",
    "shutil",
    "pathlib",
    "ctypes",
    "importlib",
    "multiprocessing",
    "threading",
    "http",
    "urllib",
    "requests",
    "ftplib",
    "pickle",
    "marshal",
    "builtins",
    "inspect",
    "code",
    "codeop",
    "pty",
    "signal",
    "resource",
    "fcntl",
    "mmap",
    "webbrowser",
    "tempfile",
    "glob",
    "runpy",
    "pkgutil",
    "posix",
    "nt",
    "sysconfig",
}

BANNED_FUNCS = {
    "open",
    "exec",
    "eval",
    "compile",
    "__import__",
    "breakpoint",
    "exit",
    "quit",
}

BANNED_ATTRS = {
    "__subclasses__",
    "__globals__",
    "__code__",
    "__builtins__",
    "__loader__",
    "__bases__",
}


def find_forbidden(source: str, allow_open: bool = False) -> SyntaxIssue | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_name = alias.name.split(".", 1)[0]
                if root_name in BANNED_MODULES:
                    return _issue(node, f"Нельзя импортировать {alias.name}. В школьной задаче этот модуль не нужен.")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                return _issue(node, "Относительные импорты здесь запрещены.")
            if node.module:
                root_name = node.module.split(".", 1)[0]
                if root_name in BANNED_MODULES:
                    return _issue(node, f"Нельзя импортировать {node.module}. В школьной задаче этот модуль не нужен.")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BANNED_FUNCS and not (allow_open and node.func.id == "open"):
                return _issue(node, f"Функция {node.func.id}() на проверяльщике запрещена.")
        elif isinstance(node, ast.Attribute) and node.attr in BANNED_ATTRS:
            return _issue(node, "Такой приём Python здесь нельзя использовать.")
        elif isinstance(node, ast.Name) and node.id in BANNED_FUNCS and not (allow_open and node.id == "open"):
            if isinstance(getattr(node, "ctx", None), ast.Load):
                # allow mentioning in comments only; this is a real name load
                return _issue(node, f"Имя {node.id} на проверяльщике запрещено.")
    return None


def _issue(node: ast.AST, explanation: str) -> SyntaxIssue:
    return SyntaxIssue(
        line=getattr(node, "lineno", None),
        column=getattr(node, "col_offset", None),
        message="forbidden",
        explanation=explanation,
        snippet="",
    )
