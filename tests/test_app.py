# -*- coding: utf-8 -*-
import json
import os
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import Handler, TEACHER_PIN
from checker.store import reset_ready


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.tmp.close()
        os.environ["CHECKER_DB"] = cls.tmp.name
        reset_ready()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.host, cls.port = cls.server.server_address

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        reset_ready()
        os.environ.pop("CHECKER_DB", None)
        Path(cls.tmp.name).unlink(missing_ok=True)

    def request(self, method, path, body=None, headers=None, cookie=""):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=20)
        hdrs = dict(headers or {})
        if cookie:
            hdrs["Cookie"] = cookie
        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
            hdrs["Content-Length"] = str(len(payload))
        conn.request(method, path, body=payload, headers=hdrs)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        data = json.loads(raw.decode("utf-8")) if raw else None
        return response.status, data, response.getheader("Set-Cookie")

    def test_health(self):
        status, data, _ = self.request("GET", "/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])

    def test_check_hides_secret_tests(self):
        status, data, _ = self.request(
            "POST",
            "/api/check",
            {
                "problem_id": "sum-two",
                "student": "Тест",
                "code": "a, b = map(int, input().split())\ns = a + b\nprint(1 if s == 0 else s)\n",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "fail")
        hidden = [item for item in data["tests"] if item["hidden"]]
        self.assertTrue(hidden)
        for item in hidden:
            self.assertEqual(item["stdin"], "")
            self.assertEqual(item["expected"], "")
            self.assertEqual(item["got"], "")

    def test_teacher_board_needs_pin(self):
        status, data, _ = self.request("GET", "/api/teacher/summary")
        self.assertEqual(status, 401)
        self.assertIn("вход", data["detail"])

    def test_teacher_login_and_attempts(self):
        status, data, cookie = self.request("POST", "/api/teacher/login", {"pin": TEACHER_PIN})
        self.assertEqual(status, 200)
        self.assertTrue(data["ok"])
        self.assertTrue(cookie)
        token = cookie.split(";", 1)[0]
        status, summary, _ = self.request("GET", "/api/teacher/summary", cookie=token)
        self.assertEqual(status, 200)
        self.assertGreaterEqual(summary["total_attempts"], 1)


if __name__ == "__main__":
    unittest.main()
