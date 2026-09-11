from __future__ import annotations

import ast
import re

from checker.models import Hint, Problem


RU_NAMES = {
    "принт": "print",
    "ввод": "input",
    "длина": "len",
    "диапазон": "range",
}

RU_WORDS = {
    "и": "and",
    "или": "or",
    "не": "not",
    "если": "if",
    "иначе": "else",
    "для": "for",
    "пока": "while",
}


def analyze_source(source: str, problem: Problem) -> list[Hint]:
    hints: list[Hint] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return _text_only_hints(source)

    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    has_input = any(_called(node, "input") for node in calls)
    has_print = any(_called(node, "print") for node in calls)
    has_int = any(_called(node, "int") for node in calls)
    has_map = any(_called(node, "map") for node in calls)
    has_split = any(
        isinstance(node.func, ast.Attribute) and node.func.attr == "split" for node in calls
    )
    input_count = sum(1 for node in calls if _called(node, "input"))

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
        hints.append(
            Hint(
                kind="logic",
                title="input() возвращает строку",
                detail="Без int(...) или map(int, ...) числа остаются текстом. Тогда 2 + 3 превращается в 23, а сравнения работают не как у чисел.",
                line=_first_input_line(tree),
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

    if "inclusive_n" in problem.tags or "factorial" in problem.tags:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _called(node, "range") and len(node.args) == 1:
                title = "range(n) не включает n"
                detail = "range(n) даёт 0, 1, …, n-1. Для суммы от 1 до N нужен range(1, n + 1) или формула n * (n + 1) // 2."
                if "factorial" in problem.tags:
                    detail = "Для n! цикл должен дойти до n. range(n) останавливается на n-1, поэтому 5! станет 24 вместо 120."
                hints.append(
                    Hint(
                        kind="logic",
                        title=title,
                        detail=detail,
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

    if "last_digit" in problem.tags and not _has_modulo_10(tree) and "[-1]" not in source:
        hints.append(
            Hint(
                kind="logic",
                title="Последняя цифра не выделена",
                detail="Последняя цифра — это n % 10. Если число может быть отрицательным, бери abs(n) % 10. Либо str(n)[-1], но тогда снова нужен int.",
            )
        )

    if "even_odd" in problem.tags and not _has_modulo_n(tree, 2):
        hints.append(
            Hint(
                kind="logic",
                title="Чётность не проверяется",
                detail="Число чётное, если n % 2 == 0. Не сравнивай само число с «чётным списком» и не смотри только на последнюю цифру глазами.",
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

    if "two_line_input" in problem.tags and input_count == 1:
        hints.append(
            Hint(
                kind="logic",
                title="Прочитана только одна строка",
                detail="В условии две строки ввода. Обычно сначала input() для N, затем второй input() для списка. Один input() заберёт только первую строку.",
                line=_first_input_line(tree),
            )
        )

    if _has_yes_no_problem(problem) and not re.search(r"YES|NO|Yes|No|EVEN|ODD", source):
        if re.search(r"\b[01]\b", source) or "True" in source or "False" in source:
            hints.append(
                Hint(
                    kind="format",
                    title="Нужны слова, не 1/0",
                    detail="Проверяющая система ждёт YES/NO (или EVEN/ODD), а не 1 и 0 и не True/False.",
                )
            )
        else:
            hints.append(
                Hint(
                    kind="format",
                    title="Нужен ответ словами из условия",
                    detail="Печатай YES/NO или EVEN/ODD заглавными буквами, без кавычек и без лишнего текста.",
                )
            )

    if "print_once" in problem.tags and _print_inside_loop(tree) and _print_count(tree) == 1:
        hints.append(
            Hint(
                kind="format",
                title="print стоит внутри цикла",
                detail="Программа печатает ответ на каждом шаге. Счётчик или сумму нужно вывести один раз после цикла.",
            )
        )

    if "single_int_out" in problem.tags and _print_many_values(tree):
        hints.append(
            Hint(
                kind="format",
                title="print печатает несколько значений",
                detail="В ответе нужно одно число. print(a, b) выведет два числа через пробел — система это не примет.",
            )
        )

    if "integer_div" in problem.tags and _has_true_div(tree):
        hints.append(
            Hint(
                kind="logic",
                title="Обычное деление вместо целого",
                detail="Оператор / даёт 2.5, а не 2. Для целого ответа в школе почти всегда нужен //.",
            )
        )

    if "vowels" in problem.tags and not re.search(r"[аеёиоуыэюяaeiou]", source, re.I):
        hints.append(
            Hint(
                kind="logic",
                title="Нет списка гласных",
                detail="Заведи набор гласных, например set('аеёиоуыэюя'), и считай символы, которые в него входят. Регистр лучше привести к одному.",
            )
        )

    if "palindrome" in problem.tags and "[::-1]" not in source and "reversed" not in source:
        hints.append(
            Hint(
                kind="logic",
                title="Строка не сравнивается с переворотом",
                detail="Палиндром: s == s[::-1]. Если регистр не важен, сначала сделай s = s.lower().",
            )
        )

    if "gcd" in problem.tags and not _has_modulo_any(tree) and "gcd" not in source:
        hints.append(
            Hint(
                kind="logic",
                title="Нет алгоритма Евклида",
                detail="НОД считают так: while b: a, b = b, a % b. Можно math.gcd(a, b), если импортируешь math.",
            )
        )

    if "binary" in problem.tags and "bin(" not in source and not _has_modulo_n(tree, 2):
        hints.append(
            Hint(
                kind="logic",
                title="Нет перевода в двоичную запись",
                detail="Либо print(bin(n)[2:]), либо собирай остатки n % 2, пока n > 0, и переверни строку.",
            )
        )

    if "power_of_two" in problem.tags and "&" not in source and not _has_modulo_n(tree, 2):
        hints.append(
            Hint(
                kind="logic",
                title="Степень двойки не проверена",
                detail="n — степень двойки, если n > 0 и n & (n - 1) == 0. Либо делить n на 2, пока делится, и проверить, что осталась единица.",
            )
        )

    if _while_true_without_break(tree):
        hints.append(
            Hint(
                kind="runtime",
                title="Возможен бесконечный цикл",
                detail="while True без break не остановится. Проверяющая система оборвёт программу по времени.",
            )
        )

    if "file_input" in problem.tags and not any(_called(node, "open") for node in calls):
        hints.append(
            Hint(
                kind="logic",
                title="Файл не открывается",
                detail="Числа №17 лежат в файле. Обычно так: data = [int(x) for x in open('17.txt')]. input() здесь не подставит файл.",
            )
        )

    if "pairs" in problem.tags and ("combinations" in source or "permutations" in source):
        hints.append(
            Hint(
                kind="logic",
                title="Пары должны быть соседними",
                detail="В №17 пара — это data[i] и data[i+1], а не combinations всех элементов. Иначе пар станет слишком много.",
            )
        )

    if "at_least_one" in problem.tags and re.search(r">\s*\w+\s+and\s+\w+\s*>", source):
        hints.append(
            Hint(
                kind="logic",
                title="Нужно хотя бы одно, не оба",
                detail="Условие «хотя бы один элемент» — это or, а не and. and отсекает пары, где подходит только одно число.",
            )
        )

    if "both" in problem.tags and re.search(r"or\s+\w+\s*<", source):
        hints.append(
            Hint(
                kind="logic",
                title="Нужны оба элемента",
                detail="Если в условии «оба меньше среднего», проверяй and, иначе в счётчик попадут лишние пары.",
            )
        )

    if "even_and_mod" in problem.tags and "37" in source and "74" not in source:
        hints.append(
            Hint(
                kind="logic",
                title="Чётно и кратно 37",
                detail="Число одновременно чётное и кратное 37 делится на 74. Проверка только % 37 пропускает нечётные кратные 37.",
            )
        )

    if "last_digit_abs" in problem.tags and "% 10" in source and "abs(" not in source:
        hints.append(
            Hint(
                kind="logic",
                title="Последняя цифра у отрицательных",
                detail="В Python (-15) % 10 == 5, но «оканчивается на 5» для отрицательных надёжнее писать abs(x) % 10.",
            )
        )

    hints.extend(_russian_keyword_hints(tree, source))
    return _unique(hints)


def _text_only_hints(source: str) -> list[Hint]:
    hints: list[Hint] = []
    if re.search(r"\bпринт\b", source):
        hints.append(
            Hint(
                kind="syntax",
                title="Русское слово вместо print",
                detail="Нужно латинское print, не «принт».",
            )
        )
    return hints


def _russian_keyword_hints(tree: ast.AST, source: str) -> list[Hint]:
    hints: list[Hint] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in RU_NAMES:
            hints.append(
                Hint(
                    kind="logic",
                    title="Русское имя вместо функции Python",
                    detail=f"«{node.id}» нужно заменить на {RU_NAMES[node.id]}.",
                    line=getattr(node, "lineno", None),
                )
            )
    for word, english in RU_WORDS.items():
        if re.search(rf"(^|[^\w]){word}([^\w]|$)", source) and english not in source.split():
            if word in {"и", "не"}:
                continue
            hints.append(
                Hint(
                    kind="syntax",
                    title="Русское слово вместо оператора",
                    detail=f"В Python пишут {english}, а не «{word}».",
                )
            )
            break
    if re.search(r"\bпринт\b", source):
        hints.append(
            Hint(
                kind="logic",
                title="Русское слово вместо print",
                detail="Нужно латинское print(...), иначе Python не узнает команду.",
            )
        )
    return hints


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
    return _has_modulo_n(tree, 10)


def _has_modulo_n(tree: ast.AST, value: int) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            if isinstance(node.right, ast.Constant) and node.right.value == value:
                return True
    return False


def _has_modulo_any(tree: ast.AST) -> bool:
    return any(isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod) for node in ast.walk(tree))


def _has_true_div(tree: ast.AST) -> bool:
    return any(isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) for node in ast.walk(tree))


def _print_inside_loop(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, (ast.For, ast.While)):
            for child in ast.walk(node):
                if isinstance(child, ast.Call) and _called(child, "print"):
                    return True
    return False


def _print_count(tree: ast.AST) -> int:
    return sum(1 for node in ast.walk(tree) if isinstance(node, ast.Call) and _called(node, "print"))


def _print_many_values(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _called(node, "print") and len(node.args) > 1:
            return True
    return False


def _while_true_without_break(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
            if not any(isinstance(child, ast.Break) for child in ast.walk(node)):
                return True
    return False


def _has_yes_no_problem(problem: Problem) -> bool:
    blob = f"{problem.output_format} {problem.statement}"
    return "YES" in blob or "EVEN" in blob


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
