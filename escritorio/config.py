# -*- coding: utf-8 -*-
"""
Estudio 1 — Configuración del experimento de escritorio (PsychoPy).

Acá vive sólo lo específico de esta plataforma: modo, ventana, apariencia,
backend de marcadores y puertos.

El CONTENIDO del experimento (prosa de las pantallas, escalas, guiones,
códigos de marcador, prompts del agente) NO está acá: vive en protocolo/ y se
lee con comun.protocolo. Así la demo web y el escritorio corren exactamente
el mismo experimento.
"""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from comun import protocolo

# =====================================================================
# MODO
# =====================================================================
# True  -> tiempos cortos, ventana chica. Para probar el flujo en 3 min.
# False -> tiempos reales del protocolo. Para correr participantes.
MODO_DEMO = True

PANTALLA_COMPLETA = not MODO_DEMO
TAMANO_VENTANA = (1280, 800)          # sólo si PANTALLA_COMPLETA = False

# Modo test: cada pantalla suma un botón "Saltar", y TECLA_SALTO hace lo
# mismo desde el teclado. Sirve para recorrer el flujo entero sin contestar
# las escalas ni esperar los tiempos. Lo que se saltea queda VACÍO en los
# CSV (las subescalas del PANAS incompletas no suman total), así que una
# corrida de test se distingue de una real. NUNCA correr participantes con
# esto en True: queda registrado en _respuestas.csv como modo_test.
MODO_TEST = False
TECLA_SALTO = "f9"

# =====================================================================
# PARÁMETROS DEL PROTOCOLO
# =====================================================================
# Los tiempos y la fórmula de latencia viven en protocolo/parametros.json,
# porque son parte del diseño y valen igual para la demo web. La latencia es
# DETERMINISTA a propósito: es función del largo del mensaje, no del azar, así
# que no puede diferir entre las condiciones Humano / IA.
PARAMETROS = protocolo.parametros("demo" if MODO_DEMO else "real")

# =====================================================================
# AGENTE
# =====================================================================
# "guionado" -> los mensajes salen de protocolo/guiones.csv (el diseño original:
#               contenido y latencia idénticos entre condiciones).
# "llm"      -> los genera un modelo vía OpenRouter (ver comun/agente_llm.py).
#               El saludo que pide la situación sigue guionado igual, y si
#               la API falla el turno cae al guion. OJO: modo experimental,
#               no calibrado con el comité de ética; lo que escribe el
#               participante viaja a OpenRouter y al proveedor del modelo.
# La key se lee de OPENROUTER_API_KEY o del archivo openrouter_key.txt.
# El modelo y su temperatura están en protocolo/prompts.json.
AGENTE = "guionado"

TIMEOUT_LLM = 20      # s de espera de la API antes de caer al guion

# =====================================================================
# SINCRONIZACIÓN CON EL EQUIPO FISIOLÓGICO
# =====================================================================
# "csv"      -> sólo log de eventos con timestamps (sirve para Empatica E4,
#               Shimmer3 y cualquier equipo que grabe en su propio reloj)
# "lsl"      -> además publica un stream de marcadores por Lab Streaming Layer
# "serial"   -> además manda un byte TTL por puerto serie
# "paralelo" -> además manda un byte por puerto paralelo (no existe en Mac)
BACKEND_MARCADORES = "csv"

PUERTO_SERIAL   = "/dev/tty.usbserial-XXXX"   # sólo si BACKEND_MARCADORES = "serial"
BAUDIOS_SERIAL  = 115200
DIRECCION_PARALELO = 0x0378                    # sólo si BACKEND_MARCADORES = "paralelo"

# =====================================================================
# APARIENCIA
# =====================================================================
COLOR_FONDO       = "#F2F3F5"
COLOR_TEXTO       = "#1C1C1E"
COLOR_TENUE       = "#8A8A8E"
COLOR_BURBUJA_AG  = "#FFFFFF"   # mensajes del agente (izquierda)
COLOR_BURBUJA_PA  = "#D8E7FA"   # mensajes del participante (derecha)
COLOR_BARRA       = "#FFFFFF"
COLOR_ACENTO      = "#3070C6"

FUENTE            = "Helvetica"
ALTURA_LETRA      = 0.026       # unidades 'height'
ANCHO_BURBUJA_MAX = 0.52
