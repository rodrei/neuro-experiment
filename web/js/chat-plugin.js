/* Chat plugin: a whole episode in a single jsPsych trial.
 *
 * Replicates desktop/chat.py and run_episode() from study1.py:
 *
 *   scripted greeting -> the participant tells their situation (minimum
 *   number of characters) -> 3 agent turns with a free reply in between ->
 *   final free-reply window.
 *
 * What must hold no matter what:
 *
 *  - The LATENCY IS DETERMINISTIC (invariant 2): a function of the message
 *    length, not of chance, and it comes from protocol/parameters.json. Two
 *    people who receive the same message wait exactly the same, so the wait
 *    cannot differ between the Human / AI conditions.
 *  - In LLM mode the generation happens WHILE it says "en línea", and the
 *    latency is applied AFTERWARDS, on the length of the generated text.
 *    Otherwise the API time would add to the wait and give it away.
 *  - Not answering is a data point: the final window may stay empty and that
 *    is recorded as [sin respuesta], not as an error.
 */

var jsPsychChatEpisode = (function (jspsych) {
  "use strict";

  const info = {
    name: "chat-episode",
    parameters: {
      feedback: { type: jspsych.ParameterType.STRING },     // validation | rejection
      episode: { type: jspsych.ParameterType.INT },
      label: { type: jspsych.ParameterType.STRING },        // chat bar
      agent_mode: { type: jspsych.ParameterType.STRING },   // scripted | llm
      access_code: { type: jspsych.ParameterType.STRING },
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
      const t0 = performance.now();

      const transcript = [];
      const events = [];
      const history = [];          // for the LLM: [{role, content}]
      const data = { episode: trial.episode, feedback: trial.feedback };

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

      function addBubble(author, text, origin, latency) {
        const div = document.createElement("div");
        div.className = "bubble " + author;
        div.textContent = text;
        elMessages.appendChild(div);
        elMessages.scrollTop = elMessages.scrollHeight;
        const row = {
          author: author,
          text: text,
          t_experiment_s: Number(now().toFixed(4)),
        };
        if (origin) row.origin = origin;
        if (latency !== undefined && latency !== null) {
          row.latency_s = Number(latency.toFixed(3));
        }
        transcript.push(row);
      }

      /* Deterministic: same message -> same wait, in both conditions. */
      function latencyOf(text) {
        const t = p.latency_base + text.length * p.latency_per_char;
        return Math.min(t, p.latency_max) * 1000;
      }

      /* Asks the server for the turn. The key lives there, never here. */
      async function requestTurn(fallbackLine) {
        try {
          const resp = await fetch("/api/turn", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              feedback: trial.feedback,
              history: history,
              fallback_line: fallbackLine,
              access_code: trial.access_code,
            }),
          });
          if (!resp.ok) throw new Error("HTTP " + resp.status);
          const obj = await resp.json();
          return [obj.text, obj.origin];
        } catch (e) {
          // Same spirit as the desktop: it never goes down, it falls back.
          console.warn("turn fell back to the script:", e);
          return [fallbackLine, "fallback"];
        }
      }

      async function agentSays(text, markerLabel, origin) {
        elStatus.textContent = "en línea";
        await wait(p.min_reading_time * 1000);
        elStatus.textContent = "escribiendo…";
        await wait(latencyOf(text));
        elStatus.textContent = "en línea";
        addBubble("agent", text, origin || "script");
        if (markerLabel) mark(markerLabel, text.slice(0, 60));
        history.push({ role: "assistant", content: text });
      }

      /* Returns {text, latency}. If the timeout runs out with nothing
         written, returns text "" and latency null: not answering is data. */
      function waitForParticipant(options) {
        const minChars = options.minChars || 0;
        const marker = options.marker || "participant_message";
        const limit = options.timeout;

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
            addBubble("participant", clean, null, latency);
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
            transcript.push({
              author: "participant",
              text: "[sin respuesta]",
              t_experiment_s: Number(now().toFixed(4)),
            });
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

          // Test mode: sends whatever there is, and if the message was
          // mandatory fills it in with the protocol's filler so the
          // conversation still has a topic (above all in LLM mode).
          currentSkip = () => {
            const clean = elText.value.trim();
            if (clean && clean.length >= minChars) return send();
            if (minChars) {
              elText.value = p.test_filler_text;
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
        mark("episode_start", trial.episode + "_" + trial.feedback);

        // The greeting that asks for the situation is ALWAYS scripted: it
        // has to ask for it no matter what, and it is identical across
        // conditions.
        const greetingKey = trial.episode === 1 ? "greeting" : "greeting2";
        await agentSays(scriptLine(greetingKey, 0), "agent_asks_situation", "script");

        const situation = await waitForParticipant({
          timeout: p.situation_timeout,
          minChars: p.min_situation_chars,
          marker: "situation_revealed",
        });
        data.situation = situation.text;
        data.situation_chars = situation.text.length;
        data.situation_latency_s = situation.latency;

        for (const turn of [1, 2, 3]) {
          const line = scriptLine(trial.feedback, turn);
          let text = line;
          let origin = "script";
          if (trial.agent_mode === "llm") {
            // Generated while the screen says "en línea"; the latency is
            // applied afterwards, on the length of the generated text.
            const [t, o] = await requestTurn(line);
            text = t;
            origin = o;
          }
          await agentSays(text, "agent_message_" + turn, origin);

          if (turn < 3) {
            const r = await waitForParticipant({ timeout: 90 });
            data["reply_" + turn] = r.text;
            data["reply_latency_" + turn] = r.latency;
          }
        }

        // Final window: answering or not is a behavioral DV of the design.
        mark("free_reply_start", trial.feedback);
        const final = await waitForParticipant({
          timeout: p.free_reply_window,
        });
        data.final_reply = final.text;
        data.final_latency_s = final.latency;
        data.replied_at_end = final.text ? 1 : 0;

        mark("episode_end", trial.episode + "_" + trial.feedback);

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
