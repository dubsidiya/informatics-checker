from __future__ import annotations

"""Turn a technical verdict into one small teacher-like intervention.

This is deliberately rule based: it only makes claims supported by the code,
the verdict and the task tags.  A helpful coach must not pretend to read a
student's mind or disclose a hidden test answer.
"""

from checker.facts import extract_facts, extract_outcome
from checker.models import GradeResult, Problem


def add_coach_turn(problem: Problem, result: GradeResult, source: str) -> GradeResult:
    exp = result.explanation
    if not exp or result.status == "ok":
        return result

    facts = extract_facts(source)
    outcome = extract_outcome(result.tests) if result.tests else None
    hint = result.hints[0] if result.hints else None
    title = (hint.title if hint else "").lower()
    error_type = outcome.first.error_type if outcome else ""
    tags = set(problem.tags)

    thought, question, check = _turn(title, error_type, facts, tags, outcome)
    exp.thought = thought
    exp.question = question
    exp.self_check = check
    return result


def _turn(title, error_type, facts, tags, outcome) -> tuple[str, str, str]:
    if error_type == "NameError":
        return (
            "Похоже, ты считаешь, что эта переменная уже была создана.",
            "Где выше по коду ей впервые присваивается значение?",
            "Прочитай код сверху вниз: каждое имя должно появиться слева от `=` до первого использования.",
        )
    if error_type == "IndexError":
        return (
            "Похоже, ты берёшь следующий элемент, не оставив для него места в конце списка.",
            "На последнем i чему равен i + 1 и существует ли такой индекс?",
            "Для соседних пар проверь на списке из двух чисел: цикл должен выполниться ровно один раз.",
        )
    if error_type in {"TypeError", "ValueError"}:
        return (
            "Похоже, ты работаешь с текстом как с числом или читаешь строку не в том формате.",
            "Что возвращает именно этот `input()` — одно число или строку из нескольких чисел?",
            "Поставь мысленно `print(type(переменная))`: до арифметики там должен быть `int`, а не `str`.",
        )
    if error_type == "EOFError":
        return (
            "Похоже, программа ждёт больше строк, чем дано во вводе.",
            "Сколько раз вызывается input() и сколько строк показано в примере?",
            "Сверь каждый input() с отдельной строкой формата ввода; несколько чисел одной строки читают через split().",
        )
    if error_type == "ZeroDivisionError":
        return (
            "Похоже, ты предположил, что знаменатель всегда ненулевой.",
            "На каком значении знаменатель становится 0?",
            "Проверь крайний случай с нулём до деления и реши, что должна делать программа.",
        )
    if error_type == "PermissionError":
        return (
            "Похоже, ты пытаешься создать или изменить файл, хотя данные уже готовы.",
            "Нужно ли задаче записывать файл или достаточно прочитать данные?",
            "Открой файл без второго аргумента: `open('имя_файла')`.",
        )
    if error_type == "RecursionError":
        return (
            "Похоже, рекурсивный шаг не приближает вычисление к остановке или одинаковые значения считаются повторно.",
            "Для какого самого маленького n функция обязана закончиться сразу?",
            "Выпиши базовые случаи и проверь, что каждый рекурсивный вызов идёт к одному из них.",
        )
    if "строк" in title or facts.raw_input_add or (facts.has_input and not facts.has_int and facts.has_print):
        return (
            "Похоже, введённые цифры воспринимаются как текст, а не как числа.",
            "Какой результат в Python у выражения `'2' + '3'`? А какой нужен задаче?",
            "Перед сложением, сравнением или вычитанием преобразуй ввод через int или map(int, ...).",
        )
    if "range" in title or (outcome and outcome.off_by_one):
        return (
            "Похоже, правую границу или последний индекс ты мысленно включил в range, хотя Python его исключает.",
            "Какое последнее число даёт твой range при маленьком примере?",
            "Подставь границу вручную: если она должна участвовать, остановка range должна быть на единицу больше.",
        )
    if "and" in title or "or" in title:
        return (
            "Похоже, слова условия «оба» и «хотя бы одно» были переведены в логическое выражение не так.",
            "Должен ли пройти случай, где верно только первое условие?",
            "Составь две строки истины: для and нужны оба True, для or достаточно одного True.",
        )
    if "констант" in title or facts.constant_prints:
        return (
            "Похоже, ответ из примера принят за правило для всех входных данных.",
            "Что изменится в программе, если заменить числа во вводе на другие?",
            "Убери готовый ответ из print и проследи, от каких переменных должен зависеть результат.",
        )
    if "формат" in title or (outcome and outcome.format_only):
        return (
            "Похоже, вычисление уже верное, но проверяльщик видит другой вид ответа.",
            "В условии просят одно число, два числа через пробел или слово в точном регистре?",
            "Сравни свой print с образцом посимвольно: без подписей, скобок и лишних строк.",
        )
    if "ege24" in tags:
        return (
            "Похоже, ты уже начал разбирать строку, но потерял правило обновления текущей цепочки.",
            "Что должно стать с текущей длиной, когда встречается неподходящий символ?",
            "Прогони код по строке из 4–5 букв и после каждой буквы запиши текущую длину и максимум.",
        )
    if "ege17" in tags and facts.has_open:
        return (
            "Похоже, общий проход по файлу есть, но одно условие отбора или величина для ответа отличается от условия.",
            "Какие два условия должна выполнять именно одна пара или число?",
            "Раздели условие на чек-лист и отметь, где каждое из них стоит в if; отдельно сверь, что считаешь и что берёшь как max/min.",
        )
    return (
        "Похоже, общий замысел есть, но код проверяет не совсем то свойство, которое сформулировано в задаче.",
        "Какой один маленький пример отличит твоё правило от правила из условия?",
        "Придумай крайний случай: граница, ноль, повтор или минимальный размер данных — и пройди его на бумаге до print.",
    )
