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
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from psychopy import visual, core, event, gui

import config
import escalas
from comun.agente_llm import AgenteLLM, cargar_api_key
from comun import protocolo, salida
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
        win, text=protocolo.textos()["conectando"], font=config.FUENTE,
        height=0.040, color=config.COLOR_TENUE, pos=(0, 0))
    salto = escalas.boton_salto(win)
    raton = event.Mouse(win=win)
    fin = core.getTime() + config.PARAMETROS["dur_conectando"]
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
        timeout=config.PARAMETROS["timeout_situacion"],
        minimo_caracteres=config.PARAMETROS["min_caracteres_situacion"],
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
        timeout=config.PARAMETROS["ventana_respuesta_libre"])
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
    base = salida.nombre_base(info["id_participante"],
                              info["condicion_agente"], sello)
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

    txt = protocolo.textos()
    conv = Chat(win, registro, txt["etiqueta_agente"][info["condicion_agente"]])
    respuestas = dict(info)
    respuestas["archivo"] = base
    respuestas["plataforma"] = "escritorio"

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
        respuestas["modelo_llm"] = protocolo.prompts()["modelo"]

    # ---------------------------------------------------------------
    # Consentimiento e instrucciones
    # ---------------------------------------------------------------
    escalas.pantalla_texto(win, txt["consentimiento"]["cuerpo"],
                           titulo=txt["consentimiento"]["titulo"])

    # ---------------------------------------------------------------
    # Línea base fisiológica
    # ---------------------------------------------------------------
    escalas.pantalla_texto(win, txt["reposo"]["cuerpo"],
                           titulo=txt["reposo"]["titulo"])

    registro.marcar("baseline_inicio")
    escalas.cuenta_regresiva(win, config.PARAMETROS["dur_baseline"])
    registro.marcar("baseline_fin")

    # OJO: en la línea base NO van los ítems de autenticidad. Todavía no hay
    # interlocutor sobre el cual opinar.
    medidas_base = escalas.bloque_medidas(win, registro, "baseline",
                                          incluir_autenticidad=False)
    respuestas.update({"baseline_" + k: v for k, v in medidas_base.items()})

    # ---------------------------------------------------------------
    # Historia de cobertura (acá se manipula el factor entre-sujetos)
    # ---------------------------------------------------------------
    escalas.pantalla_texto(win, txt["cobertura"][info["condicion_agente"]],
                           titulo=txt["cobertura_titulo"])

    # ---------------------------------------------------------------
    # Los dos episodios, en el orden contrabalanceado.
    # La situación personal se cuenta dentro de cada chat.
    # ---------------------------------------------------------------
    secuencia = (["validacion", "rechazo"] if info["orden"] == 1
                 else ["rechazo", "validacion"])

    conductual = []
    for i, tipo in enumerate(secuencia, start=1):
        # un AgenteLLM nuevo por episodio: cada conversación arranca de cero
        agente = (AgenteLLM(tipo, timeout=config.TIMEOUT_LLM)
                  if usar_llm else None)
        datos = correr_episodio(win, conv, registro, guiones, tipo, i,
                                agente=agente)
        conductual.append(datos)
        respuestas["situacion_%d" % i] = datos["situacion"]

        medidas = escalas.bloque_medidas(win, registro, tipo)
        respuestas.update({"%s_%s" % (tipo, k): v for k, v in medidas.items()})

        if i < len(secuencia):
            escalas.pantalla_texto(win, txt["pausa"]["cuerpo"],
                                   titulo=txt["pausa"]["titulo"])

    # ---------------------------------------------------------------
    # Chequeo de manipulación + funnel debriefing
    # ---------------------------------------------------------------
    registro.marcar("chequeo_manipulacion")

    chequeo = txt["chequeo"]
    creencia = chequeo["creencia_persona_real"]
    respuestas["creencia_persona_real"] = escalas.preguntar_escala(
        win, creencia["enunciado"], creencia["ticks"], creencia["etiquetas"])

    for clave in ("sospecha_1", "sospecha_2", "sospecha_3"):
        respuestas[clave] = escalas.preguntar_texto(
            win, chequeo[clave], minimo_caracteres=1)

    # ---------------------------------------------------------------
    # Debriefing
    # ---------------------------------------------------------------
    # El debriefing depende del modo con el que corrió el agente: con "llm"
    # los mensajes no estaban escritos de antemano, y decírselo así sería
    # mentirle justo en la pantalla donde se le deja de mentir.
    deb = protocolo.debriefing(config.AGENTE)
    escalas.pantalla_texto(win, deb["cuerpo"], titulo=deb["titulo"])

    consiente = chequeo["consiente_tras_debriefing"]
    respuestas["consiente_tras_debriefing"] = escalas.preguntar_escala(
        win, consiente["enunciado"], consiente["ticks"], consiente["etiquetas"])

    escalas.pantalla_texto(win, txt["cierre"]["cuerpo"],
                           pie=txt["cierre"]["pie"])

    # ---------------------------------------------------------------
    # Guardar
    # ---------------------------------------------------------------
    registro.marcar("fin_experimento")

    # _eventos.csv no va acá: RegistroEventos lo viene escribiendo en
    # streaming desde que arrancó la sesión.
    salida.escribir_todo(carpeta, base,
                         respuestas=respuestas,
                         conductual=conductual,
                         chat=conv.transcripcion)

    registro.cerrar()
    win.close()
    core.quit()


if __name__ == "__main__":
    main()
