from __future__ import annotations

import json
import unittest

from checker.config import reset_config
from checker.grade import grade_solution
from checker.mentor import add_mentor, build_messages, parse_mentor
from checker.models import Explanation, GradeResult
from checker.problems import get_problem


class MentorParseTests(unittest.TestCase):
    def test_reads_json_wrapped_in_thoughts(self):
        raw = '<think>долго</think>\n```json\n{"path":"fixable","note":"Смотри на range: конец отрезка не входит, прибавь единицу."}\n```'
        path, note = parse_mentor(raw)
        self.assertEqual(path, "fixable")
        self.assertIn("range", note)
        self.assertNotIn("json", note)

    def test_rejects_a_full_program(self):
        note = "def f():\n    return 1\n; print(1); print(2); print(3); print(4); print(5)"
        self.assertIsNone(parse_mentor(json.dumps({"path": "fixable", "note": note})))

    def test_rejects_unknown_path(self):
        self.assertIsNone(parse_mentor('{"path":"maybe","note":"Тут достаточно длинная заметка для ученика."}'))


class MentorPromptTests(unittest.TestCase):
    def test_hidden_answers_stay_out_of_the_prompt(self):
        problem = get_problem("ege17-271")
        source = "print(2, -13)\n"
        result = grade_solution(problem, source)
        blob = json.dumps(build_messages(problem, result, source), ensure_ascii=False)
        hidden = [case.stdout.strip() for case in problem.tests if case.hidden and len(case.stdout.strip()) >= 4]
        self.assertTrue(hidden)
        for secret in hidden:
            self.assertNotIn(secret, blob)

    def test_public_failure_is_visible_to_the_model(self):
        problem = get_problem("sum-two")
        source = "a, b = map(int, input().split())\nprint(a - b)\n"
        result = grade_solution(problem, source)
        blob = json.dumps(build_messages(problem, result, source), ensure_ascii=False)
        self.assertIn("a - b", blob)
        self.assertIn("fixable", blob)

    def test_model_cannot_smuggle_a_hidden_answer_back(self):
        problem = get_problem("ege17-271")
        source = "print(2, -13)\n"
        result = grade_solution(problem, source)
        hidden = next(case.stdout.strip() for case in problem.tests if case.hidden and len(case.stdout.strip()) >= 4)

        def complete(_messages):
            return json.dumps(
                {
                    "path": "dead_end",
                    "note": f"Этот код печатает чужой ответ {hidden}, а задача про другое. Начни с чтения файла.",
                },
                ensure_ascii=False,
            )

        add_mentor(problem, result, source, complete=complete)
        payload = json.dumps(result.to_dict(), ensure_ascii=False)
        self.assertNotIn(hidden, payload)
        self.assertIn("скрытый ответ", result.explanation.mentor)
        self.assertEqual(result.explanation.mentor_path, "dead_end")

    def test_accepted_solution_does_not_call_the_model(self):
        problem = get_problem("sum-two")
        result = GradeResult(
            status="ok",
            message="ok",
            passed=1,
            total=1,
            explanation=Explanation(headline="ok", what="ok", why="ok", how="ok"),
        )

        def complete(_messages):
            raise AssertionError("модель не нужна, когда тесты прошли")

        add_mentor(problem, result, "print(1)\n", complete=complete)
        self.assertEqual(result.explanation.mentor, "")

    def test_disabled_model_keeps_the_rule_based_hint(self):
        reset_config()
        problem = get_problem("sum-two")
        source = "print(xyz)\n"
        result = grade_solution(problem, source)
        how = result.explanation.how
        add_mentor(problem, result, source)
        self.assertEqual(result.explanation.how, how)
        self.assertEqual(result.explanation.mentor, "")


if __name__ == "__main__":
    unittest.main()
