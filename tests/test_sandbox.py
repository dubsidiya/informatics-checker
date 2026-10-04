# -*- coding: utf-8 -*-
import os
import unittest

os.environ.setdefault("CHECKER_ENV", "test")
os.environ.setdefault("CHECKER_RUNNER", "local")

from checker.grade import grade_solution
from checker.problems import get_problem
from checker.safety import find_forbidden
from checker.sandbox import run_student


class SandboxTests(unittest.TestCase):
    def test_timeout_kills_the_student_process(self):
        result = run_student("while True:\n    pass\n", "", timeout=0.4)
        self.assertTrue(result.timed_out)
        self.assertEqual(result.error_type, "TimeoutError")

    def test_file_task_rejects_a_foreign_path(self):
        result = run_student(
            "print(open('/etc/passwd').read()[:20])\n",
            "",
            timeout=2,
            files=["ege24/long-c-1.txt"],
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("ABCCC", result.stdout)
        self.assertNotIn("root", result.stdout)

    def test_file_task_rejects_write_mode(self):
        result = run_student(
            "open('24.txt', 'x')\n",
            "",
            timeout=2,
            files=["ege24/long-c-1.txt"],
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PermissionError", result.stderr)

    def test_ege24_alias_and_real_name_both_open(self):
        problem = get_problem("ege24-long-c")
        for source in (
            "s = open('24.txt').read().strip()\n"
            "cur = best = 0\n"
            "for ch in s:\n"
            "    cur = cur + 1 if ch == 'C' else 0\n"
            "    best = max(best, cur)\n"
            "print(best)\n",
            "s = open('long-c-1.txt').read().strip()\n"
            "cur = best = 0\n"
            "for ch in s:\n"
            "    cur = cur + 1 if ch == 'C' else 0\n"
            "    best = max(best, cur)\n"
            "print(best)\n",
        ):
            result = grade_solution(problem, source)
            self.assertEqual(result.status, "ok", source)

    def test_wrong_topic_alias_does_not_open_ege24(self):
        result = grade_solution(
            get_problem("ege24-long-c"),
            "print(open('17.txt').read())\n",
        )
        self.assertEqual(result.status, "fail")

    def test_io_import_is_forbidden_even_with_a_file(self):
        blocked = find_forbidden("import io\nprint(io.open('24.txt').read())\n", allow_open=True)
        self.assertIsNotNone(blocked)


if __name__ == "__main__":
    unittest.main()
