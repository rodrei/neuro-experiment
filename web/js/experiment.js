/* The timeline of the debate design (2x2 within-subject).
 *
 * start form -> consent -> baseline -> instructions -> 4 episodes, each:
 * interlocutor intro -> topic pick -> connecting -> chat -> measures
 * (-> pause) -> debriefing -> close -> submission.
 *
 * The order of the four conditions comes from protocol/sequences.json (a
 * Latin square indexed by the sequence chosen on the start form). */

let SESSION_CONFIG = null;

document.addEventListener("DOMContentLoaded", async () => {
  const status = document.getElementById("load-status");
  const button = document.getElementById("begin");
  const idField = document.querySelector("input[name=participant_id]");
  const sequenceSelect = document.getElementById("sequence");
  button.disabled = true;

  for (let i = 1; i <= 4; i++) {
    const option = document.createElement("option");
    option.value = String(i);
    option.textContent = String(i);
    sequenceSelect.appendChild(option);
  }

  // Sequence suggested from the id, so the four rows of the Latin square
  // spread over participants without anyone thinking about it. Stops
  // following the id once the experimenter picks one by hand.
  let sequenceTouched = false;
  const suggest = () => {
    if (sequenceTouched) return;
    sequenceSelect.value = String(suggestedSequence(idField.value));
  };
  idField.addEventListener("input", suggest);
  sequenceSelect.addEventListener("change", () => { sequenceTouched = true; });
  suggest();

  try {
    await loadProtocol();
    status.textContent = "Protocolo cargado.";
    button.disabled = false;
  } catch (e) {
    status.textContent = "No se pudo cargar el protocolo: " + e.message;
    return;
  }

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
    // An unchecked checkbox is not in the FormData.
    SESSION_CONFIG.test_mode = data.get("test_mode") === "1";
    document.getElementById("start").style.display = "none";
    document.getElementById("jspsych-target").classList.add("active");
    runExperiment();
  });
});

function suggestedSequence(id) {
  const sum = Array.from(String(id || "")).reduce((a, c) => a + c.charCodeAt(0), 0);
  return (sum % 4) + 1;
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

  timeline.push(mark("experiment_start", "seq" + cfg.sequence));

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
    data: { screen: "rest" },
  });
  timeline.push(mark("baseline_end"));

  // Baseline measures: WITHOUT authenticity (no interlocutor yet).
  timeline.push(mark("measures_start", "baseline"));
  for (const t of measuresBlock("baseline", false, mark)) timeline.push(t);
  timeline.push(mark("measures_end", "baseline"));

  // General instructions for the four debates.
  timeline.push(textScreen(txt.instructions.title, txt.instructions.body));

  // The four episodes, in the order of the Latin square row.
  const sequence = window.PROTOCOL.sequences[String(cfg.sequence)];
  const interlocutors = window.PROTOCOL.interlocutors;
  const usedInterlocutors = [];
  const usedTopics = [];
  const plan = [];      // filled here; read by submit()

  sequence.forEach((condition, i) => {
    const episode = i + 1;
    const [agentType, feedback] = condition.split("_");
    const moment = "ep" + episode;

    // Names are assigned by position within the agent type, not by
    // feedback: the sequences balance name x feedback across participants.
    const who = interlocutors.find(
      (it) => it.type === agentType && !usedInterlocutors.includes(it.name));
    usedInterlocutors.push(who.name);
    const entry = { episode, condition, agent_type: agentType, feedback,
                    interlocutor: who.name, topic: null };
    plan.push(entry);

    // Interlocutor intro: honest, no persuasion.
    timeline.push(mark("interlocutor_intro", episode + "_" + condition));
    timeline.push(Object.assign(
      textScreen(txt.interlocutor_intro.title,
                 fill(txt.interlocutor_intro[agentType], { name: who.name })),
      { data: { screen: "intro" } }));

    // Topic pick: the questions not used yet in this session, as cards.
    timeline.push(mark("topic_shown", String(episode)));
    timeline.push({
      type: jsPsychHtmlButtonResponse,
      stimulus: `<div class="screen-title">${txt.topic_pick.title}</div>
                 <div class="screen-lead">${txt.topic_pick.lead}</div>`,
      choices: () => remainingTopics(usedTopics).map((t) => t.id),
      button_html: (choice) => {
        const topic = window.PROTOCOL.topics.find((t) => t.id === choice);
        return `<button class="topic-card" data-topic="${topic.id}">
                  <span class="topic-category">${topic.category}</span>
                  <span class="topic-question">${topic.question}</span>
                </button>`;
      },
      button_layout: "flex",
      data: { screen: "topic-pick", episode: episode },
      on_finish: (d) => {
        const remaining = remainingTopics(usedTopics);
        // A skipped screen (test mode) picks the first remaining topic so
        // the episode still has a question.
        const topic = d.response === null || d.response === undefined
          ? remaining[0] : remaining[d.response];
        usedTopics.push(topic.id);
        entry.topic = topic;
        d.topic_id = topic.id;
        record("topic_chosen", topic.id);
      },
    });

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
      interlocutor: who.name,
      label: fill(txt.interlocutor_label[agentType], { name: who.name }),
      topic: () => entry.topic,
      access_code: cfg.access_code || "",
      test_mode: cfg.test_mode,
    });

    timeline.push(mark("measures_start", moment + "_" + condition));
    for (const t of measuresBlock(moment, true, mark)) timeline.push(t);
    timeline.push(mark("measures_end", moment + "_" + condition));

    if (i < sequence.length - 1) {
      timeline.push(Object.assign(textScreen(txt.pause.title, txt.pause.body),
                                  { data: { screen: "pause" } }));
    }
  });

  timeline.push(Object.assign(
    textScreen(txt.debriefing.title, txt.debriefing.body),
    { data: { screen: "debriefing" } }));

  timeline.push(Object.assign(textScreen(null, txt.closing.body, "Terminar"),
                              { data: { screen: "close" } }));
  timeline.push(mark("experiment_end"));

  jsPsych.plan = plan;
  jsPsych.run(timeline);
}

function remainingTopics(usedTopics) {
  return window.PROTOCOL.topics.filter((t) => !usedTopics.includes(t.id));
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
    sequence: cfg.sequence,
    test_mode: cfg.test_mode,
    llm_model: window.PROTOCOL.prompts.model,
  };

  const baseline = collectMeasures(jsPsych, "baseline");
  for (const [key, value] of Object.entries(baseline)) {
    responses["baseline_" + key] = value;
  }

  const episodes = jsPsych.data.get()
    .filter({ trial_type: "chat-episode" }).values();

  const behavioral = [];
  let chat = [];
  let events = generalEvents.slice();

  jsPsych.plan.forEach((entry) => {
    const prefix = "ep" + entry.episode + "_";
    responses[prefix + "condition"] = entry.condition;
    responses[prefix + "agent_type"] = entry.agent_type;
    responses[prefix + "feedback"] = entry.feedback;
    responses[prefix + "topic"] = entry.topic ? entry.topic.id : null;
    responses[prefix + "interlocutor"] = entry.interlocutor;

    const ep = episodes.find((e) => e.episode === entry.episode);
    // A skipped screen brings no response. It goes as null, not undefined:
    // JSON.stringify drops undefined keys and the row would disappear from
    // the CSV instead of staying empty, as it does on the desktop.
    responses[prefix + "opinion"] = valueOrNull(ep && ep.opinion);

    const measures = collectMeasures(jsPsych, "ep" + entry.episode);
    for (const [key, value] of Object.entries(measures)) {
      responses[prefix + key] = value;
    }

    if (ep) {
      const row = Object.assign({}, ep);
      chat = chat.concat(row.transcript || []);
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
