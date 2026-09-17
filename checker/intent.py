from __future__ import annotations

from checker.facts import closed_range_bounds, extract_facts, extract_outcome
from checker.models import GradeResult, Problem
import re


def apply_intent(problem: Problem, result: GradeResult, source: str = "") -> GradeResult:
    exp = result.explanation
    if not exp:
        return result
    plan = infer_intent(problem, source, result)
    if plan:
        exp.intent = plan
    exp.headline = soften_headline(exp.headline, exp.kind, result.status)
    return result


def infer_intent(problem: Problem, source: str, result: GradeResult) -> str:
    facts = extract_facts(source)
    outcome = extract_outcome(result.tests) if result.tests else None
    tags = set(problem.tags)
    blob = f"{problem.statement} {problem.title} {problem.input_format}".lower()

    if result.status == "ok":
        return "Я прогнал и пример, и скрытую проверку. Твой код считает то, что просят в условии."

    if result.status == "syntax":
        return _syntax_plan(facts, result, source)

    first = outcome.first if outcome else None
    if first and first.verdict == "RE":
        return _runtime_plan(facts, first, source)
    if first and first.verdict == "TLE":
        return _tle_plan(facts, tags)

    plan = _plan(facts, problem, tags, blob)
    gap = _gap(facts, problem, outcome, tags, blob)
    if plan and gap:
        return f"{plan} {gap}"
    return plan or gap or "Я разобрал твой код и сравнил его с условием."


def soften_headline(headline: str, kind: str, status: str) -> str:
    text = (headline or "").strip()
    if status == "ok":
        return "Получилось — код делает то, что просят."
    if not text:
        return text
    if text.startswith("Нет "):
        return "Почти: " + text[0].lower() + text[1:]
    if text.startswith("НЕТ "):
        return "Почти: " + text.lower()
    if text.startswith("Ошибка выполнения"):
        return "Код запустился, но упал — видно, на чём."
    if text == "Программа даже не запустилась":
        return "Почти написал программу — Python споткнулся о запись."
    if text == "Программа думает слишком долго":
        return "Замысел есть, но программа зациклилась."
    if text == "Программа упала":
        return "Я вижу, на какой команде код упал."
    return text


def _syntax_plan(facts, result: GradeResult, source: str) -> str:
    syn = result.syntax
    msg = ((syn.explanation if syn else "") + " " + (result.message or "")).lower()
    if "двоеточ" in msg:
        return "Ты хотел начать блок if/for/while. Python ждёт двоеточие в конце этой строки — без него дальше даже не читает."
    if source.lstrip().startswith("if ") or source.lstrip().startswith("for ") or source.lstrip().startswith("while "):
        return "Ты хотел написать условие или цикл. Синтаксис сломался до того, как программа успела что-то посчитать."
    if not source.strip():
        return "Пока нет кода, который можно понять. Напиши решение — разберу, что ты хотел."
    return "Я вижу, что ты начал программу, но Python не понял запись. Пока синтаксис сломан, логику даже не запускаю."


def _runtime_plan(facts, first, source: str) -> str:
    kind = first.error_type or ""
    err = first.error or ""
    if kind == "NameError":
        match = re.search(r"name '([^']+)'", err)
        name = match.group(1) if match else ""
        if name:
            return f"Ты обращаешься к `{name}`, как будто эта переменная уже есть. Я её в коде не нашёл — опечатка или создаёшь позже, чем читаешь."
        return "Ты используешь имя, которого в программе ещё нет."
    if kind == "IndexError":
        return "Ты хотел взять элемент списка, но индекс вылез за конец. Так бывает, если писать a[i+1] без range(len(a)-1) или трогать пустой список."
    if kind == "TypeError":
        if facts.raw_input_add or (facts.has_input and not facts.has_int):
            return "Ты хотел посчитать числа, но в этот момент в переменной ещё строка. input() без int так и оставляет текст."
        return "Ты вызвал операцию с не тем типом — часто строка вместо числа или число вместо списка."
    if kind == "ValueError":
        return "Ты хотел превратить текст в число. int() падает, если в строке несколько чисел или пусто — сначала split()."
    if kind == "ZeroDivisionError":
        return "Ты делишь одно на другое, и на этом тесте знаменатель оказался 0."
    if kind == "EOFError":
        return "Ты вызываешь input() чаще, чем есть строк во вводе. Лишняя строка чтения или данные лежат в одной строке."
    if kind == "RecursionError":
        return "Ты считаешь рекурсией, но выход не срабатывает или нет памяти @lru_cache — вызовов слишком много."
    if kind == "AttributeError":
        return "Ты вызываешь метод, которого у этого объекта нет. Например, .split() есть у строки, не у числа."
    return "Программа дошла до выполнения и упала. Я посмотрел сообщение Python и строку, на которой это случилось."


def _tle_plan(facts, tags: set[str]) -> str:
    if "ege16" in tags or "ege23" in tags:
        return "Ты считаешь рекурсией все ветки. Без @lru_cache или массива снизу вверх одни и те же значения пересчитываются снова и снова."
    if "ege8" in tags:
        return "Ты перебираешь слова. Перебор слишком широкий — сузь алфавит, длину или условие внутри цикла."
    if "ege25" in tags:
        return "Ты, похоже, гоняешь цикл до огромного числа. В №25 маску собирают, а не проверяют каждое число до миллиарда."
    if facts.has_loop:
        return "Ты крутишь цикл, который на этом тесте не заканчивается — while без изменения переменной или слишком большой range."
    return "Программа думает слишком долго. Я остановил её, чтобы она не зависла."


def _plan(facts, problem: Problem, tags: set[str], blob: str) -> str:
    src = facts.source
    if facts.constant_prints and not facts.has_loop and not facts.has_open and not facts.has_range:
        return "По коду видно: ты напечатал готовое число, как в примере."
    if facts.raw_input_add:
        return "Ты хотел сложить два введённых значения."
    if facts.has_split and not facts.has_int and facts.has_print:
        return "Ты хотел взять два числа из одной строки и сложить их."
    if facts.has_input and not facts.has_int and facts.has_print:
        return "Ты хотел прочитать ввод и что-то с ним сделать. Сейчас input() остаётся строкой."

    if "ege8" in tags:
        if "permutations" in src and "product" not in src:
            return "Ты перебираешь слова через permutations — каждая буква один раз."
        if "product" in src:
            return "Ты перебираешь все слова заданной длины из алфавита через product. Это как раз подход №8."
        if facts.nested_fors:
            return "Ты перебираешь слова вложенными циклами по буквам."
        return "Ты хотел посчитать или найти слово из букв алфавита."

    if "ege9" in tags:
        if facts.has_open:
            return "Ты открываешь файл таблицы и смотришь каждую строку. Замысел №9 верный."
        return "В №9 данные в файле-таблице. Сейчас файла в коде не видно."

    if "ege13" in tags:
        if "ipaddress" in src or "ip_network" in src or "ip_address" in src:
            return "Ты считаешь адреса через ipaddress — так на №13 и делают."
        return "Ты хотел получить IP, маску или номер узла из условия."

    if "ege14" in tags:
        if facts.moduli or "%" in src:
            return "Ты переводишь число в другую систему через остаток % и деление //. Это правильный ход."
        return "Ты хотел разобрать запись числа в другой системе счисления."

    if "ege16" in tags:
        return "Ты описываешь F(n) по формуле из условия." if "def " in src else "В №16 нужно перенести формулу F(n) в функцию или массив."
    if "ege23" in tags:
        return "Ты считаешь, сколькими командами исполнитель переводит одно число в другое."

    if "ege25" in tags:
        if "for " in src and "10**" in src.replace(" ", ""):
            return "Ты перебираешь подряд огромный диапазон. В №25 обычно собирают число по маске."
        return "Ты ищешь числа по маске или по числу делителей."

    if "ege17" in tags or "closed_range" in tags:
        bounds = closed_range_bounds(problem.statement)
        if facts.uses_combinations or (facts.nested_fors and not facts.consecutive_pair):
            return "Ты перебираешь пары «каждый с каждым». Так получают все пары, не только соседние."
        if facts.has_open and (facts.consecutive_pair or "i+1" in src.replace(" ", "") or "i + 1" in src):
            return "Ты читаешь файл и смотришь соседние числа. Для файлового №17 это как раз то, что нужно."
        if facts.has_open:
            return "Ты читаешь файл чисел и что-то по нему считаешь."
        if bounds:
            a, b = bounds
            return f"Ты хотел пройти отрезок [{a}; {b}] и отобрать подходящие числа."
        if facts.has_range:
            return "Ты идёшь циклом по отрезку чисел. Замысел такой, как в условии."
        if facts.uses_max or facts.uses_min:
            return "Ты ищешь максимум или минимум среди отобранных чисел."
        return "Ты решаешь №17: отбор чисел или пар и два числа в ответе."

    if facts.has_loop and facts.has_range:
        return "Ты хотел пройти числа циклом и что-то посчитать."
    if facts.has_loop:
        return "Ты идёшь по данным циклом."
    if facts.has_print and facts.has_input:
        return "Ты читаешь ввод и печатаешь ответ."
    if facts.has_print:
        return "Ты печатаешь ответ. Я смотрю, совпадает ли он с тем, что просят."
    return "Я разобрал твой код и сверил его с условием."


def _gap(facts, problem: Problem, outcome, tags: set[str], blob: str) -> str:
    if outcome is None:
        return ""
    if outcome.format_only:
        return "Сами значения уже те — разъехались пробелы, регистр или лишнее слово вокруг ответа."
    if outcome.off_by_one:
        return "Ответ рядом: ошибка на единицу. Часто виноват range без +1 или индекс на один шаг дальше."
    if outcome.sign_only:
        return "Модуль числа верный, знак — нет. Проверь abs и что просят: сумму, максимум или модуль."
    if outcome.count_ok and outcome.value_ok is False:
        return "Количество совпало. Второе число — нет: его считают по тем же отобранным (max, min или сумма), не по другим."
    if outcome.value_ok and outcome.count_ok is False:
        return "Второе число совпало, количество — нет. Фильтр чуть шире или уже, чем в условии."
    if outcome.count_more:
        if "сосед" in blob or ("пар" in blob and "отрезок" not in blob):
            return "Количество больше нужного: if пропускает лишнее. Не хватает какого-то условия на пару — соседи, знаки, делимость."
        return "Количество больше нужного: if пропускает лишнее. Не хватает какого-то «и не делится / и меньше» из условия."
    if outcome.count_less:
        return "Количество меньше нужного: фильтр слишком жёсткий или цикл не доходит до конца отрезка."
    if outcome.empty:
        return "Расчёт мог быть, но print не сработал — стоит внутри if, который на этом тесте не зашёл, или его нет."
    if facts.constant_prints:
        return "Подгонка под пример не проходит скрытую проверку. Нужен общий алгоритм из условия."
    if "ege17" in tags and (facts.uses_combinations or (facts.nested_fors and not facts.consecutive_pair)):
        if "сосед" in blob or "пар" in blob:
            return "В этой задаче пара — два соседних элемента, не combinations всех со всеми."
    return ""
