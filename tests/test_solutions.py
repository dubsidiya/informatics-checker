# -*- coding: utf-8 -*-
import os
import unittest

os.environ.setdefault("CHECKER_ENV", "test")
os.environ.setdefault("CHECKER_RUNNER", "local")

from checker.problems import get_problem
from checker.solutions import _topic_steps


class SolutionTests(unittest.TestCase):
    def test_ip_restore_uses_task_specific_walkthrough(self):
        title, steps, complexity = _topic_steps(get_problem("ege13-15"))

        text = " ".join(step["text"] for step in steps)
        self.assertEqual(title, "Восстановление IPv4-адреса")
        self.assertIn("25 | 74 | 125 | 136", text)
        self.assertIn("574", text)
        self.assertIn("255", text)
        self.assertIn("четыре", text)
        self.assertIn("перебор", complexity.lower())


if __name__ == "__main__":
    unittest.main()
