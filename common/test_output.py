# -*- coding: utf-8 -*-
"""
Tests of the shared CSV writer:
    python3 -m unittest common.test_output -v

They pin the output FORMAT, which is what has to be identical between the
desktop and the web demo: if a column changes, any existing analysis script
breaks silently.
"""

import csv
import os
import tempfile
import unittest

from common import output


class TestBaseName(unittest.TestCase):

    def test_builds_the_protocol_prefix(self):
        self.assertEqual(output.base_name("07", "ai", "20260906_1200"),
                         "S1_07_ai_20260906_1200")


class TestWriteResponses(unittest.TestCase):

    def test_two_columns_with_sorted_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "r.csv")
            output.write_responses(path, {"suds": 40, "auth_1": 5})
            with open(path, encoding="utf-8") as f:
                rows = list(csv.reader(f))
        self.assertEqual(rows, [["auth_1", "5"], ["suds", "40"]])


class TestWriteBehavioral(unittest.TestCase):

    def test_unions_the_keys_of_different_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "b.csv")
            output.write_behavioral(
                path, [{"episode": 1, "feedback": "validation"},
                       {"episode": 2, "feedback": "rejection", "extra": "x"}])
            with open(path, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(sorted(rows[0]), ["episode", "extra", "feedback"])
        self.assertEqual(rows[0]["extra"], "")


class TestWriteChat(unittest.TestCase):

    def test_uses_the_fixed_fields_and_ignores_extras(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "ch.csv")
            output.write_chat(path, [
                {"author": "agent", "text": "hola", "origin": "script",
                 "t_experiment_s": 1.0, "latency_s": None, "spare": 1}])
            with open(path, encoding="utf-8") as f:
                rows = list(csv.reader(f))
        self.assertEqual(rows[0], output.CHAT_FIELDS)


class TestWriteEvents(unittest.TestCase):

    def test_same_header_as_the_desktop_log(self):
        self.assertEqual(
            output.EVENT_FIELDS,
            ["t_experiment_s", "t_unix", "code", "label", "detail"])

    def test_writes_the_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "e.csv")
            output.write_events(path, [
                {"t_experiment_s": 0.5, "t_unix": 1.0, "code": 1,
                 "label": "experiment_start", "detail": "ai"}])
            with open(path, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        self.assertEqual(rows[0]["label"], "experiment_start")


class TestWriteAll(unittest.TestCase):

    def test_returns_the_written_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = output.write_all(
                folder, "S1_x_ai_today",
                responses={"a": 1}, behavioral=[{"episode": 1}],
                chat=[{"author": "agent", "text": "hola"}],
                events=[{"t_experiment_s": 0, "t_unix": 0, "code": 1,
                         "label": "experiment_start", "detail": ""}])
            self.assertEqual(len(paths), 4)
            for p in paths:
                self.assertTrue(os.path.exists(p))

    def test_without_events_writes_three(self):
        """The desktop streams _events.csv while running, so it does not pass it."""
        with tempfile.TemporaryDirectory() as folder:
            paths = output.write_all(
                folder, "S1_x_ai_today",
                responses={"a": 1}, behavioral=[{"episode": 1}],
                chat=[{"author": "agent", "text": "hola"}])
        self.assertEqual(len(paths), 3)

    def test_creates_the_folder_if_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            target = os.path.join(folder, "data", "new")
            output.write_all(target, "S1_x_ai_today", responses={"a": 1},
                             behavioral=[{"episode": 1}], chat=[])
            self.assertTrue(os.path.isdir(target))


if __name__ == "__main__":
    unittest.main()
