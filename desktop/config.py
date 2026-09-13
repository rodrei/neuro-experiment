# -*- coding: utf-8 -*-
"""
Study 1 — Configuration of the desktop experiment (PsychoPy).

Only what is specific to this platform lives here: mode, window, appearance,
marker backend and ports.

The experiment's CONTENT (screen prose, scales, scripts, marker codes, agent
prompts) is NOT here: it lives in protocol/ and is read through
common.protocol. That way the web demo and the desktop run exactly the same
experiment.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from common import protocol

# =====================================================================
# MODE
# =====================================================================
# True  -> short timings, small window. To try the flow in 3 minutes.
# False -> the protocol's real timings. To run participants.
DEMO_MODE = True

FULLSCREEN = not DEMO_MODE
WINDOW_SIZE = (1280, 800)          # only if FULLSCREEN = False

# Test mode: every screen gets a "Saltar" button, and SKIP_KEY does the same
# from the keyboard. It walks the whole flow without answering the scales or
# waiting the timings. Whatever is skipped stays EMPTY in the CSVs
# (incomplete PANAS subscales get no total), so a test run is told apart from
# a real one. NEVER run participants with this True: it is recorded in
# _responses.csv as test_mode.
TEST_MODE = False
SKIP_KEY = "f9"

# =====================================================================
# PROTOCOL PARAMETERS
# =====================================================================
# Timings and the latency formula live in protocol/parameters.json, because
# they are part of the design and hold equally for the web demo. The latency
# is DETERMINISTIC on purpose: a function of the message length, not of
# chance, so it cannot differ between the Human / AI conditions.
PARAMETERS = protocol.parameters("demo" if DEMO_MODE else "real")

# =====================================================================
# AGENT
# =====================================================================
# "scripted" -> the messages come from protocol/scripts.csv (the original
#               design: content and latency identical across conditions).
# "llm"      -> a model generates them via OpenRouter (see common/llm_agent.py).
#               The greeting that asks for the situation stays scripted, and
#               if the API fails the turn falls back to the script. NOTE:
#               experimental mode, not cleared with the ethics committee;
#               what the participant writes travels to OpenRouter and to the
#               model provider.
# The key is read from OPENROUTER_API_KEY or from openrouter_key.txt.
# The model and its temperature are in protocol/prompts.json.
AGENT = "scripted"

LLM_TIMEOUT = 20      # seconds to wait for the API before falling back

# =====================================================================
# SYNCHRONISATION WITH THE PHYSIOLOGICAL EQUIPMENT
# =====================================================================
# "csv"      -> only an event log with timestamps (works for Empatica E4,
#               Shimmer3 and any device that records on its own clock)
# "lsl"      -> also publishes a marker stream over Lab Streaming Layer
# "serial"   -> also sends a TTL byte over a serial port
# "parallel" -> also sends a byte over a parallel port (does not exist on Mac)
MARKER_BACKEND = "csv"

SERIAL_PORT      = "/dev/tty.usbserial-XXXX"   # only if MARKER_BACKEND = "serial"
SERIAL_BAUD      = 115200
PARALLEL_ADDRESS = 0x0378                      # only if MARKER_BACKEND = "parallel"

# =====================================================================
# APPEARANCE
# =====================================================================
COLOR_BACKGROUND     = "#F2F3F5"
COLOR_TEXT           = "#1C1C1E"
COLOR_MUTED          = "#8A8A8E"
COLOR_BUBBLE_AGENT   = "#FFFFFF"   # agent messages (left)
COLOR_BUBBLE_PARTICIPANT = "#D8E7FA"   # participant messages (right)
COLOR_BAR            = "#FFFFFF"
COLOR_ACCENT         = "#3070C6"

FONT                 = "Helvetica"
LETTER_HEIGHT        = 0.026       # 'height' units
BUBBLE_MAX_WIDTH     = 0.52
