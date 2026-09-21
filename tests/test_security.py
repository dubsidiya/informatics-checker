# -*- coding: utf-8 -*-
import io
import json
import os
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock

os.environ["CHECKER_ENV"] = "test"
os.environ["CHECKER_RUNNER"] = "local"
os.environ.setdefault("TEACHER_PIN", "test-teacher-pin")

from checker.auth import hash_pin, verify_pin
from checker.backup import restore_sqlite, sqlite_backup
from checker.catalog import validate_catalog
from checker.config import reset_config
from checker.http_security import client_ip, parse_content_length
from checker.judge0 import Judge0Runner
from checker.problems import all_problems
from checker.runner import ExecutionRequest, RunnerError, set_runner
from checker.store import (
    create_student_session,
    export_backup_json,
    get_student_session,
    init_store,
    record_attempt,
    reset_ready,
    restore_backup_json,
    revoke_restored_sessions,
)


class AuthCryptoTests(unittest.TestCase):
    def test_scrypt_pin(self):
        encoded = hash_pin("secret-pin")
        self.assertTrue(encoded.startswith("scrypt$"))
        self.assertTrue(verify_pin("secret-pin", encoded))
        self.assertFalse(verify_pin("other", encoded))


class HttpSecurityUnitTests(unittest.TestCase):
    def test_negative_content_length(self):
        self.assertIsNone(parse_content_length("-3"))
        self.assertIsNone(parse_content_length("1.5"))
        self.assertEqual(parse_content_length("12"), 12)
        self.assertEqual(parse_content_length(None), 0)

    def test_untrusted_forwarded_ip_ignored(self):
        self.assertEqual(client_ip("203.0.113.9", "1.2.3.4", ("10.0.0.0/8",)), "203.0.113.9")
        self.assertEqual(client_ip("10.1.2.3", "203.0.113.9, 10.1.2.3", ("10.0.0.0/8",)), "203.0.113.9")


class CatalogTests(unittest.TestCase):
    def test_no_single_hidden_oracle_in_examples(self):
        self.assertEqual(validate_catalog(all_problems()), [])


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.prev = os.environ.get("CHECKER_DB")
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        os.environ["CHECKER_DB"] = self.tmp.name
        reset_ready()
        init_store()

    def tearDown(self):
        reset_ready()
        if self.prev is None:
            os.environ.pop("CHECKER_DB", None)
        else:
            os.environ["CHECKER_DB"] = self.prev
        Path(self.tmp.name).unlink(missing_ok=True)
        for extra in (self.tmp.name + "-wal", self.tmp.name + "-shm"):
            Path(extra).unlink(missing_ok=True)

    def test_json_backup_keeps_code_and_revokes_sessions(self):
        record_attempt("Ira", "sum-two", "ok", 2, 2, "ok", "print(1+1)")
        session = create_student_session("Ira")
        self.assertIsNotNone(get_student_session(session["token"]))
        payload = export_backup_json()
        self.assertEqual(payload["format"], "informatics-checker-backup")
        self.assertTrue(any(item.get("code") == "print(1+1)" for item in payload["attempts"]))
        restore_backup_json(payload)
        self.assertIsNone(get_student_session(session["token"]))

    def test_sqlite_backup_roundtrip(self):
        record_attempt("Oleg", "sum-two", "fail", 0, 2, "no", "print(0)")
        dest = Path(self.tmp.name + ".copy")
        sqlite_backup(dest)
        restore_sqlite(dest)
        dest.unlink(missing_ok=True)


class RunnerContractTests(unittest.TestCase):
    def tearDown(self):
        set_runner(None)
        reset_config()

    def test_judge0_batch_without_expected_output(self):
        created = {}

        class Resp:
            def __init__(self, payload, status=200):
                self._payload = json.dumps(payload).encode("utf-8")
                self.status = status

            def read(self):
                return self._payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        class Opener:
            def open(self, req, timeout=0):
                url = req.full_url
                if req.get_method() == "POST" and "/submissions/batch" in url:
                    body = json.loads(req.data.decode("utf-8"))
                    created["body"] = body
                    return Resp([{"token": "aaa"}])
                if req.get_method() == "GET" and "/submissions/batch" in url:
                    return Resp(
                        {
                            "submissions": [
                                {
                                    "token": "aaa",
                                    "status_id": 3,
                                    "stdout": "NQo=",
                                    "stderr": "",
                                    "exit_code": 0,
                                }
                            ]
                        }
                    )
                raise AssertionError(url)

        os.environ["JUDGE0_URL"] = "https://judge.example.internal"
        os.environ["JUDGE0_AUTH_TOKEN"] = "secret"
        reset_config()
        from checker.config import get_config

        runner = Judge0Runner(get_config(), opener=Opener())
        results = runner.run_many([ExecutionRequest(source="print(1)\n", stdin="", timeout_seconds=1.0)])
        self.assertEqual(results[0].returncode, 0)
        submission = created["body"]["submissions"][0]
        self.assertNotIn("expected_output", submission)
        self.assertFalse(submission["enable_network"])
        os.environ.pop("JUDGE0_URL", None)
        os.environ.pop("JUDGE0_AUTH_TOKEN", None)

    def test_private_judge0_language_ready(self):
        url = os.environ.get("JUDGE0_INTEGRATION_URL")
        token = os.environ.get("JUDGE0_INTEGRATION_TOKEN")
        if not url or not token:
            self.skipTest("private Judge0 endpoint is not configured")
        os.environ["JUDGE0_URL"] = url
        os.environ["JUDGE0_AUTH_TOKEN"] = token
        reset_config()
        from checker.config import get_config
        from checker.judge0 import Judge0Runner

        ok, detail = Judge0Runner(get_config()).ready()
        self.assertTrue(ok, detail)

    def test_judge0_https_required_in_production(self):
        os.environ["CHECKER_ENV"] = "production"
        os.environ["JUDGE0_URL"] = "http://judge.example.internal"
        os.environ["JUDGE0_AUTH_TOKEN"] = "secret"
        reset_config()
        from checker.config import get_config

        runner = Judge0Runner(get_config(), opener=MagicMock())
        with self.assertRaises(RunnerError):
            runner.run_many([ExecutionRequest(source="print(1)\n", stdin="", timeout_seconds=1.0)])
        os.environ["CHECKER_ENV"] = "test"
        os.environ.pop("JUDGE0_URL", None)
        os.environ.pop("JUDGE0_AUTH_TOKEN", None)
        reset_config()


class PerimeterApiTests(unittest.TestCase):
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

    def _raw(self, method, path, body=b"", headers=None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        try:
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            data = raw.decode("utf-8")
        return response.status, data

    def _json(self, method, path, body=None, cookie="", csrf=""):
        extra = {}
        payload = None
        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            extra["Content-Type"] = "application/json"
            extra["Content-Length"] = str(len(payload))
        if cookie:
            extra["Cookie"] = cookie
        if csrf:
            extra["X-CSRF-Token"] = csrf
        return self._raw(method, path, payload or b"", extra)

    def test_negative_content_length_rejected(self):
        status, data = self._raw("POST", "/api/check", b"{}", {"Content-Length": "-3", "Content-Type": "application/json"})
        self.assertEqual(status, 400)

    def test_csrf_required_for_check(self):
        status, headers_data = self._json("POST", "/api/student/session", {"student": "Csrf User"})
        self.assertEqual(status, 200)
        cookie = ""
        # headers not returned; use second request via HTTPConnection in _json without csrf
        conn = HTTPConnection("127.0.0.1", self.port, timeout=30)
        payload = json.dumps({"student": "Csrf User"}).encode("utf-8")
        conn.request("POST", "/api/student/session", body=payload, headers={"Content-Type": "application/json", "Content-Length": str(len(payload))})
        response = conn.getresponse()
        raw = json.loads(response.read().decode("utf-8"))
        cookie = ""
        for key, value in response.getheaders():
            if key.lower() == "set-cookie" and value.startswith("student="):
                cookie = value.split(";", 1)[0]
        conn.close()
        status, data = self._json("POST", "/api/check", {"problem_id": "sum-two", "code": "print(1)"}, cookie=cookie)
        self.assertEqual(status, 403)

    def test_exam_restore_does_not_need_second_start(self):
        payload = json.dumps({"student": "Exam Restore"}).encode("utf-8")
        conn = HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.request("POST", "/api/student/session", body=payload, headers={"Content-Type": "application/json", "Content-Length": str(len(payload))})
        response = conn.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        cookie = ""
        for key, value in response.getheaders():
            if key.lower() == "set-cookie" and value.startswith("student="):
                cookie = value.split(";", 1)[0]
        conn.close()
        status, exam = self._json("POST", "/api/exam", {"action": "start", "topic": "ЕГЭ 17"}, cookie=cookie, csrf=data["csrf"])
        self.assertEqual(status, 200)
        first_ids = exam["problem_ids"]
        status, me = self._json("GET", "/api/student/me", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertEqual(me["exam"]["problem_ids"], first_ids)
        status, again = self._json("POST", "/api/exam", {"action": "start", "topic": "ЕГЭ 17"}, cookie=cookie, csrf=data["csrf"])
        self.assertEqual(status, 200)
        self.assertEqual(again["problem_ids"], first_ids)


if __name__ == "__main__":
    unittest.main()
