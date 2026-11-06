# -*- coding: utf-8 -*-
"""
Tests of the protocol loader. They run with the system Python, without
network:  python3 -m unittest common.test_protocol -v

If a key the experiment needs is missing, it has to fail here and not in the
middle of a session.
"""

import unittest

from common import protocol


class TestTexts(unittest.TestCase):

    def test_every_prose_screen_is_present(self):
        t = protocol.texts()
        for key in ("consent", "rest", "elicitation", "instructions", "pause",
                    "final_check", "debriefing", "closing"):
            self.assertIn(key, t)
            self.assertTrue(t[key]["body"].strip(),
                            "screen %s has no body" % key)

    def test_consent_declares_the_stated_purpose_and_the_external_provider(self):
        body = protocol.texts()["consent"]["body"]
        self.assertIn("ponen en palabras experiencias emocionales", body)
        self.assertIn("OpenRouter", body)

    def test_the_consent_limits_the_external_provider_to_the_ai_conversations(self):
        body = protocol.texts()["consent"]["body"]
        self.assertIn("en las conversaciones con una inteligencia artificial", body)

    def test_announcements_are_the_exact_wording_of_the_spec(self):
        announcement = protocol.texts()["agent_announcement"]
        self.assertEqual(
            announcement["human"],
            "En esta ronda vas a conversar con otro participante del estudio.")
        self.assertEqual(
            announcement["ai"],
            "En esta ronda vas a conversar con una inteligencia artificial.")

    def test_each_agent_type_has_its_header_label(self):
        label = protocol.texts()["interlocutor_label"]
        self.assertIn("otra persona participando en el estudio", label["human"])
        self.assertIn("asistente de inteligencia artificial", label["ai"])

    def test_the_opening_names_the_domain(self):
        self.assertIn("{domain}", protocol.texts()["chat"]["opening"])

    def test_the_elicitation_names_the_domain_and_asks_for_detail(self):
        prompt = protocol.texts()["elicitation"]["prompt"]
        self.assertIn("{domain}", prompt)
        self.assertIn("mayor detalle posible", prompt)

    def test_the_debriefing_reveals_who_was_behind_each_label(self):
        body = protocol.texts()["debriefing"]["body"]
        self.assertIn("persona del equipo de investigación", body)
        self.assertIn("sistema de inteligencia artificial", body)
        self.assertNotIn("mismo sistema", body)
        self.assertNotIn("no hubo otra persona", body.lower())

    def test_the_debriefing_says_a_person_read_what_was_written(self):
        self.assertIn("leyó lo que le escribiste", protocol.texts()["debriefing"]["body"])

    def test_the_debriefing_does_not_say_a_model_replaced_the_person(self):
        debriefing = protocol.texts()["debriefing"]
        self.assertEqual(set(debriefing), {"title", "body"})
        self.assertNotIn("modelo de lenguaje", debriefing["body"])

    def test_the_demo_says_the_model_answers_the_human_condition_too(self):
        demo = protocol.texts()["demo"]
        self.assertIn("modelo de lenguaje", demo["human_note"])
        self.assertIn("una persona", demo["start_note"])

    def test_the_final_block_asks_about_suspicion_and_each_interlocutor(self):
        final = protocol.texts()["final_check"]
        self.assertTrue(final["suspicion"].strip())
        self.assertIn("{domain}", final["stood_out"])

    def test_the_demo_notice_says_nothing_is_recorded(self):
        self.assertIn("no se registra", protocol.texts()["demo"]["badge"].lower())


class TestScales(unittest.TestCase):

    def test_every_scale_is_present(self):
        s = protocol.scales()
        self.assertEqual(
            set(s),
            {"suds", "sam_valence", "sam_arousal", "authenticity",
             "manipulation_check", "naturalness", "pre_rating", "credibility",
             "ai_use", "panas"})

    def test_ticks_and_labels_have_the_same_length(self):
        """Ticks and labels are paired by position: if they do not match, the
        anchors shift and nobody notices by looking at the screen."""
        s = protocol.scales()
        for key in ("suds", "sam_valence", "sam_arousal", "authenticity",
                    "manipulation_check", "naturalness", "pre_rating",
                    "credibility"):
            self.assertEqual(len(s[key]["ticks"]), len(s[key]["labels"]),
                             "ticks and labels differ in %s" % key)
        for item in s["ai_use"]["items"]:
            self.assertEqual(len(item["ticks"]), len(item["labels"]),
                             "ticks and labels differ in %s" % item["key"])

    def test_panas_has_one_anchor_per_tick(self):
        panas = protocol.scales()["panas"]
        self.assertEqual(len(panas["ticks"]), len(panas["anchors"]))

    def test_authenticity_has_three_items_none_reversed(self):
        items = protocol.scales()["authenticity"]["items"]
        self.assertEqual([i["key"] for i in items], ["auth_1", "auth_2", "auth_3"])
        self.assertFalse(any(i["reverse"] for i in items))

    def test_suds_and_pre_rating_go_from_0_to_10(self):
        s = protocol.scales()
        for key in ("suds", "pre_rating"):
            self.assertEqual((s[key]["ticks"][0], s[key]["ticks"][-1]), (0, 10))

    def test_four_manipulation_items_two_per_component(self):
        items = protocol.scales()["manipulation_check"]["items"]
        self.assertEqual(
            [(i["key"], i["component"]) for i in items],
            [("mc_understood", "invalidation"),
             ("mc_made_sense", "invalidation"),
             ("mc_interested", "withdrawal"),
             ("mc_wanted_to_end", "withdrawal")])

    def test_naturalness_does_not_mention_the_interlocutor_identity(self):
        """It runs after every episode: naming the identity would announce
        from the first one that it is in question."""
        spec = protocol.scales()["naturalness"]
        text = (spec["prompt"] + " ".join(spec["labels"])).lower()
        for word in ("persona", "inteligencia artificial", " ia", "humano"):
            self.assertNotIn(word, text)

    def test_credibility_goes_from_ai_to_person(self):
        spec = protocol.scales()["credibility"]
        self.assertEqual((spec["ticks"][0], spec["ticks"][-1]), (0, 100))
        self.assertIn("inteligencia artificial", spec["labels"][0])
        self.assertIn("una persona", spec["labels"][-1])
        self.assertIn("{domain}", spec["prompt"])


class TestInstruments(unittest.TestCase):

    def test_ucla3_and_ecr_are_declared(self):
        instruments = protocol.instruments()
        self.assertEqual(set(instruments), {"ucla3", "ecr"})
        self.assertEqual(instruments["ucla3"]["n_items"], 20)
        self.assertEqual(instruments["ecr"]["n_items"], 36)

    def test_items_are_all_there_or_still_pending(self):
        """A half-filled instrument would be scored as if it were complete."""
        for name, block in protocol.instruments().items():
            self.assertIn(len(block["items"]), (0, block["n_items"]),
                          "%s is only partly filled in" % name)
            if block["items"]:
                self.assertEqual(len(block["ticks"]), len(block["anchors"]))


class TestParameters(unittest.TestCase):

    def test_real_mode_carries_the_protocol_timings(self):
        p = protocol.parameters("real")
        self.assertEqual(p["baseline_duration"], 300)

    def test_demo_mode_shortens_the_timings(self):
        self.assertLess(protocol.parameters("demo")["baseline_duration"],
                        protocol.parameters("real")["baseline_duration"])

    def test_common_parameters_are_in_both_modes(self):
        """The latency formula is design invariant 2: it cannot differ
        between modes."""
        for mode in ("real", "demo"):
            p = protocol.parameters(mode)
            self.assertEqual(p["latency_base"], 1.2)
            self.assertEqual(p["latency_per_char"], 0.045)
            self.assertEqual(p["latency_max"], 12.0)
            self.assertEqual(p["rounds"], 3)
            self.assertEqual(p["distress_threshold"], 9)

    def test_unknown_mode_fails(self):
        with self.assertRaises(ValueError):
            protocol.parameters("pilot")


class TestMarkers(unittest.TestCase):

    def test_the_spec_events_have_a_code(self):
        markers = protocol.markers()
        for label in ("baseline_start", "baseline_end", "episode_start",
                      "episode_end", "round_start_1", "round_start_2",
                      "round_start_3", "agent_message_1", "agent_message_2",
                      "agent_message_3", "measures_start", "measures_end",
                      "final_check_start", "final_check_end"):
            self.assertIn(label, markers)

    def test_codes_do_not_repeat(self):
        """Two events with the same code are indistinguishable when
        segmenting the signals offline."""
        codes = list(protocol.markers().values())
        self.assertEqual(len(codes), len(set(codes)))

    def test_codes_fit_in_a_byte(self):
        """Recording equipment takes event codes as one byte."""
        for label, code in protocol.markers().items():
            self.assertTrue(0 <= code <= 255,
                            "%s does not fit in a byte: %s" % (label, code))


class TestPanas(unittest.TestCase):

    def test_has_twenty_items(self):
        self.assertEqual(len(protocol.panas()), 20)

    def test_ten_per_subscale(self):
        items = protocol.panas()
        for sub in ("PA", "NA"):
            self.assertEqual(
                len([i for i in items if i["subscale"] == sub]), 10,
                "subscale %s does not have 10 items" % sub)

    def test_keys_do_not_repeat(self):
        keys = [i["key"] for i in protocol.panas()]
        self.assertEqual(len(keys), len(set(keys)))

    def test_keys_carry_their_subscale_prefix(self):
        for item in protocol.panas():
            self.assertTrue(item["key"].startswith(item["subscale"].lower() + "_"),
                            "%s does not start with its subscale" % item["key"])


class TestEverything(unittest.TestCase):

    def test_carries_every_section(self):
        self.assertEqual(
            set(protocol.everything()),
            {"texts", "scales", "markers", "prompts", "parameters", "panas",
             "sequences", "domain_sequences", "domains", "instruments",
             "fallback"})

    def test_is_json_serializable(self):
        """The browser consumes it via GET /api/protocol."""
        import json
        self.assertTrue(json.dumps(protocol.everything()))


class TestSequences(unittest.TestCase):

    def test_four_sequences_of_four(self):
        seqs = protocol.sequences()
        self.assertEqual(sorted(seqs), ["1", "2", "3", "4"])
        for s in seqs.values():
            self.assertEqual(sorted(s), sorted(protocol.CONDITIONS))

    def test_is_a_latin_square(self):
        seqs = protocol.sequences()
        for position in range(4):
            column = [seqs[k][position] for k in sorted(seqs)]
            self.assertEqual(sorted(column), sorted(protocol.CONDITIONS))

    def test_split_condition(self):
        self.assertEqual(protocol.split_condition("ai_rejection"),
                         ("ai", "rejection"))
        with self.assertRaises(ValueError):
            protocol.split_condition("robot_love")


class TestDomains(unittest.TestCase):

    def test_the_four_domains_in_order(self):
        self.assertEqual(
            [d["label"] for d in protocol.domains()],
            ["el trabajo o el estudio", "una amistad",
             "tu familia o tu pareja", "vos mismo"])

    def test_ids_are_unique(self):
        ids = [d["id"] for d in protocol.domains()]
        self.assertEqual(len(ids), len(set(ids)))


class TestDomainSequences(unittest.TestCase):

    def test_every_row_gives_each_condition_a_different_domain(self):
        ids = sorted(d["id"] for d in protocol.domains())
        rows = protocol.domain_sequences()
        self.assertEqual(sorted(rows), ["1", "2", "3", "4"])
        for row in rows.values():
            self.assertEqual(sorted(row), sorted(protocol.CONDITIONS))
            self.assertEqual(sorted(row.values()), ids)

    def test_every_condition_meets_every_domain_across_rows(self):
        """Without this a domain would be confounded with a condition."""
        ids = sorted(d["id"] for d in protocol.domains())
        rows = protocol.domain_sequences().values()
        for condition in protocol.CONDITIONS:
            self.assertEqual(sorted(row[condition] for row in rows), ids)


class TestFallbackLines(unittest.TestCase):

    def test_three_per_feedback(self):
        lines = protocol.fallback_lines()
        self.assertEqual(set(lines), {"validation", "rejection"})
        for feedback in lines:
            self.assertEqual(sorted(lines[feedback]), [1, 2, 3])

    def test_lines_are_balanced_in_length(self):
        """Invariant 2: the agent latency is a function of length, so
        unbalanced lines would make the wait differ by condition."""
        lines = protocol.fallback_lines()
        length = {f: sum(len(x) for x in lines[f].values())
                  for f in ("validation", "rejection")}
        difference = abs(length["validation"] - length["rejection"])
        self.assertLess(difference, 0.20 * max(length.values()),
                        "the lines differ by more than 20%% in length: %s"
                        % length)

    def test_lines_fit_the_message_cap(self):
        cap = protocol.prompts()["max_chars"]
        for block in protocol.fallback_lines().values():
            for line in block.values():
                self.assertLessEqual(len(line), cap)


class TestPrompts(unittest.TestCase):

    def test_uses_the_model_of_the_spec(self):
        self.assertEqual(protocol.prompts()["model"],
                         "anthropic/claude-haiku-4.5")
        self.assertEqual(protocol.prompts()["max_chars"], 350)

    def test_the_rules_have_the_placeholders(self):
        rules = protocol.prompts()["rules"]
        for ph in ("{role}", "{max_chars}", "{examples}"):
            self.assertIn(ph, rules)

    def test_one_task_paragraph_per_feedback(self):
        self.assertEqual(set(protocol.prompts()["role"]),
                         {"validation", "rejection"})


if __name__ == "__main__":
    unittest.main()
