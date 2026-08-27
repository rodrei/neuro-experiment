# -*- coding: utf-8 -*-
"""
Estudio 1 — Parámetros de configuración.

Todo lo que el equipo puede querer cambiar sin tocar el código vive acá.
"""

# =====================================================================
# MODO
# =====================================================================
# True  -> tiempos cortos, ventana chica. Para probar el flujo en 3 min.
# False -> tiempos reales del protocolo. Para correr participantes.
MODO_DEMO = True

PANTALLA_COMPLETA = not MODO_DEMO
TAMANO_VENTANA = (1280, 800)          # sólo si PANTALLA_COMPLETA = False

# =====================================================================
# TIEMPOS (segundos)
# =====================================================================
DUR_BASELINE          = 15 if MODO_DEMO else 300    # línea base en reposo (5 min)
DUR_CONECTANDO        = 3  if MODO_DEMO else 8      # pantalla "conectando..."
DUR_LECTURA_MIN       = 1.0                          # piso antes de "escribiendo"
VENTANA_RESPUESTA_LIBRE = 20 if MODO_DEMO else 120  # ventana final de respuesta libre

# El participante cuenta su situación DENTRO del chat, cuando el interlocutor
# se la pide. El mínimo de caracteres evita que la segunda salga en dos
# palabras; el tope de espera evita que la sesión se cuelgue si se traba.
MIN_CARACTERES_SITUACION = 120
TIMEOUT_SITUACION        = 60 if MODO_DEMO else 300

# Latencia del agente. DETERMINISTA a propósito: es función del largo del
# mensaje, no del azar. Así dos participantes que reciben el mismo mensaje
# esperan exactamente lo mismo, y la latencia no puede diferir entre las
# condiciones Humano / IA (que es justamente el control que pide el diseño).
LATENCIA_BASE         = 1.2      # s de "pensando" antes de "escribiendo..."
LATENCIA_POR_CARACTER = 0.045    # s por carácter mientras dice "escribiendo..."
LATENCIA_MAX          = 12.0     # tope, para que no se vuelva absurdo

# =====================================================================
# HISTORIA DE COBERTURA
# =====================================================================
# Mismo nombre en las dos condiciones: si el nombre cambiara entre
# condiciones, sería una diferencia adicional a la fuente atribuida.
NOMBRE_AGENTE = "Alex"

ETIQUETA_AGENTE = {
    "humano": "Alex · otra persona participando del estudio",
    "ia":     "Alex · asistente conversacional (IA)",
}

COBERTURA = {
    "humano": (
        "En unos segundos vas a quedar conectada/o por chat con "
        "OTRA PERSONA que está participando del estudio en este momento, "
        "desde otra sala.\n\n"
        "Es alguien que no conocés y que tampoco te conoce. Va a leer lo que "
        "escribas y te va a responder en tiempo real.\n\n"
        "Van a tener dos conversaciones. En cada una te va a pedir que le "
        "cuentes algo que te haya pasado."
    ),
    "ia": (
        "En unos segundos vas a quedar conectada/o por chat con un "
        "ASISTENTE CONVERSACIONAL DE INTELIGENCIA ARTIFICIAL, "
        "basado en un modelo de lenguaje.\n\n"
        "No es una persona. Va a leer lo que escribas y te va a responder "
        "en tiempo real.\n\n"
        "Van a tener dos conversaciones. En cada una te va a pedir que le "
        "cuentes algo que te haya pasado."
    ),
}

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

# Códigos de marcador (los que quedan en el log y se mandan al equipo)
MARCADORES = {
    "inicio_experimento":   1,
    "baseline_inicio":     10,
    "baseline_fin":         11,
    "episodio_inicio":      20,
    "agente_pide_situacion": 19,
    "situacion_revelada":   18,
    "agente_mensaje_1":     21,
    "agente_mensaje_2":     22,
    "agente_mensaje_3":     23,
    "participante_mensaje": 30,
    "respuesta_libre_inicio": 35,
    "episodio_fin":         40,
    "medidas_inicio":       50,
    "medidas_fin":          51,
    "panas_inicio":         52,
    "panas_fin":            53,
    "chequeo_manipulacion": 60,
    "fin_experimento":      99,
}

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
