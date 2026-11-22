from __future__ import annotations

import re

from checker.models import Explanation, GradeResult, Hint, Problem, TestResult


def attach_explanation(problem: Problem, result: GradeResult, source: str = "") -> GradeResult:
    from checker.intent import apply_intent

    result.explanation = explain_result(problem, result, source)
    return apply_intent(problem, result, source)


def explain_result(problem: Problem, result: GradeResult, source: str = "") -> Explanation:
    if result.status == "ok":
        from checker.success import success_advice

        advice = success_advice(problem, source)
        return Explanation(
            headline="Задача сдана",
            what="Все тесты прошли: программа считает то, что просят, и печатает ответ в нужном виде.",
            why=advice.praise,
            how="Можно открывать следующую задачу этой темы.",
            next_step=advice.speed_tip,
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
        return _runtime(first, result.hints, source, problem)

    return _wrong_answer(problem, result, first, hint)


def _runtime(first: TestResult, hints: list[Hint] | Hint | None, source: str, problem: Problem | None = None) -> Explanation:
    if isinstance(hints, Hint) or hints is None:
        hint_list = [hints] if isinstance(hints, Hint) else []
    else:
        hint_list = list(hints)
    hint = hint_list[0] if hint_list else None
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
        why = "Обращение к элементу за границей списка. Индексы идут с 0 до len(список) − 1."
        how = _index_how(source, problem)
        if "range(n + 1)" in how or "range(n+1)" in how.replace(" ", ""):
            return Explanation(
                headline="Список смежности короче графа",
                what=what,
                why=why,
                how=how,
                line=line,
                kind="runtime",
            )
    elif kind == "TypeError":
        why = "Операция вызвана не с тем типом. Часто это строка вместо числа или минус между строками."
        how = _type_how(source, first.error or "")
        headline = "input() остался строкой" if "int(input())" in how or "map(int" in how else "Минус между строками" if how.startswith("Замени `-`") else "Программа упала"
        return Explanation(headline=headline, what=what, why=why, how=how, line=line, kind="runtime")
    elif kind == "ValueError":
        precise = next(
            (
                item
                for item in hint_list
                if _hint_about(item, ("точкой с запятой", "нужны пробелы", "нужна точка"))
            ),
            None,
        )
        if precise:
            why = precise.detail
            how = _how_from_hint(precise) or precise.detail
            return Explanation(
                headline=precise.title,
                what=what,
                why=why,
                how=how,
                line=line,
                kind="runtime",
            )
        why = "Значение нельзя преобразовать. int() падает, если в строке не одно число — например «2 3» или пустая строка."
        how = _value_how(source, problem)
        if how.startswith("Замени"):
            return Explanation(
                headline="Неверный разделитель",
                what=what,
                why=why,
                how=how,
                line=line,
                kind="runtime",
            )
    elif kind == "ZeroDivisionError":
        concrete = _concrete_hint(hint_list, kind)
        if concrete is not None:
            return Explanation(
                headline=concrete.title,
                what=what,
                why=concrete.detail,
                how=_how_from_hint(concrete) or concrete.detail,
                line=line or concrete.line,
                kind=concrete.kind or "runtime",
            )
        why = "Деление на ноль. Знаменатель на этом тесте оказался 0."
        how = "Перед делением проверь знаменатель: `if b != 0`."
    elif kind == "EOFError":
        why = "input() вызван чаще, чем есть строк во вводе. Лишний input или читают по строке, а данные в одной."
        how = "Посчитай, сколько раз вызывается input(), и сравни с примером ввода. Часто хватает одного `input().split()`."
    elif kind == "AttributeError":
        why = "У объекта нет такого метода. У числа нет .split() — сначала нужна строка. У строки нет .append()."
        how = "Посмотри тип переменной на этой строке. Если это число — .split() нельзя; если строка — .append() нельзя."
    elif kind == "RecursionError":
        concrete = _concrete_hint(hint_list, kind)
        if concrete is not None:
            return Explanation(
                headline=concrete.title,
                what=what,
                why=concrete.detail,
                how=_how_from_hint(concrete) or concrete.detail,
                line=line or concrete.line,
                kind=concrete.kind or "runtime",
            )
        why = "Рекурсия ушла слишком глубоко: шаг уходит от условия выхода или выхода нет."
        how = _recursion_how(source)
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


def _concrete_hint(hints: list[Hint], error_type: str = "") -> Hint | None:
    from checker.logic import _FACT_HINTS_AHEAD, _GENERIC_WA_TITLES

    banned = set(_GENERIC_WA_TITLES)
    if error_type == "RecursionError":
        banned.update({"Пустой print()", "В print есть лишнее слово"})
    for item in hints:
        if not item or item.title in banned or item.title in _GENERIC_RUNTIME:
            continue
        if item.title in _FACT_HINTS_AHEAD or _how_from_hint(item):
            return item
    return None


_GENERIC_RUNTIME = frozenset({
    "Программа упала",
    "Ошибка выполнения",
})


def _type_how(source: str, error: str) -> str:
    if "str" in error and re.search(r"operand type\(s\) for -", error):
        return "Замени `-` на `+`."
    if "string formatting" in error or "not all arguments converted" in error:
        return "Замени `input() % ...` на `int(input()) % ...`."
    if re.search(r"=\s*input\(\)\.split\(\)", source):
        return "Замени `input().split()` на `map(int, input().split())`."
    wrapped = re.search(r"(?<![\w])int\s*\(\s*input\s*\(", source) or "map(int" in source
    if "input()" in source and not wrapped:
        if "split" in source:
            return "Замени `input().split()` на `map(int, input().split())`."
        return "Замени `input()` на `int(input())`."
    return "Оберни строку в `int(...)` перед арифметикой."


def _value_how(source: str, problem: Problem | None) -> str:
    files = " ".join(problem.files) if problem is not None else ""
    statement = (problem.statement if problem is not None else "").lower()
    if ("split(';')" in source or 'split(";")' in source) and ".csv" not in files and "csv" not in statement:
        return "Замени `split(';')` на `split()`."
    if "split(',')" in source or 'split(",")' in source:
        if ".csv" in files or "csv" in statement:
            return "Замени `split(',')` на `split(';')`."
        return "Замени `split(',')` на `split()`."
    if "int(input())" in source.replace(" ", "") and "split" not in source:
        return "Замени `int(input())` на `a, b = map(int, input().split())`."
    return "Если в строке несколько чисел — сначала split(), потом map(int, ...). int(input()) подходит только для одного числа в строке."


def _index_how(source: str, problem: Problem | None) -> str:
    tags = set(problem.tags) if problem is not None else set()
    compact = source.replace(" ", "")
    if "ege1" in tags or "g[" in compact:
        if "range(n)" in compact and "range(n+1)" not in compact:
            return "Замени `range(n)` на `range(n + 1)`: вершина n не влезает в список."
        return "Индекс вершины вылез за список смежности. Замени границу списка на `range(n + 1)`."
    if "ege17" in tags:
        return "Перед обращением проверь длину: `if i + 1 < len(a)`. Для пар в №17 цикл `for i in range(len(data) - 1)`."
    return "Индекс вылез за конец списка. Для соседей пиши `range(len(a) - 1)`."


def _recursion_how(source: str) -> str:
    if re.search(r"\b[sx]\s*-\s*\d+", source):
        return "Замени шаг с минусом на плюс: `x - 1` на `x + 1` или `s - 1` на `s + 1`."
    if "lru_cache" in source or "@cache" in source:
        return "Кэш уже стоит. Замени шаг, который уводит вызов от условия выхода."
    return "Добавь условие выхода. Если ветки уже ведут к цели, поставь `@lru_cache(None)` над функцией."


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
    advice = getattr(hint, "advice", "") if hint else ""
    if advice:
        return "Сделай именно это: " + advice.rstrip(".") + "."
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
    if "ege4" in tags:
        return "Код одной буквы фиксированной длины: `format(index, '02b')`. Если просят двоичную строку, не переводи её в hex. Чтобы расшифровать, бери куски по 2 символа."
    if "ege6" in tags:
        return "Внутри прямоугольника точек (w - 1) * (h - 1). Длина обхода по границе — `2 * (w + h)`. Площадь — `w * h`."
    if "ege7" in tags:
        return "Если в условии цвета, бери `math.ceil(math.log2(c))`, не само c. Байты — это `(биты + 7) // 8`. Секунды вверх: `(s + v - 1) // v`."
    if "ege10" in tags:
        return "Открой `10.txt`. Точное слово бери из `re.findall`, не через `text.count`. Без учёта регистра допиши `.lower()`, запятую сними через `strip`."
    if "ege3" in tags:
        return "Открой `3.txt` и дели строку через `split(';')`. Сумма груза — `sum(int(груз) for ...)`, привоз оставь фильтром `k == 'in'`."
    if "ege1" in tags:
        return "Для ребра a—b запиши обе связи: `g[a].append(b)` и `g[b].append(a)`. Степень вершины v — это `len(g[v])`, не число M."
    if "ege5" in tags:
        return "Раздели условие на проверки в скобках: «и» — and, «или» — or, «ровно одно» — !=. В конце напечатай int(условие), чтобы получить 1 или 0."
    if "games" in tags:
        return "Сначала выпиши полное состояние и точный терминал именно этой игры. Учти специальные правила (вторую кучу, запрет повтора, суперход, проигрыш при перелёте), затем перебери только допустимые ходы и проверь требуемые min/max S."
    if "ege24" in tags:
        return "Прочитай строку из файла через open(...). Иди по ней слева направо: храни длину текущей подходящей непрерывной цепочки и обновляй максимум."
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


def _hint_about(hint: Hint | None, words: tuple[str, ...]) -> Hint | None:
    if not hint:
        return None
    blob = f"{hint.title} {hint.detail}".lower()
    if any(word in blob for word in words):
        return hint
    return None


def _how_from_hint(hint: Hint | None) -> str:
    if not hint:
        return ""
    title = hint.title
    for key, text in HOW_BY_TITLE:
        if key.lower() in title.lower():
            return text
    return ""


def _syntax_how(explanation: str, line: int | None) -> str:
    if "join" in explanation and "точка" in explanation:
        where = f"Строка {line}: " if line else ""
        return where + "Поставь точку перед join: `''.join(x)` вместо `''join(x)`."
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
    ("списка смежности", "Построй список смежности и напечатай `len(g[v])`, а не M. M — число рёбер всего графа."),
    ("не из той ячейки", "Печатай `len(g[v - 1])`: рёбра лежат в ячейках `a - 1`, а `g[v]` — это уже следующая вершина."),
    ("только в одну сторону", "Рядом с `g[a].append(b)` допиши `g[b].append(a)`."),
    ("попала внутрь", "Замени формулу на `print((w - 1) * (h - 1))`. Точки на самой границе не считай."),
    ("площадь вместо длины", "Замени `w * h` на `print(2 * (w + h))`: это длина обхода по границе."),
    ("нет двойки", "Допиши двойку: `print(2 * (w + h))`. Сумма w + h — только половина пути."),
    ("цветов принято за биты", "Замени множитель `c` на `math.ceil(math.log2(c))` и добавь `import math`."),
    ("биты, не байты", "Замени print на `print((биты + 7) // 8)`."),
    ("секунды округлены", "Замени `s // v` на `(s + v - 1) // v`."),
    ("ищется как подстрока", "Замени `text.count('слово')` на `sum(word == 'слово' for word in re.findall(r'[а-яё]+', text))`."),
    ("регистр не нормализован", "Допиши `.lower()` сразу после чтения: `text = open('10.txt').read().lower()`."),
    ("препинания прилип", "Перед сравнением очисти слово: `word = word.strip('.,!?;:«»')`."),
    ("неверный разделитель", "Замени `split(',')` или `split()` на `split(';')`."),
    ("рейсы, не груз", "Замени `sum(условие)` на `sum(int(груз) for ... if условие)`."),
    ("попал и вывоз", "Допиши в фильтр привоз: `and k == 'in'`."),
    ("попали зависимые", "Замени `ans += int(t)` на `ans += int(t) if rest == ['0'] else 0`."),
    ("путь по зависимостям", "Убери `@lru_cache` и `def finish`. В цикле напиши `ans += int(t)` и в конце оставь `print(ans)`."),
    ("вычли зависимые", "Замени `print(n - ans)` на `print(ans)`."),
    ("процессы без зависимости", "Замени `rest == ['0']` на `rest != ['0']`."),
    ("путь не вычисляется", "Замени `ans += int(t)` на `finish[p] = int(t) + max((finish[x] for x in deps), default=0)` и печатай `max(finish.values())`."),
    ("значений принято", "Замени `print(v * n)` на `print(math.ceil(math.log2(v)) * n)` и добавь `import math`."),
    ("формуле and вместо or", "Замени `and z` на `or z`."),
    ("∨ записана как and", "Там, где в формуле стоит ∨, замени `and` на `or`."),
    ("записана как равенство", "Замени `==` в импликации на `<=`. p → q пишется `p <= q`."),
    ("отрезку через равенство", "Замени `a == x == b` на `a <= x <= b`."),
    ("повторы слов не убраны", "Оберни слова в множество: `print(len(set(words)))`."),
    ("принят за 1000", "Замени `1000` на `1024`: 1 Кбайт = 1024 байт."),
    ("нужна точка с запятой", "Замени `split(',')` на `split(';')`."),
    ("нужны пробелы", "Замени `split(';')` или `split(',')` на `split()` без аргументов."),
    ("потеряно not", "Замени `and y` на `and not y`."),
    ("чтение не до нуля", "Замени цикл на `while x != 0:` и после прибавления или умножения снова напиши `x = int(input())`."),
    ("произведение начато с нуля", "Замени `p = 0` на `p = 1`."),
    ("только первый делитель", "Убери `break` после `print(i)`."),
    ("считаются с единицы", "Замени `range(1, x + 1)` на `range(2, x + 1)`."),
    ("оставлены нечётные", "Замени `x % 2 == 1` на `x % 2 == 0`."),
    ("чётные не отобраны", "Оставь отбор `filter(f, числа)` или `if x % 2 == 0`, где f возвращает истину для чётного x."),
    ("кратность простого не снята", "После `a.append(i)` допиши `x //= i`."),
    ("не попала единица", "До цикла положи в список единицу и само число: `l = [1, x]`."),
    ("ищут от 2 до корня", "Замени цикл до x на `for i in range(2, int(x ** 0.5) + 1):`. При `x % i == 0` добавь и `i`, и `x // i`, затем напечатай `sorted(set(список))`."),
    ("не переведены в целые", "Замени `print(math.ceil(math.log2(a)) * n)` на `print((math.ceil(math.log2(a)) * n + 7) // 8)`."),
    ("шестнадцатеричная запись", "Убери `format(..., 'X')` и напечатай склейку `format(index, '02b')`."),
    ("нули кода", "Пиши `format(alphabet.index(ch), '02b')`. У A код 00, не 0."),
    ("стала числом", "Режь строку по два символа: `alphabet[int(bits[i:i + 2], 2)]`, где `alphabet = 'ABCD'`."),
    ("строка из файла", "Прочитай строку из файла: `s = open('24.txt').read().strip()`. Затем пройди её слева направо и обновляй длину текущей цепочки и максимум."),
    ("не делится", "Добавь в if все «не делится на …» из условия: `x % k != 0` для каждого такого k."),
    ("нет проверки", "Допиши в if недостающую проверку из условия. Не выкидывай те, что уже стоят."),

    ("склеились две строки", "Сначала преврати ввод в числа: `a, b = map(int, input().split())`, и только потом складывай."),
    ("input() вернул строку", "После input() нужен int или map(int, ...). Иначе «2» + «3» склеится в 23."),
    ("складываются строки", "Нельзя писать input() + input(). Сначала int, потом сложение."),
    ("нет вывода", "В конце должен быть print с ответом. Без print проверяльщик считает, что программа ничего не решила."),
    ("ничего не вывела", "В конце напиши print(ответ). Пустой print() проверяльщик читает как пустую строку."),
    ("формат", "Печатай ровно то, что в примере: те же пробелы, регистр, без подписи «ответ:»."),
    ("напечатан список", "Вместо print(список) напиши print(*список) — числа через пробел, без скобок."),
    ("ошибка на единицу", "В вызове range допиши конец: range(1, n + 1) или range(A, B + 1), чтобы последнее значение вошло."),
    ("range не включает N", "Замени `range(n)` на `range(1, n + 1)`."),
    ("файл не открывается", "Данные в файле. Напиши open('17.txt') или имя файла из условия — проверяльщик подставит его сам."),
    ("разделитель", "Посмотри файл: если числа через `;`, пиши split(';'). Если через пробел — split() без аргументов."),
    ("пары должны быть соседними", "В №17 пара — data[i] и data[i+1]. Не бери combinations всех элементов."),
    ("все пары, не соседние", "Один проход: for i in range(len(data) - 1). Два вложенных for дают все пары, это другая задача."),
    ("стоит and вместо or", "Замени `and` на `or`."),
    ("не доходит до n", "Замени `range(1, n)` на `range(1, n + 1)`."),
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
    ("+ n + 3", "Замени правую часть return на `2 * f(n - 1) + n + 3`."),
    ("лишнее слово", "Убери слово из print и оставь `print` только с ответом."),
    ("пустой print", "Замени `print()` на `print` с выражением ответа."),
    ("осталась строкой", "Замени `input().split()` на `map(int, input().split())`."),
    ("input() без int", "Замени `input()` на `int(input())`."),
    ("сравнивает строки", "Замени `max(input().split())` на `max(map(int, input().split()))`."),
    ("вычитание вместо сложения", "Замени `-` на `+`."),
    ("минус вместо плюса", "Замени `(n - 1)` на `(n + 1)`."),
    ("пропал + 1", "Замени `n * n // 2` на `n * (n + 1) // 2`."),
    ("or вместо and", "Замени `or` на `and`."),
    ("нужно «оба»", "Замени `or` на `and`."),
    ("уходит от цели", "Замени `x - 1` на `x + 1` в рекурсивном вызове."),
    ("записан с минусом", "Замени `s - 1` на `s + 1`."),
    ("граница отрезка через равенство", "Замени `== x` на `<= x`."),
    ("октет сравнивается", "Замени `0 == int(...)` на `0 <= int(...)`."),
    ("октета or", "Замени `or` на `and` в проверке блока адреса."),
    ("цепочки не прибавляет", "Замени `cur - 1` или `cur = cur if` на `cur = cur + 1 if`."),
    ("до самого числа", "Замени `range(2, x + 1)` на `range(2, int(x ** 0.5) + 1)` и добавь пару `x // i`."),
    ("вычитают, а не прибавляют", "Замени `-` на `+` при переходе в клетку."),
    ("шаг по таблице со знаком минус", "Замени `r - 1` на `r + 1`."),
    ("не тот split у input", "Замени `input().split(';')` на `input().split()`."),
    ("в фильтре таблицы or", "Замени `or` на `and` в условии строки."),
    ("записана как or", "Замени `or` на `and`."),
    ("тот же сосед", "Замени `a[i] + a[i]` на `a[i] + a[i + 1]`."),
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
    """Count the attempt and encourage one changed step on later tries.

    ``how`` stays the single next step: retry advice is shown beside it, not
    glued into it, so the child can tell the instruction from the praise.
    """
    from checker.topics import retry_how

    result.tries = max(1, int(tries or 1))
    if result.explanation is not None:
        retry = retry_how(problem, result.tries)
        if retry:
            result.explanation.thought = retry
    return result
