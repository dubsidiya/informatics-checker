from __future__ import annotations

import csv
import io
import json
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                student TEXT NOT NULL,
                topic TEXT NOT NULL,
                status TEXT NOT NULL,
                solved INTEGER NOT NULL DEFAULT 0,
                total INTEGER NOT NULL DEFAULT 0,
                skipped INTEGER NOT NULL DEFAULT 0,
                problem_ids TEXT NOT NULL DEFAULT '[]',
                updated REAL NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_exams_student ON exams(student, updated)")
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
    ts: float | None = None,
) -> int:
    init_store()
    stamp = float(ts) if ts else time.time()
    with _LOCK:
        conn = _connect()
        cursor = conn.execute(
            """
            INSERT INTO attempts (ts, student, problem_id, status, passed, total, message, code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stamp,
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


def _attempt_exists(conn: sqlite3.Connection, student: str, problem_id: str, status: str, ts: float) -> bool:
    row = conn.execute(
        """
        SELECT id FROM attempts
        WHERE student = ? AND problem_id = ? AND status = ? AND abs(ts - ?) < 1.5
        LIMIT 1
        """,
        (student, problem_id, status, ts),
    ).fetchone()
    return row is not None


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
        return {"student": "", "solved": [], "attempts": 0, "problems": {}}
    init_store()
    with _LOCK:
        conn = _connect()
        rows = conn.execute(
            "SELECT problem_id, status FROM attempts WHERE student = ?",
            (name,),
        ).fetchall()
    problems: dict[str, dict[str, Any]] = {}
    for row in rows:
        cell = problems.setdefault(
            row["problem_id"],
            {"attempts": 0, "fails": 0, "solved": False},
        )
        cell["attempts"] += 1
        if row["status"] == "ok":
            cell["solved"] = True
        else:
            cell["fails"] += 1
    solved = sorted(pid for pid, cell in problems.items() if cell["solved"])
    return {"student": name, "solved": solved, "attempts": len(rows), "problems": problems}


def problem_attempt_count(student: str, problem_id: str) -> int:
    name = clean_student_name(student)
    if name == "без имени" or not problem_id:
        return 0
    init_store()
    with _LOCK:
        conn = _connect()
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM attempts WHERE student = ? AND problem_id = ?",
            (name, problem_id),
        ).fetchone()
    return int(row["n"] if row else 0)


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
    stuck: list[dict[str, Any]] = []
    for bucket in roster:
        for cell in bucket["problems"].values():
            if cell.get("best_status") == "ok":
                continue
            if int(cell.get("attempts") or 0) < 3:
                continue
            stuck.append(
                {
                    "student": bucket["name"],
                    "problem_id": cell["problem_id"],
                    "attempts": cell["attempts"],
                    "passed": cell.get("best_passed", cell.get("passed", 0)),
                    "total": cell.get("best_total", cell.get("total", 0)),
                    "ts": cell.get("ts", 0),
                }
            )
    stuck.sort(key=lambda item: (-item["attempts"], -item["ts"]))
    return {
        "students": roster,
        "total_attempts": len(rows),
        "total_students": len(roster),
        "stuck": stuck[:40],
        "exams": exam_board(),
    }


def _exam_row(row: sqlite3.Row) -> dict[str, Any]:
    try:
        ids = json.loads(row["problem_ids"] or "[]")
    except json.JSONDecodeError:
        ids = []
    if not isinstance(ids, list):
        ids = []
    return {
        "id": row["id"],
        "ts": row["ts"],
        "student": row["student"],
        "topic": row["topic"],
        "status": row["status"],
        "solved": row["solved"],
        "total": row["total"],
        "skipped": row["skipped"],
        "problem_ids": [str(item) for item in ids][:40],
        "updated": row["updated"],
    }


def exam_board() -> dict[str, Any]:
    init_store()
    now = time.time()
    with _LOCK:
        conn = _connect()
        live_rows = conn.execute(
            """
            SELECT id, ts, student, topic, status, solved, total, skipped, problem_ids, updated
            FROM exams
            WHERE status = 'live' AND updated >= ?
            ORDER BY updated DESC
            LIMIT 80
            """,
            (now - 3 * 3600,),
        ).fetchall()
        recent_rows = conn.execute(
            """
            SELECT id, ts, student, topic, status, solved, total, skipped, problem_ids, updated
            FROM exams
            WHERE status IN ('done', 'left')
            ORDER BY updated DESC
            LIMIT 40
            """
        ).fetchall()
    return {
        "live": [_exam_row(row) for row in live_rows],
        "recent": [_exam_row(row) for row in recent_rows],
    }


def start_exam(student: str, topic: str, problem_ids: list[str]) -> dict[str, Any]:
    name = clean_student_name(student)
    topic_name = " ".join(str(topic or "").split())[:80] or "тема"
    ids = [str(item)[:80] for item in problem_ids if str(item).strip()][:40]
    now = time.time()
    payload = json.dumps(ids, ensure_ascii=False)
    init_store()
    with _LOCK:
        conn = _connect()
        conn.execute(
            "UPDATE exams SET status = 'left', updated = ? WHERE student = ? AND status = 'live'",
            (now, name),
        )
        cursor = conn.execute(
            """
            INSERT INTO exams (ts, student, topic, status, solved, total, skipped, problem_ids, updated)
            VALUES (?, ?, ?, 'live', 0, ?, 0, ?, ?)
            """,
            (now, name, topic_name, len(ids), payload, now),
        )
        conn.commit()
        exam_id = int(cursor.lastrowid)
    return {
        "id": exam_id,
        "student": name,
        "topic": topic_name,
        "status": "live",
        "solved": 0,
        "total": len(ids),
        "skipped": 0,
        "problem_ids": ids,
    }


def update_exam(
    student: str,
    *,
    solved: int | None = None,
    skipped: int | None = None,
    total: int | None = None,
    status: str | None = None,
) -> dict[str, Any] | None:
    name = clean_student_name(student)
    if name == "без имени":
        return None
    init_store()
    now = time.time()
    with _LOCK:
        conn = _connect()
        row = conn.execute(
            """
            SELECT id, ts, student, topic, status, solved, total, skipped, problem_ids, updated
            FROM exams
            WHERE student = ? AND status = 'live'
            ORDER BY updated DESC
            LIMIT 1
            """,
            (name,),
        ).fetchone()
        if not row:
            return None
        new_status = status if status in {"live", "done", "left"} else row["status"]
        try:
            new_solved = row["solved"] if solved is None else max(0, min(int(solved), 200))
            new_skipped = row["skipped"] if skipped is None else max(0, min(int(skipped), 200))
            new_total = row["total"] if total is None else max(0, min(int(total), 200))
        except (TypeError, ValueError):
            new_solved, new_skipped, new_total = row["solved"], row["skipped"], row["total"]
        conn.execute(
            """
            UPDATE exams
            SET solved = ?, skipped = ?, total = ?, status = ?, updated = ?
            WHERE id = ?
            """,
            (new_solved, new_skipped, new_total, new_status, now, row["id"]),
        )
        conn.commit()
        fresh = conn.execute(
            """
            SELECT id, ts, student, topic, status, solved, total, skipped, problem_ids, updated
            FROM exams WHERE id = ?
            """,
            (row["id"],),
        ).fetchone()
    return _exam_row(fresh) if fresh else None


def _parse_ts(value: object) -> float | None:
    if isinstance(value, (int, float)) and value > 0:
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y %H:%M:%S"):
        try:
            return time.mktime(time.strptime(text[:19], fmt))
        except ValueError:
            continue
    try:
        return float(text)
    except ValueError:
        return None


def import_journal(text: str, kind: str = "csv") -> dict[str, Any]:
    raw = text or ""
    if len(raw) > 2_000_000:
        return {"inserted": 0, "skipped": 0, "detail": "file too large"}
    rows: list[dict[str, Any]] = []
    mode = (kind or "csv").lower()
    if mode == "json":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {"inserted": 0, "skipped": 0, "detail": "bad json"}
        if isinstance(payload, dict) and isinstance(payload.get("students"), list):
            return {"inserted": 0, "skipped": 0, "detail": "need attempt list"}
        items = payload if isinstance(payload, list) else payload.get("attempts") if isinstance(payload, dict) else []
        if not isinstance(items, list):
            return {"inserted": 0, "skipped": 0, "detail": "need attempt list"}
        for item in items[:8000]:
            if isinstance(item, dict):
                rows.append(item)
    else:
        sample = raw.lstrip("\ufeff")
        reader = csv.DictReader(io.StringIO(sample), delimiter=";")
        if not reader.fieldnames:
            return {"inserted": 0, "skipped": 0, "detail": "empty csv"}
        for item in reader:
            rows.append(item)
            if len(rows) >= 8000:
                break

    inserted = 0
    skipped = 0
    init_store()
    with _LOCK:
        conn = _connect()
        for item in rows:
            student = clean_student_name(item.get("student") or item.get("ученик") or "")
            problem_id = str(item.get("problem_id") or item.get("задача") or "").strip()[:80]
            status = str(item.get("status") or item.get("статус") or "").strip()[:20]
            if student == "без имени" or not problem_id or status not in {"ok", "fail", "syntax"}:
                skipped += 1
                continue
            try:
                passed = int(item.get("passed") if item.get("passed") is not None else item.get("пройдено") or 0)
                total = int(item.get("total") if item.get("total") is not None else item.get("всего") or 0)
            except (TypeError, ValueError):
                skipped += 1
                continue
            message = str(item.get("message") or item.get("сообщение") or status)[:400]
            code = str(item.get("code") or "")[:80_000]
            stamp = _parse_ts(item.get("ts") or item.get("время")) or time.time()
            if _attempt_exists(conn, student, problem_id, status, stamp):
                skipped += 1
                continue
            conn.execute(
                """
                INSERT INTO attempts (ts, student, problem_id, status, passed, total, message, code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (stamp, student, problem_id, status, passed, total, message, code),
            )
            inserted += 1
        conn.commit()
    return {"inserted": inserted, "skipped": skipped}

