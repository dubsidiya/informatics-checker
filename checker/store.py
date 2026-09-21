from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from checker.auth import hash_token, new_token
from checker.config import get_config, reset_config
from checker.migrations import (
    CURRENT_SCHEMA_VERSION,
    _normalise_name,
    migrate,
)
from checker.problems import all_problems
from checker.runner import set_runner

_LOCK = threading.Lock()
_READY_FOR = ""
_CONN: sqlite3.Connection | None = None
_CONN_PATH = ""


def db_path() -> Path:
    return get_config().db_path


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
        conn.execute("PRAGMA foreign_keys=ON")
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
        migrate(conn)
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
    set_runner(None)
    reset_config()


def clean_student_name(raw: object) -> str:
    display, _ = _normalise_name(raw)
    return display


def _get_or_create_student(conn: sqlite3.Connection, name: str) -> str:
    display, normalised = _normalise_name(name)
    row = conn.execute(
        """
        SELECT id FROM students
        WHERE normalized_name = ?
        ORDER BY legacy ASC, created_at ASC
        LIMIT 1
        """,
        (normalised,),
    ).fetchone()
    if row:
        return str(row["id"])
    sid = secrets.token_hex(16)
    conn.execute(
        """
        INSERT INTO students (id, display_name, normalized_name, created_at, legacy)
        VALUES (?, ?, ?, ?, 0)
        """,
        (sid, display, normalised, time.time()),
    )
    return sid


def record_attempt(
    student: str,
    problem_id: str,
    status: str,
    passed: int,
    total: int,
    message: str,
    code: str,
    ts: float | None = None,
    student_id: str | None = None,
    student_session_id: str | None = None,
) -> int:
    init_store()
    stamp = float(ts) if ts else time.time()
    name = clean_student_name(student)
    with _LOCK:
        conn = _connect()
        sid = student_id or _get_or_create_student(conn, name)
        exam_id = None
        if sid:
            exam = conn.execute(
                "SELECT id FROM exams WHERE student_id = ? AND status = 'live' ORDER BY updated DESC LIMIT 1",
                (sid,),
            ).fetchone()
            if exam:
                exam_id = int(exam["id"])
        row = conn.execute(
            "SELECT COALESCE(MAX(attempt_no), 0) AS n FROM attempts WHERE student_id = ? AND problem_id = ?",
            (sid, problem_id),
        ).fetchone()
        attempt_no = int(row["n"] if row else 0) + 1
        cursor = conn.execute(
            """
            INSERT INTO attempts (
                ts, student, problem_id, status, passed, total, message, code,
                student_id, student_session_id, attempt_no, exam_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stamp,
                name,
                problem_id,
                status,
                passed,
                total,
                message,
                code,
                sid,
                student_session_id,
                attempt_no,
                exam_id,
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


def student_progress(student: str, student_id: str | None = None) -> dict[str, Any]:
    name = clean_student_name(student)
    if name == "без имени" and student_id is None:
        return {"student": "", "solved": [], "attempts": 0, "problems": {}}
    init_store()
    with _LOCK:
        conn = _connect()
        if student_id is not None:
            rows = conn.execute(
                "SELECT problem_id, status FROM attempts WHERE student_id = ?",
                (student_id,),
            ).fetchall()
            name_row = conn.execute("SELECT display_name FROM students WHERE id = ?", (student_id,)).fetchone()
            name = name_row["display_name"] if name_row else name
        else:
            rows = conn.execute("SELECT problem_id, status FROM attempts WHERE student = ?", (name,)).fetchall()
    problems: dict[str, dict[str, Any]] = {}
    for row in rows:
        cell = problems.setdefault(row["problem_id"], {"attempts": 0, "fails": 0, "solved": False})
        cell["attempts"] += 1
        if row["status"] == "ok":
            cell["solved"] = True
        else:
            cell["fails"] += 1
    solved = sorted(pid for pid, cell in problems.items() if cell["solved"])
    return {"student": name, "solved": solved, "attempts": len(rows), "problems": problems}


def problem_attempt_count(student: str, problem_id: str, student_id: str | None = None) -> int:
    name = clean_student_name(student)
    if (name == "без имени" and student_id is None) or not problem_id:
        return 0
    init_store()
    with _LOCK:
        conn = _connect()
        if student_id is not None:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM attempts WHERE student_id = ? AND problem_id = ?",
                (student_id, problem_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM attempts WHERE student = ? AND problem_id = ?",
                (name, problem_id),
            ).fetchone()
    return int(row["n"] if row else 0)


def export_attempts(limit: int | None = None, include_code: bool = False) -> list[dict[str, Any]]:
    init_store()
    fields = "id, ts, student, problem_id, status, passed, total, message"
    if include_code:
        fields += ", code"
    sql = f"SELECT {fields} FROM attempts ORDER BY ts DESC"
    args: list[object] = []
    if limit is not None:
        sql += " LIMIT ?"
        args.append(max(1, min(limit, 200_000)))
    with _LOCK:
        conn = _connect()
        rows = conn.execute(sql, args).fetchall()
    return [dict(row) for row in rows]


def export_csv(limit: int | None = 4000) -> str:
    rows = export_attempts(limit, include_code=False)
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


def export_backup_json() -> dict[str, Any]:
    init_store()
    with _LOCK:
        conn = _connect()
        attempts = [dict(row) for row in conn.execute("SELECT * FROM attempts ORDER BY id").fetchall()]
        exams = [dict(row) for row in conn.execute("SELECT * FROM exams ORDER BY id").fetchall()]
        students = [dict(row) for row in conn.execute("SELECT id, display_name, normalized_name, created_at, legacy FROM students ORDER BY created_at").fetchall()]
    return {
        "format": "informatics-checker-backup",
        "version": CURRENT_SCHEMA_VERSION,
        "attempts": attempts,
        "exams": exams,
        "students": students,
    }


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
        total_attempts = len(rows)
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
        bucket["solved"] = sum(1 for cell in bucket["problems"].values() if cell.get("best_status") == "ok")
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
    catalog = all_problems()
    by_problem = {item.id: item for item in catalog}
    topic_stats: dict[str, dict[str, Any]] = {}
    for item in catalog:
        topic_stats[item.topic] = {
            "topic": item.topic,
            "tasks": 0,
            "attempted": 0,
            "solved": 0,
            "attempts": 0,
        }
    for bucket in roster:
        for problem_id, cell in bucket["problems"].items():
            problem = by_problem.get(problem_id)
            if not problem:
                continue
            stat = topic_stats.setdefault(problem.topic, {
                "topic": problem.topic, "tasks": 0, "attempted": 0, "solved": 0, "attempts": 0,
            })
            stat["attempted"] += 1
            stat["attempts"] += int(cell.get("attempts") or 0)
            if cell.get("best_status") == "ok":
                stat["solved"] += 1
    for stat in topic_stats.values():
        stat["tasks"] = sum(1 for item in catalog if item.topic == stat["topic"])
        stat["success_rate"] = round(stat["solved"] / stat["attempted"] * 100) if stat["attempted"] else 0
    hard_tasks: list[dict[str, Any]] = []
    for problem_id, problem in by_problem.items():
        attempts = 0
        fails = 0
        solved = 0
        for bucket in roster:
            cell = bucket["problems"].get(problem_id)
            if not cell:
                continue
            attempts += int(cell.get("attempts") or 0)
            if cell.get("best_status") == "ok":
                solved += 1
            else:
                fails += int(cell.get("attempts") or 0)
        if attempts:
            hard_tasks.append({
                "problem_id": problem_id,
                "title": problem.title,
                "topic": problem.topic,
                "level": problem.level,
                "attempts": attempts,
                "fails": fails,
                "solved": solved,
                "success_rate": round(solved / max(1, solved + fails) * 100),
            })
    hard_tasks.sort(key=lambda item: (-item["fails"], item["success_rate"], -item["attempts"]))
    now = time.time()
    inactive = [
        {"name": item["name"], "last_ts": item["last_ts"]}
        for item in roster
        if not item["last_ts"] or now - item["last_ts"] > 45 * 60
    ]
    return {
        "students": roster,
        "total_attempts": total_attempts,
        "total_students": len(roster),
        "stuck": stuck[:40],
        "topics": sorted(topic_stats.values(), key=lambda item: (-item["attempts"], item["topic"])),
        "hard_tasks": hard_tasks[:40],
        "inactive": inactive[:40],
        "exams": exam_board(),
    }


def _exam_row(row: sqlite3.Row) -> dict[str, Any]:
    try:
        ids = json.loads(row["problem_ids"] or "[]")
    except json.JSONDecodeError:
        ids = []
    if not isinstance(ids, list):
        ids = []
    skipped_raw = row["skipped_ids"] if "skipped_ids" in row.keys() else "[]"
    try:
        skipped = json.loads(skipped_raw or "[]")
    except json.JSONDecodeError:
        skipped = []
    if not isinstance(skipped, list):
        skipped = []
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
        "skipped_ids": [str(item) for item in skipped][:40],
        "updated": row["updated"],
    }


def exam_board() -> dict[str, Any]:
    init_store()
    now = time.time()
    with _LOCK:
        conn = _connect()
        live_rows = conn.execute(
            """
            SELECT id, ts, student, topic, status, solved, total, skipped, problem_ids, skipped_ids, updated
            FROM exams
            WHERE status = 'live' AND updated >= ?
            ORDER BY updated DESC
            LIMIT 80
            """,
            (now - 3 * 3600,),
        ).fetchall()
        recent_rows = conn.execute(
            """
            SELECT id, ts, student, topic, status, solved, total, skipped, problem_ids, skipped_ids, updated
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


def pick_exam_ids(topic: str, student_id: str, seed: str) -> list[str]:
    pool = [item for item in all_problems() if item.topic == topic]
    if not pool:
        return []

    def order(item) -> str:
        return hashlib.sha256(f"{seed}:{student_id}:{item.id}".encode("utf-8")).hexdigest()

    buckets = {"старт": [], "средне": [], "сложно": []}
    for item in sorted(pool, key=order):
        buckets.get(item.level, buckets["средне"]).append(item)
    picked = []

    def take(level: str, count: int) -> None:
        bucket = buckets[level]
        while count > 0 and bucket:
            picked.append(bucket.pop(0))
            count -= 1

    take("старт", 3)
    take("средне", 3)
    take("сложно", 2)
    rest = [item for item in sorted(pool, key=order) if item not in picked]
    for item in rest:
        if len(picked) >= 8:
            break
        picked.append(item)
    return [item.id for item in picked[:8]]


def _exam_counts(conn: sqlite3.Connection, exam: sqlite3.Row) -> tuple[int, int, int]:
    ids = json.loads(exam["problem_ids"] or "[]")
    skipped = json.loads(exam["skipped_ids"] or "[]") if "skipped_ids" in exam.keys() else []
    ids = [str(item) for item in ids]
    skipped = [str(item) for item in skipped]
    solved = 0
    if exam["student_id"] is not None and ids:
        rows = conn.execute(
            """
            SELECT DISTINCT problem_id FROM attempts
            WHERE student_id = ? AND status = 'ok' AND ts >= ? AND problem_id IN ({})
            """.format(",".join("?" * len(ids))),
            [exam["student_id"], exam["ts"], *ids],
        ).fetchall()
        solved = len(rows)
    return solved, len(set(skipped) & set(ids)), len(ids)


def start_exam(student: str, topic: str, problem_ids: list[str] | None = None, student_id: str | None = None) -> dict[str, Any]:
    name = clean_student_name(student)
    topic_name = " ".join(str(topic or "").split())[:80] or "тема"
    now = time.time()
    init_store()
    with _LOCK:
        conn = _connect()
        sid = student_id or _get_or_create_student(conn, name)
        live = conn.execute(
            """
            SELECT id, ts, student, topic, status, solved, total, skipped, problem_ids, skipped_ids, updated, student_id
            FROM exams WHERE student_id = ? AND status = 'live' ORDER BY updated DESC LIMIT 1
            """,
            (sid,),
        ).fetchone()
        if live and live["topic"] == topic_name:
            solved, skipped_n, total = _exam_counts(conn, live)
            conn.execute(
                "UPDATE exams SET solved = ?, skipped = ?, total = ?, updated = ? WHERE id = ?",
                (solved, skipped_n, total, now, live["id"]),
            )
            conn.commit()
            fresh = conn.execute(
                "SELECT id, ts, student, topic, status, solved, total, skipped, problem_ids, skipped_ids, updated FROM exams WHERE id = ?",
                (live["id"],),
            ).fetchone()
            return _exam_row(fresh)
        conn.execute(
            "UPDATE exams SET status = 'left', updated = ?, finished_at = ? WHERE student_id = ? AND status = 'live'",
            (now, now, sid),
        )
        seed = hashlib.sha256(f"{sid}:{topic_name}:{now}:{random.random()}".encode("utf-8")).hexdigest()
        ids = pick_exam_ids(topic_name, sid, seed)
        payload = json.dumps(ids, ensure_ascii=False)
        cursor = conn.execute(
            """
            INSERT INTO exams (
                ts, student, topic, status, solved, total, skipped, problem_ids, updated,
                student_id, exam_seed, skipped_ids
            )
            VALUES (?, ?, ?, 'live', 0, ?, 0, ?, ?, ?, ?, '[]')
            """,
            (now, name, topic_name, len(ids), payload, now, sid, seed),
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
        "skipped_ids": [],
    }


def update_exam(
    student: str,
    *,
    solved: int | None = None,
    skipped: int | None = None,
    total: int | None = None,
    status: str | None = None,
    student_id: str | None = None,
    skip_problem: str | None = None,
) -> dict[str, Any] | None:
    name = clean_student_name(student)
    if name == "без имени" and student_id is None:
        return None
    init_store()
    now = time.time()
    with _LOCK:
        conn = _connect()
        if student_id is not None:
            row = conn.execute(
                """
                SELECT id, ts, student, topic, status, solved, total, skipped, problem_ids, skipped_ids, updated, student_id
                FROM exams
                WHERE student_id = ? AND status = 'live'
                ORDER BY updated DESC
                LIMIT 1
                """,
                (student_id,),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT id, ts, student, topic, status, solved, total, skipped, problem_ids, skipped_ids, updated, student_id
                FROM exams
                WHERE student = ? AND status = 'live'
                ORDER BY updated DESC
                LIMIT 1
                """,
                (name,),
            ).fetchone()
        if not row:
            return None
        skipped_ids = json.loads(row["skipped_ids"] or "[]")
        ids = [str(item) for item in json.loads(row["problem_ids"] or "[]")]
        if skip_problem and skip_problem in ids and skip_problem not in skipped_ids:
            skipped_ids.append(skip_problem)
        new_status = status if status in {"live", "done", "left"} else row["status"]
        solved_n, skipped_n, total_n = _exam_counts(conn, row)
        skipped_n = len(set(skipped_ids) & set(ids))
        if new_status == "live" and total_n and solved_n >= total_n:
            new_status = "done"
        finished_at = now if new_status in {"done", "left"} else None
        conn.execute(
            """
            UPDATE exams
            SET solved = ?, skipped = ?, total = ?, status = ?, updated = ?, skipped_ids = ?, finished_at = COALESCE(?, finished_at)
            WHERE id = ?
            """,
            (solved_n, skipped_n, total_n, new_status, now, json.dumps(skipped_ids, ensure_ascii=False), finished_at, row["id"]),
        )
        conn.commit()
        fresh = conn.execute(
            "SELECT id, ts, student, topic, status, solved, total, skipped, problem_ids, skipped_ids, updated FROM exams WHERE id = ?",
            (row["id"],),
        ).fetchone()
    return _exam_row(fresh) if fresh else None


def live_exam(student_id: str) -> dict[str, Any] | None:
    init_store()
    with _LOCK:
        conn = _connect()
        row = conn.execute(
            """
            SELECT id, ts, student, topic, status, solved, total, skipped, problem_ids, skipped_ids, updated, student_id
            FROM exams
            WHERE student_id = ? AND status = 'live'
            ORDER BY updated DESC LIMIT 1
            """,
            (student_id,),
        ).fetchone()
        if not row:
            return None
        solved_n, skipped_n, total_n = _exam_counts(conn, row)
        conn.execute(
            "UPDATE exams SET solved = ?, skipped = ?, total = ?, updated = ? WHERE id = ?",
            (solved_n, skipped_n, total_n, time.time(), row["id"]),
        )
        conn.commit()
        fresh = conn.execute(
            "SELECT id, ts, student, topic, status, solved, total, skipped, problem_ids, skipped_ids, updated FROM exams WHERE id = ?",
            (row["id"],),
        ).fetchone()
    return _exam_row(fresh) if fresh else None


def create_student_session(name: str, hours: int = 12) -> dict[str, Any]:
    clean = clean_student_name(name)
    if clean == "без имени":
        raise ValueError("name")
    token = new_token()
    csrf = new_token()
    session_id = new_token()
    now = time.time()
    init_store()
    with _LOCK:
        conn = _connect()
        sid = _get_or_create_student(conn, clean)
        conn.execute(
            "UPDATE student_sessions SET revoked_at = ? WHERE student_id = ? AND revoked_at IS NULL",
            (now, sid),
        )
        conn.execute(
            """
            INSERT INTO student_sessions (id, student_id, token_hash, csrf_hash, created_at, expires_at, revoked_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (session_id, sid, hash_token(token), hash_token(csrf), now, now + hours * 3600),
        )
        conn.commit()
    return {"token": token, "csrf": csrf, "student_id": sid, "student": clean, "session_id": session_id}


def get_student_session(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    init_store()
    now = time.time()
    with _LOCK:
        conn = _connect()
        row = conn.execute(
            """
            SELECT s.id, s.student_id, s.csrf_hash, s.expires_at, s.revoked_at, st.display_name
            FROM student_sessions s
            JOIN students st ON st.id = s.student_id
            WHERE s.token_hash = ?
            """,
            (hash_token(token),),
        ).fetchone()
    if not row or row["revoked_at"] is not None or row["expires_at"] < now:
        return None
    return {
        "session_id": row["id"],
        "student_id": row["student_id"],
        "student": row["display_name"],
        "csrf_hash": row["csrf_hash"],
    }


def revoke_student_session(token: str) -> None:
    init_store()
    with _LOCK:
        conn = _connect()
        conn.execute(
            "UPDATE student_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
            (time.time(), hash_token(token)),
        )
        conn.commit()


def create_teacher_session(fingerprint: str, hours: int = 12) -> dict[str, Any]:
    token = new_token()
    csrf = new_token()
    session_id = new_token()
    now = time.time()
    init_store()
    with _LOCK:
        conn = _connect()
        conn.execute(
            """
            INSERT INTO teacher_sessions (
                id, token_hash, csrf_hash, credential_fingerprint, created_at, expires_at, revoked_at
            )
            VALUES (?, ?, ?, ?, ?, ?, NULL)
            """,
            (session_id, hash_token(token), hash_token(csrf), fingerprint, now, now + hours * 3600),
        )
        conn.commit()
    return {"token": token, "csrf": csrf, "session_id": session_id}


def get_teacher_session(token: str, fingerprint: str) -> dict[str, Any] | None:
    if not token:
        return None
    init_store()
    now = time.time()
    with _LOCK:
        conn = _connect()
        row = conn.execute(
            """
            SELECT id, csrf_hash, credential_fingerprint, expires_at, revoked_at
            FROM teacher_sessions WHERE token_hash = ?
            """,
            (hash_token(token),),
        ).fetchone()
    if not row or row["revoked_at"] is not None or row["expires_at"] < now:
        return None
    if fingerprint and row["credential_fingerprint"] != fingerprint:
        return None
    return {"session_id": row["id"], "csrf_hash": row["csrf_hash"]}


def revoke_teacher_session(token: str) -> None:
    init_store()
    with _LOCK:
        conn = _connect()
        conn.execute(
            "UPDATE teacher_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
            (time.time(), hash_token(token)),
        )
        conn.commit()


def revoke_all_teacher_sessions() -> None:
    init_store()
    with _LOCK:
        conn = _connect()
        conn.execute("UPDATE teacher_sessions SET revoked_at = ? WHERE revoked_at IS NULL", (time.time(),))
        conn.commit()


def revoke_all_student_sessions() -> None:
    init_store()
    with _LOCK:
        conn = _connect()
        conn.execute("UPDATE student_sessions SET revoked_at = ? WHERE revoked_at IS NULL", (time.time(),))
        conn.commit()


def revoke_restored_sessions() -> None:
    revoke_all_teacher_sessions()
    revoke_all_student_sessions()


def probe_write() -> bool:
    init_store()
    with _LOCK:
        conn = _connect()
        conn.execute("CREATE TABLE IF NOT EXISTS readiness_probe (k INTEGER PRIMARY KEY, v REAL)")
        conn.execute("INSERT OR REPLACE INTO readiness_probe (k, v) VALUES (1, ?)", (time.time(),))
        conn.commit()
    return True


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


def restore_backup_json(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("format") != "informatics-checker-backup":
        raise ValueError("bad backup")
    version = int(payload.get("version") or 0)
    if version > CURRENT_SCHEMA_VERSION:
        raise ValueError("backup newer than schema")
    attempts = payload.get("attempts") or []
    exams = payload.get("exams") or []
    students = payload.get("students") or []
    if not isinstance(attempts, list) or not isinstance(exams, list) or not isinstance(students, list):
        raise ValueError("bad backup")
    init_store()
    inserted = 0
    skipped = 0
    with _LOCK:
        conn = _connect()
        for item in students:
            if not isinstance(item, dict):
                skipped += 1
                continue
            sid = str(item.get("id") or "")
            display = clean_student_name(item.get("display_name") or item.get("name") or "")
            if not sid or display == "без имени":
                skipped += 1
                continue
            _, normalised = _normalise_name(display)
            created = float(item.get("created_at") or item.get("created") or time.time())
            legacy = int(item.get("legacy") or 0)
            conn.execute(
                """
                INSERT OR IGNORE INTO students (id, display_name, normalized_name, created_at, legacy)
                VALUES (?, ?, ?, ?, ?)
                """,
                (sid, display, normalised, created, 1 if legacy else 0),
            )
        for item in attempts:
            if not isinstance(item, dict):
                skipped += 1
                continue
            student = clean_student_name(item.get("student") or "")
            problem_id = str(item.get("problem_id") or "").strip()[:80]
            status = str(item.get("status") or "").strip()[:20]
            if student == "без имени" or not problem_id or status not in {"ok", "fail", "syntax"}:
                skipped += 1
                continue
            stamp = _parse_ts(item.get("ts")) or time.time()
            if _attempt_exists(conn, student, problem_id, status, stamp):
                skipped += 1
                continue
            try:
                passed = int(item.get("passed") or 0)
                total = int(item.get("total") or 0)
            except (TypeError, ValueError):
                skipped += 1
                continue
            sid = str(item.get("student_id") or "") or _get_or_create_student(conn, student)
            row = conn.execute(
                "SELECT COALESCE(MAX(attempt_no), 0) AS n FROM attempts WHERE student_id = ? AND problem_id = ?",
                (sid, problem_id),
            ).fetchone()
            attempt_no = int(row["n"] if row else 0) + 1
            conn.execute(
                """
                INSERT INTO attempts (
                    ts, student, problem_id, status, passed, total, message, code,
                    student_id, attempt_no
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stamp,
                    student,
                    problem_id,
                    status,
                    passed,
                    total,
                    str(item.get("message") or status)[:400],
                    str(item.get("code") or "")[:80_000],
                    sid,
                    attempt_no,
                ),
            )
            inserted += 1
        for item in exams:
            if not isinstance(item, dict):
                continue
            student = clean_student_name(item.get("student") or "")
            if student == "без имени":
                continue
            sid = str(item.get("student_id") or "") or _get_or_create_student(conn, student)
            conn.execute(
                """
                INSERT INTO exams (
                    ts, student, topic, status, solved, total, skipped, problem_ids, updated,
                    student_id, exam_seed, skipped_ids, finished_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    float(item.get("ts") or time.time()),
                    student,
                    str(item.get("topic") or "")[:80],
                    "left" if item.get("status") == "live" else str(item.get("status") or "left")[:20],
                    int(item.get("solved") or 0),
                    int(item.get("total") or 0),
                    int(item.get("skipped") or 0),
                    json.dumps(item.get("problem_ids") or [], ensure_ascii=False)
                    if not isinstance(item.get("problem_ids"), str)
                    else item.get("problem_ids"),
                    float(item.get("updated") or time.time()),
                    sid,
                    str(item.get("exam_seed") or item.get("seed") or ""),
                    json.dumps(item.get("skipped_ids") or [], ensure_ascii=False)
                    if not isinstance(item.get("skipped_ids"), str)
                    else item.get("skipped_ids") or "[]",
                    item.get("finished_at"),
                ),
            )
        conn.commit()
    revoke_restored_sessions()
    return {"inserted": inserted, "skipped": skipped}


def import_journal(text: str, kind: str = "csv") -> dict[str, Any]:
    raw = text or ""
    if len(raw) > 8_000_000:
        return {"inserted": 0, "skipped": 0, "detail": "file too large"}
    rows: list[dict[str, Any]] = []
    mode = (kind or "csv").lower()
    if mode == "json":
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return {"inserted": 0, "skipped": 0, "detail": "bad json"}
        if isinstance(payload, dict) and payload.get("format") == "informatics-checker-backup":
            return restore_backup_json(payload)
        if isinstance(payload, dict) and isinstance(payload.get("students"), list) and "attempts" not in payload:
            return {"inserted": 0, "skipped": 0, "detail": "need attempt list"}
        items = payload if isinstance(payload, list) else payload.get("attempts") if isinstance(payload, dict) else []
        if not isinstance(items, list):
            return {"inserted": 0, "skipped": 0, "detail": "need attempt list"}
        for item in items:
            if isinstance(item, dict):
                rows.append(item)
    else:
        sample = raw.lstrip("\ufeff")
        reader = csv.DictReader(io.StringIO(sample), delimiter=";")
        if not reader.fieldnames:
            return {"inserted": 0, "skipped": 0, "detail": "empty csv"}
        for item in reader:
            rows.append(item)

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
            sid = _get_or_create_student(conn, student)
            row = conn.execute(
                "SELECT COALESCE(MAX(attempt_no), 0) AS n FROM attempts WHERE student_id = ? AND problem_id = ?",
                (sid, problem_id),
            ).fetchone()
            attempt_no = int(row["n"] if row else 0) + 1
            conn.execute(
                """
                INSERT INTO attempts (
                    ts, student, problem_id, status, passed, total, message, code, student_id, attempt_no
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (stamp, student, problem_id, status, passed, total, message, code, sid, attempt_no),
            )
            inserted += 1
        conn.commit()
    return {"inserted": inserted, "skipped": skipped}
