/* Pantallas de texto y escalas de autoinforme.
 *
 * Todo sale de protocolo/escalas.json y protocolo/textos.json: acá no hay
 * enunciados ni anclas escritos a mano.
 *
 * TRAMPA: un <input type="range"> SIEMPRE tiene un valor. Sin
 * require_movement, quien no toca el control "contesta" el punto medio y
 * queda registrado como un dato válido. Es el equivalente en navegador de la
 * trampa de style="radio" que ya está documentada para PsychoPy. */

function pantallaTexto(titulo, cuerpo, etiquetaBoton) {
  return {
    type: jsPsychHtmlButtonResponse,
    stimulus: () =>
      (titulo ? `<div class="pantalla-titulo">${titulo}</div>` : "") +
      `<div class="pantalla-cuerpo">${cuerpo}</div>`,
    choices: [etiquetaBoton || "Continuar"],
  };
}

function saltoDeLinea(texto) {
  return String(texto).replace(/\n/g, "<br>");
}

/* Escala tipo Likert / SAM / SUDS. `spec` viene de protocolo/escalas.json. */
function escalaSlider(spec, clave) {
  const ticks = spec.ticks;
  const paso = ticks.length > 1 ? ticks[1] - ticks[0] : 1;
  return {
    type: jsPsychHtmlSliderResponse,
    stimulus: `<p class="enunciado">${spec.enunciado}</p>`,
    labels: spec.etiquetas.map(saltoDeLinea),
    min: ticks[0],
    max: ticks[ticks.length - 1],
    step: paso,
    slider_start: ticks[Math.floor(ticks.length / 2)],
    require_movement: true,
    button_label: "Continuar",
    data: { clave: clave },
  };
}

/* PANAS en grilla, en páginas de 10. Son 20 ítems y tres administraciones:
 * de a uno por pantalla, el intervalo entre episodios se estiraría tanto que
 * la activación se disiparía antes del segundo. */
function panasTrials(momento) {
  const cfg = window.PROTOCOLO.escalas.panas;
  const items = window.PROTOCOLO.panas;
  const porPagina = cfg.items_por_pagina;
  const anclas = cfg.anclas.map(saltoDeLinea);
  const trials = [];

  for (let i = 0; i < items.length; i += porPagina) {
    const pagina = items.slice(i, i + porPagina);
    trials.push({
      type: jsPsychSurveyLikert,
      preamble: `<p class="enunciado">${cfg.consigna}</p>`,
      questions: pagina.map((it) => ({
        prompt: it.item,
        labels: anclas,
        required: true,
      })),
      button_label: "Continuar",
      data: {
        bloque: "panas",
        momento: momento,
        claves: pagina.map((it) => it.clave),
      },
    });
  }
  return trials;
}

/* Bloque de medidas, en el orden fijo SUDS -> SAM -> autenticidad -> PANAS.
 *
 * En la LÍNEA BASE va sin autenticidad: todavía no existe ningún interlocutor
 * sobre el cual opinar, y preguntarlo adelantaría la historia de cobertura. */
function bloqueMedidas(momento, incluirAutenticidad, marca) {
  const esc = window.PROTOCOLO.escalas;
  const trials = [];

  trials.push(escalaSlider(esc.suds, momento + "_suds"));
  trials.push(escalaSlider(esc.sam_valencia, momento + "_sam_valencia"));
  trials.push(escalaSlider(esc.sam_arousal, momento + "_sam_arousal"));

  if (incluirAutenticidad) {
    const aut = esc.autenticidad;
    for (const item of aut.items) {
      trials.push(escalaSlider(
        { enunciado: item.enunciado, ticks: aut.ticks, etiquetas: aut.etiquetas },
        momento + "_" + item.clave));
    }
  }

  // El PANAS va último a propósito: SUDS y SAM son las medidas sensibles al
  // tiempo y hay que tomarlas apenas termina el episodio.
  if (marca) trials.push(marca("panas_inicio", momento));
  for (const t of panasTrials(momento)) trials.push(t);
  if (marca) trials.push(marca("panas_fin", momento));

  return trials;
}

/* Respuesta ausente (pantalla salteada en modo test) -> null. Con undefined,
 * JSON.stringify tira la clave y la fila desaparece del CSV en vez de quedar
 * vacía, como queda en el escritorio. */
function valorONulo(valor) {
  return valor === undefined ? null : valor;
}

/* Recolecta las respuestas de un momento desde los datos de jsPsych.
 * Los totales PA/NA siguen la misma regla que el escritorio: una subescala
 * incompleta NO tiene total, para que un total parcial no se lea después
 * como un dato válido. */
function recolectarMedidas(jsPsych, momento) {
  const salida = {};

  jsPsych.data.get().filter({ trial_type: "html-slider-response" }).values()
    .forEach((fila) => {
      if (fila.clave && fila.clave.startsWith(momento + "_")) {
        salida[fila.clave.slice(momento.length + 1)] = valorONulo(fila.response);
      }
    });

  const items = window.PROTOCOLO.panas;
  const porClave = {};
  jsPsych.data.get().filter({ bloque: "panas", momento: momento }).values()
    .forEach((fila) => {
      const resp = fila.response || {};      // página salteada: sin response
      fila.claves.forEach((clave, i) => {
        const valor = resp["Q" + i];
        // survey-likert devuelve el índice (0..4); el protocolo usa 1..5.
        porClave[clave] = valor === null || valor === undefined
          ? null : valor + 1;
      });
    });
  Object.assign(salida, porClave);

  for (const sub of ["PA", "NA"]) {
    const valores = items.filter((it) => it.subescala === sub)
      .map((it) => porClave[it.clave]);
    const incompleta = valores.some((v) => v === null || v === undefined);
    salida[sub + "_total"] = incompleta
      ? null : valores.reduce((a, b) => a + b, 0);
  }

  return salida;
}
