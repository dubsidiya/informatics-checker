# -*- coding: utf-8 -*-
import unittest

from checker.grade import grade_solution
from checker.problems import get_problem


class GradeTests(unittest.TestCase):
    def test_correct_sum_two(self):
        result = grade_solution(
            get_problem("sum-two"),
            "a, b = map(int, input().split())\nprint(a + b)\n",
        )
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
        result = grade_solution(
            get_problem("sum-two"),
            "print(a + b)\n",
        )
        self.assertEqual(result.status, "fail")
        self.assertTrue(any(test.verdict == "RE" for test in result.tests))
        self.assertTrue(any(hint.kind == "runtime" for hint in result.hints))


if __name__ == "__main__":
    unittest.main()
