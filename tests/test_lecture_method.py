# -*- coding: utf-8 -*-
import json
import os
import unittest

os.environ.setdefault("CHECKER_ENV", "test")
os.environ.setdefault("CHECKER_RUNNER", "local")

from checker.grade import grade_solution
from checker.problems import get_problem

MANIFEST = {
    item["id"]: item["source"]
    for item in json.load(open("data/solution_manifest.json", encoding="utf-8"))
}

# Same answers as the tests, another algorithm than the one on the board.
OTHER_WAYS = {
    "sum-until-zero": "xs=[]\nwhile True:\n x=int(input())\n if x==0: break\n xs.append(x)\nprint(sum(xs))\n",
    "product-until-zero": "import math\nxs=[]\nwhile True:\n x=int(input())\n if x==0: break\n xs.append(x)\nprint(math.prod(xs) if xs else 1)\n",
    "divisors-from-two": "x=int(input())\nprint(*[i for i in range(2,x+1) if x%i==0], sep='\\n')\n",
    "keep-evens": "print(*[x for x in map(int, input().split()) if x%2==0])\n",
    "prime-factors": (
        "x=int(input())\na=[]\nd=2\n"
        "while d*d<=x:\n"
        " while x%d==0:\n  a.append(d); x//=d\n"
        " d+=1\n"
        "if x>1: a.append(x)\n"
        "print(*a)\n"
    ),
    "all-divisors": "x=int(input())\nprint(*[i for i in range(1,x+1) if x%i==0])\n",
}


class LectureMethodTests(unittest.TestCase):
    def test_lecture_source_is_accepted(self):
        for problem_id, source in MANIFEST.items():
            if problem_id not in OTHER_WAYS:
                continue
            with self.subTest(problem_id=problem_id):
                result = grade_solution(get_problem(problem_id), source)
                self.assertEqual(result.status, "ok", result.message)
                self.assertNotIn("не из лекции", (result.message or "").lower())

    def test_other_algorithm_is_accepted_with_shorter_line(self):
        for problem_id, source in OTHER_WAYS.items():
            with self.subTest(problem_id=problem_id):
                result = grade_solution(get_problem(problem_id), source)
                self.assertEqual(result.status, "ok", result.message)
                self.assertNotEqual(result.status, "fail")
                self.assertNotIn("не из лекции", (result.message or "").lower())
                explanation = result.explanation
                self.assertIsNotNone(explanation)
                blob = f"{explanation.headline} {explanation.next_step} {explanation.how}".lower()
                self.assertIn("можно короче", explanation.next_step.lower())
                self.assertIn("напиши", explanation.next_step.lower())

    def test_ege_task_is_outside_the_gate(self):
        from checker.lecture_method import lecture_gap

        problem = get_problem("ege17-1")
        self.assertIsNone(lecture_gap(problem, "print(1)\n"))
        result = grade_solution(problem, MANIFEST["ege17-1"])
        self.assertEqual(result.status, "ok", result.message)
        self.assertNotIn("не из лекции", (result.message or "").lower())
        self.assertNotIn("можно короче", (result.explanation.next_step or "").lower())
