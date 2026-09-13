# Handoff — Phase 2: a real person in the person-labelled episodes

Written 2026-09-13 at the end of the phase-1 session. Read this together
with `CLAUDE.md` (architecture, invariants, commands) and the phase-1 spec
`docs/superpowers/specs/2026-09-12-phase1-debate-design.md`. Start phase 2
with a brainstorming pass (it is architectural), then spec → plan → build.

## Where things stand

- `main` (`036b890`, pushed) has the debate design on the web: four
  episodes, participant picks a topic, honest interlocutor intro, LLM answers
  every episode — including the two introduced as a person. Deployed at
  https://neuro-estudio1-demo.fly.dev, access code `akCzVIv2iFpf` (secret
  `ACCESS_CODE`; rotate after demos).
- The desktop (PsychoPy) is still on the original two-episode cover-story
  design. Out of scope for phase 2 unless the user says otherwise.
- Verification that must keep passing: `python3 -m unittest discover -s
  common -t .`, `... -s web -t .`, and `node web/e2e/run_flow.mjs --url <url>
  --code <code>` locally and against fly after every deploy.

## Goal of phase 2 (the user's words, paraphrased)

The person-labelled episodes are answered by an actual person, not the
LLM. That will probably need users, some sort of login, and an admin side;
none of it is designed yet. Phase 1 is a diploma demo; showing the intent
matters more than running a real experiment.

## Constraints inherited from phase 1

- No deception: the participant is told, before each episode, whether the
  interlocutor is a person or an AI. Nothing asks them to guess.
- Interlocutor names come from `protocol/interlocutors.json`, assigned by
  position within agent type; the Latin square in `protocol/sequences.json`
  balances name × feedback. The person-labelled episodes are `human_validation`
  and `human_rejection`; whoever plays the person has to deliver the assigned
  feedback type.
- The CSV contract in `common/output.py` (`CHAT_FIELDS`, `EVENT_FIELDS`, four
  files, `S1_<id>_seq<n>_<stamp>`) is what any analysis will read; extend it,
  don't fork it. `origin` currently takes `llm` / `fallback` / `participant`.
- The server is stdlib-only `http.server`, stateless, on a 256 MB fly machine
  (legacy Hobby plan; do not grow memory or the volume). The data volume
  (`datos`, mounted at `/data`) is not durable storage.
- Participant-facing text is Argentine Spanish and lives in `protocol/`;
  code, docs, keys and commits are English.
- The LLM latency formula (`latency_base + latency_per_char × chars`) is
  applied to generated text; the design doc wants confederate and AI
  behaviour "equivalent in content, intensity and structure".

## Open questions to settle in the brainstorm

Design:

1. **Who is the person?** A trained confederate from the group (the design
   doc says so), any logged-in teammate, or the experimenter at the next
   desk? This decides how much "accounts" really means.
2. **What happens when nobody is online** for a person-labelled episode:
   wait with a visible "connecting…" up to a timeout, fall back to the LLM
   (and record that it did), or refuse to start the session?
3. **Does the confederate get a script or guidance?** The role text from
   `protocol/prompts.json` `debate.role.{validation,rejection}` shown on
   their screen? Suggested lines? A required number of turns (the LLM does
   exactly three)?
4. **Latency.** Keep the deterministic formula for the person too (delay
   their message until the formula's time has passed) so the two agent types
   feel the same, or let real typing time show? The design doc's
   "equivalent structure" argues for the former.
5. **Turn structure.** The LLM flow is: participant opinion → 3 agent turns
   with a 90 s free reply between → final free-reply window. Same skeleton
   for the person (the UI enforces it), or a free conversation with a time
   cap?
6. **Chat CSV for person episodes.** `origin = human`? Record the
   confederate's id? Anything about their latency?

Product / operations:

7. **Login model.** Options range from a single shared confederate password
   (env secret, like `ACCESS_CODE`) to real accounts with names. What is the
   minimum that makes the demo credible?
8. **Admin view.** A queue of waiting participants, one chat at a time per
   confederate, the pinned topic and the assigned role visible, and the
   participant's opinion as the first message. Anything else (session list,
   CSV download)?
9. **Transport.** Long-polling keeps the stdlib server; WebSockets mean the
   first dependency (or a different server). Both browsers on the same fly
   machine is fine either way; state has to live in the server process (or
   on the volume) since the proxy is currently stateless.
10. **Persistence.** In-memory state on one machine is enough for a demo but
    dies on restart / auto-stop (`min_machines_running = 0`). Is that
    acceptable, or should sessions survive a restart?
11. **Multiple participants at once.** Does the demo ever have two
    participants in parallel? If yes, matching logic; if no, one queue.
12. **Security of the confederate side.** The page is public with an access
    code; the confederate view would expose live participant text. Same code,
    a second code, or accounts?

Environment quirks worth knowing:

- Playwright is installed globally; the sandbox blocks `NODE_PATH`, so
  `web/e2e/run_flow.mjs` resolves it via `npm root -g` (or `PLAYWRIGHT_DIR`).
- In a worktree session the sandbox refuses `git -C <other checkout>`,
  heredoc-python and multi-step compound commands: use plain commands and the
  Edit/Write tools; leave the worktree (`ExitWorktree keep`) to merge into
  `main`.
- `openrouter_key.txt` is gitignored: copy it into any new worktree or the
  pre-flight will report "no key".
- The fly deploy applies staged secrets; `fly logs --no-tail` shows the boot
  lines (`LLM key: found in …`) and one `LLM fallback (...)` line per failed
  turn.
