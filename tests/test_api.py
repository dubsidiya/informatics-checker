# -*- coding: utf-8 -*-
import json
import os
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from checker.store import record_attempt, reset_ready


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.tmp.close()
        os.environ["CHECKER_DB"] = cls.tmp.name
        reset_ready()
        from app import Handler, _teacher_pin

        cls.pin = _teacher_pin()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        reset_ready()
        os.environ.pop("CHECKER_DB", None)
        Path(cls.tmp.name).unlink(missing_ok=True)
        for extra in (cls.tmp.name + "-wal", cls.tmp.name + "-shm"):
            Path(extra).unlink(missing_ok=True)

    def _request(self, method, path, body=None, headers=None, cookie=""):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=30)
        extra = dict(headers or {})
        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            extra["Content-Type"] = "application/json"
            extra["Content-Length"] = str(len(payload))
        if cookie:
            extra["Cookie"] = cookie
        conn.request(method, path, body=payload, headers=extra)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        text = raw.decode("utf-8")
        try:
            data = json.loads(text) if text else {}
        except json.JSONDecodeError:
            data = text
        return response.status, response.getheaders(), data

    def test_health(self):
        status, _, data = self._request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertTrue(data.get("ok"))

    def test_problems_catalog(self):
        status, _, data = self._request("GET", "/api/problems")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(data), 30)
        self.assertIn("id", data[0])

    def test_check_requires_name(self):
        status, _, data = self._request(
            "POST",
            "/api/check",
            {"problem_id": "sum-two", "code": "print(1)", "student": "  "},
        )
        self.assertEqual(status, 400)
        self.assertIn("\u0438\u043c\u044f", data["detail"].lower())

    def test_check_accepts_correct_sum(self):
        status, _, data = self._request(
            "POST",
            "/api/check",
            {
                "problem_id": "sum-two",
                "code": "a, b = map(int, input().split())\nprint(a + b)\n",
                "student": "Api User",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")

    def test_progress_after_solve(self):
        name = "Progress Katya"
        status, _, data = self._request(
            "POST",
            "/api/check",
            {
                "problem_id": "sum-two",
                "code": "a, b = map(int, input().split())\nprint(a + b)\n",
                "student": name,
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")
        status, _, progress = self._request("GET", f"/api/progress?student={quote(name)}")
        self.assertEqual(status, 200)
        self.assertIn("sum-two", progress.get("solved", []))

    def test_hidden_answer_not_in_http(self):
        status, _, data = self._request(
            "POST",
            "/api/check",
            {"problem_id": "ege17-271", "code": "print(2, -13)\n", "student": "Hidden User"},
        )
        self.assertEqual(status, 200)
        blob = json.dumps(data, ensure_ascii=False)
        self.assertNotIn("792 -587", blob)
        self.assertNotIn("-587", blob)

    def test_teacher_summary_needs_login(self):
        status, _, data = self._request("GET", "/api/teacher/summary")
        self.assertEqual(status, 401)

    def test_teacher_login_and_export(self):
        record_attempt("Export User", "sum-two", "ok", 5, 5, "ok", "print(1)")
        status, headers, data = self._request("POST", "/api/teacher/login", {"pin": self.pin})
        self.assertEqual(status, 200)
        self.assertTrue(data.get("ok"))
        cookie = ""
        for key, value in headers:
            if key.lower() == "set-cookie" and value.startswith("teacher="):
                cookie = value.split(";", 1)[0]
                break
        self.assertTrue(cookie)
        status, _, summary = self._request("GET", "/api/teacher/summary", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(summary["total_students"], 1)
        status, _, body = self._request("GET", "/api/teacher/export.csv", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertIn("Export User", body)


if __name__ == "__main__":
    unittest.main()
