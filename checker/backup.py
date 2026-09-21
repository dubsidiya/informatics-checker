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
    finally:
        check.close()
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
