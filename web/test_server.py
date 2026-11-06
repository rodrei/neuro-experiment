# -*- coding: utf-8 -*-
"""
Tests of the demo server:
    python3 -m unittest discover -s web -t . -v

They start the real server on an ephemeral port and hit it over HTTP, with no
outside network: the LLM transport is replaced with a fake one.
"""

import base64
import io
import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile

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
        app._visits.clear()

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
            {"texts", "scales", "markers", "prompts", "parameters",
             "sequences", "domain_sequences", "domains", "fallback", "demo_mode"})

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

    def test_the_demo_stores_sessions_too(self):
        status, body = request(self.port, "/api/data", {
            "info": {"participant_id": "demo-abc123", "sequence": 3},
            "responses": {}, "behavioral": [], "chat": [], "events": []})
        self.assertEqual(status, 200)
        self.assertEqual(len(os.listdir(self.folder)), 4)
        self.assertTrue(body["files"][0].startswith("S1_demo-abc123_seq3_"))

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


class TestCheckCode(ServerBase):
    """The start form asks before the session begins, so a wrong code cannot
    silently turn every reply into a fixed line."""

    def setUp(self):
        super().setUp()
        app.ACCESS_CODE = "secret"

    def check(self, code):
        return request(self.port, "/api/check-code", {"access_code": code})

    def test_the_right_code_is_valid(self):
        self.assertEqual(self.check("secret"), (200, {"valid": True}))

    def test_a_wrong_code_is_not_valid(self):
        self.assertEqual(self.check("Secret"), (200, {"valid": False}))

    def test_a_blank_code_is_not_valid(self):
        self.assertEqual(self.check(""), (200, {"valid": False}))

    def test_any_code_is_valid_when_the_server_requires_none(self):
        app.ACCESS_CODE = ""
        self.assertEqual(self.check(""), (200, {"valid": True}))

    def test_guessing_is_rate_limited(self):
        self.addCleanup(setattr, app, "RATE_LIMIT_PER_MINUTE", app.RATE_LIMIT_PER_MINUTE)
        app.RATE_LIMIT_PER_MINUTE = 1
        self.check("uno")
        self.assertEqual(self.check("dos")[0], 429)


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

    def test_a_crafted_id_cannot_leave_the_data_folder(self):
        status, body = request(self.port, "/api/data", {
            "info": {"participant_id": "../../../evil", "sequence": "../x"},
            "responses": {}, "behavioral": [], "chat": [], "events": []})
        self.assertEqual(status, 200)
        for name in body["files"]:
            self.assertNotIn("/", name)
            self.assertNotIn("..", name)
            self.assertTrue(os.path.isfile(os.path.join(self.folder, name)))

    def test_a_malformed_session_is_400_and_writes_nothing(self):
        for bad in ({"chat": "text"}, {"chat": ["text"]}, {"responses": []},
                    {"events": [1]}, {"behavioral": {}}):
            status, _ = request(self.port, "/api/data", dict(
                {"info": {"participant_id": "07"}}, **bad))
            self.assertEqual(status, 400, bad)
        self.assertEqual(os.listdir(self.folder), [])

    def test_a_body_over_the_limit_is_413_and_writes_nothing(self):
        previous = app.MAX_BODY_BYTES
        app.MAX_BODY_BYTES = 100
        self.addCleanup(setattr, app, "MAX_BODY_BYTES", previous)
        status, _ = request(self.port, "/api/data", {
            "info": {"participant_id": "07"},
            "responses": {"a": "x" * 200}})
        self.assertEqual(status, 413)
        self.assertEqual(os.listdir(self.folder), [])

    def test_a_full_disk_is_an_error_the_browser_can_see(self):
        """The page then offers the session as a download instead of losing it."""
        original = output.write_all
        def failing(*args, **kwargs):
            raise OSError("no space left")
        output.write_all = failing
        self.addCleanup(setattr, output, "write_all", original)
        status, _ = self._send()
        self.assertEqual(status, 500)


class TestRateLimit(ServerBase):

    def setUp(self):
        super().setUp()
        app.ACCESS_CODE = ""
        self.addCleanup(setattr, app, "RATE_LIMIT_PER_MINUTE", app.RATE_LIMIT_PER_MINUTE)
        app.RATE_LIMIT_PER_MINUTE = 1
        app._visits.clear()
        self.addCleanup(app._visits.clear)

    def _post_from(self, ip):
        req = urllib.request.Request(
            "http://127.0.0.1:%d/api/data" % self.port,
            data=b'{"info": {"participant_id": "07"}}',
            headers={"Content-Type": "application/json", "Fly-Client-IP": ip})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            with e:
                return e.code

    def test_visitors_behind_the_proxy_do_not_share_a_limit(self):
        self.assertEqual(self._post_from("203.0.113.1"), 200)
        self.assertEqual(self._post_from("203.0.113.2"), 200)
        self.assertEqual(self._post_from("203.0.113.1"), 429)


class TestAdmin(ServerBase):

    PASSWORD = "team-secret"

    def setUp(self):
        super().setUp()
        app.ACCESS_CODE = "evaluators"
        self.addCleanup(setattr, app, "ADMIN_CODE", app.ADMIN_CODE)
        app.ADMIN_CODE = self.PASSWORD

    def _save(self, participant_id="demo-abc123", text="Me sentí invisible.",
              **responses):
        _, body = request(self.port, "/api/data", {
            "access_code": "evaluators",
            "info": {"participant_id": participant_id, "sequence": 2},
            "responses": dict({"participant_id": participant_id}, **responses),
            "behavioral": [{"episode": 1, "condition": "ai_rejection",
                            "rounds_completed": 3, "fallback_turns": 1}],
            "chat": [{"participant_id": participant_id, "episode": 1,
                      "condition": "ai_rejection", "agent_type": "ai",
                      "feedback": "rejection", "domain": "friendship",
                      "round": 1, "turn": 2, "author": "participant",
                      "text": text, "chars": len(text), "origin": "participant"}],
            "events": [{"t_experiment_s": 0, "t_unix": 0, "code": 1,
                        "label": "experiment_start", "detail": ""}]})
        return body["files"][0].rsplit("_", 1)[0]

    def _get(self, path, password=PASSWORD, user="equipo"):
        headers = {}
        if password is not None:
            token = base64.b64encode(("%s:%s" % (user, password)).encode()).decode()
            headers["Authorization"] = "Basic " + token
        req = urllib.request.Request("http://127.0.0.1:%d%s" % (self.port, path),
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read(), resp.headers
        except urllib.error.HTTPError as e:
            with e:
                return e.code, e.read(), e.headers

    def test_is_off_when_no_password_is_set(self):
        app.ADMIN_CODE = ""
        self.assertEqual(self._get("/admin")[0], 404)
        self.assertEqual(self._get("/admin", password="")[0], 404)

    def test_asks_for_the_password(self):
        status, _, headers = self._get("/admin", password=None)
        self.assertEqual(status, 401)
        self.assertIn("Basic", headers["WWW-Authenticate"])

    def test_refuses_a_wrong_password_and_the_evaluators_code(self):
        self.assertEqual(self._get("/admin", password="wrong")[0], 401)
        self.assertEqual(self._get("/admin", password="evaluators")[0], 401)

    def test_every_route_needs_the_password(self):
        base = self._save()
        for path in ("/admin/all.zip", "/admin/session/%s" % base,
                     "/admin/session/%s.zip" % base,
                     "/admin/file/%s_chat.csv" % base):
            self.assertEqual(self._get(path, password=None)[0], 401, path)

    def test_lists_the_saved_sessions(self):
        base = self._save()
        status, body, _ = self._get("/admin")
        self.assertEqual(status, 200)
        self.assertIn("demo-abc123", body.decode())
        self.assertIn("/admin/session/%s" % base, body.decode())

    def test_an_empty_folder_lists_nothing_without_failing(self):
        shutil.rmtree(self.folder)
        status, body, _ = self._get("/admin")
        self.assertEqual(status, 200)
        self.assertIn("Todavía no hay sesiones", body.decode())

    def test_a_session_shows_its_conversation_and_responses(self):
        base = self._save(ep1_suds=7)
        status, body, _ = self._get("/admin/session/%s" % base)
        page = body.decode()
        self.assertEqual(status, 200)
        self.assertIn("Me sentí invisible.", page)
        self.assertIn("ep1_suds", page)
        self.assertIn("ai_rejection", page)

    def test_what_participants_write_is_never_interpreted_as_html(self):
        attack = "<script>alert(1)</script>"
        base = self._save(text=attack, suspicion=attack)
        _, body, headers = self._get("/admin/session/%s" % base)
        self.assertNotIn(attack, body.decode())
        self.assertIn("&lt;script&gt;", body.decode())
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])

    def test_downloads_each_file(self):
        base = self._save()
        status, body, headers = self._get("/admin/file/%s_chat.csv" % base)
        self.assertEqual(status, 200)
        self.assertIn("Me sentí invisible.", body.decode())
        self.assertIn("attachment", headers["Content-Disposition"])
        self.assertIn("text/csv", headers["Content-Type"])

    def test_downloads_a_session_as_a_zip(self):
        base = self._save()
        status, body, _ = self._get("/admin/session/%s.zip" % base)
        self.assertEqual(status, 200)
        names = zipfile.ZipFile(io.BytesIO(body)).namelist()
        self.assertEqual(sorted(names), sorted(
            "%s_%s.csv" % (base, kind)
            for kind in ("responses", "behavioral", "chat", "events")))

    def test_the_full_download_leaves_out_the_browser_checks(self):
        real = self._save("demo-abc123")
        check = self._save("check-abc123")
        status, body, _ = self._get("/admin/all.zip")
        self.assertEqual(status, 200)
        names = zipfile.ZipFile(io.BytesIO(body)).namelist()
        self.assertEqual(len(names), 4)
        self.assertTrue(all(n.startswith(real) for n in names), names)
        self.assertNotIn(check, " ".join(names))

    def test_a_crafted_path_reaches_nothing(self):
        self._save()
        secret = os.path.join(os.path.dirname(self.folder), "outside_chat.csv")
        with open(secret, "w") as f:
            f.write("secret")
        self.addCleanup(os.remove, secret)
        for path in ("/admin/file/..%2Foutside_chat.csv",
                     "/admin/file/../outside_chat.csv",
                     "/admin/session/..%2F..%2Fetc",
                     "/admin/file/S1_missing_seq1_x_chat.csv",
                     "/admin/session/S1_missing_seq1_x",
                     "/admin/file/nope.txt"):
            status, body, _ = self._get(path)
            self.assertEqual(status, 404, path)
            self.assertNotIn(b"secret", body)

    def test_pages_are_not_cached_or_indexed(self):
        _, _, headers = self._get("/admin")
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("noindex", headers["X-Robots-Tag"])


if __name__ == "__main__":
    unittest.main()
