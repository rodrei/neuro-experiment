# web/ — browser implementation

The study, in a browser against a standard-library Python server: four chat
episodes about personal situations, two labelled as another participant and two
as an AI, with validation or rejection. In the study a person from the research
team answers the first two. The chat for that person is not built yet, so the LLM
answers all four, and the demo's start form and human announcements say so.
Deployed on fly.io in demo mode for the evaluators.

It reads `protocol/` through `common/protocol.py`. See the root `README.md` for
the flow, the two modes and the output files.

## Run locally

```bash
python3 -m web.server.app
```

Serves <http://localhost:8080>. Environment variables:

| Variable | Default | What it does |
| --- | --- | --- |
| `DEMO_MODE` | `1` | `1`: short timings, the «no se registra nada» notice, nothing stored. `0`: the full session and its four CSVs |
| `PORT` | `8080` | Listening port |
| `DATA_DIR` | `data/` | Where the CSVs are written |
| `ACCESS_CODE` | empty | If set, `/api/turn` and `/api/data` require it |
| `OPENROUTER_API_KEY` | — | The key (or `openrouter_key.txt` at the repo root). Without it every turn falls back |
| `LLM_TIMEOUT` | `20` | Seconds to wait for the API before falling back |
| `RATE_LIMIT_PER_MINUTE` | `30` | Requests per IP per minute |
| `MAX_TURNS_PER_DAY` | `600` | Demo only: model calls per day across all sessions (a walkthrough is twelve). Past it, turns come from the fallback lines |

On boot the server prints where it found the key (or that it did not).

Tests: `python3 -m unittest discover -s web -t . -v`

## What is inside

| File | What it does |
| --- | --- |
| `server/app.py` | Serves the page; `GET /api/protocol` (with `demo_mode`), `GET /api/health` (LLM probe, cached 60 s, `?refresh=1`), `POST /api/turn` (stateless proxy to the LLM: `{feedback, history, fallback_line}` → `{text, origin, fallback_reason}`; a history longer than an episode is 400), `POST /api/data` (writes the four CSVs; 403 in demo mode). Stdlib only |
| `index.html` | Start form (id, age, sex, the two Latin square rows, access code, test mode) and the LLM pre-flight line; in demo mode, only the access code and the notice |
| `js/protocol.js` | Loads `/api/protocol`; `parameters()`, `fallbackLine()`, `fill()` |
| `js/chat-plugin.js` | Custom plugin: one episode in one trial — fixed opening, three rounds, final hold, experimenter hotkey, fallback banner in test mode |
| `js/scales.js` | Text screens, sliders, grids, open questions, measure collection |
| `js/experiment.js` | The timeline, the row assignment, the distress alert, Saltar, submission |
| `static/styles.css` | Palette; centred screens; demo notice; banner |
| `static/vendor/` | jsPsych 8.3.0 and plugins, pinned (no CDN) |
| `e2e/run_flow.mjs` | Playwright walk of the whole flow with assertions and screenshots |

## Seeing what the LLM is doing

- **Pre-flight** on the start form, outside the demo: green «LLM listo: <model>
  respondió en N s (key: env|file)» or red with the reason (no key, 401,
  timeout, TLS…). «Volver a comprobar el LLM» forces a new probe.
- **Test mode banner** under the chat bar: «Fallback (ronda N): <reason>» the
  moment a turn falls back; amber «N turno(s) cayeron al fallback» once a later
  turn succeeds.
- **Server output**: one `LLM fallback (<feedback>): <reason>` line per
  failure (`fly logs` in production).
- **CSV**: `origin` and `fallback_reason` per message in `_chat.csv`,
  `fallback_turns` per episode in `_behavioral.csv`.

## Test mode

Outside the demo, the **Modo test** checkbox adds a **Saltar** button bottom
right and the **F9** key (on a Mac usually with `fn`) on every screen, plus the
fallback banner. Whatever is skipped stays **empty** in the CSVs and a skipped
PANAS page leaves the subscale without a total; `test_mode` is recorded in
`_responses.csv`. Inside the chat the skip does not end the episode: it cuts the
current wait or sends whatever is typed, filling an empty first message with
`test_filler_text` from the protocol.

In the demo, Saltar and F9 work on every screen except the chat.

## Browser check

```bash
node web/e2e/run_flow.mjs --url http://localhost:8080 --code <ACCESS_CODE> --shots /tmp/shots
```

Needs Playwright installed globally (`npm i -g playwright && playwright
install chromium`; `PLAYWRIGHT_DIR` if it lives elsewhere). It reads the mode
from the server. See `e2e/README.md` for what it asserts. Run it locally in both
modes, and against the deployment after every deploy.

## Deploy on fly.io

App `neuro-estudio1-demo`, organisation `personal`, region `gru` (São
Paulo; fly has no region in Argentina).

```bash
fly deploy --app neuro-estudio1-demo
```

`Dockerfile` and `fly.toml` are at the **repo root**: the container needs
`protocol/` and `common/` besides `web/`. `fly.toml` sets `DEMO_MODE = "1"`.
Secrets: `OPENROUTER_API_KEY` and `ACCESS_CODE` (`fly secrets set
ACCESS_CODE=<new> --app neuro-estudio1-demo`). It is a public URL that spends
OpenRouter credit: keep a code and rotate it after each demo.

### Four things that start billing silently

The account is on the **legacy Hobby plan**, which keeps the old free
allowance: 3 `shared-cpu-1x` VMs of 256 MB, 3 GB of volume and 100 GB of
traffic. This app uses 1 machine and 1 GB.

1. **Memory.** `fly.toml` pins `memory = "256mb"`.
2. **IPv4.** Must be **shared** (`fly ips allocate-v4 --shared`); a dedicated
   one costs USD 2/month. Check with `fly ips list`.
3. **Volume.** Billed by provisioned size, not usage. The fly volume keeps its
   original name `datos`; it is mounted at `/data`.
4. **Plan.** Leaving the legacy plan is **irreversible**. Decline any
   dashboard offer to move to pay-as-you-go.

## What it does not do

No database, no accounts, no attention checks, no pictorial SAM, no phone
support (a notice asks for a computer), no hardware trigger output (LSL, serial
or parallel): `_events.csv` is aligned with the recording offline, by `t_unix`.
