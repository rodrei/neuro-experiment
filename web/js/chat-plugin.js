/* Plugin de chat: un episodio completo en un solo trial de jsPsych.
 *
 * Replica escritorio/chat.py y correr_episodio() de estudio1.py:
 *
 *   saludo guionado -> el participante cuenta su situación (mínimo de
 *   caracteres) -> 3 turnos del agente con respuesta libre entre medio ->
 *   ventana final de respuesta libre.
 *
 * Lo que hay que respetar sí o sí:
 *
 *  - La LATENCIA ES DETERMINISTA (invariante 2): función del largo del
 *    mensaje, no del azar, y sale de protocolo/parametros.json. Dos personas
 *    que reciben el mismo mensaje esperan exactamente lo mismo, así que la
 *    espera no puede diferir entre las condiciones Humano / IA.
 *  - En modo LLM la generación ocurre MIENTRAS dice "en línea", y la latencia
 *    se aplica DESPUÉS, sobre el largo del texto ya generado. Si no, el
 *    tiempo de la API se sumaría a la espera y la delataría.
 *  - No contestar es un dato: la ventana final puede quedar vacía y eso se
 *    registra como [sin respuesta], no como error.
 */

var jsPsychChatEpisodio = (function (jspsych) {
  "use strict";

  const info = {
    name: "chat-episodio",
    parameters: {
      tipo: { type: jspsych.ParameterType.STRING },          // validacion | rechazo
      episodio: { type: jspsych.ParameterType.INT },
      etiqueta: { type: jspsych.ParameterType.STRING },      // barra del chat
      modo_agente: { type: jspsych.ParameterType.STRING },   // guionado | llm
      codigo: { type: jspsych.ParameterType.STRING },
    },
  };

  const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

  class ChatEpisodio {
    constructor(jsPsych) {
      this.jsPsych = jsPsych;
    }

    trial(display, trial) {
      const p = parametros();
      const t0 = performance.now();

      const transcripcion = [];
      const eventos = [];
      const historial = [];          // para el LLM: [{role, content}]
      const datos = { episodio: trial.episodio, tipo: trial.tipo };

      const ahora = () => (performance.now() - t0) / 1000;

      function marcar(etiqueta, detalle) {
        eventos.push({
          t_experimento_s: Number(ahora().toFixed(4)),
          t_unix: Date.now() / 1000,
          codigo: window.PROTOCOLO.marcadores[etiqueta] || 0,
          etiqueta: etiqueta,
          detalle: detalle || "",
        });
      }

      display.innerHTML = `
        <div class="chat">
          <div class="chat-barra">
            <div class="chat-nombre">${trial.etiqueta}</div>
            <div class="chat-estado" id="chat-estado">en línea</div>
          </div>
          <div class="chat-mensajes" id="chat-mensajes"></div>
          <div class="chat-entrada">
            <textarea id="chat-texto" placeholder="Escribí tu mensaje…"></textarea>
            <button id="chat-enviar" type="button">Enviar</button>
          </div>
          <div class="chat-ayuda" id="chat-ayuda">Enter para enviar</div>
        </div>`;

      const elMensajes = display.querySelector("#chat-mensajes");
      const elEstado = display.querySelector("#chat-estado");
      const elTexto = display.querySelector("#chat-texto");
      const elEnviar = display.querySelector("#chat-enviar");
      const elAyuda = display.querySelector("#chat-ayuda");

      function agregarBurbuja(autor, texto, origen, latencia) {
        const div = document.createElement("div");
        div.className = "burbuja " + autor;
        div.textContent = texto;
        elMensajes.appendChild(div);
        elMensajes.scrollTop = elMensajes.scrollHeight;
        const fila = {
          autor: autor,
          texto: texto,
          t_experimento_s: Number(ahora().toFixed(4)),
        };
        if (origen) fila.origen = origen;
        if (latencia !== undefined && latencia !== null) {
          fila.latencia_s = Number(latencia.toFixed(3));
        }
        transcripcion.push(fila);
      }

      /* Determinista: mismo mensaje -> misma espera, en las dos condiciones. */
      function latenciaDe(texto) {
        const t = p.latencia_base + texto.length * p.latencia_por_caracter;
        return Math.min(t, p.latencia_max) * 1000;
      }

      /* Pide el turno al servidor. La key vive allá, nunca acá. */
      async function pedirTurnoAlModelo(guionFallback) {
        try {
          const resp = await fetch("/api/turno", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              tipo: trial.tipo,
              historial: historial,
              guion_fallback: guionFallback,
              codigo: trial.codigo,
            }),
          });
          if (!resp.ok) throw new Error("HTTP " + resp.status);
          const obj = await resp.json();
          return [obj.texto, obj.origen];
        } catch (e) {
          // Mismo espíritu que el escritorio: nunca se cae, cae al guion.
          console.warn("turno al guion:", e);
          return [guionFallback, "fallback"];
        }
      }

      async function agenteDice(texto, etiquetaMarcador, origen) {
        elEstado.textContent = "en línea";
        await esperar(p.dur_lectura_min * 1000);
        elEstado.textContent = "escribiendo…";
        await esperar(latenciaDe(texto));
        elEstado.textContent = "en línea";
        agregarBurbuja("agente", texto, origen || "guion");
        if (etiquetaMarcador) marcar(etiquetaMarcador, texto.slice(0, 60));
        historial.push({ role: "assistant", content: texto });
      }

      /* Devuelve {texto, latencia}. Si se agota el timeout sin nada escrito,
         devuelve texto "" y latencia null: no contestar es un dato. */
      function esperarParticipante(opciones) {
        const minimo = opciones.minimoCaracteres || 0;
        const marcador = opciones.marcador || "participante_mensaje";
        const limite = opciones.timeout;

        return new Promise((resolver) => {
          const inicio = performance.now();
          elTexto.value = "";
          elTexto.disabled = false;
          elEnviar.disabled = false;
          elTexto.focus();

          let cronometro = null;

          const actualizarAyuda = () => {
            const limpio = elTexto.value.trim();
            if (minimo && limpio.length < minimo) {
              elAyuda.textContent =
                `Al menos ${minimo} caracteres (llevás ${limpio.length})`;
            } else {
              elAyuda.textContent = "Enter para enviar";
            }
          };

          const terminar = (texto, latencia) => {
            elTexto.removeEventListener("input", actualizarAyuda);
            elTexto.removeEventListener("keydown", alTeclear);
            elEnviar.removeEventListener("click", alEnviar);
            if (cronometro) clearTimeout(cronometro);
            elTexto.value = "";
            elTexto.disabled = true;
            elEnviar.disabled = true;
            elAyuda.textContent = "Enter para enviar";
            resolver({ texto: texto, latencia: latencia });
          };

          const enviar = () => {
            const limpio = elTexto.value.trim();
            if (!limpio || limpio.length < minimo) return;
            const latencia = (performance.now() - inicio) / 1000;
            agregarBurbuja("participante", limpio, null, latencia);
            marcar(marcador, "latencia=" + latencia.toFixed(2));
            historial.push({ role: "user", content: limpio });
            terminar(limpio, latencia);
          };

          const alTeclear = (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              enviar();
            }
          };
          const alEnviar = () => enviar();

          elTexto.addEventListener("input", actualizarAyuda);
          elTexto.addEventListener("keydown", alTeclear);
          elEnviar.addEventListener("click", alEnviar);
          actualizarAyuda();

          if (limite) {
            cronometro = setTimeout(() => {
              const limpio = elTexto.value.trim();
              if (limpio && limpio.length >= minimo) return enviar();
              marcar(marcador, "sin respuesta");
              transcripcion.push({
                autor: "participante",
                texto: "[sin respuesta]",
                t_experimento_s: Number(ahora().toFixed(4)),
              });
              historial.push({ role: "user", content: "(no responde)" });
              terminar("", null);
            }, limite * 1000);
          }
        });
      }

      // ---------------------------------------------------------------
      // El episodio
      // ---------------------------------------------------------------
      const self = this;

      (async function correr() {
        marcar("episodio_inicio", trial.episodio + "_" + trial.tipo);

        // El saludo que pide la situación es SIEMPRE guionado: tiene que
        // pedirla sí o sí, y es idéntico entre condiciones.
        const claveSaludo = trial.episodio === 1 ? "saludo" : "saludo2";
        await agenteDice(guion(claveSaludo, 0), "agente_pide_situacion", "guion");

        const situacion = await esperarParticipante({
          timeout: p.timeout_situacion,
          minimoCaracteres: p.min_caracteres_situacion,
          marcador: "situacion_revelada",
        });
        datos.situacion = situacion.texto;
        datos.situacion_caracteres = situacion.texto.length;
        datos.latencia_situacion = situacion.latencia;

        for (const turno of [1, 2, 3]) {
          const guionTurno = guion(trial.tipo, turno);
          let texto = guionTurno;
          let origen = "guion";
          if (trial.modo_agente === "llm") {
            // Se genera mientras la pantalla dice "en línea"; la latencia se
            // aplica después, sobre el largo del texto ya generado.
            const [t, o] = await pedirTurnoAlModelo(guionTurno);
            texto = t;
            origen = o;
          }
          await agenteDice(texto, "agente_mensaje_" + turno, origen);

          if (turno < 3) {
            const r = await esperarParticipante({ timeout: 90 });
            datos["respuesta_" + turno] = r.texto;
            datos["latencia_" + turno] = r.latencia;
          }
        }

        // Ventana final: contestar o no es una VD conductual del diseño.
        marcar("respuesta_libre_inicio", trial.tipo);
        const final = await esperarParticipante({
          timeout: p.ventana_respuesta_libre,
        });
        datos.respuesta_final = final.texto;
        datos.latencia_final = final.latencia;
        datos.respondio_al_final = final.texto ? 1 : 0;

        marcar("episodio_fin", trial.episodio + "_" + trial.tipo);

        datos.transcripcion = transcripcion;
        datos.eventos = eventos;
        self.jsPsych.finishTrial(datos);
      })();
    }
  }

  ChatEpisodio.info = info;
  return ChatEpisodio;
})(jsPsychModule);
