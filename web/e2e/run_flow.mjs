/* End-to-end check of the web flow in a real browser.
 *
 *   node web/e2e/run_flow.mjs --url http://localhost:8080 [--code X] [--admin Y] [--shots DIR]
 *
 * Reads the mode from /api/protocol and adapts. On a server that requires an
 * access code it also checks the pop-up for a wrong or blank one.
 *
 * Two runs. The first walks the whole session in test mode, typing in the chat
 * and using the experimenter hotkey, and asserts the order of the screens. The
 * second answers the elicitation by hand to exercise the distress alert, then
 * sends one real message in a chat.
 *
 * Uses the globally installed Playwright: set PLAYWRIGHT_DIR to the folder
 * that contains its package (default: `npm root -g`/playwright). Not part of
 * the unit suite; run it by hand, locally and after a deploy. Exit code 0 =
 * every assertion held. */

import { createRequire } from "node:module";
import { execSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import path from "node:path";

const args = parseArgs(process.argv.slice(2));
const URL_BASE = args.url || "http://localhost:8080";
const CODE = args.code || "";
const ADMIN = args.admin || "";
const SHOTS = args.shots || "";

let savedFiles = [];      // what /api/data answered for the full flow's session
if (SHOTS) mkdirSync(SHOTS, { recursive: true });

const playwrightDir = process.env.PLAYWRIGHT_DIR
  || path.join(execSync("npm root -g").toString().trim(), "playwright");
const { chromium } = createRequire(import.meta.url)(playwrightDir);

const PROTOCOL = await (await fetch(URL_BASE + "/api/protocol")).json();
const DEMO = PROTOCOL.demo_mode;
const TXT = PROTOCOL.texts;
const EXPERIMENTER_LINE = "Mensaje escrito por el experimentador.";

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

const targetText = (page) =>
  page.$eval("#jspsych-target", (el) => el.innerText || "");

/* What kind of screen is on display, from the DOM. */
async function classify(page) {
  return page.evaluate((demoEnd) => {
    const el = document.querySelector("#jspsych-target");
    if (!el) return "none";
    const text = el.innerText || "";
    if (el.querySelector(".chat")) return "chat";
    if (el.querySelector(".fixation-cross")) return "rest";
    if (el.querySelector(".jspsych-survey-likert-statement")) return "panas";
    if (el.querySelector("input[type=range]")) return "slider";
    if (el.querySelector("textarea")) return "text-question";
    if (text.startsWith("Conectando")) return "connecting";
    if (text.startsWith("Próxima conversación")) return "announcement";
    if (text.startsWith("Antes de empezar")) return "consent";
    if (text.startsWith("Registro en reposo")) return "rest-instructions";
    if (text.startsWith("Acá va el cuestionario")) return "instrument";
    if (text.startsWith("Tus situaciones")) return "elicitation-intro";
    if (text.startsWith("Avisale al experimentador")) return "distress-alert";
    if (text.startsWith("Las conversaciones")) return "instructions";
    if (text.startsWith("Pausa")) return "pause";
    if (text.startsWith("Últimas preguntas")) return "final-intro";
    if (text.startsWith("Sobre lo que acabás")) return "debriefing";
    if (text.startsWith("Tus datos")) return "data-use";
    if (text.includes("Se guardaron")) return "saved";
    if (text.startsWith(demoEnd)) return "demo-end";
    if (text.startsWith("Listo")) return "close";
    if (text.startsWith("Guardando")) return "saving";
    if (text.trim() === "") return "blank";
    return "other";
  }, TXT.demo.end_title);
}

async function openStart(browser, viewport) {
  const page = await browser.newPage({ viewport });
  page.errors = [];
  page.on("pageerror", (e) => page.errors.push("pageerror: " + e.message));
  page.on("console", (m) => {
    if (m.type() === "error") page.errors.push("console: " + m.text());
  });
  await page.goto(URL_BASE + "/?check");
  await page.waitForFunction(
    () => document.getElementById("load-status").textContent.includes("cargado"),
    null, { timeout: 30000 });
  await page.waitForSelector("#llm-health.ok, #llm-health.error",
                             { timeout: 60000, state: "attached" });
  return page;
}

async function begin(page, { testMode }) {
  if (!DEMO) await page.fill("input[name=participant_id]", "check-7");
  if (testMode) {
    await page.evaluate(() => {
      document.querySelector("input[name=test_mode]").checked = true;
    });
  }
  if (CODE) await page.fill("input[name=access_code]", CODE);
  await page.click("#begin");
}

/* Answers the screen on display the way a participant would, so the values
 * reach the CSVs. False when there is nothing to answer (a timed screen). */
async function answerScreen(page, kind) {
  if (kind === "slider") {
    await page.evaluate(() => {
      const el = document.querySelector("input[type=range]");
      el.value = Number(el.min) + Number(el.step);
      el.dispatchEvent(new Event("change"));
    });
    await page.click("#jspsych-html-slider-response-next");
    return true;
  }
  if (kind === "panas") {
    await page.evaluate(() => {
      document.querySelectorAll(".jspsych-survey-likert-opts").forEach((row) => {
        row.querySelector("input[type=radio]").checked = true;
      });
    });
    await page.click("#jspsych-survey-likert-next");
    return true;
  }
  if (kind === "text-question") {
    await page.fill("textarea", "Respuesta de prueba, con detalle y sin recortar.");
    await page.click("#jspsych-survey-text-next");
    return true;
  }
  const button = await page.$("#jspsych-target .jspsych-btn");
  if (button) {
    await button.click();
    return true;
  }
  return false;
}

const postCheckCode = async (code) => {
  const response = await fetch(URL_BASE + "/api/check-code", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access_code: code }),
  });
  return (await response.json()).valid;
};

/* A wrong or blank code stops at the pop-up. The demo can go on with fixed
 * replies, which touch neither the model nor the saved data. */
async function accessCodeFlow(browser) {
  console.log("\n== access code");
  const T = TXT.access_code;
  const page = await openStart(browser, { width: 1280, height: 800 });
  const called = [];
  page.on("request", (r) => {
    if (/\/api\/(turn|data)$/.test(r.url())) called.push(r.url());
  });
  if (!DEMO) await page.fill("input[name=participant_id]", "check-7");
  const submitted = async (code) => {
    await page.fill("input[name=access_code]", code);
    await page.click("#begin");
    await page.waitForSelector("#code-dialog[open]", { timeout: 10000 });
    return page.textContent("#code-dialog");
  };

  check((await submitted("")).includes(T.blank), "a blank code opens the pop-up and says so");
  check(await page.isVisible("#code-retry"), "the pop-up offers to enter another code");
  await shot(page, "code-blank");
  await page.click("#code-retry");
  check(!(await page.isVisible("#code-dialog")), "entering another code closes the pop-up");
  check(await page.isVisible("#start"), "and goes back to the form");
  const focused = await page.waitForFunction(
    () => document.activeElement === document.querySelector("input[name=access_code]"),
    null, { timeout: 2000 }).then(() => true, () => false);
  check(focused, "with the code field ready to type");

  check((await submitted("no-es-el-codigo")).includes(T.invalid),
        "a wrong code opens the pop-up and says so");
  await shot(page, "code-invalid");

  if (!DEMO) {
    check(!(await page.isVisible("#code-fixed")), "fixed replies are not offered in a real session");
    check(called.length === 0, "nothing was sent to the model or saved");
    check(page.errors.length === 0, "no JS errors" + (page.errors.length ? ": " + page.errors.join(" | ") : ""));
    await page.close();
    return;
  }

  check((await page.textContent("#code-dialog")).includes(T.fixed_question),
        "the pop-up asks about going on with fixed replies");
  await page.click("#code-fixed");
  check(!(await page.isVisible("#start")), "going on starts the session");
  check((await page.textContent("#demo-badge")).trim() === TXT.demo.fixed_badge,
        "the badge says there is no AI and nothing is saved");

  let announcement = "";
  for (let i = 0; i < 400; i++) {
    const kind = await classify(page);
    if (kind === "announcement") announcement = await targetText(page);
    if (kind === "chat") break;
    await skipOutsideChat(page);
    await page.waitForTimeout(50);
  }
  check(announcement.includes(TXT.demo.fixed_note), "the announcement says the replies are fixed");

  await page.waitForFunction(
    () => !document.querySelector("#chat-text").disabled, null, { timeout: 30000 });
  await page.fill("#chat-text", "Me sentí muy mal con lo que pasó.");
  await page.keyboard.press("Enter");
  await page.waitForFunction(
    () => document.querySelectorAll(".chat-messages .bubble.agent").length === 2,
    null, { timeout: 30000 });
  const reply = await page.$$eval(".chat-messages .bubble.agent", (b) => b[1].textContent);
  const lines = Object.values(PROTOCOL.fallback).flatMap((block) => Object.values(block));
  check(lines.includes(reply), `the reply is a fixed line: «${reply}»`);
  check(await page.$eval("#fallback-banner", (el) => el.hidden), "a fixed reply is not reported as a failure");
  await shot(page, "code-fixed-chat");
  await page.keyboard.press("F9");

  let last = "";
  for (let i = 0; i < 600; i++) {
    last = await classify(page);
    if (last === "demo-end") break;
    await page.keyboard.press("F9");
    await page.waitForTimeout(100);
  }
  check(last === "demo-end", `the session reaches the end (${last})`);
  check((await targetText(page)).includes(TXT.demo.fixed_end_body), "the last screen says nothing was saved");
  check(called.length === 0, "nothing was sent to the model or saved");
  check(page.errors.length === 0, "no JS errors" + (page.errors.length ? ": " + page.errors.join(" | ") : ""));
  await page.close();
}

/* Withdrawing leaves nothing on the server, and FIN ends an episode early.
 * Everything else is skipped, which must not break the run. */
async function withdrawFlow(browser) {
  console.log("\n== withdrawal and experimenter FIN");
  const page = await openStart(browser, { width: 1280, height: 800 });
  const posted = [];
  page.on("request", (r) => {
    if (r.url().endsWith("/api/data")) posted.push(r.url());
  });
  page.on("dialog", (d) => d.accept("FIN"));
  await begin(page, { testMode: true });

  let ended = false;
  let endedWith = "";
  let reachedDataUse = false;
  for (let i = 0; i < 1500; i++) {
    await page.waitForTimeout(100);
    const kind = await classify(page);
    // The situations get text, so FIN meets a pre-filled box.
    if (kind === "text-question" && !ended) {
      await answerScreen(page, kind);
      continue;
    }
    if (kind === "chat" && !ended) {
      const authors = await page.$$eval(".chat-messages .bubble",
        (b) => b.map((x) => (x.classList.contains("agent") ? "A" : "P")).join(""));
      if (authors === "A") {
        await page.keyboard.press("Control+Shift+E");
        await page.waitForSelector("#chat-continue:not([hidden])", { timeout: 30000 });
        endedWith = await page.$$eval(".chat-messages .bubble",
          (b) => b.map((x) => (x.classList.contains("agent") ? "A" : "P")).join(""));
        ended = true;
      }
      if (!ended) continue;
    }
    if (kind === "data-use") {
      reachedDataUse = true;
      await page.click(`button:has-text("${TXT.data_use.withdraw}")`);
      continue;
    }
    if (reachedDataUse && kind === "close") {
      await page.click("#jspsych-target .jspsych-btn");
      continue;
    }
    if ((await targetText(page)).startsWith(TXT.withdrawn.title)) break;
    await page.keyboard.press("F9");
  }
  check(endedWith === "A", `FIN ended the first episode without sending the box (got ${endedWith})`);
  check((await targetText(page)).startsWith(TXT.withdrawn.title), "the withdrawal screen appears");
  check(posted.length === 0, "a withdrawn session sends nothing to /api/data");
  check(page.errors.length === 0, "no JS errors" + (page.errors.length ? ": " + page.errors.join(" | ") : ""));
  await page.close();
}

/* The team's view, against the session the full flow just saved. */
async function adminFlow(browser) {
  console.log("\n== the team's view of the sessions");
  const open = (path, password) => fetch(URL_BASE + path, {
    headers: password === undefined ? {} : {
      Authorization: "Basic " + Buffer.from("equipo:" + password).toString("base64"),
    },
  });
  const suffix = "_responses.csv";
  const file = savedFiles.find((name) => name.endsWith(suffix));
  check(Boolean(file), "the full flow saved a session to look for");
  if (!file) return;
  const base = file.slice(0, -suffix.length);

  check((await open("/admin")).status === 401, "/admin asks for a password");
  check((await open("/admin", "wrong")).status === 401, "a wrong password is refused");
  if (CODE) {
    check((await open("/admin", CODE)).status === 401, "the evaluators' code does not open it");
  }
  const list = await open("/admin", ADMIN);
  check(list.status === 200 && (await list.text()).includes(base), "the session is in the list");

  const detail = await (await open("/admin/session/" + base, ADMIN)).text();
  check(detail.includes("Me sentí muy mal con lo que pasó"), "its page shows the conversation");
  check(detail.includes("ep1_condition"), "its page shows the responses");

  const csvResponse = await open(`/admin/file/${base}_chat.csv`, ADMIN);
  check(csvResponse.status === 200
        && (csvResponse.headers.get("content-disposition") || "").includes("attachment")
        && (await csvResponse.text()).includes("Me sentí muy mal con lo que pasó"),
        "its transcript downloads");

  const isZip = async (response) => {
    const bytes = new Uint8Array(await response.arrayBuffer());
    return response.status === 200 && bytes[0] === 0x50 && bytes[1] === 0x4b;
  };
  check(await isZip(await open(`/admin/session/${base}.zip`, ADMIN)), "the session downloads as a zip");
  check(await isZip(await open("/admin/all.zip", ADMIN)), "everything downloads as a zip");

  if (SHOTS) {
    const context = await browser.newContext({
      httpCredentials: { username: "equipo", password: ADMIN },
      viewport: { width: 1280, height: 800 },
    });
    const page = await context.newPage();
    await page.goto(URL_BASE + "/admin");
    await shot(page, "admin-list");
    await page.goto(URL_BASE + "/admin/session/" + base);
    await shot(page, "admin-session");
    await context.close();
  }
}

/* F9, unless a chat has just appeared: checked in the page, in one step, so a
 * chat that starts between two commands is not skipped by accident. */
async function skipOutsideChat(page) {
  await page.evaluate(() => {
    if (document.querySelector("#jspsych-target .chat")) return;
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "F9", bubbles: true }));
  });
}

/* Demo only: Saltar and F9 end a conversation at any moment, and what was under
 * way in the skipped one must not leak into the next. */
async function skipChatFlow(browser) {
  console.log("\n== skipping conversations (demo)");
  const page = await openStart(browser, { width: 1280, height: 800 });
  const posted = [];
  page.on("request", (r) => {
    if (r.url().endsWith("/api/data")) posted.push(r.url());
  });
  await begin(page, { testMode: false });

  const untilChat = async () => {
    for (let i = 0; i < 400; i++) {
      if (await classify(page) === "chat") return true;
      await skipOutsideChat(page);
      await page.waitForTimeout(100);
    }
    return false;
  };
  const inputOpen = () => page.waitForFunction(
    () => !document.querySelector("#chat-text").disabled, null, { timeout: 30000 });
  const left = async () => {
    await page.waitForTimeout(200);
    return !(await page.isVisible("#jspsych-target .chat"));
  };

  check(await untilChat(), "reached the first chat");
  check(await page.isVisible("#skip"), "Saltar shows inside the chat");
  await page.keyboard.press("F9");
  check(await left(), "F9 ends a conversation while the opening is on its way");
  check(await classify(page) === "panas", "the measures follow a skipped conversation");

  check(await untilChat(), "reached the second chat");
  await inputOpen();
  await page.fill("#chat-text", "Me dejaron afuera y me sentí mal.");
  await page.keyboard.press("Enter");
  await page.click("#skip");
  check(await left(), "Saltar ends a conversation while a reply is on its way");

  check(await untilChat(), "reached the third chat");
  await inputOpen();
  await page.fill("#chat-text", "Me sentí muy mal con lo que pasó.");
  await page.keyboard.press("Enter");
  await page.waitForFunction(
    () => document.querySelectorAll(".chat-messages .bubble.agent").length === 2,
    null, { timeout: 60000 });
  const authors = await page.$$eval(".chat-messages .bubble",
    (b) => b.map((x) => (x.classList.contains("agent") ? "A" : "P")).join(""));
  check(authors === "APA", `a skipped conversation does not leak into the next (got ${authors})`);
  await page.keyboard.press("F9");
  check(await left(), "F9 ends a conversation after a reply");

  check(await untilChat(), "reached the fourth chat");
  await inputOpen();
  await page.fill("#chat-text", "Esto no se envía.");
  await page.keyboard.press("F9");
  check(await left(), "F9 ends a conversation while the participant is typing");

  let last = "";
  for (let i = 0; i < 400; i++) {
    last = await classify(page);
    if (last === "demo-end") break;
    await skipOutsideChat(page);
    await page.waitForTimeout(100);
  }
  check(last === "demo-end", `the session still reaches the end (${last})`);
  check(posted.length === 1, "a session with skipped conversations is still saved");
  check(page.errors.length === 0, "no JS errors" + (page.errors.length ? ": " + page.errors.join(" | ") : ""));
  await page.close();
}

async function fullFlow(browser) {
  console.log(`\n== full session (${DEMO ? "demo" : "research"} mode)`);
  const page = await openStart(browser, { width: 1280, height: 800 });
  const healthOk = await page.$eval("#llm-health", (el) => el.classList.contains("ok"));
  check((await page.textContent("#llm-health")).trim().length > 0, "health line rendered");
  await shot(page, "start");

  const posted = [];
  page.on("request", (r) => {
    if (r.url().endsWith("/api/data")) posted.push(r.url());
  });
  page.on("response", async (r) => {
    if (r.url().endsWith("/api/data") && r.ok()) savedFiles = (await r.json()).files;
  });
  page.on("dialog", (d) => d.accept(EXPERIMENTER_LINE));

  check(DEMO === await page.isVisible("#demo-badge"),
        "the demo's badge shows only in the demo");
  if (DEMO) {
    check((await page.textContent("#demo-badge")) === TXT.demo.badge
          && (await page.textContent("#demo-note")) === TXT.demo.start_note,
          "the demo says the session is saved and who can see it");
  }
  check(!DEMO === await page.isVisible("input[name=age]"),
        "the experimenter's fields show only outside the demo");
  check(!DEMO === await page.isVisible("#llm-health"),
        "the LLM pre-flight line shows only outside the demo");

  const assigned = await page.evaluate(() => {
    const seq = {}, combos = new Set();
    for (let n = 1; n <= 150; n++) {
      const a = assignedRows(String(n));
      seq[a.sequence] = (seq[a.sequence] || 0) + 1;
      if (n <= 16) combos.add(a.sequence + "/" + a.domain_sequence);
    }
    return { seq, combos: combos.size, p7: assignedRows("P007") };
  });
  check(JSON.stringify(Object.values(assigned.seq)) === "[38,38,37,37]",
        "150 participants split 38/38/37/37 over the sequences");
  check(assigned.combos === 16, "16 participants cover all 16 sequence × domain rows");
  check(assigned.p7.sequence === 3 && assigned.p7.domain_sequence === 2,
        "the rows come from the number in the id (P007 -> 3, 2)");

  await begin(page, { testMode: true });

  const screens = [];      // signatures in order of appearance
  const chats = [];        // what each chat ended up showing
  const shotTaken = new Set();
  let usedHotkey = false;
  const fallbackBanners = new Set();
  let lastSignature = "";

  for (let i = 0; i < 1200; i++) {
    await page.waitForTimeout(150);
    const kind = await classify(page);
    const text = await targetText(page);
    // A chat is one screen however its text changes; the rest differ by text.
    const signature = kind === "chat" ? kind : kind + "|" + text;

    if (signature !== lastSignature) {
      lastSignature = signature;
      screens.push({ kind, text });
      if (!shotTaken.has(kind) && kind !== "blank" && kind !== "none") {
        await shot(page, kind);
        shotTaken.add(kind);
      }
      if (kind === "chat") chats.push({});
    }
    if (kind === "saved" || kind === "demo-end") break;

    if (kind === "chat") {
      const state = await page.evaluate(() => {
        const bubbles = [...document.querySelectorAll(".chat-messages .bubble")];
        const box = document.querySelector("#chat-text");
        return {
          label: document.querySelector(".chat-name").textContent,
          authors: bubbles.map((b) => (b.classList.contains("agent") ? "A" : "P")).join(""),
          lines: bubbles.map((b) => b.textContent),
          inputOpen: !box.disabled,
          continueShown: !document.querySelector("#chat-continue").hidden,
          banner: (document.querySelector(".fallback-banner:not([hidden])") || {}).textContent,
        };
      });
      Object.assign(chats[chats.length - 1], state);
      if (state.banner) fallbackBanners.add(state.banner);

      if (state.inputOpen) {
        // Round 2 of the first chat goes through the experimenter hotkey.
        if (chats.length === 1 && !usedHotkey && state.authors === "APA") {
          await page.keyboard.press("Control+Shift+E");
          usedHotkey = true;
        }
        await page.fill("#chat-text", "Me sentí muy mal con lo que pasó, y todavía me pesa.");
        await page.keyboard.press("Enter");
        continue;
      }
      if (state.continueShown) {
        await page.click("#chat-continue");
        continue;
      }
    }
    if (kind === "chat") {
      // In test mode F9 cuts the wait; in the demo it would end the conversation.
      if (!DEMO) await page.keyboard.press("F9");
      continue;
    }
    if (!(await answerScreen(page, kind))) await skipOutsideChat(page);
  }

  const final = screens[screens.length - 1].kind;
  check(final === (DEMO ? "demo-end" : "saved"), `reached the last screen (${final})`);
  check(posted.length === 1, "the session was sent to /api/data once");
  check(savedFiles.length === 4, "four files saved");
  if (DEMO) {
    check(screens[screens.length - 1].text.includes(TXT.demo.end_body),
          "the demo's last screen says the answers were saved");
  }

  const kinds = screens.map((s) => s.kind).filter((k) => k !== "blank");
  const firstIndex = (k) => kinds.indexOf(k);
  const inOrder = ["consent", "rest", "instrument", "elicitation-intro",
                   "instructions", "announcement", "chat", "final-intro",
                   "debriefing", "data-use"]
    .map(firstIndex);
  check(inOrder.every((v, i) => v >= 0 && (i === 0 || v > inOrder[i - 1])),
        "session order: consent, rest, baseline, elicitation, episodes, final block, debriefing");

  check(chats.length === 4, `four chat episodes (got ${chats.length})`);
  for (const [i, chat] of chats.entries()) {
    check(chat.authors === "APAPAPA",
          `chat ${i + 1}: opening, then three rounds (got ${chat.authors})`);
    check([TXT.interlocutor_label.human, TXT.interlocutor_label.ai].includes(chat.label),
          `chat ${i + 1}: header shows the label`);
  }

  const announcements = screens.filter((s) => s.kind === "announcement");
  check(announcements.length === 4, "an announcement before each episode");
  const said = announcements.map((a) =>
    a.text.includes(TXT.agent_announcement.human) ? "human"
      : a.text.includes(TXT.agent_announcement.ai) ? "ai" : "?");
  check(said.filter((s) => s === "human").length === 2
        && said.filter((s) => s === "ai").length === 2,
        `two announced as a person, two as an AI (got ${said})`);
  for (const [i, chat] of chats.entries()) {
    check(chat.label === TXT.interlocutor_label[said[i]],
          `chat ${i + 1}: the label matches what was announced`);
  }
  check(announcements.every((a, i) =>
    a.text.includes(TXT.demo.human_note) === (DEMO && said[i] === "human")),
        "only the demo's human announcements say the model answers");

  const domains = PROTOCOL.domains.map((d) => d.label);
  const openings = chats.map((c) => (c.lines || [""])[0]);
  check(domains.every((d) => openings.some((o) => o.includes(d))),
        "each episode opens on a different domain");

  check(chats[0].lines.includes(EXPERIMENTER_LINE),
        "the experimenter's message appeared as the next agent turn");

  // Measures after the first episode, in the order of the spec.
  const firstChat = screens.findIndex((s) => s.kind === "chat");
  const after = screens.slice(firstChat + 1);
  const end = after.findIndex((s) => s.kind === "pause");
  const block = after.slice(0, end).filter((s) => s.kind !== "blank");
  const sc = PROTOCOL.scales;
  const expected = [
    ...Array(2).fill("panas"),
    sc.sam_valence.prompt, sc.sam_arousal.prompt, sc.suds.prompt,
    ...sc.authenticity.items.map((it) => it.prompt),
    ...sc.manipulation_check.items.map((it) => it.prompt),
    sc.naturalness.prompt,
  ];
  const got = block.map((s) => (s.kind === "panas" ? "panas" : s.text));
  const matches = expected.length === got.length
    && expected.every((e, i) => got[i].startsWith(e));
  check(matches, "post-episode order: PANAS, SAM, SUDS, authenticity, checks, naturalness"
    + (matches ? "" : ` (got ${JSON.stringify(got.map((g) => g.slice(0, 30)))})`));

  // Final block: credibility per episode first, the open questions after.
  const finalIntro = screens.findIndex((s) => s.kind === "final-intro");
  const debrief = screens.findIndex((s) => s.kind === "debriefing");
  const finalBlock = screens.slice(finalIntro + 1, debrief).filter((s) => s.kind !== "blank");
  check(finalBlock.slice(0, 4).every((s) => s.kind === "slider"),
        "the final block starts with the four credibility scales");
  check(domains.every((d) => finalBlock.slice(0, 4).some((s) => s.text.includes(d))),
        "each credibility scale names a domain");
  check(finalBlock.slice(4, 9).length === 5 && finalBlock.slice(4, 9).every((s) => s.kind === "text-question"),
        "then the suspicion question and one open question per interlocutor");
  check(finalBlock[4].text.includes("autenticidad"), "suspicion comes before the per-interlocutor question");

  const identity = /(persona|inteligencia artificial|con quién)/i;
  const beforeFinal = screens.slice(0, finalIntro)
    .filter((s) => s.kind === "slider" || s.kind === "panas");
  check(!beforeFinal.some((s) => identity.test(s.text)
                                 && !s.text.includes("compañeros de inteligencia artificial")
                                 && !s.text.includes("Alex")),
        "no scale before the final block asks about the interlocutor's identity");

  const debriefing = screens.find((s) => s.kind === "debriefing").text;
  check(debriefing.includes("persona del equipo de investigación"),
        "the debriefing reveals the person behind the human label");
  check(!debriefing.includes("modelo de lenguaje"),
        "the debriefing does not say a model replaced the person");

  if (healthOk) {
    check(fallbackBanners.size === 0, "no fallback banner while the LLM is reachable"
      + (fallbackBanners.size ? ": " + [...fallbackBanners].join(" | ") : ""));
  } else {
    console.log("  note LLM not reachable during this run; fallback banners expected");
  }
  check(page.errors.length === 0, "no JS errors" + (page.errors.length ? ": " + page.errors.join(" | ") : ""));
  await page.close();
}

async function elicitationFlow(browser) {
  console.log("\n== by hand: distress alert and one real chat message");
  const page = await openStart(browser, { width: 1440, height: 900 });
  // The research mode has no Saltar outside test mode.
  await begin(page, { testMode: !DEMO });

  const untilKind = async (wanted) => {
    for (let i = 0; i < 200; i++) {
      const kind = await classify(page);
      if (kind === wanted) return true;
      await skipOutsideChat(page);
      await page.waitForTimeout(100);
    }
    return false;
  };
  const answerText = async (text) => {
    await page.fill("textarea", text);
    await page.click("#jspsych-survey-text-next");
    await page.waitForTimeout(150);
  };
  const answerSlider = async (value) => {
    await page.evaluate((v) => {
      const el = document.querySelector("input[type=range]");
      el.value = v;
      el.dispatchEvent(new Event("change"));
    }, value);
    await page.click("#jspsych-html-slider-response-next");
    await page.waitForTimeout(150);
  };

  check(await untilKind("elicitation-intro"), "reached the elicitation");
  await page.keyboard.press("F9");
  await page.waitForTimeout(150);

  const firstPrompt = await targetText(page);
  check(firstPrompt.includes(PROTOCOL.domains[0].label), "the first prompt names the first domain");
  await answerText("Primera versión de la situación.");
  await answerSlider(9);
  check(await classify(page) === "distress-alert", "a rating of 9 triggers the alert");
  await shot(page, "distress-alert");
  await page.click(`button:has-text("${TXT.distress_alert.replace}")`);
  await page.waitForTimeout(150);

  const again = await targetText(page);
  check(again.includes(PROTOCOL.domains[0].label), "replacing asks again for the same domain");
  await answerText("Segunda versión de la situación.");
  await answerSlider(3);
  check((await targetText(page)).includes(PROTOCOL.domains[1].label),
        "a rating of 3 moves on to the next domain with no alert");

  const situationOf = { [PROTOCOL.domains[0].label]: "Segunda versión de la situación." };
  for (const domain of PROTOCOL.domains.slice(1)) {
    situationOf[domain.label] = `Lo que me pasó con ${domain.label}.`;
    await answerText(situationOf[domain.label]);
    await answerSlider(3);
  }

  /* Waits for the box to open, and checks it holds this domain's situation. */
  const checkPrefilled = async () => {
    await page.waitForFunction(
      () => !document.querySelector("#chat-text").disabled, null, { timeout: 30000 });
    const opening = await page.$eval(".chat-messages .bubble.agent", (b) => b.textContent);
    const label = Object.keys(situationOf).find((l) => opening.includes(l));
    check(await page.inputValue("#chat-text") === situationOf[label],
          `the first message box holds the situation about ${label}`);
    check((await page.$$(".chat-messages .bubble.participant")).length === 0,
          "the situation is not sent until the participant sends it");
  };

  check(await untilKind("chat"), "reached the first chat");
  await checkPrefilled();
  await shot(page, "chat-prefilled");
  await page.fill("#chat-text", "En el trabajo me dejaron afuera de un proyecto y me sentí invisible.");
  await page.keyboard.press("Enter");
  await page.waitForFunction(
    () => document.querySelectorAll(".chat-messages .bubble.agent").length === 2,
    null, { timeout: 60000 });
  const reply = await page.$$eval(".chat-messages .bubble.agent", (b) => b[1].textContent);
  check(reply.length > 0 && reply.length <= PROTOCOL.prompts.max_chars,
        `the agent answered within the cap: «${reply}»`);
  const sent = await page.$eval(".chat-messages .bubble.participant", (b) => b.textContent);
  check(sent.startsWith("En el trabajo"), "an edited situation is sent as edited");
  await shot(page, "chat-reply");
  if (DEMO) {
    // The other three chats, which include the replaced situation's domain.
    for (let i = 0; i < 3; i++) {
      await page.keyboard.press("F9");
      check(await untilKind("chat"), `reached chat ${i + 2}`);
      await checkPrefilled();
    }
  }
  check(page.errors.length === 0, "no JS errors" + (page.errors.length ? ": " + page.errors.join(" | ") : ""));
  await page.close();
}

const codeRequired = !(await postCheckCode(""));
if (codeRequired && !(await postCheckCode(CODE))) {
  console.error("This server requires an access code: pass the right one with --code.");
  process.exit(2);
}

const browser = await chromium.launch();
try {
  if (codeRequired) await accessCodeFlow(browser);
  await fullFlow(browser);
  await elicitationFlow(browser);
  if (DEMO) await skipChatFlow(browser);
  await withdrawFlow(browser);
  if (ADMIN) await adminFlow(browser);
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
