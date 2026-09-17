from __future__ import annotations

import re
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
class Explanation:
    headline: str
    what: str
    why: str
    how: str
    line: int | None = None
    kind: str = "logic"


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
    explanation: Explanation | None = None
    tries: int = 1

    def to_dict(self, *, reveal_hidden: bool = False) -> dict[str, Any]:
        tests = []
        for item in self.tests:
            payload = asdict(item)
            if item.hidden and not reveal_hidden:
                payload["stdin"] = ""
                payload["expected"] = ""
                payload["got"] = ""
                if item.verdict != "OK":
                    payload["error"] = item.error_type or "скрытый тест не пройден"
            tests.append(payload)
        hints = [asdict(item) for item in self.hints]
        explain = asdict(self.explanation) if self.explanation else None
        if not reveal_hidden:
            secrets = self._hidden_secrets()
            for hint in hints:
                hint["title"] = self._scrub(hint.get("title", ""), secrets)
                hint["detail"] = self._scrub(hint.get("detail", ""), secrets)
            if explain:
                for key in ("headline", "what", "why", "how"):
                    explain[key] = self._scrub(explain.get(key, ""), secrets)
        return {
            "status": self.status,
            "message": self.message,
            "passed": self.passed,
            "total": self.total,
            "syntax": asdict(self.syntax) if self.syntax else None,
            "tests": tests,
            "hints": hints,
            "explanation": explain,
            "trace": [asdict(item) for item in self.trace] if not self._first_fail_is_hidden() or reveal_hidden else [],
            "first_fail_index": self.first_fail_index,
            "tries": self.tries,
        }

    def _first_fail_is_hidden(self) -> bool:
        if self.first_fail_index is None:
            return False
        for item in self.tests:
            if item.index == self.first_fail_index:
                return item.hidden
        return False

    def _hidden_secrets(self) -> list[str]:
        found: list[str] = []
        for item in self.tests:
            if not item.hidden:
                continue
            found.extend(self._secret_pieces(item.expected))
        uniq: list[str] = []
        seen: set[str] = set()
        for secret in sorted(found, key=len, reverse=True):
            if secret not in seen:
                seen.add(secret)
                uniq.append(secret)
        return uniq

    @staticmethod
    def _secret_pieces(text: str) -> list[str]:
        raw = (text or "").strip()
        if not raw:
            return []
        pieces: list[str] = []
        if raw:
            pieces.append(f"`{raw}`")
        if len(raw) >= 2:
            pieces.append(raw)
        compact = " ".join(raw.split())
        if compact != raw and len(compact) >= 2:
            pieces.append(compact)
        for token in re.split(r"[\s,;]+", raw):
            bare = token.lstrip("-")
            if len(token) >= 4 or "." in token:
                pieces.append(token)
            elif bare.isdigit() and len(bare) >= 3:
                pieces.append(token)
        return pieces

    @staticmethod
    def _scrub(text: str, secrets: list[str]) -> str:
        out = text or ""
        for secret in secrets:
            out = out.replace(secret, "скрытый ответ")
        return out
