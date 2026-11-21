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
    (
        "ege5-exclusive-or",
        "a, b = map(int, input().split())\nprint(int(a % 2 == 0 or b % 3 == 0))\n",
        ["ровно одно", "or"],
        ["пары", "сочетания"],
    ),
    (
        "ege5-between",
        "a, b, x = map(int, input().split())\nprint(int(a < x < b))\n",
        ["границ", "min"],
        ["пары", "сочетания"],
    ),
    (
        "ege5-not-all",
        "x = int(input())\nprint(int(x > 0 and x % 2 == 0 and x % 4 == 0))\n",
        ["отрицан", "not"],
        ["пары", "сочетания"],
    ),
    (
        "ege24-long-c",
        "print(4)\n",
        ["файл", "строк"],
        ["сочетания", "сосед"],
    ),
    (
        "ege24-pattern-bafe",
        "s = open('pattern-bafe-29.txt').read()\nprint(s.count('BAFE'))\n",
        ["цепоч", "фрагмент", "строк"],
        ["сочетания", "сосед"],
    ),
    (
        "ege20-petya-second",
        "print(24)\n",
        ["стратег", "втор"],
        ["сочетания", "сосед"],
    ),
    (
        "ege21-vanya-second",
        "print(26)\n",
        ["стратег", "−2", "-2"],
        ["сочетания", "сосед"],
    ),
    (
        "ege8-10",
        "from itertools import permutations\nprint(len(list(permutations('АОУ', 5))))\n",
        ["повтор", "product"],
        ["пары должны"],
    ),
    (
        "ege16-99",
        "a=b=1\nfor _ in range(45):\n    a, b = b, a + b\nprint(b)\n",
        ["последн", "цифр"],
        ["сочетания"],
    ),
    (
        "ege13-15",
        "print(2574125136)\n",
        ["точк", "ip", "маск"],
        ["сочетания"],
    ),
    (
        "ege23-1",
        "print(15)\n",
        ["динамик", "кэш", "программ"],
        ["сочетания"],
    ),
    (
        "ege25-5",
        "for n in range(150750, 150763):\n    d=[i for i in range(1,n+1) if n%i==0]\n    if len(d)==4:\n        print(*d)\n",
        ["range", "конец", "последн"],
        ["сочетания"],
    ),
    (
        "ege9-160",
        "print(sum(1 for s in open('9-160.csv') for _ in [s.split(',')]))\n",
        [";"],
        ["сочетания"],
    ),
    (
        "ege14-1",
        "print(6, 9, 18)\n",
        ["запят", "разделител", "основан", "цифр"],
        ["сочетания"],
    ),
    (
        "ege8-480",
        "print(777332)\n",
        ["слово", "номер", "код", "перебор"],
        ["сочетания"],
    ),
    (
        "ege13-241",
        "print('135.13.142.126')\n",
        ["точк", "ip", "маск"],
        ["сочетания"],
    ),
    (
        "ege25-206",
        "for i in range(10):\n    for j in range(10):\n        n=int(f'1{i}34567{j}9')\n        if n%17==0:\n            print(n)\n",
        ["числ", "частн", "строк"],
        ["сочетания"],
    ),
]


# Headline and «Что сделать» must name the bug. A later hint in the checklist
# is not enough: the generic numeric comparison used to stay first.
PRIMARY = [
    (
        "archive-ege1-01",
        "n,m=map(int,input().split())\n"
        "g=[[] for _ in range(n+1)]\n"
        "for _ in range(m):\n"
        " a,b=map(int,input().split())\n"
        " g[a].append(b)\n"
        "v=int(input())\n"
        "print(len(g[v]))\n",
        "Ребро записано только в одну сторону",
        "g[b].append(a)",
        ["range(1, n + 1)", "сочетания"],
    ),
    (
        "archive-ege1-01",
        "n,m=map(int,input().split())\n"
        "g=[[] for _ in range(n)]\n"
        "for _ in range(m):\n"
        " a,b=map(int,input().split())\n"
        " g[a-1].append(b-1); g[b-1].append(a-1)\n"
        "v=int(input())\n"
        "print(len(g[v]))\n",
        "Степень взята не из той ячейки",
        "v - 1",
        ["range(1, n + 1)", "сочетания"],
    ),
    (
        "archive-ege1-01",
        "n,m=map(int,input().split())\nprint(m)\n",
        "Степень не из списка смежности",
        "len(g[v])",
        ["сочетания"],
    ),
    (
        "archive-ege6-01",
        "w,h=map(int,input().split())\nprint(w*h)\n",
        "Граница попала внутрь",
        "(w - 1) * (h - 1)",
        ["дважды", "сочетания"],
    ),
    (
        "archive-ege6-02",
        "w,h=map(int,input().split())\nprint(w*h)\n",
        "Посчитана площадь вместо длины пути",
        "2 * (w + h)",
        ["сочетания"],
    ),
    (
        "archive-ege6-02",
        "w,h=map(int,input().split())\nprint(w+h)\n",
        "В длине пути нет двойки",
        "2 * (w + h)",
        ["сочетания"],
    ),
    (
        "archive-ege4-01",
        "s=input()\n"
        "code={'A':'0','B':'1','C':'10','D':'11'}\n"
        "print(''.join(code[ch] for ch in s))\n",
        "Ведущие нули кода пропали",
        "02b",
        ["5.0", "сочетания"],
    ),
    (
        "archive-ege4-01",
        "s=input()\n"
        "code={'A':'00','B':'01','C':'10','D':'11'}\n"
        "bits=''.join(code[ch] for ch in s)\n"
        "print(format(int(bits,2),'X'))\n",
        "Напечатана шестнадцатеричная запись",
        "02b",
        ["сочетания"],
    ),
    (
        "archive-ege4-03",
        "bits=input()\nprint(int(bits, 2))\n",
        "Двоичная строка стала числом",
        "i + 2",
        ["сочетания"],
    ),
    (
        "archive-ege7-01",
        "w, h, c = map(int, input().split())\nprint((w * h * c + 7) // 8)\n",
        "Число цветов принято за биты",
        "log2",
        ["пар", "сочетания", "секунд"],
    ),
    (
        "archive-ege7-01",
        "import math\nw, h, c = map(int, input().split())\nprint(w * h * math.ceil(math.log2(c)))\n",
        "Напечатаны биты, не байты",
        "// 8",
        ["пар", "сочетания", "секунд"],
    ),
    (
        "archive-ege7-04",
        "s, v = map(int, input().split())\nprint(s // v)\n",
        "Секунды округлены вниз",
        "v - 1",
        ["пар", "сочетания", "log2"],
    ),
    (
        "archive-ege10-01",
        "text = open('10.txt').read().lower()\nprint(text.count('портрет'))\n",
        "Слово ищется как подстрока",
        "count",
        ["пар", "сочетания", "range(1, n + 1)", "lower"],
    ),
    (
        "archive-ege10-01",
        "import re\ntext = open('10.txt').read()\n"
        "print(len(re.findall(r'(?<![а-яё])портрет(?![а-яё])', text)))\n",
        "Регистр не нормализован",
        "lower",
        ["пар", "сочетания", "range(1, n + 1)", "count"],
    ),
    (
        "archive-ege10-01",
        "text = open('10.txt').read().lower()\n"
        "words = text.split()\n"
        "print(sum(word == 'портрет' for word in words))\n",
        "Знак препинания прилип к слову",
        "strip",
        ["пар", "сочетания", "range(1, n + 1)", "count"],
    ),
    (
        "archive-ege3-09",
        "rows = [line.strip().split(',') for line in open('3.txt') if line.strip()]\n"
        "total = 0\n"
        "for row in rows:\n"
        "    if len(row) >= 4 and row[0] == 'Иванов' and row[2] == 'in':\n"
        "        total += int(row[1])\n"
        "print(total)\n",
        "Неверный разделитель таблицы",
        "split(';')",
        ["пар", "сочетания", "рейс"],
    ),
    (
        "archive-ege3-09",
        "rows = [line.strip().split(';') for line in open('3.txt') if line.strip()]\n"
        "print(sum(n == 'Иванов' and k == 'in' for n, c, k, r in rows))\n",
        "Считаются рейсы, не груз",
        "int(груз)",
        ["пар", "сочетания", "split(';')"],
    ),
    (
        "archive-ege3-09",
        "rows = [line.strip().split(';') for line in open('3.txt') if line.strip()]\n"
        "print(sum(int(c) for n, c, k, r in rows if n == 'Иванов'))\n",
        "В сумму попал и вывоз",
        "'in'",
        ["пар", "сочетания", "разделитель"],
    ),
    (
        "archive-ege22-11",
        "n=int(input());ans=0\n"
        "for _ in range(n):\n"
        " p,t,*rest=input().split();ans+=int(t)\n"
        "print(ans)\n",
        "В сумму попали зависимые процессы",
        "rest == ['0']",
        ["пар", "сочетания", "кластер", "нечёт", "критическ", "19", "22", "20"],
    ),
    (
        "archive-ege22-06",
        "n=int(input());rows={}\n"
        "for _ in range(n):\n"
        " p,t,*rest=input().split();deps=[] if rest==['0'] else list(map(int,rest[0].split(';')));rows[int(p)]=(int(t),deps)\n"
        "from functools import lru_cache\n"
        "@lru_cache(None)\n"
        "def finish(p):\n"
        " t,d=rows[p];return t+max((finish(x) for x in d),default=0)\n"
        "print(max(finish(p) for p in rows))\n",
        "Считается путь по зависимостям, не сумма",
        "ans += int(t)",
        ["пар", "сочетания", "кластер", "нечёт", "75", "55", "50"],
    ),
    (
        "archive-ege22-36",
        "n=int(input())\n"
        "ans=0\n"
        "for _ in range(n):\n"
        " p,t,*rest=input().split()\n"
        " if rest == ['0']:\n"
        "  ans += 1\n"
        "print(ans)\n",
        "Посчитаны процессы без зависимости",
        "rest != ['0']",
        ["пар", "сочетания", "кластер", "нечёт", "критическ"],
    ),
    (
        "archive-ege22-36",
        "n=int(input());ans=0\n"
        "for _ in range(n):\n"
        " p,t,*rest=input().split();ans+=0 if rest==['0'] else 1\n"
        "print(n-ans)\n",
        "Из числа процессов вычли зависимые",
        "print(ans)",
        ["пар", "сочетания", "кластер", "нечёт", "критическ"],
    ),
    (
        "archive-ege22-01",
        "n=int(input());ans=0\n"
        "for _ in range(n):\n"
        " p,t,*rest=input().split();ans+=int(t)\n"
        "print(ans)\n",
        "Критический путь не вычисляется",
        "finish[p]",
        ["пар", "сочетания", "кластер", "нечёт", "23", "13", "22"],
    ),
    (
        "archive-ege11-01",
        "v, n = map(int, input().split())\n"
        "print(v * n)\n",
        "Число значений принято за биты",
        "log2",
        ["пар", "сочетания", "кластер", "нечёт", "150", "80"],
    ),
    (
        "archive-ege11-16",
        "import math\n"
        "a, n = map(int, input().split())\n"
        "print(math.ceil(math.log2(a)) * n)\n",
        "Биты не переведены в целые байты",
        "// 8",
        ["пар", "сочетания", "кластер", "нечёт", "10"],
    ),
    (
        "ege24-long-c",
        "s = open('long-c-1.txt').read()\nprint(len(s))\n",
        "Нужно пройти строку посимвольно",
        "cur",
        ["map(int, input().split())"],
    ),
    (
        "ege8-10",
        "from itertools import permutations\n"
        "letters='АОУ'\n"
        "target='ОАОАО'\n"
        "for i,word in enumerate(permutations(letters,5),1):\n"
        "    if ''.join(word)==target:\n"
        "        print(i); break\n",
        "Буквы могут повторяться",
        "product",
        ["пар", "сочетания", "кластер", "нечёт"],
    ),
    (
        "ege16-1",
        "f=[0]*20\n"
        "f[1]=1\n"
        "for n in range(2,20):\n"
        "    f[n]=2*f[n-1]\n"
        "print(f[19])\n",
        "В формуле потеряно + n + 3",
        "формул",
        ["input()"],
    ),
    (
        "sum-until-zero",
        "n = int(input())\nprint(n * (n + 1) // 2)\n",
        "Чтение не до нуля",
        "while x != 0",
        ["пар", "сочетания", "кластер", "нечёт", "7"],
    ),
    (
        "product-until-zero",
        "x = int(input())\np = 0\nwhile x != 0:\n    p *= x\n    x = int(input())\nprint(p)\n",
        "Произведение начато с нуля",
        "p = 1",
        ["пар", "сочетания", "кластер", "нечёт", "6", "-10"],
    ),
    (
        "divisors-from-two",
        "x = int(input())\nfor i in range(2, x + 1):\n    if x % i == 0:\n        print(i)\n        break\n",
        "Напечатан только первый делитель",
        "break",
        ["пар", "сочетания", "кластер", "нечёт", "13"],
    ),
    (
        "keep-evens",
        "print(*[x for x in map(int, input().split()) if x % 2 == 1])\n",
        "Оставлены нечётные",
        "% 2 == 0",
        ["пар", "сочетания", "кластер", "-2"],
    ),
    (
        "prime-factors",
        "x = int(input())\nprint(*[i for i in range(2, x + 1) if x % i == 0])\n",
        "Кратность простого не снята",
        "x //= i",
        ["пар", "сочетания", "кластер", "нечёт", "13"],
    ),
    (
        "all-divisors",
        "x = int(input())\nprint(*[i for i in range(1, x + 1) if x % i == 0])\n",
        "Делители ищут от 2 до корня",
        "** 0.5",
        ["пар", "сочетания", "кластер", "нечёт", "9"],
    ),
]


class DiagnoseTests(unittest.TestCase):
    def test_every_problem_has_a_case(self):
        ids = {item.id for item in all_problems()}
        covered = {case[0] for case in CASES}
        self.assertTrue(covered <= ids)
        self.assertGreaterEqual(len(covered), 24)

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

    def test_primary_explanation_names_the_bug(self):
        for problem_id, source, title, must, banned in PRIMARY:
            with self.subTest(problem_id=problem_id, title=title):
                result = grade_solution(get_problem(problem_id), source)
                self.assertEqual(result.status, "fail", problem_id)
                explanation = result.explanation
                self.assertIsNotNone(explanation)
                self.assertEqual(explanation.headline, title)
                blob = f"{explanation.headline} {explanation.why} {explanation.how}".lower()
                self.assertIn(must.lower(), blob, blob)
                for token in banned:
                    self.assertNotIn(token.lower(), blob, f"{title} unexpectedly mentions {token}: {blob}")


if __name__ == "__main__":
    unittest.main()
