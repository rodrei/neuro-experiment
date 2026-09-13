# -*- coding: utf-8 -*-
"""
Instruction screens and self-report scales.

SAM: for now it is presented as a 9-point numeric scale with verbal anchors.
For the original pictorial version (the manikins), put the PNGs in
protocol/sam/ and the code already draws them above the scale. See the
README.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from psychopy import visual, core, event

import config
from common import protocol

SAM_DIR = os.path.join(ROOT, "protocol", "sam")
USE_SAM_IMAGES = os.path.isdir(SAM_DIR)


# ---------------------------------------------------------------------
def _button(win, text, pos=(0, -0.40), size=(0.24, 0.075), height=0.026,
            color=None):
    box = visual.Rect(win, width=size[0], height=size[1], pos=pos,
                      fillColor=color or config.COLOR_ACCENT, lineColor=None)
    label = visual.TextStim(win, text=text, font=config.FONT,
                            height=height, color="#FFFFFF", pos=pos)
    return box, label


# ---------------------------------------------------------------------
# Test mode: skipping screens
# ---------------------------------------------------------------------
# Also used by chat.py and study1.py, so the button is in the same place on
# every screen. Bottom right: nothing is there on any screen, not even at the
# narrowest aspect ratio.
SKIP_POS = (0.52, -0.455)


def skip_button(win):
    """The test-mode 'Saltar' button. Outside test mode, (None, None)."""
    if not config.TEST_MODE:
        return None, None
    return _button(win, "Saltar (%s)" % config.SKIP_KEY.upper(),
                   pos=SKIP_POS, size=(0.22, 0.055), height=0.021,
                   color=config.COLOR_MUTED)


def draw_skip(button):
    """Draws the skip button, if there is one."""
    if button[0] is not None:
        button[0].draw()
        button[1].draw()


def skip_requested(button=(None, None), mouse=None):
    """True if test mode is on and skipping the screen was requested.

    The key is ALWAYS polled with keyList: that way event.getKeys() leaves
    the rest of the buffer intact, which is what screens with an editable
    TextBox2 need to keep receiving what is typed.
    """
    if not config.TEST_MODE:
        return False
    if event.getKeys(keyList=[config.SKIP_KEY]):
        return True
    return bool(button[0] is not None and mouse is not None
                and mouse.isPressedIn(button[0]))


def release_mouse(win, mouse):
    """Waits for the button to be released: one click must not skip twice."""
    while mouse.getPressed()[0]:
        win.flip()


def text_screen(win, text, footer="Presioná ESPACIO para continuar",
                title=None, height=0.032):
    """Shows a block of text and waits for the space bar."""
    body = visual.TextStim(
        win, text=text, font=config.FONT, height=height,
        color=config.COLOR_TEXT, pos=(0, 0.02), wrapWidth=1.15,
        alignText="left")
    heading = None
    if title:
        heading = visual.TextStim(
            win, text=title, font=config.FONT, height=0.045, bold=True,
            color=config.COLOR_ACCENT, pos=(0, 0.34), wrapWidth=1.15)
    notice = visual.TextStim(
        win, text=footer, font=config.FONT, height=0.024,
        color=config.COLOR_MUTED, pos=(0, -0.42))

    skip = skip_button(win)
    mouse = event.Mouse(win=win)
    event.clearEvents()
    while True:
        if heading:
            heading.draw()
        body.draw()
        notice.draw()
        draw_skip(skip)
        win.flip()
        if event.getKeys(keyList=["space"]):
            return
        if skip_requested(skip, mouse):
            release_mouse(win, mouse)
            return


def countdown(win, duration, text=None):
    """Physiological baseline: fixation cross for `duration` seconds."""
    if text is None:
        text = protocol.texts()["rest_caption"]
    cross = visual.TextStim(win, text="+", font=config.FONT, height=0.12,
                            color=config.COLOR_TEXT, pos=(0, 0))
    caption = visual.TextStim(win, text=text, font=config.FONT, height=0.026,
                              color=config.COLOR_MUTED, pos=(0, -0.32),
                              wrapWidth=1.0)
    skip = skip_button(win)
    mouse = event.Mouse(win=win)
    end = core.getTime() + duration
    while core.getTime() < end:
        cross.draw()
        caption.draw()
        draw_skip(skip)
        win.flip()
        if skip_requested(skip, mouse):
            release_mouse(win, mouse)
            return


# ---------------------------------------------------------------------
def ask_scale(win, prompt, ticks, labels, sam_images=None):
    """Likert / SAM style scale. Returns the chosen value."""
    text = visual.TextStim(
        win, text=prompt, font=config.FONT, height=0.034,
        color=config.COLOR_TEXT, pos=(0, 0.28), wrapWidth=1.15)

    slider = visual.Slider(
        win, ticks=ticks, labels=labels, granularity=1,
        pos=(0, -0.08), size=(1.0, 0.05), style="rating",
        font=config.FONT, labelHeight=0.024, labelWrapWidth=0.30,
        color=config.COLOR_TEXT, fillColor=config.COLOR_ACCENT,
        borderColor=config.COLOR_MUTED)
    try:
        slider.marker.color = config.COLOR_ACCENT
    except Exception:
        pass

    figures = []
    if sam_images and USE_SAM_IMAGES:
        n = len(sam_images)
        for i, name in enumerate(sam_images):
            path = os.path.join(SAM_DIR, name)
            if os.path.exists(path):
                x = -0.44 + i * (0.88 / max(1, n - 1))
                figures.append(visual.ImageStim(
                    win, image=path, pos=(x, 0.10), size=(0.11, 0.11)))

    box, label = _button(win, "Continuar")
    notice = visual.TextStim(
        win, text="Elegí una opción para continuar", font=config.FONT,
        height=0.022, color=config.COLOR_MUTED, pos=(0, -0.30))
    skip = skip_button(win)
    mouse = event.Mouse(win=win)
    event.clearEvents()

    while True:
        text.draw()
        for f in figures:
            f.draw()
        slider.draw()
        value = slider.getRating()
        if value is None:
            notice.draw()
        else:
            box.draw()
            label.draw()
        draw_skip(skip)
        win.flip()

        if skip_requested(skip, mouse):
            release_mouse(win, mouse)
            return value
        if value is not None and mouse.isPressedIn(box):
            while mouse.getPressed()[0]:
                win.flip()
            return value
        if value is not None and event.getKeys(keyList=["space", "return"]):
            return value


def ask_text(win, prompt, min_chars=0, height=0.26):
    """Open answer on its own screen. Returns the typed text."""
    text = visual.TextStim(
        win, text=prompt, font=config.FONT, height=0.032,
        color=config.COLOR_TEXT, pos=(0, 0.30), wrapWidth=1.15)

    entry = visual.TextBox2(
        win, text="", font=config.FONT, pos=(0, 0.02),
        size=(1.05, height), letterHeight=config.LETTER_HEIGHT,
        color=config.COLOR_TEXT, fillColor="#FFFFFF",
        borderColor="#D0D0D4", borderWidth=2, padding=0.016,
        anchor="center", alignment="top-left", editable=True,
        placeholder="Escribí acá…")

    box, label = _button(win, "Continuar", pos=(0, -0.34))
    notice = visual.TextStim(
        win, text="", font=config.FONT, height=0.022,
        color=config.COLOR_MUTED, pos=(0, -0.42))

    skip = skip_button(win)
    mouse = event.Mouse(win=win)
    try:
        win.currentEditable = entry
    except Exception:
        pass
    event.clearEvents()

    while True:
        content = entry.getText().strip()
        ready = len(content) >= min_chars
        notice.text = ("" if ready else
                       "Escribí al menos %d caracteres (llevás %d)."
                       % (min_chars, len(content)))

        text.draw()
        entry.draw()
        notice.draw()
        if ready:
            box.draw()
            label.draw()
        draw_skip(skip)
        win.flip()

        if skip_requested(skip, mouse):
            release_mouse(win, mouse)
            try:
                win.removeEditable(entry)
            except Exception:
                pass
            return content
        if ready and mouse.isPressedIn(box):
            while mouse.getPressed()[0]:
                win.flip()
            try:
                win.removeEditable(entry)
            except Exception:
                pass
            return content


# ---------------------------------------------------------------------
# Measure blocks
# ---------------------------------------------------------------------
# The prompts, ticks and anchors of every scale live in protocol/scales.json.
#
# The perceived authenticity / empathy items are adapted from Rubin et al.
# (2025). A reversed item is flagged with "reverse": true in the protocol
# and has to be recoded before averaging the subscale.


# ---------------------------------------------------------------------
# PANAS
# ---------------------------------------------------------------------
# 20 items (10 PA / 10 NA), in the canonical order of Watson, Clark &
# Tellegen (1988). STATE version: it asks about the present moment, not the
# last month. Translation after the Rioplatense Spanish adaptation of
# Moriondo et al. (2012) — THE TERMS SHOULD BE CHECKED AGAINST THE ORIGINAL
# ARTICLE before running participants.
#
# Presented as a grid of 10 items per screen, not one at a time. With 3
# administrations (baseline + the two episodes) that is 60 answers: one per
# screen would stretch the interval between episodes enough for the
# physiological activation to dissipate before the second one.

def ask_panas(win, items_per_page=None):
    """State PANAS as a grid. Returns {key: 1..5} plus the PA/NA totals."""
    cfg = protocol.scales()["panas"]
    items = protocol.panas()
    if items_per_page is None:
        items_per_page = cfg["items_per_page"]
    ticks, anchors = cfg["ticks"], cfg["anchors"]
    answers = {}
    mouse = event.Mouse(win=win)

    instruction = visual.TextStim(
        win, text=cfg["instruction"],
        font=config.FONT, height=0.030, color=config.COLOR_TEXT,
        pos=(0, 0.44), wrapWidth=1.15)

    x_center, width = 0.12, 0.42
    x_first = x_center - width / 2.0
    step = width / (len(ticks) - 1)
    headers = [
        visual.TextStim(win, text=anchors[k], font=config.FONT,
                        height=0.017, color=config.COLOR_MUTED,
                        pos=(x_first + k * step, 0.355), wrapWidth=0.115)
        for k in range(len(ticks))]

    for start in range(0, len(items), items_per_page):
        page = items[start:start + items_per_page]
        sliders, labels = [], []
        y0, dy = 0.27, 0.062

        for j, it in enumerate(page):
            y = y0 - j * dy
            # NOTE: style="radio" does NOT work here. In PsychoPy, categorical
            # is True for every radio slider, and then .rating returns
            # self.labels[...]: with labels=None it crashes on the first
            # click and with empty labels it stores '' instead of the number.
            # style="rating" leaves categorical=False and returns the numeric
            # value.
            sliders.append(visual.Slider(
                win, ticks=ticks, labels=None, granularity=1,
                style="rating", pos=(x_center, y), size=(width, 0.022),
                color=config.COLOR_TEXT, fillColor=config.COLOR_ACCENT,
                borderColor=config.COLOR_MUTED))
            labels.append(visual.TextStim(
                win, text=it["item"], font=config.FONT, height=0.024,
                color=config.COLOR_TEXT, pos=(-0.13, y),
                anchorHoriz="right", alignText="right", wrapWidth=0.55))

        box, label = _button(win, "Continuar", pos=(0, -0.43))
        notice = visual.TextStim(
            win, text="", font=config.FONT, height=0.022,
            color=config.COLOR_MUTED, pos=(0, -0.43))
        skip = skip_button(win)
        event.clearEvents()

        while True:
            instruction.draw()
            for h in headers:
                h.draw()
            for sl, lb in zip(sliders, labels):
                lb.draw()
                sl.draw()

            missing = sum(1 for sl in sliders if sl.getRating() is None)
            if missing:
                notice.text = ("Falta 1 ítem" if missing == 1
                               else "Faltan %d ítems" % missing)
                notice.draw()
            else:
                box.draw()
                label.draw()
            draw_skip(skip)
            win.flip()

            if skip_requested(skip, mouse):
                release_mouse(win, mouse)
                break
            if not missing and mouse.isPressedIn(box):
                while mouse.getPressed()[0]:
                    win.flip()
                break

        for it, sl in zip(page, sliders):
            answers[it["key"]] = sl.getRating()

    # subscale totals (range 10-50 each). An incomplete subscale has no
    # total: that only happens when the grid was skipped in test mode, and a
    # partial total in there would later read as a valid data point.
    for sub in ("PA", "NA"):
        values = [answers[it["key"]] for it in items if it["subscale"] == sub]
        answers[sub + "_total"] = (
            None if any(v is None for v in values) else sum(values))
    return answers


def measures_block(win, log, moment, include_authenticity=True,
                   include_panas=True):
    """SUDS + SAM (+ authenticity, only once there has been an interlocutor).

    Order: SUDS -> SAM -> authenticity -> PANAS.

    At BASELINE it must be called with include_authenticity=False: there is
    no interlocutor to rate yet, so asking "did my interlocutor understand
    me?" has no referent and also gives the cover story away early.
    """
    log.mark("measures_start", moment)
    sc = protocol.scales()
    r = {}

    suds = sc["suds"]
    r["suds"] = ask_scale(win, suds["prompt"], suds["ticks"], suds["labels"])

    for key in ("sam_valence", "sam_arousal"):
        sam = sc[key]
        r[key] = ask_scale(win, sam["prompt"], sam["ticks"], sam["labels"],
                           sam["images"])

    if include_authenticity:
        auth = sc["authenticity"]
        for item in auth["items"]:
            r[item["key"]] = ask_scale(
                win, item["prompt"], auth["ticks"], auth["labels"])

    # The PANAS goes LAST on purpose: it is 20 items, and SUDS/SAM are the
    # time-sensitive measures (they must be taken as soon as possible after
    # the episode, while the activation has not yet dissipated).
    if include_panas:
        log.mark("panas_start", moment)
        r.update(ask_panas(win))
        log.mark("panas_end", moment)

    log.mark("measures_end", moment)
    return r
