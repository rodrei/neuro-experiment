# -*- coding: utf-8 -*-
"""
Tests of common/llm_agent.py. They run with the system Python, without
network and without PsychoPy:  python3 -m unittest common.test_llm_agent -v

The transport (the HTTP call to OpenRouter) is injected, so everything else
is tested here: history assembly, role per condition, fallback to the
script, and text cleanup.
"""

import os
import ssl
import tempfile
import threading
import unittest

from common import llm_agent
from common.llm_agent import (LLMAgent, _ssl_context, load_api_key,
                              clean_reply)


def fixed_transport(reply):
    """Fake transport: always returns `reply` and records what it received."""
    calls = []

    def transport(payload):
        calls.append(payload)
        return reply

    transport.calls = calls
    return transport


class TestReply(unittest.TestCase):

    def test_returns_the_model_text_with_origin_llm(self):
        transport = fixed_transport("Te entiendo, debe haber sido difícil.")
        agent = LLMAgent("validation", transport=transport)
        agent.hear("Me peleé con mi hermana y quedé muy mal.")

        text, origin, reason = agent.reply(fallback_line="fallback line")

        self.assertEqual(text, "Te entiendo, debe haber sido difícil.")
        self.assertEqual(origin, "llm")
        self.assertIsNone(reason)

    def test_sends_the_whole_history_in_order(self):
        transport = fixed_transport("ok")
        agent = LLMAgent("validation", transport=transport)
        agent.greet("Hola, contame algo que te haya pasado.")
        agent.hear("Perdí el trabajo.")
        agent.reply(fallback_line="fallback")
        agent.hear("Gracias por escucharme.")
        agent.reply(fallback_line="fallback")

        messages = transport.calls[-1]["messages"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(
            [(m["role"], m["content"]) for m in messages[1:]],
            [("assistant", "Hola, contame algo que te haya pasado."),
             ("user", "Perdí el trabajo."),
             ("assistant", "ok"),
             ("user", "Gracias por escucharme.")])

    def test_the_condition_role_is_in_the_system_prompt(self):
        for feedback, word in [("validation", "valid"), ("rejection", "rechaz")]:
            transport = fixed_transport("ok")
            agent = LLMAgent(feedback, transport=transport)
            agent.hear("hola")
            agent.reply(fallback_line="fallback")
            system = transport.calls[0]["messages"][0]["content"]
            self.assertIn(word, system.lower(),
                          "the %s system prompt does not mention its role" % feedback)

    def test_unknown_feedback_fails_on_construction(self):
        with self.assertRaises(ValueError):
            LLMAgent("neutral")


class TestFallback(unittest.TestCase):

    def test_if_the_transport_fails_returns_the_line(self):
        def transport(payload):
            raise IOError("no network")

        agent = LLMAgent("rejection", transport=transport)
        agent.hear("hola")

        text, origin, reason = agent.reply(fallback_line="Mmm, no sé.")

        self.assertEqual(text, "Mmm, no sé.")
        self.assertEqual(origin, "fallback")
        self.assertEqual(reason, "OSError: no network")

    def test_if_the_model_returns_empty_uses_the_line(self):
        agent = LLMAgent("validation", transport=fixed_transport("   "))
        agent.hear("hola")

        text, origin, reason = agent.reply(fallback_line="fallback")

        self.assertEqual(text, "fallback")
        self.assertEqual(origin, "fallback")
        self.assertEqual(reason, "empty reply from model")

    def test_after_a_fallback_the_history_keeps_the_line(self):
        """The conversation has to stay consistent with what was shown on
        screen: if a turn came from the script, the model's next turn has to
        receive that line as if it had said it."""
        transport = fixed_transport("ok")

        def transport_failing_first(payload):
            if not transport.calls:
                transport.calls.append(payload)
                raise IOError("no network")
            return transport(payload)

        agent = LLMAgent("validation", transport=transport_failing_first)
        agent.hear("hola")
        agent.reply(fallback_line="fallback")
        agent.hear("sigo acá")
        agent.reply(fallback_line="fallback 2")

        messages = transport.calls[-1]["messages"]
        self.assertIn(("assistant", "fallback"),
                      [(m["role"], m["content"]) for m in messages])


class TestCleanup(unittest.TestCase):

    def test_short_text_stays_the_same(self):
        self.assertEqual(clean_reply("Todo bien.", max_chars=100),
                         "Todo bien.")

    def test_collapses_line_breaks(self):
        """A single chat bubble: no paragraphs, no lists."""
        self.assertEqual(
            clean_reply("Primero.\n\nSegundo.\n- item", max_chars=100),
            "Primero. Segundo. - item")

    def test_cuts_long_text_at_a_sentence_end(self):
        text = "Una oración corta. " * 30
        cut = clean_reply(text, max_chars=100)
        self.assertLessEqual(len(cut), 100)
        self.assertTrue(cut.endswith("."))

    def test_hard_cut_without_punctuation(self):
        cut = clean_reply("x" * 500, max_chars=100)
        self.assertEqual(len(cut), 100)


class TestReplyInThread(unittest.TestCase):
    """The request runs in the background so the screen can keep drawing
    ("en línea") while the API is awaited."""

    def test_does_not_block_and_delivers_the_same_result(self):
        started = threading.Event()
        release = threading.Event()

        def slow_transport(payload):
            started.set()
            release.wait(timeout=5)
            return "slow reply"

        agent = LLMAgent("validation", transport=slow_transport)
        agent.hear("hola")

        pending = agent.reply_in_thread(fallback_line="fallback")
        self.assertTrue(started.wait(timeout=5))
        self.assertFalse(pending.ready())   # the transport is still hanging

        release.set()
        self.assertEqual(pending.result(), ("slow reply", "llm", None))
        self.assertTrue(pending.ready())
        self.assertEqual(agent.history[-1]["content"], "slow reply")


class TestSSLContext(unittest.TestCase):
    """PsychoPy's embedded Python does not find the CA bundle where OpenSSL
    looks: without a context of our own every call to OpenRouter dies with
    CERTIFICATE_VERIFY_FAILED and the turn falls back. These tests fail with
    the default context when run with PsychoPy's Python, which is where it
    matters."""

    def test_the_context_has_authorities_loaded(self):
        self.assertTrue(_ssl_context().get_ca_certs())

    def test_the_context_verifies_the_certificate(self):
        context = _ssl_context()
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(context.check_hostname)


class TestApiKey(unittest.TestCase):

    def setUp(self):
        self._previous = os.environ.pop("OPENROUTER_API_KEY", None)

    def tearDown(self):
        if self._previous is not None:
            os.environ["OPENROUTER_API_KEY"] = self._previous

    def test_reads_the_environment_variable(self):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-from-env"
        self.assertEqual(load_api_key(), "sk-or-from-env")

    def test_reads_the_file_when_there_is_no_variable(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "openrouter_key.txt")
            with open(path, "w") as f:
                f.write("sk-or-from-file\n")
            self.assertEqual(load_api_key(folder=folder), "sk-or-from-file")

    def test_without_key_returns_none(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(load_api_key(folder=folder))


class TestNoReplyMark(unittest.TestCase):
    """When the person does not answer we pass "(no responde)" to the model
    as if it were their message. Sometimes the model repeats it when
    starting its turn, and showing it on screen gives the scaffolding away."""

    def test_strips_the_mark_at_the_start(self):
        self.assertEqual(
            clean_reply("(no responde) Bueno, a veces pasa.", max_chars=100),
            "Bueno, a veces pasa.")

    def test_strips_the_mark_with_attached_punctuation(self):
        self.assertEqual(
            clean_reply("(no responde). Dale, seguimos.", max_chars=100),
            "Dale, seguimos.")

    def test_leaves_the_mark_in_the_middle(self):
        text = "Me dijiste (no responde) y no entendí."
        self.assertEqual(clean_reply(text, max_chars=100), text)


class TestDebatePrompt(unittest.TestCase):

    def test_contains_name_question_and_role(self):
        system = llm_agent.build_system_prompt(
            "rejection", name="Nova",
            question="¿Messi es el mejor de la historia?")
        self.assertIn("Nova", system)
        self.assertIn("¿Messi es el mejor de la historia?", system)
        self.assertIn("RECHAZO", system)
        self.assertNotIn("{", system)

    def test_without_question_uses_the_situation_prompt(self):
        system = llm_agent.build_system_prompt("validation")
        self.assertIn("situación personal", system)
        self.assertNotIn("{", system)

    def test_agent_uses_debate_prompt_when_given_a_question(self):
        seen = {}

        def transport(payload):
            seen["system"] = payload["messages"][0]["content"]
            return "ok"

        agent = LLMAgent("validation", transport=transport,
                         name="Julián", question="¿La religión hace bien?")
        agent.hear("Yo creo que sí.")
        agent.reply("fallback")
        self.assertIn("¿La religión hace bien?", seen["system"])
        self.assertIn("Julián", seen["system"])
        self.assertIn("VALIDAR", seen["system"])


class TestProbe(unittest.TestCase):

    def test_ok(self):
        ok, latency, error = llm_agent.probe(transport=lambda p: "h")
        self.assertTrue(ok)
        self.assertIsNone(error)
        self.assertGreaterEqual(latency, 0)

    def test_sends_a_one_token_request_with_the_configured_model(self):
        seen = {}

        def transport(payload):
            seen.update(payload)
            return "h"

        llm_agent.probe(transport=transport)
        self.assertEqual(seen["max_tokens"], 1)
        self.assertEqual(seen["model"], llm_agent.protocol.prompts()["model"])

    def test_failure(self):
        def transport(payload):
            raise RuntimeError("401 Unauthorized")

        ok, latency, error = llm_agent.probe(transport=transport)
        self.assertFalse(ok)
        self.assertEqual(error, "RuntimeError: 401 Unauthorized")


class TestHttpErrorReason(unittest.TestCase):

    def test_http_error_becomes_a_readable_runtime_error(self):
        import io
        import urllib.error
        err = urllib.error.HTTPError(
            "https://x", 401, "Unauthorized", {},
            io.BytesIO(b'{"error":{"message":"bad key"}}'))
        with self.assertRaises(RuntimeError) as cm:
            llm_agent._raise_readable(err)
        self.assertIn("HTTP 401", str(cm.exception))
        self.assertIn("bad key", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
