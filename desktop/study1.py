# -*- coding: utf-8 -*-
"""
STUDY 1 — Validation and rejection: AI vs. human agent
Neurodiplo, Group 3 · AI companions

Design: 2 x 2 mixed
  · Agent type (Human vs. AI)  ............ between-subjects, set at start
  · Feedback (Validation vs. Rejection) ... within-subject, counterbalanced

Run with:  PsychoPy Coder  ->  open this file  ->  Run
or from the terminal, see the README.

Quit at any time: Ctrl + Q
"""

import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from psychopy import visual, core, event, gui

import config
import scales
from common.llm_agent import LLMAgent, load_api_key
from common import protocol, output
from chat import Chat
from markers import EventLog


# =====================================================================
# 1. Initial dialog
# =====================================================================
def initial_dialog():
    info = {
        "participant_id": "",
        "age": "",
        "sex": ["mujer", "varón", "otro / prefiero no decir"],
        "agent_condition": ["human", "ai"],
        "order": ["1 = validation first", "2 = rejection first"],
        "records_eeg": False,
    }
    dlg = gui.DlgFromDict(
        info, title="Study 1 — AI companions",
        order=["participant_id", "age", "sex", "agent_condition",
               "order", "records_eeg"])
    if not dlg.OK:
        core.quit()
    if not info["participant_id"].strip():
        info["participant_id"] = "no_id"
    info["order"] = 1 if info["order"].startswith("1") else 2
    return info


def load_scripts():
    return protocol.scripts()


# =====================================================================
# 2. One chat episode (validation or rejection)
# =====================================================================
def run_episode(win, chat, log, scripts, feedback, episode_number,
                agent=None):
    """feedback: 'validation' or 'rejection'. Returns a dict of behavioral data.

    The participant tells their situation INSIDE the chat: the agent asks for
    it and they write it right there. That way the cover story does not
    break.

    If `agent` (LLMAgent) is not None, the model generates the three turns;
    the greeting stays scripted. If the API fails, the turn falls back to
    the script.
    """
    chat.clear()
    log.mark("episode_start", "%d_%s" % (episode_number, feedback))

    # connection screen (standardised across conditions)
    waiting = visual.TextStim(
        win, text=protocol.texts()["connecting"], font=config.FONT,
        height=0.040, color=config.COLOR_MUTED, pos=(0, 0))
    skip = scales.skip_button(win)
    mouse = event.Mouse(win=win)
    end = core.getTime() + config.PARAMETERS["connecting_duration"]
    while core.getTime() < end:
        waiting.draw()
        scales.draw_skip(skip)
        win.flip()
        if scales.skip_requested(skip, mouse):
            scales.release_mouse(win, mouse)
            break

    data = {"episode": episode_number, "feedback": feedback}

    # the agent asks for the situation (neutral greeting, identical across
    # conditions, ALWAYS scripted: it has to ask for it no matter what)
    greeting_key = "greeting" if episode_number == 1 else "greeting2"
    chat.agent_says(scripts[greeting_key][0],
                    marker_label="agent_asks_situation")
    if agent is not None:
        agent.greet(scripts[greeting_key][0])

    # the participant tells it here, in the chat
    situation, situation_latency = chat.wait_for_participant(
        timeout=config.PARAMETERS["situation_timeout"],
        min_chars=config.PARAMETERS["min_situation_chars"],
        marker="situation_revealed")
    data["situation"] = situation
    data["situation_chars"] = len(situation)
    data["situation_latency_s"] = situation_latency
    if agent is not None:
        agent.hear(situation or "(no responde)")

    # three agent turns, with a free participant reply in between
    for turn in (1, 2, 3):
        if agent is not None:
            # generated in a thread; meanwhile the screen stays "en línea",
            # like someone reading. The visible latency is applied afterwards
            # in agent_says(), as a function of length.
            pending = agent.reply_in_thread(scripts[feedback][turn])
            while not pending.ready():
                chat.draw()
            turn_text, origin, _reason = pending.result()
        else:
            turn_text, origin = scripts[feedback][turn], "script"
        chat.agent_says(turn_text,
                        marker_label="agent_message_%d" % turn,
                        origin=origin)
        if turn < 3:
            text, latency = chat.wait_for_participant(timeout=90)
            data["reply_%d" % turn] = text
            data["reply_latency_%d" % turn] = latency
            if agent is not None:
                agent.hear(text or "(no responde)")

    # final free-reply window: they may answer or not.
    # The latency here is a behavioral DV of the design.
    log.mark("free_reply_start", feedback)
    text, latency = chat.wait_for_participant(
        timeout=config.PARAMETERS["free_reply_window"])
    data["final_reply"] = text
    data["final_latency_s"] = latency
    data["replied_at_end"] = int(bool(text))

    log.mark("episode_end", "%d_%s" % (episode_number, feedback))
    return data


# =====================================================================
# 3. Main program
# =====================================================================
def main():
    info = initial_dialog()
    scripts = load_scripts()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = output.base_name(info["participant_id"],
                            info["agent_condition"], stamp)
    folder = os.path.join(ROOT, "data")
    os.makedirs(folder, exist_ok=True)

    win = visual.Window(
        size=config.WINDOW_SIZE, fullscr=config.FULLSCREEN,
        color=config.COLOR_BACKGROUND, units="height", allowGUI=False,
        winType="pyglet")
    win.mouseVisible = True

    event.globalKeys.clear()
    event.globalKeys.add(key="q", modifiers=["ctrl"], func=core.quit)

    clock = core.Clock()
    log = EventLog(
        os.path.join(folder, base + "_events.csv"),
        clock, backend=config.MARKER_BACKEND)
    log.mark("experiment_start", info["agent_condition"])

    txt = protocol.texts()
    chat = Chat(win, log, txt["agent_label"][info["agent_condition"]])
    responses = dict(info)
    responses["file"] = base
    responses["platform"] = "desktop"

    # Agent mode: scripted (the original design) or LLM via OpenRouter.
    use_llm = config.AGENT == "llm"
    if use_llm and not load_api_key():
        print("NOTICE: AGENT='llm' but there is no API key (OPENROUTER_API_KEY "
              "or openrouter_key.txt). Every turn will fall back to the script.")
    responses["agent"] = config.AGENT
    responses["test_mode"] = config.TEST_MODE
    if config.TEST_MODE:
        print("NOTICE: TEST_MODE is on. Every screen can be skipped with the "
              "'Saltar' button or with %s, and whatever is skipped stays "
              "empty in the CSVs. Not for participants."
              % config.SKIP_KEY.upper())
    if use_llm:
        responses["llm_model"] = protocol.prompts()["model"]

    # ---------------------------------------------------------------
    # Consent and instructions
    # ---------------------------------------------------------------
    scales.text_screen(win, txt["desktop_consent"]["body"],
                       title=txt["desktop_consent"]["title"])

    # ---------------------------------------------------------------
    # Physiological baseline
    # ---------------------------------------------------------------
    scales.text_screen(win, txt["rest"]["body"], title=txt["rest"]["title"])

    log.mark("baseline_start")
    scales.countdown(win, config.PARAMETERS["baseline_duration"])
    log.mark("baseline_end")

    # NOTE: the authenticity items do NOT go in the baseline. There is no
    # interlocutor to rate yet.
    baseline_measures = scales.measures_block(win, log, "baseline",
                                              include_authenticity=False)
    responses.update({"baseline_" + k: v for k, v in baseline_measures.items()})

    # ---------------------------------------------------------------
    # Cover story (the between-subjects factor is manipulated here)
    # ---------------------------------------------------------------
    scales.text_screen(win, txt["cover_story"][info["agent_condition"]],
                       title=txt["cover_story_title"])

    # ---------------------------------------------------------------
    # The two episodes, in the counterbalanced order.
    # The personal situation is told inside each chat.
    # ---------------------------------------------------------------
    sequence = (["validation", "rejection"] if info["order"] == 1
                else ["rejection", "validation"])

    behavioral = []
    for i, feedback in enumerate(sequence, start=1):
        # a new LLMAgent per episode: every conversation starts from scratch
        agent = (LLMAgent(feedback, timeout=config.LLM_TIMEOUT)
                 if use_llm else None)
        data = run_episode(win, chat, log, scripts, feedback, i, agent=agent)
        behavioral.append(data)
        responses["situation_%d" % i] = data["situation"]

        measures = scales.measures_block(win, log, feedback)
        responses.update({"%s_%s" % (feedback, k): v for k, v in measures.items()})

        if i < len(sequence):
            scales.text_screen(win, txt["desktop_pause"]["body"],
                               title=txt["desktop_pause"]["title"])

    # ---------------------------------------------------------------
    # Manipulation check + funnel debriefing
    # ---------------------------------------------------------------
    log.mark("manipulation_check")

    check = txt["manipulation_check"]
    belief = check["believed_real_person"]
    responses["believed_real_person"] = scales.ask_scale(
        win, belief["prompt"], belief["ticks"], belief["labels"])

    for key in ("suspicion_1", "suspicion_2", "suspicion_3"):
        responses[key] = scales.ask_text(win, check[key], min_chars=1)

    # ---------------------------------------------------------------
    # Debriefing
    # ---------------------------------------------------------------
    # The debriefing depends on the mode the agent ran in: with "llm" the
    # messages were not written in advance, and saying so would be lying on
    # the very screen where the lying stops.
    deb = protocol.desktop_debriefing(config.AGENT)
    scales.text_screen(win, deb["body"], title=deb["title"])

    consents = check["consents_after_debriefing"]
    responses["consents_after_debriefing"] = scales.ask_scale(
        win, consents["prompt"], consents["ticks"], consents["labels"])

    scales.text_screen(win, txt["closing"]["body"],
                       footer=txt["closing"]["footer"])

    # ---------------------------------------------------------------
    # Save
    # ---------------------------------------------------------------
    log.mark("experiment_end")

    # _events.csv is not written here: EventLog has been streaming it since
    # the session started.
    output.write_all(folder, base,
                     responses=responses,
                     behavioral=behavioral,
                     chat=chat.transcript)

    log.close()
    win.close()
    core.quit()


if __name__ == "__main__":
    main()
