from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Verdict = Literal["OK", "WA", "RE", "TLE", "SE"]
Status = Literal["ok", "syntax", "fail"]


@dataclass
class Example:
    stdin: str
    stdout: str


@dataclass
class TestCase:
    stdin: str
    stdout: str
    hidden: bool = False
    file: str | None = None


@dataclass
class Problem:
    id: str
    title: str
    level: str
    statement: str
    input_format: str
    output_format: str
    examples: list[Example]
    tests: list[TestCase]
    topic: str = "общее"
    tags: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "level": self.level,
            "topic": self.topic,
            "statement": self.statement,
            "input_format": self.input_format,
            "output_format": self.output_format,
            "tags": self.tags,
            "examples": [asdict(item) for item in self.examples],
            "files": [{"name": item.rsplit("/", 1)[-1]} for item in self.files],
        }

    def files_for(self, case: TestCase) -> list[str]:
        if case.file:
            return [case.file]
        return list(self.files)


@dataclass
class SyntaxIssue:
    line: int | None
    column: int | None
    message: str
    explanation: str
    snippet: str


@dataclass
class Hint:
    kind: Literal["syntax", "format", "logic", "runtime", "style"]
    title: str
    detail: str
    line: int | None = None


@dataclass
class TraceStep:
    line: int
    locals: dict[str, str]


@dataclass
class TestResult:
    index: int
    hidden: bool
    verdict: Verdict
    stdin: str
    expected: str
    got: str
    error: str = ""
    error_type: str = ""
    error_line: int | None = None


@dataclass
class GradeResult:
    status: Status
    message: str
    passed: int
    total: int
    syntax: SyntaxIssue | None = None
    tests: list[TestResult] = field(default_factory=list)
    hints: list[Hint] = field(default_factory=list)
    trace: list[TraceStep] = field(default_factory=list)
    first_fail_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "passed": self.passed,
            "total": self.total,
            "syntax": asdict(self.syntax) if self.syntax else None,
            "tests": [asdict(item) for item in self.tests],
            "hints": [asdict(item) for item in self.hints],
            "trace": [asdict(item) for item in self.trace],
            "first_fail_index": self.first_fail_index,
        }
