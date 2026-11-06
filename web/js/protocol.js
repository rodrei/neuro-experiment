/* Protocol loading.
 *
 * The browser does NOT parse protocol/: it receives it already built by
 * common.protocol.everything(), plus the server's demo_mode.
 *
 * Mind the fallback lines: after JSON the turn keys, which are integers in
 * Python, arrive as strings ("1", "2", "3"). */

window.PROTOCOL = null;

async function loadProtocol() {
  const resp = await fetch("/api/protocol");
  if (!resp.ok) {
    throw new Error("the server did not return the protocol (" + resp.status + ")");
  }
  window.PROTOCOL = await resp.json();
  return window.PROTOCOL;
}

function isDemo() {
  return window.PROTOCOL.demo_mode;
}

function parameters() {
  return window.PROTOCOL.parameters[isDemo() ? "demo" : "real"];
}

function texts() {
  return window.PROTOCOL.texts;
}

/* The fixed line shown when an LLM turn fails. `round` is a number; the keys
 * come as strings. */
function fallbackLine(feedback, round) {
  const block = window.PROTOCOL.fallback[feedback] || {};
  return block[String(round)] || "";
}

/* Fills the {domain}, {title}, ... placeholders of a protocol text. */
function fill(template, values) {
  return String(template).replace(/\{(\w+)\}/g, (m, key) =>
    key in values ? values[key] : m);
}
