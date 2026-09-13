/* El timeline: transcripción directa de main() en escritorio/estudio1.py.
 *
 * diálogo inicial -> consentimiento -> línea base -> historia de cobertura ->
 * 2 episodios de chat (cada uno seguido de su bloque de medidas) -> chequeo
 * de manipulación -> debriefing -> reconsentimiento -> envío. */

let CONFIG_SESION = null;

document.addEventListener("DOMContentLoaded", async () => {
  const estado = document.getElementById("estado-carga");
  const boton = document.getElementById("empezar");
  boton.disabled = true;
  try {
    await cargarProtocolo();
    estado.textContent = "Protocolo cargado.";
    boton.disabled = false;
  } catch (e) {
    estado.textContent = "No se pudo cargar el protocolo: " + e.message;
    return;
  }

  document.getElementById("formulario").addEventListener("submit", (e) => {
    e.preventDefault();
    const datos = new FormData(e.target);
    CONFIG_SESION = Object.fromEntries(datos.entries());
    CONFIG_SESION.orden = parseInt(CONFIG_SESION.orden, 10);
    // Un checkbox sin marcar no viene en el FormData.
    CONFIG_SESION.modo_test = datos.get("modo_test") === "1";
    document.getElementById("inicio").style.display = "none";
    document.getElementById("jspsych-target").classList.add("activo");
    correrExperimento();
  });
});

function correrExperimento() {
  const p = parametros();
  const txt = textos();
  const cfg = CONFIG_SESION;
  const eventos = [];
  const t0 = performance.now();

  function marcar(etiqueta, detalle) {
    eventos.push({
      t_experimento_s: Number(((performance.now() - t0) / 1000).toFixed(4)),
      t_unix: Date.now() / 1000,
      codigo: window.PROTOCOLO.marcadores[etiqueta] || 0,
      etiqueta: etiqueta,
      detalle: detalle || "",
    });
  }

  const jsPsych = initJsPsych({
    display_element: "jspsych-target",
    on_finish: () => enviar(jsPsych, eventos),
  });

  if (cfg.modo_test) activarModoTest(jsPsych);

  const marca = (etiqueta, detalle) => ({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: "",
    choices: "NO_KEYS",
    trial_duration: 0,
    on_finish: () => marcar(etiqueta, detalle),
  });

  const timeline = [];

  timeline.push(marca("inicio_experimento", cfg.condicion_agente));

  // Consentimiento
  timeline.push(pantallaTexto(txt.consentimiento.titulo,
                              txt.consentimiento.cuerpo));

  // Línea base: cruz de fijación. Sin EDA no mide nada, pero se mantiene para
  // que el recorrido sea el mismo que el del escritorio.
  timeline.push(pantallaTexto(txt.reposo.titulo, txt.reposo.cuerpo));
  timeline.push(marca("baseline_inicio"));
  timeline.push({
    type: jsPsychHtmlKeyboardResponse,
    stimulus: `<div class="cruz-fijacion">+</div>
               <div class="leyenda-reposo">${txt.reposo_leyenda}</div>`,
    choices: "NO_KEYS",
    trial_duration: p.dur_baseline * 1000,
  });
  timeline.push(marca("baseline_fin"));

  // Medidas de línea base: SIN autenticidad (todavía no hay interlocutor).
  timeline.push(marca("medidas_inicio", "baseline"));
  for (const t of bloqueMedidas("baseline", false, marca)) timeline.push(t);
  timeline.push(marca("medidas_fin", "baseline"));

  // Historia de cobertura: acá se manipula el factor entre-sujetos.
  timeline.push(pantallaTexto(txt.cobertura_titulo,
                              txt.cobertura[cfg.condicion_agente]));

  // Los dos episodios, en el orden contrabalanceado.
  const secuencia = cfg.orden === 1
    ? ["validacion", "rechazo"]
    : ["rechazo", "validacion"];

  secuencia.forEach((tipo, i) => {
    const nEpisodio = i + 1;

    timeline.push({
      type: jsPsychHtmlKeyboardResponse,
      stimulus: `<div class="leyenda-reposo">${txt.conectando}</div>`,
      choices: "NO_KEYS",
      trial_duration: p.dur_conectando * 1000,
    });

    timeline.push({
      type: jsPsychChatEpisodio,
      tipo: tipo,
      episodio: nEpisodio,
      etiqueta: txt.etiqueta_agente[cfg.condicion_agente],
      modo_agente: cfg.agente,
      codigo: cfg.codigo || "",
    });

    timeline.push(marca("medidas_inicio", tipo));
    for (const t of bloqueMedidas(tipo, true, marca)) timeline.push(t);
    timeline.push(marca("medidas_fin", tipo));

    if (i < secuencia.length - 1) {
      timeline.push(pantallaTexto(txt.pausa.titulo, txt.pausa.cuerpo));
    }
  });

  // Chequeo de manipulación + funnel debriefing
  timeline.push(marca("chequeo_manipulacion"));
  const chequeo = txt.chequeo;
  timeline.push(escalaSlider(chequeo.creencia_persona_real,
                             "final_creencia_persona_real"));
  timeline.push({
    type: jsPsychSurveyText,
    preamble: "<p class=\"enunciado\">Últimas preguntas.</p>",
    questions: [
      { prompt: chequeo.sospecha_1, rows: 4, columns: 60, required: true },
      { prompt: chequeo.sospecha_2, rows: 4, columns: 60, required: true },
      { prompt: chequeo.sospecha_3, rows: 4, columns: 60, required: true },
    ],
    button_label: "Continuar",
    data: { bloque: "sospecha" },
  });

  // Debriefing: la versión del modo con el que efectivamente corrió.
  timeline.push(pantallaTexto(txt.debriefing.titulo,
                              txt.debriefing.cuerpo[cfg.agente]));

  timeline.push(escalaSlider(chequeo.consiente_tras_debriefing,
                             "final_consiente_tras_debriefing"));

  timeline.push(pantallaTexto(null, txt.cierre.cuerpo, "Terminar"));
  timeline.push(marca("fin_experimento"));

  jsPsych.run(timeline);
}

/* Modo test: botón Saltar y tecla F9 para recorrer el flujo sin contestar.
 *
 * Lo salteado queda VACÍO en los CSV (una página del PANAS salteada deja la
 * subescala sin total), y la corrida queda marcada con modo_test en
 * _respuestas.csv, así que nunca se confunde con una real. */
function activarModoTest(jsPsych) {
  const boton = document.getElementById("saltar");
  boton.hidden = false;

  function saltar() {
    // Dentro del chat no se saltea el episodio entero sino la espera activa
    // (la latencia del agente o la caja de texto), igual que en el escritorio.
    if (document.querySelector("#jspsych-target .chat")) {
      jsPsychChatEpisodio.saltar();
      return;
    }
    try {
      jsPsych.finishTrial({ salteado: true });
    } catch (e) {
      // Entre dos trials no hay nada que terminar: se ignora el clic.
    }
  }

  boton.addEventListener("click", saltar);
  document.addEventListener("keydown", (e) => {
    if (e.key === "F9") {
      e.preventDefault();
      saltar();
    }
  });
}

/* Arma los cuatro archivos y los manda al servidor. */
async function enviar(jsPsych, eventosGenerales) {
  const cfg = CONFIG_SESION;
  const target = document.getElementById("jspsych-target");
  target.innerHTML = "<p class=\"pantalla-cuerpo\">Guardando…</p>";

  const respuestas = {
    id_participante: cfg.id_participante,
    edad: cfg.edad,
    sexo: cfg.sexo,
    condicion_agente: cfg.condicion_agente,
    orden: cfg.orden,
    agente: cfg.agente,
    modo_test: cfg.modo_test,
  };
  if (cfg.agente === "llm") {
    respuestas.modelo_llm = window.PROTOCOLO.prompts.modelo;
  }

  for (const momento of ["baseline", "validacion", "rechazo"]) {
    const medidas = recolectarMedidas(jsPsych, momento);
    for (const [clave, valor] of Object.entries(medidas)) {
      respuestas[momento + "_" + clave] = valor;
    }
  }

  // Una pantalla salteada no trae response. Va como null, no undefined:
  // JSON.stringify tira las claves undefined y la fila desaparecería del CSV
  // en vez de quedar vacía, como queda en el escritorio.
  jsPsych.data.get().filter({ trial_type: "html-slider-response" }).values()
    .forEach((fila) => {
      if (fila.clave && fila.clave.startsWith("final_")) {
        respuestas[fila.clave.slice("final_".length)] = valorONulo(fila.response);
      }
    });

  const sospecha = jsPsych.data.get().filter({ bloque: "sospecha" }).values()[0];
  const resp = (sospecha && sospecha.response) || {};
  respuestas.sospecha_1 = valorONulo(resp.Q0);
  respuestas.sospecha_2 = valorONulo(resp.Q1);
  respuestas.sospecha_3 = valorONulo(resp.Q2);

  const episodios = jsPsych.data.get()
    .filter({ trial_type: "chat-episodio" }).values();

  const conductual = [];
  let chat = [];
  let eventos = eventosGenerales.slice();

  episodios.forEach((ep) => {
    const fila = Object.assign({}, ep);
    chat = chat.concat(fila.transcripcion || []);
    eventos = eventos.concat(fila.eventos || []);
    delete fila.transcripcion;
    delete fila.eventos;
    // jsPsych mete sus propios campos internos; sólo van los del diseño.
    ["trial_type", "trial_index", "time_elapsed", "plugin_version",
     "internal_node_id"].forEach((k) => delete fila[k]);
    conductual.push(fila);
    respuestas["situacion_" + fila.episodio] = fila.situacion;
  });

  eventos.sort((a, b) => a.t_experimento_s - b.t_experimento_s);

  const carga = {
    info: {
      id_participante: cfg.id_participante,
      condicion_agente: cfg.condicion_agente,
    },
    respuestas: respuestas,
    conductual: conductual,
    chat: chat,
    eventos: eventos,
    codigo: cfg.codigo || "",
  };

  try {
    const resp = await fetch("/api/datos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(carga),
    });
    if (!resp.ok) throw new Error("HTTP " + resp.status);
    const obj = await resp.json();
    target.innerHTML =
      `<div class="pantalla-titulo">Listo</div>
       <div class="pantalla-cuerpo">Gracias por participar.
       Se guardaron ${obj.archivos.length} archivos.</div>`;
  } catch (e) {
    // Que un problema de red no se lleve puesta la sesión.
    const blob = new Blob([JSON.stringify(carga, null, 2)],
                          { type: "application/json" });
    const url = URL.createObjectURL(blob);
    target.innerHTML =
      `<div class="pantalla-titulo">No se pudieron guardar los datos</div>
       <div class="pantalla-cuerpo">${e.message}.
       <a href="${url}" download="sesion.json">Descargar la sesión</a>
       y pasársela a quien te está acompañando.</div>`;
  }
}
