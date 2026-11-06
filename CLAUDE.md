# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Implementation of Study 1 of a neuroscience diploma experiment: "Validation and rejection: AI vs. human agent" (Group 3, AI companions). Design: **2×2 fully within-subject** — agent type (person vs. AI) × feedback (validation vs. rejection) — four episodes of three rounds each, about personal situations from four domains. In the study's human condition a person from the research team writes every turn, following the protocol, presented as another participant; in the AI condition an LLM does. **The chat for that person is not built yet, so the LLM answers all four episodes in both modes**, and the demo says so. A debriefing reveals the setup as designed. The assignment is delivered as if the study had run: there are no real participants, and the results come from simulated data.

The specification lives in the group's Drive folder `entrega final`: «Rodrigo modificas al experimento», the paper's Method and Annexes A1 and A2, and «Decisiones de diseño y su fundamento». Follow those documents on design questions rather than proposing alternatives, except that the real person in the human condition is a later group decision and overrides what they say about a single LLM.

It runs in a browser: `web/` (jsPsych + stdlib `http.server`, deployed on fly.io in demo mode).

**Language rule:** code, comments, docstrings, JSON keys, CSV headers, developer docs and commit messages are in **English**. Everything a participant reads (values in `protocol/*.json`, `fallback.csv`, `panas.csv`, and the UI strings in `web/index.html` / the JS) is **Argentine Spanish (voseo)**. The design doc and `docs/superpowers/*` from before the rename stay Spanish.

## How to run

- Web: `python3 -m web.server.app` → http://localhost:8080. Key in `OPENROUTER_API_KEY` or `openrouter_key.txt` (gitignored). Env: `DEMO_MODE` (default `1`; `0` is the full session with its CSVs), `PORT`, `DATA_DIR`, `ACCESS_CODE`, `LLM_TIMEOUT`, `RATE_LIMIT_PER_MINUTE`, `MAX_TURNS_PER_DAY`.
- Tests (system Python, no network): `python3 -m unittest discover -s common -t . -v` and `python3 -m unittest discover -s web -t . -v`.
- Browser check: `node web/e2e/run_flow.mjs --url <url> [--code X] [--shots DIR]` (global Playwright; adapts to the server's mode). Run it locally in both modes and after every deploy.
- Console chat to iterate on the prompt: `python3 -m common.llm_agent`.
- Deploy: `fly deploy --app neuro-estudio1-demo` from the repo root (see `web/README.md`).

## Architecture

Dependency direction: `web/` → `common/` → `protocol/`, never back.

**`protocol/`** — content as data: `texts.json` (screens), `scales.json`, `instruments.json` (UCLA-3, ECR), `parameters.json`, `markers.json`, `prompts.json` (Annex A2), `domains.json`, `sequences.json` (Williams Latin square), `domain_sequences.json` (independent Latin square), `fallback.csv` (fallback lines, also the prompt's style examples), `panas.csv`. **Edit content here, never in code.** Run the common tests afterwards.

**`common/`** — stdlib Python: `protocol.py` (only reader of `protocol/`), `llm_agent.py` (`build_system_prompt`, `LLMAgent.reply()` → `(text, origin, reason)`, `probe()`; transport injected, hence testable without network), `output.py` (CSV writer; `CHAT_FIELDS`, `EVENT_FIELDS`). No new dependencies.

**`web/`** — `server/app.py` (routes: `/api/protocol`, `/api/health`, `/api/turn`, `/api/data`; stateless proxy, the browser sends the full history each turn), `js/experiment.js` (timeline, row assignment, submission), `js/chat-plugin.js` (one episode per trial, experimenter hotkey, fallback banner in test mode), `js/scales.js`, `static/styles.css` (screens centred via a full-viewport flex `#jspsych-target`), `e2e/run_flow.mjs`.

**`simulation/`** — the simulated data behind the paper's Results, independent of the rest and with its own dependencies (numpy, pandas, scipy, openpyxl). A working copy of Elena's scripts, keeping their Spanish names so they can be diffed against hers; her originals on Drive are never modified. See `simulation/README.md`.

Output: four CSVs per session in `data/` (`_events`, `_responses`, `_behavioral`, `_chat`), prefix `S1_<id>_seq<n>_<stamp>`. In demo mode nothing is written.

## Design invariants (do not break)

1. Until the human chat exists, the LLM writes every turn from one fixed prompt; if the API does not answer in 20 s or the reply is empty, the turn comes from `fallback.csv` with `origin = fallback` and a reason.
2. **The model never receives the label.** `/api/turn` takes only the feedback type and the conversation.
3. Agent latency is deterministic: `latency_base + latency_per_char × chars`, capped — applied after generation.
4. Nothing asks about the interlocutor's identity before the final block; the per-episode naturalness item does not mention it. In the final block, credibility comes before the open questions.
5. Post-episode order: PANAS → SAM → SUDS → authenticity → manipulation checks → naturalness. The baseline has no interlocutor items.
6. Every message is stored verbatim with origin, shown latency, length and turn number.
7. Agent messages are stamped when they reach the screen, not when requested or when the typing indicator starts. Every relevant event leaves a marker (`markers.json`).
8. When the demo says nothing is recorded, `/api/data` must refuse to store.
9. The demo says the model answers every conversation, on the start form and on each human announcement. The debriefing describes the study as designed and does not mention it, so `DEMO_MODE=0` must not be used with real participants until the human chat exists.

## Known pending items

See README "Still pending": the live chat for the person in the human condition, UCLA-3 and ECR wording, group review of the drafted Spanish, PANAS translation check, access-code rotation after demos.
