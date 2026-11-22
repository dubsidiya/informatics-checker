from __future__ import annotations

import ast
import re


def russian_traceback(stderr: str) -> str:
    """Explain the last Python exception in plain Russian."""
    text = stderr or ""
    match = re.search(r"(?P<type>[A-Za-z_][A-Za-z0-9_]*Error): (?P<message>.*)", text)
    if not match:
        return ""
    kind = match.group("type")
    message = match.group("message").strip()
    name = _quoted(message)
    explanations = {
        "NameError": f"Имя {name or 'переменной'} ещё не создано. Проверь опечатку и что присваивание стоит выше.",
        "TypeError": "Операция применена к неподходящим типам. Например, функцию сравнивают с числом или строку складывают с числом.",
        "ValueError": "Значение имеет верный тип, но неподходящее содержание. Часто int() получил текст, который не является одним числом.",
        "IndexError": "Такого номера элемента нет. Индексы списка начинаются с 0 и заканчиваются на длине списка минус 1.",
        "KeyError": f"В словаре нет ключа {name or 'с таким именем'}. Сначала проверь, что ключ был добавлен.",
        "ZeroDivisionError": "Делить на ноль нельзя. Проверь значение знаменателя перед делением.",
        "RecursionError": "Функция вызывает саму себя слишком много раз. Добавь условие остановки или измени аргумент так, чтобы вызовы закончились.",
        "IndentationError": "Сломаны отступы. Команды одного блока должны начинаться на одном уровне, обычно кратном 4 пробелам.",
        "SyntaxError": "Python не понял запись кода. Проверь двоеточие, скобки, кавычки и знаки == в условиях.",
        "FileNotFoundError": "Файл с таким именем не найден. Загрузи его в песочницу и открой точно тем именем, которое показано рядом с кнопкой.",
        "PermissionError": "Этот файл можно только читать. Запись и открытие посторонних путей в песочнице запрещены.",
        "AttributeError": "У этого объекта нет вызванного свойства или метода. Проверь тип значения слева от точки.",
        "EOFError": "input() запросил ещё одну строку, но во поле ввода она закончилась.",
    }
    base = explanations.get(kind, "Программа остановилась из-за ошибки Python.")
    if kind == "TypeError" and "function" in message and "int" in message:
        base = "С числом сравнивается сама функция. Используй её аргумент, например n > 10, а не имя функции f > 10."
    return f"По-русски: {base}"


def _quoted(message: str) -> str:
    match = re.search(r"'([^']+)'", message)
    return f"«{match.group(1)}»" if match else ""

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
    (re.compile(r"leading zeros", re.I), "В Python 3 нельзя писать числа с ведущим нулём вроде 07. Это должна быть строка '07' или число 7."),
    (re.compile(r"invalid decimal", re.I), "Число записано неверно. Проверь точку, запятую и лишние символы."),
]


def explain_syntax(source: str) -> SyntaxIssue | None:
    try:
        ast.parse(source)
    except SyntaxError as exc:
        raw = exc.msg or "Неверный синтаксис"
        explanation = _translate(raw)
        snippet = _snippet(source, exc.lineno, exc.offset)
        if exc.text:
            code = re.sub(r"\s*#.*$", "", exc.text).rstrip()
            if (re.search("''*(?:join|split)\\(", code) or re.search("'(?:join|split)\\(", code)) and not re.search('\\.[A-Za-z_]\\w*\\(', code):
                explanation = "\u041f\u0440\u043e\u043f\u0443\u0449\u0435\u043d\u0430 \u0442\u043e\u0447\u043a\u0430 \u043f\u0435\u0440\u0435\u0434 join: \u043d\u0443\u0436\u043d\u043e ''.join(x), \u0430 \u043d\u0435 ''join(x)."
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


def russian_traceback(stderr: str) -> str:
    """Explain the last Python exception in plain Russian."""
    text = stderr or ""
    match = re.search(r"(?P<type>[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception)): (?P<message>.*)", text)
    if not match:
        return ""
    kind = match.group("type")
    message = match.group("message").strip()
    line = _student_line(text)
    where = f"На строке {line}: " if line else ""
    return where + _runtime_translation(kind, message)


def _student_line(stderr: str) -> int | None:
    found = None
    for match in re.finditer(r'File ".*student\.py", line (\d+)', stderr):
        found = int(match.group(1))
    return found


def _runtime_translation(kind: str, message: str) -> str:
    name = _quoted(message)
    pairs = _type_pair(message)
    if kind == "NameError":
        return f"имя {name or 'переменной'} ещё не создано. Проверь опечатку и поставь присваивание выше первого использования."
    if kind == "UnboundLocalError":
        return f"имя {name or 'переменной'} используется до присваивания внутри функции. Дай ему значение раньше или не скрывай внешнюю переменную."
    if kind == "TypeError":
        if "function" in message and pairs:
            return f"с типом {pairs[1]} сравнивается сама функция. Пиши аргумент, например n > 10, а не имя функции."
        if "unsupported operand" in message and pairs:
            return f"операцию нельзя выполнить между типами {pairs[0]} и {pairs[1]}. Преобразуй значения к одному типу: строке через str() или числу через int()."
        if "not callable" in message:
            return f"{name or 'это значение'} — не функция. После имени стоят скобки, хотя вызывать его нельзя."
        if "missing" in message and "required positional argument" in message:
            return "при вызове функции не хватает аргумента. Сверь имя функции и значения в скобках."
        if "takes" in message and "positional arguments but" in message:
            return "в функцию передано неверное количество аргументов. Посчитай параметры в def и значения в вызове."
        if "can only concatenate str" in message:
            return "строку можно соединять только со строкой. Для числа используй str(число) или печатай значения через print(a, b)."
        if "object is not iterable" in message:
            return f"тип {pairs[0] if pairs else 'этого значения'} нельзя перебирать циклом. Список или строка подходят, а число — нет."
        if "object is not subscriptable" in message:
            return "к этому значению нельзя обращаться по индексу в квадратных скобках. Индексы работают у списка, строки и словаря."
        return "операция применена к неподходящему типу данных. Проверь, где ожидалось число, строка, список или функция."
    if kind == "ValueError":
        if "invalid literal for int" in message:
            return "int() не смог получить число из текста. Сначала раздели строку через split(), если в ней несколько значений."
        if "not enough values to unpack" in message:
            return "слева от = указано больше переменных, чем значений получено справа."
        if "too many values to unpack" in message:
            return "справа получено больше значений, чем переменных слева от =."
        return "значение имеет подходящий тип, но неверное содержание для этой операции."
    if kind == "IndexError":
        if "pop from empty" in message:
            return "нельзя взять элемент из пустого списка."
        return "такого номера элемента нет. Индексы начинаются с 0 и заканчиваются на длине минус 1."
    if kind == "KeyError":
        return f"в словаре нет ключа {name or 'с таким именем'}. Проверь его написание или используй .get()."
    if kind == "ZeroDivisionError":
        return "делить на ноль нельзя. Проверь знаменатель перед делением."
    if kind == "RecursionError":
        return "функция вызывает саму себя слишком много раз. Добавь достижимое условие остановки и меняй аргумент на каждом шаге."
    if kind == "IndentationError":
        return "сломаны отступы. Все команды одного блока начинай на одном уровне, обычно кратном четырём пробелам."
    if kind == "TabError":
        return "в отступах смешаны пробелы и Tab. Оставь только пробелы, по четыре на уровень."
    if kind == "SyntaxError":
        return _translate(message).rstrip(".") + "."
    if kind == "FileNotFoundError":
        return f"файл {name or 'с таким именем'} не найден. Загрузи его и открой точно тем именем, которое показано рядом с кнопкой."
    if kind == "PermissionError":
        return "этот файл можно только читать. Запись и открытие посторонних путей в песочнице запрещены."
    if kind == "AttributeError":
        return f"у объекта нет свойства или метода {name or 'с таким именем'}. Проверь тип значения слева от точки."
    if kind == "EOFError":
        return "input() запросил ещё одну строку, но в поле ввода строки закончились."
    if kind == "OverflowError":
        return "число стало слишком большим для этой операции. Проверь, нет ли бесконечного роста или лишнего цикла."
    if kind == "MemoryError":
        return "программе не хватило памяти. Уменьши размер создаваемого списка или глубину перебора."
    if kind == "TimeoutError":
        return "программа работала слишком долго. Проверь условие цикла и аргументы рекурсии."
    return "программа остановилась из-за ошибки Python. Смотри указанную строку и тип значения, с которым выполняется операция."


def _quoted(message: str) -> str:
    match = re.search(r"'([^']+)'", message)
    return f"«{match.group(1)}»" if match else ""


def _type_pair(message: str) -> tuple[str, str] | None:
    types = re.findall(r"'([^']+)'", message)
    if len(types) >= 2:
        return types[-2], types[-1]
    if len(types) == 1:
        return types[0], ""
    return None
