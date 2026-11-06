# web/e2e — browser check

Drives sessions in a real (headless) Chromium and asserts the flow matches the
specification; screenshots every screen type. It reads the mode from
`/api/protocol` and adapts, so run it against both `DEMO_MODE=1` and
`DEMO_MODE=0`.

```bash
node web/e2e/run_flow.mjs --url http://localhost:8080 --code <ACCESS_CODE> --admin <ADMIN_CODE> --shots /tmp/shots
```

It saves real sessions. Their ids start with `check-`: `/admin` marks them as tests
and the full download leaves them out. After a run against the deployment, remove
them with `fly ssh console --app neuro-estudio1-demo -C "sh -c 'rm /data/S1_check-*'"`.

Needs Playwright installed globally (`npm i -g playwright && playwright
install chromium`); set `PLAYWRIGHT_DIR` if it lives elsewhere. Not part of the
unit suite: run it by hand, locally and after every deploy. Exit code 0 means
every check held.

- **Full session**, answering every screen: the order of the session, four
  episodes of opening plus three rounds, an announcement matching each header
  label, one domain per episode, the post-episode order, the final block, the
  debriefing, the experimenter's typed message, the 38/38/37/37 row split, and
  that the session is saved as four files.
- **By hand**: a rating of 9 triggers the alert, replacing asks for the same
  domain again, and one real message gets an answer from the model within the
  cap.
- **Withdrawal**: FIN ends an episode at once, and a withdrawn session sends
  nothing to the server.
- **The team's view** (with `--admin`): `/admin` refuses a missing or wrong password
  and the evaluators' code, and shows and downloads the session just saved.
