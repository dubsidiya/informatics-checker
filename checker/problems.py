from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from checker.models import Example, Problem, TestCase

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "problems.json"


def _load_problem(raw: dict) -> Problem:
    return Problem(
        id=raw["id"],
        title=raw["title"],
        level=raw["level"],
        topic=raw.get("topic", "общее"),
        statement=raw["statement"],
        input_format=raw["input_format"],
        output_format=raw["output_format"],
        tags=list(raw.get("tags", [])),
        examples=[Example(**item) for item in raw.get("examples", [])],
        tests=[TestCase(**item) for item in raw.get("tests", [])],
        files=list(raw.get("files", [])),
    )


@lru_cache(maxsize=1)
def all_problems() -> list[Problem]:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return [_load_problem(item) for item in payload]


def list_summaries() -> list[dict]:
    return [
        {
            "id": problem.id,
            "title": problem.title,
            "level": problem.level,
            "topic": problem.topic,
        }
        for problem in all_problems()
    ]


def list_topics() -> list[str]:
    seen: list[str] = []
    for problem in all_problems():
        if problem.topic not in seen:
            seen.append(problem.topic)
    return seen


def get_problem(problem_id: str) -> Problem:
    for problem in all_problems():
        if problem.id == problem_id:
            return problem
    raise KeyError(problem_id)
