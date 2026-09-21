#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from checker.safety import find_forbidden

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
HARVEST_NAMES = [
    "harvest_8.json",
    "harvest_9.json",
    "harvest_13.json",
    "harvest_14.json",
    "harvest_16.json",
    "harvest_17.json",
    "harvest_23.json",
    "harvest_25.json",
]
TOPIC = {n: "\u0415\u0413\u042d %d" % n for n in (8, 9, 13, 14, 16, 17, 23, 25)}


def _tags(item: dict) -> list[str]:
    tags = list(item.get("tags") or [])
    kind = f"ege{item['type']}"
    if kind not in tags:
        tags.insert(0, kind)
    stdout = (item.get("stdout") or "").strip()
    if "\n" in stdout and "multi_line_out" not in tags:
        tags.append("multi_line_out")
    if stdout.replace("-", "").isdigit() and "single_int_out" not in tags:
        tags.append("single_int_out")
    elif len(stdout.split()) == 2 and all(part.lstrip("-").isdigit() for part in stdout.split()):
        if "two_int_out" not in tags:
            tags.append("two_int_out")
    if item.get("files") and "file_input" not in tags:
        tags.append("file_input")
    return tags


def _hide_oracle_examples(examples: list[dict], oracle: str) -> list[dict]:
    clean = []
    oracle_out = (oracle or "").strip()
    for item in examples:
        stdout = str(item.get("stdout") or "").strip()
        if oracle_out and stdout == oracle_out:
            continue
        clean.append(item)
    return clean


def _problem(item: dict, old: dict | None) -> dict:
    files = list(item.get("files") or [])
    stdout = item["stdout"]
    test: dict = {"stdin": "", "stdout": stdout, "hidden": True}
    if files:
        test["file"] = files[0]
    tests = [test]
    examples: list[dict] = []
    if old:
        old_tests = list(old.get("tests") or [])
        if len(old_tests) > 1:
            tests = []
            for case in old_tests:
                row = dict(case)
                same_oracle = str(row.get("stdout") or "").strip() == str(stdout or "").strip()
                oracle_file = files[0] if files else None
                if same_oracle and (not row.get("file") or row.get("file") == oracle_file):
                    row["hidden"] = True
                tests.append(row)
            if not any(case.get("hidden") for case in tests):
                tests[-1]["hidden"] = True
        elif old_tests:
            row = dict(old_tests[0])
            row["hidden"] = True
            if files and not row.get("file"):
                row["file"] = files[0]
            tests = [row]
        examples = _hide_oracle_examples(list(old.get("examples") or []), stdout)
    default_in = "No input." if not files else f"open('{Path(files[0]).name}')"
    return {
        "id": item["id"],
        "title": item["title"],
        "level": item.get("level") or "\u0441\u0440\u0435\u0434\u043d\u0435",
        "topic": TOPIC[item["type"]],
        "tags": _tags(item),
        "statement": item["statement"],
        "input_format": item.get("input_format") or default_in,
        "output_format": item.get("output_format") or "Print the answer from the statement.",
        "files": files,
        "examples": examples,
        "tests": tests,
    }


def main() -> None:
    catalog = json.loads((DATA / "problems.json").read_text(encoding="utf-8"))
    old_ege = {item["id"]: item for item in catalog if str(item["id"]).startswith("ege")}
    school = [item for item in catalog if not str(item["id"]).startswith("ege")]

    harvested: dict[str, dict] = {}
    dropped = []
    for name in HARVEST_NAMES:
        payload = json.loads((DATA / name).read_text(encoding="utf-8"))
        for item in payload:
            allow_open = bool(item.get("files"))
            blocked = find_forbidden(item["source"], allow_open=allow_open)
            if blocked:
                dropped.append((item["id"], blocked.explanation))
                continue
            harvested[item["id"]] = item

    if dropped:
        print("dropped forbidden", dropped)

    ege = [_problem(item, old_ege.get(item["id"])) for item in harvested.values()]
    ege.sort(key=lambda item: (item["topic"], int(item["id"].split("-")[-1])))

    counts: dict[str, int] = {}
    for item in ege:
        counts[item["topic"]] = counts.get(item["topic"], 0) + 1
    print("ege counts", counts)
    short = {topic: n for topic, n in counts.items() if n < 30}
    if short:
        raise SystemExit(f"need 30 per topic, got {short}")

    out = school + ege
    for item in out:
        tests = item.get("tests") or []
        if str(item.get("id", "")).startswith("ege") and len(tests) == 1:
            tests[0]["hidden"] = True
            oracle = str(tests[0].get("stdout") or "").strip()
            item["examples"] = [
                example
                for example in (item.get("examples") or [])
                if str(example.get("stdout") or "").strip() != oracle
            ]
        item["tests"] = tests
    (DATA / "problems.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("wrote", len(out), "problems", "school", len(school), "ege", len(ege))
    from checker.catalog import validate_catalog
    from checker.problems import all_problems

    all_problems.cache_clear()
    errors = validate_catalog()
    if errors:
        raise SystemExit("\n".join(errors[:20]))


if __name__ == "__main__":
    main()
