# -*- coding: utf-8 -*-
"""ЕГЭ 8 hints must name the property the program misses.

The old fallback showed «Считался не тот набор объектов» for any wrong ЕГЭ 8
answer, even when the program counted the right objects at the right length.
These tests take a real task and a real student program and require a hint
about the actual filter.
"""

import unittest

from checker.ege8_model import analyze, compare, parse_spec
from checker.grade import grade_solution
from checker.problems import get_problem

GENERIC = "Считался не тот набор объектов"

DIGITS_INSTEAD_OF_LETTERS = (
    "from itertools import product\n"
    "a = [''.join(x) for x in product('0123', repeat=4)]\n"
    "b = [i for i in a if i[0] != '0' and any(i.count(x) >= 2 for x in i)]\n"
    "print(len(b))\n"
)
TYPO_JOIN = (
    "from itertools import product\n"
    "a = [''join(x) for x in product('0123', repeat=4)]\n"
    "print(len(a))\n"
)
ABAK_CORRECT = (
    "from itertools import permutations\n"
    "s = set()\n"
    "for p in permutations('АБАК'):\n"
    "    w = ''.join(p)\n"
    "    if all(w[i] != w[i + 1] for i in range(len(w) - 1)):\n"
    "        s.add(w)\n"
    "print(len(s))\n"
)
ABAK_NO_NEIGHBOURS = (
    "from itertools import permutations\n"
    "s = set()\n"
    "for p in permutations('АБАК'):\n"
    "    s.add(''.join(p))\n"
    "print(len(s))\n"
)
NO_REPEAT_FILTER = (
    "from itertools import product\n"
    "bad = 0\n"
    "for w in product('0123', repeat=4):\n"
    "    if w[0] == '0':\n"
    "        continue\n"
    "    if len(set(w)) == 4:\n"
    "        bad += 1\n"
    "print(4 ** 4 - 1 - bad)\n"
)
NO_PARITY_FILTER = (
    "from itertools import product\n"
    "count = 0\n"
    "for w in product('01234', repeat=4):\n"
    "    if w[0] == '0':\n"
    "        continue\n"
    "    if '1' in w:\n"
    "        count += 1\n"
    "print(count)\n"
)
NO_REPEAT_ARG = (
    "from itertools import product\n"
    "count = 0\n"
    "for w in product('0123'):\n"
    "    if len(w) == 4:\n"
    "        count += 1\n"
    "print(count)\n"
)


def _text(result):
    return " ".join(item.title + " " + item.detail for item in result.hints)


def _headline(result):
    return result.explanation.headline if result.explanation else ""


def _fault(problem_id, source, tag):
    """Title of the statement-model finding about one kind of filter."""
    problem = get_problem(problem_id)
    findings = compare(parse_spec(problem.statement), analyze(source), counts_size=True)
    for item in findings:
        if item.tag == tag:
            return item.title
    raise AssertionError(f"no {tag} finding for {problem_id}")


class Ege8HintTests(unittest.TestCase):
    def test_digits_instead_of_letters_is_named(self):
        result = grade_solution(get_problem("ege8-word-abc"), DIGITS_INSTEAD_OF_LETTERS)
        self.assertEqual(result.status, "fail")
        self.assertEqual(_headline(result), "Перебираются цифры, а нужны буквы")
        self.assertIn("product('АБВГ'", result.explanation.how)
        self.assertNotIn(GENERIC, _text(result))

    def test_missing_neighbour_filter_is_named(self):
        result = grade_solution(get_problem("ege8-114"), ABAK_NO_NEIGHBOURS)
        self.assertEqual(result.status, "fail")
        self.assertEqual(_headline(result), _fault("ege8-114", ABAK_NO_NEIGHBOURS, "neighbours"))
        self.assertIn("s[i] != s[i + 1]", result.explanation.how)

    def test_missing_repeat_filter_is_named(self):
        result = grade_solution(get_problem("ege8-385"), NO_REPEAT_FILTER)
        self.assertEqual(result.status, "fail")
        self.assertEqual(_headline(result), _fault("ege8-385", NO_REPEAT_FILTER, "double"))

    def test_parity_neighbour_rule_is_named(self):
        result = grade_solution(get_problem("ege8-400"), NO_PARITY_FILTER)
        self.assertEqual(result.status, "fail")
        self.assertEqual(_headline(result), _fault("ege8-400", NO_PARITY_FILTER, "neighbours"))

    def test_missing_repeat_argument_is_named(self):
        problem = get_problem("ege8-385")
        findings = compare(parse_spec(problem.statement), analyze(NO_REPEAT_ARG), counts_size=True)
        iterator = [item for item in findings if item.tag == "iterator"]
        self.assertTrue(iterator, "a product without repeat must be reported")
        self.assertIn("repeat", iterator[0].how)

    def test_missing_dot_before_join_is_named(self):
        result = grade_solution(get_problem("ege8-word-abc"), TYPO_JOIN)
        self.assertEqual(result.status, "syntax")
        self.assertIn("join", result.explanation.why)
        self.assertIn("''.join(x)", result.explanation.how)
        self.assertNotIn("двоеточ", result.explanation.how)

    def test_correct_solution_still_passes(self):
        result = grade_solution(get_problem("ege8-114"), ABAK_CORRECT)
        self.assertEqual(result.status, "ok")


if __name__ == "__main__":
    unittest.main()
