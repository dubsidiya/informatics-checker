#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end smoke against a running checker instance.

Drives the full classroom flow over plain HTTP, the same way a browser does:

  student session -> check a problem -> progress -> exam start/finish
  -> teacher login -> summary -> CSV export -> logout.

Usage:
    python3 tools/e2e_smoke.py [base_url]
    # base_url defaults to http://127.0.0.1:8765
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765").rstrip("/")
PIN = "test-teacher-pin"


def request(method, path, body=None, cookie="", csrf=""):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {}
    if data:
        headers["Content-Type"] = "application/json"
    # Act like the site's own browser: cross-origin POSTs are rejected by
    # design, and inside Docker the client address is the bridge IP, not
    # loopback, so no-Origin requests would be (correctly) refused.
    if method == "POST":
        headers["Origin"] = BASE
    if cookie:
        headers["Cookie"] = cookie
    if csrf:
        headers["X-CSRF-Token"] = csrf
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as error:
        # 401/403/4xx are expected outcomes for the negative checks.
        resp = error
    with resp:
        raw = resp.read()
        text = raw.decode("utf-8")
        raw_headers = resp.headers.items()
    set_cookies = [value for key, value in raw_headers if key.lower() == "set-cookie"]
    payload = json.loads(text) if text else {}
    return resp.status, set_cookies, payload


def cookie_value(set_cookies, name):
    for line in set_cookies:
        if line.startswith(name + "="):
            return line.split(";", 1)[0]
    return ""


def wait_ready(timeout=60.0):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            status, _, payload = request("GET", "/readyz")
            if status == 200 and payload.get("ok"):
                return
            last = payload
        except (urllib.error.URLError, OSError) as exc:
            # The container port can reset while the app is still booting.
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(1.0)
    raise SystemExit(f"instance not ready within {timeout}s: {last}")


def main():
    failures = []

    def check(label, ok, detail=""):
        print(("ok  " if ok else "FAIL  ") + label + ("" if ok or not detail else " -- " + detail))
        if not ok:
            failures.append(f"{label}: {detail}")

    wait_ready()

    # Anonymous: login-required endpoints must refuse.
    status, _, _ = request("GET", "/api/teacher/summary")
    check("teacher summary needs login", status == 401, str(status))
    status, _, _ = request("POST", "/api/check", {"problem_id": "sum-two", "code": "print(1)"})
    check("check needs a name", status == 401, str(status))

    # Catalog.
    status, _, problems = request("GET", "/api/problems")
    check("problems catalog", status == 200 and len(problems) >= 30, str(status))
    status, _, topic_cards = request("GET", "/api/topics")
    check("topic cards", status == 200 and len(topic_cards) >= 5, str(status))

    # Student session + solve.
    status, cookies, payload = request("POST", "/api/student/session", {"student": "Smoke Student"})
    check("student session", status == 200 and payload.get("csrf"), str(status))
    student_cookie = cookie_value(cookies, "student")
    student_csrf = payload.get("csrf", "")

    status, _, result = request(
        "POST",
        "/api/check",
        {
            "problem_id": "sum-two",
            "code": "a, b = map(int, input().split())\nprint(a + b)\n",
        },
        cookie=student_cookie,
        csrf=student_csrf,
    )
    check("correct solution passes", status == 200 and result.get("status") == "ok", json.dumps(result)[:200])

    status, _, wrong = request(
        "POST",
        "/api/check",
        {"problem_id": "sum-two", "code": "print(int(input()) + int(input()) + 1)\n"},
        cookie=student_cookie,
        csrf=student_csrf,
    )
    check(
        "wrong solution fails with explanation",
        status == 200 and wrong.get("status") == "fail" and wrong.get("explanation", {}).get("what"),
        json.dumps(wrong)[:200],
    )

    status, _, progress = request("GET", "/api/progress", cookie=student_cookie)
    check(
        "progress records the solve",
        status == 200 and "sum-two" in progress.get("solved", []),
        json.dumps(progress)[:200],
    )

    # Exam flow.
    status, _, exam = request(
        "POST",
        "/api/exam",
        {"action": "start", "topic": "?????"},
        cookie=student_cookie,
        csrf=student_csrf,
    )
    check("exam starts", status == 200 and exam.get("status") == "live", json.dumps(exam)[:200])
    status, _, exam = request(
        "POST",
        "/api/exam",
        {"action": "finish"},
        cookie=student_cookie,
        csrf=student_csrf,
    )
    check("exam finishes", status == 200 and exam.get("status") == "done", json.dumps(exam)[:200])

    # CSRF must be enforced.
    status, _, _ = request("POST", "/api/check", {"problem_id": "sum-two", "code": "print(1)"}, cookie=student_cookie)
    check("check without csrf is rejected", status == 403, str(status))

    # Teacher flow.
    status, cookies, payload = request("POST", "/api/teacher/login", {"pin": PIN})
    check("teacher login", status == 200 and payload.get("ok"), str(status))
    teacher_cookie = cookie_value(cookies, "teacher")
    teacher_csrf = payload.get("csrf", "")

    status, _, summary = request("GET", "/api/teacher/summary", cookie=teacher_cookie)
    check(
        "teacher summary sees the student",
        status == 200 and summary.get("total_students", 0) >= 1,
        json.dumps(summary)[:200],
    )

    req = urllib.request.Request(
        BASE + "/api/teacher/export.csv",
        data=b"{}",
        headers={
            "Content-Type": "application/json",
            "Origin": BASE,
            "Cookie": teacher_cookie,
            "X-CSRF-Token": teacher_csrf,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        csv_body = resp.read().decode("utf-8")
        check("csv export has the student", "Smoke Student" in csv_body)

    status, _, _ = request("POST", "/api/teacher/logout", cookie=teacher_cookie, csrf=teacher_csrf)
    check("teacher logout", status == 200, str(status))
    status, _, _ = request("GET", "/api/teacher/summary", cookie=teacher_cookie)
    check("teacher session revoked after logout", status == 401, str(status))

    if failures:
        raise SystemExit("e2e smoke failed:\n" + "\n".join(failures))
    print("e2e smoke ok")


if __name__ == "__main__":
    main()
