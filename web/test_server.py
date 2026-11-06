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

from common import output, protocol
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
        self._previous_demo = app.DEMO_MODE
        self._previous_cap = app.MAX_TURNS_PER_DAY
        app.DEMO_MODE = False
        app.reset_turn_budget()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.folder, ignore_errors=True)
        app.ACCESS_CODE = self._previous_code
        app.TRANSPORT = self._previous_transport
        app.PROBE_TRANSPORT = self._previous_probe
        app.DEMO_MODE = self._previous_demo
        app.MAX_TURNS_PER_DAY = self._previous_cap
        app.reset_turn_budget()


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

    def test_protocol_carries_every_section_and_the_mode(self):
        status, body = request(self.port, "/api/protocol")
        self.assertEqual(status, 200)
        self.assertEqual(
            set(body),
            {"texts", "scales", "markers", "prompts", "parameters", "panas",
             "sequences", "domain_sequences", "domains", "instruments",
             "fallback", "demo_mode"})

    def test_protocol_reports_the_demo_mode(self):
        app.DEMO_MODE = True
        _, body = request(self.port, "/api/protocol")
        self.assertIs(body["demo_mode"], True)
        app.DEMO_MODE = False
        _, body = request(self.port, "/api/protocol")
        self.assertIs(body["demo_mode"], False)

    def test_fallback_turns_arrive_with_string_keys(self):
        """After JSON the integer keys become strings: the browser side has
        to read them that way."""
        _, body = request(self.port, "/api/protocol")
        self.assertIn("1", body["fallback"]["validation"])

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
            "feedback": "validation",
            "history": [{"role": "user", "content": "Perdí el trabajo."}],
            "fallback_line": "fallback"})
        self.assertEqual(status, 200)
        self.assertEqual(body, {"text": "model reply", "origin": "llm",
                                "fallback_reason": None})

    def test_nothing_the_client_sends_can_change_the_prompt(self):
        """The model must not receive the label shown to the participant."""
        seen = []

        def transport(payload):
            seen.append(payload["messages"][0]["content"])
            return "ok"

        app.TRANSPORT = transport
        for extra in ({"agent_type": "human", "label": "otra persona",
                       "name": "Kai", "question": "¿Quién?"},
                      {"agent_type": "ai", "label": "una IA"}):
            request(self.port, "/api/turn", dict(
                extra, feedback="rejection", history=[], fallback_line="x"))
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0], seen[1])
        self.assertNotIn("Kai", seen[0])

    def test_a_history_longer_than_an_episode_is_400(self):
        """Opening plus three rounds is at most six messages: a longer history
        is someone using the proxy as a free chat."""
        rounds = protocol.parameters("demo")["rounds"]
        history = [{"role": "user", "content": "x"}] * (2 * rounds + 1)
        status, _ = request(self.port, "/api/turn", {
            "feedback": "validation", "history": history,
            "fallback_line": "x"})
        self.assertEqual(status, 400)

    def test_a_full_episode_history_is_accepted(self):
        rounds = protocol.parameters("demo")["rounds"]
        history = [{"role": "user", "content": "x"}] * (2 * rounds)
        status, _ = request(self.port, "/api/turn", {
            "feedback": "validation", "history": history,
            "fallback_line": "x"})
        self.assertEqual(status, 200)

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
        """The demo does not go down because of one turn: it falls back."""
        def transport(payload):
            raise IOError("no network")

        app.TRANSPORT = transport
        status, body = request(self.port, "/api/turn", {
            "feedback": "rejection", "history": [],
            "fallback_line": "Mmm, no sé."})
        self.assertEqual(status, 200)
        self.assertEqual(body, {"text": "Mmm, no sé.", "origin": "fallback",
                                "fallback_reason": "OSError: no network"})


class TestDemoMode(ServerBase):

    def setUp(self):
        super().setUp()
        app.ACCESS_CODE = ""
        app.DEMO_MODE = True

    def test_storing_a_session_is_refused_and_writes_nothing(self):
        """The screen promises that nothing is recorded."""
        status, _ = request(self.port, "/api/data", {
            "info": {"participant_id": "07", "sequence": 3},
            "responses": {}, "behavioral": [], "chat": [], "events": []})
        self.assertEqual(status, 403)
        self.assertEqual(os.listdir(self.folder), [])

    def test_past_the_daily_cap_turns_come_from_the_fallback_line(self):
        calls = []

        def transport(payload):
            calls.append(1)
            return "model reply"

        app.TRANSPORT = transport
        app.MAX_TURNS_PER_DAY = 1
        turn = {"feedback": "validation", "history": [],
                "fallback_line": "respaldo"}
        _, first = request(self.port, "/api/turn", turn)
        status, second = request(self.port, "/api/turn", turn)
        self.assertEqual(first["origin"], "llm")
        self.assertEqual(status, 200)
        self.assertEqual(second["text"], "respaldo")
        self.assertEqual(second["origin"], "fallback")
        self.assertIn("cap", second["fallback_reason"])
        self.assertEqual(len(calls), 1)

    def test_the_cap_only_applies_to_the_demo(self):
        app.DEMO_MODE = False
        app.TRANSPORT = lambda payload: "model reply"
        app.MAX_TURNS_PER_DAY = 1
        turn = {"feedback": "validation", "history": [], "fallback_line": "x"}
        request(self.port, "/api/turn", turn)
        _, second = request(self.port, "/api/turn", turn)
        self.assertEqual(second["origin"], "llm")


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
            "responses": {"ep1_suds": 4},
            "behavioral": [{"episode": 1, "condition": "ai_rejection"}],
            "chat": [{"episode": 1, "condition": "ai_rejection",
                      "domain": "friendship", "round": 1, "turn": 2,
                      "author": "agent", "text": "hola", "chars": 4,
                      "origin": "fallback",
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
        self.assertEqual(header.split(","), output.CHAT_FIELDS)
        self.assertIn("OSError: no network", row)
        self.assertIn("friendship", row)

    def test_marks_the_platform_as_web(self):
        _, body = self._send()
        responses = [n for n in body["files"] if "_responses" in n][0]
        with open(os.path.join(self.folder, responses), encoding="utf-8") as f:
            content = f.read()
        self.assertIn("platform,web", content)


if __name__ == "__main__":
    unittest.main()
