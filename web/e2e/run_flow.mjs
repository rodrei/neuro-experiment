/* End-to-end check of the web flow in a real browser.
 *
 *   node web/e2e/run_flow.mjs --url http://localhost:8080 [--code X] [--shots DIR]
 *
 * Runs the whole session in test mode against the given URL, asserts the
 * flow matches the debate design, and screenshots every screen type at
 * 1280x800 (and the first screens again at 1440x900) under --shots.
 *
 * Uses the globally installed Playwright: set PLAYWRIGHT_DIR to the folder
 * that contains its package (default: `npm root -g`/playwright). Not part of
 * the unit suite; run it by hand after a deploy. Exit code 0 = every
 * assertion held. */

import { createRequire } from "node:module";
import { execSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";

const args = parseArgs(process.argv.slice(2));
const URL = args.url || "http://localhost:8080";
const CODE = args.code || "";
const SHOTS = args.shots || "";
if (SHOTS) mkdirSync(SHOTS, { recursive: true });

const playwrightDir = process.env.PLAYWRIGHT_DIR
  || path.join(execSync("npm root -g").toString().trim(), "playwright");
const { chromium } = createRequire(import.meta.url)(playwrightDir);

const failures = [];
function check(condition, message) {
  console.log((condition ? "  ok   " : "  FAIL ") + message);
  if (!condition) failures.push(message);
}

let shotIndex = 0;
async function shot(page, kind) {
  if (!SHOTS) return;
  shotIndex += 1;
  const name = `${String(shotIndex).padStart(2, "0")}-${kind}.png`;
  await page.screenshot({ path: path.join(SHOTS, name) });
}

/* What kind of screen is on display, from the DOM. */
async function classify(page) {
  return page.evaluate(() => {
    const el = document.querySelector("#jspsych-target");
    if (!el) return "none";
    const text = el.innerText || "";
    if (el.querySelector(".chat")) return "chat";
    if (el.querySelector(".topic-card")) return "topic-pick";
    if (el.querySelector(".fixation-cross")) return "rest";
    if (el.querySelector(".jspsych-survey-likert-statement")) return "panas";
    if (el.querySelector("input[type=range]")) return "slider";
    if (text.startsWith("Conectando")) return "connecting";
    if (text.startsWith("Tu próxima conversación")) return "intro";
    if (text.startsWith("Antes de empezar")) return "consent";
    if (text.startsWith("Registro en reposo")) return "rest-instructions";
    if (text.startsWith("Las conversaciones")) return "instructions";
    if (text.startsWith("Pausa")) return "pause";
    if (text.startsWith("Sobre lo que acabás")) return "debriefing";
    if (text.includes("Se guardaron")) return "saved";
    if (text.startsWith("Listo")) return "close";
    if (text.startsWith("Guardando")) return "saving";
    if (text.trim() === "") return "blank";
    return "other";
  });
}

async function runFlow(browser, viewport, { full }) {
  console.log(`\n== ${viewport.width}x${viewport.height}${full ? "" : " (start screens only)"}`);
  const page = await browser.newPage({ viewport });
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });

  await page.goto(URL);
  await page.waitForFunction(
    () => document.getElementById("load-status").textContent.includes("cargado"),
    null, { timeout: 30000 });
  await page.waitForSelector("#llm-health.ok, #llm-health.error", { timeout: 60000 });
  const health = await page.textContent("#llm-health");
  const healthOk = await page.$eval("#llm-health", (el) => el.classList.contains("ok"));
  check(health.trim().length > 0, "health line rendered: " + health.trim());
  await shot(page, "start");

  await page.fill("input[name=participant_id]", "e2e");
  await page.check("input[name=test_mode]");
  if (CODE) await page.fill("input[name=access_code]", CODE);
  await page.click("#begin");

  const shotTaken = new Set();
  const topicCounts = [];
  const introsBeforeChats = [];
  let chats = 0;
  let sawCoverStory = false;
  let sawSuspicion = false;
  let bubbleInsidePinned = false;
  let firstBubbleParticipant = true;
  const firstBubbleChecked = new Set();
  let fallbackBanners = 0;
  let last = "";
  let idle = 0;

  for (let i = 0; i < 400; i++) {
    await page.waitForTimeout(300);
    const kind = await classify(page);
    const text = await page.$eval("#jspsych-target", (el) => el.innerText || "");

    if (text.includes("En unos segundos vas a quedar")) sawCoverStory = true;
    if (text.includes("creíste que estabas interactuando")) sawSuspicion = true;

    if (kind !== last) {
      idle = 0;
      if (!shotTaken.has(kind) && kind !== "blank" && kind !== "none") {
        await shot(page, kind);
        shotTaken.add(kind);
      }
      if (kind === "intro") introsBeforeChats.push(chats);
      if (kind === "topic-pick") {
        topicCounts.push(await page.$$eval(".topic-card", (c) => c.length));
      }
      if (kind === "chat") {
        chats += 1;
        const info = await page.evaluate(() => {
          const pinned = document.querySelector(".topic-pinned");
          const first = document.querySelector(".chat-messages .bubble");
          return {
            pinned: !!pinned,
            pinnedIsBubble: pinned ? pinned.classList.contains("bubble") : false,
            pinnedHasBubble: pinned ? !!pinned.querySelector(".bubble") : false,
            firstBubble: first ? first.className : null,
          };
        });
        check(info.pinned, `chat ${chats}: pinned topic card present`);
        if (info.pinnedIsBubble || info.pinnedHasBubble) bubbleInsidePinned = true;
      }
      last = kind;
    } else {
      idle += 1;
    }

    if (kind === "chat") {
      // Watch the first bubble as it appears and the banner in test mode.
      const state = await page.evaluate(() => {
        const first = document.querySelector(".chat-messages .bubble");
        const banner = document.querySelector(".fallback-banner:not([hidden])");
        return { first: first ? first.className : null, banner: !!banner };
      });
      if (state.first && !firstBubbleChecked.has(chats)) {
        firstBubbleChecked.add(chats);
        if (!state.first.includes("participant")) firstBubbleParticipant = false;
      }
      if (state.banner) fallbackBanners += 1;
    }

    if (kind === "saved") break;
    if (!full && kind === "chat" && chats >= 1 && idle > 2) break;

    const card = await page.$(".topic-card");
    if (card) { await card.click(); continue; }
    await page.keyboard.press("F9");
  }

  if (full) {
    const final = await classify(page);
    check(final === "saved", "run reached the saved screen (" + final + ")");
    const savedText = await page.$eval("#jspsych-target", (el) => el.innerText);
    check(/Se guardaron 4 archivos/.test(savedText), "four files saved");
    check(chats === 4, `four chat episodes (got ${chats})`);
    check(JSON.stringify(topicCounts) === JSON.stringify([8, 7, 6, 5]),
          `topic list shrinks 8,7,6,5 (got ${JSON.stringify(topicCounts)})`);
    check(JSON.stringify(introsBeforeChats) === JSON.stringify([0, 1, 2, 3]),
          `an interlocutor intro precedes every episode (got ${JSON.stringify(introsBeforeChats)})`);
    check(!sawCoverStory, "no cover-story screen");
    check(!sawSuspicion, "no suspicion / belief screen");
    check(!bubbleInsidePinned, "pinned card is not a bubble");
    check(firstBubbleParticipant, "first bubble of a chat is the participant's");
    if (healthOk) {
      check(fallbackBanners === 0, "no fallback banner while the LLM is reachable");
    } else {
      console.log("  note LLM not reachable during this run; fallback banners expected");
    }
  }
  check(errors.length === 0, "no JS errors" + (errors.length ? ": " + errors.join(" | ") : ""));
  await page.close();
}

const browser = await chromium.launch();
try {
  await runFlow(browser, { width: 1280, height: 800 }, { full: true });
  await runFlow(browser, { width: 1440, height: 900 }, { full: false });
} finally {
  await browser.close();
}

console.log(failures.length ? `\n${failures.length} failure(s)` : "\nall checks passed");
process.exit(failures.length ? 1 : 0);

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) out[argv[i].slice(2)] = argv[i + 1] || "";
  }
  return out;
}
