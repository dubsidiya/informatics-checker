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


def _problem(item: dict, old: dict | None) -> dict:
    files = list(item.get("files") or [])
    stdout = item["stdout"]
    test: dict = {"stdin": "", "stdout": stdout, "hidden": False}
    if files:
        test["file"] = files[0]
    tests = [test]
    examples = [{"stdin": "", "stdout": stdout}]
    if old:
        if len(old.get("tests") or []) > 1:
            tests = old["tests"]
        if old.get("examples"):
            examples = old["examples"]
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
    (DATA / "problems.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("wrote", len(out), "problems", "school", len(school), "ege", len(ege))


if __name__ == "__main__":
    main()
