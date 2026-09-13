# -*- coding: utf-8 -*-
"""
Tests of the protocol loader. They run with the system Python, without
network and without PsychoPy:  python3 -m unittest common.test_protocol -v

There is no automated suite on the PsychoPy side, so these tests are the only
net that catches a half-done extraction: if a key the desktop needs is
missing, it has to fail here and not in the middle of a session.
"""

import unittest

from common import protocol


class TestTexts(unittest.TestCase):

    def test_every_prose_screen_is_present(self):
        t = protocol.texts()
        for key in ("consent", "rest", "pause", "closing"):
            self.assertIn(key, t)
            self.assertTrue(t[key]["body"].strip(),
                            "screen %s has no body" % key)
        self.assertIn("debriefing", t)

    def test_cover_story_has_both_conditions(self):
        cover = protocol.texts()["cover_story"]
        self.assertEqual(set(cover), {"human", "ai"})

    def test_the_two_cover_stories_differ(self):
        """It is the only manipulation of the between-subjects factor: if
        they were equal, the experiment manipulates nothing."""
        cover = protocol.texts()["cover_story"]
        self.assertNotEqual(cover["human"], cover["ai"])

    def test_manipulation_check_has_the_five_questions(self):
        check = protocol.texts()["manipulation_check"]
        self.assertEqual(
            set(check),
            {"believed_real_person", "suspicion_1", "suspicion_2",
             "suspicion_3", "consents_after_debriefing"})


class TestDesktopDebriefing(unittest.TestCase):
    """On the desktop the debriefing is the screen where the participant
    stops being deceived: it has to tell the truth of the mode that ran."""

    def test_one_version_per_agent_mode(self):
        bodies = protocol.texts()["desktop_debriefing"]["body"]
        self.assertEqual(set(bodies), {"scripted", "llm"})

    def test_returns_title_and_body(self):
        for agent in ("scripted", "llm"):
            d = protocol.desktop_debriefing(agent)
            self.assertEqual(set(d), {"title", "body"})
            self.assertTrue(d["body"].strip())

    def test_the_two_versions_differ(self):
        self.assertNotEqual(protocol.desktop_debriefing("scripted")["body"],
                            protocol.desktop_debriefing("llm")["body"])

    def test_only_the_scripted_one_claims_everything_was_written(self):
        """The sentence that was false in LLM mode and motivated the split."""
        self.assertIn("escritos de antemano",
                      protocol.desktop_debriefing("scripted")["body"])
        self.assertNotIn("Todos los mensajes que recibiste estaban escritos",
                         protocol.desktop_debriefing("llm")["body"])

    def test_the_llm_one_says_a_model_generated_them(self):
        body = protocol.desktop_debriefing("llm")["body"]
        self.assertIn("modelo de lenguaje", body)

    def test_both_deny_there_was_another_person(self):
        """The 'human' cover story is the deception to lift, whichever mode
        ran."""
        for agent in ("scripted", "llm"):
            self.assertIn("no había",
                          protocol.desktop_debriefing(agent)["body"].lower())

    def test_both_state_the_rejection_was_not_personal(self):
        """What has to be said before the participant leaves."""
        for agent in ("scripted", "llm"):
            self.assertIn("con lo que contaste",
                          protocol.desktop_debriefing(agent)["body"],
                          "the %s debriefing does not detach the person from "
                          "the rejection" % agent)

    def test_unknown_agent_fails(self):
        with self.assertRaises(ValueError):
            protocol.desktop_debriefing("human")


class TestScales(unittest.TestCase):

    def test_every_scale_is_present(self):
        s = protocol.scales()
        self.assertEqual(
            set(s),
            {"suds", "sam_valence", "sam_arousal", "authenticity", "panas"})

    def test_ticks_and_labels_have_the_same_length(self):
        """PsychoPy pairs ticks with labels by position: if they do not
        match, the anchors shift and nobody notices by looking at the
        screen."""
        s = protocol.scales()
        for key in ("suds", "sam_valence", "sam_arousal", "authenticity"):
            self.assertEqual(len(s[key]["ticks"]), len(s[key]["labels"]),
                             "ticks and labels differ in %s" % key)

    def test_panas_has_one_anchor_per_tick(self):
        panas = protocol.scales()["panas"]
        self.assertEqual(len(panas["ticks"]), len(panas["anchors"]))

    def test_authenticity_has_three_items_none_reversed(self):
        items = protocol.scales()["authenticity"]["items"]
        self.assertEqual([i["key"] for i in items], ["auth_1", "auth_2", "auth_3"])
        self.assertFalse(any(i["reverse"] for i in items))


class TestParameters(unittest.TestCase):

    def test_real_mode_carries_the_protocol_timings(self):
        p = protocol.parameters("real")
        self.assertEqual(p["baseline_duration"], 300)

    def test_demo_mode_shortens_the_timings(self):
        self.assertLess(protocol.parameters("demo")["baseline_duration"],
                        protocol.parameters("real")["baseline_duration"])

    def test_common_parameters_are_in_both_modes(self):
        """The latency formula is design invariant 2: it cannot differ
        between modes or platforms."""
        for mode in ("real", "demo"):
            p = protocol.parameters(mode)
            self.assertEqual(p["latency_base"], 1.2)
            self.assertEqual(p["latency_per_char"], 0.045)
            self.assertEqual(p["latency_max"], 12.0)

    def test_unknown_mode_fails(self):
        with self.assertRaises(ValueError):
            protocol.parameters("pilot")


class TestMarkers(unittest.TestCase):

    def test_the_twenty_two_codes_are_there(self):
        self.assertEqual(len(protocol.markers()), 22)

    def test_the_debate_markers_are_there(self):
        for label in ("interlocutor_intro", "topic_shown", "topic_chosen",
                      "opinion_sent"):
            self.assertIn(label, protocol.markers())

    def test_codes_do_not_repeat(self):
        """Two events with the same code are indistinguishable when
        segmenting the EDA offline."""
        codes = list(protocol.markers().values())
        self.assertEqual(len(codes), len(set(codes)))

    def test_codes_fit_in_a_byte(self):
        """The serial and parallel backends send the code as one byte."""
        for label, code in protocol.markers().items():
            self.assertTrue(0 <= code <= 255,
                            "%s does not fit in a byte: %s" % (label, code))


class TestScripts(unittest.TestCase):

    def test_both_greetings_are_there(self):
        s = protocol.scripts()
        self.assertIn("greeting", s)
        self.assertIn("greeting2", s)

    def test_each_feedback_has_three_turns(self):
        s = protocol.scripts()
        for feedback in ("validation", "rejection"):
            self.assertEqual(sorted(s[feedback]), [1, 2, 3],
                             "turns missing in %s" % feedback)

    def test_turns_are_balanced_in_length(self):
        """Invariant 2: the agent latency is a function of length, so
        unbalanced scripts would make the wait differ by condition."""
        s = protocol.scripts()
        length = {f: sum(len(x) for x in s[f].values())
                  for f in ("validation", "rejection")}
        difference = abs(length["validation"] - length["rejection"])
        self.assertLess(difference, 0.20 * max(length.values()),
                        "the scripts differ by more than 20%% in length: %s"
                        % length)


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

    def test_carries_the_eleven_sections(self):
        self.assertEqual(
            set(protocol.everything()),
            {"texts", "scales", "markers", "prompts", "parameters",
             "scripts", "panas", "sequences", "interlocutors", "topics",
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


class TestInterlocutors(unittest.TestCase):

    def test_two_per_type_with_distinct_names(self):
        people = protocol.interlocutors()
        self.assertEqual(len(people), 4)
        self.assertEqual(len({p["name"] for p in people}), 4)
        self.assertEqual(sum(p["type"] == "human" for p in people), 2)
        self.assertEqual(sum(p["type"] == "ai" for p in people), 2)


class TestTopics(unittest.TestCase):

    def test_eight_topics_with_unique_ids_and_questions(self):
        topics = protocol.topics()
        self.assertEqual(len(topics), 8)
        self.assertEqual(len({t["id"] for t in topics}), 8)
        for t in topics:
            self.assertTrue(t["question"].endswith("?"))
            self.assertTrue(t["category"])


class TestFallbackLines(unittest.TestCase):

    def test_three_per_feedback(self):
        lines = protocol.fallback_lines()
        self.assertEqual(set(lines), {"validation", "rejection"})
        for feedback in lines:
            self.assertEqual(sorted(lines[feedback]), [1, 2, 3])


class TestDebatePrompts(unittest.TestCase):

    def test_debate_rules_have_the_placeholders(self):
        debate = protocol.prompts()["debate"]
        for ph in ("{name}", "{question}", "{role}", "{max_chars}"):
            self.assertIn(ph, debate["rules"])
        self.assertEqual(set(debate["role"]), {"validation", "rejection"})

    def test_situation_prompts_still_there_for_the_desktop(self):
        situation = protocol.prompts()["situation"]
        self.assertIn("{examples}", situation["rules"])
        self.assertEqual(set(situation["role"]), {"validation", "rejection"})


class TestWebTexts(unittest.TestCase):

    def test_new_screens_present(self):
        t = protocol.texts()
        for key in ("instructions", "interlocutor_intro", "topic_pick",
                    "topic_card", "interlocutor_label", "debriefing"):
            self.assertIn(key, t)
        self.assertIn("{name}", t["interlocutor_intro"]["human"])
        self.assertIn("{name}", t["interlocutor_intro"]["ai"])
        self.assertIn("{name}", t["interlocutor_label"]["ai"])
        self.assertTrue(t["topic_card"]["hint"].strip())
        self.assertIsInstance(t["debriefing"]["body"], str)

    def test_opinion_has_no_minimum_length_but_a_test_filler(self):
        p = protocol.parameters("demo")
        self.assertNotIn("min_opinion_chars", p)
        self.assertTrue(p["test_filler_opinion"].strip())


if __name__ == "__main__":
    unittest.main()
