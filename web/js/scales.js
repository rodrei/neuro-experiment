/* Text screens and self-report scales.
 *
 * Everything comes from protocol/scales.json, protocol/instruments.json and
 * protocol/texts.json: there are no hand-written prompts or anchors here.
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

/* One sliderScale per item of a block that shares its ticks and labels. */
function itemScales(block, moment) {
  return block.items.map((item) => sliderScale(
    { prompt: item.prompt, ticks: block.ticks, labels: block.labels },
    moment + "_" + item.key));
}

/* A grid questionnaire, in pages. With 20 or more items, one per screen would
 * stretch the interval between episodes so much that the activation would
 * dissipate before the next. */
function likertPages(cfg, items, block, moment) {
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
        block: block,
        moment: moment,
        keys: page.map((it) => it.key),
      },
    });
  }
  return trials;
}

function panasTrials(moment) {
  return likertPages(window.PROTOCOL.scales.panas, window.PROTOCOL.panas,
                     "panas", moment);
}

/* UCLA-3 or ECR: its items, or a screen naming it while their wording is
 * pending. */
function instrumentTrials(name, moment) {
  const cfg = window.PROTOCOL.instruments[name];
  if (cfg.items.length === 0) {
    return [textScreen(null, fill(texts().instrument_pending,
                                  { title: cfg.title, n: cfg.n_items }))];
  }
  return likertPages(cfg, cfg.items, name, moment);
}

/* Baseline: UCLA-3, ECR, the AI companion use items and PANAS. There is no
 * interlocutor to rate yet. */
function baselineMeasures(mark) {
  const moment = "baseline";
  const trials = [
    ...instrumentTrials("ucla3", moment),
    ...instrumentTrials("ecr", moment),
  ];
  for (const item of window.PROTOCOL.scales.ai_use.items) {
    trials.push(sliderScale(item, moment + "_" + item.key));
  }
  trials.push(mark("panas_start", moment));
  trials.push(...panasTrials(moment));
  trials.push(mark("panas_end", moment));
  return trials;
}

/* After each episode: PANAS, SAM, SUDS, authenticity, the four manipulation
 * checks and naturalness. Nothing here names the interlocutor's identity:
 * asking about it now would announce from the first episode that it is in
 * question. */
function episodeMeasures(moment, mark) {
  const sc = window.PROTOCOL.scales;
  return [
    mark("panas_start", moment),
    ...panasTrials(moment),
    mark("panas_end", moment),
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

/* Collects the answers of one moment from jsPsych's data.
 * An incomplete PA/NA subscale has NO total, so a partial total is never
 * later read as valid. */
function collectMeasures(jsPsych, moment) {
  const out = {};

  jsPsych.data.get().filter({ trial_type: "html-slider-response" }).values()
    .forEach((row) => {
      if (row.key && row.key.startsWith(moment + "_")) {
        out[row.key.slice(moment.length + 1)] = valueOrNull(row.response);
      }
    });

  // Grid questionnaires. survey-likert returns the index; PANAS scores from 1.
  const panasValues = {};
  jsPsych.data.get().filter({ moment: moment }).values()
    .filter((row) => row.block)
    .forEach((row) => {
      const resp = row.response || {};      // skipped page: no response
      row.keys.forEach((key, i) => {
        const value = resp["Q" + i];
        const score = value === null || value === undefined ? null : value + 1;
        out[key] = score;
        if (row.block === "panas") panasValues[key] = score;
      });
    });

  if (Object.keys(panasValues).length > 0) {
    for (const sub of ["PA", "NA"]) {
      const values = window.PROTOCOL.panas.filter((it) => it.subscale === sub)
        .map((it) => panasValues[it.key]);
      const incomplete = values.some((v) => v === null || v === undefined);
      out[sub + "_total"] = incomplete ? null : values.reduce((a, b) => a + b, 0);
    }
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
