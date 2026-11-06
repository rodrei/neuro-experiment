# web/e2e — browser check

Drives sessions in a real (headless) Chromium and asserts the flow matches the
specification; screenshots every screen type. It reads the mode from
`/api/protocol` and adapts, so run it against both `DEMO_MODE=1` and
`DEMO_MODE=0`.

```bash
node web/e2e/run_flow.mjs --url http://localhost:8080 --code <ACCESS_CODE> --shots /tmp/shots
```

Needs Playwright installed globally (`npm i -g playwright && playwright
install chromium`); set `PLAYWRIGHT_DIR` if it lives elsewhere. Not part of the
unit suite: run it by hand, locally and after every deploy. Exit code 0 means
every check held.

- **Full session**, answering every screen: the order of the session, four
  episodes of opening plus three rounds, an announcement matching each header
  label, one domain per episode, the post-episode order, the final block, the
  debriefing, the experimenter's typed message, the 38/38/37/37 row split. In
  the demo, nothing reaches `/api/data`; otherwise, four files are saved.
- **By hand**: a rating of 9 triggers the alert, replacing asks for the same
  domain again, and one real message gets an answer from the model within the
  cap.
- **Withdrawal** (research mode only): FIN ends an episode at once, and a
  withdrawn session sends nothing to the server.
