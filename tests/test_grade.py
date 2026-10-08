# -*- coding: utf-8 -*-
import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("CHECKER_ENV", "test")
os.environ.setdefault("CHECKER_RUNNER", "local")

from checker.grade import grade_solution
from checker.models import Explanation, GradeResult, Hint, TestResult
from checker.problems import all_problems, get_problem, list_summaries
from checker.store import (
    clean_student_name,
    export_csv,
    record_attempt,
    reset_ready,
    student_progress,
    summarize,
)

def _harvest_solutions():
    root = Path(__file__).resolve().parent.parent / "data"
    out = {}
    names = (
        "harvest_8.json",
        "harvest_9.json",
        "harvest_13.json",
        "harvest_14.json",
        "harvest_16.json",
        "harvest_17.json",
        "harvest_23.json",
        "harvest_25.json",
    )
    for name in names:
        for item in json.loads((root / name).read_text(encoding="utf-8")):
            out[item["id"]] = item["source"]
    return out


def _author_solutions():
    path = Path(__file__).resolve().parent.parent / "data" / "author_solutions.json"
    if not path.exists():
        return {}
    return {item["id"]: item["source"] for item in json.loads(path.read_text(encoding="utf-8"))}


def _archive_solutions():
    root = Path(__file__).resolve().parent.parent / "data"
    out = {}
    for name in ("archive_solutions.json", "game_reference_sources.json"):
        path = root / name
        if path.exists():
            out.update({item["id"]: item["source"] for item in json.loads(path.read_text(encoding="utf-8"))})
    return out


SOLUTIONS = {
    "sum-two": "a, b = map(int, input().split())\nprint(a + b)\n",
    "sum-1-n": "n = int(input())\nprint(n * (n + 1) // 2)\n",
    "max-three": "print(max(map(int, input().split())))\n",
    "even-odd": "n = int(input())\nprint('EVEN' if n % 2 == 0 else 'ODD')\n",
    "last-digit": "print(int(input()) % 10)\n",
    "abs-diff": "a, b = map(int, input().split())\nprint(abs(a - b))\n",
    "school-grade": (
        "n = int(input())\n"
        "if n < 50:\n    print(2)\n"
        "elif n < 70:\n    print(3)\n"
        "elif n < 90:\n    print(4)\n"
        "else:\n    print(5)\n"
    ),
    "repeat-string": "s = input()\nk = int(input())\nprint(s * k)\n",
    "min-of-n": "input()\nprint(min(map(int, input().split())))\n",
    "power-of-two": "n = int(input())\nprint('YES' if n > 0 and n & (n - 1) == 0 else 'NO')\n",
    "count-even": "input()\nprint(sum(x % 2 == 0 for x in map(int, input().split())))\n",
    "digit-sum": "print(sum(map(int, input().strip())))\n",
    "linear-search": (
        "n, x = map(int, input().split())\n"
        "a = list(map(int, input().split()))\n"
        "print('YES' if x in a else 'NO')\n"
    ),
    "factorial": "n = int(input())\np = 1\nfor i in range(2, n + 1):\n    p *= i\nprint(p)\n",
    "reverse-digits": "print(int(input().strip()[::-1] or '0'))\n",
    "count-vowels": "v = set('аеёиоуыэюяАЕЁИОУЫЭЮЯ')\nprint(sum(ch in v for ch in input()))\n",
    "palindrome": "s = input().strip().lower()\nprint('YES' if s == s[::-1] else 'NO')\n",
    "fizz-count": "n = int(input())\nprint(sum(1 for i in range(1, n + 1) if i % 3 == 0 or i % 5 == 0))\n",
    "gcd-two": "a, b = map(int, input().split())\nwhile b:\n    a, b = b, a % b\nprint(a)\n",
    "to-binary": "print(bin(int(input()))[2:])\n",
    "unique-count": "input()\nprint(len(set(map(int, input().split()))))\n",
    "prefix-sum": (
        "input()\ns = 0\nout = []\n"
        "for x in map(int, input().split()):\n"
        "    s += x\n    out.append(s)\n"
        "print(*out)\n"
    ),
    "second-max": "input()\na = sorted(set(map(int, input().split())))\nprint(a[-2])\n",
    "pair-sum": (
        "n, s = map(int, input().split())\n"
        "a = list(map(int, input().split()))\n"
        "seen = set()\n"
        "ok = False\n"
        "for x in a:\n"
        "    if s - x in seen:\n"
        "        ok = True\n"
        "        break\n"
        "    seen.add(x)\n"
        "print('YES' if ok else 'NO')\n"
    ),
    "ege5-logic-table": "x = int(input())\nprint(int(x % 3 == 0 and x % 5 != 0))\n",
    "ege5-boolean-condition": "a, b = map(int, input().split())\nprint(int((a > 0) != (b > 0)))\n",
    "ege5-interval": "x = int(input())\nprint(int(10 <= x <= 20 and x != 15))\n",
    "ege5-three-condition": "x = int(input())\nprint(int(x > 0 and x % 2 != 0 and x % 3 == 0))\n",
    "ege5-exclusive-or": "a, b = map(int, input().split())\nprint(int((a % 2 == 0) != (b % 3 == 0)))\n",
    "ege5-range-exclusions": "x = int(input())\nprint(int(-5 <= x <= 12 and x not in (0, 7)))\n",
    "ege5-min-condition": "x = int(input())\nprint(int(x == 4))\n",
    "ege5-order": "a, b, c = map(int, input().split())\nprint(int(a < b < c))\n",
    "ege5-three-divisibility": "x = int(input())\nprint(int(sum(x % d == 0 for d in (2, 3, 5)) == 2))\n",
    "ege5-digits-order": "x = input()\nprint(int(x[0] < x[1] < x[2]))\n",
    "ege5-area": "x, y = map(int, input().split())\nprint(int(-2 <= x <= 4 and 1 <= y <= 5 and x != 1))\n",
    "ege5-absolute": "x = int(input())\nprint(int(abs(x) <= 7 and x != 0))\n",
    "ege5-union": "x = int(input())\nprint(int(-10 <= x <= -3 or 5 <= x <= 9))\n",
    "ege5-exactly-two": "x = int(input())\nprint(int(sum((x > 0, x % 2 == 0, x % 3 == 0)) == 2))\n",
    "ege5-between": "a, b, x = map(int, input().split())\nprint(int(min(a, b) < x < max(a, b)))\n",
    "ege5-max-digit": "s = input()\nprint(int(s[0] > s[1] and s[0] > s[2]))\n",
    "ege5-sum-sign": "a, b = map(int, input().split())\nprint(int(a + b > 0 and a * b < 0))\n",
    "ege5-digits-sum": "s = input()\nprint(int(sum(map(int, s)) > 10))\n",
    "ege5-parity-match": "a, b = map(int, input().split())\nprint(int((a % 2) == (b % 2)))\n",
    "ege5-divisor-choice": "x = int(input())\nprint(int(x > 0 and ((x % 4 == 0) != (x % 7 == 0))))\n",
    "ege5-last-digit-div": "x = int(input())\nprint(int(abs(x) % 10 in (4, 7) and x % 3 == 0))\n",
    "ege5-range-step": "x = int(input())\nprint(int(10 <= x <= 50 and x % 6 == 0 and x % 9 != 0))\n",
    "ege5-sum-divisible": "a, b = map(int, input().split())\ns = a + b\nprint(int(s > 0 and s % 5 == 0))\n",
    "ege5-not-all": "x = int(input())\nprint(int(not (x > 0 and x % 2 == 0 and x % 4 == 0)))\n",
    "ege5-two-digits": "x = int(input())\nprint(int(10 <= abs(x) <= 99))\n",
    "ege5-diff-range": "a, b = map(int, input().split())\nd = abs(a - b)\nprint(int(3 <= d <= 10))\n",
    "ege5-digit-count": "x = input().strip().lstrip('-')\nprint(int(len(x) == 3))\n",
    "ege5-middle-of-three": "a, b, c = map(int, input().split())\nprint(int(a < b < c or c < b < a))\n",
    "ege5-pair-product": "a, b = map(int, input().split())\nprint(int(a * b > 10))\n",
    "ege5-remainder-check": "x = int(input())\nprint(int(x % 7 in (2, 4)))\n",
    "ege2-200": """from itertools import product, permutations
rows = [(None, 1, None, None), (0, None, 0, None), (None, 0, 0, None)]
def f(x, y, z, w):
    return ((not x) or z == w) or (y and not w)
for order in permutations('xyzw'):
    variants = []
    for row in rows:
        variants.append([v for v in product((0, 1), repeat=4) if not f(**dict(zip(order, v))) and all(a is None or a == b for a, b in zip(row, v))])
    if any(len(set(choice)) == 3 for choice in product(*variants)):
        print(''.join(order))
""",
    "ege15-105": """best = 0
for a1 in range(101):
    for a2 in range(a1, 101):
        ok = True
        for x in range(101):
            p = 44 <= x <= 49
            q = 28 <= x <= 53
            a = a1 <= x <= a2
            if not ((not a) or p or q):
                ok = False
        if ok:
            best = max(best, a2 - a1)
print(best)
""",
    "ege18-95": """lines = [line for line in open('18-95.txt') if line.strip()]
a = [list(map(int, line.split())) for line in lines]
if len(a[0]) == 1:
    a = a[1:]
n, m = len(a), len(a[0])
lo = [[10**9] * m for _ in range(n)]
hi = [[-10**9] * m for _ in range(n)]
lo[-1][0] = hi[-1][0] = 2 * a[-1][0]
for r in range(n - 1, -1, -1):
    for c in range(m):
        if r == n - 1 and c == 0:
            continue
        value = 2 * a[r][c] if (r, c) == (0, m - 1) else a[r][c]
        choices = []
        if r < n - 1:
            choices.append((lo[r + 1][c] + value, hi[r + 1][c] + value))
        if c:
            choices.append((lo[r][c - 1] + value, hi[r][c - 1] + value))
        if r < n - 1 and c:
            choices.append((lo[r + 1][c - 1] + 2 * a[r][c], hi[r + 1][c - 1] + 2 * a[r][c]))
        lo[r][c] = min(x[0] for x in choices)
        hi[r][c] = max(x[1] for x in choices)
print(hi[0][-1], lo[0][-1])
""",
    "ege26-83": """rows = {}
for line in list(open('26-82.txt'))[1:]:
    row, pos = map(int, line.split())
    if pos % 2:
        rows.setdefault(row, set()).add(pos)
best_count = max(map(len, rows.values()))
best_row = min(row for row, positions in rows.items() if len(positions) == best_count)
print(best_count, best_row)
""",
    "ege27-66": """from math import hypot
points = [tuple(map(lambda x: float(x.replace(',', '.')), line.split())) for line in open('27-66a.txt') if line.strip()]
left = set(range(len(points)))
clusters = []
while left:
    seed = left.pop()
    cluster = [seed]
    for i in cluster:
        near = [j for j in left if hypot(points[i][0] - points[j][0], points[i][1] - points[j][1]) < 0.7]
        for j in near:
            left.remove(j)
        cluster.extend(near)
    if len(cluster) >= 11:
        clusters.append(cluster)
centers = []
for cluster in clusters:
    centers.append(min(cluster, key=lambda i: sum(hypot(points[i][0] - points[j][0], points[i][1] - points[j][1]) for j in cluster)))
px = sum(points[i][0] for i in centers) / len(centers)
py = sum(points[i][1] for i in centers) / len(centers)
print(int(px * 10000), int(py * 10000))
""",
    "ege24-long-c": (
        "s = open('long-c-1.txt').read().strip()\n"
        "cur = best = 0\n"
        "for ch in s:\n"
        "    cur = cur + 1 if ch == 'C' else 0\n"
        "    best = max(best, cur)\n"
        "print(best)\n"
    ),
    "ege24-pattern-bafe": (
        "s = open('pattern-bafe-29.txt').read().strip()\n"
        "pattern = 'BAFE'\n"
        "cur = best = 0\n"
        "for ch in s:\n"
        "    cur = cur + 1 if ch == pattern[cur % 4] else (1 if ch == 'B' else 0)\n"
        "    best = max(best, cur)\n"
        "print(best)\n"
    ),
    "ege24-no-aa": (
        "s = open('no-aa.txt').read().strip()\n"
        "start = best = 0\n"
        "for i in range(1, len(s)):\n"
        "    if s[i - 1:i + 1] == 'AA': start = i\n"
        "    best = max(best, i - start + 1)\n"
        "print(max(best, 1))\n"
    ),
    "ege19-vanya-first": (
        "def can_win(a, b):\n"
        "    return any(x + y >= 62 for x, y in ((a + 2, b), (a * 2, b), (a, b + 2), (a, b * 2)))\n"
        "ans = [s for s in range(1, 55) if any(a + b < 62 and can_win(a, b) for a, b in ((9, s), (14, s), (7, s + 2), (7, 2 * s)))]\n"
        "print(min(ans))\n"
    ),
    "ege20-petya-second": (
        "from functools import cache\n"
        "@cache\n"
        "def game(a, b):\n"
        "    if a + b >= 62: return 0\n"
        "    codes = [game(a + 2, b), game(a * 2, b), game(a, b + 2), game(a, b * 2)]\n"
        "    bad = [x for x in codes if x <= 0]\n"
        "    return -max(bad) + 1 if bad else -max(codes)\n"
        "print(max(s for s in range(1, 55) if game(7, s) == 2))\n"
    ),
    "ege21-vanya-second": (
        "from functools import cache\n"
        "@cache\n"
        "def game(a, b):\n"
        "    if a + b >= 62: return 0\n"
        "    codes = [game(a + 2, b), game(a * 2, b), game(a, b + 2), game(a, b * 2)]\n"
        "    bad = [x for x in codes if x <= 0]\n"
        "    return -max(bad) + 1 if bad else -max(codes)\n"
        "print(max(s for s in range(1, 55) if game(7, s) == -2))\n"
    ),
    "ege17-1": (
        "xs = [x for x in range(1012, 9639) if x % 3 == 0 and all(x % p != 0 for p in (11, 13, 17, 19))]\n"
        "print(len(xs), max(xs))\n"
    ),
    "ege17-2": (
        "xs = [x for x in range(3201, 12877) if x % 4 == 0 and all(x % p != 0 for p in (7, 11, 13, 19))]\n"
        "print(len(xs), max(xs))\n"
    ),
    "ege17-243": (
        "data = [int(x) for x in open('17-243.txt')]\n"
        "ref = max(x for x in data if x % 19 == 0)\n"
        "count = mi = 0\n"
        "mi = 10 ** 10\n"
        "for i in range(1, len(data)):\n"
        "    a, b = data[i - 1], data[i]\n"
        "    if a > ref or b > ref:\n"
        "        count += 1\n"
        "        mi = min(mi, a + b)\n"
        "print(count, mi)\n"
    ),
    "ege17-271": (
        "data = [int(x) for x in open('17-271.txt')]\n"
        "av = sum(data) / len(data)\n"
        "count, max_s = 0, -10 ** 9\n"
        "for i in range(len(data) - 1):\n"
        "    a, b = data[i], data[i + 1]\n"
        "    if abs(a) % 10 + abs(b) % 10 == 7:\n"
        "        count += 1\n"
        "        if a < av and b < av:\n"
        "            max_s = max(max_s, a + b)\n"
        "print(count, max_s)\n"
    ),
    "ege17-272": (
        "data = [int(x) for x in open('17-272.txt')]\n"
        "pos = [x for x in data if x > 0]\n"
        "av = sum(pos) / len(pos)\n"
        "count, max_s = 0, -10 ** 9\n"
        "for i in range(len(data) - 1):\n"
        "    a, b = data[i], data[i + 1]\n"
        "    if a > av or b > av:\n"
        "        count += 1\n"
        "        max_s = max(max_s, sum(map(int, str(abs(a)))), sum(map(int, str(abs(b)))))\n"
        "print(count, max_s)\n"
    ),
    "ege17-274": (
        "data = [int(x) for x in open('17-274.txt')]\n"
        "count, mi = 0, 10 ** 9\n"
        "for i in range(len(data) - 1):\n"
        "    a, b = data[i], data[i + 1]\n"
        "    if abs(a) + abs(b) > 17043 and (abs(a) + abs(b)) % 3 == 0:\n"
        "        count += 1\n"
        "        mi = min(mi, a + b)\n"
        "print(count, mi)\n"
    ),
    "ege17-204": (
        "data = [int(x) for x in open('17-204.txt')]\n"
        "def cond(x):\n"
        "    return x > 0 and x % 10 == 9\n"
        "count, ma = 0, -10 ** 9\n"
        "for i in range(2, len(data)):\n"
        "    if (not cond(data[i - 2])) and cond(data[i - 1]) and (not cond(data[i])):\n"
        "        count += 1\n"
        "        ma = max(ma, sum(data[i - 2:i + 1]))\n"
        "print(count, ma)\n"
    ),
    "ege17-205": (
        "data = [int(x) for x in open('17-205.txt')]\n"
        "count, ma = 0, -10 ** 9\n"
        "for i in range(1, len(data)):\n"
        "    if abs(data[i] - data[i - 1]) % 74 == 0:\n"
        "        count += 1\n"
        "        ma = max(ma, data[i] + data[i - 1])\n"
        "print(count, ma)\n"
    ),
    "ege17-257": (
        "data = [int(x) for x in open('17-257.txt')]\n"
        "m7 = min(x for x in data if x % 7 == 0)\n"
        "m13 = min(x for x in data if x % 13 == 0)\n"
        "k = 7 if m7 > m13 else 13\n"
        "xs = [x for x in data if x % k == 0]\n"
        "print(len(xs), max(xs))\n"
    ),
    "count-words": "print(len(input().split()))\n",
    "bridge-range-count-max": "a, b = map(int, input().split())\nxs = [x for x in range(a, b + 1) if x % 2 == 0]\nprint(len(xs), max(xs))\n",
    "bridge-two-conditions": "x = int(input())\nprint(int(x > 0 and x % 3 == 0))\n",
    "bridge-exactly-one": "a, b = map(int, input().split())\nprint(int((a % 2 == 0) != (b % 2 == 0)))\n",
    "bridge-segment-except": "x = int(input())\nprint(int(10 <= x <= 20 and x != 15))\n",
    "bridge-last-digit": "print(int(input()) % 10)\n",
    "bridge-digit-sum": "print(sum(map(int, input().strip())))\n",
    "bridge-base-digits": "n, b = map(int, input().split())\ns = 0\nwhile n:\n    s += n % b\n    n //= b\nprint(s)\n",
    "bridge-count-in-list": "print(sum(x % 2 == 0 and x % 3 != 0 for x in map(int, input().split())))\n",
    "bridge-neighbor-pairs": "a = list(map(int, input().split()))\nxs = [a[i] + a[i + 1] for i in range(len(a) - 1) if a[i] > 0 and a[i + 1] > 0]\nprint(len(xs), max(xs) if xs else 0)\n",
    "bridge-longest-run": "s = input().strip()\nbest = cur = 1\nfor i in range(1, len(s)):\n    cur = cur + 1 if s[i] == s[i - 1] else 1\n    best = max(best, cur)\nprint(best)\n",
    "bridge-no-double": "s = input().strip()\nbest = cur = 1\nfor i in range(1, len(s)):\n    cur = cur + 1 if s[i] != s[i - 1] else 1\n    best = max(best, cur)\nprint(best)\n",
    "bridge-word-number": "from itertools import product\nn = int(input())\nwords = [''.join(p) for p in product('ABC', repeat=2)]\nprint(words[n - 1])\n",
    "bridge-count-words": "from itertools import product\nprint(sum('A' in ''.join(p) for p in product('AB', repeat=3)))\n",
    "bridge-command-count": "n = int(input())\nf = [0] * (n + 1)\nf[1] = 1\nfor x in range(1, n):\n    if x + 1 <= n:\n        f[x + 1] += f[x]\n    if x * 2 <= n:\n        f[x * 2] += f[x]\nprint(f[n])\n",
    "bridge-recursive-sum": "n = int(input())\nprint(n * (n + 1) // 2)\n",
    "bridge-four-divisors": "a, b = map(int, input().split())\nxs = []\nfor x in range(a, b + 1):\n    divs = [d for d in range(1, x + 1) if x % d == 0]\n    if len(divs) == 4:\n        xs.append(x)\nprint(len(xs), max(xs))\n",
    "reverse-number": "print(int(input()[::-1]))\n",
    "max-pair-diff": (
        "a = list(map(int, input().split()))\n"
        "print(max(abs(a[i + 1] - a[i]) for i in range(len(a) - 1)))\n"
    ),
    "count-divisible-range": (
        "a, b, k = map(int, input().split())\n"
        "print(sum(1 for x in range(a, b + 1) if x % k == 0))\n"
    ),
    "leap-year": (
        "y = int(input())\n"
        "print('YES' if (y % 4 == 0 and y % 100 != 0) or y % 400 == 0 else 'NO')\n"
    ),
    "second-minimum": "a = sorted(set(map(int, input().split())))\nprint(a[-2])\n",
    "ege8-word-abc": (
        "from itertools import product\n"
        "n = int(input())\n"
        "L = ['А', 'Б', 'В', 'Г']\n"
        "words = [''.join(p) for p in product(L, repeat=4)]\n"
        "print(words[n - 1])\n"
    ),
    "ege14-sum-base5": (
        "n = 125\n"
        "s = ''\n"
        "while n > 0:\n"
        "    s = str(n % 5) + s\n"
        "    n //= 5\n"
        "print(sum(int(c) for c in s))\n"
    ),
    "ege16-fmod": (
        "from functools import lru_cache\n"
        "@lru_cache(None)\n"
        "def f(n):\n"
        "    return 1 if n <= 2 else f(n - 1) + f(n - 2)\n"
        "print(str(f(50) % 100).zfill(2))\n"
    ),
    "ege23-programs": (
        "from functools import lru_cache\n"
        "@lru_cache(None)\n"
        "def p(c, g=8):\n"
        "    if c > g:\n"
        "        return 0\n"
        "    if c == g:\n"
        "        return 1\n"
        "    return p(c + 1) + p(c * 2)\n"
        "print(p(1))\n"
    ),
    "ege25-div3-7": (
        "for x in range(100, 201):\n"
        "    d = [i for i in range(1, x) if x % i == 0]\n"
        "    if len(d) == 3:\n"
        "        print(x, max(d))\n"
    ),
}
SOLUTIONS.update(_harvest_solutions())
SOLUTIONS.update(_author_solutions())
SOLUTIONS.update(_archive_solutions())


class GradeTests(unittest.TestCase):
    def test_correct_sum_two(self):
        result = grade_solution(get_problem("sum-two"), SOLUTIONS["sum-two"])
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.passed, result.total)

    def test_string_concat_is_logic_error(self):
        result = grade_solution(
            get_problem("sum-two"),
            "a, b = input().split()\nprint(a + b)\n",
        )
        self.assertEqual(result.status, "fail")
        blob = " ".join(hint.title + " " + hint.detail for hint in result.hints)
        self.assertTrue("input" in blob or "int" in blob)

    def test_syntax_missing_colon(self):
        result = grade_solution(
            get_problem("sum-1-n"),
            "n = int(input())\nif n > 0\n    print(n)\n",
        )
        self.assertEqual(result.status, "syntax")
        self.assertIsNotNone(result.syntax)
        self.assertEqual(result.syntax.line, 2)

    def test_range_misses_last(self):
        result = grade_solution(
            get_problem("sum-1-n"),
            "n = int(input())\nprint(sum(range(n)))\n",
        )
        self.assertEqual(result.status, "fail")
        text = " ".join(hint.title + hint.detail for hint in result.hints)
        self.assertTrue("range" in text or "1" in text)

    def test_runtime_name_error(self):
        result = grade_solution(get_problem("sum-two"), "print(a + b)\n")
        self.assertEqual(result.status, "fail")
        self.assertTrue(any(test.verdict == "RE" for test in result.tests))
        self.assertTrue(any(hint.kind == "runtime" for hint in result.hints))

    def test_catalog_has_topics_and_levels(self):
        items = list_summaries()
        self.assertGreaterEqual(len(items), 20)
        self.assertTrue(all(item.get("topic") and item.get("level") for item in items))
        for problem in all_problems():
            self.assertTrue(problem.tests)
            ege = any(tag.startswith("ege") for tag in problem.tags)
            if not problem.files and not ege and not problem.author_created:
                self.assertGreaterEqual(len(problem.tests), 4)
                self.assertTrue(problem.examples)

    def test_all_reference_solutions(self):
        missing = [item.id for item in all_problems() if item.id not in SOLUTIONS]
        self.assertEqual(missing, [])
        for problem in all_problems():
            result = grade_solution(problem, SOLUTIONS[problem.id])
            self.assertEqual(result.status, "ok", problem.id)
            self.assertTrue(result.explanation.next_step.strip(), problem.id)
            self.assertTrue(result.explanation.thought.strip(), problem.id)
            self.assertTrue(result.explanation.question.strip(), problem.id)
            self.assertTrue(result.explanation.self_check.strip(), problem.id)

    def test_every_catalog_task_has_coaching_contract(self):
        for problem in all_problems():
            self.assertTrue(problem.provenance.strip(), problem.id)
            self.assertGreaterEqual(len(problem.mistake_hints), 2, problem.id)
            self.assertTrue(problem.fast_path.strip(), problem.id)
            self.assertEqual(problem.author_created, bool(problem.author_created), problem.id)

    def test_yes_no_printed_as_one_zero(self):
        result = grade_solution(
            get_problem("linear-search"),
            "n, x = map(int, input().split())\na = list(map(int, input().split()))\nprint(1 if x in a else 0)\n",
        )
        self.assertEqual(result.status, "fail")
        text = " ".join(hint.title + hint.detail for hint in result.hints)
        self.assertTrue("1/0" in text or "YES" in text or "слов" in text)

    def test_factorial_range_hint(self):
        result = grade_solution(
            get_problem("factorial"),
            "n = int(input())\np = 1\nfor i in range(n):\n    p *= i\nprint(p)\n",
        )
        self.assertEqual(result.status, "fail")
        text = " ".join(hint.title + hint.detail for hint in result.hints)
        self.assertTrue("range" in text or "n!" in text or "120" in text)

    def test_int_on_two_numbers_hint(self):
        result = grade_solution(get_problem("sum-two"), "print(int(input()))\n")
        self.assertEqual(result.status, "fail")
        text = " ".join(hint.title + hint.detail for hint in result.hints)
        self.assertTrue("split" in text or "ValueError" in text or "int" in text)


    def test_ege17_file_and_two_numbers(self):
        result = grade_solution(get_problem("ege17-271"), SOLUTIONS["ege17-271"])
        self.assertEqual(result.status, "ok")

    def test_ege17_wrong_filename_still_works(self):
        result = grade_solution(
            get_problem("ege17-257"),
            "data = [int(x) for x in open('desktop/foo.txt')]\nm7 = min(x for x in data if x % 7 == 0)\nm13 = min(x for x in data if x % 13 == 0)\nk = 7 if m7 > m13 else 13\nxs = [x for x in data if x % k == 0]\nprint(len(xs), max(xs))\n",
        )
        self.assertEqual(result.status, "ok")

    def test_ege17_one_number_hint(self):
        result = grade_solution(
            get_problem("ege17-1"),
            "print(2151)\n",
        )
        self.assertEqual(result.status, "fail")
        text = " ".join(hint.title + hint.detail for hint in result.hints)
        self.assertTrue("два" in text)

    def test_ege17_range_missing_divisor_not_pairs(self):
        result = grade_solution(
            get_problem("ege17-1"),
            "kol = mx = 0\n"
            "for x in range(1012, 9639):\n"
            "    if x % 3 == 0 and all(x % y != 0 for y in [11, 13, 17]):\n"
            "        kol += 1\n"
            "        mx = max(mx, x)\n"
            "print(kol, mx)\n",
        )
        self.assertEqual(result.status, "fail")
        text = " ".join(hint.title + hint.detail for hint in result.hints)
        self.assertIn("19", text)
        self.assertTrue("больше" in text or "лишн" in text)
        self.assertNotIn("сочетания", text)
        self.assertNotIn("хотя бы одно", text)
        self.assertNotIn("подряд", text)

    def test_ege17_combinations_hint(self):
        result = grade_solution(
            get_problem("ege17-243"),
            "from itertools import combinations\ndata = [int(x) for x in open('17.txt')]\nprint(len(list(combinations(data, 2))), 0)\n",
        )
        self.assertEqual(result.status, "fail")
        text = " ".join(hint.title + hint.detail for hint in result.hints)
        self.assertTrue("сосед" in text or "подряд" in text or "combinations" in text.lower() or "Пары" in text)

    def test_new_ege_topic_reference_solutions(self):
        for problem_id in ("ege2-200", "ege15-105", "ege18-95", "ege26-83", "ege27-66"):
            result = grade_solution(get_problem(problem_id), SOLUTIONS[problem_id])
            self.assertEqual(result.status, "ok", problem_id)

    def test_ege26_distinct_odd_positions_required(self):
        result = grade_solution(
            get_problem("ege26-83"),
            """d = {}
for s in list(open('26-82.txt'))[1:]:
 r, p = map(int, s.split())
 if p % 2: d[r] = d.get(r, 0) + 1
r = max(d, key=d.get)
print(d[r], r)
""",
        )
        self.assertEqual(result.status, "fail")
        self.assertTrue(any("Повторы" in h.title for h in result.hints))

    def test_ege27_cluster_task_is_coordinate_only(self):
        problem = get_problem("ege27-66")
        self.assertIn("coordinates", problem.tags)
        self.assertNotIn("prefix_sums", problem.tags)
        self.assertNotIn("remainders", problem.tags)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        os.environ["CHECKER_DB"] = self.tmp.name
        reset_ready()

    def tearDown(self):
        reset_ready()
        os.environ.pop("CHECKER_DB", None)
        Path(self.tmp.name).unlink(missing_ok=True)

    def test_empty_name(self):
        self.assertEqual(clean_student_name("   "), "без имени")

    def test_summary_tracks_best(self):
        record_attempt("Анна", "sum-two", "fail", 1, 5, "нет", "print(1)")
        ok_id = record_attempt("Анна", "sum-two", "ok", 5, 5, "да", "print(2)")
        last_id = record_attempt("Борис", "sum-two", "fail", 0, 5, "нет", "print(3)")
        data = summarize()
        self.assertEqual(data["total_students"], 2)
        anna = next(item for item in data["students"] if item["name"] == "Анна")
        boris = next(item for item in data["students"] if item["name"] == "Борис")
        self.assertEqual(anna["solved"], 1)
        self.assertEqual(anna["problems"]["sum-two"]["best_status"], "ok")
        self.assertEqual(anna["problems"]["sum-two"]["best_attempt_id"], ok_id)
        self.assertEqual(boris["problems"]["sum-two"]["attempt_id"], last_id)

    def test_best_survives_later_fail(self):
        record_attempt("Анна", "sum-two", "fail", 1, 5, "нет", "print(1)")
        ok_id = record_attempt("Анна", "sum-two", "ok", 5, 5, "да", "print(2)")
        record_attempt("Анна", "sum-two", "fail", 0, 5, "нет", "print(3)")
        data = summarize()
        anna = next(item for item in data["students"] if item["name"] == "Анна")
        cell = anna["problems"]["sum-two"]
        self.assertEqual(cell["best_status"], "ok")
        self.assertEqual(cell["best_attempt_id"], ok_id)
        self.assertEqual(cell["status"], "fail")

    def test_progress_and_csv(self):
        record_attempt("Катя", "sum-two", "ok", 5, 5, "да", "print(2)")
        record_attempt("Катя", "sum-1-n", "fail", 0, 4, "нет", "print(1)")
        progress = student_progress("Катя")
        self.assertEqual(progress["solved"], ["sum-two"])
        csv_text = export_csv()
        self.assertIn("Катя", csv_text)
        self.assertIn("sum-two", csv_text)


class HiddenPayloadTests(unittest.TestCase):
    def test_ege17_hidden_answer_not_in_student_json(self):
        problem = get_problem("ege17-271")
        hidden = next(case.stdout for case in problem.tests if case.hidden)
        self.assertTrue(hidden.strip())
        result = grade_solution(problem, "print(2, -13)\n")
        self.assertEqual(result.status, "fail")
        payload = result.to_dict()
        blob = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn(hidden, blob)
        for token in hidden.split():
            if token.lstrip("-").isdigit() and len(token.lstrip("-")) >= 3:
                self.assertNotIn(token, blob)
        hidden_rows = [item for item in payload["tests"] if item["hidden"]]
        self.assertTrue(hidden_rows)
        for row in hidden_rows:
            self.assertEqual(row["expected"], "")
            self.assertEqual(row["got"], "")
            self.assertEqual(row["stdin"], "")
        self.assertFalse(payload["trace"])

    def test_teacher_can_still_see_hidden_in_internal_result(self):
        problem = get_problem("ege17-271")
        hidden = next(case.stdout for case in problem.tests if case.hidden)
        result = grade_solution(problem, "print(2, -13)\n")
        revealed = json.dumps(result.to_dict(reveal_hidden=True), ensure_ascii=False)
        self.assertIn(hidden, revealed)

    def test_short_hidden_answer_only_leaves_backticks(self):
        result = GradeResult(
            status="fail",
            message="нет",
            passed=0,
            total=1,
            tests=[
                TestResult(index=0, hidden=True, verdict="WA", stdin="", expected="8", got="7"),
            ],
            hints=[Hint(kind="logic", title="t", detail="Ожидалось `8`, получилось `7`.")],
            first_fail_index=0,
        )
        blob = json.dumps(result.to_dict(), ensure_ascii=False)
        self.assertNotIn("`8`", blob)
        self.assertNotIn("Ожидалось 8", blob)
        self.assertNotIn("получилось 7", blob)
        self.assertIn("скрытый ответ", blob)

    def test_hidden_answer_is_scrubbed_from_coach_fields(self):
        result = GradeResult(
            status="fail",
            message="нет",
            passed=0,
            total=1,
            tests=[TestResult(index=0, hidden=True, verdict="WA", stdin="", expected="42", got="41")],
            explanation=Explanation(
                headline="нет",
                what="42",
                why="42",
                how="42",
                intent="42",
                thought="42",
                question="42",
                self_check="42",
            ),
            first_fail_index=0,
        )
        blob = json.dumps(result.to_dict(), ensure_ascii=False)
        self.assertNotIn("42", blob)

    def test_short_hidden_tokens_do_not_destroy_public_counterexample(self):
        result = GradeResult(
            status="fail",
            message="нет",
            passed=0,
            total=2,
            tests=[
                TestResult(index=0, hidden=False, verdict="WA", stdin="1 3 6 7 12", expected="3", got="0"),
                TestResult(index=1, hidden=True, verdict="WA", stdin="2 3 8", expected="3", got="0"),
            ],
            hints=[Hint(kind="logic", title="t", detail="На вводе `1 3 6 7 12` ожидалось 3.")],
            explanation=Explanation(headline="t", what="3", why="3", how="3"),
            first_fail_index=0,
        )
        payload = result.to_dict()
        self.assertEqual(payload["tests"][0]["stdin"], "1 3 6 7 12")
        self.assertIn("1 3 6 7 12", payload["hints"][0]["detail"])


if __name__ == "__main__":
    unittest.main()
