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
CONDITIONS = ("human_validation", "human_rejection",
              "ai_validation", "ai_rejection")

_cache = {}


def _read_json(name):
    """Reads protocol/<name>.json once and caches it."""
    if name not in _cache:
        path = os.path.join(PROTOCOL_DIR, name + ".json")
        with open(path, encoding="utf-8") as f:
            _cache[name] = json.load(f)
    return _cache[name]


def _read_lines_csv(filename):
    """{feedback: {turn: text}} from a feedback,turn,text CSV."""
    out = {}
    with open(os.path.join(PROTOCOL_DIR, filename), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.setdefault(row["feedback"], {})[int(row["turn"])] = row["text"]
    return out


def texts():
    """Screen prose for both platforms (the desktop-only entries are prefixed
    desktop_ or listed in protocol/README.md)."""
    return _read_json("texts")


def desktop_debriefing(agent):
    """The desktop debriefing that matches the agent mode that was used.

    There are two versions because what happened was different. With the
    scripted agent every message was written in advance and identical across
    participants. With the LLM agent it was not: a model generated them from
    what the person said, and telling them otherwise would be lying on the
    very screen where the lying stops.
    """
    if agent not in AGENTS:
        raise ValueError("agent must be one of %s, not %r" % (AGENTS, agent))
    block = texts()["desktop_debriefing"]
    return {"title": block["title"], "body": block["body"][agent]}


def scales():
    """SUDS, SAM, authenticity and PANAS: prompts, ticks and anchors."""
    return _read_json("scales")


def markers():
    """{label: code} for the event log and the EDA equipment."""
    return _read_json("markers")


def prompts():
    """Model parameters plus the two prompt families: `debate` (web) and
    `situation` (desktop), each with a rules template and a role per
    feedback type."""
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


def sequences():
    """Williams Latin square: {"1": [condition x4], ..., "4": [...]}."""
    return _read_json("sequences")


def interlocutors():
    """Four {name, type} entries, two per agent type, in assignment order."""
    return _read_json("interlocutors")


def topics():
    """Eight {id, category, question} debate topics."""
    return _read_json("topics")


def split_condition(condition):
    """'ai_rejection' -> ('ai', 'rejection')."""
    if condition not in CONDITIONS:
        raise ValueError("condition must be one of %s, not %r"
                         % (CONDITIONS, condition))
    agent_type, feedback = condition.split("_")
    return agent_type, feedback


def scripts():
    """{feedback: {turn: text}} from protocol/scripts.csv (desktop)."""
    return _read_lines_csv("scripts.csv")


def fallback_lines():
    """{feedback: {turn: text}} from protocol/fallback.csv: the generic lines
    the web shows when an LLM turn fails."""
    return _read_lines_csv("fallback.csv")


def panas():
    """The 20 PANAS items, in order, from protocol/panas.csv."""
    with open(os.path.join(PROTOCOL_DIR, "panas.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def everything():
    """The whole protocol in one dict, to serve it over HTTP to the browser.

    Note: after json.dumps, the integer keys of scripts() and
    fallback_lines() come out as strings ("1", "2", "3"). The browser side
    reads them that way.
    """
    return {
        "texts": texts(),
        "scales": scales(),
        "markers": markers(),
        "prompts": prompts(),
        "parameters": {mode: parameters(mode) for mode in MODES},
        "scripts": scripts(),
        "fallback": fallback_lines(),
        "panas": panas(),
        "sequences": sequences(),
        "interlocutors": interlocutors(),
        "topics": topics(),
    }
