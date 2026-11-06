# Study 1 — Validation and rejection: AI vs. human agent

Neurodiplo, Group 3 · AI companions

A 2 × 2 within-subject experiment that runs in a browser (`web/`): four chat
episodes about personal situations, one per domain, with a person or an AI as
the interlocutor, who validates or rejects. A debriefing reveals how it was set
up.

**The interlocutors.** In the study's human condition, a person from the research
team writes every turn, following the protocol, and is presented as another
participant. In the AI condition, a language model does. **The chat for that person
is not built yet, so the model answers all four episodes, in both modes.** The demo
says so on the start form and on each human announcement. The debriefing describes
the study as designed in both modes, so **`DEMO_MODE=0` must not be used with real
participants until that chat exists**: it would tell them a person answered when
the model did.

The specification is in the group's Drive folder `entrega final`: the paper's
Method and Annexes A1 and A2, «Decisiones de diseño y su fundamento» and
«Pendientes». «Rodrigo modificas al experimento» and the handoff predate the person
in the human condition and the reduced set of scales, so where they disagree the
other three win.

Code, comments, JSON keys, CSV headers and developer docs are in English.
Everything a participant reads is Argentine Spanish (voseo) and lives in
`protocol/`.

---

## Two modes

| | `DEMO_MODE=1` (default, what fly.io runs) | `DEMO_MODE=0` |
|---|---|---|
| **For** | Evaluators walking through the study | A full session |
| **Baseline** | 15 s | 5 minutes |
| **Data** | Four CSVs per session, with a generated id and no age or sex | Four CSVs per session |
| **Screen** | A permanent badge saying the answers are saved, and notes saying the model answers every conversation, who sees the session and what goes to the model's provider | Experimenter fields on the start form |
| **Saltar / F9** | On every screen, to pass the questionnaires; in the chat, it ends the conversation | Only in test mode, where it cuts the waits in the chat |
| **Rows of the Latin squares** | Random | From the number in the participant id |
| **API spend** | `MAX_TURNS_PER_DAY` across all sessions; past it, turns come from the fallback lines | No cap |

## Running it

```bash
python3 -m web.server.app              # demo, http://localhost:8080
DEMO_MODE=0 python3 -m web.server.app  # full session, writes data/
```

No dependencies: the server is standard library only. Put the OpenRouter key
in `OPENROUTER_API_KEY` or in `openrouter_key.txt` at the repo root
(gitignored); without it every turn falls back to fixed lines. See
`web/README.md` for the environment variables, the deploy and the browser check.

## Tests

```bash
python3 -m unittest discover -s common -t . -v    # protocol, LLM agent, CSV writer
python3 -m unittest discover -s web -t . -v       # the HTTP server, with a fake LLM
node web/e2e/run_flow.mjs --url http://localhost:8080 --shots /tmp/shots   # real browser
```

The browser check reads the mode from the server, so run it against both.

---

## Layout

Three layers; the dependency always points the same way
(`web/` → `common/` → `protocol/`, never back).

| Path | What it is |
|---|---|
| **`protocol/`** | **The experiment's content as data. This is where the experiment is edited.** See `protocol/README.md`. |
| **`common/`** | **Python, stdlib only** |
| `common/protocol.py` | The only reader of `protocol/` |
| `common/llm_agent.py` | The LLM agent (OpenRouter): prompt, turn, fallback, health probe |
| `common/output.py` | The CSV writer |
| **`web/`** | **Browser implementation: `http.server` + jsPsych** |
| `web/server/app.py` | Serves the page, `/api/protocol`, `/api/health`, `/api/turn`, `/api/data` |
| `web/js/experiment.js` | The timeline and the submission |
| `web/js/chat-plugin.js` | One episode in one jsPsych trial |
| `web/js/scales.js` | Text screens, sliders, grids, measure collection |
| `web/e2e/run_flow.mjs` | Playwright walk of the whole flow |
| **`simulation/`** | **The simulated data behind the paper's Results, independent of the rest.** See `simulation/README.md`. |
| `data/` | Output (created on demand, gitignored) |

---

## The flow

1. Start form; LLM pre-flight outside the demo.
2. Consent, with the stated purpose of the study.
3. Resting baseline (fixation cross), then the AI companion use items. The
   loneliness and attachment scales are not part of the session.
4. **The four situations**, one per domain, all before any feedback, each with
   a 0–10 distress rating. A rating of 9 or 10 shows an alert so the
   experimenter can offer to replace the situation; both versions are kept.
5. **Four episodes**, in the order of the condition's Latin square, with the
   domain of each condition from an independent one. Each episode:
   1. SUDS.
   2. **Announcement** of the agent on its own screen.
   3. Connecting…
   4. **Chat**, with the agent's label permanently in the header. A fixed
      opening names the domain; then **three rounds**, each the participant
      writing and the agent answering. The first message box starts with the
      situation written in step 4, which the participant can edit and has to
      send. The last message stays up for a fixed hold before Continuar.
   5. SAM → SUDS → authenticity → six manipulation checks → naturalness.
   6. Pause (except after the fourth).
6. **Final block**: for each episode, identified by its domain, a 0–100 scale
   of who the participant believes they talked to; then the open suspicion
   question; then what stood out about each interlocutor.
7. Debriefing, which reveals that the "other participant" was a person from the
   research team following a protocol. The participant can then withdraw their
   data, in which case nothing is stored.

### Invariants of the flow

1. **Until the human chat exists, the LLM answers.** It writes every turn from one fixed prompt
   (Annex A2). If the API does not answer within 20 s or the reply is empty, the
   turn comes from `protocol/fallback.csv`, and the chat CSV records
   `origin = fallback` and the reason.
2. **The model never receives the label.** Nothing about how the interlocutor is
   presented reaches the prompt: `/api/turn` only takes the feedback type and
   the conversation.
3. **The agent latency is deterministic**: `1.2 s + 0.045 s × characters`
   (cap 12 s), applied after the text is generated, so API time never shows.
4. **Nothing asks about the interlocutor's identity before the final block.**
   The per-episode naturalness item does not mention it.
5. **Measures keep their order** (see the flow above), and the baseline has no
   interlocutor items.
6. **Every message is stored verbatim** with its origin, shown latency, length
   and turn number.
7. **Agent messages are stamped when they reach the screen**, not when they are
   requested or when the typing indicator starts.

### Experimenter intervention

**Ctrl+Shift+E** inside a chat pauses it with a dialog: type the agent's next
message (`origin = experimenter`), leave it empty to resume, or type `FIN` to
end the episode. Confirming the dialog flags the episode with
`experimenter_intervention = 1`; cancelling it changes nothing.

---

## Output

Four CSVs per session in `DATA_DIR` (`data/` by default, `/data` on fly.io),
prefixed `S1_<id>_seq<n>_<stamp>`, with the stamp in UTC. A session that withdraws
writes nothing. The team reads and downloads them at `/admin` (see `web/README.md`).

| File | Content |
|---|---|
| `_events.csv` | `t_experiment_s`, `t_unix`, `code`, `label`, `detail`: baseline, situations, each episode, each round, each agent message, each scale block, final block, debriefing. **The one to align with the physiological recording.** |
| `_chat.csv` | Every message: `participant_id`, `episode`, `condition`, `agent_type`, `feedback`, `domain`, `round` (0 is the opening), `turn`, `author`, `text`, `chars`, `origin` (`opening`, `llm`, `fallback`, `experimenter`, `participant`), `fallback_reason`, `t_experiment_s`, `t_unix`, `shown_latency_s`, `response_latency_s` |
| `_behavioral.csv` | One row per episode: `participant_id`, `episode`, `condition`, `agent_type`, `feedback`, `domain`, `pre_rating`, `rounds_completed`, `agent_turns`, `agent_chars_total`, `agent_chars_mean`, `total_shown_latency_s`, `participant_messages`, `replies_timed_out`, `fallback_turns`, `experimenter_turns`, `experimenter_intervention` |
| `_responses.csv` | key,value rows: session info, `baseline_*`, `situation_<domain>` with `_pre_rating`, `_alerted`, `_discarded`, `suspicion`, and per episode `epN_condition`, `epN_agent_type`, `epN_feedback`, `epN_domain`, `epN_pre_rating`, `epN_pre_suds`, `epN_suds`, `epN_sam_*`, `epN_auth_1..3`, `epN_auth_mean`, `epN_mc_*`, `epN_naturalness`, `epN_credibility`, `epN_stood_out` |

A skipped screen leaves its value empty; `test_mode` is recorded in
`_responses.csv`. The session is held in the
browser and sent once at the end, so closing the tab mid-session loses it.

---

## Seeing LLM failures

- **Before the session:** the start form's pre-flight line, backed by
  `GET /api/health` (key found? model answered? in how long? or which error).
  Cached 60 s; the «Volver a comprobar» link forces a new probe.
- **During the session:** in test mode a red banner under the chat bar shows
  the reason the moment a turn falls back.
- **Afterwards:** `origin` and `fallback_reason` in `_chat.csv`,
  `fallback_turns` in `_behavioral.csv`, and one `LLM fallback (...)` line per
  failure in the server output (`fly logs`).

---

## The paper

The app differs from what the paper's Drive document says in these places, which
the group has to carry over by hand:

- **Annex A2, validation:** if the person has not named a feeling, the model does
  not attribute one; it validates first and may close with one question about what
  was told, which counts within the three sentences, and none in its third message.
- **Annex A2, rejection:** it adds that the model never asks questions, not even
  rhetorical ones.
- **Sections 2.5 and 3:** six manipulation items, not four. The two new ones are the
  wording «Pendientes» proposes, still to be validated by Valentina.
- **Section 2.4:** the first message box of each episode starts with the situation
  written earlier.

---

## Still pending

- [ ] The live chat for the person in the human condition. Until it exists,
      `DEMO_MODE=0` must not be used with real participants.
- [ ] Group review of everything drafted here that is not in the paper: the
      three style examples / fallback lines, the AI companion use items, the
      two attribution items, and the consent and debriefing wording.
- [ ] The paper's Annex A2 and sections 2.5 and 3 need to catch up with the app:
      see "The paper" below.
- [ ] Rotate the fly.io access code after each demo.
