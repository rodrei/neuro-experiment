/* Chat plugin: a whole episode in a single jsPsych trial.
 *
 *   fixed opening naming the domain -> three rounds, each: the participant
 *   writes, the agent answers -> the last message stays on screen for a fixed
 *   hold -> Continuar.
 *
 * What must hold no matter what:
 *
 *  - The model only ever receives the feedback type and the conversation.
 *    The agent type lives in the header label, never in the request: the
 *    content cannot depend on how the agent is being presented.
 *  - The LATENCY IS DETERMINISTIC: a function of the message length, not of
 *    chance, and it comes from protocol/parameters.json. Two people who
 *    receive the same message wait exactly the same, so the wait cannot
 *    differ between the person / AI conditions.
 *  - The generation happens WHILE it says "en línea", and the latency is
 *    applied AFTERWARDS, on the length of the generated text. Otherwise the
 *    API time would add to the wait and give it away.
 *  - Each agent message is stamped when it reaches the screen: that event is
 *    what the physiological response windows are locked to, not the request
 *    or the start of the "escribiendo…" indicator.
 *  - Every message goes to the transcript verbatim, with its origin. If a turn
 *    falls back to a fixed line the reason goes too; in test mode a banner
 *    shows it on screen.
 *  - Not answering is a data point: it is recorded as [sin respuesta], not as
 *    an error.
 *
 * Experimenter intervention: Ctrl+Shift+E pauses the chat. The experimenter
 * can type the agent's next message (origin "experimenter"), resume, or end
 * the episode. Whatever they do, the episode is flagged.
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
      domain: { type: jspsych.ParameterType.OBJECT },         // {id, label}
      label: { type: jspsych.ParameterType.STRING },          // chat bar
      access_code: { type: jspsych.ParameterType.STRING },
      test_mode: { type: jspsych.ParameterType.BOOL },
    },
  };

  /* The active wait (the agent latency or the participant's box) leaves here
   * how to cut itself short; ChatEpisode.skip() calls it in test mode, and the
   * experimenter's FIN calls it too. */
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

  /* Resolves in the frame that paints what was just added to the DOM. The
   * timer covers a hidden tab, where animation frames do not fire. */
  function nextPaint() {
    return new Promise((resolve) => {
      requestAnimationFrame(resolve);
      setTimeout(resolve, 100);
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
        agent_type: trial.agent_type,
        feedback: trial.feedback,
        domain: trial.domain.id,
      };
      const data = Object.assign({
        rounds_completed: 0,
        participant_messages: 0,
        replies_timed_out: 0,
        fallback_turns: 0,
        experimenter_turns: 0,
        experimenter_intervention: 0,
        agent_turns: 0,
        agent_chars_total: 0,
        total_shown_latency_s: 0,
      }, context);

      let turn = 0;                // message counter within the episode
      let overrideLine = null;     // the experimenter's next agent message
      let endRequested = false;    // the experimenter ended the episode

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
          <div class="chat-messages" id="chat-messages"></div>
          <div class="chat-input">
            <textarea id="chat-text" disabled></textarea>
            <button id="chat-send" type="button" disabled>Enviar</button>
            <button id="chat-continue" type="button" hidden>Continuar</button>
          </div>
          <div class="chat-help" id="chat-help">Enter para enviar</div>
        </div>`;
      document.body.classList.add("in-chat");

      const elMessages = display.querySelector("#chat-messages");
      const elStatus = display.querySelector("#chat-status");
      const elText = display.querySelector("#chat-text");
      const elSend = display.querySelector("#chat-send");
      const elContinue = display.querySelector("#chat-continue");
      const elHelp = display.querySelector("#chat-help");
      const elBanner = display.querySelector("#fallback-banner");

      function addBubble(author, text) {
        const div = document.createElement("div");
        div.className = "bubble " + author;
        div.textContent = text;
        elMessages.appendChild(div);
        elMessages.scrollTop = elMessages.scrollHeight;
      }

      function record(fields) {
        turn += 1;
        transcript.push(Object.assign({
          turn: turn,
          chars: fields.text.length,
          fallback_reason: null,
          shown_latency_s: null,
          response_latency_s: null,
          t_experiment_s: Number(now().toFixed(4)),
          t_unix: Date.now() / 1000,
        }, context, fields));
      }

      /* Deterministic: same message -> same wait, in both conditions. */
      function latencyOf(text) {
        const l = p.latency_base + text.length * p.latency_per_char;
        return Math.min(l, p.latency_max);
      }

      /* The experimenter sees why a turn fell back; participants never do. */
      function showFallback(round, reason) {
        data.fallback_turns += 1;
        if (!trial.test_mode) return;
        elBanner.hidden = false;
        elBanner.className = "fallback-banner error";
        elBanner.textContent = `Fallback (ronda ${round}): ${reason}`;
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

      async function agentSays(text, markerLabel, origin, reason, round) {
        const shown = latencyOf(text);
        elStatus.textContent = "en línea";
        await wait(p.min_reading_time * 1000);
        elStatus.textContent = "escribiendo…";
        await wait(shown * 1000);
        elStatus.textContent = "en línea";
        addBubble("agent", text);
        await nextPaint();
        record({ author: "agent", text: text, origin: origin,
                 fallback_reason: reason || null, round: round,
                 shown_latency_s: Number(shown.toFixed(3)) });
        mark(markerLabel, "round=" + round);
        history.push({ role: "assistant", content: text });
        data.total_shown_latency_s =
          Number((data.total_shown_latency_s + shown).toFixed(3));
      }

      /* Returns once the participant has sent or the time ran out. */
      function waitForParticipant(options) {
        const round = options.round;
        const filler = options.filler || "";

        return new Promise((resolve) => {
          const start = performance.now();
          elText.value = "";
          elText.placeholder = options.placeholder;
          elText.disabled = false;
          elSend.disabled = false;
          elText.focus();

          let timer = null;

          const finish = () => {
            elText.removeEventListener("keydown", onKey);
            elSend.removeEventListener("click", send);
            if (timer) clearTimeout(timer);
            currentSkip = null;
            elText.value = "";
            elText.disabled = true;
            elSend.disabled = true;
            resolve();
          };

          const send = () => {
            const clean = elText.value.trim();
            if (!clean) return;
            const latency = (performance.now() - start) / 1000;
            addBubble("participant", clean);
            record({ author: "participant", text: clean, origin: "participant",
                     round: round,
                     response_latency_s: Number(latency.toFixed(3)) });
            mark("participant_message", "latency=" + latency.toFixed(2));
            history.push({ role: "user", content: clean });
            data.participant_messages += 1;
            finish();
          };

          const onKey = (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          };

          elText.addEventListener("keydown", onKey);
          elSend.addEventListener("click", send);

          const noReply = () => {
            mark("participant_message", "no reply");
            data.replies_timed_out += 1;
            record({ author: "participant", text: "[sin respuesta]",
                     origin: "participant", round: round, chars: 0 });
            history.push({ role: "user", content: "(no responde)" });
            finish();
          };

          timer = setTimeout(() => {
            if (elText.value.trim()) return send();
            noReply();
          }, options.timeout * 1000);

          // Test mode sends whatever there is; the opening round, which
          // passes a filler, fills an empty box so the conversation has
          // something to react to. Ending the episode never invents text.
          currentSkip = () => {
            if (elText.value.trim()) return send();
            if (filler && !endRequested) {
              elText.value = filler;
              return send();
            }
            noReply();
          };
        });
      }

      function intervene(e) {
        if (!(e.ctrlKey && e.shiftKey && e.key.toLowerCase() === "e")) return;
        e.preventDefault();
        const answer = window.prompt(t.chat.experimenter_prompt);
        if (answer === null) return;
        data.experimenter_intervention = 1;
        const clean = answer.trim();
        mark("experimenter_intervention", clean.toUpperCase() === "FIN" ? "end" : "");
        if (clean.toUpperCase() === "FIN") {
          endRequested = true;
          if (currentSkip) currentSkip();
        } else if (clean) {
          overrideLine = clean;
        }
      }
      document.addEventListener("keydown", intervene);

      // ---------------------------------------------------------------
      // The episode
      // ---------------------------------------------------------------
      const self = this;

      (async function run() {
        mark("episode_start", trial.episode + "_" + trial.condition);

        await agentSays(fill(t.chat.opening, { domain: trial.domain.label }),
                        "opening_message", "opening", null, 0);

        for (let round = 1; round <= p.rounds && !endRequested; round++) {
          mark("round_start_" + round, trial.condition);

          await waitForParticipant({
            round: round,
            timeout: round === 1 ? p.situation_timeout : p.reply_timeout,
            placeholder: round === 1 ? t.chat.placeholder_situation
                                     : t.chat.placeholder_feeling,
            filler: round === 1 ? p.test_filler_text : "",
          });
          if (endRequested) break;

          let text, origin, reason;
          if (overrideLine !== null) {
            text = overrideLine;
            origin = "experimenter";
            reason = null;
            overrideLine = null;
            data.experimenter_turns += 1;
          } else {
            // Generated while the screen says "en línea"; the latency is
            // applied afterwards, on the length of the generated text.
            [text, origin, reason] = await requestTurn(
              fallbackLine(trial.feedback, round));
            if (origin === "fallback") showFallback(round, reason);
            else showRecovered();
          }
          await agentSays(text, "agent_message_" + round, origin, reason, round);
          data.agent_turns += 1;
          data.agent_chars_total += text.length;
          data.rounds_completed = round;
        }

        // The last message stays up for a fixed time, so the response window
        // locked to it is not cut by the measures.
        elHelp.textContent = t.chat.ended;
        await wait(p.final_message_hold * 1000);
        elSend.hidden = true;
        elContinue.hidden = false;
        await new Promise((resolve) => {
          const done = () => {
            currentSkip = null;
            resolve();
          };
          elContinue.addEventListener("click", done);
          currentSkip = done;
        });

        mark("episode_end", trial.episode + "_" + trial.condition);

        document.removeEventListener("keydown", intervene);
        document.body.classList.remove("in-chat");
        data.agent_chars_mean = data.agent_turns
          ? Number((data.agent_chars_total / data.agent_turns).toFixed(1)) : null;
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
