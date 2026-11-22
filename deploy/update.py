#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deploy the checker on the host into /opt/informatics-checker.

Run it on the server, from any directory:

    bash deploy/update.sh             # update from origin/main
    bash deploy/update.sh --rollback  # go back to the previous commit
    bash deploy/update.sh --backup    # only copy the database

The database in /var/lib/informatics-checker is never touched.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

APP = Path("/opt/informatics-checker")
VENV = APP / ".venv"
BACKUPS = Path("/root/backups/informatics-checker")
SERVICE = "informatics-checker"
BRANCH = "main"


def run(*command: str, check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(command), flush=True)
    return subprocess.run(command, cwd=str(APP), check=check, text=True)


def health() -> bool:
    return run("curl", "-fsS", "--max-time", "10", "http://127.0.0.1/health", check=False).returncode == 0


def previous_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD~1"], cwd=str(APP), capture_output=True, text=True, check=False
    )
    return result.stdout.strip()


def release(rollback: bool) -> int:
    if not APP.is_dir():
        print("NO_APP_DIR " + str(APP), file=sys.stderr)
        return 2
    if rollback:
        target = previous_commit()
        if not target:
            print("NO_HISTORY", file=sys.stderr)
            return 2
        print("ROLLBACK " + target)
        run("git", "reset", "--hard", target)
    else:
        run("git", "fetch", "origin")
        run("git", "reset", "--hard", "origin/" + BRANCH)
    run("chown", "-R", "checker:checker", str(APP))
    if (APP / "requirements.txt").exists():
        run(str(VENV / "bin/python"), "-m", "pip", "install", "-q", "-r", "requirements.txt")
    run(str(VENV / "bin/python"), "-m", "compileall", "-q", "checker", "app.py")
    run("systemctl", "restart", SERVICE)
    if health():
        print("OK service answers /health")
        return 0
    print("NO_HEALTH", file=sys.stderr)
    run("journalctl", "-u", SERVICE, "-n", "40", "--no-pager", check=False)
    return 1


def backup() -> int:
    """A database copy made before a risky release, kept off the web root."""
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = subprocess.run(
        ["date", "+%F-%H%M"], capture_output=True, text=True, check=True
    ).stdout.strip()
    target = BACKUPS / ("checker-" + stamp + ".sqlite3")
    code = (
        "import sqlite3, sys\n"
        "source = sqlite3.connect('/var/lib/informatics-checker/checker.sqlite3')\n"
        "target = sqlite3.connect(sys.argv[1])\n"
        "source.backup(target)\n"
        "target.close()\n"
        "source.close()\n"
    )
    run(str(VENV / "bin/python"), "-c", code, str(target))
    print("BACKUP " + str(target))
    return 0


def main() -> int:
    if os.geteuid() != 0:
        print("NEED_ROOT", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description="Deploy the informatics checker.")
    parser.add_argument("--rollback", action="store_true", help="previous commit")
    parser.add_argument("--backup", action="store_true", help="database copy only")
    args = parser.parse_args()
    if args.backup:
        return backup()
    return release(args.rollback)


if __name__ == "__main__":
    raise SystemExit(main())
