# -*- coding: utf-8 -*-
import json
import unittest

from checker.grade import grade_solution
from checker.problems import get_problem


class ExplainTests(unittest.TestCase):
    def test_string_concat_has_what_why_how(self):
        result = grade_solution(
            get_problem("sum-two"),
            "a, b = input().split()\nprint(a + b)\n",
        )
        self.assertEqual(result.status, "fail")
        exp = result.explanation
        self.assertIsNotNone(exp)
        blob = (exp.what + exp.why + exp.how).lower()
        self.assertTrue("int" in blob or "\u0441\u0442\u0440\u043e\u043a" in blob or "23" in blob)
        self.assertIn("what", result.to_dict()["explanation"])
        self.assertTrue(exp.how.strip())

    def test_syntax_colon_tells_what_to_do(self):
        result = grade_solution(get_problem("sum-two"), "if True\n    print(1)\n")
        self.assertEqual(result.status, "syntax")
        exp = result.explanation
        self.assertEqual(exp.kind, "syntax")
        self.assertIn(":", exp.how)

    def test_name_error_mentions_name(self):
        result = grade_solution(get_problem("sum-two"), "print(xyz)\n")
        self.assertEqual(result.status, "fail")
        blob = (result.explanation.what + result.explanation.why + result.explanation.how)
        self.assertIn("xyz", blob)

    def test_hidden_ege_answer_not_in_explanation(self):
        problem = get_problem("ege17-271")
        hidden = next(case.stdout for case in problem.tests if case.hidden)
        result = grade_solution(problem, "print(2, -13)\n")
        payload = json.dumps(result.to_dict(), ensure_ascii=False)
        self.assertNotIn(hidden, payload)
        self.assertNotIn("-587", payload)


if __name__ == "__main__":
    unittest.main()
