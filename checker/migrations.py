from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable

CURRENT_SCHEMA_VERSION = 3


class MigrationError(RuntimeError):
    """Raised when a database cannot be migrated safely."""


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not _table_exists(conn, table):
        return set()
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}


def _add_column(conn: sqlite3.Connection, table: str, definition: str) -> None:
    name = definition.split(maxsplit=1)[0].strip('"')
    if name not in _columns(conn, table):
        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN {definition}')


def _normalise_name(value: object) -> tuple[str, str]:
    display = " ".join(str(value or "").split())[:80] or "без имени"
    return display, display.casefold()


def _legacy_student_id(normalised_name: str) -> str:
    digest = hashlib.sha256(
        ("informatics-checker:legacy-student:" + normalised_name).encode("utf-8")
    ).hexdigest()
    return f"legacy-{digest[:40]}"


def _migration_1(conn: sqlite3.Connection) -> None:
    """Create the historical schema for new databases."""
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attempts_student ON attempts(student)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_attempts_problem ON attempts(problem_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_attempts_student_problem "
        "ON attempts(student, problem_id, ts)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_exams_student ON exams(student, updated)"
    )


def _migration_2(conn: sqlite3.Connection) -> None:
    """Add stable student identities and revocable hashed sessions."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            created_at REAL NOT NULL,
            legacy INTEGER NOT NULL DEFAULT 0 CHECK (legacy IN (0, 1))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS teacher_sessions (
            id TEXT PRIMARY KEY,
            token_hash TEXT NOT NULL UNIQUE,
            csrf_hash TEXT NOT NULL,
            credential_fingerprint TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            revoked_at REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS student_sessions (
            id TEXT PRIMARY KEY,
            student_id TEXT NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            csrf_hash TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            revoked_at REAL
        )
        """
    )

    _add_column(
        conn,
        "attempts",
        "student_id TEXT REFERENCES students(id) ON DELETE RESTRICT",
    )
    _add_column(
        conn,
        "attempts",
        "student_session_id TEXT REFERENCES student_sessions(id) ON DELETE SET NULL",
    )
    _add_column(
        conn,
        "exams",
        "student_id TEXT REFERENCES students(id) ON DELETE RESTRICT",
    )
    _add_column(
        conn,
        "exams",
        "student_session_id TEXT REFERENCES student_sessions(id) ON DELETE SET NULL",
    )

    names: dict[str, tuple[str, float]] = {}
    for table, stamp_column in (("attempts", "ts"), ("exams", "ts")):
        if not _table_exists(conn, table):
            continue
        for raw_name, stamp in conn.execute(
            f'SELECT student, MIN("{stamp_column}") FROM "{table}" GROUP BY student'
        ):
            display, normalised = _normalise_name(raw_name)
            created = float(stamp or 0.0)
            previous = names.get(normalised)
            if previous is None or created < previous[1]:
                names[normalised] = (display, created)

    for normalised, (display, created_at) in names.items():
        conn.execute(
            """
            INSERT OR IGNORE INTO students
                (id, display_name, normalized_name, created_at, legacy)
            VALUES (?, ?, ?, ?, 1)
            """,
            (_legacy_student_id(normalised), display, normalised, created_at),
        )

    for table in ("attempts", "exams"):
        if not _table_exists(conn, table):
            continue
        raw_names = [
            row[0]
            for row in conn.execute(
                f'SELECT DISTINCT student FROM "{table}" WHERE student_id IS NULL'
            )
        ]
        for raw_name in raw_names:
            _, normalised = _normalise_name(raw_name)
            conn.execute(
                f'UPDATE "{table}" SET student_id = ? '
                "WHERE student_id IS NULL AND student = ?",
                (_legacy_student_id(normalised), raw_name),
            )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_students_normalized "
        "ON students(normalized_name)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_students_legacy_normalized "
        "ON students(normalized_name) WHERE legacy = 1"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_teacher_sessions_expiry "
        "ON teacher_sessions(expires_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_student_sessions_student "
        "ON student_sessions(student_id, expires_at)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_attempts_student_id "
        "ON attempts(student_id, ts)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_exams_student_id "
        "ON exams(student_id, updated)"
    )


def _migration_3(conn: sqlite3.Connection) -> None:
    """Add atomic attempt numbering and authoritative exam state."""
    _add_column(conn, "attempts", "attempt_no INTEGER")
    _add_column(conn, "attempts", "exam_id INTEGER REFERENCES exams(id) ON DELETE SET NULL")
    _add_column(conn, "exams", "skipped_ids TEXT NOT NULL DEFAULT '[]'")
    _add_column(conn, "exams", "exam_seed TEXT NOT NULL DEFAULT ''")
    _add_column(conn, "exams", "finished_at REAL")

    rows = conn.execute(
        """
        SELECT id, student_id, student, problem_id
        FROM attempts
        ORDER BY COALESCE(student_id, student), problem_id, ts, id
        """
    ).fetchall()
    counters: dict[tuple[str, str], int] = {}
    updates: list[tuple[int, int]] = []
    for attempt_id, student_id, student, problem_id in rows:
        key = (str(student_id or student), str(problem_id))
        counters[key] = counters.get(key, 0) + 1
        updates.append((counters[key], int(attempt_id)))
    if updates:
        conn.executemany(
            "UPDATE attempts SET attempt_no = ? WHERE id = ? AND attempt_no IS NULL",
            updates,
        )

    # Historical versions could leave several live rows for one student.
    conn.execute(
        """
        UPDATE exams
        SET status = 'left'
        WHERE status = 'live'
          AND student_id IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM exams AS newer
              WHERE newer.status = 'live'
                AND newer.student_id = exams.student_id
                AND (newer.updated > exams.updated
                     OR (newer.updated = exams.updated AND newer.id > exams.id))
          )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_attempts_number "
        "ON attempts(student_id, problem_id, attempt_no) "
        "WHERE student_id IS NOT NULL AND attempt_no IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_attempts_exam ON attempts(exam_id, status)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_exams_one_live_student "
        "ON exams(student_id) WHERE status = 'live' AND student_id IS NOT NULL"
    )


_MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _migration_1,
    2: _migration_2,
    3: _migration_3,
}


def schema_version(conn: sqlite3.Connection) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


def migrate(conn: sqlite3.Connection) -> int:
    """Migrate *conn* transactionally and return the current schema version."""
    version = schema_version(conn)
    if version > CURRENT_SCHEMA_VERSION:
        raise MigrationError(
            f"database schema v{version} is newer than supported "
            f"v{CURRENT_SCHEMA_VERSION}"
        )
    if version == CURRENT_SCHEMA_VERSION:
        return version

    try:
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        for target in range(version + 1, CURRENT_SCHEMA_VERSION + 1):
            migration = _MIGRATIONS.get(target)
            if migration is None:
                raise MigrationError(f"missing migration for schema v{target}")
            migration(conn)
            conn.execute(f"PRAGMA user_version = {target}")
        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise MigrationError("foreign key check failed after migration")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return CURRENT_SCHEMA_VERSION


def require_supported_schema(conn: sqlite3.Connection) -> int:
    version = schema_version(conn)
    if version != CURRENT_SCHEMA_VERSION:
        raise MigrationError(
            f"expected database schema v{CURRENT_SCHEMA_VERSION}, found v{version}"
        )
    return version
