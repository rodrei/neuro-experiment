# web/ — browser implementation

The reference implementation of the current design: four debate episodes
per participant, two introduced as a person and two as an AI, each about a
question the participant picks, with validation or rejection from an LLM.
Runs in a browser against a standard-library Python server; deployed on
fly.io for the group.

It reads the same `protocol/` as `desktop/`, through `common/protocol.py`.
It records no EDA. In phase 1 every episode is answered by the LLM, including
the ones introduced as a person; phase 2 connects those to a real person.

## Run locally

```bash
python3 -m web.server.app
```

Serves <http://localhost:8080>. Environment variables:

| Variable | Default | What it does |
| --- | --- | --- |
| `PORT` | `8080` | Listening port |
| `DATA_DIR` | `data/` | Where the CSVs are written |
| `ACCESS_CODE` | empty | If set, `/api/turn` and `/api/data` require it |
| `OPENROUTER_API_KEY` | — | The key (or `openrouter_key.txt` at the repo root). Without it every turn falls back |
| `LLM_TIMEOUT` | `20` | Seconds to wait for the API before falling back |
| `RATE_LIMIT_PER_MINUTE` | `30` | Requests per IP per minute |

On boot the server prints where it found the key (or that it did not).

Tests: `python3 -m unittest discover -s web -t . -v`

## What is inside

| File | What it does |
| --- | --- |
| `server/app.py` | Serves the page; `GET /api/protocol`, `GET /api/health` (LLM probe, cached 60 s, `?refresh=1`), `POST /api/turn` (stateless proxy to the LLM: `{feedback, name, question, history, fallback_line}` → `{text, origin, fallback_reason}`), `POST /api/data` (writes the four CSVs). Stdlib only |
| `index.html` | Start form (id, age, sex, sequence, access code, test mode) and the LLM pre-flight line |
| `js/protocol.js` | Loads `/api/protocol`; `fallbackLine()`, `fill()` |
| `js/chat-plugin.js` | Custom plugin: one episode in one trial — pinned topic card, opinion first, three LLM turns, free replies, fallback banner in test mode |
| `js/scales.js` | Text screens, sliders, PANAS grid, measure collection |
| `js/experiment.js` | The timeline (sequence → four episodes), test mode, submission |
| `static/styles.css` | Palette of the desktop; centred screens; topic cards; pinned card; banner |
| `static/vendor/` | jsPsych 8.3.0 and plugins, pinned (no CDN) |
| `e2e/run_flow.mjs` | Playwright walk of the whole flow with assertions and screenshots |

## Seeing what the LLM is doing

- **Pre-flight** on the start form: green «LLM listo: <model> respondió en
  N s (key: env|file)» or red with the reason (no key, 401, timeout, TLS…).
  «Volver a comprobar el LLM» forces a new probe.
- **Test mode banner** under the chat bar: «Fallback (turno N): <reason>» the
  moment a turn falls back; amber «N turno(s) cayeron al fallback» once a
  later turn succeeds. Participants outside test mode see nothing.
- **Server output**: one `LLM fallback (<feedback>): <reason>` line per
  failure (`fly logs` in production).
- **CSV**: `origin` and `fallback_reason` per message in `_chat.csv`,
  `fallback_turns` per episode in `_behavioral.csv`.

## Test mode

The **Modo test** checkbox adds a **Saltar** button bottom right and the
**F9** key (on a Mac usually with `fn`) on every screen, plus the fallback
banner. Whatever is skipped stays **empty** in the CSVs and a skipped PANAS
page leaves the subscale without a total; `test_mode` is recorded in
`_responses.csv`. Inside the chat the skip does not end the episode: it sends
whatever is typed, filling the mandatory opinion with `test_filler_opinion`
from the protocol. A skipped topic pick takes the first remaining topic.

## Browser check

```bash
node web/e2e/run_flow.mjs --url http://localhost:8080 --code <ACCESS_CODE> --shots /tmp/shots
```

Needs Playwright installed globally (`npm i -g playwright && playwright
install chromium`; `PLAYWRIGHT_DIR` if it lives elsewhere). It runs the
full session in test mode at 1280×800, the start screens again at 1440×900,
asserts the flow (four episodes, 8/7/6/5 topics, an intro before every
chat, no cover-story or suspicion screens, the pinned card is not a bubble,
the participant speaks first, no fallback while the LLM is reachable, no JS
errors) and screenshots every screen type. Run it locally and against the
deployment after every deploy.

## Deploy on fly.io

App `neuro-estudio1-demo`, organisation `personal`, region `gru` (São
Paulo; fly has no region in Argentina).

```bash
fly deploy --app neuro-estudio1-demo
```

`Dockerfile` and `fly.toml` are at the **repo root**: the container needs
`protocol/` and `common/` besides `web/`. Secrets: `OPENROUTER_API_KEY` and
`ACCESS_CODE` (`fly secrets set ACCESS_CODE=<new> --app neuro-estudio1-demo`).
It is a public URL that spends OpenRouter credit: keep a code and rotate it
after each demo.

### Four things that start billing silently

The account is on the **legacy Hobby plan**, which keeps the old free
allowance: 3 `shared-cpu-1x` VMs of 256 MB, 3 GB of volume and 100 GB of
traffic. This app uses 1 machine and 1 GB.

1. **Memory.** `fly.toml` pins `memory = "256mb"`.
2. **IPv4.** Must be **shared** (`fly ips allocate-v4 --shared`); a dedicated
   one costs USD 2/month. Check with `fly ips list`.
3. **Volume.** Billed by provisioned size, not usage: 1 GB is ~65,000
   sessions at 16 KB each. The fly volume keeps its original name `datos`;
   it is mounted at `/data`.
4. **Plan.** Leaving the legacy plan is **irreversible**. Decline any
   dashboard offer to move to pay-as-you-go.

### Getting the data down

The volume is tied to one machine: **not durable storage**. After each
session or demo:

```bash
fly ssh console --app neuro-estudio1-demo -C "ls /data"
fly sftp get /data/<file>.csv --app neuro-estudio1-demo
```

## What it does not do

No database, no accounts, no attention checks, no pictorial SAM, no phone
support (a notice asks for a computer), no LSL or serial equivalent. It always
runs with the `demo` timings of `protocol/parameters.json`.
