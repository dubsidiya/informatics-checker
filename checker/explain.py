from __future__ import annotations

import re

from checker.models import Explanation, GradeResult, Hint, Problem, TestResult


def attach_explanation(problem: Problem, result: GradeResult, source: str = "") -> GradeResult:
    result.explanation = explain_result(problem, result, source)
    return result


def explain_result(problem: Problem, result: GradeResult, source: str = "") -> Explanation:
    if result.status == "ok":
        return Explanation(
            headline="Задача сдана",
            what="Все тесты прошли: программа считает то, что просят, и печатает ответ в нужном виде.",
            why="Значит, и пример из условия, и скрытая проверка совпали.",
            how="Можно открывать следующую задачу этой темы.",
            kind="ok",
        )

    if result.status == "syntax" and result.syntax:
        line = result.syntax.line
        where = f" на строке {line}" if line else ""
        return Explanation(
            headline="Программа даже не запустилась",
            what=f"Python не понял текст программы{where}. Пока синтаксис сломан, ни один тест не выполняется.",
            why=result.syntax.explanation,
            how=_syntax_how(result.syntax.explanation, result.syntax.line),
            line=line,
            kind="syntax",
        )

    if result.status == "syntax":
        return Explanation(
            headline="Программа даже не запустилась",
            what="В редакторе нет кода, который можно запустить.",
            why="Пустую программу проверить нельзя.",
            how="Напиши решение в редакторе и нажми «Проверить».",
            kind="syntax",
        )

    first = next((item for item in result.tests if item.verdict != "OK"), None)
    hint = result.hints[0] if result.hints else None
    if first is None:
        return Explanation(
            headline="Проверка не прошла",
            what=result.message,
            why=(hint.detail if hint else "Автоматический разбор не нашёл типичную ошибку."),
            how="Перечитай условие и сравни свой вывод с примером.",
            kind="logic",
        )

    if first.verdict == "TLE":
        return Explanation(
            headline="Программа думает слишком долго",
            what=f"Тест {first.index + 1} не уложился во время. Проверяльщик остановил программу, чтобы она не зависла навсегда.",
            why="Чаще всего виноват бесконечный while, слишком большой перебор или рекурсия без памяти.",
            how=_how_from_hint(hint)
            or "Найди цикл, который никогда не заканчивается, или сузь перебор. В №16 и №23 почти всегда нужен @lru_cache или массив.",
            line=first.error_line or (hint.line if hint else None),
            kind="runtime",
        )

    if first.verdict == "RE":
        return _runtime(first, hint, source)

    return _wrong_answer(problem, result, first, hint)


def _runtime(first: TestResult, hint: Hint | None, source: str) -> Explanation:
    name = _name_from_error(first.error)
    line = first.error_line or (hint.line if hint else None)
    where = f" на строке {line}" if line else ""
    kind = first.error_type or "ошибка"

    what = f"Программа запустилась, но упала{where} с ошибкой {kind}."
    if first.error and not first.hidden:
        what += f" Python сказал: {first.error}."

    if kind == "NameError":
        why = (
            f"Имени `{name}` ещё нет. " if name else "Используется имя, которого нет. "
        ) + "Либо опечатка, либо переменную создают позже, чем читают."
        how = (
            f"Найди `{name}`{where}: либо исправь опечатку, либо создай переменную выше, например `{name} = int(input())`."
            if name
            else "Посмотри строку с ошибкой: это имя должно появиться раньше."
        )
    elif kind == "IndexError":
        why = "Обращение к элементу за границей списка. Индексы идут с 0 до len(список) − 1. Пустой список или i == len(a) как раз дают эту ошибку."
        how = "Перед обращением проверь длину: `if i + 1 < len(a)`. Для пар в №17 цикл `for i in range(len(data) - 1)`."
    elif kind == "TypeError":
        why = "Операция вызвана не с тем типом. Часто складывают строку с числом: input() без int, или берут len от числа."
        how = "Преобразуй ввод в числа: `a, b = map(int, input().split())`. Для печати нескольких чисел используй `print(x, y)`."
    elif kind == "ValueError":
        why = "Значение нельзя преобразовать. int() падает, если в строке не одно число — например «2 3» или пустая строка."
        how = "Если в строке несколько чисел — сначала split(), потом map(int, ...). int(input()) подходит только для одного числа в строке."
    elif kind == "ZeroDivisionError":
        why = "Деление на ноль. Знаменатель на этом тесте оказался 0."
        how = "Перед делением проверь знаменатель: `if b != 0`."
    elif kind == "EOFError":
        why = "input() вызван чаще, чем есть строк во вводе. Лишний input или читают по строке, а данные в одной."
        how = "Посчитай, сколько раз вызывается input(), и сравни с примером ввода. Часто хватает одного `input().split()`."
    elif kind == "AttributeError":
        why = "У объекта нет такого метода. У числа нет .split() — сначала нужна строка. У строки нет .append()."
        how = "Посмотри тип переменной на этой строке. Если это число — .split() нельзя; если строка — .append() нельзя."
    elif kind == "RecursionError":
        why = "Рекурсия ушла слишком глубоко: нет выхода или он не достигается."
        how = "Добавь условие выхода и память: @lru_cache или считай снизу вверх массивом."
    elif kind == "PermissionError":
        why = "Программа пыталась записать в файл. На проверяльщике open() только читает готовый файл задачи."
        how = "Пиши open('17.txt') без режима записи. Файл задачи уже подставлен."
    elif kind == "KeyError":
        why = "В словаре нет такого ключа. Сначала проверь `if key in d`."
        how = "Не бери d[key] вслепую. Используй `d.get(key)` или проверку `if key in d`."
    else:
        why = hint.detail if hint else "Программа прервалась во время выполнения."
        how = _how_from_hint(hint) or "Открой строку с ошибкой и исправь то, на что указывает сообщение Python."

    return Explanation(headline="Программа упала", what=what, why=why, how=how, line=line, kind="runtime")


def _wrong_answer(problem: Problem, result: GradeResult, first: TestResult, hint: Hint | None) -> Explanation:
    visible = not first.hidden
    if visible:
        got = (first.got or "").strip() or "ничего"
        exp = (first.expected or "").strip() or "ответ из условия"
        stdin = (first.stdin or "").strip()
        what = f"На тесте {first.index + 1} программа напечатала `{_short(got)}`, а нужно `{_short(exp)}`."
        if stdin and not stdin.startswith("[файл"):
            what += f" Ввод был: `{_short(stdin)}`."
        elif stdin.startswith("[файл"):
            what += " Данные берутся из файла задачи."
    else:
        what = (
            f"Тест {first.index + 1} скрытый — это полный набор из условия, эталон ученику не показываем. "
            "Примеры могли пройти, а настоящий ответ задачи — нет."
        )

    why = hint.detail if hint else "Ответ не совпал с правильным. Перечитай условие: что именно считают и в каком виде печатают."
    how = _how_from_hint(hint) or _how_from_detail(hint) or _generic_how(problem, visible)
    headline = hint.title if hint else "Ответ не тот"
    kind = hint.kind if hint else "logic"
    line = hint.line if hint else None
    return Explanation(headline=headline, what=what, why=why, how=how, line=line, kind=kind)


def _how_from_detail(hint: Hint | None) -> str:
    if not hint or not (hint.detail or "").strip():
        return ""
    detail = hint.detail.strip()
    if detail.endswith("."):
        detail = detail[:-1]
    return "Сделай именно это: " + detail + ". Остальное в программе не ломай."


def _ege17_how(problem: Problem) -> str:
    blob = f"{problem.statement} {problem.input_format} {problem.title}".lower()
    if "пар" in blob or "сосед" in blob:
        return "Сверь, что такое пара (обычно два соседних числа), оба условия отбора и что печатать первым: количество или сумму/максимум."
    if "файл" in blob or "17.txt" in blob:
        return "Считай файл в список. Дальше отбери числа или пары по всем условиям из формулировки и напечатай два числа в том порядке, как просят."
    return "Это отрезок, не файл. Цикл range(A, B + 1), в if все условия сразу, в конце print(количество, максимум или минимум) — как в условии."


def _generic_how(problem: Problem, visible: bool) -> str:
    tags = set(problem.tags)
    if "ege17" in tags:
        return _ege17_how(problem)
    if "ege9" in tags:
        return "Проверь split: в csv чаще `;`, в txt — пробел. Затем оба условия из формулировки на одной строке таблицы."
    if "ege8" in tags:
        return "Перебор — product или permutations по алфавиту. Сверь длину слова, можно ли повторять буквы и нумерацию с 1."
    if "ege13" in tags:
        return "Сверь адрес узла, сеть и маску. Печатай ровно тот октет или IP, который просят, с точками или без — как в примере."
    if "ege14" in tags:
        return "Перевод в систему: n % b и n // b. Сверь основание, какую цифру считают и формат: число или список через запятую."
    if "ege16" in tags or "ege23" in tags:
        return "Сверь формулы веток и границы. Если просят последние цифры — это % 10**k, не всё огромное число."
    if "ege25" in tags:
        return "Границы range(A, B + 1), что печатать в каждой строке, и не гоняй цикл до миллиарда по маске."
    if visible:
        return "Пройди пример из условия вручную на бумаге и сравни со своим print. Часто виноваты формат, range или то, что считают не ту величину."
    return "Не подгоняй программу под пример. Перечитай условие целиком: границы, знаки, что считается парой и сколько чисел выводить."


def _how_from_hint(hint: Hint | None) -> str:
    if not hint:
        return ""
    title = hint.title
    for key, text in HOW_BY_TITLE:
        if key.lower() in title.lower():
            return text
    return ""


def _syntax_how(explanation: str, line: int | None) -> str:
    where = f"Строка {line}: " if line else ""
    if "двоеточ" in explanation:
        return f"{where}после if / for / while / def / else поставь `:` и со следующей строки сделай отступ 4 пробела."
    if "отступ" in explanation:
        return f"{where}выдели блок Tab или четырьмя пробелами. Все команды одного if/for должны начинаться в одном столбце."
    if "скобк" in explanation:
        return f"{where}посчитай пары () [] {{}}. Каждая открытая скобка должна закрыться."
    if "кавыч" in explanation or "строка не закрыта" in explanation.lower():
        return f"{where}открой и закрой одну и ту же кавычку."
    if "==" in explanation:
        return f"{where}в условии пиши `if a == b:`, а не `if a = b:`."
    if "запрещен" in explanation or "Нельзя" in explanation:
        return "Убери запрещённый импорт или функцию. Для задачи хватает input, print, open на чтение и циклов."
    return f"{where}исправь указанную строку и проверь ещё раз. Пока синтаксис сломан, логика даже не запускается."


def _name_from_error(error: str) -> str:
    match = re.search(r"name '([^']+)'", error or "")
    return match.group(1) if match else ""


def _short(text: str, limit: int = 80) -> str:
    clean = " ".join((text or "").split())
    if len(clean) > limit:
        return clean[: limit - 1] + "…"
    return clean


HOW_BY_TITLE = [
    ("не делится", "Добавь в if все «не делится на …» из условия: `x % k != 0` для каждого такого k."),
    ("нет проверки", "Допиши в if недостающую проверку из условия. Не выкидывай те, что уже стоят."),

    ("строк", "Сначала преврати ввод в числа: `a, b = map(int, input().split())`, и только потом складывай."),
    ("input() вернул строку", "После input() нужен int или map(int, ...). Иначе «2» + «3» склеится в 23."),
    ("складываются строки", "Нельзя писать input() + input(). Сначала int, потом сложение."),
    ("нет вывода", "В конце должен быть print с ответом. Без print проверяльщик считает, что программа ничего не решила."),
    ("ничего не вывела", "print стоит внутри if, который на этом тесте не сработал, либо до print программа ушла в другой ветке."),
    ("формат", "Печатай ровно то, что в примере: те же пробелы, регистр, без подписи «ответ:»."),
    ("напечатан список", "Вместо print(список) напиши print(*список) — числа через пробел, без скобок."),
    ("ошибка на единицу", "Проверь range: нужен range(1, n + 1), если n должно войти. Для индексов — len(a) - 1, не len(a)."),
    ("range не включает", "Правый конец отрезка входит в условие. Пиши range(A, B + 1), не range(A, B)."),
    ("файл не открывается", "Данные в файле. Напиши open('17.txt') или имя файла из условия — проверяльщик подставит его сам."),
    ("разделитель", "Посмотри файл: если числа через `;`, пиши split(';'). Если через пробел — split() без аргументов."),
    ("пары должны быть соседними", "В №17 пара — data[i] и data[i+1]. Не бери combinations всех элементов."),
    ("все пары, не соседние", "Один проход: for i in range(len(data) - 1). Два вложенных for дают все пары, это другая задача."),
    ("стоит and", "«Хотя бы одно» — это or. and оставляет только случаи, где условие у обоих сразу."),
    ("стоит or", "«Оба» — это and. or наберёт лишние пары."),
    ("последняя цифра без abs", "Для отрицательных пиши abs(x) % 10, иначе -17 % 10 в Python даст не 7."),
    ("среднее отсекает пары из счётчика", "Количество считают по одному условию, второе число — по другому. Не мешай их в одном if."),
    ("нужно слово, не номер", "В print должно быть само слово, не его номер в списке."),
    ("нужен номер, не слово", "Считай позицию (обычно с 1) и печатай число, не саму строку."),
    ("буквы могут повторяться", "Нужен product(..., repeat=n), не permutations. Permutations каждую букву берёт один раз."),
    ("нет перебора слов", "Подключи itertools.product или напиши вложенные циклы по алфавиту."),
    ("алфавит", "Слова нумеруют в алфавитном порядке. Сначала sorted(алфавит), потом product."),
    ("в ip нужны точки", "Печатай как 192.168.0.1 — четыре числа через точку, если так в примере."),
    ("не должно быть точки", "В этой задаче IP просят одной строкой цифр, без точек."),
    ("маску удобно", "Перебери длину префикса и сравни сеть: ip_network(f'{узел}/{p}', strict=False)."),
    ("систему", "Чтобы перевести число в систему b: пока n > 0, цифры это n % b, затем n //= b."),
    ("последние цифры", "Огромное F(n) не нужно целиком. Бери ответ % 10**k, где k — сколько цифр просят."),
    ("рекурсия без памяти", "Поставь @lru_cache(None) над функцией или считай массив снизу вверх. Иначе не уложишься во время."),
    ("запрещённое число", "Если текущее значение равно запрещённому, возвращай 0 — этот путь не считается."),
    ("несколько строк", "Каждое найденное число — отдельный print. Не склеивай всё в одну строку."),
    ("потеряна последняя строка", "range не дошёл до конца отрезка. Пиши range(A, B + 1)."),
    ("не перебирай до миллиарда", "Собери число по маске: цифры на местах ? и * перебери сами, не цикл до 10**9."),
    ("ровно 4 делителя", "Это либо p³, либо произведение двух простых. Не забудь 1 и само число."),
    ("скрытый тест", "Не подгоняй код под пример. Перечитай условие: границы, знаки, что такое пара, сколько чисел выводить."),
    ("минимум, не максимум", "В условии просят максимум — в коде должен быть max, не min."),
    ("1/0 вместо слова", "Печатай YES/NO или EVEN/ODD, как в условии, не True/False и не 1/0."),
    ("наоборот", "Проверь if: не перепутаны ли == и !=, not, in. Условие сработало зеркально."),
]


def deepen_explanation(problem: Problem, result: GradeResult, tries: int) -> GradeResult:
    from checker.topics import retry_how

    result.tries = max(1, int(tries or 1))
    exp = result.explanation
    if not exp or result.status == "ok":
        return result
    extra = retry_how(problem, result.tries)
    if extra and extra not in (exp.how or ""):
        exp.how = ((exp.how or "").rstrip() + " " + extra).strip()
    return result

