/* The timeline of the study (2x2 within-subject).
 *
 * start form -> consent -> rest baseline -> baseline questionnaires -> the four
 * situations, each with its 0-10 rating -> 4 episodes, each: SUDS ->
 * announcement -> connecting -> chat -> measures (-> pause) -> credibility and
 * open questions -> debriefing -> data use -> close -> submission.
 *
 * The order of the four conditions comes from protocol/sequences.json and the
 * domain of each condition from protocol/domain_sequences.json, two Latin
 * squares indexed by the rows chosen on the start form.
 *
 * In demo mode the server stores nothing: the page says so, and the submission
 * is replaced by a closing screen. */

let SESSION_CONFIG = null;

document.addEventListener("DOMContentLoaded", async () => {
  const status = document.getElementById("load-status");
  const button = document.getElementById("begin");
  const idField = document.querySelector("input[name=participant_id]");
  const sequenceSelect = document.getElementById("sequence");
  const domainSelect = document.getElementById("domain_sequence");
  button.disabled = true;

  for (const select of [sequenceSelect, domainSelect]) {
    for (let i = 1; i <= 4; i++) {
      const option = document.createElement("option");
      option.value = String(i);
      option.textContent = String(i);
      select.appendChild(option);
    }
  }

  // Rows suggested from the id, so the 16 row combinations spread over
  // participants without anyone thinking about it. A row stops following the
  // id once the experimenter picks one by hand.
  const touched = { sequence: false, domain: false };
  const suggest = () => {
    const rows = assignedRows(idField.value);
    if (!touched.sequence) sequenceSelect.value = String(rows.sequence);
    if (!touched.domain) domainSelect.value = String(rows.domain_sequence);
  };
  idField.addEventListener("input", suggest);
  sequenceSelect.addEventListener("change", () => { touched.sequence = true; });
  domainSelect.addEventListener("change", () => { touched.domain = true; });
  suggest();

  try {
    await loadProtocol();
    status.textContent = "Protocolo cargado.";
    button.disabled = false;
  } catch (e) {
    status.textContent = "No se pudo cargar el protocolo: " + e.message;
    return;
  }

  if (isDemo()) applyDemoMode(sequenceSelect, domainSelect);

  checkHealth(false);
  document.getElementById("llm-retry").addEventListener("click", (e) => {
    e.preventDefault();
    checkHealth(true);
  });

  document.getElementById("form").addEventListener("submit", (e) => {
    e.preventDefault();
    const data = new FormData(e.target);
    SESSION_CONFIG = Object.fromEntries(data.entries());
    SESSION_CONFIG.sequence = parseInt(SESSION_CONFIG.sequence, 10);
    SESSION_CONFIG.domain_sequence = parseInt(SESSION_CONFIG.domain_sequence, 10);
    // An unchecked checkbox is not in the FormData.
    SESSION_CONFIG.test_mode = data.get("test_mode") === "1";
    document.getElementById("start").style.display = "none";
    document.getElementById("jspsych-target").classList.add("active");
    runExperiment();
  });
});

/* Which rows of the two Latin squares a participant gets, from the number in
 * their id: the sequence cycles every participant and the domain row every
 * four, so the two squares cross independently. */
function assignedRows(id) {
  const digits = String(id || "").match(/\d+/);
  const n = digits
    ? parseInt(digits[0], 10)
    : Array.from(String(id || "")).reduce((a, c) => a + c.charCodeAt(0), 1);
  const index = Math.max(n - 1, 0);
  return { sequence: index % 4 + 1,
           domain_sequence: Math.floor(index / 4) % 4 + 1 };
}

/* The hosted walkthrough: a notice that nothing is recorded, no experimenter
 * fields, and any row of the squares. */
function applyDemoMode(sequenceSelect, domainSelect) {
  document.body.classList.add("demo");
  const badge = document.getElementById("demo-badge");
  badge.textContent = texts().demo.badge;
  badge.hidden = false;
  const note = document.getElementById("demo-note");
  note.textContent = texts().demo.start_note;
  note.hidden = false;
  const randomRow = () => String(Math.floor(Math.random() * 4) + 1);
  sequenceSelect.value = randomRow();
  domainSelect.value = randomRow();
}

/* Pre-flight: is the LLM going to answer? Shown under the start form so a
 * dead key or an unreachable API is known before the session, not after. */
async function checkHealth(refresh) {
  const el = document.getElementById("llm-health");
  el.className = "health pending";
  el.textContent = "Comprobando el LLM…";
  try {
    const resp = await fetch("/api/health" + (refresh ? "?refresh=1" : ""));
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const llm = (await resp.json()).llm;
    if (llm.reachable) {
      el.className = "health ok";
      el.textContent = `LLM listo: ${llm.model} respondió en ${llm.latency_s.toFixed(1)} s (key: ${llm.key_source})`;
    } else {
      el.className = "health error";
      el.textContent = llm.key_found
        ? `LLM no disponible: ${llm.error}`
        : "LLM no disponible: no hay API key (OPENROUTER_API_KEY u openrouter_key.txt). Los turnos van a salir de las líneas fijas.";
    }
  } catch (e) {
    el.className = "health error";
    el.textContent = "No se pudo consultar /api/health: " + e.message;
  }
}

function runExperiment() {
  const p = parameters();
  const txt = texts();
  const sc = window.PROTOCOL.scales;
  const cfg = SESSION_CONFIG;
  const events = [];
  const t0 = performance.now();
  window.EXPERIMENT_T0 = t0;      // the chat plugin stamps with the same clock

  function record(label, detail) {
    events.push({
      t_experiment_s: Number(((performance.now() - t0) / 1000).toFixed(4)),
      t_unix: Date.now() / 1000,
      code: window.PROTOCOL.markers[label] || 0,
      label: label,
      detail: detail || "",
    });
  }

  const session = {
    plan: [],           // one entry per episode; read by submit()
    situations: {},     // domain id -> {text, pre_rating, discarded, ...}
    answers: {},        // open questions, verbatim
    withdrawn: false,
  };

  const jsPsych = initJsPsych({
    display_element: "jspsych-target",
    on_finish: () => submit(jsPsych, events, session),
  });

  if (cfg.test_mode || isDemo()) enableSkip(jsPsych);
  if (cfg.test_mode) document.body.classList.add("test-mode");

  const mark = (label, detail) => ({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: "",
    choices: "NO_KEYS",
    trial_duration: 0,
    on_finish: () => record(label, detail),
  });

  const timeline = [];

  timeline.push(mark("experiment_start",
                     "seq" + cfg.sequence + "_dom" + cfg.domain_sequence));

  // Consent, with the stated purpose of the study.
  timeline.push(textScreen(txt.consent.title, txt.consent.body));

  // Resting baseline: fixation cross.
  timeline.push(textScreen(txt.rest.title, txt.rest.body));
  timeline.push(mark("baseline_start"));
  timeline.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: `<div class="fixation-cross">+</div>
               <div class="rest-caption">${txt.rest_caption}</div>`,
    choices: "NO_KEYS",
    trial_duration: p.baseline_duration * 1000,
    data: { screen: "rest" },
  });
  timeline.push(mark("baseline_end"));

  timeline.push(mark("measures_start", "baseline"));
  timeline.push(...baselineMeasures(mark));
  timeline.push(mark("measures_end", "baseline"));

  // The four situations, all before any feedback.
  timeline.push(textScreen(txt.elicitation.title, txt.elicitation.body));
  for (const domain of window.PROTOCOL.domains) {
    timeline.push(elicitationNode(domain, session, p, txt, sc, mark, record));
  }

  timeline.push(textScreen(txt.instructions.title, txt.instructions.body));

  // The four episodes, in the order of the Latin square row.
  const sequence = window.PROTOCOL.sequences[String(cfg.sequence)];
  const domainOf = window.PROTOCOL.domain_sequences[String(cfg.domain_sequence)];

  sequence.forEach((condition, i) => {
    const episode = i + 1;
    const [agentType, feedback] = condition.split("_");
    const moment = "ep" + episode;
    const domain = window.PROTOCOL.domains.find((d) => d.id === domainOf[condition]);
    session.plan.push({ episode, condition, agent_type: agentType, feedback, domain });

    timeline.push(sliderScale(sc.suds, moment + "_pre_suds"));

    timeline.push(mark("agent_announcement", episode + "_" + condition));
    timeline.push(Object.assign(
      textScreen(txt.agent_announcement.title, txt.agent_announcement[agentType]),
      { data: { screen: "announcement" } }));

    timeline.push({
      type: jsPsychHtmlKeyboardResponse,
      stimulus: `<div class="rest-caption">${txt.connecting}</div>`,
      choices: "NO_KEYS",
      trial_duration: p.connecting_duration * 1000,
      data: { screen: "connecting" },
    });

    timeline.push({
      type: jsPsychChatEpisode,
      episode: episode,
      condition: condition,
      agent_type: agentType,
      feedback: feedback,
      domain: domain,
      label: txt.interlocutor_label[agentType],
      access_code: cfg.access_code || "",
      test_mode: cfg.test_mode,
    });

    timeline.push(mark("measures_start", moment + "_" + condition));
    timeline.push(...episodeMeasures(moment, mark));
    timeline.push(mark("measures_end", moment + "_" + condition));

    if (i < sequence.length - 1) {
      timeline.push(Object.assign(textScreen(txt.pause.title, txt.pause.body),
                                  { data: { screen: "pause" } }));
    }
  });

  // Final block: the direct questions about identity come only now, so they
  // cannot contaminate the episodes.
  timeline.push(mark("final_check_start"));
  timeline.push(textScreen(txt.final_check.title, txt.final_check.body));
  for (const entry of session.plan) {
    timeline.push(sliderScale(
      Object.assign({}, sc.credibility,
                    { prompt: fill(sc.credibility.prompt, { domain: entry.domain.label }) }),
      "ep" + entry.episode + "_credibility"));
  }
  timeline.push(openQuestion(txt.final_check.suspicion, "suspicion", session.answers));
  for (const entry of session.plan) {
    timeline.push(openQuestion(
      fill(txt.final_check.stood_out, { domain: entry.domain.label }),
      "ep" + entry.episode + "_stood_out", session.answers));
  }
  timeline.push(mark("final_check_end"));

  timeline.push(mark("debriefing_start"));
  timeline.push(Object.assign(
    textScreen(txt.debriefing.title, txt.debriefing.body),
    { data: { screen: "debriefing" } }));

  timeline.push({
    type: jsPsychHtmlButtonResponse,
    stimulus: `<div class="screen-title">${txt.data_use.title}</div>
               <div class="screen-body">${txt.data_use.body}</div>`,
    choices: [txt.data_use.keep, txt.data_use.withdraw],
    on_finish: (d) => { session.withdrawn = d.response === 1; },
  });

  timeline.push(Object.assign(textScreen(null, txt.closing.body, "Terminar"),
                              { data: { screen: "close" } }));
  timeline.push(mark("experiment_end"));

  jsPsych.run(timeline);
}

/* One domain: the text, its rating and, at the top of the scale, the alert that
 * lets the experimenter replace it. A replacement repeats the whole node. */
function elicitationNode(domain, session, p, txt, sc, mark, record) {
  const situation = { text: null, pre_rating: null, discarded: [], alerted: 0 };
  session.situations[domain.id] = situation;
  let replacing = false;

  const rating = sliderScale(sc.pre_rating, "situation_" + domain.id + "_pre_rating");
  rating.on_finish = (d) => {
    situation.pre_rating = valueOrNull(d.response);
    record("situation_end", domain.id + "_rating=" + situation.pre_rating);
  };

  const alert = {
    timeline: [{
      type: jsPsychHtmlButtonResponse,
      stimulus: `<div class="screen-title">${txt.distress_alert.title}</div>
                 <div class="screen-body">${txt.distress_alert.body}</div>`,
      choices: [txt.distress_alert.keep, txt.distress_alert.replace],
      on_start: () => {
        situation.alerted = 1;
        record("distress_alert", domain.id);
      },
      on_finish: (d) => {
        replacing = d.response === 1;
        if (replacing) {
          situation.discarded.push({ text: situation.text,
                                     pre_rating: situation.pre_rating });
          record("situation_replaced", domain.id);
        }
      },
    }],
    conditional_function: () =>
      situation.pre_rating !== null && situation.pre_rating >= p.distress_threshold,
  };

  return {
    timeline: [
      mark("situation_start", domain.id),
      openQuestionInto(fill(txt.elicitation.prompt, { domain: domain.label }), situation),
      rating,
      alert,
    ],
    loop_function: () => {
      const again = replacing;
      replacing = false;
      return again;
    },
  };
}

function openQuestionInto(prompt, situation) {
  return {
    type: jsPsychSurveyText,
    questions: [{ prompt: prompt, name: "answer", rows: 8, columns: 70, required: true }],
    button_label: "Continuar",
    on_finish: (d) => {
      situation.text = valueOrNull(d.response && d.response.answer);
    },
  };
}

/* The Saltar button and the F9 key. In the demo they let an evaluator pass the
 * questionnaires; in test mode they also cut the waits inside the chat.
 *
 * Whatever is skipped stays EMPTY in the CSVs (a skipped PANAS page leaves the
 * subscale without a total), and a test run is flagged with test_mode in
 * _responses.csv, so it is never confused with a real one. */
function enableSkip(jsPsych) {
  const button = document.getElementById("skip");
  button.hidden = false;

  function skip() {
    if (document.querySelector("#jspsych-target .chat")) {
      if (SESSION_CONFIG.test_mode) jsPsychChatEpisode.skip();
      return;
    }
    try {
      jsPsych.finishTrial({ skipped: true });
    } catch (e) {
      // Between two trials there is nothing to finish: the click is ignored.
    }
  }

  button.addEventListener("click", skip);
  document.addEventListener("keydown", (e) => {
    if (e.key === "F9") {
      e.preventDefault();
      skip();
    }
  });
}

function endScreen(title, body) {
  document.getElementById("skip").hidden = true;
  document.getElementById("jspsych-target").innerHTML =
    `<div class="end-screen"><div class="screen-title">${title}</div>
     <div class="screen-body">${body}</div></div>`;
}

/* Builds the four files and sends them to the server. */
async function submit(jsPsych, generalEvents, session) {
  const txt = texts();
  if (isDemo()) {
    endScreen(txt.demo.end_title, txt.demo.end_body);
    return;
  }
  if (session.withdrawn) {
    endScreen(txt.withdrawn.title, txt.withdrawn.body);
    return;
  }

  const cfg = SESSION_CONFIG;
  endScreen("Guardando…", "");

  const responses = {
    participant_id: cfg.participant_id,
    age: cfg.age,
    sex: cfg.sex,
    sequence: cfg.sequence,
    domain_sequence: cfg.domain_sequence,
    test_mode: cfg.test_mode,
    llm_model: window.PROTOCOL.prompts.model,
    suspicion: valueOrNull(session.answers.suspicion),
  };

  const baseline = collectMeasures(jsPsych, "baseline");
  for (const [key, value] of Object.entries(baseline)) {
    responses["baseline_" + key] = value;
  }

  for (const [id, situation] of Object.entries(session.situations)) {
    responses["situation_" + id] = situation.text;
    responses["situation_" + id + "_pre_rating"] = situation.pre_rating;
    responses["situation_" + id + "_alerted"] = situation.alerted;
    responses["situation_" + id + "_discarded"] =
      situation.discarded.length ? JSON.stringify(situation.discarded) : null;
  }

  const episodes = jsPsych.data.get()
    .filter({ trial_type: "chat-episode" }).values();

  const behavioral = [];
  let chat = [];
  let events = generalEvents.slice();

  session.plan.forEach((entry) => {
    const prefix = "ep" + entry.episode + "_";
    const preRating = session.situations[entry.domain.id].pre_rating;
    responses[prefix + "condition"] = entry.condition;
    responses[prefix + "agent_type"] = entry.agent_type;
    responses[prefix + "feedback"] = entry.feedback;
    responses[prefix + "domain"] = entry.domain.id;
    responses[prefix + "pre_rating"] = preRating;
    responses[prefix + "stood_out"] = valueOrNull(session.answers[prefix + "stood_out"]);

    const measures = collectMeasures(jsPsych, "ep" + entry.episode);
    for (const [key, value] of Object.entries(measures)) {
      responses[prefix + key] = value;
    }

    const ep = episodes.find((e) => e.episode === entry.episode);
    if (ep) {
      const row = Object.assign({ participant_id: cfg.participant_id,
                                  pre_rating: preRating }, ep);
      chat = chat.concat((row.transcript || []).map((message) =>
        Object.assign({ participant_id: cfg.participant_id }, message)));
      events = events.concat(row.events || []);
      delete row.transcript;
      delete row.events;
      // jsPsych adds its own internal fields; only the design's go out.
      ["trial_type", "trial_index", "time_elapsed", "plugin_version",
       "internal_node_id"].forEach((k) => delete row[k]);
      behavioral.push(row);
    }
  });

  events.sort((a, b) => a.t_experiment_s - b.t_experiment_s);

  const payload = {
    info: {
      participant_id: cfg.participant_id,
      sequence: cfg.sequence,
    },
    responses: responses,
    behavioral: behavioral,
    chat: chat,
    events: events,
    access_code: cfg.access_code || "",
  };

  try {
    const resp = await fetch("/api/data", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const obj = await resp.json();
    endScreen("Listo", `Gracias por participar.
      Se guardaron ${obj.files.length} archivos.`);
  } catch (e) {
    // A network problem must not take the session down with it.
    const blob = new Blob([JSON.stringify(payload, null, 2)],
                          { type: "application/json" });
    const url = URL.createObjectURL(blob);
    endScreen("No se pudieron guardar los datos",
      `${e.message}. <a href="${url}" download="session.json">Descargar la sesión</a>
       y pasársela a quien te está acompañando.`);
  }
}
