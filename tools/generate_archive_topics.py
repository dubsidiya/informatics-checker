#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate safe, input-based adaptations of techniques from ege2027kp.

The archive is primarily a collection of static exam questions and answers.
A static answer does not make a fair programming-checker task, so this tool
adds transparently labelled author adaptations with independent public and
hidden variants.  The technique and provenance point to the complete archive;
the task is not presented as an official EGE variant.
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
TOPICS = {1: "ЕГЭ 1", 3: "ЕГЭ 3", 4: "ЕГЭ 4", 6: "ЕГЭ 6", 7: "ЕГЭ 7", 10: "ЕГЭ 10", 11: "ЕГЭ 11", 12: "ЕГЭ 12", 22: "ЕГЭ 22"}
PROVENANCE = "Авторская автоматизируемая адаптация приёмов из полного локального архива ege2027kp; это не официальный вариант ЕГЭ."


def hints(*items: tuple[str, str, str]) -> list[dict[str, str]]:
    return [{"title": a, "detail": b, "signal": c} for a, b, c in items]


def task(pid: str, title: str, number: int, index: int, tags: list[str], statement: str,
         input_format: str, output_format: str, cases: list[tuple[str, Any]], source: str,
         fast_path: str, mistake_hints: list[dict[str, str]]) -> tuple[dict, dict]:
    tests = [{"stdin": str(stdin), "stdout": str(stdout), "hidden": pos >= 2}
             for pos, (stdin, stdout) in enumerate(cases)]
    item = {
        "id": pid, "title": title, "level": ("старт", "средне", "сложно")[index % 3],
        "topic": TOPICS[number], "tags": [f"ege{number}", "archive_adaptation", *tags],
        "statement": statement, "input_format": input_format, "output_format": output_format,
        "examples": [{"stdin": x["stdin"], "stdout": x["stdout"]} for x in tests[:2]],
        "tests": tests, "files": [], "provenance": PROVENANCE, "author_created": True,
        "mistake_hints": mistake_hints, "fast_path": fast_path,
    }
    return item, {"id": pid, "source": source.rstrip() + "\n"}


def file_task(pid: str, title: str, number: int, index: int, tags: list[str], statement: str,
              output_format: str, fixtures: list[tuple[str, Any]], source: str,
              fast_path: str, mistake_hints: list[dict[str, str]]) -> tuple[dict, dict]:
    folder = DATA / f"ege{number}"
    folder.mkdir(parents=True, exist_ok=True)
    tests = []
    public = ""
    for pos, (content, expected) in enumerate(fixtures):
        name = f"archive-ege{number}-{pid.rsplit('-', 1)[-1]}-{'public' if pos == 0 else f'hidden-{pos}'}.txt"
        rel = f"ege{number}/{name}"
        (DATA / rel).write_text(content, encoding="utf-8")
        if pos == 0:
            public = rel
        tests.append({"stdin": "", "stdout": str(expected), "hidden": pos >= 2, "file": rel})
    item = {
        "id": pid, "title": title, "level": ("старт", "средне", "сложно")[index % 3],
        "topic": TOPICS[number], "tags": [f"ege{number}", "archive_adaptation", "file_input", *tags],
        "statement": statement,
        "input_format": f"Файл `{Path(public).name}` уже подключён; в программе доступен и как `{number}.txt`.",
        "output_format": output_format,
        "examples": [{"stdin": "", "stdout": str(fixtures[0][1])}, {"stdin": "", "stdout": str(fixtures[1][1])}],
        "tests": tests, "files": [public], "provenance": PROVENANCE, "author_created": True,
        "mistake_hints": mistake_hints, "fast_path": fast_path,
    }
    return item, {"id": pid, "source": source.rstrip() + "\n"}


def add(out: list[tuple[dict, dict]], ids: set[str], pair: tuple[dict, dict]) -> None:
    if pair[0]["id"] not in ids:
        out.append(pair)
        ids.add(pair[0]["id"])


# ----- №1: graph modelling -------------------------------------------------
def graph_edges(seed: int, n: int) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    edges = {(i, i + 1) for i in range(1, n)}
    for _ in range(4):
        a, b = sorted(rng.sample(range(1, n + 1), 2))
        edges.add((a, b))
    return sorted(edges)


def graph_text(n: int, edges: list[tuple[int, int]], extra: str = "") -> str:
    lines = [f"{n} {len(edges)}", *[f"{a} {b}" for a, b in edges]]
    if extra:
        lines.append(extra)
    return "\n".join(lines)


def adjacency(n: int, edges: list[tuple[int, int]]) -> list[list[int]]:
    g = [[] for _ in range(n + 1)]
    for a, b in edges:
        g[a].append(b)
        g[b].append(a)
    return g


def components(n: int, edges: list[tuple[int, int]]) -> int:
    g, seen, answer = adjacency(n, edges), set(), 0
    for start in range(1, n + 1):
        if start in seen:
            continue
        answer += 1
        seen.add(start)
        q = [start]
        for v in q:
            for u in g[v]:
                if u not in seen:
                    seen.add(u)
                    q.append(u)
    return answer


def distance(n: int, edges: list[tuple[int, int]], s: int, t: int) -> int:
    g = adjacency(n, edges)
    d = [-1] * (n + 1)
    d[s] = 0
    q = deque([s])
    while q:
        v = q.popleft()
        for u in g[v]:
            if d[u] == -1:
                d[u] = d[v] + 1
                q.append(u)
    return d[t]


def ege1(count: int, ids: set[str]) -> list[tuple[dict, dict]]:
    out = []
    sources = [
        ("степень вершины", "degree"), ("число рёбер", "edges"), ("число компонент", "components"),
        ("максимальная степень", "maxdegree"), ("достижимость", "reachable"),
        ("кратчайший путь", "distance"), ("вершины степени не меньше K", "threshold"), ("треугольники", "triangles"),
    ]
    for index in range(count):
        label, family = sources[index % len(sources)]
        cases: list[tuple[str, Any]] = []
        for seed in range(index, index + 5):
            n = 5 + seed % 3
            edges = graph_edges(seed + 101, n)
            g = adjacency(n, edges)
            if family == "degree":
                v = seed % n + 1; cases.append((graph_text(n, edges, str(v)), len(g[v])))
            elif family == "edges": cases.append((graph_text(n, edges), len(edges)))
            elif family == "components": cases.append((graph_text(n, edges), components(n, edges)))
            elif family == "maxdegree": cases.append((graph_text(n, edges), max(map(len, g[1:]))))
            elif family == "reachable": cases.append((graph_text(n, edges, f"1 {n}"), "YES" if distance(n, edges, 1, n) >= 0 else "NO"))
            elif family == "distance": cases.append((graph_text(n, edges, f"1 {n}"), distance(n, edges, 1, n)))
            elif family == "threshold":
                k = 2 + seed % 3; cases.append((graph_text(n, edges, str(k)), sum(len(g[v]) >= k for v in range(1, n + 1))))
            else:
                edge_set = set(edges)
                ans = sum((a, b) in edge_set and (a, c) in edge_set and (b, c) in edge_set
                          for a in range(1, n + 1) for b in range(a + 1, n + 1) for c in range(b + 1, n + 1))
                cases.append((graph_text(n, edges), ans))
        if family == "degree":
            statement, output = "Дан неориентированный граф. Найди степень указанной вершины.", "Одно число — степень вершины."
            source = """n,m=map(int,input().split())
g=[[] for _ in range(n+1)]
for _ in range(m):
 a,b=map(int,input().split());g[a].append(b);g[b].append(a)
v=int(input())
print(len(g[v]))"""
        elif family == "edges":
            statement, output = "Дан неориентированный граф. Выведи число его рёбер.", "Одно целое число."
            source = """n,m=map(int,input().split())
for _ in range(m): input()
print(m)"""
        elif family == "components":
            statement, output = "Дан неориентированный граф. Найди число компонент связности.", "Одно целое число."
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
        elif family == "maxdegree":
            statement, output = "Дан неориентированный граф. Найди наибольшую степень вершины.", "Одно целое число."
            source = """n,m=map(int,input().split())
d=[0]*(n+1)
for _ in range(m):
 a,b=map(int,input().split());d[a]+=1;d[b]+=1
print(max(d))"""
        elif family == "reachable":
            statement, output = "Дан неориентированный граф и две вершины. Выведи YES, если путь существует, иначе NO.", "YES или NO."
            source = """n,m=map(int,input().split())
g=[[] for _ in range(n+1)]
for _ in range(m):
 a,b=map(int,input().split());g[a].append(b);g[b].append(a)
s,t=map(int,input().split());seen={s};q=[s]
for v in q:
 for u in g[v]:
  if u not in seen: seen.add(u);q.append(u)
print('YES' if t in seen else 'NO')"""
        elif family == "distance":
            statement, output = "Дан неориентированный граф и две вершины. Найди длину кратчайшего пути по числу рёбер, либо -1.", "Одно целое число."
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
        elif family == "threshold":
            statement, output = "Дан неориентированный граф и число K. Посчитай вершины степени не меньше K.", "Одно целое число."
            source = """n,m=map(int,input().split());d=[0]*(n+1)
for _ in range(m):
 a,b=map(int,input().split());d[a]+=1;d[b]+=1
k=int(input());print(sum(x>=k for x in d[1:]))"""
        else:
            statement, output = "Дан неориентированный граф. Посчитай треугольники — тройки попарно соединённых вершин.", "Одно целое число."
            source = """n,m=map(int,input().split());e=set()
for _ in range(m):
 a,b=sorted(map(int,input().split()));e.add((a,b))
ans=0
for a in range(1,n+1):
 for b in range(a+1,n+1):
  for c in range(b+1,n+1): ans+=(a,b) in e and (a,c) in e and (b,c) in e
print(ans)"""
        _add(out, ids, task(f"archive-ege1-{index + 1:02d}", f"ЕГЭ 1 · графы {index + 1:02d}", 1, index,
            ["graphs", "single_int_out"], statement,
            "N M, затем M рёбер; дополнительные данные указаны в условии.", output, cases, source,
            "Быстрее: построй список смежности один раз; обход BFS/DFS работает за O(N + M).",
            hints(("Ребро добавлено в одну сторону", "Граф неориентированный: добавь обе связи a→b и b→a.", "algorithm"),
                  ("Нумерация вершин сдвинута", "Вершины идут с 1, поэтому удобно хранить N+1 ячеек.", "boundary"),
                  ("Путь проверен одним шагом", "Достижимость требует обхода всей цепочки рёбер.", "always"))))
    return out
