from __future__ import annotations

import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from checker.llm_gateway import GatewayHandler


class _Ollama(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or "0")
        incoming = json.loads(self.rfile.read(length).decode("utf-8"))
        body = json.dumps({"message": {"role": "assistant", "content": "наводка"}, "model": incoming.get("model")}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self._old_token = os.environ.get("LLM_TOKEN")
        self._old_ollama = os.environ.get("OLLAMA_URL")
        upstream = ThreadingHTTPServer(("127.0.0.1", 0), _Ollama)
        self.upstream = upstream
        self.upstream_thread = threading.Thread(target=upstream.serve_forever, daemon=True)
        self.upstream_thread.start()
        os.environ["OLLAMA_URL"] = f"http://127.0.0.1:{upstream.server_address[1]}"
        os.environ["LLM_TOKEN"] = "test-token"
        self.gateway = ThreadingHTTPServer(("127.0.0.1", 0), GatewayHandler)
        self.gateway_thread = threading.Thread(target=self.gateway.serve_forever, daemon=True)
        self.gateway_thread.start()
        self.base = f"http://127.0.0.1:{self.gateway.server_address[1]}"

    def tearDown(self):
        self.gateway.shutdown()
        self.upstream.shutdown()
        if self._old_token is None:
            os.environ.pop("LLM_TOKEN", None)
        else:
            os.environ["LLM_TOKEN"] = self._old_token
        if self._old_ollama is None:
            os.environ.pop("OLLAMA_URL", None)
        else:
            os.environ["OLLAMA_URL"] = self._old_ollama

    def test_chat_requires_the_token_and_forwards_only_that_route(self):
        body = json.dumps({"model": "mimo-v2.6", "messages": [{"role": "user", "content": "привет"}]}).encode()
        with self.assertRaises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(urllib.request.Request(self.base + "/api/chat", data=body, method="POST"), timeout=3)
        self.assertEqual(denied.exception.code, 401)

        request = urllib.request.Request(
            self.base + "/api/chat",
            data=body,
            headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            payload = json.loads(response.read().decode())
        self.assertEqual(payload["message"]["content"], "наводка")
        self.assertEqual(payload["model"], "mimo-v2.6")

        blocked = urllib.request.Request(
            self.base + "/api/pull",
            data=body,
            headers={"Authorization": "Bearer test-token"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as missing:
            urllib.request.urlopen(blocked, timeout=3)
        self.assertEqual(missing.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
