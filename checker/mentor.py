from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable
from pathlib import Path

from checker.llm import complete as llm_complete
from checker.mentor_topics import pack_notes, topic_guide
from checker.models import GradeResult, Problem
from checker.observability import bump

_SLOT = threading.BoundedSemaphore(1)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_FENCE = re.compile(r"```.*?```", re.DOTALL)

_SYSTEM = """Ты учитель информатики. Это единственное сообщение: старого чата нет, смотри только на код ниже.
Найди одно расхождение между условием и этим кодом.
- fixable: путь верный, в одной строке не тот кусок.
- dead_end: программа про другую задачу, а не про условие.

Как искать, по порядку:
1. Команды из условия. «прибавь N» в коде пишется +N, «умножь на N» пишется *N. Если число другое, look — чужое число, instead — число из условия. Если команды нет совсем, look — сумма вызовов f(...), instead — та же сумма плюс недостающий f(x+N) или f(x*N). Это fixable, не dead_end.
2. Вызов. Если считают пути от числа A к числу B, вызов должен быть f(A). Если в print(f(...)) стоит не A, look — это число в вызове, instead — A.
3. Граница отрезка [L; R] и фраза «от A до B включительно» — это range(A, B + 1). Если правый конец range равен B, а не B + 1, look — этот конец, instead — число на 1 больше. Это раньше любой другой строки.
4. Файл и таблица. Если в коде есть input(), а данные в файле, это первая и единственная правка: look — input(), instead — open('имя-файла').read().strip(). Цикл не пиши. split(',') меняют на split(';'), не на split().
5. Если программа про эту задачу, но не хватает куска из правил номера, это fixable. dead_end — только когда код про другую задачу.
6. Иначе укажи знак, имя или вызов, который уже написан в строке.

Запреты:
- look копируй из одной строки кода как есть, без номера строки и без символа |. Не называй символ, которого в этой строке нет.
- Запрещена замена, которая отличается только пробелами. `x < 18 :` и `x < 18:` — это одно и то же, так не отвечай.
- instead обязателен для fixable и должен менять смысл куска. Пустой instead запрещён.
- instead — короткая замена этого куска, в кавычках. Не пиши функцию и цикл: ответ с for или while будет выброшен.
- split(',') меняют только на split(';'). Ответ split() запрещён.
- Комментарий через # ничего не меняет. Так не отвечай.
- permutations при разрешённых повторах меняют на слово product. Это fixable, не dead_end.
- Не собирай новую формулу из max, min и имён, которых нет в этой строке. Можно добавить только недостающий вызов f(x+N) или f(x*N) из условия.
- Для dead_end instead оставь пустой строкой.
- Не пиши число, которое программа должна напечатать.
Сначала два коротких предложения ученику: какой кусок кода расходится с условием и почему из-за этого программа не получает верный ответ. Назови слово или число из условия и то, что стоит в коде. Не пиши «связка условий», «из одной точки» и «не те числа»: ученик должен понять, почему менять надо именно на кусок из условия. Не называй число, которое надо напечатать. Не пиши новую программу.
Потом с новой строки один JSON. В поле why повтори те же предложения.
В условии прибавляют 1, а в коде 23. Шаг уходит не к тому числу, поэтому путей получается не столько, сколько просят.
{"path":"fixable","line":2,"look":"23","instead":"1","why":"В условии прибавляют 1, а в коде 23. Шаг уходит не к тому числу, поэтому путей получается не столько, сколько просят."}"""


def _use_fix(
    result: GradeResult,
    path: str,
    line: int,
    look: str,
    instead: str,
    reason: str,
) -> GradeResult:
    note = _hint(path, line, look, instead)
    secrets = result._hidden_secrets()
    result.explanation.mentor = GradeResult._scrub(note, secrets)
    result.explanation.mentor_reason = GradeResult._scrub(reason, secrets)
    result.explanation.mentor_path = path
    result.explanation.line = line
    bump("mentor_ok")
    return result


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
    missing = _missing_return(source)
    if missing is not None:
        path, line, look, instead = missing
        note = _hint(path, line, look, instead)
        result.explanation.mentor = GradeResult._scrub(note, result._hidden_secrets())
        result.explanation.mentor_reason = (
            "Сумма вызовов посчитана, но не возвращается. "
            "Без return функция доходит до return 0, поэтому число программ получается 0."
        )
        result.explanation.mentor_path = path
        result.explanation.line = line
        bump("mentor_ok")
        return result
    numbered = _number_fix(problem, source)
    if numbered is not None:
        return _use_fix(result, *numbered)
    if complete is None and not get_config().llm_url:
        return result
    if not _SLOT.acquire(timeout=25):
        bump("mentor_busy")
        return result
    try:
        ask = complete or llm_complete
        messages = build_messages(problem, result, source)
        text = ask(messages)
        raw = parse_mentor(text or "")
        parsed = _accepted(raw, source)
        if parsed is None:
            messages[-1] = {
                "role": "user",
                "content": messages[-1]["content"] + "\n\n" + _retry_note(raw, source, text or ""),
            }
            text = ask(messages)
            parsed = _accepted(parse_mentor(text or ""), source)
        if parsed is None:
            bump("mentor_fail")
            return result
        path, line, look, instead = parsed
        line = _place(source, line, look)
        if line is None:
            bump("mentor_fail")
            return result
        note = _hint(path, line, look, instead)
        secrets = result._hidden_secrets()
        note = GradeResult._scrub(note, secrets)
        if len(note.strip()) < 20:
            bump("mentor_fail")
            return result
        result.explanation.mentor = note
        reason = _goal_reason(problem, source, line, look, instead) or mentor_reason(text or "")
        if _canned_reason(reason):
            reason = _plain_number_reason(problem, look, instead) or reason
        result.explanation.mentor_reason = GradeResult._scrub(reason, secrets)
        result.explanation.mentor_path = path
        if line is not None:
            result.explanation.line = line
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
        f"Ввод: {_clip(_input_format(problem), 700)}",
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
    guide = topic_guide(problem)
    if guide:
        parts.append(guide)
    numbered = "\n".join(f"{index}| {line}" for index, line in enumerate(source.splitlines(), start=1))
    parts.append("Код ученика, номер строки стоит перед чертой:\n" + _clip(numbered, 6000))
    opened = _reads_input_but_file(problem, source)
    if opened:
        parts.append(opened)
    noted = _code_notes(problem, source)
    if noted:
        parts.append(noted)
    return [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": "\n\n".join(part for part in parts if part)},
    ]


def parse_mentor(text: str) -> tuple[str, int | None, str, str] | None:
    payload = _payload(text)
    if payload is None:
        return None
    path = payload.get("path")
    if path not in {"fixable", "dead_end"}:
        return None
    line = _line_number(payload.get("line"))
    look = _piece(payload.get("look"), replacement=False)
    instead = _piece(payload.get("instead"), replacement=True, sibling=look or "") if path == "fixable" else ""
    if look is None:
        return None
    return path, line, look, instead or ""


def mentor_reason(text: str) -> str:
    """The pupil-facing explanation: the why field, or the sentences before the JSON."""
    payload = _payload(text)
    reason = ""
    if payload is not None and isinstance(payload.get("why"), str):
        reason = payload["why"]
    if len(" ".join(reason.split())) < 20:
        cleaned = _THINK.sub("", text or "").strip()
        start = cleaned.find("{")
        reason = cleaned[:start] if start >= 0 else ""
    reason = _FENCE.sub(" ", reason)
    reason = " ".join(reason.split())
    if len(reason) < 20:
        return ""
    if len(reason) > 700:
        reason = reason[:699].rstrip() + "…"
    return reason


def _payload(text: str) -> dict | None:
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
    return payload


_ARROW = re.compile(r"(\d+)\s*(?:→|->)\s*(\d+)")
_TRANSFORM = re.compile(r"число\s+(\d+)\s+преобразу\w*\s+в\s+число\s+(\d+)", re.IGNORECASE)
_PRINT_CALL = re.compile(r"print\s*\(\s*f\s*\(\s*(\d+)\s*\)\s*\)")
_ADD_COMMAND = re.compile(r"прибав\w*\s+(\d+)", re.IGNORECASE)
_MUL_COMMAND = re.compile(r"умнож\w*\s+на\s+(\d+)", re.IGNORECASE)
_ADDED = re.compile(r"\+\s*(\d+)")
_MULTIPLIED = re.compile(r"\*\s*(\d+)")


def _start_call(problem: Problem, source: str) -> tuple[str, int, str, str] | None:
    found = _ARROW.search(problem.title) or _TRANSFORM.search(problem.statement)
    if found is None:
        found = _ARROW.search(problem.statement) or _TRANSFORM.search(problem.title)
    if found is None:
        return None
    start = found.group(1)
    for index, row in enumerate(source.splitlines(), start=1):
        match = _PRINT_CALL.search(row)
        if match is None or match.group(1) == start:
            continue
        return "fixable", index, match.group(1), start
    return None


def _command_mismatch(problem: Problem, source: str) -> tuple[str, int, str, str, str] | None:
    """One command number is missing and one foreign number stands in its place."""
    if "ege23" not in problem.tags:
        return None
    pairs = (
        (set(_ADD_COMMAND.findall(problem.statement)), _ADDED, "прибавляют"),
        (set(_MUL_COMMAND.findall(problem.statement)), _MULTIPLIED, "умножают на"),
    )
    rows = source.splitlines()
    for expected, pattern, verb in pairs:
        if not expected:
            continue
        present = {match.group(1) for row in rows if "f(" in row for match in pattern.finditer(row)}
        missing = expected - present
        extra = present - expected
        if len(missing) != 1 or len(extra) != 1:
            continue
        written = next(iter(extra))
        wanted = next(iter(missing))
        for index, row in enumerate(rows, start=1):
            if "f(" not in row or not pattern.search(row):
                continue
            if not any(match.group(1) == written for match in pattern.finditer(row)):
                continue
            reason = (
                f"В условии {verb} {wanted}, а в коде стоит {written}. "
                f"Менять надо на {wanted}, потому что {wanted} написано в условии."
            )
            return "fixable", index, written, wanted, reason
    return None


def _lone_number(text: str) -> str:
    nums = re.findall(r"\d+", text or "")
    if len(nums) != 1:
        return ""
    return nums[0]


def _finish(problem: Problem) -> str:
    found = _ARROW.search(problem.title) or _TRANSFORM.search(problem.statement)
    if found is None:
        found = _ARROW.search(problem.statement) or _TRANSFORM.search(problem.title)
    if found is None:
        return ""
    return found.group(2)


_EQ_GOAL = re.compile(r"(?<![=!<>])==(?!=)\s*(\d+)")


def _wrong_goal(problem: Problem, source: str) -> tuple[str, int, str, str] | None:
    """The goal check names a number other than the finish in the statement."""
    if "ege23" not in problem.tags:
        return None
    finish = _finish(problem)
    if not finish:
        return None
    rows = source.splitlines()
    for index, row in enumerate(rows, start=1):
        nxt = rows[index] if index < len(rows) else ""
        if not _returns_one(row, nxt):
            continue
        found = _EQ_GOAL.search(row)
        if found is None or found.group(1) == finish:
            continue
        return "fixable", index, found.group(1), finish
    return None


_BOUND = re.compile(r"(?<![=!<>])(?:<=|>=|<|>)(?!=)\s*(\d+)")
_CANNED = (
    "связка условий",
    "из одной точки",
    "из этой точки",
    "не те числа",
    "не то число",
    "ответ уезжает",
    "ответ другой",
    "не сходится",
)


def _mentioned_numbers(problem: Problem) -> set[str]:
    return set(re.findall(r"\d+", f"{problem.title}\n{problem.statement}"))


def _stray_bound(problem: Problem, source: str) -> tuple[str, int, str, str, str] | None:
    """A comparison uses a number that the statement never mentions."""
    if "ege23" not in problem.tags:
        return None
    finish = _finish(problem)
    if not finish:
        return None
    known = _mentioned_numbers(problem)
    for index, row in enumerate(source.splitlines(), start=1):
        if "if " not in row:
            continue
        found = _BOUND.search(row)
        if found is None:
            continue
        written = found.group(1)
        if written in known or written in {"0", finish}:
            continue
        reason = (
            f"В условии граница — число {finish}, а в коде стоит {written}. "
            f"Менять надо на {finish}, потому что {finish} написано в условии."
        )
        return "fixable", index, written, finish, reason
    return None


def _number_fix(problem: Problem, source: str) -> tuple[str, int, str, str, str] | None:
    """A number in the code is not the number written for that role in the statement."""
    goal = _wrong_goal(problem, source)
    if goal is not None:
        path, line, look, instead = goal
        reason = _goal_reason(problem, source, line, look, instead)
        if reason:
            return path, line, look, instead, reason
    if "ege23" in problem.tags:
        started = _start_call(problem, source)
        if started is not None:
            _path, line, look, instead = started
            reason = (
                f"В условии считают пути от числа {instead}, а в коде вызывают f({look}). "
                f"Менять надо на {instead}, потому что {instead} написано в условии."
            )
            return "fixable", line, look, instead, reason
    command = _command_mismatch(problem, source)
    if command is not None:
        return command
    return _stray_bound(problem, source)


def _canned_reason(text: str) -> bool:
    lowered = (text or "").lower()
    return any(phrase in lowered for phrase in _CANNED)


def _plain_number_reason(problem: Problem, look: str, instead: str) -> str:
    written = _lone_number(look)
    wanted = _lone_number(instead)
    if not written or not wanted or written == wanted:
        return ""
    if wanted not in _mentioned_numbers(problem):
        return ""
    return (
        f"В условии написано число {wanted}, а в коде стоит {written}. "
        f"Менять надо на {wanted}, потому что {wanted} написано в условии."
    )


def _returns_one(row: str, nxt: str) -> bool:
    if re.search(r"\breturn\s+1\b", row):
        return True
    return bool(row.rstrip().endswith(":") and re.fullmatch(r"\s*return\s+1\s*", nxt or ""))


def _goal_reason(problem: Problem, source: str, line: int | None, look: str, instead: str) -> str:
    """Plain reason when the goal check uses a number other than the finish in the statement."""
    finish = _finish(problem)
    written = _lone_number(look)
    wanted = _lone_number(instead)
    if not finish or not written or wanted != finish or written == finish or line is None:
        return ""
    rows = source.splitlines()
    if not 1 <= line <= len(rows):
        return ""
    row = rows[line - 1]
    if re.search(rf"(?<!\d){re.escape(written)}(?!\d)", row) is None:
        return ""
    if re.search(r"(?<![=!<>])==(?!=)", row) is None:
        return ""
    nxt = rows[line] if line < len(rows) else ""
    if not _returns_one(row, nxt):
        return ""
    return (
        f"В условии нужно получить число {finish}, а в коде проверка стоит на {written}. "
        f"Менять надо на {finish}, потому что {finish} написано в условии."
    )


def _same_fragment(left: str, right: str) -> bool:
    return re.sub(r"\s+", "", left) == re.sub(r"\s+", "", right)


_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_STRINGS = re.compile(r"(\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*')")
_ALLOWED = {
    "open", "read", "strip", "split", "int", "abs", "range", "len", "sum", "max", "min",
    "sorted", "print", "not", "and", "or", "if", "return", "in", "is", "none", "true",
    "false", "map", "list", "tuple", "set", "dict", "enumerate", "zip", "any", "all",
    "append", "counter", "input", "float", "str", "bool", "pow", "round", "join",
}


def _names(text: str) -> set[str]:
    # The f before a quote is an f-string marker, not a variable name.
    stripped = re.sub(r"\bf(?=['\"])", "", text)
    return set(_NAME.findall(_STRINGS.sub(" ", stripped)))


def _unknown_names(instead: str, source: str) -> bool:
    known = _names(source)
    return any(name not in known and name.lower() not in _ALLOWED for name in _names(instead))


def _input_format(problem: Problem) -> str:
    text = problem.input_format or ""
    _name, sample = _file_sample(problem)
    first = sample.splitlines()[0] if sample else ""
    if ";" in first and "пробел" in text:
        text = text.replace("через пробелы или табуляцию", "через точку с запятой")
        text = text.replace(".split()", ".split(';')")
        text += " Фраза про пробелы была ошибкой описания: в файле разделитель — точка с запятой."
    return text


def _file_sample(problem: Problem) -> tuple[str, str]:
    if not problem.files:
        return "", ""
    name = problem.files[0].rsplit("/", 1)[-1]
    path = Path(__file__).resolve().parent.parent / "data" / problem.files[0]
    if not path.is_file():
        return name, ""
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return name, handle.read(240)


def _reads_input_but_file(problem: Problem, source: str) -> str:
    if "input(" not in source or not problem.files:
        return ""
    name, _sample = _file_sample(problem)
    if not name:
        return ""
    opener = f"open('{name}')" if "ege17" in problem.tags else f"open('{name}').read().strip()"
    return (
        f"Ученик написал input(), а данные лежат в файле {name}. "
        f"Это fixable: look — input(), instead — {opener}. Одного имени файла в кавычках мало."
    )


def _code_notes(problem: Problem, source: str) -> str:
    notes: list[str] = []
    tags = set(problem.tags)
    if "ege8" in tags and re.search(r"product\([^)]*0", source) and not re.search(r"\[0\]\s*!=", source):
        notes.append(
            "В алфавите есть 0, а первой цифры не проверяют. "
            "look — условие отбора, instead — то же условие и word[0] != '0'. Символ # запрещён."
        )
    if "ответ" in source:
        notes.append("В print есть слово «ответ». look — ответ, instead — печать только четырёх букв, без этого слова.")
    if "ege14" in tags and "включительно" in problem.statement and "range(" in source:
        notes.append(
            "Верх в условии включительный. Если range обрывается ровно на этом числе, "
            "look — правый конец range, instead — число на 1 больше. Другие строки не меняй."
        )
    if "ege16" in tags and "n % 2" in source:
        notes.append(
            "Если чётная и нечётная формулы перепутаны, меняй всю правую часть ветки на формулу этого случая. "
            "Не заменяй только n - 2 на n - 1."
        )
    if "ege16" in tags and re.search(r"f\(\s*n\s*-\s*1\s*\)", source) and re.search(r"F\(\s*n\s*\+\s*1\s*\)", problem.statement):
        notes.append(
            "Первая правка — направление вызова, не база. "
            "look ровно f(n - 1), instead ровно f(n + 1). Ветку if n == 1 в этом ответе не меняй."
        )
    if "ege17" in tags and "combinations" in source:
        notes.append(
            "combinations — все пары, а нужны соседи. "
            "look — combinations(data, 2), instead — zip(data, data[1:]). Строку import не меняй."
        )
    if "ege17" in tags and "не дел" in problem.statement.lower():
        notes.append("«Не делится» — остаток != 0. Несколько таких проверок соединяют and. instead с == 0 для этих делителей неверен.")
    if tags & {"ege19", "ege20", "ege21"} and "return 1" in source and ">=" in source:
        notes.append("Под концом игры return 1. look — return 1, instead — return 0. Строку if не переписывай.")
    if tags & {"ege19", "ege20", "ege21"} and "+ 1" in source and "прибавить 2" in problem.statement:
        notes.append("В условии прибавляют 2, в коде есть + 1. look — + 1, instead — + 2. Формулу с max не трогай.")
    if tags & {"ege19", "ege20", "ege21"} and ("any(" in source or "all(" in source):
        notes.append("Квантор — одно слово. look — any или all, instead — другое слово. Строку с for не копируй.")
    if "ege19" in tags and "max(" in source and "минимальн" in problem.statement.lower():
        notes.append("В №19 нужен минимум. look — max, instead — min.")
    if "ege24" in tags and ".count(" in source:
        notes.append("count — не длина подряд. look — count, instead — длину подряд. Цикл в instead запрещён.")
    if "ege25" in tags and "10 ** 9" in source:
        notes.append("Миллиардный range меняют на range(10) по каждой цифре ?. Не подставляй одно число.")
    if "ege25" in tags and "== '5'" in source:
        notes.append("Цифру ? нельзя прибивать к 5. look — == '5', instead — True.")
    if "ege18" in tags:
        notes.append("Клетку чинят в присваивании, не в print. Старт — значение * 2. Вправо и вверх без * 2, диагональ с * 2.")
    if "ege2" in tags and ">=" in source:
        notes.append(
            "Сравнение >= слишком слабое для разных строк фрагмента. "
            "look — только `>= 1`, instead — `== 3`, если строк фрагмента три. Строку с for не копируй."
        )
    extra = pack_notes(problem, source)
    if extra:
        notes.append(extra)
    return "\n".join(notes)


def _retry_note(parsed: tuple[str, int | None, str, str] | None, source: str, raw_text: str = "") -> str:
    if parsed is None and ".count(" in source and re.search(r"\bfor\b", raw_text or ""):
        return "Цикл в instead выброшен. look — count, instead — длину подряд. Без for."
    if parsed is None and re.search(r"\b(for|while)\b", raw_text or ""):
        return (
            "Строка с for в instead выброшена. look и instead — короткие куски без for и без #. "
            "Если в print есть «ответ», убери это слово. Если написано >= 1, instead — == числу строк фрагмента."
        )
    if parsed is not None:
        path, _line, look, instead = parsed
        if path == "fixable" and _bad_split(look, instead):
            return "Прошлая замена неверная: split(',') меняют на split(';'). Ответ split() запрещён."
        if path == "fixable" and instead and _unknown_names(instead, source):
            return "Прошлая замена подставила имя, которого нет в коде. Так нельзя. Замени input() на open('имя-файла').read().strip(), если данные в файле."
        if path == "fixable" and "n == 1" in look and "2024" in instead and "f(n - 1)" in source:
            return "Базу не трогай. look — f(n - 1), instead — f(n + 1)."
        if path == "fixable" and _bare_filename(instead):
            return "Имени файла мало. instead — open('имя-файла'), look — input()."
        if path == "fixable" and _comment_only(look, instead):
            return "Комментарий программу не меняет. Найди проверку или слово: ведущий ноль это s[0] != '0', permutations меняют на product, подпись в print убирают."
        if path == "fixable" and (not instead.strip() or _same_fragment(look, instead)):
            if ".count(" in source and re.search(r"\bfor\b", raw_text or ""):
                return "Цикл в instead выброшен. look — count, instead — длину подряд. Без for."
            if re.search(r"\b(for|import)\b", raw_text or ""):
                return (
                    "Цикл и import в instead выброшены. "
                    "input() меняют на open('имя-файла'). "
                    "combinations(data, 2) меняют на zip(data, data[1:]). "
                    "look — короткий кусок одной строки, без номера."
                )
            return "Прошлая замена пустая или отличается только пробелами. Найди другой знак, число или вызов."
    return "Прошлый ответ не подошёл. look скопируй из строки, instead — короткая замена этого куска."


_CALL_SUM = re.compile(
    r"([A-Za-z_]\w*\([^()\n]*\)(?:\s*\+\s*[A-Za-z_]\w*\([^()\n]*\))+)"
)


def _missing_return(source: str) -> tuple[str, int, str, str] | None:
    """A recursive sum that is computed and then thrown away."""
    for index, row in enumerate(source.splitlines(), start=1):
        match = _CALL_SUM.search(row)
        if match is None:
            continue
        expr = match.group(1).strip()
        before = row[: match.start()]
        if re.search(r"\b(?:return|def|lambda)\b", before):
            continue
        if re.search(r"(?:=|print\s*\()\s*$", before):
            continue
        return "fixable", index, expr, "return " + expr
    return None


def _comment_only(look: str, instead: str) -> bool:
    def bare(text: str) -> str:
        return re.sub(r"\s+", "", re.sub(r"#.*", "", text))

    return "#" in instead and bare(look) == bare(instead)


def _bare_filename(instead: str) -> bool:
    compact = re.sub(r"\s+", "", instead)
    return re.fullmatch(r"['\"][^'\"]+\.(?:txt|csv)['\"]", compact) is not None


def _bad_split(look: str, instead: str) -> bool:
    compact_look = re.sub(r"\s+", "", look)
    return "split(',')" in compact_look and ";" not in instead


def _accepted(parsed: tuple[str, int | None, str, str] | None, source: str) -> tuple[str, int | None, str, str] | None:
    if parsed is None:
        return None
    path, line, look, instead = parsed
    if path == "dead_end" and "a + b >=" in source and "return 1" in source:
        for index, row in enumerate(source.splitlines(), start=1):
            if "return 1" in row:
                return "fixable", index, "return 1", "return 0"
    if path == "fixable" and ".count(" in look and not instead.strip():
        return "fixable", line, "count", "длину подряд"
    if path == "fixable" and "combinations" in look and (not instead.strip() or "import " in instead.lower()):
        neighbor = _neighbor_call(source)
        if neighbor is not None:
            return neighbor
    if path == "fixable" and (
        not instead.strip()
        or _same_fragment(look, instead)
        or _bad_split(look, instead)
        or _comment_only(look, instead)
        or _bare_filename(instead)
        or ("n == 1" in look and "2024" in instead and "f(n - 1)" in source)
        or _unknown_names(instead, source)
    ):
        return None
    if _place(source, line, look) is None:
        return None
    return parsed


def _place(source: str, line: int | None, look: str) -> int | None:
    rows = source.splitlines()
    if line is not None and 1 <= line <= len(rows) and look in rows[line - 1]:
        return line
    hits = [index for index, row in enumerate(rows, start=1) if look in row]
    if len(hits) == 1:
        return hits[0]
    return None


def _line_number(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 1:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
        return number if number >= 1 else None
    return None


def _neighbor_call(source: str) -> tuple[str, int, str, str] | None:
    for index, row in enumerate(source.splitlines(), start=1):
        if "import" in row or "combinations(" not in row:
            continue
        start = row.find("combinations(")
        depth = 0
        for offset, char in enumerate(row[start:], start=start):
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return "fixable", index, row[start : offset + 1], "zip(data, data[1:])"
    return None


def _piece(value: object, *, replacement: bool, sibling: str = "") -> str | None:
    if value is None and not replacement:
        return None
    if not isinstance(value, str):
        return None
    text = _FENCE.sub(" ", value)
    text = text.replace("\\n", "\n").split("\n", 1)[0]
    text = re.split(r"\s+\d+\s*\|", text, maxsplit=1)[0]
    text = " ".join(text.split())
    if not text or len(text) > 120:
        return None
    lowered = text.lower()
    # A replacement must stay a fragment. A for that is already in the pointed-at
    # line is the student's own comprehension, not a new loop.
    banned = ("def ", "lambda ")
    if replacement:
        sibling_lower = sibling.lower()
        banned = banned + ("import ",)
        if "for " in lowered and "for " not in sibling_lower:
            return None
        if "while " in lowered and "while " not in sibling_lower:
            return None
    if any(word in lowered for word in banned):
        return None
    return text


def _hint(path: str, line: int | None, look: str, instead: str) -> str:
    where = f"Строка {line}. " if line else ""
    if path == "dead_end":
        return f"{where}Смотри на `{look}`. Этот путь не довести правкой, готовый код я не пишу."
    change = f" Поменяй это на `{instead}`." if instead else ""
    return f"{where}Смотри на `{look}`.{change}"


def _clip(text: str, limit: int) -> str:
    raw = (text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 1].rstrip() + "…"
