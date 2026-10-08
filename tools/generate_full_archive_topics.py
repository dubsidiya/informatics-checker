#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build fair programming tasks for missing EGE numbers from ege2027kp.

The full archive mainly contains static questions.  Printing a known static
answer would be accepted by a programming judge, so these are transparent,
input-based adaptations of the archived methods.  Every generated item says
that it is an author adaptation, links its archive location, has independent
hidden variants and a reference solution outside the public catalog.
"""
from __future__ import annotations

import json
import math
import random
from collections import deque
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "data" / "problems.json"
SOLUTIONS = ROOT / "data" / "archive_solutions.json"
DATA = ROOT / "data"

TOPICS = {
    1: "ЕГЭ 1", 3: "ЕГЭ 3", 4: "ЕГЭ 4", 6: "ЕГЭ 6", 7: "ЕГЭ 7",
    10: "ЕГЭ 10", 11: "ЕГЭ 11", 12: "ЕГЭ 12", 22: "ЕГЭ 22",
}
CONDITION_COUNT = {1: 195, 3: 161, 4: 293, 6: 203, 7: 182, 10: 299, 11: 163, 12: 486, 22: 168}
PROVENANCE = (
    "Авторская автоматизируемая адаптация приёмов из полного локального "
    "архива ege2027kp; это не официальный вариант ЕГЭ."
)


def mistake_hints(*rows: tuple[str, str, str]) -> list[dict[str, str]]:
    return [{"title": title, "detail": detail, "signal": signal} for title, detail, signal in rows]


def archive_ref(number: int, index: int) -> str:
    variant = index % CONDITION_COUNT[number] + 1
    return f"ege2027kp/ege{number}.doc; conditions_regen/{number}/task_{number}_{variant:03d}.txt"


def task(
    *, problem_id: str, number: int, index: int, title: str, tags: list[str],
    statement: str, input_format: str, output_format: str,
    cases: list[tuple[str, Any]], source: str, fast_path: str,
    hints: list[dict[str, str]],
) -> tuple[dict, dict]:
    normalized = [(str(stdin), str(stdout)) for stdin, stdout in cases]
    payload = {
        "id": problem_id,
        "title": title,
        "level": ("старт", "средне", "сложно")[index % 3],
        "topic": TOPICS[number],
        "tags": [f"ege{number}", "archive_adaptation", *tags],
        "statement": statement,
        "input_format": input_format,
        "output_format": output_format,
        "examples": [{"stdin": a, "stdout": b} for a, b in normalized[:2]],
        "tests": [
            {"stdin": a, "stdout": b, "hidden": pos >= 2}
            for pos, (a, b) in enumerate(normalized)
        ],
        "files": [],
        "provenance": PROVENANCE,
        "author_created": True,
        "mistake_hints": hints,
        "fast_path": fast_path,
        "archive_ref": archive_ref(number, index),
    }
    return payload, {"id": problem_id, "source": source.rstrip() + "\n"}


def file_task(
    *, problem_id: str, number: int, index: int, title: str, tags: list[str],
    statement: str, output_format: str, fixtures: list[tuple[str, Any]],
    source: str, fast_path: str, hints: list[dict[str, str]],
) -> tuple[dict, dict]:
    folder = DATA / f"ege{number}"
    folder.mkdir(parents=True, exist_ok=True)
    tests = []
    public_file = ""
    for pos, (content, expected) in enumerate(fixtures):
        suffix = "public" if pos == 0 else f"hidden-{pos}"
        relative = f"ege{number}/{problem_id}-{suffix}.txt"
        (DATA / relative).write_text(content, encoding="utf-8")
        if pos == 0:
            public_file = relative
        tests.append({"stdin": "", "stdout": str(expected), "hidden": pos >= 2, "file": relative})
    payload = {
        "id": problem_id,
        "title": title,
        "level": ("старт", "средне", "сложно")[index % 3],
        "topic": TOPICS[number],
        "tags": [f"ege{number}", "archive_adaptation", "file_input", *tags],
        "statement": statement,
        "input_format": f"Файл `{Path(public_file).name}` уже подключён; в коде он также доступен как `{number}.txt`.",
        "output_format": output_format,
        "examples": [{"stdin": "", "stdout": str(fixtures[0][1])}, {"stdin": "", "stdout": str(fixtures[1][1])}],
        "tests": tests,
        "files": [public_file],
        "provenance": PROVENANCE,
        "author_created": True,
        "mistake_hints": hints,
        "fast_path": fast_path,
        "archive_ref": archive_ref(number, index),
    }
    return payload, {"id": problem_id, "source": source.rstrip() + "\n"}


def add(out: list[tuple[dict, dict]], ids: set[str], value: tuple[dict, dict]) -> None:
    if value[0]["id"] not in ids:
        out.append(value)
        ids.add(value[0]["id"])


# ---------------------------------------------------------------------------
# №1 — graphs and information models

def graph_edges(seed: int, n: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    result = {(i, i + 1) for i in range(1, n)}
    for _ in range(3 + seed % 3):
        a, b = sorted(rng.sample(range(1, n + 1), 2))
        result.add((a, b))
    return sorted(result)


def graph_text(n: int, edges: list[tuple[int, int]], extra: str = "") -> str:
    lines = [f"{n} {len(edges)}", *[f"{a} {b}" for a, b in edges]]
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def graph_adj(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    graph = [[] for _ in range(n + 1)]
    for a, b in edges:
        graph[a].append(b)
        graph[b].append(a)
    return graph


def graph_components(n: int, edges: list[tuple[int, int]]) -> int:
    graph, seen, result = graph_adj(n, edges), set(), 0
    for start in range(1, n + 1):
        if start in seen:
            continue
        result += 1
        seen.add(start)
        queue = [start]
        for vertex in queue:
            for nxt in graph[vertex]:
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
    return result


def graph_distance(n: int, edges: list[tuple[int, int]], start: int, target: int) -> int:
    graph = graph_adj(n, edges)
    distance = [-1] * (n + 1)
    distance[start] = 0
    queue = deque([start])
    while queue:
        vertex = queue.popleft()
        for nxt in graph[vertex]:
            if distance[nxt] == -1:
                distance[nxt] = distance[vertex] + 1
                queue.append(nxt)
    return distance[target]


def build_ege1(ids: set[str]) -> list[tuple[dict, dict]]:
    out: list[tuple[dict, dict]] = []
    families = ["degree", "edges", "components", "maxdegree", "reachable", "distance", "threshold", "triangles"]
    for index in range(40):
        family = families[index % len(families)]
        cases = []
        for seed in range(index, index + 5):
            n = 5 + seed % 3
            edges = graph_edges(100 + seed, n)
            graph = graph_adj(n, edges)
            if family == "degree":
                vertex = seed % n + 1
                cases.append((graph_text(n, edges, str(vertex)), len(graph[vertex])))
            elif family == "edges":
                cases.append((graph_text(n, edges), len(edges)))
            elif family == "components":
                cases.append((graph_text(n, edges), graph_components(n, edges)))
            elif family == "maxdegree":
                cases.append((graph_text(n, edges), max(map(len, graph[1:]))))
            elif family == "reachable":
                cases.append((graph_text(n, edges, f"1 {n}"), "YES" if graph_distance(n, edges, 1, n) >= 0 else "NO"))
            elif family == "distance":
                cases.append((graph_text(n, edges, f"1 {n}"), graph_distance(n, edges, 1, n)))
            elif family == "threshold":
                k = 2 + seed % 3
                cases.append((graph_text(n, edges, str(k)), sum(len(graph[v]) >= k for v in range(1, n + 1))))
            else:
                edge_set = set(edges)
                result = sum(
                    (a, b) in edge_set and (a, c) in edge_set and (b, c) in edge_set
                    for a in range(1, n + 1)
                    for b in range(a + 1, n + 1)
                    for c in range(b + 1, n + 1)
                )
                cases.append((graph_text(n, edges), result))
        if family == "degree":
            statement = "Дан неориентированный граф. Найди степень указанной вершины."
            source = """n,m=map(int,input().split())
g=[[] for _ in range(n+1)]
for _ in range(m):
 a,b=map(int,input().split());g[a].append(b);g[b].append(a)
v=int(input())
print(len(g[v]))"""
            output = "Одно число — степень вершины."
        elif family == "edges":
            statement = "Дан неориентированный граф. Выведи число его рёбер."
            source = """n,m=map(int,input().split())
for _ in range(m): input()
print(m)"""
            output = "Одно целое число."
        elif family == "components":
            statement = "Дан неориентированный граф. Найди число компонент связности."
            source = """n,m=map(int,input().split())
g=[[] for _ in range(n+1)]
for _ in range(m):
 a,b=map(int,input().split());g[a].append(b);g[b].append(a)
seen=set();ans=0
for s in range(1,n+1):
 if s in seen: continue
 ans+=1;seen.add(s);q=[s]
 for v in q:
  for u in g[v]:
   if u not in seen: seen.add(u);q.append(u)
print(ans)"""
            output = "Одно целое число."
        elif family == "maxdegree":
            statement = "Дан неориентированный граф. Найди наибольшую степень вершины."
            source = """n,m=map(int,input().split());d=[0]*(n+1)
for _ in range(m):
 a,b=map(int,input().split());d[a]+=1;d[b]+=1
print(max(d))"""
            output = "Одно целое число."
        elif family == "reachable":
            statement = "Дан неориентированный граф и две вершины. Выведи YES, если путь существует, иначе NO."
            source = """n,m=map(int,input().split());g=[[] for _ in range(n+1)]
for _ in range(m):
 a,b=map(int,input().split());g[a].append(b);g[b].append(a)
s,t=map(int,input().split());seen={s};q=[s]
for v in q:
 for u in g[v]:
  if u not in seen: seen.add(u);q.append(u)
print('YES' if t in seen else 'NO')"""
            output = "YES или NO."
        elif family == "distance":
            statement = "Дан неориентированный граф и две вершины. Найди длину кратчайшего пути по числу рёбер, либо -1."
            source = """from collections import deque
n,m=map(int,input().split());g=[[] for _ in range(n+1)]
for _ in range(m):
 a,b=map(int,input().split());g[a].append(b);g[b].append(a)
s,t=map(int,input().split());d=[-1]*(n+1);d[s]=0;q=deque([s])
while q:
 v=q.popleft()
 for u in g[v]:
  if d[u]<0: d[u]=d[v]+1;q.append(u)
print(d[t])"""
            output = "Одно целое число."
        elif family == "threshold":
            statement = "Дан неориентированный граф и число K. Посчитай вершины степени не меньше K."
            source = """n,m=map(int,input().split());d=[0]*(n+1)
for _ in range(m):
 a,b=map(int,input().split());d[a]+=1;d[b]+=1
k=int(input());print(sum(x>=k for x in d[1:]))"""
            output = "Одно целое число."
        else:
            statement = "Дан неориентированный граф. Посчитай треугольники — тройки попарно соединённых вершин."
            source = """n,m=map(int,input().split());e=set()
for _ in range(m):
 a,b=sorted(map(int,input().split()));e.add((a,b))
ans=0
for a in range(1,n+1):
 for b in range(a+1,n+1):
  for c in range(b+1,n+1): ans+=(a,b) in e and (a,c) in e and (b,c) in e
print(ans)"""
            output = "Одно целое число."
        add(out, ids, task(
            problem_id=f"archive-ege1-{index+1:02d}", number=1, index=index,
            title=f"ЕГЭ 1 · графы {index+1:02d}", tags=["graphs", "single_int_out"],
            statement=statement,
            input_format="N M, затем M неориентированных рёбер; дополнительные данные указаны в условии.",
            output_format=output, cases=cases, source=source,
            fast_path="Быстрее: построй список смежности один раз; BFS/DFS обрабатывает граф за O(N + M).",
            hints=mistake_hints(
                ("Ребро добавлено только в одну сторону", "Граф неориентированный: добавляй обе связи a→b и b→a.", "algorithm"),
                ("Нумерация вершин сдвинута", "Вершины идут с 1, поэтому удобно хранить N+1 ячеек.", "boundary"),
                ("Путь проверен одним шагом", "Достижимость требует обхода всей цепочки рёбер.", "always"),
            ),
        ))
    return out


# ---------------------------------------------------------------------------
# №3 — spreadsheets / database tables

def records(seed: int) -> list[tuple[str, int, str, str]]:
    people = ["Иванов", "Петров", "Сидоров", "Орлов"]
    routes = ["Север", "Юг", "Запад"]
    rng = random.Random(seed)
    return [(rng.choice(people), rng.randrange(400, 5001, 100), rng.choice(["in", "out"]), rng.choice(routes)) for _ in range(18)]


def records_text(rows: list[tuple[str, int, str, str]]) -> str:
    return "\n".join(f"{name};{cargo};{kind};{route}" for name, cargo, kind, route in rows)


def build_ege3(ids: set[str]) -> list[tuple[dict, dict]]:
    out: list[tuple[dict, dict]] = []
    people, routes = ["Иванов", "Петров", "Сидоров", "Орлов"], ["Север", "Юг", "Запад"]
    for index in range(40):
        family, driver, route, threshold = index % 8, people[index % 4], routes[index % 3], 1500 + 200 * (index % 8)
        fixtures: list[tuple[str, Any]] = []
        for seed in range(index, index + 5):
            rows = records(seed + 201)
            if family == 0:
                answer = sum(c for n, c, k, r in rows if n == driver and k == "in")
            elif family == 1:
                answer = abs(sum(c for n, c, k, r in rows if n == driver and k == "in") - sum(c for n, c, k, r in rows if n == driver and k == "out"))
            elif family == 2:
                answer = sum(c > threshold for _, c, _, _ in rows)
            elif family == 3:
                answer = max(c for _, c, k, _ in rows if k == "out")
            elif family == 4:
                answer = len({n for n, c, _, _ in rows if c >= threshold})
            elif family == 5:
                answer = sum(r == route for _, _, _, r in rows)
            elif family == 6:
                answer = sum(c for _, c, _, r in rows if r == route)
            else:
                answer = len({n for n, _, _, r in rows if r == route})
            fixtures.append((records_text(rows), answer))
        header = "rows=[line.strip().split(';') for line in open('3.txt') if line.strip()]\n"
        if family == 0:
            statement = f"В таблице `водитель;груз;тип;маршрут` найди суммарный привезённый груз водителя {driver}. Тип `in` означает привоз."
            source = header + f"print(sum(int(c) for n,c,k,r in rows if n=='{driver}' and k=='in'))"
        elif family == 1:
            statement = f"Найди модуль разности между привезённым и вывезенным грузом водителя {driver}."
            source = header + f"a=sum(int(c) for n,c,k,r in rows if n=='{driver}' and k=='in')\nb=sum(int(c) for n,c,k,r in rows if n=='{driver}' and k=='out')\nprint(abs(a-b))"
        elif family == 2:
            statement = f"Посчитай рейсы с грузом строго больше {threshold} кг."
            source = header + f"print(sum(int(c)>{threshold} for n,c,k,r in rows))"
        elif family == 3:
            statement = "Найди максимальный груз среди вывозов (тип `out`)."
            source = header + "print(max(int(c) for n,c,k,r in rows if k=='out'))"
        elif family == 4:
            statement = f"Посчитай водителей, у которых есть рейс с грузом не меньше {threshold} кг."
            source = header + f"print(len({{n for n,c,k,r in rows if int(c)>={threshold}}}))"
        elif family == 5:
            statement = f"Посчитай число рейсов по маршруту {route}."
            source = header + f"print(sum(r=='{route}' for n,c,k,r in rows))"
        elif family == 6:
            statement = f"Найди суммарный груз всех рейсов по маршруту {route}."
            source = header + f"print(sum(int(c) for n,c,k,r in rows if r=='{route}'))"
        else:
            statement = f"Посчитай различных водителей, работавших на маршруте {route}."
            source = header + f"print(len({{n for n,c,k,r in rows if r=='{route}'}}))"
        add(out, ids, file_task(
            problem_id=f"archive-ege3-{index+1:02d}", number=3, index=index,
            title=f"ЕГЭ 3 · таблица рейсов {index+1:02d}", tags=["database", "tables", "single_int_out"],
            statement=statement, output_format="Одно целое число.", fixtures=fixtures, source=source,
            fast_path="Быстрее: пройди таблицу один раз и обновляй сумму, счётчик или set; не перечитывай файл для каждого значения.",
            hints=mistake_hints(
                ("Разделитель таблицы неверный", "Поля разделены `;`: используй split(';').", "input"),
                ("Строки разных записей смешаны", "Сначала проверь поле водителя, типа или маршрута, затем добавляй груз.", "condition"),
                ("Различные значения посчитаны как строки", "Если просят разных водителей, собирай имена в set.", "set"),
            ),
        ))
    return out


# ---------------------------------------------------------------------------
# №4 — coding and information representation

def build_ege4(ids: set[str]) -> list[tuple[dict, dict]]:
    out: list[tuple[dict, dict]] = []
    alphabet = "ABCD"
    for index in range(40):
        family = index % 8
        if family == 0:
            words = ["ABCD", "DABC", "CBAD", "BBDD", "ACCA"]
            cases = [(w, "".join(format(alphabet.index(ch), "02b") for ch in w)) for w in words]
            statement, output = "Буквы A,B,C,D кодируются 00,01,10,11. Выведи двоичную запись кодированного слова.", "Двоичная строка без пробелов."
            source = """word=input().strip();alphabet='ABCD'
print(''.join(format(alphabet.index(ch),'02b') for ch in word))"""
        elif family == 1:
            words = ["ABCD", "DABC", "CBAD", "BBDD", "ACCA"]
            cases = [(w, format(int("".join(format(alphabet.index(ch), "02b") for ch in w), 2), "X")) for w in words]
            statement, output = "Буквы A,B,C,D кодируются 00,01,10,11. Переведи код слова в шестнадцатеричную запись без `0x`.", "Шестнадцатеричная запись заглавными буквами."
            source = """word=input().strip();alphabet='ABCD'
bits=''.join(format(alphabet.index(ch),'02b') for ch in word)
print(format(int(bits,2),'X'))"""
        elif family == 2:
            bits = ["00011011", "11000110", "101001", "010111", "11110000"]
            cases = [(b, "".join(alphabet[int(b[i:i+2], 2)] for i in range(0, len(b), 2))) for b in bits]
            statement, output = "Каждая буква A,B,C,D закодирована 00,01,10,11. Расшифруй двоичную строку.", "Исходное слово."
            source = """bits=input().strip();alphabet='ABCD'
print(''.join(alphabet[int(bits[i:i+2],2)] for i in range(0,len(bits),2)))"""
        elif family == 3:
            values = [2, 3, 4, 5, 31]
            cases = [(str(n), math.ceil(math.log2(n))) for n in values]
            statement, output = "Дано число различных символов N. Найди минимальное целое число бит для кодирования одного символа.", "Одно целое число."
            source = """import math
n=int(input());print(math.ceil(math.log2(n)))"""
        elif family == 4:
            values = [(2, 4), (3, 3), (4, 5), (5, 2), (10, 3)]
            cases = [(f"{a} {b}", a ** b) for a, b in values]
            statement, output = "Даны размер алфавита A и длина слова L. Посчитай число слов с повторами.", "Одно целое число."
            source = """a,l=map(int,input().split());print(a**l)"""
        elif family == 5:
            values = [(8, 12), (16, 5), (2, 30), (7, 9), (10, 10)]
            cases = [(f"{a} {b}", a * b) for a, b in values]
            statement, output = "Даны число бит на символ B и длина сообщения L. Найди размер сообщения в битах.", "Одно целое число."
            source = """b,l=map(int,input().split());print(b*l)"""
        elif family == 6:
            values = [(2, 5), (5, 7), (8, 13), (3, 9), (1, 1)]
            cases = [(f"{a} {b}", (a * b + 7) // 8) for a, b in values]
            statement, output = "Даны B бит на символ и L символов. Найди минимальный размер сообщения в целых байтах.", "Одно целое число — байты."
            source = """b,l=map(int,input().split());print((b*l+7)//8)"""
        else:
            values = [(4, 2), (5, 1), (6, 3), (8, 4), (10, 2)]
            cases = [(f"{n} {k}", math.comb(n, k)) for n, k in values]
            statement, output = "Даны длина двоичного слова N и число единиц K. Посчитай слова ровно с K единицами.", "Одно целое число."
            source = """import math
n,k=map(int,input().split());print(math.comb(n,k))"""
        add(out, ids, task(
            problem_id=f"archive-ege4-{index+1:02d}", number=4, index=index,
            title=f"ЕГЭ 4 · кодирование {index+1:02d}", tags=["coding", "single_int_out"],
            statement=statement, input_format="Ввод указан в условии.", output_format=output,
            cases=cases, source=source,
            fast_path="Быстрее: работай с индексом символа и фиксированной длиной кода; не перебирай все слова, если есть формула.",
            hints=mistake_hints(
                ("Основание системы перепутано", "Двоичную строку читают через int(bits, 2), а шестнадцатеричный вывод делают format(..., 'X').", "always"),
                ("Ведущие нули потеряны", "Код каждого символа фиксированной длины: format(..., '02b') важен.", "boundary"),
                ("Биты и байты смешаны", "В одном байте 8 бит; для минимального размера нужен потолок деления.", "always"),
            ),
        ))
    return out

# ---------------------------------------------------------------------------
# №6 — Turtle / geometry (integer lattice-friendly variants)

def polygon_area2(points: list[tuple[int, int]]) -> int:
    return abs(sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] for i in range(len(points))))


def points_inside_rect(width: int, height: int) -> int:
    return max(0, width - 1) * max(0, height - 1)


def build_ege6(ids: set[str]) -> list[tuple[dict, dict]]:
    out: list[tuple[dict, dict]] = []
    for index in range(40):
        family = index % 8
        if family == 0:
            values = [(3, 4), (5, 2), (1, 8), (7, 6), (10, 3)]
            cases = [(f"{w} {h}", points_inside_rect(w, h)) for w, h in values]
            statement, output = "Черепаха обходит прямоугольник ширины W и высоты H по границе. Сколько точек с целыми координатами строго внутри?", "Одно целое число."
            source = """w,h=map(int,input().split());print(max(0,w-1)*max(0,h-1))"""
        elif family == 1:
            values = [(3, 4), (5, 2), (1, 8), (7, 6), (10, 3)]
            cases = [(f"{w} {h}", 2 * (w + h)) for w, h in values]
            statement, output = "Черепаха обходит прямоугольник ширины W и высоты H. Найди длину её пути по границе.", "Одно целое число."
            source = """w,h=map(int,input().split());print(2*(w+h))"""
        elif family == 2:
            values = [(3, 4), (5, 2), (1, 8), (7, 6), (10, 3)]
            cases = [(f"{w} {h}", w * h) for w, h in values]
            statement, output = "Черепаха прошла по сторонам прямоугольника ширины W и высоты H. Найди площадь ограниченной области.", "Одно целое число."
            source = """w,h=map(int,input().split());print(w*h)"""
        elif family == 3:
            values = [(3, 4), (5, 2), (1, 8), (7, 6), (10, 3)]
            cases = [(f"{w} {h}", 2 * (w + h) - 4) for w, h in values]
            statement, output = "Черепаха обходит прямоугольник W×H. Сколько целочисленных точек лежит на его границе?", "Одно целое число."
            source = """w,h=map(int,input().split());print(2*(w+h)-4)"""
        elif family == 4:
            values = [(2, 3), (4, 5), (7, 1), (10, 2), (6, 6)]
            cases = [(f"{a} {b}", a * b // 2) for a, b in values]
            statement, output = "Черепаха построила прямоугольный треугольник с катетами A и B. Найди площадь. Все значения подобраны для целого ответа.", "Одно целое число."
            source = """a,b=map(int,input().split());print(a*b//2)"""
        elif family == 5:
            values = [(3, 4), (5, 2), (7, 6), (10, 3), (8, 8)]
            cases = [(f"{w} {h}", (w + 1) * (h + 1)) for w, h in values]
            statement, output = "Включая границу, сколько точек с целыми координатами содержит прямоугольник W×H с вершинами в целых точках?", "Одно целое число."
            source = """w,h=map(int,input().split());print((w+1)*(h+1))"""
        elif family == 6:
            values = [(3, 4, 2), (5, 2, 3), (7, 6, 2), (10, 3, 5), (8, 8, 4)]
            cases = [(f"{w} {h} {step}", math.gcd(w, step) + math.gcd(h, step)) for w, h, step in values]
            statement, output = "Черепаха идёт по двум сторонам прямоугольника шагом S. Найди число точек поворота и касания сетки: НОД(W,S)+НОД(H,S).", "Одно целое число."
            source = """import math
w,h,s=map(int,input().split());print(math.gcd(w,s)+math.gcd(h,s))"""
        else:
            values = [(3, 4), (5, 2), (7, 6), (10, 3), (8, 8)]
            cases = [(f"{w} {h}", abs(w - h)) for w, h in values]
            statement, output = "Черепаха прошла W вправо и H вверх. Найди модуль разности координат конца.", "Одно целое число."
            source = """w,h=map(int,input().split());print(abs(w-h))"""
        add(out, ids, task(
            problem_id=f"archive-ege6-{index+1:02d}", number=6, index=index,
            title=f"ЕГЭ 6 · геометрия Черепахи {index+1:02d}", tags=["turtle", "geometry", "single_int_out"],
            statement=statement,
            input_format="Целые параметры фигуры через пробел.", output_format=output, cases=cases, source=source,
            fast_path="Быстрее: сведи траекторию к геометрическим параметрам фигуры; не нужно симулировать каждую точку пути.",
            hints=mistake_hints(
                ("Граница включена в внутренние точки", "Точки на линии не считаются внутренними: для W×H внутри (W-1)(H-1).", "boundary"),
                ("Площадь и периметр перепутаны", "Площадь — произведение сторон, периметр — сумма сторон по границе.", "always"),
                ("Шаги симулируются зря", "Для прямоугольной фигуры формула быстрее и надёжнее покадровой симуляции.", "complexity"),
            ),
        ))
    return out


# ---------------------------------------------------------------------------
# №7 — information volume and transmission

def build_ege7(ids: set[str]) -> list[tuple[dict, dict]]:
    out: list[tuple[dict, dict]] = []
    for index in range(40):
        family = index % 8
        if family == 0:
            values = [(128, 256, 64), (64, 64, 16), (320, 200, 256), (100, 100, 2), (1920, 1080, 16)]
            cases = [(f"{w} {h} {colors}", (w * h * math.ceil(math.log2(colors)) + 7) // 8) for w, h, colors in values]
            statement, output = "Даны ширина W, высота H и число цветов C. Найди минимальный объём растрового изображения в байтах.", "Одно целое число — байты."
            source = """import math
w,h,c=map(int,input().split());print((w*h*math.ceil(math.log2(c))+7)//8)"""
        elif family == 1:
            values = [(44100, 16, 2, 10), (8000, 8, 1, 60), (48000, 24, 2, 5), (22050, 16, 1, 30), (1000, 10, 3, 7)]
            cases = [(f"{f} {bits} {ch} {sec}", f * bits * ch * sec) for f, bits, ch, sec in values]
            statement, output = "Даны частота дискретизации F, глубина B, каналы C и длительность T. Найди объём несжатого звука в битах.", "Одно целое число — биты."
            source = """f,b,c,t=map(int,input().split());print(f*b*c*t)"""
        elif family == 2:
            values = [(100, 12), (256, 8), (44100, 16), (1000, 24), (50, 1)]
            cases = [(f"{rate} {bits}", rate * bits) for rate, bits in values]
            statement, output = "Даны скорость R символов в секунду и B бит на символ. Найди скорость передачи в бит/с.", "Одно целое число."
            source = """r,b=map(int,input().split());print(r*b)"""
        elif family == 3:
            values = [(1000000, 1000), (500000, 2000), (1234567, 123), (8000, 64), (1, 1)]
            cases = [(f"{size} {speed}", (size + speed - 1) // speed) for size, speed in values]
            statement, output = "Даны объём S бит и скорость V бит/с. Найди минимальное целое число секунд передачи.", "Одно целое число."
            source = """s,v=map(int,input().split());print((s+v-1)//v)"""
        elif family == 4:
            values = [(8, 100), (16, 50), (5, 12), (1, 8), (32, 10)]
            cases = [(f"{bits} {count}", (bits * count + 7) // 8) for bits, count in values]
            statement, output = "Даны B бит на объект и N объектов. Найди минимальный объём в целых байтах.", "Одно целое число."
            source = """b,n=map(int,input().split());print((b*n+7)//8)"""
        elif family == 5:
            values = [(2, 10), (4, 8), (8, 5), (16, 4), (32, 3)]
            cases = [(f"{colors} {pixels}", math.ceil(math.log2(colors)) * pixels) for colors, pixels in values]
            statement, output = "Даны число цветов C и число пикселей P. Найди объём изображения в битах.", "Одно целое число."
            source = """import math
c,p=map(int,input().split());print(math.ceil(math.log2(c))*p)"""
        elif family == 6:
            values = [(1024, 8), (2048, 16), (4096, 32), (1000, 10), (12345, 7)]
            cases = [(f"{size} {ratio}", (size + ratio - 1) // ratio) for size, ratio in values]
            statement, output = "Даны исходный объём S байт и коэффициент сжатия K. Найди минимальный целый объём после сжатия.", "Одно целое число."
            source = """s,k=map(int,input().split());print((s+k-1)//k)"""
        else:
            values = [(256, 16), (1024, 32), (44100, 8), (1000, 10), (128, 1)]
            cases = [(f"{a} {b}", a * b // math.gcd(a, b)) for a, b in values]
            statement, output = "Даны два периодических потока с интервалами A и B мс. Найди через сколько мс их события снова совпадут.", "Одно целое число."
            source = """import math
a,b=map(int,input().split());print(a*b//math.gcd(a,b))"""
        add(out, ids, task(
            problem_id=f"archive-ege7-{index+1:02d}", number=7, index=index,
            title=f"ЕГЭ 7 · объём информации {index+1:02d}", tags=["information_volume", "single_int_out"],
            statement=statement, input_format="Параметры через пробел.", output_format=output, cases=cases, source=source,
            fast_path="Быстрее: выпиши единицы измерения и одну формулу; не симулируй пиксели, символы или секунды по одному.",
            hints=mistake_hints(
                ("Биты и байты смешаны", "В одном байте 8 бит; при минимальном целом размере округляй вверх.", "always"),
                ("Число бит на цвет неверно", "Нужно ceil(log2(C)), а не само число цветов.", "algorithm"),
                ("Округление вниз", "Если требуется минимальное целое число секунд/байтов, используй (a+b-1)//b.", "boundary"),
            ),
        ))
    return out

# ---------------------------------------------------------------------------
# №10 — text search (file variants)

def text_fixture(seed: int) -> str:
    words = ["портрет", "поэт", "роман", "герой", "Портрет", "Поэт", "портреты", "поэты", "слово"]
    rng = random.Random(seed)
    return " ".join(rng.choice(words) for _ in range(80)) + ".\n"


def count_word(text: str, word: str) -> int:
    return sum(token.lower().strip(".,!?;:") == word for token in text.split())


def build_ege10(ids: set[str]) -> list[tuple[dict, dict]]:
    out: list[tuple[dict, dict]] = []
    targets = ["портрет", "поэт", "роман", "герой", "слово"]
    for index in range(40):
        family = index % 8
        target = targets[index % len(targets)]
        fixtures = []
        for seed in range(index, index + 5):
            content = text_fixture(seed + 500)
            if family == 0:
                answer = count_word(content, target)
            elif family == 1:
                answer = sum(token.lower().strip(".,!?;:").startswith(target[:3]) for token in content.split())
            elif family == 2:
                answer = sum(len(token.strip(".,!?;:")) >= 5 for token in content.split())
            elif family == 3:
                answer = len({token.lower().strip(".,!?;:") for token in content.split()})
            elif family == 4:
                answer = max(map(len, [token.strip(".,!?;:") for token in content.split()]))
            elif family == 5:
                answer = sum(token[0].isupper() for token in content.split() if token)
            elif family == 6:
                answer = sum("р" in token.lower() for token in content.split())
            else:
                answer = sum(token.lower().strip(".,!?;:") == target and pos % 2 == 0 for pos, token in enumerate(content.split()))
            fixtures.append((content, answer))
        if family == 0:
            statement = f"В текстовом файле посчитай точные вхождения слова «{target}» без учёта регистра. Формы с окончаниями не подходят."
            source = f"""import re
text=open('10.txt').read().lower()
print(len(re.findall(r'(?<![а-яё]){target}(?![а-яё])',text)))"""
        elif family == 1:
            statement = f"Посчитай слова, начинающиеся с первых трёх букв слова «{target}», без учёта регистра."
            source = f"""import re
text=open('10.txt').read().lower()
print(sum(word.startswith('{target[:3]}') for word in re.findall(r'[а-яё]+',text)))"""
        elif family == 2:
            statement = "Посчитай слова длиной не менее 5 букв. Знаки препинания не являются частью слова."
            source = """import re
text=open('10.txt').read().lower()
print(sum(len(word)>=5 for word in re.findall(r'[а-яё]+',text)))"""
        elif family == 3:
            statement = "Посчитай различные слова без учёта регистра и знаков препинания."
            source = """import re
text=open('10.txt').read().lower()
print(len(set(re.findall(r'[а-яё]+',text))))"""
        elif family == 4:
            statement = "Найди длину самого длинного слова без учёта знаков препинания."
            source = """import re
words=re.findall(r'[а-яё]+',open('10.txt').read().lower())
print(max(map(len,words)))"""
        elif family == 5:
            statement = "Посчитай слова, начинающиеся с заглавной русской буквы."
            source = """import re
text=open('10.txt').read()
print(sum(word[0].isupper() for word in re.findall(r'[А-ЯЁ][а-яё]*',text)))"""
        elif family == 6:
            statement = "Посчитай слова, содержащие букву «р» или «Р»."
            source = """import re
words=re.findall(r'[а-яё]+',open('10.txt').read().lower())
print(sum('р' in word for word in words))"""
        else:
            statement = f"Посчитай точные вхождения слова «{target}» на чётных позициях списка слов (позиции с 0)."
            source = f"""import re
words=re.findall(r'[а-яё]+',open('10.txt').read().lower())
print(sum(word=='{target}' and i%2==0 for i,word in enumerate(words)))"""
        add(out, ids, file_task(
            problem_id=f"archive-ege10-{index+1:02d}", number=10, index=index,
            title=f"ЕГЭ 10 · поиск в тексте {index+1:02d}", tags=["text_file", "regex", "single_int_out"],
            statement=statement, output_format="Одно целое число.", fixtures=fixtures, source=source,
            fast_path="Быстрее: нормализуй текст один раз и пройди список слов; не делай многократный поиск по всему файлу.",
            hints=mistake_hints(
                ("Форма слова принята за точное слово", "Для точного совпадения отдели слово от знаков препинания и окончаний.", "always"),
                ("Регистр не нормализован", "Для поиска без регистра приведи текст и слово к lower().", "always"),
                ("Пунктуация осталась в слове", "Регулярное выражение или strip должны убрать точки и запятые.", "algorithm"),
            ),
        ))
    return out


# ---------------------------------------------------------------------------
# №11 — information coding and passwords

def build_ege11(ids: set[str]) -> list[tuple[dict, dict]]:
    out: list[tuple[dict, dict]] = []
    for index in range(40):
        family = index % 8
        if family == 0:
            values = [(101, 80), (64, 100), (256, 10), (7, 50), (2, 1)]
            cases = [(f"{values_count} {measurements}", math.ceil(math.log2(values_count)) * measurements) for values_count, measurements in values]
            statement, output = "Даны число возможных значений V и число измерений N. Найди информационный объём всех измерений в битах.", "Одно целое число."
            source = """import math
v,n=map(int,input().split());print(math.ceil(math.log2(v))*n)"""
        elif family == 1:
            values = [(6, 100), (8, 25), (16, 10), (3, 80), (2, 7)]
            cases = [(f"{signals} {count}", (math.ceil(math.log2(signals)) * count + 7) // 8) for signals, count in values]
            statement, output = "Даны число видов сигналов S и число сигналов N. Найди минимальный объём последовательности в байтах.", "Одно целое число."
            source = """import math
s,n=map(int,input().split());print((math.ceil(math.log2(s))*n+7)//8)"""
        elif family == 2:
            values = [(26, 8, 100), (33, 6, 10), (10, 5, 20), (2, 12, 7), (64, 4, 30)]
            cases = [(f"{alphabet} {length} {count}", (math.ceil(math.log2(alphabet)) * length * count + 7) // 8) for alphabet, length, count in values]
            statement, output = "Даны размер алфавита A, длина пароля L и число паролей N. Найди минимальный объём базы в байтах.", "Одно целое число."
            source = """import math
a,l,n=map(int,input().split());print((math.ceil(math.log2(a))*l*n+7)//8)"""
        elif family == 3:
            values = [(255, 8), (256, 8), (257, 9), (31, 5), (32, 5)]
            cases = [(f"{v} {bits}", "YES" if 2 ** bits >= v else "NO") for v, bits in values]
            statement, output = "Даны V различных значений и B бит. Выведи YES, если B бит достаточно для кодирования V значений, иначе NO.", "YES или NO."
            source = """v,b=map(int,input().split());print('YES' if 2**b>=v else 'NO')"""
        elif family == 4:
            values = [(80, 7), (100, 8), (1, 1), (256, 8), (10, 4)]
            cases = [(f"{n} {bits}", n * bits) for n, bits in values]
            statement, output = "Даны N измерений и B бит на измерение. Найди общий объём в битах.", "Одно целое число."
            source = """n,b=map(int,input().split());print(n*b)"""
        elif family == 5:
            values = [(10, 3), (100, 7), (80, 10), (256, 1), (1, 64)]
            cases = [(f"{bytes} {count}", bytes * 8 // count) for bytes, count in values]
            statement, output = "Даны общий объём B байт и число одинаковых записей N. Найди число бит на одну запись.", "Одно целое число."
            source = """b,n=map(int,input().split());print(b*8//n)"""
        elif family == 6:
            values = [(26, 4), (26, 5), (10, 6), (64, 3), (2, 12)]
            cases = [(f"{alphabet} {length}", alphabet ** length) for alphabet, length in values]
            statement, output = "Даны размер алфавита A и длина кода L. Посчитай число возможных кодов.", "Одно целое число."
            source = """a,l=map(int,input().split());print(a**l)"""
        else:
            values = [(8, 16), (6, 9), (10, 20), (2, 64), (33, 5)]
            cases = [(f"{alphabet} {count}", (math.ceil(math.log2(alphabet)) * count + 7) // 8) for alphabet, count in values]
            statement, output = "Даны размер алфавита A и длина сообщения N. Найди минимальный объём сообщения в байтах.", "Одно целое число."
            source = """import math
a,n=map(int,input().split());print((math.ceil(math.log2(a))*n+7)//8)"""
        add(out, ids, task(
            problem_id=f"archive-ege11-{index+1:02d}", number=11, index=index,
            title=f"ЕГЭ 11 · кодирование данных {index+1:02d}", tags=["information", "passwords", "single_int_out"],
            statement=statement, input_format="Параметры через пробел.", output_format=output, cases=cases, source=source,
            fast_path="Быстрее: сначала посчитай биты на один объект через ceil(log2), потом умножь на число объектов и только в конце переводи в байты.",
            hints=mistake_hints(
                ("Взято число символов вместо бит", "Для A вариантов нужно ceil(log2(A)) бит, а не A бит.", "algorithm"),
                ("Биты и байты смешаны", "Перевод в байты делается только после подсчёта всех битов.", "always"),
                ("Округление вниз", "Минимальный целый объём требует (bits+7)//8.", "boundary"),
            ),
        ))
    return out

# ---------------------------------------------------------------------------
# №12 — Editor / string rewriting

def apply_editor(s: str, commands: list[tuple[str, str]]) -> str:
    for old, new in commands:
        s = s.replace(old, new)
    return s


def build_ege12(ids: set[str]) -> list[tuple[dict, dict]]:
    out: list[tuple[dict, dict]] = []
    rules = [
        ("AB", "C"), ("11", "0"), ("XYZ", "Q"), ("aa", "b"),
        ("101", "1"), ("BC", "A"), ("00", "1"), ("cat", "dog"),
    ]
    for index in range(40):
        old, new = rules[index % len(rules)]
        seeds = [old * 3 + "Z" + old, old + "X" + old * 2, "Q" + old * 4, old * 2 + "R", "S" + old * 3]
        cases = []
        for s in seeds:
            result = s
            while old in result:
                result = result.replace(old, new, 1)
            cases.append((s, result))
        source = f"""s=input().strip()\nwhile {old!r} in s:\n    s=s.replace({old!r},{new!r},1)\nprint(s)"""
        add(out, ids, task(
            problem_id=f"archive-ege12-{index+1:02d}", number=12, index=index,
            title=f"ЕГЭ 12 · Редактор {index+1:02d}", tags=["editor", "rewriting", "single_token_out"],
            statement=f"Редактор заменяет первое вхождение `{old}` на `{new}` и повторяет это, пока фрагмент `{old}` встречается. Для заданной строки выведи результат.",
            input_format="Одна строка без пробелов.", output_format="Итоговая строка.", cases=cases, source=source,
            fast_path="Быстрее: храни строку и повторяй replace только пока шаблон присутствует; не перебирай позиции вручную после каждой замены.",
            hints=mistake_hints(
                ("Заменены все вхождения сразу", "Одна команда заменяет первое вхождение; порядок замен важен.", "algorithm"),
                ("Цикл не доведён до остановки", "Повторяй, пока шаблон ещё встречается, иначе часть замен останется.", "loop"),
                ("Шаблон ищется после изменения индекса", "После замены строка меняет длину — ищи следующее вхождение заново.", "boundary"),
            ),
        ))
    return out


# ---------------------------------------------------------------------------
# №22 — parallel processes / critical path

def process_dataset(seed: int, n: int = 7) -> list[tuple[int, int, list[int]]]:
    rng = random.Random(seed)
    rows = []
    for i in range(1, n + 1):
        duration = 2 + rng.randrange(1, 12)
        if i <= 2:
            deps = []
        else:
            deps = sorted(rng.sample(range(1, i), rng.randrange(0, min(3, i - 1) + 1)))
        rows.append((i, duration, deps))
    return rows


def critical_time(rows: list[tuple[int, int, list[int]]]) -> int:
    by_id = {pid: (duration, deps) for pid, duration, deps in rows}
    done: dict[int, int] = {}
    def finish(pid: int) -> int:
        if pid in done:
            return done[pid]
        duration, deps = by_id[pid]
        done[pid] = duration + max((finish(dep) for dep in deps), default=0)
        return done[pid]
    return max(finish(pid) for pid, _, _ in rows)


def build_ege22(ids: set[str]) -> list[tuple[dict, dict]]:
    out: list[tuple[dict, dict]] = []
    for index in range(40):
        family = index % 8
        fixtures = []
        for seed in range(index, index + 5):
            rows = process_dataset(seed + 700)
            if family == 0:
                answer = critical_time(rows)
                statement = "Найди минимальное время завершения всех процессов при параллельном запуске независимых процессов."
            elif family == 1:
                answer = max(duration for _, duration, _ in rows)
                statement = "Найди максимальное время выполнения одного процесса без учёта зависимостей."
            elif family == 2:
                answer = sum(duration for _, duration, deps in rows if not deps)
                statement = "Найди сумму длительностей независимых процессов (у которых нет зависимостей)."
            elif family == 3:
                answer = sum(bool(deps) for _, _, deps in rows)
                statement = "Посчитай процессы, у которых есть хотя бы одна зависимость."
            elif family == 4:
                answer = max(len(deps) for _, _, deps in rows)
                statement = "Найди максимальное число непосредственных предшественников одного процесса."
            elif family == 5:
                answer = sum(duration for _, duration, _ in rows)
                statement = "Найди суммарную длительность всех процессов, если выполнять их строго последовательно."
            elif family == 6:
                answer = max(pid for pid, _, deps in rows if not deps)
                statement = "Найди максимальный идентификатор среди независимых процессов."
            else:
                answer = critical_time(rows) - max(duration for _, duration, _ in rows)
                statement = "Найди, на сколько критический путь длиннее самого долгого отдельного процесса."
            text = "\n".join([str(len(rows)), *[f"{pid} {duration} {';'.join(map(str, deps)) if deps else '0'}" for pid, duration, deps in rows]])
            fixtures.append((text, answer))
        if family == 0:
            source = """n=int(input());rows={}
for _ in range(n):
 p,t,*rest=input().split();deps=[] if rest==['0'] else list(map(int,rest[0].split(';')));rows[int(p)]=(int(t),deps)
from functools import lru_cache
@lru_cache(None)
def finish(p):
 t,d=rows[p];return t+max((finish(x) for x in d),default=0)
print(max(finish(p) for p in rows))"""
            output = "Одно число — время завершения."
        elif family == 1:
            source = """n=int(input());best=0
for _ in range(n):
 p,t,*rest=input().split();best=max(best,int(t))
print(best)"""
            output = "Одно число."
        elif family == 2:
            source = """n=int(input());ans=0
for _ in range(n):
 p,t,*rest=input().split();ans+=int(t) if rest==['0'] else 0
print(ans)"""
            output = "Одно число."
        elif family == 3:
            source = """n=int(input());ans=0
for _ in range(n):
 p,t,*rest=input().split();ans+=rest!=['0']
print(ans)"""
            output = "Одно число."
        elif family == 4:
            source = """n=int(input());best=0
for _ in range(n):
 p,t,*rest=input().split();best=max(best,0 if rest==['0'] else len(rest[0].split(';')))
print(best)"""
            output = "Одно число."
        elif family == 5:
            source = """n=int(input());ans=0
for _ in range(n):
 p,t,*rest=input().split();ans+=int(t)
print(ans)"""
            output = "Одно число."
        elif family == 6:
            source = """n=int(input());best=0
for _ in range(n):
 p,t,*rest=input().split()
 if rest==['0']: best=max(best,int(p))
print(best)"""
            output = "Одно число."
        else:
            source = """n=int(input());rows={}
for _ in range(n):
 p,t,*rest=input().split();rows[int(p)]=(int(t),[] if rest==['0'] else list(map(int,rest[0].split(';'))))
from functools import lru_cache
@lru_cache(None)
def f(p):
 t,d=rows[p];return t+max((f(x) for x in d),default=0)
critical=max(f(p) for p in rows);print(critical-max(t for t,d in rows.values()))"""
            output = "Одно число."
        add(out, ids, task(
            problem_id=f"archive-ege22-{index+1:02d}", number=22, index=index,
            title=f"ЕГЭ 22 · процессы {index+1:02d}", tags=["processes", "critical_path", "single_int_out"],
            statement=statement,
            input_format="N, затем N строк: ID, длительность и список зависимостей через `;` или 0.",
            output_format=output, cases=fixtures, source=source,
            fast_path="Быстрее: представь зависимости как DAG и вычисляй finish процесса через мемоизированный критический путь; не симулируй миллисекунды.",
            hints=mistake_hints(
                ("Процессы сложены последовательно всегда", "Независимые процессы могут идти параллельно; важен максимум времени предшественников.", "algorithm"),
                ("Зависимость прочитана наоборот", "B зависит от A: сначала заканчивается A, потом может начаться B.", "condition"),
                ("Нет кэша для общего предшественника", "Один процесс может быть предшественником нескольких; его finish считай один раз.", "complexity"),
            ),
        ))
    return out


GENERATORS = {
    1: build_ege1,
    3: build_ege3,
    4: build_ege4,
    6: build_ege6,
    7: build_ege7,
    10: build_ege10,
    11: build_ege11,
    12: build_ege12,
    22: build_ege22,
}


def main() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    existing_ids = {str(item["id"]) for item in catalog}
    generated: list[tuple[dict, dict]] = []
    for number, generator in GENERATORS.items():
        topic = TOPICS[number]
        existing = sum(item.get("topic") == topic for item in catalog)
        if existing >= 40:
            continue
        generated.extend(generator(existing_ids)[: max(0, 40 - existing)])
    # Keep the first 40 per new topic; all generators are deterministic and
    # produce at least 40.  Existing catalog tasks are not replaced here.
    for item, solution in generated:
        catalog.append(item)
    old_solutions = json.loads(SOLUTIONS.read_text(encoding="utf-8")) if SOLUTIONS.exists() else []
    solution_map = {str(item["id"]): item for item in old_solutions}
    for _, solution in generated:
        solution_map[solution["id"]] = solution
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SOLUTIONS.write_text(json.dumps(list(solution_map.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("generated", len(generated), "tasks; catalog", len(catalog))


if __name__ == "__main__":
    main()
