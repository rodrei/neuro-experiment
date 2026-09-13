# Study 1 — Validation and rejection: AI vs. human agent

Neurodiplo, Group 3 · AI companions · pre-entrega #3

Two implementations of the same study share one content folder:

- **`web/`** — the reference implementation of the current design
  (2 × 2 within-subject, four debate episodes, no deception). Runs in a
  browser, deployed on fly.io. **This is what the group demos and iterates.**
- **`desktop/`** — the PsychoPy implementation, still on the original
  two-episode design with a cover story. It is what EDA recording needs and
  will be migrated to the current design later.

The design document (Spanish) is `docs/Pre-entrega #3 — Diseño experimental.md`.
The specs and plans behind the code are under `docs/superpowers/`.

Code, comments, JSON keys, CSV headers and developer docs are in English.
Everything a participant reads is Argentine Spanish (voseo) and lives in
`protocol/`.

---

## Running the web version

```bash
python3 -m web.server.app          # http://localhost:8080
```

No dependencies: the server is standard library only. Put the OpenRouter key
in `OPENROUTER_API_KEY` or in `openrouter_key.txt` at the repo root
(gitignored); without it every turn falls back to fixed lines and the start
page says so.

The start form asks for participant id, age, sex, **sequence** (the row of
the Latin square, suggested from the id), the access code if the server has
one, and **test mode**. Under the form a pre-flight line reports whether the
model answers (`/api/health`). See `web/README.md` for the environment
variables, the deploy and the browser check.

## Running the desktop version

Open **PsychoPy Coder**, open `desktop/study1.py`, Run. From a terminal:

```bash
PYTHONHOME=/Applications/PsychoPy.app/Contents/Resources PYTHONPATH=/Applications/PsychoPy.app/Contents/Resources/lib/python3.11 /Applications/PsychoPy.app/Contents/MacOS/python desktop/study1.py
```

Quit at any time: **Ctrl + Q**. `DEMO_MODE` and `TEST_MODE` live in
`desktop/config.py`; both must be `False` for participants.

## Tests

```bash
python3 -m unittest discover -s common -t . -v    # protocol loader, LLM agent, CSV writer
python3 -m unittest discover -s web -t . -v       # the HTTP server, with a fake LLM
```

System Python, no network, no PsychoPy. The desktop has no automated suite:
compile it with PsychoPy's Python (`… -m py_compile desktop/*.py`) and walk
it by hand.

Browser check of the web flow (needs Playwright installed globally):

```bash
node web/e2e/run_flow.mjs --url http://localhost:8080 --shots /tmp/shots
```

---

## Layout

Three layers; the dependency always points the same way
(`web/`, `desktop/` → `common/` → `protocol/`, never back).

| Path | What it is |
|---|---|
| **`protocol/`** | **The experiment's content as data. This is where the experiment is edited.** See `protocol/README.md`. |
| `protocol/texts.json` | Every screen's prose, for both platforms |
| `protocol/scales.json` | SUDS, SAM, authenticity and the PANAS anchors |
| `protocol/parameters.json` | Real and demo timings, the latency formula, minimum lengths |
| `protocol/markers.json` | The 22 event codes |
| `protocol/prompts.json` | Model parameters and the two prompt families (`debate`, `situation`) |
| `protocol/topics.json` | The eight debate questions |
| `protocol/interlocutors.json` | The four interlocutor names (two people, two AIs) |
| `protocol/sequences.json` | The 4×4 Latin square of conditions |
| `protocol/fallback.csv` | Generic lines shown when an LLM turn fails (web) |
| `protocol/scripts.csv` | The original scripted messages (desktop) |
| `protocol/panas.csv` | The 20 PANAS items with their subscale |
| **`common/`** | **Shared Python, stdlib only, no PsychoPy** |
| `common/protocol.py` | The only reader of `protocol/` |
| `common/llm_agent.py` | The LLM agent (OpenRouter): prompt, turn, fallback, health probe |
| `common/output.py` | The CSV writer both platforms use |
| **`web/`** | **Browser implementation: `http.server` + jsPsych** |
| `web/server/app.py` | Serves the page, `/api/protocol`, `/api/health`, `/api/turn`, `/api/data` |
| `web/js/experiment.js` | The timeline and the submission |
| `web/js/chat-plugin.js` | One debate episode in one jsPsych trial |
| `web/js/scales.js` | Text screens, sliders, PANAS grid, measure collection |
| `web/e2e/run_flow.mjs` | Playwright walk of the whole flow |
| **`desktop/`** | **PsychoPy implementation** |
| `desktop/study1.py` | The flow (original two-episode design) |
| `desktop/chat.py`, `scales.py`, `markers.py`, `config.py` | Chat engine, scales, event log, PsychoPy settings |
| `data/` | Output (created on demand, gitignored) |

---

## The web flow

1. Start form (experimenter): id, age, sex, sequence, access code, test mode; LLM pre-flight.
2. Consent.
3. **Rest baseline** (fixation cross) → SUDS → SAM → PANAS (no authenticity: no interlocutor yet).
4. General instructions.
5. **Four episodes**, in the order the sequence gives (each of the four
   conditions once: person/AI × validation/rejection). Each episode:
   1. **Interlocutor intro** — an honest statement of who is on the other side
      (a person in another room, or an AI assistant), with their name. Names
      are assigned by position within the agent type, so name × feedback
      balances across the four sequences.
   2. **Topic pick** — the questions not yet used in this session, as cards.
   3. Connecting…
   4. **Chat** — the chosen question sits in a pinned card under the bar (it is
      not a bubble). The participant writes their opinion first (minimum 120
      characters), then the LLM answers three times, with a free reply
      window after each, and a final free-reply window.
   5. SUDS → SAM → authenticity (3 items) → PANAS.
   6. Pause (except after the fourth).
6. Debriefing: the warm or dismissive attitude was a role assigned by the
   design, not a judgment of the participant.
7. Close; the four CSVs are written.

In phase 1 every episode, including the ones introduced as a person, is
answered by the LLM. Phase 2 connects the person-labelled episodes to a real
person.

### Invariants of the web flow

1. **The LLM writes every turn**, from `protocol/prompts.json` `debate`, with
   the chosen question and the role in the system prompt. If the API fails
   the turn comes from `protocol/fallback.csv`, and the chat CSV records
   `origin = fallback` and the reason.
2. **The agent latency is deterministic**: `1.2 s + 0.045 s × characters`
   (cap 12 s), applied after the text is generated, so API time never shows.
3. **The opinion is written inside the chat**, under the pinned question.
   No screen before the chat asks for it.
4. **The baseline has no authenticity items.**
5. **Measures are always SUDS → SAM → authenticity → PANAS** (time-sensitive
   first, the long one last).
6. **Every relevant event leaves a marker** (`protocol/markers.json`) so the
   EDA can be segmented offline.

---

## Output

Four CSVs per session in `data/`. Web prefix: `S1_<id>_seq<n>_<stamp>`;
desktop prefix: `S1_<id>_<condition>_<stamp>`.

| File | Content |
|---|---|
| `_events.csv` | `t_experiment_s`, `t_unix`, `code`, `label`, `detail`. **The one to align with the EDA.** |
| `_responses.csv` | key,value rows: session info, `baseline_*` measures, and per episode `epN_condition`, `epN_agent_type`, `epN_feedback`, `epN_topic`, `epN_interlocutor`, `epN_opinion`, `epN_suds`, `epN_sam_*`, `epN_auth_1..3`, `epN_auth_mean`, `epN_pa_*`/`epN_na_*`, `epN_PA_total`, `epN_NA_total` |
| `_behavioral.csv` | One row per episode: condition, topic, interlocutor, opinion and reply lengths and latencies, timeouts, `fallback_turns` |
| `_chat.csv` | Every message: `episode`, `condition`, `interlocutor`, `topic`, `author`, `text`, `origin`, `fallback_reason`, `t_experiment_s`, `latency_s` |

A skipped screen (test mode) leaves its value empty; an incomplete PANAS
subscale has no total; `test_mode` is recorded in `_responses.csv`.

---

## Seeing LLM failures

- **Before the session:** the start form's pre-flight line, backed by
  `GET /api/health` (key found? model answered? in how long? or which error).
  Cached 60 s; the «Volver a comprobar» link forces a new probe.
- **During the session:** in test mode a red banner under the chat bar shows
  the reason the moment a turn falls back; participants outside test mode see
  nothing.
- **Afterwards:** `origin` and `fallback_reason` in `_chat.csv`,
  `fallback_turns` in `_behavioral.csv`, and one `LLM fallback (...)` line per
  failure in the server output (`fly logs`).

---

## EDA synchronisation (desktop)

`MARKER_BACKEND` in `desktop/config.py`: `"csv"` (default: timestamp log only,
enough for Empatica E4 and Shimmer3, aligned offline by `t_unix`), `"lsl"`,
`"serial"`, `"parallel"` (not on Mac). If a backend fails to open the
experiment goes on with CSV only. SCRs have 1–4 s latencies and are analysed
in windows of seconds, so millisecond triggers are not needed.

---

## PsychoPy trap: never `style="radio"`

The PANAS grid uses `style="rating"`. With `"radio"`, `Slider.categorical`
is `True` and `.rating` returns labels instead of the number: `labels=None`
raises `TypeError` on the first click; `labels=[""]*5` stores `''` silently.

---

## Before running participants

- [ ] Decide when the desktop follows the debate design (or how EDA is
      captured alongside the web version).
- [ ] Review the eight questions in `protocol/topics.json` and the two roles
      in `protocol/prompts.json` with the group; pretest the LLM transcripts
      (judges + independent sample) as the design document requires.
- [ ] Check the 20 PANAS items against Moriondo et al. (2012).
- [ ] Optional pictorial SAM: PNGs in `protocol/sam/` named `val_1..9.png`
      and `aro_1..9.png`; the desktop draws them when present.
- [ ] Choose the marker backend for the EDA equipment.
- [ ] Rotate the fly.io access code after each demo.
