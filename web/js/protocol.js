/* Protocol loading.
 *
 * The browser does NOT parse protocol/: it receives it already built by
 * common.protocol.everything(). That way the demo and the desktop read the
 * same content with the same Python code.
 *
 * Mind the scripts: after JSON the turn keys, which are integers in Python,
 * arrive as strings ("1", "2", "3"). */

window.PROTOCOL = null;

async function loadProtocol() {
  const resp = await fetch("/api/protocol");
  if (!resp.ok) {
    throw new Error("the server did not return the protocol (" + resp.status + ")");
  }
  window.PROTOCOL = await resp.json();
  return window.PROTOCOL;
}

/* The demo always runs with the short timings: the 5-minute baseline makes
 * no sense in front of a class, and without EDA it has no function either. */
function parameters() {
  return window.PROTOCOL.parameters.demo;
}

function texts() {
  return window.PROTOCOL.texts;
}

/* The scripted line of a turn. `turn` is a number; the keys come as strings. */
function scriptLine(feedback, turn) {
  const block = window.PROTOCOL.scripts[feedback] || {};
  return block[String(turn)] || "";
}
