#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Append new practice/EGE problems to data/problems.json (idempotent by id).

Reads the list of new problems from tools/new_problems.json and appends any
whose id is not already present, preserving formatting (UTF-8, indent=2).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "problems.json"
SOURCE = ROOT / "tools" / "new_problems.json"


def main() -> None:
    with SOURCE.open(encoding="utf-8") as f:
        new = json.load(f)
    with DATA.open(encoding="utf-8") as f:
        problems = json.load(f)
    existing = {p["id"] for p in problems}
    added = 0
    for item in new:
        if item["id"] in existing:
            continue
        problems.append(item)
        added += 1
    with DATA.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(problems, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Added {added} new problems. Total now: {len(problems)}")


if __name__ == "__main__":
    main()
