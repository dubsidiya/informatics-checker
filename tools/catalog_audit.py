#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quality gate for the problem catalog.

This intentionally checks facts that can be verified locally. It does not
claim that a problem came from a particular exam year without source data.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "problems.json"

REQUIRED = {"id", "title", "level", "topic", "statement", "input_format", "output_format", "tests"}
LEVELS = {"\u0441\u0442\u0430\u0440\u0442", "\u0441\u0440\u0435\u0434\u043d\u0435", "\u0441\u043b\u043e\u0436\u043d\u043e"}
EGE_MIN = 30
EGE_MAX = 40


def main() -> int:
    try:
        problems = json.loads(DATA.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"catalog: cannot read JSON: {exc}")
        return 1

    errors: list[str] = []
    ids: set[str] = set()
    topics: dict[str, list[dict]] = defaultdict(list)

    if not isinstance(problems, list):
        errors.append("root must be a list")
        problems = []

    for index, item in enumerate(problems, 1):
        label = f"item #{index}"
        if not isinstance(item, dict):
            errors.append(f"{label}: must be an object")
            continue
        missing = REQUIRED - item.keys()
        if missing:
            errors.append(f"{label}: missing {', '.join(sorted(missing))}")
        problem_id = str(item.get("id", ""))
        if not problem_id:
            errors.append(f"{label}: empty id")
        elif problem_id in ids:
            errors.append(f"{label}: duplicate id {problem_id}")
        ids.add(problem_id)
        topic = str(item.get("topic", ""))
        topics[topic].append(item)
        if item.get("level") not in LEVELS:
            errors.append(f"{problem_id}: invalid level {item.get('level')!r}")
        tests = item.get("tests")
        if not isinstance(tests, list) or not tests:
            errors.append(f"{problem_id}: no tests")
        elif not any(case.get("hidden") for case in tests if isinstance(case, dict)):
            errors.append(f"{problem_id}: no hidden test")
        files = item.get("files") or []
        for relative in files:
            path = ROOT / "data" / str(relative)
            if not path.is_file():
                errors.append(f"{problem_id}: missing file {relative}")

    print(f"catalog: {len(problems)} problems, {len(topics)} topics")
    for topic, items in sorted(topics.items()):
        marker = ""
        if topic.startswith("\u0415\u0413\u042d ") and not (EGE_MIN <= len(items) <= EGE_MAX):
            marker = f"  [target {EGE_MIN}-{EGE_MAX}]"
        print(f"  {topic}: {len(items)}{marker}")

    if errors:
        print(f"catalog: {len(errors)} quality errors")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("catalog: quality gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
