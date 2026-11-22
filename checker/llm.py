from __future__ import annotations

import json
import urllib.error
import urllib.request

from checker.config import get_config


def complete(messages: list[dict[str, str]]) -> str | None:
    """Ask the local mentor model. None means the model is off or unreachable.

    The checker keeps its own verdict either way. This call only rewrites
    the hint a student reads after the tests have already failed.
    """
    cfg = get_config()
    if not cfg.llm_url:
        return None
    body = json.dumps(
        {
            "model": cfg.llm_model,
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "messages": messages,
            "options": {"temperature": 0.2, "num_predict": 420},
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if cfg.llm_token:
        headers["Authorization"] = f"Bearer {cfg.llm_token}"
    request = urllib.request.Request(
        cfg.llm_url.rstrip("/") + "/api/chat",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=cfg.llm_timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None
    message = payload.get("message") if isinstance(payload, dict) else None
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        return None
    return content.strip()
