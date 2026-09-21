from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name, default) or "").strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _cidrs(raw: str) -> tuple[str, ...]:
    found: list[str] = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        try:
            ipaddress.ip_network(item, strict=False)
        except ValueError:
            continue
        found.append(item)
    return tuple(found)


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    db_path: Path
    public_origin: str
    is_production: bool
    teacher_pin_hash: str
    teacher_pin: str
    trusted_proxy_cidrs: tuple[str, ...]
    runner_kind: str
    judge0_url: str
    judge0_auth_header: str
    judge0_auth_token: str
    judge0_language_id: int
    judge0_language_name: str
    judge0_http_timeout: float
    judge0_result_timeout: float
    judge0_poll_interval: float
    grade_concurrency: int
    grade_queue_timeout: float
    grade_wall_seconds: float
    http_threads: int
    rate_limit: int
    login_limit: int
    name_limit: int
    progress_limit: int
    exam_limit: int
    session_hours: int
    disk_free_mb: int
    extra: dict[str, str] = field(default_factory=dict)

    def require_teacher_secret(self) -> None:
        if self.teacher_pin_hash or (self.teacher_pin and not self.is_production):
            return
        raise RuntimeError("Задайте TEACHER_PIN_HASH (или TEACHER_PIN только для локального режима).")

    def require_runner(self) -> None:
        if self.runner_kind == "local" and not self.is_production:
            return
        if self.runner_kind == "judge0" and self.judge0_url and self.judge0_auth_token:
            return
        raise RuntimeError("В production нужны JUDGE0_URL и JUDGE0_AUTH_TOKEN.")


def _runner_kind(is_production: bool) -> str:
    raw = _env("CHECKER_RUNNER").lower()
    if raw in {"judge0", "local"}:
        if is_production and raw == "local":
            return "judge0"
        return raw
    return "judge0" if is_production else "local"


def _is_production() -> bool:
    env = _env("CHECKER_ENV").lower()
    if env in {"test", "dev", "development"}:
        return False
    if env in {"production", "prod"}:
        return True
    return bool(_env("RENDER"))


def load_config() -> Config:
    is_production = _is_production()
    db_default = ROOT / "data" / "attempts.db"
    db_raw = _env("CHECKER_DB", str(db_default))
    db_path = Path(db_raw)
    if not db_path.is_absolute():
        db_path = (ROOT / db_path).resolve()
    origin = _env("PUBLIC_ORIGIN")
    if not origin and _env("RENDER_EXTERNAL_URL"):
        origin = _env("RENDER_EXTERNAL_URL")
        if origin and not origin.startswith("http"):
            origin = "https://" + origin
    trusted = _cidrs(_env("TRUSTED_PROXY_CIDRS"))
    if not trusted and is_production:
        trusted = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.1/32")
    pin_hash = _env("TEACHER_PIN_HASH")
    pin = _env("TEACHER_PIN")
    if pin == "159753pupil":
        pin = ""
    if not pin_hash and not pin and not is_production:
        pin = "test-teacher-pin"
    runner = _runner_kind(is_production)
    return Config(
        host=_env("HOST", "0.0.0.0"),
        port=_env_int("PORT", 8765),
        db_path=db_path,
        public_origin=origin.rstrip("/"),
        is_production=is_production,
        teacher_pin_hash=pin_hash,
        teacher_pin=pin if not is_production else "",
        trusted_proxy_cidrs=trusted,
        runner_kind=runner,
        judge0_url=_env("JUDGE0_URL").rstrip("/"),
        judge0_auth_header=_env("JUDGE0_AUTH_HEADER", "X-Auth-Token"),
        judge0_auth_token=_env("JUDGE0_AUTH_TOKEN"),
        judge0_language_id=_env_int("JUDGE0_LANGUAGE_ID", 109),
        judge0_language_name=_env("JUDGE0_EXPECTED_LANGUAGE_NAME", "Python (3.13.2)"),
        judge0_http_timeout=_env_float("JUDGE0_HTTP_TIMEOUT_SECONDS", 5.0),
        judge0_result_timeout=_env_float("JUDGE0_RESULT_TIMEOUT_SECONDS", 15.0),
        judge0_poll_interval=_env_float("JUDGE0_POLL_INTERVAL_SECONDS", 0.2),
        grade_concurrency=_env_int("CHECKER_GRADE_CONCURRENCY", 2 if is_production else 4),
        grade_queue_timeout=_env_float("CHECKER_GRADE_QUEUE_TIMEOUT_SECONDS", 2.0),
        grade_wall_seconds=_env_float("CHECKER_GRADE_WALL_SECONDS", 12.0),
        http_threads=_env_int("CHECKER_HTTP_THREADS", 32),
        rate_limit=_env_int("RATE_LIMIT", 90),
        login_limit=_env_int("LOGIN_LIMIT", 8),
        name_limit=_env_int("NAME_LIMIT", 25),
        progress_limit=_env_int("PROGRESS_LIMIT", 60),
        exam_limit=_env_int("EXAM_LIMIT", 40),
        session_hours=_env_int("SESSION_HOURS", 12),
        disk_free_mb=_env_int("DISK_FREE_MB", 32),
    )


@lru_cache(maxsize=1)
def get_config() -> Config:
    return load_config()


def reset_config() -> None:
    get_config.cache_clear()
