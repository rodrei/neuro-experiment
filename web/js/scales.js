/* Text screens and self-report scales.
 *
 * Everything comes from protocol/scales.json and protocol/texts.json: there
 * are no hand-written prompts or anchors here.
 *
 * TRAP: an <input type="range"> ALWAYS has a value. Without require_movement,
 * whoever does not touch the control "answers" the midpoint and it is
 * recorded as valid data. It is the browser equivalent of the style="radio"
 * trap already documented for PsychoPy. */

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

/* Likert / SAM / SUDS style scale. `spec` comes from protocol/scales.json. */
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

/* PANAS as a grid, in pages of 10. It is 20 items and several
 * administrations: one per screen would stretch the interval between
 * episodes so much that the activation would dissipate before the next. */
function panasTrials(moment) {
  const cfg = window.PROTOCOL.scales.panas;
  const items = window.PROTOCOL.panas;
  const perPage = cfg.items_per_page;
  const anchors = cfg.anchors.map(lineBreaks);
  const trials = [];

  for (let i = 0; i < items.length; i += perPage) {
    const page = items.slice(i, i + perPage);
    trials.push({
      type: jsPsychSurveyLikert,
      preamble: `<p class="prompt">${cfg.instruction}</p>`,
      questions: page.map((it) => ({
        prompt: it.item,
        labels: anchors,
        required: true,
      })),
      button_label: "Continuar",
      data: {
        block: "panas",
        moment: moment,
        keys: page.map((it) => it.key),
      },
    });
  }
  return trials;
}

/* Measures block, in the fixed order SUDS -> SAM -> authenticity -> PANAS.
 *
 * At BASELINE it goes without authenticity: there is no interlocutor to rate
 * yet. */
function measuresBlock(moment, includeAuthenticity, mark) {
  const sc = window.PROTOCOL.scales;
  const trials = [];

  trials.push(sliderScale(sc.suds, moment + "_suds"));
  trials.push(sliderScale(sc.sam_valence, moment + "_sam_valence"));
  trials.push(sliderScale(sc.sam_arousal, moment + "_sam_arousal"));

  if (includeAuthenticity) {
    const auth = sc.authenticity;
    for (const item of auth.items) {
      trials.push(sliderScale(
        { prompt: item.prompt, ticks: auth.ticks, labels: auth.labels },
        moment + "_" + item.key));
    }
  }

  // The PANAS goes last on purpose: SUDS and SAM are the time-sensitive
  // measures and have to be taken as soon as the episode ends.
  if (mark) trials.push(mark("panas_start", moment));
  for (const t of panasTrials(moment)) trials.push(t);
  if (mark) trials.push(mark("panas_end", moment));

  return trials;
}

/* Absent answer (screen skipped in test mode) -> null. With undefined,
 * JSON.stringify drops the key and the row disappears from the CSV instead
 * of staying empty, as it does on the desktop. */
function valueOrNull(value) {
  return value === undefined ? null : value;
}

/* Collects the answers of one moment from jsPsych's data.
 * The PA/NA totals follow the same rule as the desktop: an incomplete
 * subscale has NO total, so a partial total is never later read as valid. */
function collectMeasures(jsPsych, moment) {
  const out = {};

  jsPsych.data.get().filter({ trial_type: "html-slider-response" }).values()
    .forEach((row) => {
      if (row.key && row.key.startsWith(moment + "_")) {
        out[row.key.slice(moment.length + 1)] = valueOrNull(row.response);
      }
    });

  const items = window.PROTOCOL.panas;
  const byKey = {};
  jsPsych.data.get().filter({ block: "panas", moment: moment }).values()
    .forEach((row) => {
      const resp = row.response || {};      // skipped page: no response
      row.keys.forEach((key, i) => {
        const value = resp["Q" + i];
        // survey-likert returns the index (0..4); the protocol uses 1..5.
        byKey[key] = value === null || value === undefined ? null : value + 1;
      });
    });
  Object.assign(out, byKey);

  for (const sub of ["PA", "NA"]) {
    const values = items.filter((it) => it.subscale === sub)
      .map((it) => byKey[it.key]);
    const incomplete = values.some((v) => v === null || v === undefined);
    out[sub + "_total"] = incomplete ? null : values.reduce((a, b) => a + b, 0);
  }

  // Authenticity mean, only when every item was answered (same rule).
  const authKeys = window.PROTOCOL.scales.authenticity.items.map((it) => it.key);
  if (authKeys.some((k) => k in out)) {
    const values = authKeys.map((k) => out[k]);
    const incomplete = values.some((v) => v === null || v === undefined);
    out.auth_mean = incomplete
      ? null : Number((values.reduce((a, b) => a + b, 0) / values.length).toFixed(3));
  }

  return out;
}
