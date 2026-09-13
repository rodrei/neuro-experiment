# -*- coding: utf-8 -*-
"""
Reader of protocol/: the experiment's content as data.

This is the only module that knows how the protocol is stored. The desktop
experiment and the web server both read it through here, so a wording fix in
protocol/ reaches both implementations without copying anything.

Standard library only: it is imported both by PsychoPy's embedded Python and
by the server's.
"""

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROTOCOL_DIR = os.path.join(ROOT, "protocol")

MODES = ("real", "demo")
AGENTS = ("scripted", "llm")

_cache = {}


def _read_json(name):
    """Reads protocol/<name>.json once and caches it."""
    if name not in _cache:
        path = os.path.join(PROTOCOL_DIR, name + ".json")
        with open(path, encoding="utf-8") as f:
            _cache[name] = json.load(f)
    return _cache[name]


def texts():
    """Screen prose, cover story and final check."""
    return _read_json("texts")


def debriefing(agent):
    """The debriefing that matches the agent mode that was used.

    There are two versions because what happened was different. With the
    scripted agent every message was written in advance and identical across
    participants. With the LLM agent it was not: a model generated them from
    what the person said, and telling them otherwise would be lying on the
    very screen where the lying stops.
    """
    if agent not in AGENTS:
        raise ValueError("agent must be one of %s, not %r" % (AGENTS, agent))
    block = texts()["debriefing"]
    return {"title": block["title"], "body": block["body"][agent]}


def scales():
    """SUDS, SAM, authenticity and PANAS: prompts, ticks and anchors."""
    return _read_json("scales")


def markers():
    """{label: code} for the event log and the EDA equipment."""
    return _read_json("markers")


def prompts():
    """Role per condition, rules template and model parameters."""
    return _read_json("prompts")


def parameters(mode="real"):
    """Timings of the requested mode, with the common parameters merged in.

    The common ones (the latency formula, above all) hold in both modes: it
    is design invariant 2 and cannot depend on how the study is run.
    """
    if mode not in MODES:
        raise ValueError("mode must be one of %s, not %r" % (MODES, mode))
    raw = _read_json("parameters")
    merged = dict(raw["common"])
    merged.update(raw[mode])
    return merged


def scripts():
    """{feedback: {turn: text}} from protocol/scripts.csv."""
    out = {}
    with open(os.path.join(PROTOCOL_DIR, "scripts.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.setdefault(row["feedback"], {})[int(row["turn"])] = row["text"]
    return out


def panas():
    """The 20 PANAS items, in order, from protocol/panas.csv."""
    with open(os.path.join(PROTOCOL_DIR, "panas.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def everything():
    """The whole protocol in one dict, to serve it over HTTP to the browser.

    Note: after json.dumps, the integer keys of scripts() come out as strings
    ("1", "2", "3"). The browser side reads them that way.
    """
    return {
        "texts": texts(),
        "scales": scales(),
        "markers": markers(),
        "prompts": prompts(),
        "parameters": {mode: parameters(mode) for mode in MODES},
        "scripts": scripts(),
        "panas": panas(),
    }
