from __future__ import annotations

import json
import threading
import time
import uuid
from typing import Any

_LOCK = threading.Lock()
_COUNTERS: dict[str, int] = {
    "requests": 0,
    "http_429": 0,
    "http_503": 0,
    "store_fail": 0,
    "runner_fail": 0,
    "grade_ok": 0,
    "grade_fail": 0,
}


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


def bump(name: str, amount: int = 1) -> None:
    with _LOCK:
        _COUNTERS[name] = _COUNTERS.get(name, 0) + amount


def snapshot() -> dict[str, int]:
    with _LOCK:
        return dict(_COUNTERS)


def log_event(event: str, **fields: Any) -> None:
    payload = {"ts": round(time.time(), 3), "event": event}
    for key, value in fields.items():
        if key in {"code", "pin", "cookie", "token", "student", "query"}:
            continue
        payload[key] = value
    print(json.dumps(payload, ensure_ascii=False), flush=True)
