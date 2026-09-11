# -*- coding: utf-8 -*-
"""Break reference solutions in many ways and require a non-garbage hint."""

from __future__ import annotations

import unittest
from collections import defaultdict

from checker.grade import grade_solution
from checker.mutate import generate_mutants
from checker.problems import all_problems
from tests.test_grade import SOLUTIONS

PAIR_GARBAGE = ("сочетания", "хотя бы одно", "data[i]", "combinations")
GENERIC = ("вывод не совпал с эталоном", "автоматический разбор не нашёл")


def _diverse(mutants, cap: int):
    buckets: dict[str, list] = defaultdict(list)
    for item in mutants:
        buckets[item.kind].append(item)
    picked = []
    while len(picked) < cap and any(buckets.values()):
        for kind in list(buckets):
            if buckets[kind]:
                picked.append(buckets[kind].pop(0))
            if len(picked) >= cap:
                break
    return picked


class MutationDiagnoseTests(unittest.TestCase):
    def test_mutants_get_real_hints(self):
        generated = 0
        failed = 0
        covered = 0
        for problem in all_problems():
            mutants = _diverse(generate_mutants(SOLUTIONS[problem.id]), 20)
            for mutant in mutants:
                generated += 1
                result = grade_solution(problem, mutant.source)
                if result.status in {"ok", "syntax"}:
                    continue
                failed += 1
                text = " ".join(hint.title + " " + hint.detail for hint in result.hints).lower()
                self.assertTrue(
                    result.hints,
                    f"{problem.id} {mutant.kind} produced no hints",
                )
                if "pairs" not in problem.tags and "triples" not in problem.tags:
                    for word in PAIR_GARBAGE:
                        self.assertNotIn(
                            word,
                            text,
                            f"{problem.id} {mutant.kind} invented pair talk: {text}",
                        )
                generic_only = all(
                    any(token in (hint.title + hint.detail).lower() for token in GENERIC)
                    for hint in result.hints
                )
                self.assertFalse(
                    generic_only,
                    f"{problem.id} {mutant.kind} only said the answer differs",
                )
                covered += 1
        self.assertGreaterEqual(generated, 200)
        self.assertGreaterEqual(failed, 150)
        self.assertEqual(covered, failed)


if __name__ == "__main__":
    unittest.main()
