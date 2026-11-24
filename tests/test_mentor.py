from __future__ import annotations

import json
import unittest

from checker.config import reset_config
from checker.grade import grade_solution
from checker.mentor import _accepted, _goal_reason, add_mentor, build_messages, mentor_reason, parse_mentor
from checker.models import Explanation, GradeResult
from checker.problems import get_problem


class MentorParseTests(unittest.TestCase):
    def test_reads_json_wrapped_in_thoughts(self):
        raw = '<think>долго</think>\n```json\n{"path":"fixable","line":4,"look":"range(n)","instead":"range(n + 1)"}\n```'
        path, line, look, instead = parse_mentor(raw)
        self.assertEqual(path, "fixable")
        self.assertEqual(line, 4)
        self.assertEqual(look, "range(n)")
        self.assertEqual(instead, "range(n + 1)")

    def test_drops_a_rewritten_program(self):
        raw = json.dumps({"path": "fixable", "line": 1, "look": "print", "instead": "def f(): return 1"})
        path, line, look, instead = parse_mentor(raw)
        self.assertEqual((path, line, look, instead), ("fixable", 1, "print", ""))

    def test_whitespace_only_change_is_rejected(self):
        raw = json.dumps({
            "path": "fixable",
            "line": 5,
            "look": "if x < 18 : return f(x+1)+f(x*2)",
            "instead": "if x < 18: return f(x+1)+f(x*2)",
        })
        self.assertIsNone(_accepted(
            parse_mentor(raw),
            "def f(x):\n    if x < 18 : return f(x+1)+f(x*2)\n",
        ))

    def test_return_fragment_is_a_valid_hint(self):
        raw = json.dumps({"path": "fixable", "line": "6", "look": "return 0", "instead": "return 1"})
        path, line, look, instead = parse_mentor(raw)
        self.assertEqual((path, line, look, instead), ("fixable", 6, "return 0", "return 1"))

    def test_rejects_unknown_path(self):
        self.assertIsNone(parse_mentor('{"path":"maybe","line":1,"look":"print","instead":"+"}'))

    def test_reason_is_the_why_field(self):
        raw = json.dumps(
            {
                "path": "fixable",
                "line": 2,
                "look": "-",
                "instead": "+",
                "why": "В условии сумма, а код вычитает, поэтому пример даёт не ту сумму.",
            },
            ensure_ascii=False,
        )
        self.assertIn("вычитает", mentor_reason(raw))

    def test_short_reason_is_dropped(self):
        self.assertEqual(mentor_reason('{"path":"fixable","why":"коротко"}'), "")

    def test_sentences_before_json_are_the_reason(self):
        raw = (
            "В условии сумма, а код вычитает второе число из первого. "
            "На примере получается разность, а не сумма.\n"
            '{"path":"fixable","line":2,"look":"-","instead":"+"}'
        )
        self.assertIn("вычитает", mentor_reason(raw))


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
                {"path": "dead_end", "line": 1, "look": hidden, "instead": ""},
                ensure_ascii=False,
            )

        add_mentor(problem, result, source, complete=complete)
        payload = json.dumps(result.to_dict(), ensure_ascii=False)
        self.assertNotIn(hidden, payload)
        self.assertEqual(result.explanation.mentor, "")

    def test_prompt_tells_the_model_where_numbers_come_from(self):
        problem = get_problem("ege23-2")
        source = "def f(x):\n    return 0\nprint(f(550))\n"
        result = grade_solution(problem, source)
        blob = json.dumps(build_messages(problem, result, source), ensure_ascii=False)
        self.assertIn("print(f", blob)
        self.assertIn("прибавь", blob)
        self.assertIn("550", blob)

    def test_hint_about_a_removed_piece_is_dropped(self):
        problem = get_problem("sum-two")
        source = "a, b = map(int, input().split())\nprint(a * b)\n"
        result = grade_solution(problem, source)
        self.assertNotEqual(result.status, "ok")

        def complete(_messages):
            return json.dumps({"path": "fixable", "line": 2, "look": "-", "instead": "+"})

        add_mentor(problem, result, source, complete=complete)
        self.assertEqual(result.explanation.mentor, "")
        self.assertEqual(result.explanation.mentor_reason, "")

    def test_kept_hint_shows_the_reason_without_a_hidden_answer(self):
        problem = get_problem("ege17-271")
        source = "print(2, -13)\n"
        result = grade_solution(problem, source)
        hidden = next(case.stdout.strip() for case in problem.tests if case.hidden and len(case.stdout.strip()) >= 4)
        reason = "Печатается два числа, а файл читают построчно и считают пары. Верный ответ был бы " + hidden + "."

        def complete(_messages):
            return json.dumps(
                {"path": "fixable", "line": 1, "look": "print", "instead": "print(0)", "why": reason},
                ensure_ascii=False,
            )

        add_mentor(problem, result, source, complete=complete)
        self.assertIn("построчно", result.explanation.mentor_reason)
        payload = json.dumps(result.to_dict(), ensure_ascii=False)
        self.assertNotIn(hidden, payload)

    def test_prompt_does_not_repeat_an_old_hint(self):
        problem = get_problem("sum-two")
        source = "a, b = map(int, input().split())\nprint(a + b)\n"
        result = grade_solution(problem, source)
        blob = json.dumps(build_messages(problem, result, source), ensure_ascii=False)
        self.assertNotIn("не противоречь", blob)
        self.assertIn("старого чата нет", blob)
        self.assertIn("почему из-за этого", blob)

    def test_ege23_prompt_mentions_every_command(self):
        problem = get_problem("ege23-3")
        source = "def f(x):\n    if x < 18: return f(x+1)+f(x*2)\n    if x == 18: return 1\n    return 0\nprint(f(1))\n"
        result = grade_solution(problem, source)
        blob = json.dumps(build_messages(problem, result, source), ensure_ascii=False)
        self.assertIn("три слагаемых", blob)
        self.assertIn("пробел", blob)
        self.assertIn("проверка цели", blob)
        self.assertIn("из одной точки", blob)

    def test_fixable_hint_without_a_replacement_is_dropped(self):
        source = "print(s.count('C'))\n"
        parsed = parse_mentor('{"path":"fixable","line":1,"look":"count","instead":""}')
        self.assertIsNone(_accepted(parsed, source))

    def test_split_comma_must_become_semicolon(self):
        source = "nums = line.split(',')\n"
        parsed = parse_mentor('{"path":"fixable","line":1,"look":"line.split(\',\')","instead":"line.split()"}')
        self.assertIsNone(_accepted(parsed, source))

    def test_numbered_second_line_is_cut_from_the_fragment(self):
        source = "data = [int(x) for x in input()]\nprint(len(data))\n"
        parsed = parse_mentor(
            '{"path":"fixable","line":1,"look":"data = [int(x) for x in input()]\\n2| print(len(data))",'
            '"instead":"data = [int(x) for x in open(\'17-271.txt\')]\\n2| print(len(data))"}'
        )
        self.assertIsNotNone(_accepted(parsed, source))

    def test_combinations_import_points_at_the_call(self):
        source = "from itertools import combinations\nfor a, b in combinations(data, 2):\n    pass\n"
        parsed = parse_mentor(
            '{"path":"fixable","line":1,"look":"from itertools import combinations","instead":"from itertools import zip"}'
        )
        accepted = _accepted(parsed, source)
        self.assertIsNotNone(accepted)
        self.assertIn("zip(data, data[1:])", accepted)

    def test_count_loop_becomes_a_run_length_word(self):
        source = "print(s.count('C'))\n"
        parsed = parse_mentor(
            '{"path":"fixable","line":1,"look":"print(s.count(\'C\'))","instead":"print(max(len(x) for x in s.split(\'A\')))"}'
        )
        accepted = _accepted(parsed, source)
        self.assertEqual(accepted[2:], ("count", "длину подряд"))

    def test_filename_alone_is_not_a_file_open(self):
        source = "data = [int(x) for x in input()]\n"
        parsed = parse_mentor('{"path":"fixable","line":1,"look":"input()","instead":"\'17-271.txt\'"}')
        self.assertIsNone(_accepted(parsed, source))

    def test_f_string_prefix_is_not_an_invented_name(self):
        source = "print(bin(int(ip)).count('0'))\n"
        parsed = parse_mentor(
            '{"path":"fixable","line":1,"look":"bin(int(ip)).count(\'0\')","instead":"f\'{int(ip):032b}\'.count(\'0\')"}'
        )
        self.assertIsNotNone(_accepted(parsed, source))

    def test_leading_zero_note_is_in_the_prompt(self):
        problem = get_problem("ege8-385")
        source = "from itertools import product\nfor s in product('0123', repeat=4):\n    word = ''.join(s)\n"
        result = grade_solution(problem, source)
        blob = json.dumps(build_messages(problem, result, source), ensure_ascii=False)
        self.assertIn("word[0] != '0'", blob)

    def test_comment_does_not_count_as_a_change(self):
        source = "if len(set(word)) < 4:\n    n += 1\n"
        parsed = parse_mentor(
            '{"path":"fixable","line":1,"look":"if len(set(word)) < 4:","instead":"if len(set(word)) < 4: # повтор"}'
        )
        self.assertIsNone(_accepted(parsed, source))

    def test_invented_name_is_dropped(self):
        source = "s = input()\nprint(s.count('C'))\n"
        parsed = parse_mentor('{"path":"fixable","line":2,"look":"print(s.count(\'C\'))","instead":"print(best)"}')
        self.assertIsNone(_accepted(parsed, source))

    def test_ege9_prompt_uses_the_real_semicolon(self):
        problem = get_problem("ege9-160")
        source = "for line in open('9.txt'):\n    nums = line.split(',')\n"
        result = grade_solution(problem, source)
        blob = json.dumps(build_messages(problem, result, source), ensure_ascii=False)
        self.assertIn("точка с запятой", blob)
        self.assertIn("split(';')", blob)

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

    def test_ege23_wrong_goal_says_the_number_is_in_the_statement(self):
        problem = get_problem("ege23-6")
        source = (
            "from functools import lru_cache\n"
            "@lru_cache(None)\n"
            "def f(x):\n"
            "    if x < 12 : return f(x+1)+f(x+2)+f(x*3)\n"
            "    if x == 13 : return 1\n"
            "    return 0\n"
            "print(f(1))\n"
        )
        result = grade_solution(problem, source)
        self.assertNotEqual(result.status, "ok")
        self.assertEqual(grade_solution(problem, source.replace("== 13", "== 12", 1)).status, "ok")

        def complete(_messages):
            return json.dumps(
                {
                    "path": "fixable",
                    "line": 6,
                    "look": "13",
                    "instead": "12",
                    "why": "Связка условий возвращает из одной точки разные значения. В ответ попадают не те числа.",
                },
                ensure_ascii=False,
            )

        add_mentor(problem, result, source, complete=complete)
        reason = result.explanation.mentor_reason
        self.assertIn("получить число 12", reason)
        self.assertIn("проверка стоит на 13", reason)
        self.assertIn("12 написано в условии", reason)
        self.assertNotIn("одной точки", reason)
        self.assertNotIn("не те числа", reason)
        split = "def f(x):\n    if x == 13:\n        return 1\n"
        self.assertIn("12 написано в условии", _goal_reason(problem, split, 2, "13", "12"))

    def test_goal_reason_skips_a_check_that_returns_zero(self):
        problem = get_problem("ege23-6")
        source = "def f(x):\n    if x == 13:\n        return 0\n"
        self.assertEqual(_goal_reason(problem, source, 2, "13", "12"), "")

    def test_ege23_sum_without_return_is_fixable(self):
        problem = get_problem("ege23-6")
        source = (
            "from functools import lru_cache\n"
            "@lru_cache(None)\n"
            "def f(x):\n"
            "    if x < 12 : f(x+1)+f(x+2)+f(x*3)\n"
            "    if x == 12 : return 1\n"
            "    return 0\n"
            "print(f(1))\n"
        )
        result = grade_solution(problem, source)
        self.assertNotEqual(result.status, "ok")

        def complete(_messages):
            raise AssertionError("модель не нужна: не хватает только return")

        add_mentor(problem, result, source, complete=complete)
        self.assertEqual(result.explanation.mentor_path, "fixable")
        self.assertIn("return f(x+1)+f(x+2)+f(x*3)", result.explanation.mentor)
        self.assertNotIn("не довести", result.explanation.mentor)
        self.assertIn("return", result.explanation.mentor_reason)

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
