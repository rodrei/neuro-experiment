# AGENTS.md

This file provides guidance to coding agents (Codex, Claude Code and others) when working with code in this repository. It mirrors CLAUDE.md; keep the two in sync.

## What this is

Implementation of Study 1 of a neuroscience diploma experiment: "Validation and rejection: AI vs. human agent" (Group 3, AI companions). Current design: **2×2 fully within-subject** — agent type (person vs. AI) × feedback (validation vs. rejection) — four chat episodes per participant, each about a debate question the participant picks, with **no deception** (the participant is told who they are talking to). The design document is `docs/Pre-entrega #3 — Diseño experimental.md` (Spanish). The spec of the current implementation is `docs/superpowers/specs/2026-09-12-phase1-debate-design.md`.

Two implementations share one content folder: **`web/`** (browser, jsPsych + stdlib `http.server`, the reference for the current design, deployed on fly.io) and **`desktop/`** (PsychoPy Coder, still on the original two-episode cover-story design, to be migrated later).

**Language rule:** code, comments, docstrings, JSON keys, CSV headers, developer docs and commit messages are in **English**. Everything a participant reads (values in `protocol/*.json`, `fallback.csv`, `scripts.csv`, `panas.csv`, and the UI strings in `web/index.html` / the JS) is **Argentine Spanish (voseo)**. The design doc and `docs/superpowers/*` from before the rename stay Spanish.

## How to run

- Web: `python3 -m web.server.app` → http://localhost:8080. Key in `OPENROUTER_API_KEY` or `openrouter_key.txt` (gitignored). Env: `PORT`, `DATA_DIR`, `ACCESS_CODE`, `LLM_TIMEOUT`, `RATE_LIMIT_PER_MINUTE`.
- Desktop: open `desktop/study1.py` in PsychoPy Coder and Run, or `PYTHONHOME=/Applications/PsychoPy.app/Contents/Resources PYTHONPATH=/Applications/PsychoPy.app/Contents/Resources/lib/python3.11 /Applications/PsychoPy.app/Contents/MacOS/python desktop/study1.py`. Ctrl+Q quits. `DEMO_MODE` / `TEST_MODE` in `desktop/config.py`.
- Tests (system Python, no network, no PsychoPy): `python3 -m unittest discover -s common -t . -v` and `python3 -m unittest discover -s web -t . -v`. Desktop: `py_compile desktop/*.py` with PsychoPy's Python; the interactive walk is manual.
- Browser check: `node web/e2e/run_flow.mjs --url <url> [--code X] [--shots DIR]` (global Playwright). Run it locally and after every deploy.
- Console chat to iterate on the prompts: `python3 -m common.llm_agent`.
- Deploy: `fly deploy --app neuro-estudio1-demo` from the repo root (see `web/README.md`).

## Architecture

Dependency direction: `web/`, `desktop/` → `common/` → `protocol/`, never back.

**`protocol/`** — content as data: `texts.json` (screens), `scales.json`, `parameters.json`, `markers.json`, `prompts.json` (`debate` for the web, `situation` for the desktop), `topics.json`, `interlocutors.json`, `sequences.json` (Williams Latin square), `fallback.csv` (web fallback lines), `scripts.csv` (desktop scripted messages), `panas.csv`. Entries only the desktop reads are named `desktop_*` or listed in `protocol/README.md`. **Edit content here, never in code.** Run the common tests afterwards.

**`common/`** — stdlib Python: `protocol.py` (only reader of `protocol/`), `llm_agent.py` (`build_system_prompt`, `LLMAgent.reply()` → `(text, origin, reason)`, `probe()`; transport injected, hence testable without network), `output.py` (CSV writer shared by both platforms; `CHAT_FIELDS`, `EVENT_FIELDS`). No new dependencies.

**`web/`** — `server/app.py` (routes: `/api/protocol`, `/api/health`, `/api/turn`, `/api/data`; stateless proxy, the browser sends the full history each turn), `js/experiment.js` (timeline + submission), `js/chat-plugin.js` (one episode per trial, pinned topic card, fallback banner in test mode), `js/scales.js`, `static/styles.css` (screens centred via a full-viewport flex `#jspsych-target`), `e2e/run_flow.mjs`.

**`desktop/`** — `study1.py`, `chat.py` (TextBox2 bubbles built once and cached), `scales.py`, `markers.py` (`EventLog`: CSV always, optional LSL/serial/parallel), `config.py`. The modules add the repo root to `sys.path` to import `common`.

Output: four CSVs per session in `data/` (`_events`, `_responses`, `_behavioral`, `_chat`), web prefix `S1_<id>_seq<n>_<stamp>`, desktop prefix `S1_<id>_<condition>_<stamp>`.

## Design invariants (do not break)

Web (current design):
1. The LLM writes every turn from the `debate` prompt with the chosen question and the role; on failure the turn comes from `fallback.csv` with `origin = fallback` and a reason.
2. Agent latency is deterministic: `latency_base + latency_per_char × chars`, capped — applied after generation.
3. The opinion is written inside the chat under the pinned question; no earlier screen asks for it.
4. Baseline has no authenticity items.
5. Measures order: SUDS → SAM → authenticity → PANAS.
6. Every relevant event leaves a marker with a timestamp (`markers.json`).
7. Nothing asks the participant whether the interlocutor was a person or an AI; interlocutors are announced honestly before each episode. In phase 1 every episode is still answered by the LLM; the person-labelled episodes get a real person in phase 2.

Desktop (original design, until migrated): scripted agent identical across Human/AI, situation told inside the chat, cover story is the only manipulation, scripts balanced in length (`test_turns_are_balanced_in_length`).

## PsychoPy trap: sliders

The PANAS grid uses `style="rating"`. Never `"radio"`: every radio slider is `categorical=True` and `.rating` returns labels — `labels=None` raises `TypeError` on the first click; `labels=[""]*5` stores `''` silently.

## Known pending items

See README "Before running participants": desktop migration to the debate design, review of topics and roles with the group, PANAS translation check, pictorial SAM, marker backend, access-code rotation after demos.
