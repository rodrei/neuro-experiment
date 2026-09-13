# -*- coding: utf-8 -*-
"""
LLM conversational agent (OpenRouter), the alternative to the scripted agent.

Enabled with AGENT = "llm" in the desktop config. The experiment flow, the
markers and the CSVs do not change: only who writes the messages does.

Key decisions:
  - The greeting that asks for the situation is ALWAYS scripted (it has to
    ask for it no matter what, and it is identical across conditions). The
    LLM takes over once the situation has been told.
  - If the API fails or returns nothing, the turn falls back to the fixed
    line from protocol/scripts.csv and the experiment goes on (same spirit as
    the marker backends: it never crashes). The origin is recorded.
  - The key is read from OPENROUTER_API_KEY or from openrouter_key.txt
    (gitignored), because there are no environment variables when launching
    from PsychoPy Coder.
  - No new dependencies: only urllib from the standard library.

To iterate on the prompts without opening PsychoPy:  python3 -m common.llm_agent
"""

import json
import os
import ssl
import threading
import urllib.request

from common import protocol

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

FEEDBACK_TYPES = ("validation", "rejection")

# The timeout is operational, not methodological: each platform passes it
# when building the agent. This is the value used when nobody says otherwise.
DEFAULT_TIMEOUT = 20


def _script_examples(feedback):
    """The scripted lines of the feedback type, as style anchors for the prompt."""
    try:
        return list(protocol.scripts()[feedback].values())
    except (OSError, KeyError):
        return []


NO_REPLY_MARK = "(no responde)"


def clean_reply(text, max_chars):
    """Makes the text ready for a chat bubble: one line and, if it exceeds
    the maximum, cut at the last sentence end that fits.

    It also strips a leading "(no responde)": when the person does not answer
    we pass that mark to the model as if it were their message, and sometimes
    the model repeats it when starting its turn. Showing it on screen gives
    the scaffolding away.
    """
    text = " ".join(text.split())
    while text.lower().startswith(NO_REPLY_MARK):
        text = text[len(NO_REPLY_MARK):].lstrip(" .,:;-—")
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
    if last > 0:
        return cut[:last + 1]
    return cut


def load_api_key(folder=ROOT):
    """OPENROUTER_API_KEY from the environment, or openrouter_key.txt in `folder`."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    path = os.path.join(folder, "openrouter_key.txt")
    try:
        with open(path, encoding="utf-8") as f:
            key = f.read().strip()
    except OSError:
        return None
    return key or None


def _ssl_context():
    """TLS context built with a certificate authority that exists in this
    interpreter.

    PsychoPy's embedded Python does not have the certificate bundle where
    OpenSSL looks for it, so the default context cannot validate OpenRouter.
    certifi ships inside PsychoPy; if it is missing, the system bundle is
    used. Verification is never disabled: what the participant writes travels
    over this channel.
    """
    candidates = []
    try:
        import certifi
    except ImportError:
        pass
    else:
        candidates.append(certifi.where())
    candidates.append("/etc/ssl/cert.pem")
    for path in candidates:
        if os.path.exists(path):
            return ssl.create_default_context(cafile=path)
    return ssl.create_default_context()


def _openrouter_transport(payload, timeout=DEFAULT_TIMEOUT):
    """Real transport: sends the payload and returns the reply text.

    Any problem (no key, no network, HTTP != 200, odd JSON) is left to
    propagate as an exception: the caller decides to fall back.
    """
    key = load_api_key()
    if not key:
        raise RuntimeError(
            "No API key: set OPENROUTER_API_KEY or create openrouter_key.txt")
    request = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout,
                                context=_ssl_context()) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


class LLMAgent(object):
    """One conversation episode. Build a new one per episode."""

    def __init__(self, feedback, transport=None, timeout=None):
        if feedback not in FEEDBACK_TYPES:
            raise ValueError("feedback must be one of %s" % (FEEDBACK_TYPES,))
        self.feedback = feedback
        self.timeout = DEFAULT_TIMEOUT if timeout is None else timeout
        # The injected transport receives only the payload: the timeout is
        # bound here so the tests' signature does not change.
        if transport is None:
            transport = lambda payload: _openrouter_transport(
                payload, self.timeout)
        self.transport = transport
        self.history = []     # [{"role": ..., "content": ...}]

        cfg = protocol.prompts()
        self.system = cfg["situation"]["rules"].format(
            name=protocol.texts()["agent_name"],
            role=cfg["situation"]["role"][feedback],
            max_chars=cfg["max_chars"],
            examples="\n".join("- " + e for e in _script_examples(feedback))
                     or "(no examples)")

    # -----------------------------------------------------------------
    def greet(self, text):
        """Records a scripted agent message (e.g. the greeting)."""
        self.history.append({"role": "assistant", "content": text})

    def hear(self, text):
        """Records what the participant wrote."""
        self.history.append({"role": "user", "content": text})

    def reply(self, fallback_line):
        """Generates the next turn. Returns (text, origin) with origin "llm"
        or "fallback". If anything fails the turn comes from the script and
        the history stays consistent with what was shown on screen."""
        cfg = protocol.prompts()
        payload = {
            "model": cfg["model"],
            "messages": [{"role": "system", "content": self.system}]
                        + list(self.history),
            "max_tokens": cfg["max_tokens"],
            "temperature": cfg["temperature"],
        }
        reason = None
        try:
            raw = self.transport(payload)
            text = clean_reply(raw, cfg["max_chars"])
        except Exception as error:
            text = ""
            reason = "%s: %s" % (type(error).__name__, error)
        origin = "llm"
        if not text.strip():
            # Without this notice an expired key, a network outage and a
            # certificate problem all look the same from the screen: like a
            # scripted experiment.
            print("NOTICE: %s turn fell back to the script (%s)."
                  % (self.feedback, reason or "the model returned empty text"))
            text, origin = fallback_line, "fallback"
        self.history.append({"role": "assistant", "content": text})
        return text, origin

    def reply_in_thread(self, fallback_line):
        """Like reply(), but in a thread: lets the screen keep drawing while
        the API is awaited. Returns a PendingReply."""
        return PendingReply(self, fallback_line)


class PendingReply(object):
    """A reply() running in the background."""

    def __init__(self, agent, fallback_line):
        self._result = None
        self._thread = threading.Thread(
            target=self._run, args=(agent, fallback_line), daemon=True)
        self._thread.start()

    def _run(self, agent, fallback_line):
        self._result = agent.reply(fallback_line)

    def ready(self):
        return not self._thread.is_alive()

    def result(self):
        """Blocks until the (text, origin) is available."""
        self._thread.join()
        return self._result


# =====================================================================
# Console chat to try the prompts without opening PsychoPy
# =====================================================================
if __name__ == "__main__":
    feedback = ""
    while feedback not in FEEDBACK_TYPES:
        feedback = input("Feedback type? (validation/rejection): ").strip()
    agent = LLMAgent(feedback)
    greeting = ("Hola. Me dijeron que vamos a charlar un rato. Contame algo "
                "que te haya pasado últimamente y que te haya movilizado.")
    agent.greet(greeting)
    print("\n[%s] %s" % (protocol.texts()["agent_name"], greeting))
    while True:
        try:
            line = input("\n[you] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            break
        agent.hear(line)
        text, origin = agent.reply(
            fallback_line="(fallback: the scripted line would go here)")
        print("\n[%s · %s] %s"
              % (protocol.texts()["agent_name"], origin, text))
