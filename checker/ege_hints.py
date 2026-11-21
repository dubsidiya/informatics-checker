from __future__ import annotations

import ast
import re

from checker.facts import CodeFacts, Outcome
from checker.models import Hint, Problem


def diagnose_ege(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    tags = set(problem.tags)
    if "ege1" in tags:
        return _ege1(facts, problem, outcome)
    if "ege3" in tags:
        return _ege3(facts, problem, outcome)
    if "ege4" in tags:
        return _ege4(facts, problem, outcome)
    if "ege2" in tags or "author_ege2" in tags:
        return _ege2(facts, problem, outcome)
    if "ege15" in tags:
        return _ege15(facts, problem, outcome)
    if "ege18" in tags:
        return _ege18(facts, problem, outcome)
    if "ege26" in tags:
        return _ege26(facts, problem, outcome)
    if "ege27" in tags:
        return _ege27(facts, problem, outcome)
    if "ege5" in tags:
        return _ege5(facts, problem, outcome)
    if "ege6" in tags:
        return _ege6(facts, problem, outcome)
    if "ege7" in tags:
        return _ege7(facts, problem, outcome)
    if "games" in tags:
        return _games(facts, problem, outcome)
    if "ege24" in tags:
        return _ege24(facts, problem, outcome)
    if "ege8" in tags:
        return _ege8(facts, problem, outcome)
    if "ege9" in tags:
        return _ege9(facts, problem, outcome)
    if "ege10" in tags:
        return _ege10(facts, problem, outcome)
    if "ege11" in tags:
        return _ege11(facts, problem, outcome)
    if "ege12" in tags:
        return _ege12(facts, problem, outcome)
    if "ege13" in tags:
        return _ege13(facts, problem, outcome)
    if "ege14" in tags:
        return _ege14(facts, problem, outcome)
    if "ege16" in tags:
        return _ege16(facts, problem, outcome)
    if "ege23" in tags:
        return _ege23(facts, problem, outcome)
    if "ege22" in tags:
        return _ege22(facts, problem, outcome)
    if "ege25" in tags:
        return _ege25(facts, problem, outcome)
    return []


def hint(title: str, detail: str, kind: str = "logic", weight: int = 80) -> tuple[int, Hint]:
    return weight, Hint(kind=kind, title=title, detail=detail)


def _archive_fallback(problem: Problem, text: str) -> list[tuple[int, Hint]]:
    return _ensure([], "Архивный приём применён иначе", text, weight=82)


def _subscript_edge_pairs(facts: CodeFacts) -> list[tuple[str, str]]:
    if facts.tree is None:
        return []
    pairs: list[tuple[str, str]] = []
    for node in ast.walk(facts.tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr not in {"append", "add"}:
            continue
        if not isinstance(func.value, ast.Subscript):
            continue
        index = func.value.slice
        arg = node.args[0]
        if isinstance(index, ast.Name) and isinstance(arg, ast.Name):
            pairs.append((index.id, arg.id))
    return pairs


def _one_direction(facts: CodeFacts) -> bool:
    pairs = _subscript_edge_pairs(facts)
    if not pairs:
        return False
    return not any((right, left) in pairs for left, right in pairs)


def _shifted_degree_read(source: str) -> bool:
    compact = source.replace(" ", "")
    if "a-1" not in compact and "b-1" not in compact:
        return False
    return "g[v]" in compact and "g[v-1]" not in compact


def _ege1(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found: list[tuple[int, Hint]] = []
    statement = problem.statement.lower()
    asks_degree = "степен" in statement
    needs_neighbors = any(word in statement for word in ("степен", "компонент", "путь", "треугольник"))
    if asks_degree and ".append" not in facts.source and ".add(" not in facts.source:
        found.append(hint(
            "Степень не из списка смежности",
            "Число M — сколько рёбер во всём графе. Степень вершины v — это сколько раз она встретилась в рёбрах.",
            weight=96,
        ))
    elif asks_degree and _shifted_degree_read(facts.source):
        found.append(hint(
            "Степень взята не из той ячейки",
            "Рёбра записаны в g[a - 1], а печать идёт из g[v]. Это уже другая вершина.",
            weight=96,
        ))
    elif needs_neighbors and _one_direction(facts):
        found.append(hint(
            "Ребро записано только в одну сторону",
            "Граф неориентированный: из ребра a—b в список должны попасть обе дуги, сейчас записана одна.",
            weight=96,
        ))
    if not facts.has_loop:
        found.append(hint("Граф не обработан", "Прочитай все M рёбер и построй список смежности или множество рёбер.", weight=92))
    if "append" not in facts.source and "set(" not in facts.source and "edges" not in facts.source:
        found.append(hint("Не видна модель графа", "Одного чтения чисел недостаточно: сохрани связи между вершинами.", weight=88))
    return _ensure(found, "Графовая величина посчитана иначе", "Сверь, что требуется: степень, путь, компоненты или треугольники; не смешивай вершины и рёбра.")


def _ege3(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found: list[tuple[int, Hint]] = []
    statement = problem.statement.lower()
    src = facts.source
    asks_sum = "суммарн" in statement
    asks_import = "привез" in statement or "тип `in`" in statement
    if " or " in src and " and " not in src:
        found.append(hint(
            "В фильтре таблицы or вместо and",
            "Замени `or` на `and` в условии строки.",
            weight=97,
        ))
    if not facts.has_open:
        found.append(hint("Таблица не прочитана", "Открой подключённый `3.txt` и обработай каждую строку.", weight=94))
    if facts.has_open and "split(';')" not in src and 'split(";")' not in src:
        found.append(hint(
            "Неверный разделитель таблицы",
            "Поля записи разделены точкой с запятой. Замени split(',') или split() на split(';').",
            weight=96,
        ))
    elif asks_sum and not facts.has_int:
        found.append(hint(
            "Считаются рейсы, не груз",
            "sum(условие) даёт число строк. В сумму нужно само число груза: sum(int(груз) for ... if условие).",
            weight=96,
        ))
    elif asks_import and "'in'" not in src and '"in"' not in src:
        found.append(hint(
            "В сумму попал и вывоз",
            "Привоз — это тип in. Допиши в фильтр `and k == 'in'`, иначе вывоз тоже попадёт в сумму.",
            weight=96,
        ))
    return _ensure(found, "Записи таблицы отобраны иначе", "Сверь поле фильтра, тип операции и то, что считается: сумма, количество или различные значения.")


def _ege4(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found: list[tuple[int, Hint]] = []
    statement = problem.statement.lower()
    src = facts.source
    asks_bits = "двоичную запись" in statement or "двоичная запись" in statement
    if asks_bits and any(mark in src for mark in ("'X'", '"X"', "'x'", '"x"', "hex(")):
        found.append(hint(
            "Напечатана шестнадцатеричная запись",
            "Условие просит саму двоичную строку. format(..., 'X') превращает её в другое основание.",
            weight=96,
        ))
    elif asks_bits and "02b" not in src and "zfill" not in src and "'00'" not in src and '"00"' not in src:
        found.append(hint(
            "Ведущие нули кода пропали",
            "У буквы A код 00, не 0. Без ведущих нулей коды 0, 1, 10, 11 слипаются и теряют длину.",
            weight=96,
        ))
    if "расшифр" in statement and "int(" in src and "[" not in src:
        found.append(hint(
            "Двоичная строка стала числом",
            "int(bits, 2) даёт одно число. Буквы восстанавливаются кусками по два символа.",
            weight=96,
        ))
    if "format(" not in src and "bin(" not in src and "int(" not in src:
        found.append(hint("Не выполнен перевод кода", "Используй format/bin для двоичной записи или int(bits, 2) для чтения кода.", weight=90))
    if "байт" in statement and "//" not in src:
        found.append(hint("Байты округляются вниз", "Минимальный размер в байтах: (число_бит + 7) // 8.", weight=92))
    return _ensure(found, "Кодирование посчитано иначе", "Сверь длину кода символа, основание системы и единицы результата.")


def _ege6(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found: list[tuple[int, Hint]] = []
    statement = problem.statement.lower()
    compact = facts.source.replace(" ", "")
    asks_length = "длин" in statement and "пут" in statement
    doubled = "2*" in compact or "*2" in compact
    if "внутр" in statement and "-1" not in compact and "- 1" not in facts.source:
        found.append(hint(
            "Граница попала внутрь",
            "Точки на линии не считаются внутренними. Для прямоугольника W×H внутри лежит (W-1)*(H-1), не W*H.",
            weight=96,
        ))
    elif asks_length and "*" in compact and "+" not in compact and not doubled:
        found.append(hint(
            "Посчитана площадь вместо длины пути",
            "Произведение сторон — площадь. Длина обхода прямоугольника по границе вдвое больше суммы сторон.",
            weight=96,
        ))
    elif asks_length and not doubled:
        found.append(hint(
            "В длине пути нет двойки",
            "Сумма w + h — только две стороны. Обход границы проходит ширину и высоту дважды.",
            weight=96,
        ))
    if found:
        return found
    return _archive_fallback(problem, "Сверь, что требуется: площадь, периметр, точки внутри или точки на границе.")


def _has_bit_length(source: str) -> bool:
    return "log2" in source or "log(" in source or "**" in source or "while" in source


def _seconds_rounded_down(source: str) -> bool:
    compact = source.replace(" ", "")
    if "//" not in compact or "ceil" in compact:
        return False
    return re.search(r"\+\w+-1\)//", compact) is None


def _ege7(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if outcome.empty:
        return []
    found: list[tuple[int, Hint]] = []
    statement = problem.statement.lower()
    src = facts.source
    asks_bytes = "байт" in statement
    asks_colors = "цвет" in statement
    asks_seconds = "секунд" in statement
    if asks_colors and not _has_bit_length(src):
        found.append(hint(
            "Число цветов принято за биты",
            "На цвет нужно не само C, а сколько бит его кодирует. Замени множитель c на math.ceil(math.log2(c)).",
            weight=96,
        ))
    elif asks_bytes and "log2" in src and "//" not in src:
        found.append(hint(
            "Напечатаны биты, не байты",
            "Произведение дало биты. В print поставь (биты + 7) // 8.",
            weight=96,
        ))
    elif asks_seconds and _seconds_rounded_down(src):
        found.append(hint(
            "Секунды округлены вниз",
            "s // v отбрасывает неполную секунду. Минимальное целое число секунд — (s + v - 1) // v.",
            weight=96,
        ))
    if asks_bytes and "//" not in src:
        found.append(hint("Не округлено до байта", "Минимум байтов считается как (bits+7)//8.", weight=90))
    compact = re.sub(r"\s+", "", src)
    if _has_bit_length(src) and ("1000" in compact) and "1024" not in compact:
        found.append(hint(
            "Килобайт принят за 1000",
            "1 Кбайт = 1024 байт. Деление или умножение на 1000 даёт другой объём.",
            weight=96,
        ))
    return _ensure(found, "Объём информации посчитан иначе", "Сначала посчитай биты одного объекта, потом умножь на количество и переведи в байты.")


def _punctuation_stuck(source: str, statement: str) -> bool:
    if "split(" not in source or "findall" in source or "strip(" in source or "isalpha(" in source:
        return False
    return "препинан" in statement or "пунктуац" in statement or "точн" in statement


def _ege10(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found: list[tuple[int, Hint]] = []
    statement = problem.statement.lower()
    src = facts.source
    ignores_case = "без учёта регистра" in statement or "без учета регистра" in statement
    if not facts.has_open:
        found.append(hint("Текст не открыт", "Для №10 открой подключённый файл через open('10.txt').read().", weight=94))
    if ".count(" in src and "findall" not in src and "split(" not in src:
        found.append(hint(
            "Слово ищется как подстрока",
            "text.count считает кусок внутри другого слова. Замени его на сравнение целого слова из findall.",
            weight=96,
        ))
    elif ignores_case and "lower(" not in src and "casefold(" not in src:
        found.append(hint(
            "Регистр не нормализован",
            "В условии поиск без регистра. Допиши .lower() к прочитанному тексту.",
            weight=96,
        ))
    elif _punctuation_stuck(src, statement):
        found.append(hint(
            "Знак препинания прилип к слову",
            "split() оставляет запятую на слове, и «слово,» не равно «слово». Перед сравнением очисти его через strip.",
            weight=96,
        ))
    if any(word in statement for word in ("различн", "уникаль", "разные слова")) and "set(" not in src:
        found.append(hint(
            "Повторы слов не убраны",
            "В условии нужны разные слова. Список с повторами длиннее. Оберни слова в set.",
            weight=96,
        ))
    if "split(" not in src and "findall" not in src and ".count(" not in src:
        found.append(hint("Слова не выделены", "Отдели слово от пунктуации и окончаний через split/strip или регулярное выражение.", weight=88))
    return _ensure(found, "Текст отбирается иначе", "Сверь точное совпадение, регистр и знаки препинания.")


def _ege11_needs_code_bits(statement: str) -> bool:
    if "возможных кодов" in statement or "достаточно" in statement:
        return False
    if "бит на измерение" in statement or "бит на одну запись" in statement:
        return False
    return any(word in statement for word in ("возможных значений", "видов сигналов", "размер алфавита"))


def _ege11(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    if outcome.empty:
        return []
    found: list[tuple[int, Hint]] = []
    statement = problem.statement.lower()
    src = facts.source
    compact = re.sub(r"\s+", "", src)
    value_bits = "возможных значений" in statement and "в битах" in statement
    if value_bits and "log2" not in src and "**" not in src and "v*n" in compact:
        found.append(hint(
            "Число значений принято за биты",
            "V — сколько разных значений, а не число бит на одно измерение. На одно значение нужен ceil(log2(V)).",
            weight=96,
        ))
    elif (
        _ege11_needs_code_bits(statement)
        and "log2" not in src
        and "**" not in src
        and "while" not in src
    ):
        found.append(hint(
            "Не найден размер кода",
            "Для числа вариантов нужен минимум b, при котором 2**b не меньше этого числа. Сейчас в формулу подставлено само количество вариантов.",
            weight=92,
        ))
    if "байт" in statement and "log2" in src and "//" not in src:
        found.append(hint(
            "Биты не переведены в целые байты",
            "Выражение с log2 даёт биты. Неполный последний байт тоже входит в объём.",
            weight=96,
        ))
    if "log2" in src and ("//1000" in compact or "*1000" in compact or "/1000" in compact):
        found.append(hint(
            "Килобайт принят за 1000",
            "1 Кбайт = 1024 байт и 1 Мбайт = 1024 Кбайт. Деление на 1000 даёт другой объём.",
            weight=96,
        ))
    return _ensure(found, "Объём кодирования посчитан иначе", "Сверь число вариантов, бит на объект, количество объектов и единицы.")


def _ege12(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found: list[tuple[int, Hint]] = []
    if "while" not in facts.source:
        found.append(hint("Замены выполнены не до конца", "Редактор повторяет замену, пока шаблон встречается; нужен цикл while.", weight=94))
    if ".replace" not in facts.source:
        found.append(hint("Шаблон не заменяется", "Используй replace(старое, новое, 1), чтобы менять первое вхождение.", weight=90))
    return _ensure(found, "Редактор получил другую строку", "Сверь порядок замен и условие остановки цикла.")


def _ege22_kind(statement: str) -> str:
    text = statement.lower()
    if "строго последовательно" in text or "суммарную длительность всех" in text:
        return "sum_all"
    if "максимальный идентификатор" in text and "независим" in text:
        return "max_id"
    if "независим" in text and "сумм" in text:
        return "sum_indep"
    if "хотя бы одна зависимость" in text:
        return "count_dep"
    if "предшественник" in text and "максимальн" in text:
        return "max_preds"
    if "без учёта зависимостей" in text or "без учета зависимостей" in text:
        return "max_duration"
    if "критический путь" in text:
        return "slack"
    if "время завершения" in text:
        return "critical"
    return "other"


def _compact_src(source: str) -> str:
    return re.sub(r"\s+", "", source).replace('"', "'")


def _ege22(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found: list[tuple[int, Hint]] = []
    src = facts.source
    compact = _compact_src(src)
    kind = _ege22_kind(problem.statement)
    sees_zero = "['0']" in compact or "=='0'" in compact

    if kind == "sum_indep" and "+=int(t)" in compact and not sees_zero:
        found.append(hint(
            "В сумму попали зависимые процессы",
            "Независимый процесс в строке записан как 0, а не как список. Сейчас к сумме прибавляется каждая длительность.",
            weight=96,
        ))
    elif kind == "sum_all" and ("lru_cache" in src or "def finish" in src or "@cache" in src):
        found.append(hint(
            "Считается путь по зависимостям, не сумма",
            "В коде время процесса берётся от предшественников. Здесь все длительности просто складываются, одна за другой.",
            weight=96,
        ))
    elif (
        kind == "count_dep"
        and "print(n-ans)" in compact
        and re.search(r"else1(?!\d)", compact)
        and "rest==['0']" in compact
    ):
        found.append(hint(
            "Из числа процессов вычли зависимые",
            "ans уже считает процессы, у которых вместо нуля стоит список. Вычитать ans из n значит напечатать остальные.",
            weight=96,
        ))
    elif kind == "count_dep" and "!=['0']" not in compact and (
        "ifrest==['0']:ans+=1" in compact or "ans+=1ifrest==['0']" in compact
    ):
        found.append(hint(
            "Посчитаны процессы без зависимости",
            "Ноль на месте списка означает, что зависимостей нет. Прибавление сейчас стоит на этой ветке.",
            weight=96,
        ))
    elif kind == "critical" and "lru_cache" not in src and "@cache" not in src and "max(" not in src:
        found.append(hint(
            "Критический путь не вычисляется",
            "Время процесса равно его длительности плюс максимум времени предшественников.",
            weight=96,
        ))

    if "open" not in src and not facts.has_input:
        found.append(hint("Таблица процессов не прочитана", "Пройди все строки с ID, длительностью и зависимостями.", weight=90))
    if kind == "critical":
        return _ensure(
            found,
            "Зависимости процессов обработаны иначе",
            "Зависимый процесс стартует после всех предшественников; время процесса — его длительность плюс их максимум.",
        )
    return found


def _ensure(found: list[tuple[int, Hint]], title: str, detail: str, weight: int = 80) -> list[tuple[int, Hint]]:
    if not any(item[0] >= 80 for item in found):
        found.append(hint(title, detail, weight=weight))
    return found


def _tokens(text: str) -> list[str]:
    return " ".join((text or "").replace(",", " ").replace(";", " ").split()).split()


def _lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _ege2(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found: list[tuple[int, Hint]] = []
    statement = problem.statement.lower()
    src = facts.source
    compact = re.sub(r"\s+", "", src)
    arrows = problem.statement.split("Импликация")[0].count("→")
    if arrows and src.count("<=") < arrows:
        found.append(hint(
            "Импликация записана как равенство",
            "Замени `==` на `<=`. p → q пишется `p <= q`: у False значение 0, у True значение 1.",
            weight=97,
        ))
    if "∨" in problem.statement and " or " not in src and " and " in src:
        found.append(hint(
            "В формуле ∨ записана как and",
            "Там, где в формуле стоит ∨, замени `and` на `or`.",
            weight=97,
        ))
    columns = any(word in statement for word in ("фрагмент", "столбц", "перестанов"))
    if columns:
        if not facts.has_loop:
            found.append(hint("Нет перебора таблицы", "Для №2 нужно перебрать значения 0/1 и перестановки переменных; без цикла легко пропустить вариант.", weight=92))
        if "permut" not in src and "product" not in src:
            found.append(hint(
                "Не виден перебор порядков",
                "Сначала `product([0, 1], repeat=...)` по пустым клеткам, потом `permutations` столбцов.",
                weight=88,
            ))
        if found:
            return found
        return _ensure(found, "Порядок переменных не совпал", "Импликация пишется `p <= q`. Пустые клетки перебирает product, порядок столбцов — permutations.")
    if "or z" in statement and not re.search(r"\bor\b", src) and "andz" in compact:
        found.append(hint(
            "В формуле and вместо or",
            "В условии между скобкой и z стоит or. Сейчас в коде на этом месте and.",
            weight=96,
        ))
    elif "not y" in statement and not re.search(r"\bnot\b", src) and "andy" in compact:
        found.append(hint(
            "В формуле потеряно not",
            "В формуле перед y стоит not. Сейчас y входит без not.",
            weight=96,
        ))
    return found


def _ege15(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found: list[tuple[int, Hint]] = []
    statement = problem.statement
    src = facts.source
    compact = re.sub(r"\s+", "", src)
    without_mod = re.sub(r"%\s*[A-Za-z0-9_]+\s*==\s*0", "", src)
    if re.search(r"[A-Za-z0-9_]\s*==\s*x\s*==", src) or "==x==" in compact:
        found.append(hint(
            "Принадлежность отрезку через равенство",
            "Точка лежит на [a; b], если a <= x <= b. Запись a == x == b оставляет только одну точку.",
            weight=96,
        ))
    elif ("→" in statement or "импликац" in statement.lower()) and "==" in without_mod and "<=" not in src:
        found.append(hint(
            "Импликация записана как равенство",
            "p → q пишут p <= q. Равенство истинно только когда обе стороны совпали.",
            weight=96,
        ))
    if "∨" in statement and not re.search(r"\bor\b", src) and re.search(r"\band\b", src):
        found.append(hint(
            "В формуле ∨ записана как and",
            "В условии между частями стоит ∨. Замени `and` на `or`.",
            weight=97,
        ))
    if "∧" in statement and not re.search(r"\band\b", src) and re.search(r"\bor\b", src):
        found.append(hint(
            "В формуле ∧ записана как or",
            "В условии между частями стоит ∧. Замени `or` на `and`.",
            weight=97,
        ))
    if re.search(r"\w+\s*==\s*x\b", src) and ("→" in statement or "импликац" in statement.lower() or "∈" in statement):
        found.append(hint(
            "Граница отрезка через равенство",
            "Замени `== x` на `<= x` в записи отрезка.",
            weight=97,
        ))
    if not facts.has_loop:
        found.append(hint("Нет перебора отрезков", "Перебери возможные концы A и точки x: один угаданный отрезок не доказывает максимальность.", weight=92))
    if not facts.has_if:
        found.append(hint("Не проверяется формула", "Для каждого x должно вычисляться условие с P, Q и A; затем неподходящий A нужно отбросить.", weight=88))
    return _ensure(found, "Отрезок A выбран неверно", "Сверь направление импликации: `A → P` — это `(not A) or P`; границы всех отрезков включаются.")


def _ege18(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found: list[tuple[int, Hint]] = []
    if re.search(r"\]\s*-\s*[A-Za-z_]", facts.source) or re.search(r"\[[rc]\s*-\s*1\]", facts.source):
        found.append(hint(
            "Шаг по таблице со знаком минус",
            "Замени `r - 1` на `r + 1` в переходе по таблице.",
            weight=97,
        ))
    if not facts.has_open:
        found.append(hint("Файл поля не прочитан", "Таблица лежит в подключённом файле: прочитай непустые строки через open(...), затем split().", weight=92))
    if not facts.has_loop:
        found.append(hint("Не видно динамики по клеткам", "Нужны циклы по строкам и столбцам: для каждой клетки выбираются предыдущие состояния.", weight=90))
    if not (facts.uses_min and facts.uses_max):
        found.append(hint("Нужны и максимум, и минимум", "В задаче два ответа: веди две таблицы или два значения для каждой клетки.", weight=86))
    return _ensure(found, "Маршрут робота посчитан иначе", "Для клетки проверь переходы снизу, слева и по диагонали. Диагональный вход даёт удвоенную награду.")


def _ege26(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found: list[tuple[int, Hint]] = []
    if not facts.has_open:
        found.append(hint("Файл протокола не прочитан", "Координаты находятся в подключённом файле, а не во вводе input().", weight=92))
    if not facts.uses_set:
        found.append(hint("Повторы нужно исключить", "Одна и та же точка, куда попали несколько раз, светлая только один раз. Храни позиции в set.", weight=90))
    if 2 not in facts.moduli:
        found.append(hint("Нечётность позиции не проверяется", "Учитывай только позиции, для которых `pos % 2 == 1`.", weight=86))
    return _ensure(found, "Строка с рекордом выбрана неверно", "Сначала собери уникальные нечётные позиции по каждой строке, затем сравни их количества; при равенстве нужен первый номер строки.")


def _ege27(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    found: list[tuple[int, Hint]] = []
    if not facts.has_open:
        found.append(hint("Координаты не прочитаны из файла", "Пройди строки подключённого файла и замени запятую в координатах на точку перед float().", weight=92))
    if not facts.has_loop or not facts.nested_fors:
        found.append(hint("Не видно построения кластеров", "Для связных компонент нужны обход кластера и поиск соседей по расстоянию — это вложенная проверка точек.", weight=90))
    if "sqrt" not in facts.source and "hypot" not in facts.source and "dist" not in facts.source and "** 0.5" not in facts.source:
        found.append(hint("Не вычисляется евклидово расстояние", "Используй `((x1-x2)**2 + (y1-y2)**2) ** 0.5` или `math.hypot`.", weight=86))
    return _ensure(found, "Центры кластеров найдены неверно", "Отбрось малые компоненты, затем для каждой большой выбери точку с минимальной суммой расстояний. В конце применяй int, а не round.")

def _ege5(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    """Hints shared by the small Boolean-expression exercises in EGE task 5."""
    src = facts.source.replace(" ", "")
    statement = problem.statement.lower()
    found: list[tuple[int, Hint]] = []
    got, expected = outcome.got.strip(), outcome.expected.strip()
    if (
        " и " in statement
        and "ровно одно" not in statement
        and " or " in facts.source
        and " and " not in facts.source
    ):
        found.append(hint(
            "В формуле or вместо and",
            "Замени `or` на `and`.",
            weight=97,
        ))

    if got.lower() in {"true", "false"} and expected in {"0", "1"}:
        found.append(hint(
            "Нужны 1 или 0, не True/False",
            "Логическое выражение в Python печатается как True или False. Оберни его в int(...), чтобы получить 1 или 0, как требует условие.",
            kind="format",
            weight=96,
        ))
    if "ровно одно" in statement and "!=" not in src and "^" not in src and "sum(" not in src:
        found.append(hint(
            "«Ровно одно» — не обычное or",
            "or истинно и когда подходят оба признака. Для ровно одного используй `(условие1) != (условие2)` или посчитай число истинных условий.",
            weight=92,
        ))
    if "ровно два" in statement and "==2" not in src.replace(" ", "") and "sum(" not in src:
        found.append(hint(
            "Нужно ровно два признака",
            "Сложи логические значения: `sum((условие1, условие2, условие3)) == 2`. Обычный and требует все признаки, а or — хотя бы один.",
            weight=92,
        ))
    if "или отрезку" in statement and " or " not in facts.source:
        found.append(hint(
            "Отрезки объединяются через or",
            "Число должно попасть хотя бы в один из двух отрезков. Между проверками границ нужен `or`, а внутри каждого отрезка — `and`.",
            weight=92,
        ))
    if "в любом порядке" in statement and not (facts.uses_min and facts.uses_max):
        found.append(hint(
            "Границы могут быть переставлены",
            "A может быть больше B. Сначала возьми `min(A, B)` и `max(A, B)`, затем проверь, что X строго между ними.",
            weight=92,
        ))
    if ("модуль" in statement or "|x|" in statement or "без знака" in statement or "от −" in statement or "от -" in statement) and not facts.uses_abs and "lstrip" not in facts.source:
        found.append(hint(
            "Нужно учесть модуль числа",
            "В условии знак не важен. Для числа используй `abs(x)`, а для записи строки убери минус: `s.lstrip('-')`.",
            weight=90,
        ))
    if "неверно, что" in statement and "not" not in facts.source:
        found.append(hint(
            "Нужно отрицание всего условия",
            "«Неверно, что A и B и C» — это `not (A and B and C)`. Не меняй только один признак: отрицание относится ко всей скобке.",
            weight=94,
        ))
    if "остаток равен" in statement and "in" not in facts.source and "==" not in facts.source:
        found.append(hint(
            "Проверь остаток от деления",
            "Нужен остаток `% 7`, а затем сравнение с допустимыми значениями: `x % 7 in (2, 4)`.",
            weight=90,
        ))
    if "цифр" in statement and not (facts.last_digit_mod or facts.has_split or "str(" in facts.source):
        found.append(hint(
            "Цифры числа не разобраны",
            "Для последней цифры используй `abs(x) % 10`. Для нескольких цифр можно работать со строкой или выделять цифры через % 10 и // 10.",
            weight=88,
        ))
    return _ensure(
        found,
        "Логическое условие сработало иначе",
        "Разбей условие на простые признаки в скобках. «И» — and, «или» — or, «ровно одно» — !=. В конце напечатай `int(условие)`, чтобы получить 1 или 0.",
    )


def _ege24(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    src = facts.source
    found: list[tuple[int, Hint]] = []
    if re.search(r"cur\s*=\s*cur\s*-\s*1", src) or re.search(r"cur\s*=\s*cur\s+if", src):
        found.append(hint(
            "Шаг цепочки не прибавляет единицу",
            "Замени `cur - 1` или `cur = cur if` на `cur = cur + 1 if`.",
            weight=97,
        ))
    if not facts.has_open:
        found.append(hint(
            "Строка из файла не прочитана",
            "Данные лежат в файле задачи. Начни с `s = open('24.txt').read().strip()` — проверяльщик сам подставит нужный файл.",
            weight=94,
        ))
    if "longest_run" in problem.tags and not facts.has_loop:
        found.append(hint(
            "Нужно пройти строку посимвольно",
            "Заведи `cur` и `best`: на C увеличивай cur, на другом символе сбрасывай cur. После каждого шага обновляй best.",
            weight=92,
        ))
    if "sliding_window" in problem.tags and not facts.has_loop:
        found.append(hint(
            "Нужно двигать границы цепочки",
            "Ищи запрещённую пару `AA` в строке. После неё следующая подходящая цепочка начинается с последнего A этой пары.",
            weight=92,
        ))
    if "pattern" in problem.tags and "BAFE" not in src:
        found.append(hint(
            "Проверяется не тот фрагмент",
            "Цепочка строится строго по циклу B → A → F → E. Удобно сравнивать символ с `pattern[index % 4]`, где `pattern = 'BAFE'`.",
            weight=92,
        ))
    if "pattern" in problem.tags and "BAFE" in src and not facts.has_loop:
        found.append(hint(
            "Повтор фрагмента нужно проверять по всей строке",
            "`s.count('BAFE')` считает только полные непересекающиеся куски. Пройди строку и поддерживай длину текущей цепочки BAFEBAFE...",
            weight=90,
        ))
    return _ensure(
        found,
        "Длина цепочки в строке найдена неверно",
        "Прочитай весь файл, проходи строку слева направо и храни длину текущего подходящего непрерывного фрагмента вместе с максимумом.",
    )


def _games(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    src = facts.source
    statement = problem.statement.lower()
    found: list[tuple[int, Hint]] = []
    if re.search(r"\b[sS]\s*-\s*\d+", src):
        found.append(hint(
            "Ход записан с минусом",
            "Замени `s - 1` на `s + 1`. В ходах нет вычитания.",
            weight=97,
        ))
    uses_signed = bool(re.search(r"return\s+-|==\s*-1|==\s*-2", src))
    if facts.constant_prints and not facts.has_loop and "def " not in src:
        found.append(hint(
            "Ответ напечатан, но стратегия не проверяется",
            "В задачах 19–21 нужно перебрать все S и ходы. Напечатанное число может совпасть с примером, но не доказывает стратегию.",
            weight=94,
        ))
    if "def " not in src and "@cache" not in src and "lru_cache" not in src:
        found.append(hint(
            "Нужно разобрать позиции игры",
            "Сделай функцию game(...) с полным состоянием из условия: одна/две кучи, предыдущий ход, флаг суперхода — если они влияют на правила. Терминал и набор ходов тоже берутся только из этой задачи. Сохраняй результаты через @cache или @lru_cache.",
            weight=90,
        ))
    if "неудачного первого хода" in statement and ("all(" in src or "all (" in src):
        found.append(hint(
            "Для неудачного хода нужен хотя бы один вариант",
            "В условии сказано, что Петя мог ошибиться: достаточно существования одного его хода, после которого Ваня выигрывает сразу. Используй any(...), не all(...).",
            weight=94,
        ))
    if (
        "не может выиграть первым" in statement
        and not uses_signed
        and "== 2" not in src
        and "==2" not in src
        and "r == 2" not in src
    ):
        found.append(hint(
            "Нужна победа именно вторым ходом",
            "Для №20 не подходят позиции, где Петя выигрывает сразу. В кодировке позиций ищи +2: есть стратегия второго хода, но нет выигрыша первым.",
            weight=92,
        ))
    if "Ваня имеет выигрышную стратегию" in problem.statement and "-2" not in src and "== -2" not in src:
        found.append(hint(
            "Для №21 ищут позицию −2",
            "Ваня должен выиграть первым или вторым ходом, но не гарантированно сразу. В кодировке игры это −2; не путай с −1, где Ваня выигрывает первым при любом ходе Пети.",
            weight=92,
        ))
    if "min(" not in src and "минималь" in statement:
        found.append(hint("Нужен минимальный S", "После перебора подходящих S возьми min(ответы), а не первое случайно напечатанное значение.", weight=86))
    if "max(" not in src and "наибольшее" in statement:
        found.append(hint("Нужен наибольший S", "После перебора подходящих S возьми max(ответы), а не min или первое найденное значение.", weight=86))
    return _ensure(
        found,
        "Выигрышная стратегия определена неверно",
        "Отдели точный терминал от допустимых ходов. Для №19 обычно проверяют существование неудачного хода, для №20 — гарантию второго хода, для №21 — стратегию Вани с ограничением из формулировки.",
    )


def _ege8(facts: CodeFacts, problem: Problem, outcome: Outcome) -> list[tuple[int, Hint]]:
    src = facts.source
    statement = problem.statement.lower()
    found: list[tuple[int, Hint]] = []
    repeats_forbidden = any(word in statement for word in ("различн", "не повторя", "все цифры разл"))
    if "permutations" in src and "product" not in src and "repeat" not in src and not repeats_forbidden:
        found.append(hint(
            "Буквы могут повторяться",
            "permutations берёт каждую букву один раз. Если буквы слова можно брать снова, нужен product(..., repeat=n) или вложенные циклы.",
            weight=92,
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
    if outcome.empty:
        return []
    if " and " not in facts.source and " or " in facts.source and "треугольник" in problem.statement.lower():
        found.append(hint(
            "В условии строки or вместо and",
            "Замени `or` на `and`: неравенство треугольника и равные стороны проверяются вместе.",
            weight=97,
        ))
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
            "В csv нужна точка с запятой",
            "Числа в этом csv разделены ';'. split(',') оставляет всю строку одним куском, и int падает.",
            weight=96,
        ))
    if txt_file and facts.has_open and ("split(',')" in src or "split(';')" in src or 'split(";")' in src):
        found.append(hint(
            "В txt нужны пробелы",
            "В этом txt числа разделены пробелом. split(';') или split(',') здесь не режет строку.",
            weight=96,
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
    if re.search(r"\bor\s+0\s*<=", src):
        found.append(hint(
            "В проверке октета or вместо and",
            "Замени `or` на `and`: блок годится, только если он не пустой и число от 0 до 255.",
            weight=97,
        ))
    if re.search(r"0\s*==\s*int\s*\(", src):
        found.append(hint(
            "Октет сравнивается через равенство",
            "Замени `0 == int(...)` на `0 <= int(...)`.",
            weight=97,
        ))
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
    heavy = bool(re.search(r"\d{4,}", problem.statement)) or "10**" in problem.statement or "10^" in problem.statement
    if heavy and src.count("def ") >= 1 and "lru_cache" not in src and "for " not in src and "F[" not in src and "f[" not in src:
        found.append(hint(
            "Рекурсия без памяти",
            "На больших n наивная рекурсия не успеет или упрётся в глубину. Считай снизу вверх массивом или @lru_cache.",
            weight=88,
        ))
    compact_code = re.sub(r"\s+", "", src).lower()
    compact_statement = re.sub(
        r"\s+",
        "",
        problem.statement.replace("·", "*").replace("–", "-").replace("−", "-").replace("—", "-"),
    ).lower()
    if (
        "+n+3" in compact_statement
        and "+n+3" not in compact_code
        and ("f[n-1]" in compact_code or "f(n-1)" in compact_code)
    ):
        found.append(hint(
            "В формуле потеряно + n + 3",
            "Замени правую часть return на `2 * f(n - 1) + n + 3`.",
            weight=97,
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
    if re.search(r"\b[xy]\s*-\s*\d+", src) and any(word in statement for word in ("прибавь", "умнож")):
        found.append(hint(
            "Шаг уходит от цели",
            "Замени `x - 1` на `x + 1` в рекурсивном вызове. Меньше цели — сумма веток, равно цели — 1, иначе 0.",
            weight=97,
        ))
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
    heavy = bool(re.search(r"\b\d{3,}\b", problem.statement))
    if (
        heavy
        and outcome.first.verdict == "TLE"
        and "lru_cache" not in src
        and "@cache" not in src
        and "a[" not in src
        and "dp" not in src.lower()
        and "f[" not in src.lower()
    ):
        found.append(hint(
            "Считай динамикой или с кэшем",
            "На большом n поставь `@lru_cache(None)` над функцией и прогрей её циклом.",
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
    if re.search(r"range\(\s*2\s*,\s*[xn]\s*\+\s*1\s*\)", src) and "0.5" not in src and "sqrt" not in src:
        found.append(hint(
            "Делители ищут до самого числа",
            "Замени `range(2, x + 1)` на `range(2, int(x ** 0.5) + 1)` и при `x % i == 0` добавь пару `x // i`.",
            weight=97,
        ))
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
