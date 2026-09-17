# -*- coding: utf-8 -*-
import json
import os
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

from checker.explain import deepen_explanation
from checker.grade import grade_solution
from checker.problems import get_problem
from checker.store import (
    import_journal,
    record_attempt,
    reset_ready,
    start_exam,
    student_progress,
    summarize,
    update_exam,
)
from checker.topics import list_topic_cards, retry_how, topic_brief


class TopicBriefTests(unittest.TestCase):
    def test_ege17_has_pair_hint(self):
        card = topic_brief("\u0415\u0413\u042d 17")
        blob = card["what"] + " ".join(card["steps"]) + card["watch"]
        self.assertIn("\u043f\u0430\u0440", blob.lower())
        self.assertGreaterEqual(len(card["steps"]), 3)

    def test_catalog_covers_ege_topics(self):
        names = {item["topic"] for item in list_topic_cards()}
        for topic in (
            "\u0415\u0413\u042d 8",
            "\u0415\u0413\u042d 9",
            "\u0415\u0413\u042d 13",
            "\u0415\u0413\u042d 14",
            "\u0415\u0413\u042d 16",
            "\u0415\u0413\u042d 17",
            "\u0415\u0413\u042d 23",
            "\u0415\u0413\u042d 25",
        ):
            self.assertIn(topic, names)


class RetryExplainTests(unittest.TestCase):
    def test_third_try_adds_simpler_how(self):
        problem = get_problem("sum-two")
        result = grade_solution(problem, "a, b = input().split()\nprint(a + b)\n")
        self.assertEqual(result.status, "fail")
        first = result.explanation.how
        deepen_explanation(problem, result, 3)
        self.assertEqual(result.tries, 3)
        self.assertGreater(len(result.explanation.how), len(first))
        self.assertIn(
            "\u0443\u0436\u0435 \u043f\u0440\u043e\u0432\u0435\u0440\u044f\u043b",
            result.explanation.how,
        )

    def test_retry_how_empty_on_first(self):
        problem = get_problem("sum-two")
        self.assertEqual(retry_how(problem, 1), "")


class StoreClassroomTests(unittest.TestCase):
    def setUp(self):
        self.prev = os.environ.get("CHECKER_DB")
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        os.environ["CHECKER_DB"] = self.tmp.name
        reset_ready()

    def tearDown(self):
        reset_ready()
        if self.prev is None:
            os.environ.pop("CHECKER_DB", None)
        else:
            os.environ["CHECKER_DB"] = self.prev
        Path(self.tmp.name).unlink(missing_ok=True)
        for extra in (self.tmp.name + "-wal", self.tmp.name + "-shm"):
            Path(extra).unlink(missing_ok=True)

    def test_progress_counts_fails(self):
        record_attempt("Masha", "sum-two", "fail", 0, 2, "no", "print(1)")
        record_attempt("Masha", "sum-two", "fail", 1, 2, "no", "print(1)")
        progress = student_progress("Masha")
        self.assertEqual(progress["problems"]["sum-two"]["fails"], 2)
        self.assertFalse(progress["problems"]["sum-two"]["solved"])

    def test_stuck_after_three_fails(self):
        for _ in range(3):
            record_attempt("Petya", "sum-two", "fail", 0, 2, "no", "print(1)")
        board = summarize()
        self.assertTrue(any(item["student"] == "Petya" for item in board["stuck"]))

    def test_exam_live_and_finish(self):
        start_exam("Anya", "\u0415\u0413\u042d 17", ["ege17-271", "ege17-1"])
        live = summarize()["exams"]["live"]
        self.assertEqual(live[0]["student"], "Anya")
        self.assertEqual(live[0]["total"], 2)
        done = update_exam("Anya", solved=2, total=2, status="done")
        self.assertEqual(done["status"], "done")
        self.assertFalse(summarize()["exams"]["live"])

    def test_import_csv_roundtrip(self):
        header = "\u0432\u0440\u0435\u043c\u044f;\u0443\u0447\u0435\u043d\u0438\u043a;\u0437\u0430\u0434\u0430\u0447\u0430;\u0441\u0442\u0430\u0442\u0443\u0441;\u043f\u0440\u043e\u0439\u0434\u0435\u043d\u043e;\u0432\u0441\u0435\u0433\u043e;\u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435"
        csv_text = "\ufeff" + header + "\n2024-01-02 10:00:00;CSV User;sum-two;ok;5;5;ok\n"
        result = import_journal(csv_text, "csv")
        self.assertEqual(result["inserted"], 1)
        board = summarize()
        self.assertTrue(any(item["name"] == "CSV User" for item in board["students"]))


class ClassroomApiTests(unittest.TestCase):
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

    def _request(self, method, path, body=None, cookie=""):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=30)
        extra = {}
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

    def _login(self):
        status, headers, data = self._request("POST", "/api/teacher/login", {"pin": self.pin})
        self.assertEqual(status, 200)
        cookie = ""
        for key, value in headers:
            if key.lower() == "set-cookie" and value.startswith("teacher="):
                cookie = value.split(";", 1)[0]
                break
        self.assertTrue(cookie)
        return cookie

    def test_topics_endpoint(self):
        status, _, data = self._request("GET", "/api/topics")
        self.assertEqual(status, 200)
        self.assertGreaterEqual(len(data), 8)
        self.assertIn("steps", data[0])

    def test_exam_start_and_tries(self):
        status, _, exam = self._request(
            "POST",
            "/api/exam",
            {
                "student": "Exam User",
                "action": "start",
                "topic": "\u0415\u0413\u042d 17",
                "ids": ["ege17-271"],
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(exam["status"], "live")
        status, _, fail = self._request(
            "POST",
            "/api/check",
            {"problem_id": "sum-two", "code": "a, b = input().split()\nprint(a + b)\n", "student": "Exam User"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(fail["tries"], 1)
        status, _, fail2 = self._request(
            "POST",
            "/api/check",
            {"problem_id": "sum-two", "code": "a, b = input().split()\nprint(a + b)\n", "student": "Exam User"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(fail2["tries"], 2)
        self.assertIn(
            "\u0443\u0436\u0435 \u043f\u0440\u043e\u0432\u0435\u0440\u044f\u043b",
            fail2["explanation"]["how"],
        )

    def test_teacher_import_json(self):
        cookie = self._login()
        payload = [
            {
                "student": "Restored",
                "problem_id": "sum-two",
                "status": "ok",
                "passed": 5,
                "total": 5,
                "message": "ok",
                "ts": 1_700_000_100,
            }
        ]
        status, _, data = self._request(
            "POST",
            "/api/teacher/import",
            {"format": "json", "text": json.dumps(payload)},
            cookie=cookie,
        )
        self.assertEqual(status, 200)
        self.assertGreaterEqual(data["inserted"], 1)
        status, _, summary = self._request("GET", "/api/teacher/summary", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(any(item["name"] == "Restored" for item in summary["students"]))
        self.assertIn("stuck", summary)
        self.assertIn("exams", summary)


if __name__ == "__main__":
    unittest.main()
