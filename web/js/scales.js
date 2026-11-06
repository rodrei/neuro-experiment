/* Text screens and self-report scales.
 *
 * Everything comes from protocol/scales.json and protocol/texts.json: there are
 * no hand-written prompts or anchors here.
 *
 * TRAP: an <input type="range"> ALWAYS has a value. Without require_movement,
 * whoever does not touch the control "answers" the midpoint and it is
 * recorded as valid data. */

function textScreen(title, body, buttonLabel) {
  return {
    type: jsPsychHtmlButtonResponse,
    stimulus: () =>
      (title ? `<div class="screen-title">${title}</div>` : "") +
      `<div class="screen-body">${body}</div>`,
    choices: [buttonLabel || "Continuar"],
  };
}

function lineBreaks(text) {
  return String(text).replace(/\n/g, "<br>");
}

/* One slider scale. `spec` comes from protocol/scales.json. */
function sliderScale(spec, key) {
  const ticks = spec.ticks;
  const step = ticks.length > 1 ? ticks[1] - ticks[0] : 1;
  return {
    type: jsPsychHtmlSliderResponse,
    stimulus: `<p class="prompt">${spec.prompt}</p>`,
    labels: spec.labels.map(lineBreaks),
    min: ticks[0],
    max: ticks[ticks.length - 1],
    step: step,
    slider_start: ticks[Math.floor(ticks.length / 2)],
    slider_width: 600,
    require_movement: true,
    button_label: "Continuar",
    data: { key: key },
  };
}

/* One sliderScale per item of a block that shares its ticks and labels. */
function itemScales(block, moment) {
  return block.items.map((item) => sliderScale(
    { prompt: item.prompt, ticks: block.ticks, labels: block.labels },
    moment + "_" + item.key));
}

/* Baseline: the AI companion use items. There is no interlocutor to rate yet. */
function baselineMeasures() {
  return window.PROTOCOL.scales.ai_use.items.map(
    (item) => sliderScale(item, "baseline_" + item.key));
}

/* After each episode: SAM, SUDS, authenticity, the six manipulation checks and
 * naturalness. Nothing here names the interlocutor's identity: asking about it
 * now would announce from the first episode that it is in question. */
function episodeMeasures(moment) {
  const sc = window.PROTOCOL.scales;
  return [
    sliderScale(sc.sam_valence, moment + "_sam_valence"),
    sliderScale(sc.sam_arousal, moment + "_sam_arousal"),
    sliderScale(sc.suds, moment + "_suds"),
    ...itemScales(sc.authenticity, moment),
    ...itemScales(sc.manipulation_check, moment),
    sliderScale(sc.naturalness, moment + "_naturalness"),
  ];
}

/* An open question whose answer is kept verbatim in `answers[key]`. */
function openQuestion(prompt, key, answers, required) {
  return {
    type: jsPsychSurveyText,
    questions: [{ prompt: prompt, name: "answer", rows: 7, columns: 70,
                  required: !!required }],
    button_label: "Continuar",
    on_finish: (d) => {
      answers[key] = valueOrNull(d.response && d.response.answer);
    },
  };
}

/* Absent answer (screen skipped) -> null. With undefined, JSON.stringify drops
 * the key and the row disappears from the CSV instead of staying empty. */
function valueOrNull(value) {
  return value === undefined ? null : value;
}

/* Collects the answers of one moment from jsPsych's data. */
function collectMeasures(jsPsych, moment) {
  const out = {};

  jsPsych.data.get().filter({ trial_type: "html-slider-response" }).values()
    .forEach((row) => {
      if (row.key && row.key.startsWith(moment + "_")) {
        out[row.key.slice(moment.length + 1)] = valueOrNull(row.response);
      }
    });

  // Authenticity mean, only when every item was answered, so a partial mean is
  // never later read as valid.
  const authKeys = window.PROTOCOL.scales.authenticity.items.map((it) => it.key);
  if (authKeys.some((k) => k in out)) {
    const values = authKeys.map((k) => out[k]);
    const incomplete = values.some((v) => v === null || v === undefined);
    out.auth_mean = incomplete
      ? null : Number((values.reduce((a, b) => a + b, 0) / values.length).toFixed(3));
  }

  return out;
}
