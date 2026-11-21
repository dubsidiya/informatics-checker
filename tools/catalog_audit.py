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
SOLUTION_MANIFEST = ROOT / "data" / "solution_manifest.json"

REQUIRED = {
    "id", "title", "level", "topic", "statement", "input_format",
    "output_format", "tests", "provenance", "author_created",
    "mistake_hints", "fast_path",
}
LEVELS = {"\u0441\u0442\u0430\u0440\u0442", "\u0441\u0440\u0435\u0434\u043d\u0435", "\u0441\u043b\u043e\u0436\u043d\u043e"}
TOPIC_MIN = 40
# Реальные задачи Полякова, а не 40 копий одной тренировки: №2, №7, №11, №15.
TOPIC_MIN_FOR = {"ЕГЭ 2": 13, "ЕГЭ 15": 10, "ЕГЭ 11": 12, "ЕГЭ 7": 11}
# Hand-built topics that are not a full exam set yet. They stay in the
# catalog for practice, but they are not held to the 30–40 harvest bar.
EGE_DRAFTS = set()


def main() -> int:
    try:
        problems = json.loads(DATA.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"catalog: cannot read JSON: {exc}")
        return 1

    try:
        raw_solutions = json.loads(SOLUTION_MANIFEST.read_text(encoding="utf-8"))
        manifest = {
            str(item.get("id")): str(item.get("source"))
            for item in raw_solutions
            if isinstance(item, dict) and item.get("id") and isinstance(item.get("source"), str)
        }
    except Exception as exc:
        print(f"catalog: cannot read solution manifest: {exc}")
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
        if problem_id not in manifest or not manifest[problem_id].strip():
            errors.append(f"{problem_id}: missing server-side reference solution")
        topic = str(item.get("topic", ""))
        topics[topic].append(item)
        if item.get("level") not in LEVELS:
            errors.append(f"{problem_id}: invalid level {item.get('level')!r}")
        if not str(item.get("provenance", "")).strip():
            errors.append(f"{problem_id}: missing provenance")
        if not isinstance(item.get("author_created"), bool):
            errors.append(f"{problem_id}: author_created must be boolean")
        mistake_map = item.get("mistake_hints")
        if not isinstance(mistake_map, list) or len(mistake_map) < 2:
            errors.append(f"{problem_id}: need at least two mistake hints")
        else:
            for hint in mistake_map:
                if not isinstance(hint, dict) or not hint.get("title") or not hint.get("detail"):
                    errors.append(f"{problem_id}: malformed mistake hint")
        if not str(item.get("fast_path", "")).strip():
            errors.append(f"{problem_id}: missing fast_path")
        if item.get("author_created") and str(item.get("topic", "")).startswith("ЕГЭ "):
            if not str(item.get("archive_ref", "")).strip():
                errors.append(f"{problem_id}: missing archive_ref")
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
    if len(manifest) != len(ids) or set(manifest) != ids:
        errors.append("solution manifest IDs do not exactly match catalog IDs")
    for topic, items in sorted(topics.items()):
        marker = ""
        if topic in EGE_DRAFTS:
            marker = "  [draft]"
        minimum = TOPIC_MIN_FOR.get(topic, TOPIC_MIN)
        if len(items) < minimum:
            errors.append(f"{topic}: {len(items)} problems, minimum is {minimum}")
        author_items = [item for item in items if item.get("author_created")]
        if author_items and topic in {"ЕГЭ 2", "ЕГЭ 15", "ЕГЭ 18", "ЕГЭ 19–21", "ЕГЭ 24", "ЕГЭ 26", "ЕГЭ 27"}:
            focus_count = len({(item.get("mistake_hints") or [{}])[0].get("title", "") for item in author_items})
            fast_count = len({item.get("fast_path", "") for item in author_items})
            if focus_count < 4:
                errors.append(f"{topic}: author mistake focus is too repetitive ({focus_count})")
            if fast_count < 4:
                errors.append(f"{topic}: author fast paths are too repetitive ({fast_count})")
        for item in items:
            if item.get("author_created") and len(item.get("tests") or []) < 3:
                errors.append(f"{item.get('id')}: author task needs at least 3 tests")
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
