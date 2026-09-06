# -*- coding: utf-8 -*-
"""
ESTUDIO 1 — Validación y rechazo: IA vs. agente humano
Neurodiplo, Grupo 3 · AI companions

Diseño: 2 x 2 mixto
  · Tipo de agente (Humano vs. IA)  ....... entre-sujetos, se fija al iniciar
  · Retroalimentación (Validación vs. Rechazo) ... intra-sujeto, contrabalanceada

Correr con:  PsychoPy Coder  ->  abrir este archivo  ->  Run
o desde terminal, ver el README.

Salir en cualquier momento: Ctrl + Q
"""

import os
import sys
import csv
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from psychopy import visual, core, event, gui

import config
import escalas
from comun.agente_llm import AgenteLLM, cargar_api_key
from comun import protocolo
from chat import Chat
from marcadores import RegistroEventos


# =====================================================================
# 1. Diálogo inicial
# =====================================================================
def dialogo_inicial():
    info = {
        "id_participante": "",
        "edad": "",
        "sexo": ["mujer", "varón", "otro / prefiero no decir"],
        "condicion_agente": ["humano", "ia"],
        "orden": ["1 = validación primero", "2 = rechazo primero"],
        "registra_eeg": False,
    }
    dlg = gui.DlgFromDict(
        info, title="Estudio 1 — AI companions",
        order=["id_participante", "edad", "sexo", "condicion_agente",
               "orden", "registra_eeg"])
    if not dlg.OK:
        core.quit()
    if not info["id_participante"].strip():
        info["id_participante"] = "sin_id"
    info["orden"] = 1 if info["orden"].startswith("1") else 2
    return info


def cargar_guiones():
    return protocolo.guiones()


# =====================================================================
# 2. Un episodio de chat (validación o rechazo)
# =====================================================================
def correr_episodio(win, conv, registro, guiones, tipo, n_episodio,
                    agente=None):
    """tipo: 'validacion' o 'rechazo'. Devuelve dict con datos conductuales.

    El participante cuenta su situación DENTRO del chat: el agente se la pide
    y él la escribe ahí mismo. Así la historia de cobertura no se rompe.

    Si `agente` (AgenteLLM) no es None, los tres turnos los genera el modelo;
    el saludo sigue guionado igual. Si la API falla, el turno cae al guion.
    """
    conv.limpiar()
    registro.marcar("episodio_inicio", "%d_%s" % (n_episodio, tipo))

    # pantalla de conexión (estandarizada entre condiciones)
    espera = visual.TextStim(
        win, text="Conectando…", font=config.FUENTE, height=0.040,
        color=config.COLOR_TENUE, pos=(0, 0))
    salto = escalas.boton_salto(win)
    raton = event.Mouse(win=win)
    fin = core.getTime() + config.DUR_CONECTANDO
    while core.getTime() < fin:
        espera.draw()
        escalas.dibujar_salto(salto)
        win.flip()
        if escalas.salto_pedido(salto, raton):
            escalas.soltar_raton(win, raton)
            break

    datos = {"episodio": n_episodio, "tipo": tipo}

    # el agente pide la situación (saludo neutral, idéntico entre condiciones,
    # SIEMPRE guionado: tiene que pedirla sí o sí)
    clave_saludo = "saludo" if n_episodio == 1 else "saludo2"
    conv.agente_dice(guiones[clave_saludo][0],
                     etiqueta_marcador="agente_pide_situacion")
    if agente is not None:
        agente.saluda(guiones[clave_saludo][0])

    # el participante la cuenta acá, en el chat
    situacion, lat_sit = conv.esperar_participante(
        timeout=config.TIMEOUT_SITUACION,
        minimo_caracteres=config.MIN_CARACTERES_SITUACION,
        marcador="situacion_revelada")
    datos["situacion"] = situacion
    datos["situacion_caracteres"] = len(situacion)
    datos["latencia_situacion"] = lat_sit
    if agente is not None:
        agente.escucha(situacion or "(no responde)")

    # tres turnos del agente, con respuesta libre del participante entre medio
    for turno in (1, 2, 3):
        if agente is not None:
            # se genera en un hilo; mientras tanto la pantalla sigue "en
            # línea", como alguien que está leyendo. La latencia visible se
            # aplica después en agente_dice(), en función del largo.
            pedido = agente.responder_en_hilo(guiones[tipo][turno])
            while not pedido.listo():
                conv.dibujar()
            texto_turno, origen = pedido.resultado()
        else:
            texto_turno, origen = guiones[tipo][turno], "guion"
        conv.agente_dice(texto_turno,
                         etiqueta_marcador="agente_mensaje_%d" % turno,
                         origen=origen)
        if turno < 3:
            texto, latencia = conv.esperar_participante(timeout=90)
            datos["respuesta_%d" % turno] = texto
            datos["latencia_%d" % turno] = latencia
            if agente is not None:
                agente.escucha(texto or "(no responde)")

    # ventana final de respuesta libre: puede contestar o no.
    # La latencia acá es una VD conductual del diseño.
    registro.marcar("respuesta_libre_inicio", tipo)
    texto, latencia = conv.esperar_participante(
        timeout=config.VENTANA_RESPUESTA_LIBRE)
    datos["respuesta_final"] = texto
    datos["latencia_final"] = latencia
    datos["respondio_al_final"] = int(bool(texto))

    registro.marcar("episodio_fin", "%d_%s" % (n_episodio, tipo))
    return datos


# =====================================================================
# 3. Programa principal
# =====================================================================
def main():
    info = dialogo_inicial()
    guiones = cargar_guiones()

    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = "S1_%s_%s_%s" % (info["id_participante"], info["condicion_agente"], sello)
    carpeta = os.path.join(RAIZ, "datos")
    os.makedirs(carpeta, exist_ok=True)

    win = visual.Window(
        size=config.TAMANO_VENTANA, fullscr=config.PANTALLA_COMPLETA,
        color=config.COLOR_FONDO, units="height", allowGUI=False,
        winType="pyglet")
    win.mouseVisible = True

    event.globalKeys.clear()
    event.globalKeys.add(key="q", modifiers=["ctrl"], func=core.quit)

    reloj = core.Clock()
    registro = RegistroEventos(
        os.path.join(carpeta, base + "_eventos.csv"),
        reloj, backend=config.BACKEND_MARCADORES)
    registro.marcar("inicio_experimento", info["condicion_agente"])

    conv = Chat(win, registro, config.ETIQUETA_AGENTE[info["condicion_agente"]])
    respuestas = dict(info)
    respuestas["archivo"] = base

    # Modo de agente: guionado (el diseño original) o LLM vía OpenRouter.
    usar_llm = config.AGENTE == "llm"
    if usar_llm and not cargar_api_key():
        print("AVISO: AGENTE='llm' pero no hay API key (OPENROUTER_API_KEY "
              "u openrouter_key.txt). Todos los turnos van a caer al guion.")
    respuestas["agente"] = config.AGENTE
    respuestas["modo_test"] = config.MODO_TEST
    if config.MODO_TEST:
        print("AVISO: MODO_TEST activo. Se puede saltear cada pantalla con "
              "el botón 'Saltar' o con %s, y lo salteado queda vacío en los "
              "CSV. No sirve para participantes."
              % config.TECLA_SALTO.upper())
    if usar_llm:
        respuestas["modelo_llm"] = config.MODELO_LLM

    # ---------------------------------------------------------------
    # Consentimiento e instrucciones
    # ---------------------------------------------------------------
    escalas.pantalla_texto(
        win,
        "Gracias por participar.\n\n"
        "Vas a tener dos conversaciones breves por chat y vamos a hacerte "
        "algunas preguntas entre una y otra.\n\n"
        "Durante todo el estudio vamos a registrar tu actividad "
        "electrodérmica con los sensores que tenés en los dedos. No duele "
        "y no vas a sentir nada.\n\n"
        "Podés dejar de participar en cualquier momento, sin dar "
        "explicaciones y sin ninguna consecuencia.",
        titulo="Antes de empezar")

    # ---------------------------------------------------------------
    # Línea base fisiológica
    # ---------------------------------------------------------------
    escalas.pantalla_texto(
        win,
        "Primero necesitamos unos minutos de registro en reposo.\n\n"
        "Vas a ver una cruz en el centro de la pantalla. Quedate cómoda/o, "
        "mirala y tratá de moverte lo menos posible.",
        titulo="Registro en reposo")

    registro.marcar("baseline_inicio")
    escalas.cuenta_regresiva(win, config.DUR_BASELINE)
    registro.marcar("baseline_fin")

    # OJO: en la línea base NO van los ítems de autenticidad. Todavía no hay
    # interlocutor sobre el cual opinar.
    medidas_base = escalas.bloque_medidas(win, registro, "baseline",
                                          incluir_autenticidad=False)
    respuestas.update({"baseline_" + k: v for k, v in medidas_base.items()})

    # ---------------------------------------------------------------
    # Historia de cobertura (acá se manipula el factor entre-sujetos)
    # ---------------------------------------------------------------
    escalas.pantalla_texto(
        win, config.COBERTURA[info["condicion_agente"]],
        titulo="La conversación")

    # ---------------------------------------------------------------
    # Los dos episodios, en el orden contrabalanceado.
    # La situación personal se cuenta dentro de cada chat.
    # ---------------------------------------------------------------
    secuencia = (["validacion", "rechazo"] if info["orden"] == 1
                 else ["rechazo", "validacion"])

    conductual = []
    for i, tipo in enumerate(secuencia, start=1):
        # un AgenteLLM nuevo por episodio: cada conversación arranca de cero
        agente = AgenteLLM(tipo) if usar_llm else None
        datos = correr_episodio(win, conv, registro, guiones, tipo, i,
                                agente=agente)
        conductual.append(datos)
        respuestas["situacion_%d" % i] = datos["situacion"]

        medidas = escalas.bloque_medidas(win, registro, tipo)
        respuestas.update({"%s_%s" % (tipo, k): v for k, v in medidas.items()})

        if i < len(secuencia):
            escalas.pantalla_texto(
                win,
                "Terminó la primera conversación.\n\n"
                "Cuando estés lista/o, seguimos con la segunda.",
                titulo="Pausa")

    # ---------------------------------------------------------------
    # Chequeo de manipulación + funnel debriefing
    # ---------------------------------------------------------------
    registro.marcar("chequeo_manipulacion")

    respuestas["creencia_persona_real"] = escalas.preguntar_escala(
        win,
        "¿En qué medida creíste que estabas interactuando con una persona real?",
        list(range(0, 101, 10)),
        ["0\nseguro/a: era una IA"] + [""] * 4 + ["50\nno sabía"] +
        [""] * 4 + ["100\nseguro/a: era una persona"])

    respuestas["sospecha_1"] = escalas.preguntar_texto(
        win, "¿Qué te pareció que estaba pasando en este estudio? "
             "¿Qué creés que estábamos estudiando?", minimo_caracteres=1)
    respuestas["sospecha_2"] = escalas.preguntar_texto(
        win, "¿Hubo algo que te resultara raro o poco creíble durante las "
             "conversaciones?", minimo_caracteres=1)
    respuestas["sospecha_3"] = escalas.preguntar_texto(
        win, "¿Pensaste en algún momento que tu interlocutor no era lo que te "
             "habíamos dicho? Si sí, ¿en qué momento y por qué?",
        minimo_caracteres=1)

    # ---------------------------------------------------------------
    # Debriefing
    # ---------------------------------------------------------------
    escalas.pantalla_texto(
        win,
        "Ahora tenemos que contarte algo importante.\n\n"
        "En las dos conversaciones NO había ni otra persona ni una "
        "inteligencia artificial respondiéndote. Todos los mensajes que "
        "recibiste estaban escritos de antemano y eran exactamente los mismos "
        "para todos los participantes.\n\n"
        "Lo hicimos así porque queríamos estudiar si CREER que del otro lado "
        "hay una persona o una IA cambia cómo reaccionamos, emocional y "
        "fisiológicamente. Para eso el contenido tenía que ser idéntico.\n\n"
        "Los mensajes de rechazo no tenían nada que ver con vos ni con lo que "
        "contaste: eran los mismos para todo el mundo.\n\n"
        "Si querés hablar de cómo te sentiste, avisale a quien te está "
        "acompañando.",
        titulo="Sobre lo que acabás de hacer")

    respuestas["consiente_tras_debriefing"] = escalas.preguntar_escala(
        win,
        "Ahora que sabés cómo fue el estudio, ¿nos autorizás a usar tus datos?",
        [0, 1], ["0\nno, bórrenlos", "1\nsí, úsenlos"])

    escalas.pantalla_texto(
        win, "Listo. Muchas gracias por participar.",
        pie="Presioná ESPACIO para terminar")

    # ---------------------------------------------------------------
    # Guardar
    # ---------------------------------------------------------------
    registro.marcar("fin_experimento")

    with open(os.path.join(carpeta, base + "_respuestas.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for clave in sorted(respuestas):
            w.writerow([clave, respuestas[clave]])

    with open(os.path.join(carpeta, base + "_conductual.csv"), "w",
              newline="", encoding="utf-8") as f:
        campos = sorted({k for d in conductual for k in d})
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for d in conductual:
            w.writerow(d)

    with open(os.path.join(carpeta, base + "_chat.csv"), "w",
              newline="", encoding="utf-8") as f:
        campos = ["autor", "texto", "origen", "t_experimento_s", "latencia_s"]
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for fila in conv.transcripcion:
            w.writerow(fila)

    registro.cerrar()
    win.close()
    core.quit()


if __name__ == "__main__":
    main()
