# -*- coding: utf-8 -*-
import os
import unittest

os.environ.setdefault("CHECKER_ENV", "test")
os.environ.setdefault("CHECKER_RUNNER", "local")

from checker.grade import grade_solution
from checker.problems import get_problem
from checker.safety import find_forbidden
from checker.sandbox import run_playground, run_student


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

    def test_indirect_builtin_escape_is_forbidden(self):
        for source in (
            "print(globals()['__builtins__']['open']('/etc/passwd').read())\n",
            "print(getattr(object, '__subclasses__'))\n",
            "print(__builtins__.__dict__['eval']('2+2'))\n",
        ):
            self.assertIsNotNone(find_forbidden(source), source)

    def test_harmless_text_is_not_blocked(self):
        self.assertIsNone(find_forbidden("print('open')\n"))

    def test_playground_reads_only_uploaded_file(self):
        result = run_playground(
            "print(open('anything.txt').read().strip())\n",
            "",
            "input.txt",
            "hello",
            timeout=2,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "hello")

    def test_playground_cannot_write_uploaded_file(self):
        result = run_playground(
            "open('input.txt', 'w').write('bad')\n",
            "",
            "input.txt",
            "hello",
            timeout=2,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PermissionError", result.stderr)

    def test_playground_can_read_empty_uploaded_file(self):
        result = run_playground(
            "print(repr(open('empty.txt').read()))\n",
            "",
            "empty.txt",
            "",
            timeout=2,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "''")


if __name__ == "__main__":
    unittest.main()
