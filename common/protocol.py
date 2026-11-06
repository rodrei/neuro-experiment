# -*- coding: utf-8 -*-
"""
Reader of protocol/: the experiment's content as data.

This is the only module that knows how the protocol is stored; the web server
reads it through here.

Standard library only.
"""

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PROTOCOL_DIR = os.path.join(ROOT, "protocol")

MODES = ("real", "demo")
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


def texts():
    """Screen prose."""
    return _read_json("texts")


def scales():
    """Self-report scales: prompts, ticks and anchors."""
    return _read_json("scales")


def instruments():
    """UCLA-3 and ECR: their items, or an empty list while the wording of the
    validated Spanish versions is pending."""
    return _read_json("instruments")


def markers():
    """{label: code} for the event log."""
    return _read_json("markers")


def prompts():
    """Model parameters, the rules template and the task paragraph per
    feedback type (Annex A2 of the paper)."""
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


def domains():
    """The four situation domains, in elicitation order: {id, label}."""
    return _read_json("domains")


def domain_sequences():
    """Latin square of domains over conditions, independent of sequences():
    {"1": {condition: domain id}, ..., "4": {...}}."""
    return _read_json("domain_sequences")


def split_condition(condition):
    """'ai_rejection' -> ('ai', 'rejection')."""
    if condition not in CONDITIONS:
        raise ValueError("condition must be one of %s, not %r"
                         % (CONDITIONS, condition))
    agent_type, feedback = condition.split("_")
    return agent_type, feedback


def fallback_lines():
    """{feedback: {turn: text}} from protocol/fallback.csv: the lines shown
    when an LLM turn fails, which are also the prompt's style examples."""
    out = {}
    with open(os.path.join(PROTOCOL_DIR, "fallback.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.setdefault(row["feedback"], {})[int(row["turn"])] = row["text"]
    return out


def panas():
    """The 20 PANAS items, in order, from protocol/panas.csv."""
    with open(os.path.join(PROTOCOL_DIR, "panas.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def everything():
    """The whole protocol in one dict, to serve it over HTTP to the browser.

    Note: after json.dumps, the integer keys of fallback_lines() come out as
    strings ("1", "2", "3"). The browser side reads them that way.
    """
    return {
        "texts": texts(),
        "scales": scales(),
        "instruments": instruments(),
        "markers": markers(),
        "prompts": prompts(),
        "parameters": {mode: parameters(mode) for mode in MODES},
        "fallback": fallback_lines(),
        "panas": panas(),
        "sequences": sequences(),
        "domains": domains(),
        "domain_sequences": domain_sequences(),
    }
