/* Chat plugin: a whole debate episode in a single jsPsych trial.
 *
 *   pinned topic card (not a bubble) -> the participant writes their opinion
 *   (minimum number of characters) -> 3 LLM turns with a free reply in
 *   between -> final free-reply window.
 *
 * What must hold no matter what:
 *
 *  - Bubbles are only ever real messages. The chosen question lives in a
 *    pinned card under the bar, with no author and no bubble class.
 *  - The LATENCY IS DETERMINISTIC (invariant 2): a function of the message
 *    length, not of chance, and it comes from protocol/parameters.json. Two
 *    people who receive the same message wait exactly the same, so the wait
 *    cannot differ between the person / AI conditions.
 *  - The generation happens WHILE it says "en línea", and the latency is
 *    applied AFTERWARDS, on the length of the generated text. Otherwise the
 *    API time would add to the wait and give it away.
 *  - If a turn falls back to a fixed line, the origin and the reason go to
 *    the transcript; in test mode a banner shows the reason on screen.
 *  - Not answering is a data point: the final window may stay empty and that
 *    is recorded as [sin respuesta], not as an error.
 */

var jsPsychChatEpisode = (function (jspsych) {
  "use strict";

  const info = {
    name: "chat-episode",
    parameters: {
      episode: { type: jspsych.ParameterType.INT },           // 1..4
      condition: { type: jspsych.ParameterType.STRING },      // e.g. ai_rejection
      agent_type: { type: jspsych.ParameterType.STRING },     // human | ai
      feedback: { type: jspsych.ParameterType.STRING },       // validation | rejection
      interlocutor: { type: jspsych.ParameterType.STRING },   // name
      label: { type: jspsych.ParameterType.STRING },          // chat bar
      topic: { type: jspsych.ParameterType.OBJECT },          // {id, category, question}
      access_code: { type: jspsych.ParameterType.STRING },
      test_mode: { type: jspsych.ParameterType.BOOL },
    },
  };

  /* Test mode. The active wait (the agent latency or the participant's box)
   * leaves here how to skip itself; ChatEpisode.skip() calls it. Outside
   * test mode nobody invokes it. */
  let currentSkip = null;

  function wait(ms) {
    return new Promise((resolve) => {
      const timer = setTimeout(done, ms);
      function done() {
        clearTimeout(timer);
        currentSkip = null;
        resolve();
      }
      currentSkip = done;
    });
  }

  class ChatEpisode {
    constructor(jsPsych) {
      this.jsPsych = jsPsych;
    }

    trial(display, trial) {
      const p = parameters();
      const t = texts();
      // Same clock as the timeline's markers, so the transcript and the
      // events of the four episodes sort correctly into one log.
      const t0 = window.EXPERIMENT_T0 || performance.now();

      const transcript = [];
      const events = [];
      const history = [];          // for the LLM: [{role, content}]
      const context = {
        episode: trial.episode,
        condition: trial.condition,
        interlocutor: trial.interlocutor,
        topic: trial.topic.id,
      };
      const data = Object.assign({
        agent_type: trial.agent_type,
        feedback: trial.feedback,
        fallback_turns: 0,
        replies_timed_out: 0,
      }, context);

      const now = () => (performance.now() - t0) / 1000;

      function mark(label, detail) {
        events.push({
          t_experiment_s: Number(now().toFixed(4)),
          t_unix: Date.now() / 1000,
          code: window.PROTOCOL.markers[label] || 0,
          label: label,
          detail: detail || "",
        });
      }

      display.innerHTML = `
        <div class="chat">
          <div class="chat-bar">
            <div class="chat-name">${trial.label}</div>
            <div class="chat-status" id="chat-status">en línea</div>
          </div>
          <div class="fallback-banner" id="fallback-banner" hidden></div>
          <div class="topic-pinned" id="topic-pinned">
            <div class="topic-pinned-title">${t.topic_card.title}</div>
            <div class="topic-pinned-question">${trial.topic.question}</div>
            <div class="topic-pinned-hint">${t.topic_card.hint}</div>
          </div>
          <div class="chat-messages" id="chat-messages"></div>
          <div class="chat-input">
            <textarea id="chat-text" placeholder="Escribí tu mensaje…"></textarea>
            <button id="chat-send" type="button">Enviar</button>
          </div>
          <div class="chat-help" id="chat-help">Enter para enviar</div>
        </div>`;

      const elMessages = display.querySelector("#chat-messages");
      const elStatus = display.querySelector("#chat-status");
      const elText = display.querySelector("#chat-text");
      const elSend = display.querySelector("#chat-send");
      const elHelp = display.querySelector("#chat-help");
      const elBanner = display.querySelector("#fallback-banner");
      const elPinned = display.querySelector("#topic-pinned");

      function addBubble(author, text, origin, reason, latency) {
        const div = document.createElement("div");
        div.className = "bubble " + author;
        div.textContent = text;
        elMessages.appendChild(div);
        elMessages.scrollTop = elMessages.scrollHeight;
        const row = Object.assign({
          author: author,
          text: text,
          origin: origin || (author === "participant" ? "participant" : "llm"),
          fallback_reason: reason || null,
          t_experiment_s: Number(now().toFixed(4)),
          latency_s: (latency === undefined || latency === null)
            ? null : Number(latency.toFixed(3)),
        }, context);
        transcript.push(row);
      }

      /* Deterministic: same message -> same wait, in both conditions. */
      function latencyOf(text) {
        const l = p.latency_base + text.length * p.latency_per_char;
        return Math.min(l, p.latency_max) * 1000;
      }

      /* The experimenter sees why a turn fell back; participants never do. */
      function showFallback(turn, reason) {
        data.fallback_turns += 1;
        if (!trial.test_mode) return;
        elBanner.hidden = false;
        elBanner.className = "fallback-banner error";
        elBanner.textContent = `Fallback (turno ${turn}): ${reason}`;
      }

      function showRecovered() {
        if (!trial.test_mode || data.fallback_turns === 0) return;
        elBanner.className = "fallback-banner warning";
        elBanner.textContent = data.fallback_turns === 1
          ? "1 turno cayó al fallback"
          : `${data.fallback_turns} turnos cayeron al fallback`;
      }

      /* Asks the server for the turn. The key lives there, never here.
         Returns [text, origin, reason]. */
      async function requestTurn(line) {
        try {
          const resp = await fetch("/api/turn", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              feedback: trial.feedback,
              name: trial.interlocutor,
              question: trial.topic.question,
              history: history,
              fallback_line: line,
              access_code: trial.access_code,
            }),
          });
          if (!resp.ok) {
            let detail = "";
            try { detail = (await resp.json()).error || ""; } catch (e) { /* not json */ }
            throw new Error("HTTP " + resp.status + (detail ? " " + detail : ""));
          }
          const obj = await resp.json();
          return [obj.text, obj.origin, obj.fallback_reason || null];
        } catch (e) {
          // The server itself could not be reached: fall back here, with
          // the reason, same as the server does for the API.
          return [line, "fallback", "fetch: " + e.message];
        }
      }

      async function agentSays(text, markerLabel, origin, reason) {
        elStatus.textContent = "en línea";
        await wait(p.min_reading_time * 1000);
        elStatus.textContent = "escribiendo…";
        await wait(latencyOf(text));
        elStatus.textContent = "en línea";
        addBubble("agent", text, origin, reason);
        if (markerLabel) mark(markerLabel, text.slice(0, 60));
        history.push({ role: "assistant", content: text });
      }

      /* Returns {text, latency}. If the timeout runs out with nothing
         written, returns text "" and latency null: not answering is data. */
      function waitForParticipant(options) {
        const minChars = options.minChars || 0;
        const marker = options.marker || "participant_message";
        const limit = options.timeout;
        const filler = options.filler || "";

        return new Promise((resolve) => {
          const start = performance.now();
          elText.value = "";
          elText.disabled = false;
          elSend.disabled = false;
          elText.focus();

          let timer = null;

          const updateHelp = () => {
            const clean = elText.value.trim();
            if (minChars && clean.length < minChars) {
              elHelp.textContent =
                `Al menos ${minChars} caracteres (llevás ${clean.length})`;
            } else {
              elHelp.textContent = "Enter para enviar";
            }
          };

          const finish = (text, latency) => {
            elText.removeEventListener("input", updateHelp);
            elText.removeEventListener("keydown", onKey);
            elSend.removeEventListener("click", onSend);
            if (timer) clearTimeout(timer);
            currentSkip = null;
            elText.value = "";
            elText.disabled = true;
            elSend.disabled = true;
            elHelp.textContent = "Enter para enviar";
            resolve({ text: text, latency: latency });
          };

          const send = () => {
            const clean = elText.value.trim();
            if (!clean || clean.length < minChars) return;
            const latency = (performance.now() - start) / 1000;
            addBubble("participant", clean, "participant", null, latency);
            mark(marker, "latency=" + latency.toFixed(2));
            history.push({ role: "user", content: clean });
            finish(clean, latency);
          };

          const onKey = (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          };
          const onSend = () => send();

          elText.addEventListener("input", updateHelp);
          elText.addEventListener("keydown", onKey);
          elSend.addEventListener("click", onSend);
          updateHelp();

          const noReply = () => {
            mark(marker, "no reply");
            data.replies_timed_out += 1;
            transcript.push(Object.assign({
              author: "participant",
              text: "[sin respuesta]",
              origin: "participant",
              fallback_reason: null,
              t_experiment_s: Number(now().toFixed(4)),
              latency_s: null,
            }, context));
            history.push({ role: "user", content: "(no responde)" });
            finish("", null);
          };

          if (limit) {
            timer = setTimeout(() => {
              const clean = elText.value.trim();
              if (clean && clean.length >= minChars) return send();
              noReply();
            }, limit * 1000);
          }

          // Test mode: sends whatever there is; for the opening opinion
          // (the step that passes a filler) an empty box is filled with the
          // protocol's filler so the conversation has an opinion to react to.
          currentSkip = () => {
            const clean = elText.value.trim();
            if (clean && clean.length >= minChars) return send();
            if (filler) {
              elText.value = filler;
              return send();
            }
            noReply();
          };
        });
      }

      // ---------------------------------------------------------------
      // The episode
      // ---------------------------------------------------------------
      const self = this;

      (async function run() {
        mark("episode_start", trial.episode + "_" + trial.condition);

        // The participant opens: their opinion on the pinned question. Any
        // non-empty message counts; no minimum length.
        const opinion = await waitForParticipant({
          timeout: p.situation_timeout,
          marker: "opinion_sent",
          filler: p.test_filler_opinion,
        });
        data.opinion = opinion.text;
        data.opinion_chars = opinion.text.length;
        data.opinion_latency_s = opinion.latency;
        elPinned.classList.add("answered");

        for (const turn of [1, 2, 3]) {
          // Generated while the screen says "en línea"; the latency is
          // applied afterwards, on the length of the generated text.
          const [text, origin, reason] = await requestTurn(
            fallbackLine(trial.feedback, turn));
          if (origin === "fallback") showFallback(turn, reason);
          else showRecovered();
          await agentSays(text, "agent_message_" + turn, origin, reason);

          if (turn < 3) {
            const r = await waitForParticipant({ timeout: 90 });
            data["reply_" + turn] = r.text;
            data["reply_" + turn + "_chars"] = r.text.length;
            data["reply_latency_" + turn] = r.latency;
          }
        }

        // Final window: answering or not is a behavioral DV of the design.
        mark("free_reply_start", trial.condition);
        const final = await waitForParticipant({
          timeout: p.free_reply_window,
        });
        data.final_reply = final.text;
        data.final_latency_s = final.latency;
        data.replied_at_end = final.text ? 1 : 0;

        mark("episode_end", trial.episode + "_" + trial.condition);

        data.transcript = transcript;
        data.events = events;
        self.jsPsych.finishTrial(data);
      })();
    }
  }

  ChatEpisode.info = info;
  ChatEpisode.skip = () => {
    if (currentSkip) currentSkip();
  };
  return ChatEpisode;
})(jsPsychModule);
