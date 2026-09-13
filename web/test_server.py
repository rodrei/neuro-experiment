# -*- coding: utf-8 -*-
"""
Tests of the demo server:
    python3 -m unittest discover -s web -t . -v

They start the real server on an ephemeral port and hit it over HTTP, with no
outside network: the LLM transport is replaced with a fake one.
"""

import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from common import protocol
from web.server import app


def request(port, path, body=None):
    """Returns (status, json_object_or_text)."""
    url = "http://127.0.0.1:%d%s" % (port, path)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as e:
        with e:
            raw = e.read().decode("utf-8")
            status = e.code
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw


class ServerBase(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.server = app.create_server(0, data_dir=self.folder)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self._previous_code = app.ACCESS_CODE
        self._previous_transport = app.TRANSPORT
        self._previous_probe = app.PROBE_TRANSPORT

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.folder, ignore_errors=True)
        app.ACCESS_CODE = self._previous_code
        app.TRANSPORT = self._previous_transport
        app.PROBE_TRANSPORT = self._previous_probe


class TestHealth(ServerBase):

    def test_reports_reachable_when_the_probe_succeeds(self):
        app.PROBE_TRANSPORT = lambda payload: "h"
        status, body = request(self.port, "/api/health?refresh=1")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        llm = body["llm"]
        self.assertTrue(llm["reachable"])
        self.assertIsNone(llm["error"])
        self.assertEqual(llm["model"], protocol.prompts()["model"])
        self.assertGreaterEqual(llm["latency_s"], 0)
        self.assertIn("key_found", llm)
        self.assertIn("key_source", llm)

    def test_reports_the_error_when_the_probe_fails(self):
        def transport(payload):
            raise RuntimeError("HTTP 401 Unauthorized")

        app.PROBE_TRANSPORT = transport
        _, body = request(self.port, "/api/health?refresh=1")
        self.assertFalse(body["llm"]["reachable"])
        self.assertIn("401", body["llm"]["error"])

    def test_caches_the_result(self):
        calls = []

        def transport(payload):
            calls.append(1)
            return "h"

        app.PROBE_TRANSPORT = transport
        request(self.port, "/api/health?refresh=1")
        request(self.port, "/api/health")
        request(self.port, "/api/health")
        self.assertEqual(len(calls), 1)


class TestReads(ServerBase):

    def test_protocol_carries_the_eleven_sections(self):
        status, body = request(self.port, "/api/protocol")
        self.assertEqual(status, 200)
        self.assertEqual(
            set(body),
            {"texts", "scales", "markers", "prompts", "parameters",
             "scripts", "fallback", "panas", "sequences", "interlocutors",
             "topics"})

    def test_script_turns_arrive_with_string_keys(self):
        """After JSON the integer keys become strings: the browser side has
        to read them that way."""
        _, body = request(self.port, "/api/protocol")
        self.assertIn("1", body["scripts"]["validation"])

    def test_desktop_debriefing_comes_with_both_versions(self):
        _, body = request(self.port, "/api/protocol")
        self.assertEqual(set(body["texts"]["desktop_debriefing"]["body"]),
                         {"scripted", "llm"})

    def test_missing_path_is_404(self):
        status, _ = request(self.port, "/does-not-exist.js")
        self.assertEqual(status, 404)

    def test_does_not_serve_files_outside_web(self):
        """A traversal cannot reach openrouter_key.txt."""
        status, _ = request(self.port, "/../../openrouter_key.txt")
        self.assertIn(status, (403, 404))


class TestTurn(ServerBase):

    def setUp(self):
        super().setUp()
        app.ACCESS_CODE = ""
        app.TRANSPORT = lambda payload: "model reply"

    def test_returns_the_text_with_origin_llm_and_no_reason(self):
        status, body = request(self.port, "/api/turn", {
            "feedback": "validation", "name": "Nova",
            "question": "¿Messi es el mejor?",
            "history": [{"role": "user", "content": "Sí, obvio."}],
            "fallback_line": "fallback"})
        self.assertEqual(status, 200)
        self.assertEqual(body, {"text": "model reply", "origin": "llm",
                                "fallback_reason": None})

    def test_the_question_and_name_reach_the_system_prompt(self):
        seen = {}

        def transport(payload):
            seen["system"] = payload["messages"][0]["content"]
            return "ok"

        app.TRANSPORT = transport
        request(self.port, "/api/turn", {
            "feedback": "rejection", "name": "Kai",
            "question": "¿El arte es cualquier cosa?", "history": [],
            "fallback_line": "x"})
        self.assertIn("¿El arte es cualquier cosa?", seen["system"])
        self.assertIn("Kai", seen["system"])

    def test_replays_the_history_into_the_payload(self):
        seen = {}

        def transport(payload):
            seen["messages"] = payload["messages"]
            return "ok"

        app.TRANSPORT = transport
        request(self.port, "/api/turn", {
            "feedback": "rejection",
            "history": [{"role": "assistant", "content": "hola"},
                        {"role": "user", "content": "perdí el trabajo"}],
            "fallback_line": "fallback"})
        roles = [(m["role"], m["content"]) for m in seen["messages"][1:]]
        self.assertEqual(roles, [("assistant", "hola"),
                                 ("user", "perdí el trabajo")])

    def test_invalid_feedback_is_400(self):
        status, _ = request(self.port, "/api/turn", {"feedback": "neutral"})
        self.assertEqual(status, 400)

    def test_if_the_transport_fails_returns_the_line_with_200(self):
        """The demo does not go down because of one turn: it falls back,
        like the desktop."""
        def transport(payload):
            raise IOError("no network")

        app.TRANSPORT = transport
        status, body = request(self.port, "/api/turn", {
            "feedback": "rejection", "history": [],
            "fallback_line": "Mmm, no sé."})
        self.assertEqual(status, 200)
        self.assertEqual(body, {"text": "Mmm, no sé.", "origin": "fallback",
                                "fallback_reason": "OSError: no network"})


class TestAccessCode(ServerBase):

    def setUp(self):
        super().setUp()
        app.ACCESS_CODE = "secret"
        app.TRANSPORT = lambda payload: "ok"

    def test_without_code_is_403(self):
        status, _ = request(self.port, "/api/turn",
                            {"feedback": "validation", "history": []})
        self.assertEqual(status, 403)

    def test_with_code_passes(self):
        status, _ = request(self.port, "/api/turn",
                            {"feedback": "validation", "history": [],
                             "access_code": "secret"})
        self.assertEqual(status, 200)

    def test_the_protocol_needs_no_code(self):
        """The page has to be able to load before the code is typed."""
        status, _ = request(self.port, "/api/protocol")
        self.assertEqual(status, 200)


class TestData(ServerBase):

    def setUp(self):
        super().setUp()
        app.ACCESS_CODE = ""

    def _send(self):
        return request(self.port, "/api/data", {
            "info": {"participant_id": "07", "sequence": 3},
            "responses": {"ep1_suds": 40},
            "behavioral": [{"episode": 1, "condition": "ai_rejection"}],
            "chat": [{"episode": 1, "condition": "ai_rejection",
                      "interlocutor": "Nova", "topic": "art",
                      "author": "agent", "text": "hola", "origin": "fallback",
                      "fallback_reason": "OSError: no network"}],
            "events": [{"t_experiment_s": 0, "t_unix": 0, "code": 1,
                        "label": "experiment_start", "detail": "3"}]})

    def test_writes_the_four_csvs(self):
        status, body = self._send()
        self.assertEqual(status, 200)
        self.assertEqual(len(body["files"]), 4)
        for name in body["files"]:
            self.assertTrue(os.path.exists(os.path.join(self.folder, name)))

    def test_prefix_carries_id_and_sequence(self):
        _, body = self._send()
        for name in body["files"]:
            self.assertTrue(name.startswith("S1_07_seq3_"), name)

    def test_chat_csv_carries_episode_condition_and_reason(self):
        _, body = self._send()
        chat = [n for n in body["files"] if "_chat" in n][0]
        with open(os.path.join(self.folder, chat), encoding="utf-8") as f:
            header, row = f.read().splitlines()[:2]
        self.assertEqual(header.split(","), [
            "episode", "condition", "interlocutor", "topic", "author",
            "text", "origin", "fallback_reason", "t_experiment_s",
            "latency_s"])
        self.assertIn("OSError: no network", row)

    def test_marks_the_platform_as_web(self):
        _, body = self._send()
        responses = [n for n in body["files"] if "_responses" in n][0]
        with open(os.path.join(self.folder, responses), encoding="utf-8") as f:
            content = f.read()
        self.assertIn("platform,web", content)


if __name__ == "__main__":
    unittest.main()
