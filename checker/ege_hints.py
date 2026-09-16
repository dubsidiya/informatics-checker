from __future__ import annotations

import re

from checker.facts import CodeFacts, Outcome
from checker.models import Hint, Problem


def diagnose_ege(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    tags = set(problem.tags)
    if "ege8" in tags:
        return _ege8(facts, problem, outcome)
    if "ege9" in tags:
        return _ege9(facts, problem, outcome)
    if "ege13" in tags:
        return _ege13(facts, problem, outcome)
    if "ege14" in tags:
        return _ege14(facts, problem, outcome)
    if "ege16" in tags:
        return _ege16(facts, problem, outcome)
    if "ege23" in tags:
        return _ege23(facts, problem, outcome)
    if "ege25" in tags:
        return _ege25(facts, problem, outcome)
    return []


def hint(title: str, detail: str, kind: str = "logic", weight: int = 80) -> tuple[int, Hint]:
    return weight, Hint(kind=kind, title=title, detail=detail)


def _ensure(found: list[tuple[int, Hint]], title: str, detail: str, weight: int = 80) -> list[tuple[int, Hint]]:
    if not any(item[0] >= 80 for item in found):
        found.append(hint(title, detail, weight=weight))
    return found


def _tokens(text: str) -> list[str]:
    return " ".join((text or "").replace(",", " ").replace(";", " ").split()).split()


def _lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _ege8(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    src = facts.source
    statement = problem.statement.lower()
    found: list[tuple[int, Hint]] = []
    repeats_forbidden = any(word in statement for word in ("различн", "не повторя", "все цифры разл"))
    if "permutations" in src and "product" not in src and "repeat" not in src and not repeats_forbidden:
        found.append(hint(
            "Буквы могут повторяться",
            "permutations берёт каждую букву один раз. Если буквы слова можно брать снова, нужен product(..., repeat=n) или вложенные циклы.",
            weight=90,
        ))
    if "combinatorics" in problem.tags and "product" not in src and "permutations" not in src and not facts.nested_fors and "for " not in src:
        found.append(hint(
            "Нет перебора слов",
            "В №8 обычно itertools.product по алфавиту или вложенные циклы. Сейчас перебора не видно.",
            weight=86,
        ))
    letters = re.search(r"['\"]([А-ЯЁA-Z]{2,})['\"]", src)
    if "алфавитн" in statement and letters:
        alphabet = letters.group(1)
        if alphabet != "".join(sorted(alphabet)) and "sorted(" not in src:
            found.append(hint(
                "Алфавит мог быть не в том порядке",
                "Слова нумеруют в алфавитном порядке букв. Сначала отсортируй алфавит: product(sorted('...'), repeat=n).",
                weight=82,
            ))
    got, exp = outcome.got.strip(), outcome.expected.strip()
    if got.isdigit() and exp.isalpha():
        found.append(hint(
            "Нужно слово, не номер",
            "В условии просят само слово/код, а программа напечатала число.",
            kind="format",
            weight=88,
        ))
    elif exp.isdigit() and got.isalpha():
        found.append(hint(
            "Нужен номер, не слово",
            "В условии просят номер слова в списке, а программа напечатала само слово.",
            kind="format",
            weight=88,
        ))
    elif got.isalpha() and exp.isalpha() and got != exp:
        found.append(hint(
            "В списке другое слово",
            f"Ожидалось `{exp}`, получилось `{got}`. Проверь длину кода, нумерацию с 1 и что буквы идут с повторами через product.",
            weight=86,
        ))
    return _ensure(
        found,
        "Перебор слов считает другое количество",
        "В №8 обычно product/permutations по алфавиту, запрет на первую цифру 0 и условие на соседние буквы. Сверь это с формулировкой.",
    )


def _ege9(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    src = facts.source.replace(" ", "")
    files = " ".join(problem.files)
    found: list[tuple[int, Hint]] = []
    if not facts.has_open:
        found.append(hint(
            "Файл таблицы не открывается",
            "Строки №9 лежат в csv/txt. Обычно: for line in open('9-160.csv'): a = list(map(int, line.split(';'))).",
            weight=92,
        ))
    csv_file = ".csv" in files
    txt_file = ".txt" in files
    if csv_file and facts.has_open and ("split(',')" in src or 'split(",")' in src):
        found.append(hint(
            "Разделитель, скорее всего, точка с запятой",
            "В выгрузке Полякова числа разделены ';'. split(',') на такой строке даст один кусок.",
            weight=88,
        ))
    if txt_file and facts.has_open and ("split(',')" in src or "split(';')" in src or 'split(";")' in src):
        found.append(hint(
            "В этом файле числа через пробел или таб",
            "Для 9-258.txt пиши line.split() без запятой и точки с запятой.",
            weight=88,
        ))
    if "макс" in problem.statement.lower() and facts.uses_min and not facts.uses_max:
        found.append(hint("Ищется минимум, не максимум", "В условии просят максимальную сумму/значение, а в коде min.", weight=86))
    return _ensure(
        found,
        "Строки таблицы отбираются иначе",
        "Сверь оба условия из формулировки: повторы, сумма/среднее, медиана, треугольник. Частая ошибка — не тот split или сравнение max со суммой остальных.",
    )


def _ege13(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    src = facts.source
    found: list[tuple[int, Hint]] = []
    got, exp = outcome.got.strip(), outcome.expected.strip()
    got_digits = re.sub(r"\D", "", got)
    exp_digits = re.sub(r"\D", "", exp)
    if "." in exp and "." not in got and any(ch.isdigit() for ch in got):
        found.append(hint(
            "В IP нужны точки",
            f"Ожидалось `{exp}`, получилось `{got}`. Для обычной записи октеты разделяют точками. Без точек пишут только если это прямо сказано в условии.",
            kind="format",
            weight=92,
        ))
    elif "." not in exp and "." in got:
        found.append(hint(
            "В ответе не должно быть точки",
            "В этой задаче IP просят без разделителей, как в примере 11122344.",
            kind="format",
            weight=90,
        ))
    elif got_digits == exp_digits and got != exp:
        found.append(hint(
            "Цифры те, разделитель нет",
            f"Ожидалось `{exp}`, получилось `{got}`. Точки ставят только если это просят в условии.",
            kind="format",
            weight=90,
        ))
    elif "." in got and "." in exp and got != exp:
        found.append(hint(
            "Октеты разрезаны иначе",
            f"Ожидалось `{exp}`, получилось `{got}`. Каждый октет 0…255, без ведущих нулей, сумма длин — вся строка цифр.",
            weight=88,
        ))
    if "маск" in problem.statement.lower() and "ipaddress" not in src and "&" not in src:
        found.append(hint(
            "Маску удобно проверять по префиксу",
            "Перебери длину префикса /1../31: ip_network(f'{узел}/{p}', strict=False) и сравни адрес сети. Маска должна быть из единиц слева, без дыр.",
            weight=82,
        ))
    return _ensure(
        found,
        "Неверный IP или байт маски",
        "Сверь адрес узла, адрес сети и маску. Часто ищут третий байт маски или число единиц, а печатают другой октет.",
    )


def _ege14(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    src = facts.source
    found: list[tuple[int, Hint]] = []
    got_tokens = _tokens(outcome.got)
    exp_tokens = _tokens(outcome.expected)
    if "int(" in src and "," not in src.split("int(")[-1][:20] and "while" not in src and "%" not in src:
        found.append(hint(
            "Нужно перевести в другую систему",
            "int(s, base) читает из системы base. Чтобы посчитать цифры в системе b, делите n % b, пока n > 0.",
            weight=80,
        ))
    if got_tokens == exp_tokens and outcome.got.strip() != outcome.expected.strip():
        found.append(hint(
            "Числа верные, разделитель нет",
            "В ответе основания через запятую с пробелом, как в условии: 6, 9, 18.",
            kind="format",
            weight=90,
        ))
    elif "," in outcome.expected and got_tokens != exp_tokens:
        found.append(hint(
            "Не те основания или порядок",
            f"Ожидалось `{outcome.expected.strip()}`, получилось `{outcome.got.strip()}`. Перебери основание от 5 вверх и проверь последнюю цифру; выводи по возрастанию через запятую.",
            weight=82,
        ))
    return _ensure(
        found,
        "Основание или цифры считаются иначе",
        "В №14 либо перевод в систему счисления и подсчёт цифры, либо перебор оснований. Сверь основание, какую цифру считают и формат вывода.",
    )


def _ege16(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    src = facts.source
    found: list[tuple[int, Hint]] = []
    wants_tail = "последн" in problem.statement.lower() or "цифр" in problem.output_format.lower()
    if wants_tail:
        try:
            g, e = int(outcome.got_tokens[0]), int(outcome.exp_tokens[0])
            if abs(g) > abs(e) and str(g).endswith(str(e)):
                found.append(hint(
                    "Нужны только последние цифры",
                    "Полное F(n) слишком длинное. В условии просят последние 4 или 6 цифр: ответ % 10**k.",
                    weight=93,
                ))
        except (ValueError, IndexError):
            pass
    if src.count("def ") >= 1 and "lru_cache" not in src and "for " not in src and "F[" not in src and "f[" not in src:
        found.append(hint(
            "Рекурсия без памяти",
            "На больших n наивная рекурсия не успеет или упрётся в глубину. Считай снизу вверх массивом или @lru_cache.",
            weight=88,
        ))
    return _ensure(
        found,
        "Рекуррентная функция считает другое значение",
        "Сверь ветки чёт/нечёт, границы F(n) и не забыт ли остаток % 10**k, если просят последние цифры.",
    )


def _ege23(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    src = facts.source
    found: list[tuple[int, Hint]] = []
    statement = problem.statement.lower()
    if "не содерж" in statement or "без " in statement:
        if "if " not in src or ("==" not in src and "!=" not in src):
            found.append(hint(
                "Запрещённое число не отсекается",
                "Траектория не должна проходить через указанное число: если cur == запрет, возвращай 0.",
                weight=86,
            ))
    if "содерж" in statement and "не содерж" not in statement:
        if src.count("def ") == 1 and "->" not in problem.statement:
            found.append(hint(
                "Траектория через обязательную точку",
                "Если программа должна пройти через число X, считай пути start→X и X→end отдельно и перемножи.",
                weight=80,
            ))
    if "lru_cache" not in src and "a[" not in src and "dp" not in src.lower() and "f[" not in src.lower():
        found.append(hint(
            "Считай динамикой или с кэшем",
            "Число программ считают рекурсией с @lru_cache или массивом dp[x] += dp[prev]. Без памяти на 23.343 легко не уложиться во время.",
            weight=82,
        ))
    return _ensure(
        found,
        "Число программ посчитано иначе",
        "Команды исполнителя, старт и финиш, запрещённая или обязательная точка. Без кэша легко пропустить часть траекторий или не уложиться во время.",
    )


def _ege25(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    src = facts.source
    found: list[tuple[int, Hint]] = []
    got_lines = _lines(outcome.got)
    exp_lines = _lines(outcome.expected)
    if len(exp_lines) > 1 and len(got_lines) == 1:
        found.append(hint(
            "В ответе несколько строк",
            "Каждое найденное число — отдельная строка (часто само число и делители). Сейчас напечатана одна строка.",
            kind="format",
            weight=88,
        ))
    if exp_lines and got_lines:
        exp_w = len(exp_lines[0].split())
        got_w = len(got_lines[0].split())
        if exp_w != got_w:
            found.append(hint(
                f"В строке нужно {exp_w} числа",
                f"Эталон начинается с `{exp_lines[0]}`, программа печатает `{got_lines[0]}`. Для делителей обычно print(*divs), для маски — число и частное.",
                kind="format",
                weight=88,
            ))
    if len(exp_lines) > 1 and got_lines == exp_lines[:-1]:
        found.append(hint(
            "Потеряна последняя строка",
            "Набор почти совпал, не хватает последнего числа. range не включает правый конец отрезка — пиши range(A, B + 1).",
            weight=92,
        ))
    if "ровно" in problem.statement and "4" in problem.statement and "len(" in src:
        found.append(hint(
            "Ровно 4 делителя",
            "Число имеет ровно 4 делителя, если это p^3 или p*q (два простых). Не забудь 1 и само число.",
            weight=80,
        ))
    if "?" in problem.statement or "*" in problem.statement:
        if "range(" in src and "10**9" in src.replace(" ", ""):
            found.append(hint(
                "Не перебирай до миллиарда",
                "Маску 1?34567?9 лучше собрать генерацией цифр на местах ? и *, а не циклом до 10**9.",
                weight=90,
            ))
    bounds = re.search(r"\[(\d+)\s*[;,]\s*(\d+)\]", problem.statement)
    if bounds and facts.range_literals:
        start, end = int(bounds.group(1)), int(bounds.group(2))
        for left, right, _line in facts.range_literals:
            if left == start and start < right <= end:
                found.append(hint(
                    "range не включает конец отрезка",
                    f"Отрезок [{start}; {end}] включительный. range({start}, {end}) остановится на {end - 1}. Пиши range({start}, {end} + 1).",
                    weight=91,
                ))
                break
            if left == start + 1 and right in {end, end + 1}:
                found.append(hint(
                    "range отрезает начало отрезка",
                    f"Отрезок начинается с {start}, а цикл стартует с {left}.",
                    weight=88,
                ))
                break
    return _ensure(
        found,
        "Другой набор чисел, делителей или маски",
        "В №25 либо отрезок и число делителей, либо маска ?/*. Сверь границы range(A, B + 1), что печатается в строке, и не перебирай до 10**9.",
    )
