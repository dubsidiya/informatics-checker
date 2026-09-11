from __future__ import annotations

from checker.models import Hint, Problem, TestResult, TraceStep
from checker.static_analyze import analyze_source


RUNTIME_HINTS = {
    "NameError": "Используется имя, которого нет. Проверь опечатку или что переменная создаётся до использования.",
    "IndexError": "Обращение к элементу за границей списка. Индексы идут с 0 до len(список) - 1.",
    "KeyError": "Нет такого ключа в словаре. Сначала проверь `if key in d`.",
    "TypeError": "Операция вызвана с не тем типом. Часто строку складывают с числом или берут len от int.",
    "ValueError": "Значение нельзя преобразовать. int() падает, если в строке не число или там сразу два числа.",
    "ZeroDivisionError": "Деление на ноль. Проверь знаменатель до операции.",
    "RecursionError": "Слишком глубокая рекурсия. Нет условия выхода или оно не достигается.",
    "TimeoutError": "Программа думает слишком долго. Ищи while, который никогда не заканчивается.",
    "EOFError": "input() вызывается чаще, чем есть строк во вводе. Лишний input или неверный формат чтения.",
    "AttributeError": "У объекта нет такого метода. Например, у int нет .split() — сначала нужна строка.",
}


def normalize(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def compact(text: str) -> str:
    return " ".join(normalize(text).split())


def same_answer(got: str, expected: str) -> bool:
    return normalize(got) == normalize(expected)


def format_only_mismatch(got: str, expected: str) -> bool:
    if same_answer(got, expected):
        return False
    return compact(got) == compact(expected) or normalize(got).lower() == normalize(expected).lower()


def numeric_pair(got: str, expected: str) -> tuple[float, float] | None:
    try:
        return float(compact(got)), float(compact(expected))
    except ValueError:
        return None


def build_hints(
    source: str,
    problem: Problem,
    tests: list[TestResult],
) -> list[Hint]:
    hints = list(analyze_source(source, problem))
    failing = [item for item in tests if item.verdict != "OK"]
    if not failing:
        return []

    first = failing[0]

    if first.verdict == "TLE":
        hints.append(
            Hint(
                kind="runtime",
                title="Превышено время",
                detail=RUNTIME_HINTS["TimeoutError"],
                line=first.error_line,
            )
        )
    elif first.verdict == "RE" and first.error_type:
        detail = RUNTIME_HINTS.get(
            first.error_type,
            first.error or "Программа упала во время выполнения.",
        )
        if first.error and first.error_type in RUNTIME_HINTS:
            detail = f"{detail} Сообщение Python: {first.error}"
        hints.append(
            Hint(
                kind="runtime",
                title=f"Ошибка выполнения: {first.error_type}",
                detail=detail,
                line=first.error_line,
            )
        )
        hints.extend(_runtime_specific_hints(first))
    elif first.verdict == "WA":
        hints.extend(_wrong_answer_hints(first, problem))

    visible_ok = [item for item in tests if not item.hidden]
    hidden_fail = [item for item in tests if item.hidden and item.verdict != "OK"]
    if visible_ok and all(item.verdict == "OK" for item in visible_ok) and hidden_fail:
        hints.append(
            Hint(
                kind="logic",
                title="Примеры проходят, скрытый тест — нет",
                detail="Алгоритм заточен под пример, а не под условие. Проверь крайние случаи: 0, 1, отрицательные, все элементы одинаковые.",
            )
        )

    return _dedupe(hints)


def _wrong_answer_hints(test: TestResult, problem: Problem) -> list[Hint]:
    hints: list[Hint] = []
    got = test.got
    expected = test.expected

    if not normalize(got):
        hints.append(
            Hint(
                kind="logic",
                title="Программа ничего не вывела",
                detail="Проверяющая система читает то, что напечатал print. Если расчёт есть, но print забыт — ответ считается пустым.",
            )
        )
        return hints

    if format_only_mismatch(got, expected):
        hints.append(
            Hint(
                kind="format",
                title="Ответ верный, формат нет",
                detail="Лишние пробелы, пустые строки или другой регистр (yes вместо YES). Печатай ровно то, что просят в условии.",
            )
        )
        return hints

    pair_hints = _two_number_hints(got, expected, problem)
    if pair_hints:
        return pair_hints

    numbers = numeric_pair(got, expected)
    if numbers:
        got_n, exp_n = numbers
        if got_n == exp_n:
            hints.append(
                Hint(
                    kind="format",
                    title="Число совпало, текст нет",
                    detail="Возможно, напечатано 5.0 вместо 5 или есть подпись вроде «ответ: 5». Нужно только число.",
                )
            )
        elif got_n == exp_n - 1 or got_n == exp_n + 1:
            hints.append(
                Hint(
                    kind="logic",
                    title="Ошибка на единицу",
                    detail="Ответ отличается на 1. Обычно виноват диапазон: range(n) вместо range(1, n + 1), или индекс len(a) вместо len(a) - 1.",
                )
            )
        elif "inclusive_n" in problem.tags and _looks_like_missing_last(got_n, exp_n, test.stdin):
            hints.append(
                Hint(
                    kind="logic",
                    title="Последнее число не вошло в сумму",
                    detail="Для N=5 сумма 1+2+3+4+5 = 15. Если получилось 10, цикл шёл до 4. Используй range(1, n + 1).",
                )
            )
        elif exp_n != 0 and abs(got_n) == abs(exp_n) and got_n != exp_n:
            hints.append(
                Hint(
                    kind="logic",
                    title="Не тот знак",
                    detail="Модуль числа верный, знак нет. Проверь, не теряется ли минус при чтении или в условии.",
                )
            )
        elif exp_n != 0 and (got_n == exp_n * 2 or got_n * 2 == exp_n):
            hints.append(
                Hint(
                    kind="logic",
                    title="Ответ в два раза больше или меньше",
                    detail="Часто дважды считают один и тот же элемент или делят не ту величину.",
                )
            )
        else:
            hints.append(
                Hint(
                    kind="logic",
                    title="На этом тесте получается другое число",
                    detail=_compare_numbers(got_n, exp_n, test),
                )
            )
        return hints

    if compact(got) in {"1", "0", "True", "False", "true", "false"} and compact(expected).upper() in {
        "YES",
        "NO",
        "EVEN",
        "ODD",
    }:
        hints.append(
            Hint(
                kind="format",
                title="Напечатано 1/0 вместо слова",
                detail=f"Ожидалось `{_preview(expected)}`, а программа напечатала `{_preview(got)}`. Нужны слова из условия, не True/False и не 1/0.",
            )
        )
        return hints

    if compact(got).upper() in {"YES", "NO", "EVEN", "ODD"} and compact(expected).upper() in {
        "YES",
        "NO",
        "EVEN",
        "ODD",
    }:
        if compact(got).upper() != compact(expected).upper():
            hints.append(
                Hint(
                    kind="logic",
                    title="Условие сработало наоборот",
                    detail="Программа отвечает YES, когда нужно NO, или наоборот. Проверь if: не перепутаны ли == и !=, not, in.",
                )
            )
        return hints

    if got.strip().startswith(("[", "(")) and not expected.strip().startswith(("[", "(")):
        hints.append(
            Hint(
                kind="format",
                title="Напечатан список или кортеж",
                detail="print(список) даёт [1, 2, 3]. Если нужны числа в строку — print(*список). Если нужен один ответ — печатай его, а не весь список.",
            )
        )
        return hints

    if compact(expected) in compact(got) and compact(got) != compact(expected):
        hints.append(
            Hint(
                kind="format",
                title="В выводе есть лишний текст",
                detail="Кроме ответа программа печатает подсказки вроде «Введите n». Для автоматической проверки нужен только ответ.",
            )
        )
        return hints

    hints.append(
        Hint(
            kind="logic",
            title="Вывод не совпал с эталоном",
            detail=f"Ожидалось `{_preview(expected)}`, получилось `{_preview(got)}`. Пройди алгоритм на этом вводе вручную и сравни с трассировкой ниже.",
        )
    )
    return hints


def _runtime_specific_hints(test: TestResult) -> list[Hint]:
    error = test.error or ""
    hints: list[Hint] = []
    if test.error_type == "ValueError" and "invalid literal" in error:
        hints.append(
            Hint(
                kind="runtime",
                title="int() получил не одно число",
                detail="Частая ошибка: int(input()) на строке «2 3». Сначала split(), потом map(int, ...).",
                line=test.error_line,
            )
        )
    if test.error_type == "TypeError" and "concatenate" in error:
        hints.append(
            Hint(
                kind="runtime",
                title="Складываются разные типы",
                detail="Нельзя сложить строку и число. Приведи оба значения к int или оба к str — в этой задаче почти наверняка к int.",
                line=test.error_line,
            )
        )
    if test.error_type == "TypeError" and "not iterable" in error:
        hints.append(
            Hint(
                kind="runtime",
                title="Цикл идёт по числу",
                detail="for x in n не работает, если n — int. Нужно for x in range(n) или сначала прочитать список.",
                line=test.error_line,
            )
        )
    if test.error_type == "TypeError" and "not subscriptable" in error:
        hints.append(
            Hint(
                kind="runtime",
                title="Индекс берут у числа",
                detail="n[0] нельзя, если n уже int. Либо работай с числом через % и //, либо сначала оставь строку.",
                line=test.error_line,
            )
        )
    if test.error_type == "FileNotFoundError":
        hints.append(
            Hint(
                kind="runtime",
                title="Файл не найден",
                detail="Для задач с файлом пиши open('17.txt') или имя из условия. На проверяльщике файл уже подложен, путь с рабочего стола не нужен.",
                line=test.error_line,
            )
        )
    if test.error_type == "ValueError" and "empty sequence" in error:
        hints.append(
            Hint(
                kind="runtime",
                title="max/min от пустого списка",
                detail="Нет ни одного элемента с нужным свойством: слишком строгий фильтр или не то условие кратности. Сначала собери список, потом проверяй, что он не пустой.",
                line=test.error_line,
            )
        )
    if test.error_type == "AttributeError" and "split" in error:
        hints.append(
            Hint(
                kind="runtime",
                title="split вызывают не у строки",
                detail="Сначала input(), и уже у этой строки .split(). У int метода split нет.",
                line=test.error_line,
            )
        )
    return hints



def _tokens(text: str) -> list[str]:
    return compact(text.replace(",", " ").replace(";", " ")).split()


def _two_number_hints(got: str, expected: str, problem: Problem) -> list[Hint]:
    exp = _tokens(expected)
    got_t = _tokens(got)
    if len(exp) != 2:
        return []
    if len(got_t) == 1:
        return [
            Hint(
                kind="format",
                title="В ответе должно быть два числа",
                detail="В №17 обычно печатают количество и затем min/max суммы: print(count, value). Сейчас программа вывела только одно число.",
            )
        ]
    if len(got_t) != 2:
        return []
    if got_t == exp and not same_answer(got, expected):
        return [
            Hint(
                kind="format",
                title="Числа верные, разделитель нет",
                detail="Нужны два числа через пробел, без запятой и без подписей.",
            )
        ]
    if got_t[0] == exp[0] and got_t[1] != exp[1]:
        return [
            Hint(
                kind="logic",
                title="Количество совпало, второе число нет",
                detail="Счётчик пар верный, а min/max суммы — нет. Часто берут сумму модулей вместо суммы, путают min и max или забывают отфильтровать пары для второго числа.",
            )
        ]
    if got_t[1] == exp[1] and got_t[0] != exp[0]:
        return [
            Hint(
                kind="logic",
                title="Второе число совпало, счётчик нет",
                detail="Проверь, что пары идут подряд (i и i+1), а не все сочетания. И не перепутаны ли «хотя бы одно», «оба», «ровно одно».",
            )
        ]
    if "ege17" in problem.tags or "pairs" in problem.tags:
        return [
            Hint(
                kind="logic",
                title="Оба числа ответа другие",
                detail="Пройди условие на бумаге: подряд ли элементы, какое сравнение со средним/эталоном, нужен ли abs для последней цифры. Ниже сравни свой вывод с эталоном.",
            )
        ]
    return []


def _looks_like_missing_last(got: float, expected: float, stdin: str) -> bool:
    try:
        n = int(stdin.split()[0])
    except (ValueError, IndexError):
        return False
    missing_n = expected - n
    missing_last_range = n * (n - 1) / 2
    return got in {missing_n, missing_last_range}


def _compare_numbers(got: float, expected: float, test: TestResult) -> str:
    shown_in = _preview(test.stdin.replace("\n", " / "))
    return (
        f"На вводе `{shown_in}` ожидалось { _as_int(expected) }, "
        f"программа напечатала { _as_int(got) }. "
        "Посмотри трассировку: на какой строке переменная стала не той."
    )


def _as_int(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)


def _preview(text: str, limit: int = 80) -> str:
    clean = compact(text)
    if len(clean) > limit:
        return clean[: limit - 1] + "…"
    return clean


def to_trace_steps(raw: list[dict]) -> list[TraceStep]:
    steps: list[TraceStep] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        line = item.get("line")
        local_vars = item.get("locals") or {}
        if not isinstance(line, int) or not isinstance(local_vars, dict):
            continue
        steps.append(
            TraceStep(
                line=line,
                locals={str(key): str(value) for key, value in local_vars.items()},
            )
        )
    return steps


def _dedupe(hints: list[Hint]) -> list[Hint]:
    seen: set[str] = set()
    result: list[Hint] = []
    for hint in hints:
        if hint.title in seen:
            continue
        seen.add(hint.title)
        result.append(hint)
    return result
