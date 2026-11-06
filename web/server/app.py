# -*- coding: utf-8 -*-
"""
Server of the Study 1 web version.

Seven responsibilities and nothing else:

  GET  /               and static files -> serves web/
  GET  /api/protocol                    -> the protocol built by common.protocol
  GET  /api/health                      -> is the LLM reachable? (cached probe)
  POST /api/check-code                  -> is this access code valid? (for the start form)
  POST /api/turn                        -> proxy to the LLM (the key never leaves here)
  POST /api/data                        -> writes the session's four CSVs
  GET  /admin...                        -> the team's view of the sessions (admin.py)

DEMO_MODE (on by default) is the hosted walkthrough for the evaluators: short
timings, the skip button, and a daily cap on what repeated walkthroughs can
spend. DEMO_MODE=0 is the full study, with real timings. Both save the session,
unless the participant withdraws.

/admin needs ADMIN_CODE, a password separate from the evaluators' ACCESS_CODE,
because it shows what people wrote. With no ADMIN_CODE it does not exist.

It is `http.server` from the standard library on purpose: it is a few routes,
and that way the Docker image needs no `pip install` and running it locally
needs no environment.

The proxy is STATELESS: the browser sends the full history on every turn and
the server rebuilds the agent. It can be restarted in the middle of a session
and handles several sessions in parallel with no extra work.

Run locally:  python3 -m web.server.app
"""

import base64
import binascii
import hmac
import http.server
import json
import os
import posixpath
import re
import socketserver
import sys
import threading
import time
import urllib.parse
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from common import llm_agent, protocol, output
from web.server import admin

WEB_DIR = os.path.dirname(HERE)

# Environment configuration. The tests override it at module level.
ACCESS_CODE = os.environ.get("ACCESS_CODE", "")
ADMIN_CODE = os.environ.get("ADMIN_CODE", "")
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(ROOT, "data"))
PORT = int(os.environ.get("PORT", "8080"))
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "20"))
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "30"))
DEMO_MODE = os.environ.get("DEMO_MODE", "1") != "0"
# Twelve turns per walkthrough: this is fifty walkthroughs a day.
MAX_TURNS_PER_DAY = int(os.environ.get("MAX_TURNS_PER_DAY", "600"))
# A full session is well under 1 MB, even with long situations.
MAX_BODY_BYTES = 5 * 1024 * 1024

# Agent transport. None = the real one (OpenRouter). The tests override it.
TRANSPORT = None
# Transport for the health probe. None = the real one. The tests override it.
PROBE_TRANSPORT = None
# The probe costs one token per call: its result is reused for this long.
HEALTH_CACHE_S = 60

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}

ADMIN_HEADERS = {
    "Cache-Control": "no-store",
    "X-Robots-Tag": "noindex, nofollow",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
}

_visits = {}
_lock = threading.Lock()
_health_cache = {"at": 0.0, "result": None}
_turn_budget = {"day": None, "used": 0}


def reset_turn_budget():
    with _lock:
        _turn_budget["day"] = None
        _turn_budget["used"] = 0


def _spend_turn():
    """Counts one model call against today's cap. False once it is used up."""
    today = datetime.now().date()
    with _lock:
        if _turn_budget["day"] != today:
            _turn_budget["day"] = today
            _turn_budget["used"] = 0
        if _turn_budget["used"] >= MAX_TURNS_PER_DAY:
            return False
        _turn_budget["used"] += 1
    return True


def _allowed(ip):
    """Per-IP rate limit: it is a public URL that spends someone else's credit."""
    now = time.time()
    with _lock:
        recent = [t for t in _visits.get(ip, []) if now - t < 60]
        if len(recent) >= RATE_LIMIT_PER_MINUTE:
            _visits[ip] = recent
            return False
        recent.append(now)
        _visits[ip] = recent
    return True


def _health(refresh=False):
    """Whether the LLM is usable right now: key found, model answering.

    Cached HEALTH_CACHE_S seconds so reloading the start page does not spend
    credit; `refresh` forces a new probe.
    """
    with _lock:
        fresh = time.time() - _health_cache["at"] < HEALTH_CACHE_S
        if _health_cache["result"] is not None and fresh and not refresh:
            return _health_cache["result"]
    source = llm_agent.api_key_source()
    ok, latency, error = llm_agent.probe(transport=PROBE_TRANSPORT,
                                         timeout=LLM_TIMEOUT)
    result = {
        "key_found": source is not None,
        "key_source": source,
        "model": protocol.prompts()["model"],
        "reachable": ok,
        "latency_s": round(latency, 3) if ok else None,
        "error": error,
    }
    with _lock:
        _health_cache["at"] = time.time()
        _health_cache["result"] = result
    return result


class BodyTooLarge(Exception):
    pass


def _safe_for_filename(value):
    """Only what cannot leave the data folder: the id comes from the browser."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(value))[:60]


def _is_table(rows):
    return isinstance(rows, list) and all(isinstance(r, dict) for r in rows)


class Handler(http.server.BaseHTTPRequestHandler):

    server_version = "Study1Web"

    def log_message(self, fmt, *args):      # less noise in the console
        pass

    # -----------------------------------------------------------------
    # helpers
    # -----------------------------------------------------------------
    def _respond(self, status, body, content_type="application/json; charset=utf-8",
                 headers=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, obj):
        self._respond(status, json.dumps(obj, ensure_ascii=False))

    def _error(self, status, message):
        self._json(status, {"error": message})

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY_BYTES:
            raise BodyTooLarge()
        body = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(body, dict):
            raise ValueError("not an object")
        return body

    def _code_ok(self, body):
        if not ACCESS_CODE:
            return True
        return body.get("access_code", "") == ACCESS_CODE

    def _client_ip(self):
        """Behind Fly's proxy every connection comes from the proxy, which puts
        the visitor's address in this header."""
        return self.headers.get("Fly-Client-IP") or self.client_address[0]

    def _admin_password_ok(self):
        scheme, _, token = self.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "basic":
            return False
        try:
            decoded = base64.b64decode(token, validate=True)
        except (binascii.Error, ValueError):
            return False
        _, _, password = decoded.partition(b":")
        return hmac.compare_digest(password, ADMIN_CODE.encode("utf-8"))

    def _admin(self, path):
        if not ADMIN_CODE:
            return self._error(404, "not found")
        if not self._admin_password_ok():
            if not _allowed(self._client_ip()):
                return self._error(429, "too many requests")
            return self._respond(
                401, "Hace falta la contraseña del equipo.", "text/plain; charset=utf-8",
                dict(ADMIN_HEADERS,
                     **{"WWW-Authenticate": 'Basic realm="Estudio 1", charset="UTF-8"'}))
        status, body, content_type, download = admin.handle(path, DATA_DIR)
        headers = dict(ADMIN_HEADERS)
        if download:
            headers["Content-Disposition"] = 'attachment; filename="%s"' % download
        return self._respond(status, body, content_type, headers)

    # -----------------------------------------------------------------
    # GET
    # -----------------------------------------------------------------
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            query = urllib.parse.parse_qs(parsed.query)
            refresh = query.get("refresh", ["0"])[0] == "1"
            return self._json(200, {"ok": True, "llm": _health(refresh)})
        if path == "/api/protocol":
            return self._json(200, dict(protocol.everything(),
                                        demo_mode=DEMO_MODE))
        if path == "/admin" or path.startswith("/admin/"):
            return self._admin(urllib.parse.unquote(path))
        return self._static(path)

    def _static(self, path):
        if path in ("/", ""):
            path = "/index.html"
        # normalise and check it does not escape web/: otherwise a
        # ../../openrouter_key.txt would be served as is.
        clean = posixpath.normpath(urllib.parse.unquote(path)).lstrip("/")
        target = os.path.realpath(os.path.join(WEB_DIR, clean))
        if not target.startswith(os.path.realpath(WEB_DIR) + os.sep):
            return self._error(403, "path outside web/")
        if not os.path.isfile(target):
            return self._error(404, "not found")
        with open(target, "rb") as f:
            body = f.read()
        extension = os.path.splitext(target)[1].lower()
        self._respond(200, body, MIME_TYPES.get(extension, "application/octet-stream"))

    # -----------------------------------------------------------------
    # POST
    # -----------------------------------------------------------------
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if not _allowed(self._client_ip()):
            return self._error(429, "too many requests")
        try:
            body = self._read_json()
        except BodyTooLarge:
            return self._error(413, "too large")
        except ValueError:
            return self._error(400, "invalid json")
        if path == "/api/check-code":
            return self._json(200, {"valid": self._code_ok(body)})
        if not self._code_ok(body):
            return self._error(403, "invalid access code")

        if path == "/api/turn":
            return self._turn(body)
        if path == "/api/data":
            return self._data(body)
        return self._error(404, "not found")

    def _turn(self, body):
        """Rebuilds the agent, replays the history into it and asks for a turn.

        Body: {feedback, history, fallback_line, access_code}. Nothing else
        reaches the prompt: the model never learns the label the participant
        sees. Reply: {text, origin, fallback_reason}. If the API fails, reply()
        returns the fallback line with origin "fallback" and the reason: the
        session never goes down because of one turn, and the failure is
        visible.
        """
        feedback = body.get("feedback")
        if feedback not in llm_agent.FEEDBACK_TYPES:
            return self._error(400, "invalid feedback")
        history = body.get("history", [])
        # Opening + three rounds: the third turn sees at most six messages.
        if len(history) > 2 * protocol.parameters("demo")["rounds"]:
            return self._error(400, "history longer than an episode")
        if DEMO_MODE and not _spend_turn():
            return self._json(200, {"text": body.get("fallback_line", ""),
                                    "origin": "fallback",
                                    "fallback_reason": "daily turn cap"})
        agent = llm_agent.LLMAgent(feedback, transport=TRANSPORT,
                                   timeout=LLM_TIMEOUT)
        for message in history:
            text = message.get("content", "")
            if message.get("role") == "user":
                agent.hear(text)
            else:
                agent.greet(text)
        text, origin, reason = agent.reply(body.get("fallback_line", ""))
        return self._json(200, {"text": text, "origin": origin,
                                "fallback_reason": reason})

    def _data(self, body):
        """Writes the four CSVs, prefixed S1_<id>_seq<sequence>_<stamp> (UTC)."""
        info = body.get("info", {})
        responses = body.get("responses", {})
        behavioral = body.get("behavioral", [])
        chat = body.get("chat", [])
        events = body.get("events", [])
        if not (isinstance(info, dict) and isinstance(responses, dict)
                and _is_table(behavioral) and _is_table(chat) and _is_table(events)):
            return self._error(400, "malformed session")
        responses = dict(responses)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        base = output.base_name(
            _safe_for_filename(info.get("participant_id") or "no_id"),
            "seq" + _safe_for_filename(info.get("sequence") or "0"),
            stamp)
        responses["platform"] = "web"
        responses["mode"] = "demo" if DEMO_MODE else "research"
        responses["file"] = base
        try:
            paths = output.write_all(DATA_DIR, base, responses=responses,
                                     behavioral=behavioral, chat=chat, events=events)
        except OSError as e:
            print("Could not save session %s: %s" % (base, e), flush=True)
            return self._error(500, "could not save")
        return self._json(200, {"ok": True,
                                "files": [os.path.basename(p) for p in paths]})


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_server(port=0, data_dir=None):
    """A server ready for `serve_forever()`. port=0 picks a free one."""
    global DATA_DIR
    if data_dir is not None:
        DATA_DIR = data_dir
    return Server(("0.0.0.0", port), Handler)


def main():
    server = create_server(PORT)
    print("Study 1 — web at http://0.0.0.0:%d" % server.server_address[1])
    print("Mode: %s. Data in %s" % ("demo" if DEMO_MODE else "research", DATA_DIR))
    if not ADMIN_CODE:
        print("NOTICE: no ADMIN_CODE; /admin is off.")
    source = llm_agent.api_key_source()
    if source == "env":
        print("LLM key: found in OPENROUTER_API_KEY")
    elif source == "file":
        print("LLM key: found in openrouter_key.txt")
    else:
        print("LLM key: NOT FOUND (every turn will fall back to the fixed lines)")
    if not ACCESS_CODE:
        print("NOTICE: no ACCESS_CODE; anyone with the URL can spend "
              "OpenRouter credit.")
    server.serve_forever()


if __name__ == "__main__":
    main()
