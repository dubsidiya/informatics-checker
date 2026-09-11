from __future__ import annotations

from checker.facts import (
    CodeFacts,
    Outcome,
    closed_range_bounds,
    example_outputs,
    extract_facts,
    extract_outcome,
    parse_div_filters,
)
from checker.models import Hint, Problem, TestResult


def diagnose(source: str, problem: Problem, tests: list[TestResult]) -> list[Hint]:
    facts = extract_facts(source)
    outcome = extract_outcome(tests)
    if outcome is None:
        return []

    findings = _common(facts, problem, outcome)
    handler = HANDLERS.get(problem.id)
    if handler:
        findings.extend(handler(facts, problem, outcome))
    elif "closed_range" in problem.tags:
        findings.extend(_ege_range(facts, problem, outcome))
    elif "ege17" in problem.tags:
        findings.extend(_ege_file(facts, problem, outcome))

    if outcome.first.verdict == "WA" and not any(weight >= 80 for weight, _ in findings):
        findings.append(
            hint(
                "Вывод не совпал с эталоном",
                f"Ожидалось `{_preview(outcome.expected)}`, получилось `{_preview(outcome.got)}`. "
                "Пройди условие на этом вводе вручную — автоматический разбор не нашёл точечной причины.",
                weight=60,
            )
        )
    return _dedupe(_sorted(findings))[:3]


def hint(title: str, detail: str, kind: str = "logic", line: int | None = None, weight: int = 80) -> tuple[int, Hint]:
    return weight, Hint(kind=kind, title=title, detail=detail, line=line)


def _sorted(items: list[tuple[int, Hint]]) -> list[Hint]:
    return [item[1] for item in sorted(items, key=lambda pair: pair[0], reverse=True)]


def _dedupe(hints: list[Hint]) -> list[Hint]:
    seen: set[str] = set()
    result: list[Hint] = []
    for item in hints:
        if item.title in seen:
            continue
        seen.add(item.title)
        result.append(item)
    return result


def _preview(text: str, limit: int = 80) -> str:
    clean = " ".join((text or "").split())
    if len(clean) > limit:
        return clean[: limit - 1] + "..."
    return clean


def _common(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found: list[tuple[int, Hint]] = []
    tags = set(problem.tags)

    if not facts.has_print:
        found.append(hint("Нет вывода", "В программе нет print. Проверяющая система читает только напечатанное.", weight=95))

    if outcome.empty and facts.has_print:
        found.append(hint("Программа ничего не вывела", "print не сработал на этом тесте. Проверь, не стоит ли он внутри if, который не выполняется.", weight=90))

    if outcome.format_only:
        found.append(hint("Ответ верный, формат нет", "Лишние пробелы, пустая строка или другой регистр. Печатай ровно то, что просят в условии.", kind="format", weight=92))

    if "integers_from_input" in tags and not facts.has_input and not facts.has_open:
        found.append(hint("Ввод не читается", "Числа нужно брать из input(), а не записывать константой.", weight=88))

    if (
        "integers_from_input" in tags
        and facts.has_input
        and not facts.has_int
        and not facts.has_map
        and not facts.reverse_slice
        and problem.id not in {"reverse-digits", "to-binary", "repeat-string"}
    ):
        found.append(hint("input() вернул строку", "Без int(...) или map(int, ...) «2» + «3» склеивается в 23.", weight=90))

    if facts.raw_input_add:
        found.append(hint("Складываются строки", "input() + input() склеивает текст. Сначала преврати оба значения в int.", weight=90))

    if "file_input" in tags and not facts.has_open:
        found.append(hint("Файл не открывается", "Числа этой задачи лежат в файле: data = [int(x) for x in open('17.txt')].", weight=90))

    examples = example_outputs(problem)
    if facts.hardcoded_loop and facts.constant_prints:
        if any(item in examples or item == outcome.expected.strip() for item in facts.constant_prints):
            found.append(hint("Ответ записан константой", "Программа печатает число из примера, а не считает его. На другом наборе так не сработает.", weight=86))

    if "two_int_out" in tags and len(outcome.got_tokens) == 1 and len(outcome.exp_tokens) == 2:
        if "closed_range" in tags:
            detail = "Нужны два числа через пробел: сколько чисел подошло и затем максимум из них."
        elif "pairs" in tags or "triples" in tags:
            detail = "Нужны два числа: сколько пар или троек подошло и затем min/max из условия."
        else:
            detail = "В ответе должно быть два числа через пробел, как в условии."
        found.append(hint("В ответе должно быть два числа", detail, kind="format", weight=88))

    if "single_int_out" in tags and any(count > 1 for count in facts.print_value_counts):
        found.append(hint("print печатает несколько значений", "В ответе нужно одно число. print(a, b) система не примет.", kind="format", weight=84))

    if "print_once" in tags and facts.print_inside_loop:
        found.append(hint("print стоит внутри цикла", "Счётчик или сумму выведи один раз после цикла, не на каждом шаге.", kind="format", weight=85))

    return found


def _yes_no_words(outcome: Outcome) -> list[tuple[int, Hint]]:
    got = outcome.got.strip()
    exp = outcome.expected.strip().upper()
    if got in {"0", "1", "True", "False", "true", "false"} and exp in {"YES", "NO", "EVEN", "ODD"}:
        return [hint("Напечатано 1/0 вместо слова", f"Ожидалось `{outcome.expected.strip()}`, программа напечатала `{got}`. Нужны слова из условия.", kind="format", weight=94)]
    if got.upper() in {"YES", "NO"} and exp in {"YES", "NO"} and got.upper() != exp:
        return [hint("Условие сработало наоборот", "Программа отвечает YES, когда нужно NO, или наоборот. Проверь if: == и !=, not, in.", weight=88)]
    return []


def _sum_two(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found = []
    if facts.has_split and not facts.has_int and not facts.has_map:
        found.append(hint("Склеились две строки", "После split() элементы всё ещё текст. Нужно map(int, input().split()), иначе 2 и 3 дадут 23, а не 5.", weight=93))
    if outcome.sign_only:
        found.append(hint("Не тот знак", "Модуль числа верный. Проверь, не вычитаешь ли вместо сложения.", weight=80))
    return found


def _sum_1_n(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found = []
    if facts.has_range and "n + 1" not in facts.source and "n+1" not in facts.source:
        found.append(hint("range не включает N", "range(n) даёт 0 ... n-1. Для N=5 сумма будет 10, а не 15. Нужен range(1, n + 1) или n * (n + 1) // 2.", weight=93))
    if outcome.off_by_one:
        found.append(hint("Ошибка на единицу", "Для суммы 1...N обычно виноват диапазон: забыли n или начали с 0.", weight=80))
    return found


def _max_three(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if facts.uses_min and not facts.uses_max:
        return [hint("Ищется минимум, не максимум", "В условии нужно наибольшее из трёх. Сейчас вызывается min.", weight=94)]
    return []


def _even_odd(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found = []
    got = outcome.got.strip()
    if got in {"0", "1", "True", "False"}:
        found.append(hint("Нужны слова EVEN/ODD", f"Программа напечатала `{got}`. В условии просят EVEN или ODD, не 1/0.", kind="format", weight=94))
    if 2 not in facts.moduli and "%" not in facts.source:
        found.append(hint("Чётность не проверяется", "Число чётное, если n % 2 == 0.", weight=88))
    if got.upper() in {"EVEN", "ODD"} and got.upper() != outcome.expected.strip().upper():
        found.append(hint("EVEN и ODD перепутаны", "Условие сработало наоборот. Проверь, не стоит ли % 2 == 1 там, где нужен == 0.", weight=90))
    return found


def _last_digit(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if facts.floor_div and 10 not in facts.moduli:
        return [hint("Взято // 10 вместо % 10", "// 10 отбрасывает последнюю цифру. Последняя цифра — это n % 10.", weight=94)]
    if 10 not in facts.moduli and "[-1]" not in facts.source:
        return [hint("Последняя цифра не выделена", "Нужно n % 10 или int(str(n)[-1]).", weight=88)]
    return []


def _abs_diff(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if not facts.uses_abs:
        return [hint("Нет модуля разности", "a - b бывает отрицательным. Нужен abs(a - b).", weight=94)]
    return []


def _school_grade(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    missing = [item for item in (50, 70, 90) if str(item) not in facts.source]
    if missing:
        return [hint("Не все границы оценки", "По условию: меньше 50 -> 2, от 50 до 69 -> 3, от 70 до 89 -> 4, от 90 -> 5. В коде нет границы " + ", ".join(str(item) for item in missing) + ".", weight=93)]
    if "51" in facts.source or "<= 50" in facts.source or "<=50" in facts.source:
        return [hint("Граница 50 сдвинута", "50 баллов — это уже 3, не 2. Пиши if n < 50.", weight=90)]
    return [hint("Оценка не совпала на этом балле", f"На вводе `{_preview(outcome.first.stdin)}` ждали {outcome.expected.strip()}, получилось {outcome.got.strip()}. Сверь пороги 50, 70, 90.", weight=70)]


def _repeat_string(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found = []
    if facts.input_count < 2:
        found.append(hint("Прочитана только одна строка", "Сначала input() для S, затем второй input() для K.", weight=88))
    if not facts.string_repeat and "+" in facts.source:
        found.append(hint("Строка складывается, а не повторяется", "Нужно S * K. Плюс склеивает S и текст числа K.", weight=92))
    return found


def _min_of_n(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if facts.uses_max and not facts.uses_min:
        return [hint("Ищется максимум, не минимум", "В условии наименьшее число. Сейчас вызывается max.", weight=94)]
    if facts.input_count == 1:
        return [hint("Прочитана только одна строка", "Первая строка — N, числа во второй. Один input() прочитает только N.", weight=88)]
    return []


def _power_of_two(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if 2 in facts.moduli and not facts.bit_and and "n - 1" not in facts.source and "n-1" not in facts.source:
        return [hint("Проверяется чётность, не степень двойки", "6 чётное, но не степень двойки. Нужно n > 0 и n & (n - 1) == 0, либо делить на 2, пока не останется 1.", weight=94)]
    return _yes_no_words(outcome)


def _count_even(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    src = facts.source
    if ("% 2" in src or "%2" in src) and "== 0" not in src and "==0" not in src:
        return [hint("Считаются нечётные", "x % 2 даёт 1 для нечётных. Для чётных нужно x % 2 == 0 и уже это суммировать.", weight=94)]
    return []


def _digit_sum(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if 10 in facts.moduli and "while" not in facts.source and "for " not in facts.source and "str(" not in facts.source:
        return [hint("Взята только последняя цифра", "n % 10 — одна цифра. Сумму считают циклом % 10 и // 10 либо sum(map(int, str(n))).", weight=94)]
    if 10 not in facts.moduli and "str(" not in facts.source:
        return [hint("Цифры числа не разбираются", "Нужен цикл по цифрам: % 10 и // 10, либо пройтись по str(n).", weight=86)]
    return []


def _linear_search(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found = _yes_no_words(outcome)
    if " in " not in facts.source and "==" in facts.source:
        found.append(hint("Сравнивается не со всем списком", "Нужно `if x in a`. Сравнение с одним элементом пропускает остальные.", weight=88))
    return found


def _factorial(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    src = facts.source
    if "range(n)" in src or ("range(" in src and "n + 1" not in src and "n+1" not in src):
        return [hint("range не доходит до n", "Для n! цикл должен умножить на n. range(n) останавливается на n-1, а старт с 0 обнуляет произведение. Пиши range(1, n + 1), 0! = 1.", weight=94)]
    return []


def _reverse_digits(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if facts.reverse_slice and not facts.has_int:
        return [hint("Перевёрнута строка, не число", "120 превращается в «021». Ведущие нули отбрасывает int(строка[::-1]).", weight=94)]
    if not facts.reverse_slice and 10 not in facts.moduli:
        return [hint("Цифры не переставляются", "Либо int(str(n)[::-1]), либо result = result * 10 + n % 10.", weight=86)]
    return []


def _count_vowels(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if facts.vowels_latin_only:
        return [hint("Считаются латинские гласные", "В условии русские: аеёиоуыэюя и заглавные. Набор aeiou на «привет» даст 0.", weight=94)]
    if not facts.vowels_cyrillic:
        return [hint("Нет списка русских гласных", "Заведи набор аеёиоуыэюя вместе с заглавными и считай вхождения.", weight=88)]
    if "ё" not in facts.source.lower() and "Ё" not in facts.source:
        return [hint("Забыли букву ё", "Ё — гласная. Без неё «Ёлка» даст 1 вместо 2.", weight=82)]
    return []


def _palindrome(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found = []
    if not facts.reverse_slice:
        found.append(hint("Строка не сравнивается с переворотом", "Палиндром: s == s[::-1]. Сравнение строки с собой всегда YES.", weight=93))
    if not facts.has_lower:
        found.append(hint("Регистр не приведён", "Abba — палиндром. Сначала s = s.lower(), иначе A и a разные.", weight=80))
    return found


def _fizz_count(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found = []
    if " and " in facts.source and " or " not in facts.source:
        found.append(hint("Стоит and вместо or", "Нужны числа, кратные 3 или 5. and оставляет только кратные 15: для N=10 получится 0 вместо 5.", weight=95))
    missing = [item for item in (3, 5) if item not in facts.moduli]
    if missing:
        found.append(hint(f"Нет проверки на {missing[0]}", f"Считай числа, кратные 3 или 5. В коде нет % {missing[0]}.", weight=90))
    if facts.has_range and "n + 1" not in facts.source and "n+1" not in facts.source:
        found.append(hint("range не включает N", "Если N само кратно 3 или 5, оно должно войти. Пиши range(1, n + 1).", weight=82))
    return found


def _gcd_two(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if facts.uses_min and "gcd" not in facts.source and "%" not in facts.source:
        return [hint("Взяли min вместо НОД", "min(12, 18) = 12, а НОД = 6. Нужен Евклид: while b: a, b = b, a % b.", weight=94)]
    if "%" not in facts.source and "gcd" not in facts.source:
        return [hint("Нет алгоритма Евклида", "НОД: while b: a, b = b, a % b. Либо math.gcd(a, b).", weight=88)]
    return []


def _to_binary(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if facts.uses_bin and "[2:]" not in facts.source and "replace" not in facts.source:
        return [hint("Печатается префикс 0b", "bin(5) даёт 0b101. Нужно bin(n)[2:], для нуля — 0.", weight=94)]
    if not facts.uses_bin and 2 not in facts.moduli:
        return [hint("Нет перевода в двоичную запись", "Либо bin(n)[2:], либо собирай остатки n % 2 и переверни строку.", weight=86)]
    return []


def _unique_count(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if "len(" in facts.source and not facts.uses_set:
        return [hint("Считается длина списка, не уникальные", "len(a) — сколько чисел всего. Различных: len(set(a)). Для 1 2 2 3 1 ответ 3, не 5.", weight=94)]
    return []


def _prefix_sum(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if len(outcome.got_tokens) == 1 and len(outcome.exp_tokens) > 1:
        return [hint("Напечатана одна сумма, не префиксы", "Нужна нарастающая сумма: 1 2 3 4 -> 1 3 6 10, а не одно число 10.", weight=94)]
    return []


def _second_max(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if facts.uses_max and "[-2]" not in facts.source and "sorted" not in facts.source:
        return [hint("Напечатан обычный максимум", "Нужен второй среди различных. На 1 5 3 5 2 max даёт 5, ждать 3. Собери set, отсортируй, возьми предпоследний.", weight=94)]
    if "sorted" in facts.source and not facts.uses_set:
        return [hint("Дубликаты максимума не убраны", "Если 5 встречается дважды, sorted(a)[-2] снова 5. Сначала set(a).", weight=92)]
    return []


def _pair_sum(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found = [] if facts.consecutive_pair else _yes_no_words(outcome)
    if facts.consecutive_pair and not facts.nested_fors and "seen" not in facts.source:
        found.append(hint("Проверяются только соседние", "Пара может стоять на любых позициях, не только i и i+1.", weight=94))
    return found


def _ege_range(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found = []
    must, must_not = parse_div_filters(problem.statement)
    bounds = closed_range_bounds(problem.statement)
    used = set(facts.moduli)
    for group in facts.divisor_lists:
        used.update(group)

    missing_not = [item for item in must_not if item not in used]
    missing_must = [item for item in must if item not in used and not any(u % item == 0 for u in used)]

    if missing_not:
        shown = ", ".join(str(item) for item in missing_not)
        more = " Чисел получилось больше эталона — фильтр слабее условия." if outcome.count_more else ""
        found.append(hint(
            f"Нет проверки «не делится на {missing_not[0]}»",
            f"В условии числа не должны делиться на {shown}. В if этого нет.{more} Максимум может остаться тем же, если лишние числа меньше него.",
            weight=96,
        ))
    if missing_must:
        found.append(hint(
            f"Нет проверки «делится на {missing_must[0]}»",
            f"По условию число должно делиться на {', '.join(str(item) for item in missing_must)}. Без этого отбирается другой набор.",
            weight=94,
        ))

    if bounds:
        start, end = bounds
        for left, right, line in facts.range_literals:
            if left == start and right == end:
                found.append(hint(
                    "range не включает конец отрезка",
                    f"Отрезок [{start}; {end}] включительный. range({start}, {end}) остановится на {end - 1}. Пиши range({start}, {end} + 1).",
                    line=line,
                    weight=93,
                ))
            elif left != start and right in {end, end + 1}:
                found.append(hint(
                    "Левая граница отрезка другая",
                    f"В условии отрезок начинается с {start}, а range стартует с {left}.",
                    line=line,
                    weight=88,
                ))

    if outcome.value_ok and outcome.count_more and not missing_not:
        found.append(hint("Максимум верный, чисел больше", f"Получилось {outcome.got_tokens[0]} вместо {outcome.exp_tokens[0]}. Фильтр слабее: в if не хватает «не делится на ...».", weight=84))
    if outcome.value_ok and outcome.count_less:
        found.append(hint("Максимум верный, чисел меньше", f"Получилось {outcome.got_tokens[0]} вместо {outcome.exp_tokens[0]}. Фильтр строже условия или range не включает конец отрезка.", weight=84))
    if outcome.count_ok and outcome.value_ok is False:
        verb = "минимум" if facts.uses_min and not facts.uses_max else "максимум"
        found.append(hint("Количество верное, второе число нет", f"Набор чисел похож, а {verb} считается иначе. Экстремум обновляй внутри if и не путай min с max.", weight=86))
    if outcome.count_ok is False and outcome.value_ok is False and not missing_not and not missing_must:
        found.append(hint("И количество, и максимум другие", "Сверь range(A, B + 1) и полный список делителей из этого условия.", weight=72))
    return found


def _ege_file(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found = []
    tags = set(problem.tags)
    statement = problem.statement
    must, _must_not = parse_div_filters(statement)

    if "pairs" in tags and (facts.uses_combinations or facts.uses_permutations):
        found.append(hint("Пары должны быть соседними", "В №17 пара — data[i] и data[i+1], а не combinations всех элементов. Сочетания дают слишком много пар.", weight=95))
    elif "pairs" in tags and facts.nested_fors and not facts.consecutive_pair:
        found.append(hint("Перебираются все пары, не соседние", "Два вложенных цикла дают все сочетания. Нужен один проход: for i in range(len(data) - 1).", weight=94))

    if "triples" in tags and facts.consecutive_pair and not facts.window3:
        found.append(hint("Нужны тройки, не пары", "В условии три подряд идущих элемента. Сейчас окно длины 2.", weight=93))

    if "at_least_one" in tags and facts.pair_bool == "and":
        found.append(hint("Стоит and, а нужно «хотя бы одно»", "«Хотя бы один элемент» — это or. and оставляет только пары, где условие у обоих, и счётчик становится меньше.", weight=95))
    if "both" in tags and facts.pair_bool == "or":
        found.append(hint("Стоит or, а нужны оба", "«Оба меньше среднего» проверяют через and. or наберёт лишние пары.", weight=95))
    if "exactly_one" in tags and facts.pair_bool == "and":
        found.append(hint("Отмечены оба, а нужно ровно одно", "«Только второе» значит: среднее подходит, крайние — нет.", weight=93))

    if "even_and_mod" in tags and 37 in facts.moduli and 74 not in facts.moduli:
        found.append(hint("Чётно и кратно 37 — это кратно 74", "Разность одновременно чётная и кратная 37 делится на 74. Проверка только % 37 пропускает нечётные кратные 37.", weight=94))

    if "last_digit_abs" in tags and facts.last_digit_without_abs:
        found.append(hint("Последняя цифра без abs", "В файле есть отрицательные. Для «оканчивается на» пиши abs(x) % 10.", weight=82))

    missing_ref = [item for item in must if item not in facts.moduli]
    if missing_ref and "делящ" in statement:
        found.append(hint(f"Нет эталона по делимости на {missing_ref[0]}", f"Сначала найди наибольшее число файла, которое делится на {missing_ref[0]}, и уже с ним сравнивай элементы пары.", weight=92))

    if problem.id == "ege17-272" and not facts.avg_of_positives and ("sum(" in facts.source or "/" in facts.source):
        found.append(hint("Среднее считается по всем, не по положительным", "В условии среднее только положительных элементов. Отрицательные в среднее не входят.", weight=90))

    if problem.id == "ege17-274" and not facts.abs_sum and facts.uses_abs:
        found.append(hint("Модули стоят не у той суммы", "В отбор идёт abs(a) + abs(b) > 17043 и кратность 3. В ответ — обычная сумма a + b.", weight=88))
    if problem.id == "ege17-274" and not facts.uses_abs:
        found.append(hint("Нет суммы модулей", "Условие про |a| + |b|, не про a + b. Без abs в отбор попадают не те пары.", weight=92))

    if problem.id == "ege17-257":
        if 7 in facts.moduli and 13 not in facts.moduli:
            found.append(hint("Нет ветки с кратными 13", "Сравни минимум кратных 7 и минимум кратных 13. Если минимум по 7 не больше — бери группу кратных 13.", weight=93))
        elif 13 in facts.moduli and 7 not in facts.moduli:
            found.append(hint("Нет ветки с кратными 7", "Нужны оба минимума: по 7 и по 13, и уже по сравнению выбрать группу.", weight=93))

    if problem.id == "ege17-271" and _count_uses_average(facts):
        found.append(hint("Среднее отсекает пары из счётчика", "Количество — все пары с суммой последних цифр 7. Сравнение со средним нужно только для второго числа, не для счётчика.", weight=95))

    if outcome.value_ok and outcome.count_more and "pairs" in tags:
        extra = " Часто вместо «хотя бы одно» стоит and." if "at_least_one" in tags else ""
        found.append(hint("Пар больше, чем нужно", f"Второе число совпало, счётчик {outcome.got_tokens[0]} вместо {outcome.exp_tokens[0]}. В отбор попадают лишние пары.{extra}", weight=78))
    if outcome.value_ok and outcome.count_less and "pairs" in tags:
        extra = " «Хотя бы одно» — это or." if "at_least_one" in tags else ""
        found.append(hint("Пар меньше, чем нужно", f"Второе число совпало, счётчик {outcome.got_tokens[0]} вместо {outcome.exp_tokens[0]}. Условие отбора слишком узкое.{extra}", weight=78))
    if outcome.count_ok and outcome.value_ok is False:
        found.append(hint("Количество верное, второе число нет", "Пары отобраны правильно, а min/max считается по-другому: путают сумму и сумму модулей либо min и max.", weight=80))
    return found


def _count_uses_average(facts: CodeFacts) -> bool:
    src = facts.source
    if not any(name in src for name in ("count", "kol", "k +=", "k+=")):
        return False
    return ("<" in src or ">" in src) and any(name in src for name in ("avg", "av", "sred", "mean"))


HANDLERS = {
    "sum-two": _sum_two,
    "sum-1-n": _sum_1_n,
    "max-three": _max_three,
    "even-odd": _even_odd,
    "last-digit": _last_digit,
    "abs-diff": _abs_diff,
    "school-grade": _school_grade,
    "repeat-string": _repeat_string,
    "min-of-n": _min_of_n,
    "power-of-two": _power_of_two,
    "count-even": _count_even,
    "digit-sum": _digit_sum,
    "linear-search": _linear_search,
    "factorial": _factorial,
    "reverse-digits": _reverse_digits,
    "count-vowels": _count_vowels,
    "palindrome": _palindrome,
    "fizz-count": _fizz_count,
    "gcd-two": _gcd_two,
    "to-binary": _to_binary,
    "unique-count": _unique_count,
    "prefix-sum": _prefix_sum,
    "second-max": _second_max,
    "pair-sum": _pair_sum,
    "ege17-1": _ege_range,
    "ege17-2": _ege_range,
    "ege17-243": _ege_file,
    "ege17-271": _ege_file,
    "ege17-272": _ege_file,
    "ege17-274": _ege_file,
    "ege17-204": _ege_file,
    "ege17-205": _ege_file,
    "ege17-257": _ege_file,
}
