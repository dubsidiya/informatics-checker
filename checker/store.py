from __future__ import annotations

import csv
import io
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

_LOCK = threading.Lock()
_READY_FOR = ""
_CONN: sqlite3.Connection | None = None
_CONN_PATH = ""


def db_path() -> Path:
    return Path(os.environ.get("CHECKER_DB", str(ROOT / "data" / "attempts.db")))


def _connect() -> sqlite3.Connection:
    global _CONN, _CONN_PATH
    path = str(db_path())
    if _CONN is not None and _CONN_PATH == path:
        return _CONN
    if _CONN is not None:
        try:
            _CONN.close()
        except sqlite3.Error:
            pass
        _CONN = None
        _CONN_PATH = ""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.Error:
        pass
    _CONN = conn
    _CONN_PATH = path
    return conn


def init_store() -> None:
    global _READY_FOR
    with _LOCK:
        marker = str(db_path())
        if _READY_FOR == marker:
            return
        conn = _connect()
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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_attempts_student_problem ON attempts(student, problem_id, ts)"
        )
        conn.commit()
        _READY_FOR = marker


def reset_ready() -> None:
    global _READY_FOR, _CONN, _CONN_PATH
    with _LOCK:
        if _CONN is not None:
            try:
                _CONN.close()
            except sqlite3.Error:
                pass
            _CONN = None
            _CONN_PATH = ""
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
    args.append(max(1, min(limit, 500)))
    with _LOCK:
        conn = _connect()
        rows = conn.execute(sql, args).fetchall()
    return [dict(row) for row in rows]


def get_attempt(attempt_id: int) -> dict[str, Any] | None:
    init_store()
    with _LOCK:
        conn = _connect()
        row = conn.execute(
            """
            SELECT id, ts, student, problem_id, status, passed, total, message, code
            FROM attempts WHERE id = ?
            """,
            (attempt_id,),
        ).fetchone()
    return dict(row) if row else None


def latest_attempt(student: str, problem_id: str) -> dict[str, Any] | None:
    init_store()
    with _LOCK:
        conn = _connect()
        row = conn.execute(
            """
            SELECT id, ts, student, problem_id, status, passed, total, message, code
            FROM attempts
            WHERE student = ? AND problem_id = ?
            ORDER BY ts DESC LIMIT 1
            """,
            (student, problem_id),
        ).fetchone()
    return dict(row) if row else None


def student_progress(student: str) -> dict[str, Any]:
    name = clean_student_name(student)
    if name == "без имени":
        return {"student": "", "solved": [], "attempts": 0}
    init_store()
    with _LOCK:
        conn = _connect()
        rows = conn.execute(
            "SELECT problem_id, status FROM attempts WHERE student = ?",
            (name,),
        ).fetchall()
    solved = sorted({row["problem_id"] for row in rows if row["status"] == "ok"})
    return {"student": name, "solved": solved, "attempts": len(rows)}


def export_attempts(limit: int = 4000) -> list[dict[str, Any]]:
    init_store()
    with _LOCK:
        conn = _connect()
        rows = conn.execute(
            """
            SELECT id, ts, student, problem_id, status, passed, total, message
            FROM attempts
            ORDER BY ts DESC
            LIMIT ?
            """,
            (max(1, min(limit, 8000)),),
        ).fetchall()
    return [dict(row) for row in rows]


def export_csv(limit: int = 4000) -> str:
    rows = export_attempts(limit)
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf, delimiter=";", lineterminator="\n")
    writer.writerow(["время", "ученик", "задача", "статус", "пройдено", "всего", "сообщение"])
    for row in rows:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(row["ts"]))
        writer.writerow(
            [
                stamp,
                row["student"],
                row["problem_id"],
                row["status"],
                row["passed"],
                row["total"],
                row["message"],
            ]
        )
    return buf.getvalue()


def summarize() -> dict[str, Any]:
    init_store()
    with _LOCK:
        conn = _connect()
        rows = conn.execute(
            """
            SELECT id, ts, student, problem_id, status, passed, total, message
            FROM attempts
            ORDER BY ts ASC
            """
        ).fetchall()

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
                "best_attempt_id": row["id"],
                "best_status": row["status"],
                "best_passed": row["passed"],
                "best_total": row["total"],
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
            cell["best_attempt_id"] = row["id"]
            cell["best_passed"] = row["passed"]
            cell["best_total"] = row["total"]
        elif cell.get("best_status") != "ok":
            cell["best_status"] = row["status"]
            cell["best_attempt_id"] = row["id"]
            cell["best_passed"] = row["passed"]
            cell["best_total"] = row["total"]

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
