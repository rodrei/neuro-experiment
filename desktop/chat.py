# -*- coding: utf-8 -*-
"""
Chat interface engine.

It is the central piece of the experiment: PsychoPy Builder has no chat
component, so the conversation window is drawn by hand with TextBox2
(bubbles) on a Window in 'height' units.

What matters for the design:
  - The agent is FULLY SCRIPTED. No live operator is needed.
  - The agent latency is DETERMINISTIC (a function of the message length),
    so it is identical between the Human and AI conditions. That is exactly
    the control the design asks for: only the attributed source varies.
  - The participant tells their situation INSIDE the chat, when the agent
    asks for it. It is not requested up front on a software screen: that
    broke the cover story right before measuring it.
  - Every message leaves a timestamped marker, to segment the EDA afterwards.

Technical note: bubbles are built ONCE per message and then only
repositioned. Building a TextBox2 forces a font layout, which is expensive;
doing it every frame dropped the fps to the floor.
"""

from psychopy import visual, core, event

import config
import scales

BUBBLE_PADDING = 0.018
LINE_SPACING = 1.06        # measured on TextBox2: line step / letterHeight
BUBBLE_GAP = 0.022         # air between bubbles


class Chat(object):
    """Conversation window."""

    def __init__(self, win, log, agent_label):
        self.win = win
        self.log = log
        self.agent_label = agent_label
        self.messages = []          # (author, text, t)
        self.bubbles = []           # (TextBox2, height) in the same order
        self.transcript = []

        ar = win.size[0] / float(win.size[1])
        self.x_left = -ar / 2 + 0.06
        self.x_right = ar / 2 - 0.06
        self.y_top = 0.39
        self.y_bottom = -0.30

        self.bar = visual.Rect(
            win, width=ar, height=0.10, pos=(0, 0.45),
            fillColor=config.COLOR_BAR, lineColor=None)
        self.title = visual.TextStim(
            win, text=agent_label, font=config.FONT,
            height=0.028, color=config.COLOR_TEXT,
            pos=(self.x_left, 0.465), anchorHoriz="left", alignText="left")
        self.status = visual.TextStim(
            win, text="en línea", font=config.FONT,
            height=0.022, color=config.COLOR_MUTED,
            pos=(self.x_left, 0.428), anchorHoriz="left", alignText="left")

        self.box = visual.TextBox2(
            win, text="", font=config.FONT,
            pos=(self.x_left + 0.30, -0.40), size=(0.66, 0.12),
            letterHeight=config.LETTER_HEIGHT, color=config.COLOR_TEXT,
            fillColor="#FFFFFF", borderColor="#D0D0D4", borderWidth=2,
            padding=0.014, anchor="center", alignment="top-left",
            editable=True, placeholder="Escribí tu mensaje…")

        self.button = visual.Rect(
            win, width=0.16, height=0.075, pos=(self.x_left + 0.72, -0.40),
            fillColor=config.COLOR_ACCENT, lineColor=None)
        self.button_text = visual.TextStim(
            win, text="Enviar", font=config.FONT, height=0.026,
            color="#FFFFFF", pos=(self.x_left + 0.72, -0.40))
        self.help = visual.TextStim(
            win, text="Enter para enviar", font=config.FONT, height=0.019,
            color=config.COLOR_MUTED, pos=(self.x_left + 0.72, -0.455))

        self.mouse = event.Mouse(win=win)
        self.skip = scales.skip_button(win)

    def _skip_requested(self):
        """True if, in test mode, skipping the wait or the turn was requested."""
        if scales.skip_requested(self.skip, self.mouse):
            scales.release_mouse(self.win, self.mouse)
            return True
        return False

    # -----------------------------------------------------------------
    # bubble construction
    # -----------------------------------------------------------------
    def _build_bubble(self, author, text):
        """Creates the bubble measuring the real height the text takes."""
        if author == "agent":
            x, anchor = self.x_left, "left"
            fill, border = config.COLOR_BUBBLE_AGENT, "#E6E6EA"
        else:
            x, anchor = self.x_right, "right"
            fill, border = config.COLOR_BUBBLE_PARTICIPANT, None

        shared = dict(
            win=self.win, text=text, font=config.FONT,
            letterHeight=config.LETTER_HEIGHT, color=config.COLOR_TEXT,
            fillColor=fill, borderColor=border, padding=BUBBLE_PADDING,
            anchor=anchor, alignment="top-left", editable=False)

        # 1) provisional layout, only to count lines
        provisional = visual.TextBox2(
            pos=(0, 0), size=(config.BUBBLE_MAX_WIDTH, 0.5), **shared)
        n_lines = max(1, len(getattr(provisional, "_lineLenChars", [1])))

        # 2) final bubble, with the exact height
        height = (n_lines * config.LETTER_HEIGHT * LINE_SPACING
                  + 2 * BUBBLE_PADDING + 0.006)
        bubble = visual.TextBox2(
            pos=(x, 0), size=(config.BUBBLE_MAX_WIDTH, height), **shared)
        return bubble, height

    # -----------------------------------------------------------------
    # drawing
    # -----------------------------------------------------------------
    def _draw_messages(self):
        """Bottom up: the newest at the bottom, older ones move up."""
        y = self.y_bottom
        for (bubble, height), (author, _text, _t) in zip(
                reversed(self.bubbles), reversed(self.messages)):
            if y > self.y_top:
                break                      # already off screen
            x = self.x_left if author == "agent" else self.x_right
            bubble.pos = (x, y + height / 2.0)
            bubble.draw()
            y += height + BUBBLE_GAP

    def draw(self, show_input=True):
        # messages first: if one goes past the top, the bar covers it
        self._draw_messages()
        self.bar.draw()
        self.title.draw()
        self.status.draw()
        if show_input:
            self.box.draw()
            self.button.draw()
            self.button_text.draw()
            self.help.draw()
        scales.draw_skip(self.skip)
        self.win.flip()

    # -----------------------------------------------------------------
    # turns
    # -----------------------------------------------------------------
    def _add(self, author, text, origin=None):
        t = self.log.clock.getTime()
        self.messages.append((author, text, t))
        self.bubbles.append(self._build_bubble(author, text))
        row = {"author": author, "text": text, "t_experiment_s": round(t, 4)}
        if origin:
            row["origin"] = origin
        self.transcript.append(row)

    def latency_of(self, text):
        """Deterministic: same message -> same wait, in both conditions."""
        p = config.PARAMETERS
        t = p["latency_base"] + len(text) * p["latency_per_char"]
        return min(t, p["latency_max"])

    def agent_says(self, text, marker_label=None, origin="script"):
        """Shows 'escribiendo…', waits the latency, and posts the message."""
        wait = self.latency_of(text)

        self.status.text = "en línea"
        end = core.getTime() + config.PARAMETERS["min_reading_time"]
        while core.getTime() < end:
            self.draw()
            if self._skip_requested():
                break

        self.status.text = "escribiendo…"
        end = core.getTime() + wait
        while core.getTime() < end:
            self.draw()
            if self._skip_requested():
                break

        self.status.text = "en línea"
        self._add("agent", text, origin=origin)
        if marker_label:
            self.log.mark(marker_label, text[:60])
        self.draw()

    def wait_for_participant(self, timeout=None, min_chars=0,
                             marker="participant_message"):
        """Lets the participant write. Returns (text, latency_s).

        Sent with Enter (the box receives a trailing '\\n') or with the
        button. If `min_chars` > 0, sending is blocked until the minimum is
        reached and the shortfall is shown. If `timeout` runs out with no
        text, returns ("", None): in the free-reply window, not answering
        is a data point.
        """
        try:
            self.win.currentEditable = self.box
        except Exception:
            pass
        self.box.clear()
        self.box.text = ""

        t0 = core.getTime()
        deadline = None if timeout is None else t0 + timeout

        while True:
            text = self.box.getText()
            clean = text.strip()
            enough = len(clean) >= min_chars

            if min_chars and not enough:
                self.help.text = ("Al menos %d caracteres (llevás %d)"
                                  % (min_chars, len(clean)))
            else:
                self.help.text = "Enter para enviar"

            # Enter
            if text.endswith("\n"):
                if clean and enough:
                    return self._send(clean, t0, marker)
                # not enough yet: drop the newline but keep what was typed
                self.box.text = text.rstrip("\n")

            # Send button
            if self.mouse.isPressedIn(self.button):
                if clean and enough:
                    while self.mouse.getPressed()[0]:
                        self.draw()
                    return self._send(clean, t0, marker)

            # time is up
            if deadline is not None and core.getTime() > deadline:
                if clean:
                    return self._send(clean, t0, marker)
                return self._no_reply(marker)

            # test mode: sends whatever there is, and if the message was
            # mandatory fills it in so the conversation still has a topic
            if self._skip_requested():
                if clean and enough:
                    return self._send(clean, t0, marker)
                if min_chars:
                    self.box.clear()
                    self.box.text = ""
                    return self._send(
                        config.PARAMETERS["test_filler_text"], t0, marker)
                return self._no_reply(marker)

            self.draw()

    def _no_reply(self, marker):
        """Not answering is a data point: it is recorded as such."""
        self.log.mark(marker, "no reply")
        self.transcript.append({
            "author": "participant", "text": "[sin respuesta]",
            "t_experiment_s": round(self.log.clock.getTime(), 4)})
        self.help.text = "Enter para enviar"
        return "", None

    def _send(self, text, t0, marker="participant_message"):
        latency = core.getTime() - t0
        self._add("participant", text)
        self.log.mark(marker, "latency=%.2f" % latency)
        self.transcript[-1]["latency_s"] = round(latency, 3)
        self.box.clear()
        self.box.text = ""
        self.help.text = "Enter para enviar"
        self.draw()
        core.wait(0.4)
        return text, latency

    def clear(self):
        self.messages = []
        self.bubbles = []
