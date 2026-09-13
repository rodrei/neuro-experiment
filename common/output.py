# -*- coding: utf-8 -*-
"""
Writing of the output CSVs, shared by the desktop and the web.

The format is the contract with the analysis scripts: four files per
participant, prefixed S1_<id>_<tag>_<stamp>. It lives here so the two
platforms cannot diverge in their columns.

Standard library only.
"""

import csv
import os

EVENT_FIELDS = ["t_experiment_s", "t_unix", "code", "label", "detail"]
CHAT_FIELDS = ["author", "text", "origin", "t_experiment_s", "latency_s"]


def base_name(participant_id, tag, stamp):
    """The prefix shared by the four files of a session."""
    return "S1_%s_%s_%s" % (participant_id, tag, stamp)


def _open(path):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    return open(path, "w", newline="", encoding="utf-8")


def write_responses(path, responses):
    """Two columns, key and value, with the keys sorted."""
    with _open(path) as f:
        w = csv.writer(f)
        for key in sorted(responses):
            w.writerow([key, responses[key]])


def write_behavioral(path, rows):
    """One row per episode. The columns are the union of every key."""
    fields = sorted({k for row in rows for k in row})
    with _open(path) as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def write_chat(path, rows):
    """Full transcript, with the origin of every agent message."""
    with _open(path) as f:
        w = csv.DictWriter(f, fieldnames=CHAT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def write_events(path, rows):
    """Same schema as the log EventLog writes on the desktop."""
    with _open(path) as f:
        w = csv.DictWriter(f, fieldnames=EVENT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def write_all(folder, base, responses, behavioral, chat, events=None):
    """Writes a session's CSVs and returns the paths.

    `events` is optional because the desktop streams it while running (see
    markers.EventLog); the web collects the log in memory and sends it at the
    end.
    """
    os.makedirs(folder, exist_ok=True)
    paths = []
    pairs = [("_responses.csv", write_responses, responses),
             ("_behavioral.csv", write_behavioral, behavioral),
             ("_chat.csv", write_chat, chat)]
    if events is not None:
        pairs.append(("_events.csv", write_events, events))
    for suffix, writer, data in pairs:
        path = os.path.join(folder, base + suffix)
        writer(path, data)
        paths.append(path)
    return paths
