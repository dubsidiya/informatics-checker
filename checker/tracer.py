from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

MAX_EVENTS = 80
MAX_VALUE = 80


def _short(value: Any) -> str:
    try:
        text = repr(value)
    except Exception:
        text = type(value).__name__
    if len(text) > MAX_VALUE:
        return text[: MAX_VALUE - 1] + "..."
    return text


def _interesting(name: str, value: Any) -> bool:
    if name.startswith("_"):
        return False
    if callable(value):
        return False
    module = type(value).__module__
    if module == "builtins" and type(value).__name__ in {"module", "function", "type"}:
        return False
    return True


def collect_trace(source: str, source_path: str) -> list[dict]:
    events: list[dict] = []
    compiled = compile(source, source_path, "exec")

    def tracer(frame, event, arg):
        if event != "line":
            return tracer
        if frame.f_code.co_filename != source_path:
            return tracer
        if len(events) >= MAX_EVENTS:
            return None
        local_vars = {
            key: _short(value)
            for key, value in frame.f_locals.items()
            if _interesting(key, value)
        }
        if events and events[-1]["line"] == frame.f_lineno and events[-1]["locals"] == local_vars:
            return tracer
        events.append({"line": frame.f_lineno, "locals": local_vars})
        return tracer

    old_stdout = sys.stdout
    sys.settrace(tracer)
    sys.stdout = io.StringIO()
    try:
        exec(compiled, {"__name__": "__main__"})
    except Exception:
        pass
    finally:
        sys.settrace(None)
        sys.stdout = old_stdout
    return events


def main() -> None:
    if len(sys.argv) != 2:
        print("[]")
        return
    path = sys.argv[1]
    source = Path(path).read_text(encoding="utf-8")
    print(json.dumps(collect_trace(source, path), ensure_ascii=False))


if __name__ == "__main__":
    main()
