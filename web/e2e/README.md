# web/e2e — browser check

Drives the whole session in a real (headless) Chromium in test mode and
asserts the flow matches the debate design; screenshots every screen type.

```bash
node web/e2e/run_flow.mjs --url http://localhost:8080 --code <ACCESS_CODE> --shots /tmp/shots
```

Needs Playwright installed globally (`npm i -g playwright && playwright
install chromium`); set `PLAYWRIGHT_DIR` if it lives elsewhere. Not part of the
unit suite: run it by hand, locally and after every deploy. Exit code 0 means
every check held.
