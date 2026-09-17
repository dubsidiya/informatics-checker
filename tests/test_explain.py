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
        self.assertTrue((exp.intent or "").strip())
        self.assertTrue(
            "\u0441\u043b\u043e\u0436" in exp.intent.lower()
            or "\u0447\u0438\u0441" in exp.intent.lower()
            or "\u0441\u0442\u0440\u043e\u043a" in exp.intent.lower()
        )

    def test_syntax_colon_tells_what_to_do(self):
        result = grade_solution(get_problem("sum-two"), "if True\n    print(1)\n")
        self.assertEqual(result.status, "syntax")
        exp = result.explanation
        self.assertEqual(exp.kind, "syntax")
        self.assertIn(":", exp.how)
        self.assertTrue((exp.intent or "").strip())

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

    def test_ege17_range_how_is_not_about_pairs(self):
        result = grade_solution(get_problem("ege17-1"), "print(1)\n")
        how = (result.explanation.how or "").lower()
        self.assertNotIn("\u0441\u043e\u0441\u0435\u0434", how)
        self.assertTrue("%" in how or "\u0434\u0435\u043b" in how)

    def test_intent_sees_hardcoded_answer(self):
        result = grade_solution(get_problem("ege17-1"), "print(1)\n")
        intent = (result.explanation.intent or "").lower()
        self.assertTrue(intent)
        self.assertIn("intent", result.to_dict()["explanation"])
        self.assertTrue(
            "\u043d\u0430\u043f\u0435\u0447\u0430\u0442" in intent
            or "\u0433\u043e\u0442\u043e\u0432" in intent
            or "\u043f\u0440\u0438\u043c\u0435\u0440" in intent
        )

    def test_intent_sees_range_filter(self):
        code = (
            "k = 0\n"
            "m = 0\n"
            "for x in range(1012, 9639):\n"
            "    if x % 3 == 0:\n"
            "        k += 1\n"
            "        m = x\n"
            "print(k, m)\n"
        )
        result = grade_solution(get_problem("ege17-1"), code)
        self.assertEqual(result.status, "fail")
        intent = (result.explanation.intent or "").lower()
        self.assertTrue(
            "\u043e\u0442\u0440\u0435\u0437" in intent
            or "\u0446\u0438\u043a\u043b" in intent
            or "\u0447\u0438\u0441\u043b" in intent
        )

    def test_name_error_intent_mentions_xyz(self):
        result = grade_solution(get_problem("sum-two"), "print(xyz)\n")
        self.assertIn("xyz", result.explanation.intent or "")


if __name__ == "__main__":
    unittest.main()
