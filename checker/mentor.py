from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable

from checker.llm import complete as llm_complete
from checker.models import GradeResult, Problem
from checker.observability import bump

_SLOT = threading.BoundedSemaphore(1)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```.*?```", re.DOTALL)

_SYSTEM = """Ты учитель информатики в школе. Ученик написал программу на Python, автотесты её не приняли.
По условию и коду пойми, каким путём он идёт, и выбери одно:
- fixable: путь тот, код можно довести до ответа локальной правкой;
- dead_end: код решает другую задачу, и правкой пары строк его не спасти. Нужен другой способ.

Правила:
- Пиши по-русски, 2–4 коротких предложения, на «ты», без вступления.
- Не пиши готовую программу. Одна короткая строка кода допустима, только чтобы назвать место правки.
- Не называй число или строку, которые программа должна напечатать. Не угадывай скрытый тест.
- Ошибка границы, типа, формата вывода, опечатки в имени, забытый int — это fixable, не dead_end.
- dead_end ставь только когда алгоритм не про эту задачу: другой смысл ответа, не те данные, перебор не того.
- Опирайся только на текст ниже. Не выдумывай входные данные.
Ответ — только JSON без пояснений вокруг: {"path":"fixable","note":"..."} или {"path":"dead_end","note":"..."}"""


def add_mentor(
    problem: Problem,
    result: GradeResult,
    source: str,
    *,
    complete: Callable[[list[dict[str, str]]], str | None] | None = None,
) -> GradeResult:
    """Attach a model hint. A missing model leaves the rule-based explanation as it is."""
    from checker.config import get_config

    if result.status == "ok" or result.explanation is None or not source.strip():
        return result
    if complete is None and not get_config().llm_url:
        return result
    if not _SLOT.acquire(blocking=False):
        bump("mentor_busy")
        return result
    try:
        text = (complete or llm_complete)(build_messages(problem, result, source))
        parsed = parse_mentor(text or "")
        if parsed is None:
            bump("mentor_fail")
            return result
        path, note = parsed
        note = GradeResult._scrub(note, result._hidden_secrets())
        if len(note.strip()) < 20:
            bump("mentor_fail")
            return result
        result.explanation.mentor = note
        result.explanation.mentor_path = path
        bump("mentor_ok")
        return result
    except Exception:
        bump("mentor_fail")
        return result
    finally:
        _SLOT.release()


def build_messages(problem: Problem, result: GradeResult, source: str) -> list[dict[str, str]]:
    parts = [
        f"Задача: {problem.title}",
        _clip(problem.statement, 2500),
        f"Ввод: {_clip(problem.input_format, 500)}",
        f"Вывод: {_clip(problem.output_format, 500)}",
    ]
    for index, example in enumerate(problem.examples[:2], start=1):
        parts.append(
            f"Открытый пример {index}.\nВвод:\n{_clip(example.stdin, 400)}\nВывод:\n{_clip(example.stdout, 400)}"
        )
    parts.append(f"Вердикт проверяльщика: {result.status}. {result.message}")
    first = next((item for item in result.tests if item.verdict != "OK"), None)
    if first is not None and not first.hidden:
        parts.append(
            "\n".join(
                [
                    f"Первый открытый непройденный тест {first.index + 1}, вердикт {first.verdict}.",
                    f"Ввод:\n{_clip(first.stdin, 400)}",
                    f"Ожидалось:\n{_clip(first.expected, 300)}",
                    f"Программа вывела:\n{_clip(first.got, 300)}",
                    f"Ошибка:\n{_clip(first.error, 300)}" if first.error else "",
                ]
            ).strip()
        )
    elif first is not None:
        parts.append(
            f"Первый непройденный тест {first.index + 1} скрытый, вердикт {first.verdict}. "
            "Его данных у тебя нет. Не угадывай, что там должно было получиться."
        )
    if result.syntax is not None:
        where = f" на строке {result.syntax.line}" if result.syntax.line else ""
        parts.append(f"Синтаксис{where}: {_clip(result.syntax.explanation, 400)}")
    if result.explanation is not None and result.explanation.how:
        parts.append(f"Короткий разбор проверяльщика, его можно уточнить, но не противоречь фактам: {_clip(result.explanation.how, 500)}")
    parts.append("Код ученика:\n" + _clip(source, 6000))
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": "\n\n".join(part for part in parts if part)},
    ]


def parse_mentor(text: str) -> tuple[str, str] | None:
    cleaned = _THINK.sub("", text or "").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    path = payload.get("path")
    note = payload.get("note")
    if path not in {"fixable", "dead_end"} or not isinstance(note, str):
        return None
    note = _FENCE.sub(" ", note)
    note = " ".join(note.split())
    if not 20 <= len(note) <= 800:
        return None
    if note.lower().count("def ") > 1 or (note.count(";") > 4 and "print" in note):
        return None
    return path, note


def _clip(text: str, limit: int) -> str:
    raw = (text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 1].rstrip() + "…"
