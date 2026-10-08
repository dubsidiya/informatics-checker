#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fill every catalog topic to forty carefully labelled practice tasks.

The archived tasks already in ``data/problems.json`` are preserved.  New
tasks are explicitly author-created and their reference programs live in
``data/author_solutions.json`` rather than in the public catalog.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "problems.json"
SOLUTIONS = ROOT / "data" / "author_solutions.json"

AUTHOR_PROVENANCE = (
    "Авторская тренировочная задача проекта; это не официальный вариант ЕГЭ."
)
ARCHIVE_PROVENANCE = (
    "Задача из учебного каталога."
)


def mistakes(*items: tuple[str, str, str]) -> list[dict[str, str]]:
    return [{"title": a, "detail": b, "signal": c} for a, b, c in items]


COMMON_MISTAKES = mistakes(
    (
        "Ввод прочитан не тем типом",
        "input() возвращает текст. Для арифметики нужны int() или map(int, ...).",
        "input",
    ),
    (
        "Граница проверена не отдельно",
        "Подставь минимальное значение, ноль и точку ровно на границе условия.",
        "boundary",
    ),
    (
        "Ответ напечатан не в формате задачи",
        "Сверь количество величин, их порядок и отсутствие лишнего текста.",
        "output",
    ),
)


def level(index: int) -> str:
    return ("старт", "средне", "сложно")[index % 3]


def text(value: Any) -> str:
    return str(value)


def task(
    *,
    problem_id: str,
    title: str,
    topic: str,
    index: int,
    tags: list[str],
    statement: str,
    input_format: str,
    output_format: str,
    cases: list[tuple[str, Any]],
    source: str,
    fast_path: str,
    mistake_map: list[dict[str, str]],
) -> tuple[dict[str, Any], dict[str, str]]:
    normalized = [(str(stdin), text(stdout)) for stdin, stdout in cases]
    item = {
        "id": problem_id,
        "title": title,
        "level": level(index),
        "topic": topic,
        "tags": tags,
        "statement": statement,
        "input_format": input_format,
        "output_format": output_format,
        "examples": [
            {"stdin": stdin, "stdout": stdout}
            for stdin, stdout in normalized[:2]
        ],
        "tests": [
            {"stdin": stdin, "stdout": stdout, "hidden": pos >= 2}
            for pos, (stdin, stdout) in enumerate(normalized)
        ],
        "files": [],
        "provenance": AUTHOR_PROVENANCE,
        "author_created": True,
        "mistake_hints": mistake_map,
        "fast_path": fast_path,
    }
    return item, {"id": problem_id, "source": source.rstrip() + "\n"}


def append(
    generated: list[tuple[dict[str, Any], dict[str, str]]],
    ids: set[str],
    item: tuple[dict[str, Any], dict[str, str]],
) -> None:
    if item[0]["id"] not in ids:
        generated.append(item)
        ids.add(item[0]["id"])


def cases_for(values: list[Any], fn: Callable[[Any], Any]) -> list[tuple[str, Any]]:
    return [(str(value), fn(value)) for value in values]


def enrich_existing(catalog: list[dict[str, Any]]) -> None:
    """Give older entries the same visible provenance/coach contract."""
    for item in catalog:
        if "provenance" not in item or not item["provenance"]:
            item["provenance"] = (
                ARCHIVE_PROVENANCE
                if str(item.get("topic", "")).startswith("ЕГЭ ")
                else "Базовая авторская тренировочная задача проекта."
            )
        item.setdefault("author_created", not str(item.get("topic", "")).startswith("ЕГЭ "))
        item.setdefault("mistake_hints", default_mistakes(item))
        item.setdefault("fast_path", default_fast_path(item))


def default_mistakes(item: dict[str, Any]) -> list[dict[str, str]]:
    topic = str(item.get("topic", ""))
    if topic in {"ЕГЭ 2", "ЕГЭ 5"}:
        return mistakes(
            ("Таблица/условие прочитаны не целиком", "Раздели выражение на маленькие булевы признаки и проверь их независимо.", "condition"),
            ("and и or перепутаны", "«Оба» — and, «хотя бы одно» — or, «ровно одно» — !=.", "condition"),
            ("Пример принят за ответ", "Проверь ещё строку, где ровно один признак меняется.", "constant"),
        )
    if topic in {"ЕГЭ 8", "ЕГЭ 9", "ЕГЭ 13", "ЕГЭ 14", "ЕГЭ 17", "ЕГЭ 25"}:
        return mistakes(
            ("Считался не тот набор объектов", "Сначала выпиши, что является одной строкой/словом/числом, и только потом фильтруй.", "always"),
            ("Граница или формат потеряны", "Проверь включение правого конца, нумерацию с 1 и точный формат вывода.", "boundary"),
            ("Перебор сделан шире, чем нужно", "Остановись на первом различающемся условии и не пересчитывай уже найденные данные.", "complexity"),
        )
    if topic in {"ЕГЭ 15", "ЕГЭ 18", "ЕГЭ 19–21", "ЕГЭ 23", "ЕГЭ 24", "ЕГЭ 26", "ЕГЭ 27"}:
        return mistakes(
            ("Состояние задачи определено неверно", "Выпиши маленький случай и назови, что именно хранится в одной позиции/состоянии.", "algorithm"),
            ("Крайний переход пропущен", "Проверь старт, финиш, пустой компонент и самый маленький допустимый размер.", "boundary"),
            ("Рабочий, но медленный перебор", "Сначала оцени количество повторных вычислений и замени их динамикой, set или одним проходом.", "complexity"),
        )
    return list(COMMON_MISTAKES)


def default_fast_path(item: dict[str, Any]) -> str:
    topic = str(item.get("topic", ""))
    recipes = {
        "ввод-вывод": "Считай ввод один раз, выполни формулу напрямую и напечатай только нужный результат.",
        "циклы": "Обновляй счётчик или сумму в одном проходе; если диапазон большой, ищи формулу или шаг по кратным.",
        "условия": "Собери одно логическое выражение в скобках и преврати его в 0/1 через int(...).",
        "числа": "Для цифр обрабатывай запись числа за O(числа цифр), а не перебирай весь диапазон.",
        "строки": "Сделай один проход по строке и не создавай одинаковые срезы внутри цикла.",
        "списки": "Храни только нужный агрегат и проходи список один раз; set используй для задачи о различных элементах.",
        "поиск": "Раздели фильтр и обновление ответа; для поиска пары используй множество и получи O(n).",
        "на пути к ЕГЭ": "Сначала выдели один приём задачи, затем реализуй его одним проходом без лишних промежуточных списков.",
    }
    if topic in recipes:
        return recipes[topic]
    if topic == "ЕГЭ 2":
        return "Перебери 24 порядка столбцов и отбрасывай порядок на первой несовместимой строке."
    if topic == "ЕГЭ 15":
        return "Сначала найди точки, где формула может быть ложной, и только потом проверяй кандидата на A."
    if topic == "ЕГЭ 18":
        return "Храни min/max для каждой клетки и переходи только из допустимых предшественников; это O(N²)."
    if topic == "ЕГЭ 19–21":
        return "Закэшируй состояние игры: одинаковая позиция должна считаться один раз."
    if topic == "ЕГЭ 24":
        return "Один проход с текущей длиной и максимумом быстрее пересоздания подстрок."
    if topic == "ЕГЭ 26":
        return "Множество на строку убирает повторы за O(1) в среднем; максимум обновляй после чтения строки."
    if topic == "ЕГЭ 27":
        return "Сначала найди компоненты, затем один раз вычисли медоид каждой; для больших данных используй пространственное разбиение."
    return "Проверь, можно ли заменить вложенный перебор одним проходом, словарём или динамикой."


def gen_basic_io(generated: list, ids: set[str], count: int) -> None:
    topic = "ввод-вывод"
    families = [
        ("Сумма трёх", "a,b,c=map(int,input().split())\nprint(a+b+c)", lambda v: sum(v), "Три числа. Выведи сумму.", 3),
        ("Разность крайних", "a,b,c=map(int,input().split())\nprint(a-c)", lambda v: v[0]-v[2], "Три числа. Выведи первое минус последнее.", 3),
        ("Произведение", "a,b=map(int,input().split())\nprint(a*b)", lambda v: v[0]*v[1], "Два числа. Выведи произведение.", 2),
        ("Периметр", "a,b=map(int,input().split())\nprint(2*(a+b))", lambda v: 2*(v[0]+v[1]), "Даны стороны прямоугольника. Выведи периметр.", 2),
        ("Частное и остаток", "n,k=map(int,input().split())\nprint(n//k,n%k)", lambda v: f"{v[0]//v[1]} {v[0]%v[1]}", "Даны N и K. Выведи частное и остаток N на K.", 2),
        ("Квадрат разности", "a,b=map(int,input().split())\nprint((a-b)**2)", lambda v: (v[0]-v[1])**2, "Даны A и B. Выведи квадрат разности.", 2),
        ("Полные десятки", "print(int(input())//10)", lambda v: v[0]//10, "Дано N. Выведи число полных десятков.", 1),
        ("Последние две цифры", "print(int(input())%100)", lambda v: v[0]%100, "Дано N. Выведи последние две цифры как число.", 1),
        ("Сумма квадратов", "a,b=map(int,input().split())\nprint(a*a+b*b)", lambda v: v[0]**2+v[1]**2, "Даны A и B. Выведи сумму квадратов.", 2),
        ("Часы и минуты", "m=int(input())\nprint(m//60,m%60)", lambda v: f"{v[0]//60} {v[0]%60}", "Дано число минут. Выведи полные часы и остаток минут.", 1),
        ("Число десятков и единиц", "n=int(input())\nprint(n//10,n%10)", lambda v: f"{v[0]//10} {v[0]%10}", "Дано двузначное число. Выведи его десятки и единицы.", 1),
        ("Координаты", "x,y,dx,dy=map(int,input().split())\nprint(x+dx,y+dy)", lambda v: f"{v[0]+v[2]} {v[1]+v[3]}", "Даны X,Y и смещение DX,DY. Выведи новые координаты.", 4),
    ]
    values = [[2, 5, 9, 4], [-7, 3, 10, -2], [0, 1, 4, 6], [12, 4, 8, 3], [99, 6, 3, 5]]
    for i in range(count):
        name, source, fn, statement, width = families[i % len(families)]
        vals = [row[:width] for row in values]
        append(generated, ids, task(
            problem_id=f"author-io-{i+1:02d}", title=f"Ввод-вывод: {name} · вариант {i//len(families)+1}",
            topic=topic, index=i, tags=["author_basic", "integers_from_input", "two_int_out" if " и " in statement and "два" in statement.lower() else "single_int_out"],
            statement=statement, input_format="Целые числа в одной строке через пробел.", output_format="Ответ указан в условии.",
            cases=[(" ".join(map(str, row)), fn(row)) for row in vals], source=source,
            fast_path=default_fast_path({"topic": topic}), mistake_map=list(COMMON_MISTAKES),
        ))


def gen_cycles(generated: list, ids: set[str], count: int) -> None:
    topic = "циклы"
    for i in range(count):
        mode = i % 8
        n_values = [1, 5, 10, 17, 32]
        if mode == 0:
            k = 2 + i % 6
            source = f"n,k=map(int,input().split())\nprint(sum(x for x in range(1,n+1) if x%k==0))"
            statement = f"Даны N и K. Найди сумму чисел от 1 до N, кратных {k if False else 'K'}."
            cases = [(f"{n} {k}", sum(x for x in range(1, n+1) if x % k == 0)) for n in n_values]
        elif mode == 1:
            source = "n=int(input())\nprint(sum(x*x for x in range(1,n+1)))"
            statement = "Дано N. Найди сумму квадратов чисел от 1 до N."
            cases = [(str(n), sum(x*x for x in range(1, n+1))) for n in n_values]
        elif mode == 2:
            source = "n=int(input())\nprint(sum(int(c)%2==0 for c in str(n)))"
            statement = "Дано неотрицательное N. Посчитай чётные цифры в его записи."
            cases = [(str(n), sum(int(c) % 2 == 0 for c in str(n))) for n in [0, 7, 105, 2468, 9999]]
        elif mode == 3:
            source = "n=int(input())\nprint(max(map(int,str(n))))"
            statement = "Дано неотрицательное N. Выведи его максимальную цифру."
            cases = [(str(n), max(map(int, str(n)))) for n in [0, 7, 105, 2468, 9999]]
        elif mode == 4:
            source = "n=int(input())\np=1\nfor x in range(1,n+1,2):\n    p*=x\nprint(p)"
            statement = "Дано N. Найди произведение нечётных чисел от 1 до N."
            cases = [(str(n), math.prod(range(1, n+1, 2))) for n in [1, 2, 5, 8, 11]]
        elif mode == 5:
            source = "n=int(input())\nprint(sum(1 for x in range(1,n+1) if x%3==0 or x%5==0))"
            statement = "Дано N. Посчитай числа от 1 до N, кратные 3 или 5."
            cases = [(str(n), sum(x % 3 == 0 or x % 5 == 0 for x in range(1, n+1))) for n in n_values]
        elif mode == 6:
            source = "n=int(input())\ns=0\nwhile n:\n    s+=n%10\n    n//=10\nprint(s)"
            statement = "Дано неотрицательное N. Найди сумму его цифр циклом."
            cases = [(str(n), sum(map(int, str(n)))) for n in [0, 7, 105, 2468, 9999]]
        else:
            source = "n=int(input())\nc=0\nfor x in range(1,n+1):\n    if n%x==0:\n        c+=1\nprint(c)"
            statement = "Дано положительное N. Посчитай число его делителей."
            cases = [(str(n), sum(n % x == 0 for x in range(1, n+1))) for n in [1, 2, 6, 12, 36]]
        append(generated, ids, task(
            problem_id=f"author-cycles-{i+1:02d}", title=f"Циклы: упражнение {i+1}", topic=topic, index=i,
            tags=["author_basic", "integers_from_input", "single_int_out", "loop"], statement=statement,
            input_format="Ввод указан в условии.", output_format="Одно целое число.", cases=cases, source=source,
            fast_path=default_fast_path({"topic": topic}), mistake_map=mistakes(
                ("range не включает конец", "Если N должно участвовать, используй range(..., N + 1).", "range"),
                ("Аккумулятор обновляется не там", "Инициализируй сумму/счётчик до цикла и обновляй только после проверки.", "loop"),
                ("Перебор слишком большой", "Для цифр обрабатывай разряды, а для кратных используй шаг K или формулу.", "complexity"),
            ),
        ))


def gen_conditions(generated: list, ids: set[str], count: int) -> None:
    topic = "условия"
    for i in range(count):
        mode = i % 8
        if mode == 0:
            a, b = -10 - i, 10 + i
            source = f"x=int(input())\nprint(int({a}<=x<={b}))"
            statement = f"Дано X. Выведи 1, если X лежит на отрезке [{a}; {b}], иначе 0."
            fn = lambda x, a=a, b=b: int(a <= x <= b)
        elif mode == 1:
            d = 3 + i % 7
            source = f"x=int(input())\nprint(int(x%{d}==0))"
            statement = f"Дано X. Выведи 1, если X делится на {d}, иначе 0."
            fn = lambda x, d=d: int(x % d == 0)
        elif mode == 2:
            a, b = 4 + i % 7, 8 + i % 5
            source = f"x=int(input())\nprint(int(x=={a} or x=={b}))"
            statement = f"Дано X. Выведи 1, если X равен {a} или {b}, иначе 0."
            fn = lambda x, a=a, b=b: int(x == a or x == b)
        elif mode == 3:
            d = 5 + i % 5
            source = f"x=int(input())\nprint(int(x>0 and x%{d}!=0))"
            statement = f"Дано X. Выведи 1, если он положителен и не делится на {d}, иначе 0."
            fn = lambda x, d=d: int(x > 0 and x % d != 0)
        elif mode == 4:
            source = "x=int(input())\nprint(int(abs(x)%2==1 and abs(x)<20))"
            statement = "Дано X. Выведи 1, если его модуль нечётен и меньше 20, иначе 0."
            fn = lambda x: int(abs(x) % 2 == 1 and abs(x) < 20)
        elif mode == 5:
            source = "x=int(input())\nprint(int(x<0 or x>100))"
            statement = "Дано X. Выведи 1, если X вне отрезка [0; 100], иначе 0."
            fn = lambda x: int(x < 0 or x > 100)
        elif mode == 6:
            source = "x=int(input())\nprint(int(x%4==0 and x%6!=0))"
            statement = "Дано X. Выведи 1, если X делится на 4, но не делится на 6."
            fn = lambda x: int(x % 4 == 0 and x % 6 != 0)
        else:
            source = "x=int(input())\nprint(int((x%2==0)!=(x%3==0)))"
            statement = "Дано X. Выведи 1, если ровно одно из условий выполнено: X чётен, X делится на 3."
            fn = lambda x: int((x % 2 == 0) != (x % 3 == 0))
        values = [-21, -10, -1, 0, 1, 4, 6, 12, 15, 20, 36, 101]
        append(generated, ids, task(
            problem_id=f"author-conditions-{i+1:02d}", title=f"Условия: упражнение {i+1}", topic=topic, index=i,
            tags=["author_basic", "integers_from_input", "single_int_out", "boolean_condition"], statement=statement,
            input_format="Одно целое число X.", output_format="1 или 0.", cases=cases_for(values, fn), source=source,
            fast_path=default_fast_path({"topic": topic}), mistake_map=mistakes(
                ("and/or переведены неверно", "«Оба» — and, «хотя бы одно» — or, «ровно одно» — !=.", "condition"),
                ("Граница пропущена", "Проверь значение ровно на границе и сразу за ней.", "boundary"),
                ("True/False вместо 1/0", "Оберни выражение в int(...), если формат требует числа.", "output"),
            ),
        ))


def gen_numbers(generated: list, ids: set[str], count: int) -> None:
    topic = "числа"
    families = [
        ("Сумма цифр", "n=int(input())\nprint(sum(map(int,str(abs(n)))))", lambda n: sum(map(int, str(abs(n)))), "digits"),
        ("Количество цифр", "n=int(input())\nprint(len(str(abs(n))))", lambda n: len(str(abs(n))), "digits"),
        ("Последняя цифра", "n=int(input())\nprint(abs(n)%10)", lambda n: abs(n) % 10, "digits"),
        ("Наоборот", "n=int(input())\nprint(int(str(abs(n))[::-1]))", lambda n: int(str(abs(n))[::-1]), "digits"),
        ("Максимальная цифра", "n=int(input())\nprint(max(map(int,str(abs(n)))))", lambda n: max(map(int, str(abs(n)))), "digits"),
        ("Минимальная цифра", "n=int(input())\nprint(min(map(int,str(abs(n)))))", lambda n: min(map(int, str(abs(n)))), "digits"),
        ("Палиндром", "n=int(input())\ns=str(abs(n))\nprint(int(s==s[::-1]))", lambda n: int(str(abs(n)) == str(abs(n))[::-1]), "digits"),
        ("Простое число", "n=int(input())\nprint(int(n>1 and all(n%d for d in range(2,int(n**0.5)+1))))", lambda n: int(n > 1 and all(n % d for d in range(2, int(n**0.5)+1))), "prime"),
        ("Число делителей", "n=int(input())\nprint(sum(n%d==0 for d in [0] for d in range(1,n+1)))", lambda n: sum(n % d == 0 for d in range(1, n+1)), "divisors"),
        ("НОД с 12", "import math\nn=int(input())\nprint(math.gcd(n,12))", lambda n: math.gcd(n, 12), "gcd"),
        ("Остаток по 7", "n=int(input())\nprint(n%7)", lambda n: n % 7, "divisibility"),
        ("Длина двоичной записи", "n=int(input())\nprint(len(bin(n))-2)", lambda n: len(bin(n)) - 2, "binary"),
    ]
    values = [0, 7, 10, 105, 2468]
    for i in range(count):
        name, source, fn, tag = families[i % len(families)]
        vals = [2, 3, 4, 17, 25] if tag == "prime" else [1, 2, 6, 12, 36] if tag == "divisors" else values
        append(generated, ids, task(
            problem_id=f"author-numbers-{i+1:02d}", title=f"Числа: {name} · вариант {i//len(families)+1}", topic=topic, index=i,
            tags=["author_basic", "integers_from_input", "single_int_out", tag], statement=f"Дано целое число N. {name}.",
            input_format="Одно целое число N.", output_format="Одно целое число или 0/1 по условию.", cases=cases_for(vals, fn), source=source,
            fast_path=default_fast_path({"topic": topic}), mistake_map=mistakes(
                ("% и // перепутаны", "% получает последнюю цифру/остаток, // отбрасывает разряд.", "digits"),
                ("Ноль или знак не проверены", "Отдельно пройди N=0 и отрицательное число, если оно разрешено.", "boundary"),
                ("Перебор слишком широкий", "Работай с цифрами числа, а не со всеми числами до N.", "complexity"),
            ),
        ))


def gen_strings(generated: list, ids: set[str], count: int) -> None:
    topic = "строки"
    families = [
        ("Длина", "s=input()\nprint(len(s))", lambda s: len(s), "single_int_out"),
        ("Первый символ", "s=input()\nprint(s[0])", lambda s: s[0], "single_token_out"),
        ("Последний символ", "s=input()\nprint(s[-1])", lambda s: s[-1], "single_token_out"),
        ("Число A", "s=input()\nprint(s.count('A'))", lambda s: s.count("A"), "single_int_out"),
        ("Число цифр", "s=input()\nprint(sum(c.isdigit() for c in s))", lambda s: sum(c.isdigit() for c in s), "single_int_out"),
        ("Разворот", "s=input()\nprint(s[::-1])", lambda s: s[::-1], "single_token_out"),
        ("Нижний регистр", "s=input()\nprint(s.lower())", lambda s: s.lower(), "single_token_out"),
        ("Верхний регистр", "s=input()\nprint(s.upper())", lambda s: s.upper(), "single_token_out"),
        ("Число слов", "s=input()\nprint(len(s.split()))", lambda s: len(s.split()), "single_int_out"),
        ("Есть AB", "s=input()\nprint(int('ab' in s.lower()))", lambda s: int("ab" in s.lower()), "single_int_out"),
        ("Различные символы", "s=input()\nprint(len(set(s)))", lambda s: len(set(s)), "single_int_out"),
        ("Палиндром", "s=input().lower()\nprint(int(s==s[::-1]))", lambda s: int(s.lower() == s.lower()[::-1]), "single_int_out"),
    ]
    values = ["Hello", "ABBA", "a b c", "A1B20", "abracadabra", "XYZ"]
    for i in range(count):
        name, source, fn, tag = families[i % len(families)]
        append(generated, ids, task(
            problem_id=f"author-strings-{i+1:02d}", title=f"Строки: {name} · вариант {i//len(families)+1}", topic=topic, index=i,
            tags=["author_basic", "string_input", tag], statement=f"Дана строка S. {name}.", input_format="Одна строка текста.",
            output_format="Ответ по условию.", cases=cases_for(values, fn), source=source,
            fast_path=default_fast_path({"topic": topic}), mistake_map=mistakes(
                ("Строка обработана как число", "input() здесь уже возвращает текст; не вызывай int без необходимости.", "input"),
                ("Граница строки пропущена", "Проверь односимвольную строку и последний символ отдельно.", "boundary"),
                ("Регистр/пробелы не определены", "Явно реши по условию, важны ли регистр и пробелы.", "always"),
            ),
        ))


def list_cases(fn: Callable[[list[int]], Any]) -> list[tuple[str, Any]]:
    # Keep at least two elements and at least two distinct values: the
    # neighbor/second-distinct families intentionally require both.
    arrays = [[1, 2, 3, 4], [0, -2, 5, 7], [9, 1], [3, 3, 1, 3], [-5, -1, -9, 0]]
    return [(" ".join(map(str, arr)), fn(arr)) for arr in arrays]


def gen_lists(generated: list, ids: set[str], count: int) -> None:
    topic = "списки"
    families = [
        ("Сумма", "a=list(map(int,input().split()))\nprint(sum(a))", sum, "single_int_out"),
        ("Максимум", "a=list(map(int,input().split()))\nprint(max(a))", max, "single_int_out"),
        ("Минимум", "a=list(map(int,input().split()))\nprint(min(a))", min, "single_int_out"),
        ("Положительные", "a=list(map(int,input().split()))\nprint(sum(x>0 for x in a))", lambda a: sum(x > 0 for x in a), "single_int_out"),
        ("Нули", "a=list(map(int,input().split()))\nprint(sum(x==0 for x in a))", lambda a: sum(x == 0 for x in a), "single_int_out"),
        ("Сумма чётных", "a=list(map(int,input().split()))\nprint(sum(x for x in a if x%2==0))", lambda a: sum(x for x in a if x % 2 == 0), "single_int_out"),
        ("Различные", "a=list(map(int,input().split()))\nprint(len(set(a)))", lambda a: len(set(a)), "single_int_out"),
        ("Разворот", "a=list(map(int,input().split()))\nprint(*a[::-1])", lambda a: " ".join(map(str, a[::-1])), "multi_int_out"),
        ("Соседний максимум", "a=list(map(int,input().split()))\nprint(max(a[i]+a[i+1] for i in range(len(a)-1)))", lambda a: max(a[i] + a[i+1] for i in range(len(a)-1)), "single_int_out"),
        ("Второй различный", "a=sorted(set(map(int,input().split())))\nprint(a[-2])", lambda a: sorted(set(a))[-2], "single_int_out"),
    ]
    for i in range(count):
        name, source, fn, tag = families[i % len(families)]
        append(generated, ids, task(
            problem_id=f"author-lists-{i+1:02d}", title=f"Списки: {name} · вариант {i//len(families)+1}", topic=topic, index=i,
            tags=["author_basic", "sequence", "integers_from_input", tag], statement=f"Дана строка целых чисел. {name}.",
            input_format="Одна строка целых чисел через пробел.", output_format="Ответ по условию.", cases=list_cases(fn), source=source,
            fast_path=default_fast_path({"topic": topic}), mistake_map=mistakes(
                ("Прочитан не весь список", "Сделай split() по всей строке и преобразуй каждый элемент.", "input"),
                ("Соседний индекс вышел за границу", "Для пары используй range(len(a)-1).", "boundary"),
                ("Повторы не убраны", "Если нужны различные элементы, применяй set до подсчёта.", "set"),
            ),
        ))


def gen_search(generated: list, ids: set[str], count: int) -> None:
    topic = "поиск"
    arrays = [[1, 4, 2, 4, 8], [0, -2, 5, 7], [9, 9, 1], [3, 3, 1, 3], [-5, -1, -9, 0]]
    for i in range(count):
        mode = i % 6
        if mode == 0:
            source = "a=list(map(int,input().split()))\nx=int(input())\nprint(a.index(x)+1 if x in a else -1)"
            statement = "Даны список и X. Выведи номер первого X с нумерацией с 1, либо -1."
            fn = lambda a, x: a.index(x) + 1 if x in a else -1
        elif mode == 1:
            source = "a=list(map(int,input().split()))\nx=int(input())\nprint(a.count(x))"
            statement = "Даны список и X. Посчитай вхождения X."
            fn = lambda a, x: a.count(x)
        elif mode == 2:
            source = "a=list(map(int,input().split()))\nx=int(input())\nprint(int(any(a[j]+a[k]==x for j in range(len(a)) for k in range(j+1,len(a)))))"
            statement = "Даны список и S. Выведи 1, если два разных элемента дают сумму S."
            fn = lambda a, x: int(any(a[j] + a[k] == x for j in range(len(a)) for k in range(j + 1, len(a))))
        elif mode == 3:
            source = "a=list(map(int,input().split()))\nprint(next((i+1 for i,x in enumerate(a) if x>0),-1))"
            statement = "Дан список. Выведи номер первого положительного элемента или -1."
            fn = lambda a, x=None: next((j + 1 for j, value in enumerate(a) if value > 0), -1)
        elif mode == 4:
            source = "a=list(map(int,input().split()))\nprint(a.index(max(a))+1)"
            statement = "Дан список. Выведи номер первого максимального элемента."
            fn = lambda a, x=None: a.index(max(a)) + 1
        else:
            source = "a=list(map(int,input().split()))\nx=int(input())\nprint(len(a)-a[::-1].index(x) if x in a else -1)"
            statement = "Даны список и X. Выведи номер последнего X с нумерацией с 1, либо -1."
            fn = lambda a, x: len(a) - a[::-1].index(x) if x in a else -1
        cases = []
        for arr in arrays:
            x = arr[0] if mode != 2 else arr[0] + arr[-1]
            value = fn(arr, x)
            stdin = " ".join(map(str, arr)) if mode in {3, 4} else " ".join(map(str, arr)) + "\n" + str(x)
            cases.append((stdin, value))
        append(generated, ids, task(
            problem_id=f"author-search-{i+1:02d}", title=f"Поиск: упражнение {i+1}", topic=topic, index=i,
            tags=["author_basic", "sequence", "two_line_input", "single_int_out"], statement=statement,
            input_format="Список в первой строке; X/S во второй, если указан.", output_format="Одно число.", cases=cases, source=source,
            fast_path=default_fast_path({"topic": topic}), mistake_map=mistakes(
                ("Перепутана нумерация", "Индекс Python начинается с 0, а номер в условии — с 1.", "boundary"),
                ("Поиск остановлен слишком рано", "Для последнего вхождения и количества нужно обработать весь список.", "always"),
                ("Пара ищется квадратично", "Храни уже просмотренные элементы в set и проверяй дополнение.", "complexity"),
            ),
        ))


def gen_bridge(generated: list, ids: set[str], count: int) -> None:
    topic = "на пути к ЕГЭ"
    for i in range(count):
        mode = i % 6
        if mode == 0:
            d = 3 + i % 6
            source = "a=list(map(int,input().split()))\nprint(sum(x%K==0 for x in a))".replace("K", str(d))
            statement = f"Дан список. Посчитай числа, делящиеся на {d}."
            cases = [(s, sum(x % d == 0 for x in map(int, s.split()))) for s in ["1 3 6 7 12", "0 -3 4 9", "2 5 8", "6 12 18"]]
        elif mode == 1:
            d = 4 + i % 5
            source = f"n=int(input())\nprint(int(n%{d}==0))"
            statement = f"Дано N. Выведи 1, если N кратно {d}, иначе 0."
            cases = [(str(x), int(x % d == 0)) for x in [0, d, d + 1, -d, 17]]
        elif mode == 2:
            source = "s=input()\nprint(max(map(len,s.split('0'))))"
            statement = "Дана строка цифр. Найди длину самой длинной цепочки без нулей."
            cases = [(s, max(map(len, s.split("0")))) for s in ["110101", "000", "123450067", "9"]]
        elif mode == 3:
            source = "n=int(input())\nprint(bin(n)[2:].count('1'))"
            statement = "Дано N. Выведи число единиц в его двоичной записи."
            cases = [(str(x), bin(x)[2:].count("1")) for x in [0, 1, 5, 10, 31]]
        elif mode == 4:
            source = "a=list(map(int,input().split()))\nprint(max((a[i]+a[i+1] for i in range(len(a)-1) if a[i]>0 and a[i+1]>0),default=0))"
            statement = "Дан список. Выведи максимальную сумму соседней пары положительных чисел, либо 0."
            arrays = [[1, 2, -1, 8], [-1, 0, -2], [5, 5, 1], [2, 9]]
            cases = [(" ".join(map(str, a)), max((a[j] + a[j + 1] for j in range(len(a) - 1) if a[j] > 0 and a[j + 1] > 0), default=0)) for a in arrays]
        else:
            source = "n=int(input())\nprint(sum(x%3==0 or x%5==0 for x in range(1,n+1)))"
            statement = "Дано N. Посчитай числа от 1 до N, кратные 3 или 5."
            cases = [(str(x), sum(x % 3 == 0 or x % 5 == 0 for x in range(1, x + 1))) for x in [1, 5, 10, 15, 31]]
        append(generated, ids, task(
            problem_id=f"author-bridge-{i+1:02d}", title=f"Переходная задача: упражнение {i+1}", topic=topic, index=i,
            tags=["author_bridge", "single_int_out"], statement=statement, input_format="Ввод указан в условии.", output_format="Ответ по условию.",
            cases=cases, source=source, fast_path=default_fast_path({"topic": topic}), mistake_map=list(COMMON_MISTAKES),
        ))


def gen_ege2(generated: list, ids: set[str], count: int) -> None:
    topic = "ЕГЭ 2"
    formulas = [
        ("(x and not y) or z", lambda x, y, z, w: (x and not y) or z),
        ("(x == y) and (z or not w)", lambda x, y, z, w: (x == y) and (z or not w)),
        ("(x or y) and (not z or w)", lambda x, y, z, w: (x or y) and (not z or w)),
        ("(x != z) or (y and w)", lambda x, y, z, w: (x != z) or (y and w)),
    ]
    rows = [(0, 1, 0, 1), (1, 0, 1, 0), (1, 1, 0, 0), (0, 0, 1, 1)]
    for i in range(count):
        formula, fn = formulas[i % len(formulas)]
        source = f"n=int(input())\nans=0\nfor _ in range(n):\n    x,y,z,w=map(int,input().split())\n    ans+=int({formula})\nprint(ans)"
        chosen = rows[:]
        cases=[]
        for shift in range(5):
            data = chosen[shift % 2:] + chosen[:shift % 2]
            expected = sum(bool(fn(*row)) for row in data)
            cases.append((str(len(data)) + "\n" + "\n".join(" ".join(map(str, row)) for row in data), expected))
        append(generated, ids, task(
            problem_id=f"author-ege2-{i+1:02d}", title=f"ЕГЭ 2 · логическая таблица {i+1}", topic=topic, index=i,
            tags=["author_ege2", "logic_table", "single_int_out"], statement=f"В таблице из N строк вычисляется F = {formula}. Выведи число строк, где F истинна.",
            input_format="N, затем N строк с четырьмя нулями/единицами x y z w.", output_format="Одно число — количество истинных строк.", cases=cases, source=source,
            fast_path="Один проход по строкам за O(N) проще полного перебора всех 16 наборов; каждую переменную сначала сопоставь с именем в формуле.",
            mistake_map=mistakes(("Импликация/эквивалентность заменены неверно", "Раскрой каждый логический оператор отдельно и проверь строку 0/1 вручную.", "condition"), ("and и or перепутаны", "Проверь строку, где истинна только одна часть выражения.", "condition"), ("Посчитаны не все строки", "Цикл должен выполнить ровно N итераций.", "loop")),
        ))


def gen_ege5(generated: list, ids: set[str], count: int) -> None:
    topic = "ЕГЭ 5"
    for i in range(count):
        mode=i%5
        if mode==0:
            d=3+i%6; source=f"x=int(input())\nprint(int(x>0 and x%{d}==0))"; statement=f"Выведи 1, если X положителен и делится на {d}."; fn=lambda x,d=d:int(x>0 and x%d==0)
        elif mode==1:
            source="x=int(input())\nprint(int(10<=x<=30 and x!=20))"; statement="Выведи 1, если X лежит на [10;30], но не равен 20."; fn=lambda x:int(10<=x<=30 and x!=20)
        elif mode==2:
            source="x=int(input())\nprint(int((x%2==0)!=(x%3==0)))"; statement="Выведи 1, если ровно одно: X чётен или делится на 3."; fn=lambda x:int((x%2==0)!=(x%3==0))
        elif mode==3:
            source="a,b=map(int,input().split())\nprint(int(a>0 or b>0))"; statement="Выведи 1, если хотя бы одно из A и B положительно."; fn=lambda x:int(x[0]>0 or x[1]>0)
        else:
            source="x=int(input())\nprint(int(abs(x)%10 in (2,7)))"; statement="Выведи 1, если последняя цифра модуля X равна 2 или 7."; fn=lambda x:int(abs(x)%10 in (2,7))
        cases = [(str(x),fn(x)) for x in [-21,-10,-1,0,1,2,6,20,27,31]] if mode != 3 else [(f"{a} {b}",fn((a,b))) for a,b in [(-1,-2),(0,3),(4,-1),(2,5),(0,0)]]
        append(generated,ids,task(problem_id=f"author-ege5-{i+1:02d}",title=f"ЕГЭ 5 · логическое условие {i+1}",topic=topic,index=i,tags=["author_ege5","boolean_condition","single_int_out"],statement=statement,input_format="Одно число X или два числа A B — как указано в условии.",output_format="1 или 0.",cases=cases,source=source,fast_path="Сведи формулировку к одному булеву выражению и проверь отдельно границу и противоположный случай.",mistake_map=mistakes(("«И/или/ровно одно» перепутаны","and — оба, or — хотя бы одно, != — ровно одно.","condition"),("Знак/модуль потерян","Подставь отрицательное число и ноль.","boundary"),("True вместо 1","Напечатай int(условие).","output"))))


def gen_ege8(generated: list, ids: set[str], count: int) -> None:
    topic="ЕГЭ 8"
    specs=[("повторы", "sum('A' in ''.join(p) for p in product('ABC', repeat=4))", "sum('A' in ''.join(p) for p in product('ABC', repeat=4))", "Из букв A,B,C составляют слова длины 4 с повторами. Посчитай слова, содержащие A."), ("без повтора", "sum(all(p[j]!=p[j+1] for j in range(3)) for p in product('ABCD', repeat=4))", "sum(all(p[j]!=p[j+1] for j in range(3)) for p in product('ABCD', repeat=4))", "Из букв A,B,C,D составляют слова длины 4 с повторами. Посчитай слова без одинаковых соседей."), ("первая буква", "sum(p[0]=='B' for p in product('ABC', repeat=5))", "sum(p[0]=='B' for p in product('ABC', repeat=5))", "Из букв A,B,C составляют слова длины 5 с повторами. Посчитай слова, начинающиеся с B."), ("ровно две A", "sum(p.count('A')==2 for p in product('ABC', repeat=5))", "sum(p.count('A')==2 for p in product('ABC', repeat=5))", "Из букв A,B,C составляют слова длины 5 с повторами. Посчитай слова ровно с двумя A."), ("код по номеру", "words=[''.join(p) for p in product('ABC', repeat=3)];print(words[int(input())-1])", "", "Из A,B,C составляют слова длины 3 с повторами в алфавитном порядке. По номеру выведи слово.")]
    for i in range(count):
        name, expression, _unused, statement = specs[i%len(specs)]
        if name=="код по номеру":
            source="from itertools import product\nwords=[''.join(p) for p in product('ABC', repeat=3)]\nprint(words[int(input())-1])"
            cases=[(str(n), ''.join(p)) for n,p in enumerate(__import__('itertools').product('ABC',repeat=3),1)]
        else:
            source=f"from itertools import product\nprint({expression})"
            value=eval(expression,{"product":__import__('itertools').product})
            cases=[("",value)]*2 + [("\n",value)]*3
        append(generated,ids,task(problem_id=f"author-ege8-{i+1:02d}",title=f"ЕГЭ 8 · комбинаторика {i+1}",topic=topic,index=i,tags=["author_ege8","combinatorics","single_token_out" if name=="код по номеру" else "single_int_out"],statement=statement,input_format="Номер слова, если он указан; иначе ввода нет.",output_format="Ответ по условию.",cases=cases,source=source,fast_path="Сначала реши, разрешены ли повторы и какова длина слова; генерация product сразу перебирает ровно нужное пространство.",mistake_map=mistakes(("product заменён на permutations","Если буквы можно повторять, используй product, а не permutations.","always"),("Нумерация сдвинута","Слова нумеруются с 1, поэтому индекс — N-1.","boundary"),("Условие проверяется после неполного слова","Собери слово целиком и затем проверь длину/соседей.","always"))))


def gen_ege9(generated: list, ids: set[str], count: int) -> None:
    topic="ЕГЭ 9"
    for i in range(count):
        mode=i%4; rows=[[1,2,3,4],[2,2,4,4],[1,3,5,7],[4,4,4,1],[0,1,2,3]]
        if mode==0:
            source="n=int(input())\nans=0\nfor _ in range(n):\n    a=list(map(int,input().split()))\n    if len(set(a))==len(a): ans+=1\nprint(ans)"; statement="В каждой строке таблицы из 4 чисел посчитай строки без повторов."; fn=lambda r:len(set(r))==len(r)
        elif mode==1:
            source="n=int(input())\nans=0\nfor _ in range(n):\n    a=list(map(int,input().split()))\n    if sum(a)%2==0: ans+=1\nprint(ans)"; statement="Посчитай строки из 4 чисел с чётной суммой."; fn=lambda r:sum(r)%2==0
        elif mode==2:
            source="n=int(input())\nans=0\nfor _ in range(n):\n    a=list(map(int,input().split()))\n    if max(a)==sum(a)-max(a): ans+=1\nprint(ans)"; statement="Посчитай строки, где максимум равен сумме остальных трёх чисел."; fn=lambda r:max(r)==sum(r)-max(r)
        else:
            source="n=int(input())\nans=0\nfor _ in range(n):\n    a=list(map(int,input().split()))\n    if a[0]<a[1]<a[2]<a[3]: ans+=1\nprint(ans)"; statement="Посчитай строки с четырьмя числами, идущими строго по возрастанию."; fn=lambda r:r[0]<r[1]<r[2]<r[3]
        cases=[]
        for shift in range(5):
            rr=[[x+shift for x in row] for row in rows]
            cases.append((str(len(rr))+"\n"+"\n".join(" ".join(map(str,r)) for r in rr),sum(fn(r) for r in rr)))
        append(generated,ids,task(problem_id=f"author-ege9-{i+1:02d}",title=f"ЕГЭ 9 · таблица {i+1}",topic=topic,index=i,tags=["author_ege9","table_input","single_int_out"],statement=statement,input_format="N, затем N строк по 4 целых числа.",output_format="Одно число — количество подходящих строк.",cases=cases,source=source,fast_path="Обрабатывай одну строку за раз и сразу обновляй счётчик; не смешивай столбцы разных строк.",mistake_map=mistakes(("Разделитель/число столбцов неверны","Разбери ровно одну строку и проверь, что в ней 4 числа.","input"),("Условие строки собрано неверно","Проверь строку, где выполнено только одно из требований.","condition"),("Все строки не прочитаны","Внешний цикл должен сделать N проходов.","loop"))))


def gen_ege13(generated: list, ids: set[str], count: int) -> None:
    topic="ЕГЭ 13"
    for i in range(count):
        mode=i%4; p=8+i%8
        if mode==0:
            source="a,b,c,d,p=map(int,input().split())\nmask=(2**32-1) ^ (2**(32-p)-1)\nnet=((a<<24)|(b<<16)|(c<<8)|d)&mask\nprint((net>>24)&255,(net>>16)&255,(net>>8)&255,net&255)"; statement="Даны IPv4-адрес и длина префикса. Выведи четыре октета адреса сети."; fn=lambda v: " ".join(map(str,[( ((v[0]<<24)|(v[1]<<16)|(v[2]<<8)|v[3]) & (((1<<32)-1)^((1<<(32-v[4]))-1)) )>>s &255 for s in (24,16,8,0)]))
        elif mode==1:
            source="a,b,c,d,p=map(int,input().split())\nprint(2**(32-p)-2)"; statement="Даны IPv4-адрес и длина префикса. Выведи число адресов узлов без адресов сети и broadcast."; fn=lambda v:2**(32-v[4])-2
        elif mode==2:
            source="a,b,c,d,p=map(int,input().split())\nprint(p)"; statement="Даны IPv4-адрес и длина префикса. Выведи число единиц в маске сети."; fn=lambda v:v[4]
        else:
            source="a,b,c,d,p=map(int,input().split())\nprint((d+1)%256)"; statement="Даны IPv4-адрес и префикс. Выведи следующий номер последнего октета (по модулю 256)."; fn=lambda v:(v[3]+1)%256
        vals=[[192,168,1,7,p],[10,0,0,1,max(1,p-2)],[172,16,4,99,min(30,p+3)],[8,8,8,8,16],[100,64,12,200,24]]
        cases=[(" ".join(map(str,v)),fn(v)) for v in vals]
        append(generated,ids,task(problem_id=f"author-ege13-{i+1:02d}",title=f"ЕГЭ 13 · IP и маски {i+1}",topic=topic,index=i,tags=["author_ege13","ip","single_int_out"],statement=statement,input_format="Пять чисел: четыре октета IP и длина префикса.",output_format="Ответ по условию.",cases=cases,source=source,fast_path="Представь IP одним 32-битным числом и применяй маску битовой операцией; это быстрее ручного перебора адресов.",mistake_map=mistakes(("Октеты сдвинуты","Сверь порядок 24,16,8,0 бит и не перепутай адрес узла с адресом сети.","always"),("Префикс превращён в число адресов неверно","В сети /p остаётся 32-p бит адресации.","boundary"),("Формат октетов неверен","Печатай ровно четыре величины в указанном порядке.","output"))))


def gen_ege14(generated: list, ids: set[str], count: int) -> None:
    topic="ЕГЭ 14"
    for i in range(count):
        base=2+i%8; mode=i%4
        if mode==0:
            source="n,b=map(int,input().split())\ns=0\nwhile n:\n    s+=n%b\n    n//=b\nprint(s)"; statement="Даны N и основание B. Выведи сумму цифр записи N в системе B."; fn=lambda v: (lambda n,b: (sum_digits_base(n,b)))(*v)
        elif mode==1:
            source="n,b=map(int,input().split())\nc=0\nwhile n:\n    c+=n%b==0\n    n//=b\nprint(c)"; statement="Даны N и B. Посчитай нулевые цифры в записи N по основанию B."; fn=lambda v: sum_digits_base_count(v[0],v[1],0)
        elif mode==2:
            source="n,b=map(int,input().split())\nans=[]\nwhile n:\n    ans.append(str(n%b))\n    n//=b\nprint(''.join(ans[::-1]) or '0')"; statement="Даны N и B (B<=10). Выведи запись N в системе B."; fn=lambda v: base_repr(v[0],v[1])
        else:
            source="n,b=map(int,input().split())\nans=[]\nwhile n:\n    ans.append(n%b)\n    n//=b\nprint(ans[-1] if ans else 0)"; statement="Даны N и B. Выведи первую (старшую) цифру записи N в системе B."; fn=lambda v: int(base_repr(v[0],v[1])[0])
        vals=[[13,base],[25,max(2,base-1)],[64,min(10,base+1)],[100,5],[7,2]]
        cases=[(" ".join(map(str,v)),fn(v)) for v in vals]
        append(generated,ids,task(problem_id=f"author-ege14-{i+1:02d}",title=f"ЕГЭ 14 · системы счисления {i+1}",topic=topic,index=i,tags=["author_ege14","bases","single_int_out"],statement=statement,input_format="N и основание B через пробел.",output_format="Ответ по условию.",cases=cases,source=source,fast_path="Используй повторяющиеся операции n % B и n // B; не переводи число перебором всех возможных записей.",mistake_map=mistakes(("Остатки собраны в обратном порядке","Цифры появляются от младшей к старшей — в конце разверни список.","always"),("Основание перепутано","И деление, и остаток должны использовать B, не фиксированную 2/10.","input"),("Ноль обработан отдельно неверно","Для N=0 запись состоит из одной цифры 0.","boundary"))))


def sum_digits_base(n: int, b: int) -> int:
    if n == 0:
        return 0
    result = 0
    while n:
        result += n % b
        n //= b
    return result


def sum_digits_base_count(n: int, b: int, digit: int) -> int:
    if n == 0:
        return int(digit == 0)
    result = 0
    while n:
        result += int(n % b == digit)
        n //= b
    return result


def base_repr(n: int, b: int) -> str:
    if n == 0:
        return "0"
    out = []
    while n:
        out.append(str(n % b))
        n //= b
    return "".join(reversed(out))


def gen_ege15(generated: list, ids: set[str], count: int) -> None:
    topic="ЕГЭ 15"
    source="p1,p2,q1,q2=map(int,input().split())\nbest=0\nfor a in range(-20,41):\n    for b in range(a,41):\n        ok=True\n        for x in range(-20,41):\n            A=a<=x<=b; P=p1<=x<=p2; Q=q1<=x<=q2\n            if not ((not A or P) or Q): ok=False\n        if ok: best=max(best,b-a)\nprint(best)"
    def solve(v):
        p1,p2,q1,q2=v; best=0
        for a in range(-20,41):
            for b in range(a,41):
                if all(((not (a<=x<=b)) or (p1<=x<=p2) or (q1<=x<=q2)) for x in range(-20,41)):
                    best=max(best,b-a)
        return best
    for i in range(count):
        vals=[[0,5,3,10],[-5,2,0,8],[4,12,-3,6],[-10,-2,-5,15],[8,18,10,20]]
        cases=[(" ".join(map(str,v)),solve(v)) for v in vals]
        append(generated,ids,task(problem_id=f"author-ege15-{i+1:02d}",title=f"ЕГЭ 15 · отрезок A {i+1}",topic=topic,index=i,tags=["author_ege15","logic_intervals","single_int_out"],statement="Даны отрезки P=[p1;p2] и Q=[q1;q2]. Найди максимальную длину отрезка A, при которой (A → P) ∨ Q истинна для всех целых x от -20 до 40.",input_format="Четыре целых числа p1 p2 q1 q2.",output_format="Одно целое число — максимальная длина A.",cases=cases,source=source,fast_path="Сначала определи множество точек, где Q ложно и значит A обязана лежать в P; это заменяет тройной перебор анализом границ.",mistake_map=mistakes(("Импликация направлена наоборот","A → P равна (not A) or P; ложь возникает только при A и not P.","condition"),("Длина перепутана с числом точек","Для [a;b] длина — b-a, а не b-a+1.","boundary"),("Проверены только примеры","Нужно контролировать все важные границы объединения P,Q.","always"))))


def gen_ege16(generated: list, ids: set[str], count: int) -> None:
    topic="ЕГЭ 16"
    recs=[("F(0)=0, F(1)=1, F(n)=F(n-1)+F(n-2)","return 0 if n==0 else 1 if n==1 else f(n-1)+f(n-2)",lambda n: fib(n)),("F(0)=0, F(n)=2F(n-1)+1", "return 0 if n==0 else 2*f(n-1)+1",lambda n:2**n-1),("F(0)=2, F(n)=F(n-1)+n", "return 2 if n==0 else f(n-1)+n",lambda n:2+n*(n+1)//2)]
    for i in range(count):
        statement,body,fn=recs[i%len(recs)]
        if i%len(recs)==0: source=f"from functools import lru_cache\n@lru_cache(None)\ndef f(n):\n    {body}\nn=int(input())\nprint(f(n))"
        elif i%len(recs)==1: source=f"from functools import lru_cache\n@lru_cache(None)\ndef f(n):\n    {body}\nn=int(input())\nprint(f(n))"
        else: source=f"from functools import lru_cache\n@lru_cache(None)\ndef f(n):\n    {body}\nn=int(input())\nprint(f(n))"
        vals=[0,1,2,5,10]; cases=[(str(n),fn(n)) for n in vals]
        append(generated,ids,task(problem_id=f"author-ege16-{i+1:02d}",title=f"ЕГЭ 16 · рекурсия {i+1}",topic=topic,index=i,tags=["author_ege16","recursion","single_int_out"],statement=f"{statement}. По N выведи F(N).",input_format="Одно целое N.",output_format="Одно число.",cases=cases,source=source,fast_path="Кэшируй одинаковые состояния через lru_cache или считай снизу вверх; без этого ветвящаяся рекурсия повторяет работу.",mistake_map=mistakes(("Базовый случай сдвинут","Проверь F(0), F(1) и F(2) отдельно до рекурсии.","boundary"),("Ветка формулы переписана неверно","Сравни каждый индекс и коэффициент с условием.","algorithm"),("Нет кэша","Одинаковый F(k) не должен вычисляться заново.","complexity"))))


def fib(n: int) -> int:
    a,b=0,1
    for _ in range(n): a,b=b,a+b
    return b


def gen_ege17(generated: list, ids: set[str], count: int) -> None:
    topic="ЕГЭ 17"
    for i in range(count):
        mod=3+i; source=f"a=list(map(int,input().split()))\nk=0\nmx=-10**9\nfor j in range(len(a)-1):\n    if (a[j]+a[j+1])%{mod}==0:\n        k+=1;mx=max(mx,a[j]+a[j+1])\nprint(k,mx if k else 0)"
        def solve(s,mod=mod):
            a=list(map(int,s.split())); vals=[a[j]+a[j+1] for j in range(len(a)-1) if (a[j]+a[j+1])%mod==0]; return f"{len(vals)} {max(vals) if vals else 0}"
        cases=[(s,solve(s)) for s in ["1 2 3 4 5","-2 5 7 1","3 3 3 3","0 0 0 0","10 1 8 4"]]
        append(generated,ids,task(problem_id=f"author-ege17-{i+1:02d}",title=f"ЕГЭ 17 · соседние пары {i+1}",topic=topic,index=i,tags=["author_ege17","pairs","two_int_out"],statement=f"Дан список. Для соседних пар посчитай пары, сумма которых делится на {mod}, и их максимальную сумму.",input_format="Одна строка целых чисел.",output_format="Количество и максимум через пробел; при отсутствии пар 0 0.",cases=cases,source=source,fast_path="Один проход по соседним элементам даёт O(n); не используй combinations для пар, которые должны быть соседними.",mistake_map=mistakes(("Взяты все сочетания вместо соседей","Пара — a[j] и a[j+1], цикл range(len(a)-1).","algorithm"),("Счётчик смешан с максимумом","Считай все подходящие пары, а максимум обновляй только внутри того же if.","always"),("Потерян случай без пар","Инициализируй ответ и явно выведи 0 0.","boundary"))))


def gen_ege18(generated: list, ids: set[str], count: int) -> None:
    topic="ЕГЭ 18"
    source="n=int(input())\na=[list(map(int,input().split())) for _ in range(n)]\nlo=[[10**9]*n for _ in range(n)]\nhi=[[-10**9]*n for _ in range(n)]\nlo[0][0]=hi[0][0]=2*a[0][0]\nfor i in range(n):\n    for j in range(n):\n        if i==0 and j==0: continue\n        vals=[]\n        if i: vals.append((lo[i-1][j],hi[i-1][j],a[i][j]))\n        if j: vals.append((lo[i][j-1],hi[i][j-1],a[i][j]))\n        if i and j: vals.append((lo[i-1][j-1],hi[i-1][j-1],2*a[i][j]))\n        lo[i][j]=min(x[0]+x[2] for x in vals);hi[i][j]=max(x[1]+x[2] for x in vals)\nhi[-1][-1]+=a[-1][-1];lo[-1][-1]+=a[-1][-1]\nprint(hi[-1][-1],lo[-1][-1])"
    def solve(grid):
        n=len(grid); lo=[[10**9]*n for _ in range(n)]; hi=[[-10**9]*n for _ in range(n)]; lo[0][0]=hi[0][0]=2*grid[0][0]
        for i in range(n):
            for j in range(n):
                if i==0 and j==0: continue
                vals=[]
                if i: vals.append((lo[i-1][j],hi[i-1][j],grid[i][j]))
                if j: vals.append((lo[i][j-1],hi[i][j-1],grid[i][j]))
                if i and j: vals.append((lo[i-1][j-1],hi[i-1][j-1],2*grid[i][j]))
                lo[i][j]=min(a+b for a,b,c in vals for b in [c] if False) if False else min(x[0]+x[2] for x in vals); hi[i][j]=max(x[1]+x[2] for x in vals)
        return f"{hi[-1][-1]+grid[-1][-1]} {lo[-1][-1]+grid[-1][-1]}"
    for i in range(count):
        cases=[]
        for n in [2,3,4,2,3]:
            grid=[[((r+1)*(c+2)+i)%9+1 for c in range(n)] for r in range(n)]
            cases.append((str(n)+"\n"+"\n".join(" ".join(map(str,row)) for row in grid),solve(grid)))
        append(generated,ids,task(problem_id=f"author-ege18-{i+1:02d}",title=f"ЕГЭ 18 · таблица и диагональ {i+1}",topic=topic,index=i,tags=["author_ege18","dynamic_programming","two_int_out"],statement="Робот идёт из левой верхней клетки в правую нижнюю вправо, вниз или по диагонали. Стартовая клетка удваивается; диагональный вход удваивает значение клетки. Найди максимум и минимум суммы.",input_format="N, затем квадратная таблица N×N.",output_format="Максимум и минимум через пробел.",cases=cases,source=source,fast_path="Динамика по клеткам хранит min и max и использует только три предшественника; это O(N²) вместо перебора всех маршрутов.",mistake_map=mistakes(("Старт/финиш начислены неверно","Отдельно проверь удвоение старта, диагонали и последней клетки.","boundary"),("Пропущен диагональный переход","У клетки может быть три предшественника, не два.","algorithm"),("Ищется только максимум","Веди две независимые таблицы min и max.","always"))))


def gen_games(generated: list, ids: set[str], count: int) -> None:
    topic="ЕГЭ 19–21"
    source="from functools import lru_cache\n@lru_cache(None)\ndef win(x,t):\n    if x>=t:return False\n    return any(not win(y,t) for y in (x+1,x+2,x*2) if y<t)\nt,s=map(int,input().split())\nans=[q for q in range(1,t) if win(s+q,t)]\nprint(min(ans) if ans else 0)"
    def solve(v):
        t,s=v
        from functools import lru_cache
        @lru_cache(None)
        def win(x):
            if x>=t:return False
            return any(not win(y) for y in (x+1,x+2,x*2) if y<t)
        vals=[q for q in range(1,t) if win(s+q)]
        return min(vals) if vals else 0
    for i in range(count):
        vals=[[15,2],[20,3],[25,4],[30,5],[18,1]]
        cases=[(" ".join(map(str,v)),solve(v)) for v in vals]
        append(generated,ids,task(problem_id=f"author-games-{i+1:02d}",title=f"ЕГЭ 19–21 · игра {i+1}",topic=topic,index=i,tags=["author_games","games","single_int_out"],statement="В игре на одной куче можно за ход прибавить 1, прибавить 2 или умножить на 2. При достижении T игра заканчивается. Даны T и S. Найди минимальное q от 1 до T-1, для которого позиция S+q выигрышная для игрока, который ходит.",input_format="T и S через пробел.",output_format="Минимальное q или 0.",cases=cases,source=source,fast_path="Опиши позицию игры и закэшируй win(x); повторное вычисление одного состояния — главный источник медленной работы.",mistake_map=mistakes(("Терминал обработан как обычный ход","Позиция x>=T уже закончилась и не должна порождать новый ход.","boundary"),("any/all перепутаны","Существование выигрышного хода — any, гарантия против любого ответа — all.","condition"),("Состояния пересчитываются","@lru_cache превращает дерево в граф состояний.","complexity"))))


def gen_ege23(generated: list, ids: set[str], count: int) -> None:
    topic="ЕГЭ 23"
    source="from functools import lru_cache\n@lru_cache(None)\ndef f(x,n):\n    if x>n:return 0\n    if x==n:return 1\n    return f(x+1,n)+f(x*2,n)\nn=int(input())\nprint(f(1,n))"
    def solve(n):
        @__import__('functools').lru_cache(None)
        def f(x):
            if x>n:return 0
            if x==n:return 1
            return f(x+1)+f(x*2)
        return f(1)
    for i in range(count):
        cases=[(str(n),solve(n)) for n in [1,2,4,8,12]]
        append(generated,ids,task(problem_id=f"author-ege23-{i+1:02d}",title=f"ЕГЭ 23 · исполнитель {i+1}",topic=topic,index=i,tags=["author_ege23","dp","single_int_out"],statement="Исполнитель начинает с 1 и может прибавить 1 или умножить число на 2. По N посчитай число программ, получающих ровно N.",input_format="Одно N.",output_format="Одно число — количество программ.",cases=cases,source=source,fast_path="Кэшируй количество путей от состояния к цели; одинаковые x не должны пересчитываться.",mistake_map=mistakes(("Пропущена команда","В переходах должны быть и +1, и *2.","algorithm"),("Финиш/перелёт перепутаны","x==N даёт 1, x>N — 0.","boundary"),("Нет динамики","@lru_cache или таблица dp снижает повторные вызовы.","complexity"))))


def gen_ege24(generated: list, ids: set[str], count: int) -> None:
    topic="ЕГЭ 24"
    for i in range(count):
        mode=i%4
        if mode==0:
            source="s=input().strip()\ncur=best=0\nfor ch in s:\n    cur=cur+1 if ch=='A' else 0\n    best=max(best,cur)\nprint(best)"; statement="Дана строка. Найди максимальную длину непрерывной цепочки A."; fn=lambda s:max(map(len,s.split("B"))) if s else 0
            vals=["AAABBA","BBBB","A","BAAAAB","ABABA"]
        elif mode==1:
            source="s=input().strip()\ncur=best=0\nfor i,ch in enumerate(s):\n    cur=cur+1 if ch=='A' else 0\n    best=max(best,cur)\nprint(best)"; statement="Дана строка. Найди максимальную длину цепочки A тем же проходом."; fn=lambda s:max(map(len,s.split("B"))) if s else 0; vals=["A","AB","AAAA","BABA","AAAAB"]
        elif mode==2:
            source="s=input().strip()\nif not s:\n    print(0)\nelse:\n    cur=best=1\n    for i in range(1,len(s)):\n        cur=cur+1 if s[i]!=s[i-1] else 1\n        best=max(best,cur)\n    print(best)"; statement="Дана строка. Найди длину самой длинной подстроки без одинаковых соседей."; fn=lambda s: no_double(s); vals=["ABABA","AABBA","AAAA","ABBA","B"]
        else:
            source="s=input().strip();p='BAFE';cur=best=0\nfor ch in s:\n    cur=cur+1 if ch==p[cur%4] else (1 if ch=='B' else 0)\n    best=max(best,cur)\nprint(best)"; statement="Дана строка. Найди длину максимального фрагмента, повторяющего BAFE по кругу."; fn=lambda s: max_pattern(s,"BAFE"); vals=["BAFEBAFE","BBAFE","BAFF","EBAFE"]
        cases=[(s,fn(s)) for s in vals]
        append(generated,ids,task(problem_id=f"author-ege24-{i+1:02d}",title=f"ЕГЭ 24 · строка {i+1}",topic=topic,index=i,tags=["author_ege24","strings_file_practice","single_int_out"],statement=statement,input_format="Одна строка текста.",output_format="Одно число — длина фрагмента.",cases=cases,source=source,fast_path="Один проход с текущей длиной и максимумом работает за O(n); не создавай все подстроки.",mistake_map=mistakes(("Цепочка прерывается не в тот момент","При неподходящем символе сбрось текущую длину и проверь следующий старт.","algorithm"),("Перепутана непрерывность","Нужен один непрерывный фрагмент, а не общее количество букв.","always"),("Потерян односимвольный случай","Проверь строку длины 1 и строку без подходящих фрагментов.","boundary"))))


def max_pattern(s: str, pattern: str) -> int:
    cur=best=0
    for ch in s:
        cur=cur+1 if ch==pattern[cur%len(pattern)] else (1 if ch==pattern[0] else 0)
        best=max(best,cur)
    return best


def no_double(s: str) -> int:
    if not s:
        return 0
    cur = best = 1
    for i in range(1, len(s)):
        cur = cur + 1 if s[i] != s[i - 1] else 1
        best = max(best, cur)
    return best


def gen_ege25(generated: list, ids: set[str], count: int) -> None:
    topic="ЕГЭ 25"
    for i in range(count):
        source="a,b=map(int,input().split())\nans=[]\nfor x in range(a,b+1):\n    c=sum(x%d==0 for d in range(1,x+1))\n    if c==4: ans.append(x)\nprint(len(ans),max(ans) if ans else 0)"
        def solve(v):
            a,b=v; ans=[x for x in range(a,b+1) if sum(x%d==0 for d in range(1,x+1))==4]; return f"{len(ans)} {max(ans) if ans else 0}"
        cases=[("2 20",solve([2,20])),("10 40",solve([10,40])),("50 80",solve([50,80])),("1 10",solve([1,10])),("90 120",solve([90,120]))]
        append(generated,ids,task(problem_id=f"author-ege25-{i+1:02d}",title=f"ЕГЭ 25 · делители {i+1}",topic=topic,index=i,tags=["author_ege25","divisors","two_int_out"],statement="На отрезке [A;B] найди количество чисел с ровно четырьмя делителями и максимальное из них.",input_format="A и B через пробел.",output_format="Количество и максимум через пробел; если чисел нет — 0 0.",cases=cases,source=source,fast_path="Проверяй делители только до sqrt(x), добавляя парный делитель; это быстрее полного перебора 1..x.",mistake_map=mistakes(("Не учтены 1 и само число","Пара делителей d и x//d должна считаться целиком.","algorithm"),("Правый конец отрезка пропущен","Используй range(A,B+1).","boundary"),("Перебор слишком медленный","Для каждого x достаточно идти до sqrt(x).","complexity"))))


def gen_ege26(generated: list, ids: set[str], count: int) -> None:
    topic="ЕГЭ 26"
    source="n=int(input())\nrows={}\nfor _ in range(n):\n    r,p=map(int,input().split())\n    if p%2: rows.setdefault(r,set()).add(p)\nbest=max((len(v),-k) for k,v in rows.items())\nprint(best[0],-best[1])"
    def solve(data):
        rows={}
        for r,p in data:
            if p%2: rows.setdefault(r,set()).add(p)
        k=max(rows,key=lambda r:(len(rows[r]),-r)); return f"{len(rows[k])} {k}"
    for i in range(count):
        datasets=[[(1,1),(1,1),(1,3),(2,2),(2,5),(2,5),(3,7)],[(1,2),(1,4),(2,1),(2,3),(2,3),(3,9)],[(4,1),(4,5),(5,7),(5,9),(5,9),(6,2)]]
        cases=[]
        for data in datasets:
            cases.append((str(len(data))+"\n"+"\n".join(f"{r} {p}" for r,p in data),solve(data)))
        append(generated,ids,task(problem_id=f"author-ege26-{i+1:02d}",title=f"ЕГЭ 26 · позиции {i+1}",topic=topic,index=i,tags=["author_ege26","sets","two_int_out"],statement="В журнале указаны номер строки и позиция попадания. Посчитай различные нечётные позиции в каждой строке и выведи максимум и номер первой строки с максимумом.",input_format="N, затем N пар row position.",output_format="Два числа: максимум и номер строки.",cases=cases,source=source,fast_path="Словарь строк с set позиций даёт один проход и автоматически убирает повторы; при равенстве выбирай меньший номер.",mistake_map=mistakes(("Повторы посчитаны дважды","Одинаковая позиция добавляется в set только один раз.","set"),("Чётные позиции включены","Фильтруй именно position % 2 == 1, а не номер строки.","condition"),("Взята последняя строка при равенстве","Сравнивай пару (количество, -номер) или обновляй только при строгом улучшении.","boundary"))))


def gen_ege27(generated: list, ids: set[str], count: int) -> None:
    topic="ЕГЭ 27"
    source="from math import hypot\nn=int(input())\ne=float(input())\np=[tuple(map(float,input().split())) for _ in range(n)]\nleft=set(range(n));cs=[]\nwhile left:\n    seed=left.pop();q=[seed];c=[seed]\n    for i in q:\n        for j in list(left):\n            if hypot(p[i][0]-p[j][0],p[i][1]-p[j][1])<e:\n                left.remove(j);q.append(j);c.append(j)\n    if len(c)>=3: cs.append(c)\ncenters=[]\nfor c in cs:\n    centers.append(min(c,key=lambda i:sum(hypot(p[i][0]-p[j][0],p[i][1]-p[j][1]) for j in c)))\nprint(int(sum(p[i][0] for i in centers)/len(centers)*10000),int(sum(p[i][1] for i in centers)/len(centers)*10000))"
    def solve(data):
        e,points=data; left=set(range(len(points))); comps=[]
        while left:
            seed=left.pop(); q=[seed]; c=[seed]
            for x in q:
                for y in list(left):
                    if math.hypot(points[x][0]-points[y][0],points[x][1]-points[y][1])<e:
                        left.remove(y);q.append(y);c.append(y)
            if len(c)>=3: comps.append(c)
        centers=[min(c,key=lambda x:sum(math.hypot(points[x][0]-points[y][0],points[x][1]-points[y][1]) for y in c)) for c in comps]
        return f"{int(sum(points[x][0] for x in centers)/len(centers)*10000)} {int(sum(points[x][1] for x in centers)/len(centers)*10000)}"
    for i in range(count):
        datasets=[]
        for shift in range(5):
            pts=[(0+shift*0.01,0),(0.1+shift*0.01,0.05),(0.05+shift*0.01,0.1),(2+shift*0.01,2),(2.1+shift*0.01,2.05),(2.05+shift*0.01,2.1),(10+shift,10)]
            datasets.append((0.3,pts))
        cases=[]
        for e,pts in datasets:
            cases.append((str(len(pts))+"\n"+str(e)+"\n"+"\n".join(f"{x} {y}" for x,y in pts),solve((e,pts))))
        append(generated,ids,task(problem_id=f"author-ege27-{i+1:02d}",title=f"ЕГЭ 27 · кластеры {i+1}",topic=topic,index=i,tags=["author_ege27","clusters","coordinates","two_int_out"],statement="Даны точки и порог расстояния. Точки одной компоненты связаны цепочкой расстояний меньше порога; компоненты из менее чем 3 точек — шум. Для каждой оставшейся компоненты найди медоид, затем выведи усечённые средние координаты медоидов, умноженные на 10000.",input_format="N, порог e, затем N пар вещественных координат.",output_format="Два целых числа через пробел.",cases=cases,source=source,fast_path="Сначала выдели компоненты обходом, затем ищи медоид только внутри каждой большой компоненты; не пересчитывай связи между уже разделёнными компонентами.",mistake_map=mistakes(("Компонента заменена ближайшими соседями только от seed","Обход нужно расширять до неподвижности, иначе цепочка распадётся.","algorithm"),("Медоид перепутан со средним","Центр — существующая точка с минимальной суммой расстояний.","always"),("round вместо int","В конце требуется отбросить дробную часть после умножения.","output"))))


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    enrich_existing(catalog)
    ids = {str(item["id"]) for item in catalog}
    counts: dict[str, int] = {}
    for item in catalog:
        counts[item.get("topic", "общее")] = counts.get(item.get("topic", "общее"), 0) + 1
    generated: list[tuple[dict[str, Any], dict[str, str]]] = []
    generators = {
        "ввод-вывод": gen_basic_io,
        "циклы": gen_cycles,
        "условия": gen_conditions,
        "числа": gen_numbers,
        "строки": gen_strings,
        "списки": gen_lists,
        "поиск": gen_search,
        "на пути к ЕГЭ": gen_bridge,
        "ЕГЭ 2": gen_ege2,
        "ЕГЭ 5": gen_ege5,
        "ЕГЭ 8": gen_ege8,
        "ЕГЭ 9": gen_ege9,
        "ЕГЭ 13": gen_ege13,
        "ЕГЭ 14": gen_ege14,
        "ЕГЭ 15": gen_ege15,
        "ЕГЭ 16": gen_ege16,
        "ЕГЭ 17": gen_ege17,
        "ЕГЭ 18": gen_ege18,
        "ЕГЭ 19–21": gen_games,
        "ЕГЭ 23": gen_ege23,
        "ЕГЭ 24": gen_ege24,
        "ЕГЭ 25": gen_ege25,
        "ЕГЭ 26": gen_ege26,
        "ЕГЭ 27": gen_ege27,
    }
    for topic, generator in generators.items():
        generator(generated, ids, max(0, 40 - counts.get(topic, 0)))
    for item, _solution in generated:
        catalog.append(item)
    previous = json.loads(SOLUTIONS.read_text(encoding="utf-8")) if SOLUTIONS.exists() else []
    solution_map = {str(item["id"]): item for item in previous}
    for _item, solution in generated:
        solution_map[solution["id"]] = solution
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SOLUTIONS.write_text(json.dumps(list(solution_map.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"generated {len(generated)} tasks; catalog now {len(catalog)}")


if __name__ == "__main__":
    main()
