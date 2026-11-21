from __future__ import annotations

import re

from checker.diagnose import diagnose
from checker.facts import range_misses_end
from checker.models import Hint, Problem, TestResult, TraceStep


# A bare numeric or text mismatch is true, but it hides the bug the topic
# checker already saw in the code. These titles are allowed to become the
# headline the student reads in «Что сделать».
_GENERIC_WA_TITLES = frozenset({
    "На этом тесте получается другое число",
    "Текстовый ответ отличается",
    "Ошибка на единицу",
    "Ответ в два раза больше или меньше",
    "Число совпало, текст нет",
    "В выводе есть лишний текст",
    "Программа ничего не вывела",
    "Оба числа ответа другие",
    "Количество совпало, второе число нет",
    "Второе число совпало, счётчик нет",
    "Последнее число не вошло в сумму",
})
_FACT_HINTS_AHEAD = frozenset({
    "Степень не из списка смежности",
    "Степень взята не из той ячейки",
    "Ребро записано только в одну сторону",
    "Граница попала внутрь",
    "Посчитана площадь вместо длины пути",
    "В длине пути нет двойки",
    "Напечатана шестнадцатеричная запись",
    "Ведущие нули кода пропали",
    "Двоичная строка стала числом",
    "Число цветов принято за биты",
    "Напечатаны биты, не байты",
    "Секунды округлены вниз",
    "Слово ищется как подстрока",
    "Регистр не нормализован",
    "Знак препинания прилип к слову",
    "Неверный разделитель таблицы",
    "Считаются рейсы, не груз",
    "В сумму попал и вывоз",
    "В сумму попали зависимые процессы",
    "Считается путь по зависимостям, не сумма",
    "Из числа процессов вычли зависимые",
    "Посчитаны процессы без зависимости",
    "Критический путь не вычисляется",
    "Число значений принято за биты",
    "Биты не переведены в целые байты",
    "В формуле and вместо or",
    "В формуле потеряно not",
    "Чтение не до нуля",
    "Произведение начато с нуля",
    "Напечатан только первый делитель",
    "Делители считаются с единицы",
    "Оставлены нечётные",
    "Чётные не отобраны",
    "Кратность простого не снята",
    "В список не попала единица",
    "Делители ищут от 2 до корня",
    "Импликация записана как равенство",
    "Принадлежность отрезку через равенство",
    "В формуле ∨ записана как and",
    "Повторы слов не убраны",
    "Килобайт принят за 1000",
    "В csv нужна точка с запятой",
    "В txt нужны пробелы",
    "Склеились две строки",
    "Вычитание вместо сложения",
    "В формуле минус вместо плюса",
    "В формуле пропал + 1",
    "В print есть лишнее слово",
    "Пустой print()",
    "Часть ввода осталась строкой",
    "input() без int",
    "max сравнивает строки",
    "В формуле or вместо and",
    "Получилось «хотя бы одно», а нужно «оба»",
    "Нужны оба условия",
    "Нужно ровно одно положительное",
    "Шаг уходит от цели",
    "Ход записан с минусом",
    "Граница отрезка через равенство",
    "В проверке октета or вместо and",
    "Октет сравнивается через равенство",
    "Шаг цепочки не прибавляет единицу",
    "Делители ищут до самого числа",
    "Из клетки вычитают, а не прибавляют",
    "В формуле ∧ записана как or",
    "В условии строки or вместо and",
    "В отборе or вместо and",
    "В сумму попал тот же сосед",
    "range не включает конец отрезка",
    "Буквы могут повторяться",
    "В формуле потеряно + n + 3",
    "Нужно пройти строку посимвольно",
    "Стоит and вместо or",
    "range не доходит до n",
    "В фильтре таблицы or вместо and",
    "Не тот split у input",
    "Шаг по таблице со знаком минус",
})


def _prefer_fact_hint(generic: list[Hint], topic: list[Hint]) -> list[Hint]:
    if not generic or generic[0].title not in _GENERIC_WA_TITLES:
        return generic
    for item in topic:
        if item.title in _FACT_HINTS_AHEAD:
            return [item, *generic]
    return generic


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
    failing = [item for item in tests if item.verdict != "OK"]
    if not failing:
        return []

    first = failing[0]
    hints: list[Hint] = []

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
            "Программа упала во время выполнения.",
        )
        if first.error and first.error_type in RUNTIME_HINTS and not first.hidden:
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
    if first.verdict in {"WA", "RE", "TLE"}:
        # Give priority to observable output mistakes (off-by-one, sign,
        # two-number order, YES/NO and similar) before broad topic hints.
        # A fact-based topic title may still go first: otherwise the student
        # is told to fix range when the graph edge was stored one way.
        topic_hints = diagnose(source, problem, tests)
        wa_hints = []
        named = [
            item for item in topic_hints
            if item.title not in _GENERIC_WA_TITLES and item.title != "Программа ничего не вывела"
        ]
        if first.verdict == "WA" and not first.hidden:
            wa_hints = _wrong_answer_hints(first, problem, source)
        elif first.verdict == "WA" and not normalize(first.got or "") and not named:
            wa_hints = _wrong_answer_hints(first, problem, source)
        hints.extend(_prefer_fact_hint(wa_hints, topic_hints))
        hints.extend(topic_hints)

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


def _range_misses_end(source: str) -> bool:
    return range_misses_end(source)


def _untyped_split(source: str) -> bool:
    return bool(re.search(r"=\s*input\(\)\.split\(\)", source))


def _real_sign_bug(source: str, got_n: float) -> bool:
    compact = re.sub(r"\s+", "", source)
    if got_n == -1 and ("else-1" in compact or "else:-1" in compact):
        return False
    return True


def _wrong_answer_hints(test: TestResult, problem: Problem, source: str = "") -> list[Hint]:
    hints: list[Hint] = []
    got = test.got
    expected = test.expected

    if not normalize(got):
        hints.append(
            Hint(
                kind="logic",
                title="Программа ничего не вывела",
                detail="Проверяльщик читает то, что напечатал print. Пустой print() или print без значения даёт пустой ответ.",
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
        elif (got_n == exp_n - 1 or got_n == exp_n + 1) and _range_misses_end(source):
            hints.append(
                Hint(
                    kind="logic",
                    title="Ошибка на единицу",
                    detail="В range не хватает последнего значения. Если n должно войти, пиши range(1, n + 1) или range(A, B + 1).",
                )
            )
        elif (
            "inclusive_n" in problem.tags
            and _range_misses_end(source)
            and _looks_like_missing_last(got_n, exp_n, test.stdin)
        ):
            hints.append(
                Hint(
                    kind="logic",
                    title="Последнее число не вошло в сумму",
                    detail="Цикл не дошёл до n. Замени конец range на `n + 1`.",
                )
            )
        elif exp_n != 0 and abs(got_n) == abs(exp_n) and got_n != exp_n and _real_sign_bug(source, got_n):
            hints.append(
                Hint(
                    kind="logic",
                    title="Не тот знак",
                    detail="Число совпало по модулю, но знак другой. Если в условии модуль, оберни выражение в abs.",
                )
            )
        elif exp_n != 0 and (got_n == exp_n * 2 or got_n * 2 == exp_n):
            hints.append(
                Hint(
                    kind="logic",
                    title="Ответ в два раза больше или меньше",
                    detail="Ответ отличается ровно в два раза. Ищи лишнюю двойку: * 2, / 2 или пропущенный abs.",
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
        if compact(got).upper() != compact(expected).upper() and not _untyped_split(source):
            hints.append(
                Hint(
                    kind="logic",
                    title="Условие сработало наоборот",
                    detail="Программа отвечает YES, когда нужно NO, или наоборот. Проверь if: не перепутаны ли == и !=, not, in.",
                )
            )
            return hints
        if _untyped_split(source):
            pass
        else:
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
            title="Текстовый ответ отличается",
            detail=(
                f"Ожидалось `{_preview(expected)}`, получилось `{_preview(got)}`. "
                "Сверь длину ответа, порядок символов, нумерацию и условие отбора."
            ),
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
    tags = set(problem.tags)
    if len(got_t) == 1:
        if "closed_range" in tags:
            detail = "Нужны два числа через пробел: количество подходящих чисел и затем максимум (или минимум) из них."
        elif "pairs" in tags or "triples" in tags:
            detail = "Нужны два числа: сколько пар (троек) подошло и затем min/max суммы. Сейчас программа вывела только одно число."
        else:
            detail = "В ответе должно быть два числа через пробел, как в условии."
        return [Hint(kind="format", title="В ответе должно быть два числа", detail=detail)]
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
    if got_t == [exp[1], exp[0]] and exp[0] != exp[1]:
        return [
            Hint(
                kind="format",
                title="Числа ответа переставлены",
                detail=(
                    f"Напечатано `{_preview(got)}`, нужно `{_preview(expected)}`. "
                    "Сверь порядок величин в формате ответа: первое число — первый пункт условия, второе — второй."
                ),
            )
        ]
    if got_t[0] == exp[0] and got_t[1] != exp[1]:
        return [
            Hint(
                kind="logic",
                title="Количество совпало, второе число нет",
                detail=_count_ok_value_wrong(tags),
            )
        ]
    if got_t[1] == exp[1] and got_t[0] != exp[0]:
        return [
            Hint(
                kind="logic",
                title="Второе число совпало, счётчик нет",
                detail=_count_wrong_value_ok(got_t[0], exp[0], tags),
            )
        ]
    if "ege17" in tags or "pairs" in tags or "closed_range" in tags:
        return [
            Hint(
                kind="logic",
                title="Оба числа ответа другие",
                detail=_both_wrong(tags),
            )
        ]
    return [
        Hint(
            kind="logic",
            title="Оба числа ответа другие",
            detail=(
                f"Получилось `{_preview(got)}`, а нужно `{_preview(expected)}`. "
                "Проверь отдельно вычисление первого и второго показателя и порядок их печати."
            ),
        )
    ]


def _count_ok_value_wrong(tags: set[str]) -> str:
    if "closed_range" in tags:
        return (
            "Чисел отобрали столько, сколько нужно, а максимум/минимум другой. "
            "Экстремум обновляй внутри того же if, и не путай min с max."
        )
    if "pairs" in tags or "triples" in tags:
        return (
            "Счётчик верный, а min/max суммы нет. Часто берут сумму модулей вместо суммы, "
            "путают min и max или считают второе число по другому набору пар."
        )
    return "Первое число ответа верное, второе нет. Перечитай, что именно просят вывести вторым."


def _count_wrong_value_ok(got_count: str, exp_count: str, tags: set[str]) -> str:
    extra = _int_or_none(got_count)
    need = _int_or_none(exp_count)
    more = extra is not None and need is not None and extra > need

    if "closed_range" in tags:
        if more:
            return (
                "Максимум тот же, а чисел больше. "
                "Замени в if пропущенное `x % k != 0`."
            )
        return (
            "Максимум тот же, а чисел меньше. "
            "Замени конец range на `B + 1`, если отрезок включительный."
        )

    if "pairs" in tags or "triples" in tags:
        who = "пар" if "pairs" in tags else "троек"
        how = ""
        if "at_least_one" in tags:
            how = " «Хотя бы одно» — это or, не and."
        elif "both" in tags:
            how = " «Оба» — это and, не or."
        elif "exactly_one" in tags:
            how = " «Ровно одно» — два условия через != / xor, не оба сразу."
        if more:
            return f"Второе число верное, а {who} больше. Условие отбора шире.{how}"
        return f"Второе число верное, а {who} меньше. Условие отбора уже.{how}"

    return "Второе число совпало, а первое нет. Замени оператор в фильтре на тот, что в условии: and или or."


def _both_wrong(tags: set[str]) -> str:
    if "closed_range" in tags:
        return "И количество, и максимум другие. Замени конец range на `B + 1`, если отрезок включительный."
    if "pairs" in tags:
        return (
            "Оба числа другие. Пара в №17 — это соседние элементы data[i] и data[i+1], "
            "а не произвольные элементы списка. Дальше сверь сравнение со средним или эталоном."
        )
    return "Оба числа другие. Пройди условие на этом наборе вручную и сравни с эталоном."


def _int_or_none(text: str) -> int | None:
    try:
        return int(text)
    except ValueError:
        return None


def _looks_like_missing_last(got: float, expected: float, stdin: str) -> bool:
    try:
        n = int(stdin.split()[0])
    except (ValueError, IndexError):
        return False
    missing_n = expected - n
    missing_last_range = n * (n - 1) / 2
    return got in {missing_n, missing_last_range}


def _compare_numbers(got: float, expected: float, test: TestResult) -> str:
    _ = (got, expected, test)
    return "Число на этом тесте другое. Замени в строке с ответом тот оператор, который не совпадает с действием: `+` или `-`."


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
