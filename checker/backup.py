from __future__ import annotations

import sqlite3
from pathlib import Path

from checker.migrations import require_supported_schema
from checker.store import db_path, init_store, reset_ready, revoke_restored_sessions


def sqlite_backup(dest: Path) -> None:
    init_store()
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(db_path()))
    try:
        dst = sqlite3.connect(str(dest))
        try:
            src.backup(dst)
            row = dst.execute("PRAGMA integrity_check").fetchone()
            if not row or row[0] != "ok":
                raise RuntimeError("integrity_check failed")
        finally:
            dst.close()
    finally:
        src.close()


def restore_sqlite(src: Path) -> None:
    if not src.is_file():
        raise RuntimeError("backup missing")
    try:
        _validate_backup(src)
    except RuntimeError:
        raise
    except sqlite3.Error as exc:
        # Corrupt uploads must surface as a controlled restore error, not a 500.
        raise RuntimeError(f"backup unreadable: {exc}") from exc
    reset_ready()
    target = db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    incoming = sqlite3.connect(str(src))
    try:
        outgoing = sqlite3.connect(str(target))
        try:
            incoming.backup(outgoing)
        finally:
            outgoing.close()
    finally:
        incoming.close()
    reset_ready()
    init_store()
    conn = sqlite3.connect(str(target))
    try:
        require_supported_schema(conn)
    finally:
        conn.close()
    revoke_restored_sessions()


def _validate_backup(src: Path) -> None:
    """Full pre-swap validation of an uploaded SQLite backup."""
    check = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        row = check.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise RuntimeError("integrity_check failed")
        tables = {item[0] for item in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "attempts" not in tables:
            raise RuntimeError("backup schema missing attempts")
        # Verify the backup is on a supported schema version BEFORE we overwrite
        # the live database — otherwise a too-old backup would wipe the journal
        # and then fail, losing all current data.
        require_supported_schema(check)
        # Foreign keys must also be consistent before the swap: a restore that
        # silently breaks attempts -> students links would corrupt the journal
        # even though the schema version matches.
        violations = check.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError("backup has broken foreign keys")
    finally:
        check.close()
