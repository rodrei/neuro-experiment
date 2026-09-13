/* The timeline: a direct transcription of main() in desktop/study1.py.
 *
 * initial dialog -> consent -> baseline -> cover story -> 2 chat episodes
 * (each followed by its measures block) -> manipulation check -> debriefing
 * -> re-consent -> submission. */

let SESSION_CONFIG = null;

document.addEventListener("DOMContentLoaded", async () => {
  const status = document.getElementById("load-status");
  const button = document.getElementById("begin");
  button.disabled = true;
  try {
    await loadProtocol();
    status.textContent = "Protocolo cargado.";
    button.disabled = false;
  } catch (e) {
    status.textContent = "No se pudo cargar el protocolo: " + e.message;
    return;
  }

  document.getElementById("form").addEventListener("submit", (e) => {
    e.preventDefault();
    const data = new FormData(e.target);
    SESSION_CONFIG = Object.fromEntries(data.entries());
    SESSION_CONFIG.order = parseInt(SESSION_CONFIG.order, 10);
    // An unchecked checkbox is not in the FormData.
    SESSION_CONFIG.test_mode = data.get("test_mode") === "1";
    document.getElementById("start").style.display = "none";
    document.getElementById("jspsych-target").classList.add("active");
    runExperiment();
  });
});

function runExperiment() {
  const p = parameters();
  const txt = texts();
  const cfg = SESSION_CONFIG;
  const events = [];
  const t0 = performance.now();

  function record(label, detail) {
    events.push({
      t_experiment_s: Number(((performance.now() - t0) / 1000).toFixed(4)),
      t_unix: Date.now() / 1000,
      code: window.PROTOCOL.markers[label] || 0,
      label: label,
      detail: detail || "",
    });
  }

  const jsPsych = initJsPsych({
    display_element: "jspsych-target",
    on_finish: () => submit(jsPsych, events),
  });

  if (cfg.test_mode) enableTestMode(jsPsych);

  const mark = (label, detail) => ({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: "",
    choices: "NO_KEYS",
    trial_duration: 0,
    on_finish: () => record(label, detail),
  });

  const timeline = [];

  timeline.push(mark("experiment_start", cfg.agent_condition));

  // Consent
  timeline.push(textScreen(txt.consent.title, txt.consent.body));

  // Baseline: fixation cross. Without EDA it measures nothing, but it stays
  // so the walkthrough is the same as the desktop's.
  timeline.push(textScreen(txt.rest.title, txt.rest.body));
  timeline.push(mark("baseline_start"));
  timeline.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: `<div class="fixation-cross">+</div>
               <div class="rest-caption">${txt.rest_caption}</div>`,
    choices: "NO_KEYS",
    trial_duration: p.baseline_duration * 1000,
  });
  timeline.push(mark("baseline_end"));

  // Baseline measures: WITHOUT authenticity (no interlocutor yet).
  timeline.push(mark("measures_start", "baseline"));
  for (const t of measuresBlock("baseline", false, mark)) timeline.push(t);
  timeline.push(mark("measures_end", "baseline"));

  // Cover story: the between-subjects factor is manipulated here.
  timeline.push(textScreen(txt.cover_story_title,
                           txt.cover_story[cfg.agent_condition]));

  // The two episodes, in the counterbalanced order.
  const sequence = cfg.order === 1
    ? ["validation", "rejection"]
    : ["rejection", "validation"];

  sequence.forEach((feedback, i) => {
    const episodeNumber = i + 1;

    timeline.push({
      type: jsPsychHtmlKeyboardResponse,
      stimulus: `<div class="rest-caption">${txt.connecting}</div>`,
      choices: "NO_KEYS",
      trial_duration: p.connecting_duration * 1000,
    });

    timeline.push({
      type: jsPsychChatEpisode,
      feedback: feedback,
      episode: episodeNumber,
      label: txt.agent_label[cfg.agent_condition],
      agent_mode: cfg.agent,
      access_code: cfg.access_code || "",
    });

    timeline.push(mark("measures_start", feedback));
    for (const t of measuresBlock(feedback, true, mark)) timeline.push(t);
    timeline.push(mark("measures_end", feedback));

    if (i < sequence.length - 1) {
      timeline.push(textScreen(txt.pause.title, txt.pause.body));
    }
  });

  // Manipulation check + funnel debriefing
  timeline.push(mark("manipulation_check"));
  const check = txt.manipulation_check;
  timeline.push(sliderScale(check.believed_real_person,
                            "final_believed_real_person"));
  timeline.push({
    type: jsPsychSurveyText,
    preamble: "<p class=\"prompt\">Últimas preguntas.</p>",
    questions: [
      { prompt: check.suspicion_1, rows: 4, columns: 60, required: true },
      { prompt: check.suspicion_2, rows: 4, columns: 60, required: true },
      { prompt: check.suspicion_3, rows: 4, columns: 60, required: true },
    ],
    button_label: "Continuar",
    data: { block: "suspicion" },
  });

  // Debriefing: the version of the mode that actually ran.
  timeline.push(textScreen(txt.debriefing.title,
                           txt.debriefing.body[cfg.agent]));

  timeline.push(sliderScale(check.consents_after_debriefing,
                            "final_consents_after_debriefing"));

  timeline.push(textScreen(null, txt.closing.body, "Terminar"));
  timeline.push(mark("experiment_end"));

  jsPsych.run(timeline);
}

/* Test mode: Skip button and F9 key to walk the flow without answering.
 *
 * Whatever is skipped stays EMPTY in the CSVs (a skipped PANAS page leaves
 * the subscale without a total), and the run is flagged with test_mode in
 * _responses.csv, so it is never confused with a real one. */
function enableTestMode(jsPsych) {
  const button = document.getElementById("skip");
  button.hidden = false;

  function skip() {
    // Inside the chat the whole episode is not skipped, only the active
    // wait (the agent latency or the text box), as on the desktop.
    if (document.querySelector("#jspsych-target .chat")) {
      jsPsychChatEpisode.skip();
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

/* Builds the four files and sends them to the server. */
async function submit(jsPsych, generalEvents) {
  const cfg = SESSION_CONFIG;
  const target = document.getElementById("jspsych-target");
  target.innerHTML = "<p class=\"screen-body\">Guardando…</p>";

  const responses = {
    participant_id: cfg.participant_id,
    age: cfg.age,
    sex: cfg.sex,
    agent_condition: cfg.agent_condition,
    order: cfg.order,
    agent: cfg.agent,
    test_mode: cfg.test_mode,
  };
  if (cfg.agent === "llm") {
    responses.llm_model = window.PROTOCOL.prompts.model;
  }

  for (const moment of ["baseline", "validation", "rejection"]) {
    const measures = collectMeasures(jsPsych, moment);
    for (const [key, value] of Object.entries(measures)) {
      responses[moment + "_" + key] = value;
    }
  }

  // A skipped screen brings no response. It goes as null, not undefined:
  // JSON.stringify drops undefined keys and the row would disappear from the
  // CSV instead of staying empty, as it does on the desktop.
  jsPsych.data.get().filter({ trial_type: "html-slider-response" }).values()
    .forEach((row) => {
      if (row.key && row.key.startsWith("final_")) {
        responses[row.key.slice("final_".length)] = valueOrNull(row.response);
      }
    });

  const suspicion = jsPsych.data.get().filter({ block: "suspicion" }).values()[0];
  const resp = (suspicion && suspicion.response) || {};
  responses.suspicion_1 = valueOrNull(resp.Q0);
  responses.suspicion_2 = valueOrNull(resp.Q1);
  responses.suspicion_3 = valueOrNull(resp.Q2);

  const episodes = jsPsych.data.get()
    .filter({ trial_type: "chat-episode" }).values();

  const behavioral = [];
  let chat = [];
  let events = generalEvents.slice();

  episodes.forEach((ep) => {
    const row = Object.assign({}, ep);
    chat = chat.concat(row.transcript || []);
    events = events.concat(row.events || []);
    delete row.transcript;
    delete row.events;
    // jsPsych adds its own internal fields; only the design's go out.
    ["trial_type", "trial_index", "time_elapsed", "plugin_version",
     "internal_node_id"].forEach((k) => delete row[k]);
    behavioral.push(row);
    responses["situation_" + row.episode] = row.situation;
  });

  events.sort((a, b) => a.t_experiment_s - b.t_experiment_s);

  const payload = {
    info: {
      participant_id: cfg.participant_id,
      agent_condition: cfg.agent_condition,
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
    target.innerHTML =
      `<div class="screen-title">Listo</div>
       <div class="screen-body">Gracias por participar.
       Se guardaron ${obj.files.length} archivos.</div>`;
  } catch (e) {
    // A network problem must not take the session down with it.
    const blob = new Blob([JSON.stringify(payload, null, 2)],
                          { type: "application/json" });
    const url = URL.createObjectURL(blob);
    target.innerHTML =
      `<div class="screen-title">No se pudieron guardar los datos</div>
       <div class="screen-body">${e.message}.
       <a href="${url}" download="session.json">Descargar la sesión</a>
       y pasársela a quien te está acompañando.</div>`;
  }
}
