# -*- coding: utf-8 -*-
import unittest

from checker.grade import grade_solution
from checker.problems import all_problems, get_problem


# Typical student mistake for every problem: hint must name the real bug
# and must not invent pairs / combinations on unrelated tasks.
CASES = [
    (
        "sum-two",
        "a, b = input().split()\nprint(a + b)\n",
        ["строк", "int"],
        ["пар"],
    ),
    (
        "sum-1-n",
        "n = int(input())\nprint(sum(range(n)))\n",
        ["range", "15"],
        ["пар"],
    ),
    (
        "max-three",
        "print(min(map(int, input().split())))\n",
        ["минимум", "max"],
        ["пар"],
    ),
    (
        "even-odd",
        "n = int(input())\nprint(n % 2)\n",
        ["EVEN"],
        ["пар"],
    ),
    (
        "last-digit",
        "print(int(input()) // 10)\n",
        ["%", "10"],
        ["пар"],
    ),
    (
        "abs-diff",
        "a, b = map(int, input().split())\nprint(a - b)\n",
        ["abs", "модул"],
        ["пар"],
    ),
    (
        "school-grade",
        "n = int(input())\nif n < 51:\n    print(2)\nelse:\n    print(5)\n",
        ["50", "70"],
        ["пар"],
    ),
    (
        "repeat-string",
        "print(input() + input())\n",
        ["*", "повтор"],
        ["пар"],
    ),
    (
        "min-of-n",
        "input()\nprint(max(map(int, input().split())))\n",
        ["макс", "min"],
        ["пар"],
    ),
    (
        "power-of-two",
        "n = int(input())\nprint('YES' if n % 2 == 0 else 'NO')\n",
        ["степен", "чётн"],
        ["пар"],
    ),
    (
        "count-even",
        "input()\nprint(sum(x % 2 for x in map(int, input().split())))\n",
        ["нечёт", "чёт"],
        ["пар"],
    ),
    (
        "digit-sum",
        "print(int(input()) % 10)\n",
        ["последн", "сумм"],
        ["пар"],
    ),
    (
        "linear-search",
        "n, x = map(int, input().split())\na = list(map(int, input().split()))\nprint(1 if x in a else 0)\n",
        ["YES"],
        ["combinations"],
    ),
    (
        "factorial",
        "n = int(input())\np = 1\nfor i in range(n):\n    p *= i\nprint(p)\n",
        ["range"],
        ["пар"],
    ),
    (
        "reverse-digits",
        "print(input().strip()[::-1])\n",
        ["нулей", "int"],
        ["пар"],
    ),
    (
        "count-vowels",
        "print(sum(ch in 'aeiou' for ch in input()))\n",
        ["латин", "русск"],
        ["пар"],
    ),
    (
        "palindrome",
        "s = input()\nprint('YES' if s == s else 'NO')\n",
        ["переворот", "::-1"],
        ["пар"],
    ),
    (
        "fizz-count",
        "n = int(input())\nprint(sum(1 for i in range(1, n + 1) if i % 3 == 0 and i % 5 == 0))\n",
        ["and", "or"],
        ["пар"],
    ),
    (
        "gcd-two",
        "a, b = map(int, input().split())\nprint(min(a, b))\n",
        ["НОД", "min"],
        ["пар"],
    ),
    (
        "to-binary",
        "print(bin(int(input())))\n",
        ["0b"],
        ["пар"],
    ),
    (
        "unique-count",
        "input()\nprint(len(list(map(int, input().split()))))\n",
        ["set", "уникал"],
        ["пар"],
    ),
    (
        "prefix-sum",
        "input()\nprint(sum(map(int, input().split())))\n",
        ["префикс", "10"],
        ["пар"],
    ),
    (
        "second-max",
        "input()\nprint(max(map(int, input().split())))\n",
        ["втор", "макс"],
        ["пар"],
    ),
    (
        "pair-sum",
        "n, s = map(int, input().split())\n"
        "a = list(map(int, input().split()))\n"
        "print('YES' if any(a[i] + a[i + 1] == s for i in range(len(a) - 1)) else 'NO')\n",
        ["сосед"],
        ["ЕГЭ"],
    ),
    (
        "ege17-1",
        "kol = mx = 0\n"
        "for x in range(1012, 9639):\n"
        "    if x % 3 == 0 and all(x % y != 0 for y in [11, 13, 17]):\n"
        "        kol += 1\n"
        "        mx = max(mx, x)\n"
        "print(kol, mx)\n",
        ["19"],
        ["сочетания", "хотя бы одно", "подряд"],
    ),
    (
        "ege17-2",
        "xs = [x for x in range(3201, 12877) if x % 4 == 0 and all(x % p != 0 for p in (11, 13, 19))]\n"
        "print(len(xs), max(xs))\n",
        ["7"],
        ["сочетания", "хотя бы одно"],
    ),
    (
        "ege17-243",
        "from itertools import combinations\n"
        "data = [int(x) for x in open('17.txt')]\n"
        "print(len(list(combinations(data, 2))), 0)\n",
        ["сосед", "combinations"],
        [],
    ),
    (
        "ege17-243",
        "data = [int(x) for x in open('17.txt')]\n"
        "ref = max(x for x in data if x % 19 == 0)\n"
        "c = m = 0\n"
        "m = 10 ** 9\n"
        "for i in range(1, len(data)):\n"
        "    a, b = data[i - 1], data[i]\n"
        "    if a > ref and b > ref:\n"
        "        c += 1\n"
        "        m = min(m, a + b)\n"
        "print(c, m)\n",
        ["хотя бы", "or"],
        ["сочетания"],
    ),
    (
        "ege17-271",
        "data = [int(x) for x in open('17-271.txt')]\n"
        "av = sum(data) / len(data)\n"
        "count = max_s = 0\n"
        "max_s = -10 ** 9\n"
        "for i in range(len(data) - 1):\n"
        "    a, b = data[i], data[i + 1]\n"
        "    if abs(a) % 10 + abs(b) % 10 == 7 and a < av and b < av:\n"
        "        count += 1\n"
        "        max_s = max(max_s, a + b)\n"
        "print(count, max_s)\n",
        ["средн", "счётчик"],
        ["сочетания"],
    ),
    (
        "ege17-272",
        "data = [int(x) for x in open('17-272.txt')]\n"
        "pos = [x for x in data if x > 0]\n"
        "av = sum(pos) / len(pos)\n"
        "count = max_s = 0\n"
        "max_s = -10 ** 9\n"
        "for i in range(len(data) - 1):\n"
        "    a, b = data[i], data[i + 1]\n"
        "    if a > av and b > av:\n"
        "        count += 1\n"
        "        max_s = max(max_s, sum(map(int, str(abs(a)))), sum(map(int, str(abs(b)))))\n"
        "print(count, max_s)\n",
        ["хотя бы", "or"],
        ["сочетания"],
    ),
    (
        "ege17-274",
        "data = [int(x) for x in open('17-274.txt')]\n"
        "count, mi = 0, 10 ** 9\n"
        "for i in range(len(data) - 1):\n"
        "    a, b = data[i], data[i + 1]\n"
        "    if a + b > 17043 and (a + b) % 3 == 0:\n"
        "        count += 1\n"
        "        mi = min(mi, a + b)\n"
        "print(count, mi)\n",
        ["модул", "abs"],
        ["сочетания"],
    ),
    (
        "ege17-204",
        "data = [int(x) for x in open('17-204.txt')]\n"
        "count, ma = 0, -10 ** 9\n"
        "for i in range(1, len(data)):\n"
        "    if data[i] % 10 == 9:\n"
        "        count += 1\n"
        "        ma = max(ma, data[i] + data[i - 1])\n"
        "print(count, ma)\n",
        ["тро"],
        ["сочетания"],
    ),
    (
        "ege17-205",
        "data = [int(x) for x in open('17-205.txt')]\n"
        "count, ma = 0, -10 ** 9\n"
        "for i in range(1, len(data)):\n"
        "    if abs(data[i] - data[i - 1]) % 37 == 0:\n"
        "        count += 1\n"
        "        ma = max(ma, data[i] + data[i - 1])\n"
        "print(count, ma)\n",
        ["74"],
        ["сочетания"],
    ),
    (
        "ege17-257",
        "data = [int(x) for x in open('17-257.txt')]\n"
        "xs = [x for x in data if x % 7 == 0]\n"
        "print(len(xs), max(xs))\n",
        ["13"],
        ["сочетания", "хотя бы одно"],
    ),
]


class DiagnoseTests(unittest.TestCase):
    def test_every_problem_has_a_case(self):
        ids = {item.id for item in all_problems()}
        covered = {case[0] for case in CASES}
        self.assertEqual(ids, covered)

    def test_typical_mistakes(self):
        for problem_id, source, must, banned in CASES:
            with self.subTest(problem_id):
                result = grade_solution(get_problem(problem_id), source)
                self.assertEqual(result.status, "fail", problem_id)
                text = " ".join(hint.title + " " + hint.detail for hint in result.hints).lower()
                self.assertTrue(
                    any(token.lower() in text for token in must),
                    f"{problem_id}: expected one of {must} in {text!r}",
                )
                for token in banned:
                    self.assertNotIn(token.lower(), text, f"{problem_id} unexpectedly mentions {token}")


if __name__ == "__main__":
    unittest.main()
