from __future__ import annotations

from checker.facts import CodeFacts, Outcome, parse_div_filters
from checker.models import Hint, Problem


def extra_findings(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if outcome.first.verdict != "WA":
        return []
    found: list[tuple[int, Hint]] = []
    found.extend(_yes_no_swap(outcome))
    found.extend(_swapped_numbers(outcome, problem))
    found.extend(_minmax_vs_statement(facts, problem, outcome))
    found.extend(_inverted_moduli(facts, problem))
    found.extend(_formula_and_ops(facts, problem, outcome))
    found.extend(_compare_flips(facts, problem, outcome))
    found.extend(_two_number_facts(facts, problem, outcome))
    found.extend(_one_number_facts(facts, problem, outcome))
    return found


def hint(title: str, detail: str, kind: str = "logic", weight: int = 80) -> tuple[int, Hint]:
    return weight, Hint(kind=kind, title=title, detail=detail)

def _yes_no_swap(outcome: Outcome) -> list[tuple[int, Hint]]:
    got = outcome.got.strip().upper()
    exp = outcome.expected.strip().upper()
    words = {"YES", "NO", "EVEN", "ODD"}
    if got in words and exp in words and got != exp:
        return [
            hint(
                "Слова ответа перепутаны",
                f"Ожидалось {outcome.expected.strip()}, программа напечатала {outcome.got.strip()}. "
                "YES/NO или EVEN/ODD стоят наоборот — либо в print, либо условие if сработало наоборот.",
                weight=89,
            )
        ]
    return []



def _ints(tokens: list[str]) -> tuple[int | None, int | None]:
    if len(tokens) != 2:
        return None, None
    try:
        return int(tokens[0]), int(tokens[1])
    except ValueError:
        return None, None


def _swapped_numbers(outcome: Outcome, problem: Problem) -> list[tuple[int, Hint]]:
    got, exp = outcome.got_tokens, outcome.exp_tokens
    if len(got) == 2 and len(exp) == 2 and got == [exp[1], exp[0]]:
        return [
            hint(
                "Числа ответа переставлены",
                f"Напечатано `{got[0]} {got[1]}`, нужно `{exp[0]} {exp[1]}`. "
                "Сначала идёт количество, потом второе число из условия — не наоборот.",
                weight=92,
            )
        ]
    return []


def _minmax_vs_statement(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    text = problem.statement.lower()
    want_max = "макс" in text or "наибольш" in text
    want_min = "миним" in text or "наименьш" in text
    if want_max and facts.uses_min and not facts.uses_max:
        return [
            hint(
                "Стоит min, а нужен максимум",
                "В условии просят наибольшее / максимум, а в коде вызывается min. Из-за этого второе число ответа другое.",
                weight=90,
            )
        ]
    if want_min and not want_max and facts.uses_max and not facts.uses_min:
        return [
            hint(
                "Стоит max, а нужен минимум",
                "В условии просят наименьшее / минимум, а в коде вызывается max.",
                weight=90,
            )
        ]
    if outcome.count_ok and outcome.value_ok is False and facts.uses_min and facts.uses_max:
        return [
            hint(
                "min и max, скорее всего, перепутаны",
                "Количество совпало, второе число нет. Проверь, не берёшь ли min там, где нужен max, или наоборот.",
                weight=84,
            )
        ]
    return []


def _inverted_moduli(facts: CodeFacts, problem: Problem) -> list[tuple[int, Hint]]:
    must, must_not = parse_div_filters(problem.statement)
    found = []
    for check in facts.mod_checks:
        if check.modulus in must and check.equals_zero is False:
            found.append(
                hint(
                    f"Проверка на {check.modulus} перевёрнута",
                    f"Нужно `x % {check.modulus} == 0`, а стоит `!= 0`. Условие отбора работает наоборот.",
                    weight=91,
                )
            )
        if check.modulus in must_not and check.equals_zero is True:
            found.append(
                hint(
                    f"Нужно НЕ делиться на {check.modulus}",
                    f"В условии «не делится на {check.modulus}», а в коде стоит `% {check.modulus} == 0`.",
                    weight=91,
                )
            )
    return found[:2]


def _formula_and_ops(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    src = facts.source
    found = []
    if problem.id == "sum-two" and " - " in src and "+" not in src.replace("++", ""):
        found.append(hint("Вычитание вместо сложения", "В условии сумма a + b. Сейчас числа вычитаются, поэтому знак или величина другие.", weight=90))
    if problem.id == "sum-1-n":
        if "n - 1" in src or "n-1" in src:
            found.append(hint("В формуле минус вместо плюса", "Сумма 1...N равна n * (n + 1) // 2. Сейчас стоит (n - 1), это сумма до n-1.", weight=90))
        if "n * n" in src or "n*n" in src:
            found.append(hint("В формуле пропал + 1", "Нужно n * (n + 1) // 2, не n * n // 2.", weight=90))
        if facts.true_div and not facts.floor_div:
            found.append(hint("Обычное деление вместо //", "Оператор / даёт 15.0 или дробь. Для целого ответа нужен //.", weight=88))
    if problem.id == "abs-diff" and " - " in src and not facts.uses_abs:
        found.append(hint("Нет модуля разности", "a - b бывает отрицательным. Нужен abs(a - b).", weight=90))
    if problem.id == "abs-diff" and "+" in src and "abs" in src:
        found.append(hint("Складываются вместо вычитания", "Нужен модуль разности abs(a - b), не сумма.", weight=86))
    if " // " in src and "%" not in src and problem.id in {"count-even", "last-digit", "ege17-205", "ege17-274"}:
        found.append(hint("Стоит // вместо %", "Остаток от деления — это %, не целое деление //.", weight=88))
    if problem.id == "count-even" and ("// 2" in src or "//2" in src):
        found.append(hint("Стоит // 2 вместо % 2", "Чётность проверяют через x % 2 == 0. // 2 отбрасывает младший бит иначе.", weight=90))
    if "модул" in problem.statement or "|" in problem.statement or "abs" in problem.statement:
        if not facts.uses_abs:
            found.append(hint("Нет модуля", "В условии есть модуль / абсолютная величина, а в коде abs нет.", weight=88))
        elif "274" in problem.id and not facts.abs_sum:
            found.append(hint("Модули стоят не у той суммы", "В отбор идёт abs(a) + abs(b). Если abs снять с одного слагаемого, пары отберутся иначе.", weight=86))
    return found


def _compare_flips(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    src = facts.source
    found = []
    if problem.id == "palindrome" and ("!=" in src or "not " in src) and facts.reverse_slice:
        found.append(hint("Сравнение с переворотом перевёрнуто", "Палиндром — это s == s[::-1]. Сейчас стоит неравенство, YES и NO меняются местами.", weight=90))
    if problem.id == "count-vowels" and " not " in src:
        found.append(hint("in перевёрнут в not in", "Считаются символы, которые НЕ гласные. Убери not.", weight=90))
    if problem.id == "fizz-count":
        if "!=" in src or "not " in src:
            found.append(hint("Условие кратности перевёрнуто", "Нужны числа, которые делятся на 3 или 5: % == 0. Сейчас стоит !=, считаются как раз не те.", weight=90))
    if "pairs" in problem.tags or "triples" in problem.tags:
        if "больше" in problem.statement and "<" in src and ">" not in src.replace(">=", ""):
            found.append(hint("Сравнение перевёрнуто", "В условии «больше», а в коде стоит <. Пары отбираются наоборот.", weight=86))
        if "меньше" in problem.statement and ">" in src and "<" not in src.replace("<=", ""):
            found.append(hint("Сравнение перевёрнуто", "В условии «меньше», а в коде стоит >.", weight=86))
    if problem.id == "ege17-257" and (">" in src) != True:
        pass
    if problem.id == "ege17-257" and facts.uses_min and facts.uses_max:
        if "m7 <" in src or "m7<" in src:
            found.append(hint("Сравнение минимумов перевёрнуто", "По условию ветка зависит от того, больше ли минимум кратных 7, чем минимум кратных 13.", weight=86))
    return found


def _two_number_facts(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if len(outcome.got_tokens) != 2 or len(outcome.exp_tokens) != 2:
        return []
    if outcome.first.hidden:
        return []
    if outcome.got_tokens == [outcome.exp_tokens[1], outcome.exp_tokens[0]]:
        return []
    g0, e0 = outcome.got_tokens[0], outcome.exp_tokens[0]
    g1, e1 = outcome.got_tokens[1], outcome.exp_tokens[1]
    bits = []
    if outcome.count_more:
        bits.append(f"первое число больше эталона ({g0} вместо {e0})")
    elif outcome.count_less:
        bits.append(f"первое число меньше эталона ({g0} вместо {e0})")
    elif outcome.count_ok:
        bits.append(f"количество {e0} совпало")
    else:
        bits.append(f"первое число {g0} вместо {e0}")
    if outcome.value_ok:
        bits.append("второе число верное")
    else:
        bits.append(f"второе число {g1} вместо {e1}")
    if outcome.count_ok and not outcome.value_ok:
        title = "Счётчик верный, второе число нет"
    elif outcome.value_ok and not outcome.count_ok:
        title = "Второе число верное, счётчик нет"
    else:
        title = "Оба числа ответа другие"
    who = "чисел"
    if "pairs" in problem.tags:
        who = "пар"
    elif "triples" in problem.tags:
        who = "троек"
    elif "closed_range" in problem.tags:
        who = "чисел на отрезке"
    detail = "; ".join(bits) + f". Смотри отбор {who} и то, что просят вторым числом."
    if " and " in facts.source and " or " not in facts.source and "at_least_one" in problem.tags:
        detail += " Если в условии «хотя бы одно», нужен or, не and."
    if " or " in facts.source and " and " not in facts.source and "both" in problem.tags:
        detail += " Если в условии «оба», нужен and, не or."
    return [hint(title, detail, weight=81)]


def _one_number_facts(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if len(outcome.got_tokens) != 1 or len(outcome.exp_tokens) != 1:
        return []
    if outcome.first.hidden:
        return []
    try:
        got_n = float(outcome.got_tokens[0])
        exp_n = float(outcome.exp_tokens[0])
    except ValueError:
        return []
    if got_n == exp_n:
        return []
    if got_n == -exp_n:
        return [hint("Не тот знак", f"Модуль совпал ({int(abs(got_n))}), знак нет. Проверь вычитание и abs.", weight=88)]
    if abs(got_n - exp_n) == 1:
        return [hint("Ошибка на единицу", f"Получилось {outcome.got_tokens[0]}, ждали {outcome.exp_tokens[0]}. Часто виноват range без n или индекс на 1 короче.", weight=86)]
    if exp_n != 0 and (got_n == 2 * exp_n or exp_n == 2 * got_n):
        return [hint("Ответ в два раза больше или меньше", "Дважды учли элемент или делят не ту величину.", weight=84)]
    if facts.true_div and not facts.floor_div and "integer" in " ".join(problem.tags):
        return [hint("Обычное деление вместо //", "Оператор / даёт дробь. Для целого ответа нужен //.", weight=86)]
    return [
        hint(
            "На этом тесте получается другое число",
            f"Ожидалось {outcome.exp_tokens[0]}, программа напечатала {outcome.got_tokens[0]}. "
            f"Ввод: `{_short(outcome.first.stdin)}`.",
            weight=80,
        )
    ]


def _short(text: str, limit: int = 60) -> str:
    clean = " ".join((text or "").split())
    return clean if len(clean) <= limit else clean[: limit - 1] + "..."
