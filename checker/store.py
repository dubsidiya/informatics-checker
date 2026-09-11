from __future__ import annotations

import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

_LOCK = threading.Lock()
_READY_FOR = ""


def db_path() -> Path:
    return Path(os.environ.get("CHECKER_DB", str(ROOT / "data" / "attempts.db")))


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_store() -> None:
    global _READY_FOR
    with _LOCK:
        marker = str(db_path())
        if _READY_FOR == marker:
            return
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    student TEXT NOT NULL,
                    problem_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    code TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_attempts_student ON attempts(student)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_attempts_problem ON attempts(problem_id)")
            conn.commit()
        finally:
            conn.close()
        _READY_FOR = marker


def reset_ready() -> None:
    global _READY_FOR
    with _LOCK:
        _READY_FOR = ""


def clean_student_name(raw: object) -> str:
    if not isinstance(raw, str):
        return "без имени"
    name = " ".join(raw.split())
    if not name:
        return "без имени"
    return name[:80]


def record_attempt(
    student: str,
    problem_id: str,
    status: str,
    passed: int,
    total: int,
    message: str,
    code: str,
) -> int:
    init_store()
    with _LOCK:
        conn = _connect()
        try:
            cursor = conn.execute(
                """
                INSERT INTO attempts (ts, student, problem_id, status, passed, total, message, code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    time.time(),
                    clean_student_name(student),
                    problem_id,
                    status,
                    passed,
                    total,
                    message,
                    code,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)
        finally:
            conn.close()


def list_attempts(student: str = "", problem_id: str = "", limit: int = 120) -> list[dict[str, Any]]:
    init_store()
    where: list[str] = []
    args: list[object] = []
    if student:
        where.append("student = ?")
        args.append(student)
    if problem_id:
        where.append("problem_id = ?")
        args.append(problem_id)
    sql = "SELECT id, ts, student, problem_id, status, passed, total, message FROM attempts"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY ts DESC LIMIT ?"
    args.append(max(1, min(limit, 300)))
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(sql, args).fetchall()
        finally:
            conn.close()
    return [dict(row) for row in rows]


def get_attempt(attempt_id: int) -> dict[str, Any] | None:
    init_store()
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT id, ts, student, problem_id, status, passed, total, message, code
                FROM attempts WHERE id = ?
                """,
                (attempt_id,),
            ).fetchone()
        finally:
            conn.close()
    return dict(row) if row else None


def latest_attempt(student: str, problem_id: str) -> dict[str, Any] | None:
    init_store()
    with _LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT id, ts, student, problem_id, status, passed, total, message, code
                FROM attempts
                WHERE student = ? AND problem_id = ?
                ORDER BY ts DESC LIMIT 1
                """,
                (student, problem_id),
            ).fetchone()
        finally:
            conn.close()
    return dict(row) if row else None


def summarize() -> dict[str, Any]:
    init_store()
    with _LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT id, ts, student, problem_id, status, passed, total, message
                FROM attempts
                ORDER BY ts ASC
                """
            ).fetchall()
        finally:
            conn.close()

    students: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = row["student"]
        bucket = students.setdefault(
            name,
            {"name": name, "attempts": 0, "solved": 0, "last_ts": 0.0, "problems": {}},
        )
        bucket["attempts"] += 1
        bucket["last_ts"] = row["ts"]
        cell = bucket["problems"].setdefault(
            row["problem_id"],
            {
                "problem_id": row["problem_id"],
                "attempts": 0,
                "status": row["status"],
                "passed": row["passed"],
                "total": row["total"],
                "ts": row["ts"],
                "attempt_id": row["id"],
                "best_status": row["status"],
            },
        )
        cell["attempts"] += 1
        cell["status"] = row["status"]
        cell["passed"] = row["passed"]
        cell["total"] = row["total"]
        cell["ts"] = row["ts"]
        cell["attempt_id"] = row["id"]
        if row["status"] == "ok":
            cell["best_status"] = "ok"
        elif cell.get("best_status") != "ok":
            cell["best_status"] = row["status"]

    roster = []
    for bucket in students.values():
        bucket["solved"] = sum(
            1 for cell in bucket["problems"].values() if cell.get("best_status") == "ok"
        )
        roster.append(bucket)
    roster.sort(key=lambda item: (-item["solved"], -item["attempts"], item["name"].lower()))
    return {
        "students": roster,
        "total_attempts": len(rows),
        "total_students": len(roster),
    }
