# -*- coding: utf-8 -*-
"""
Pantallas de instrucciones y escalas de autoinforme.

SAM: por ahora se presenta como escala numérica de 9 puntos con anclas
verbales. Si quieren la versión pictórica original (los monigotes), hay que
poner los PNG en stim/sam/ y el código ya los dibuja arriba de la escala.
Ver el README.
"""

import os
import csv

from psychopy import visual, core, event

import config

CARPETA_SAM = os.path.join(os.path.dirname(__file__), "stim", "sam")
USAR_IMAGENES_SAM = os.path.isdir(CARPETA_SAM)


# ---------------------------------------------------------------------
def _boton(win, texto, pos=(0, -0.40)):
    caja = visual.Rect(win, width=0.24, height=0.075, pos=pos,
                       fillColor=config.COLOR_ACENTO, lineColor=None)
    etiqueta = visual.TextStim(win, text=texto, font=config.FUENTE,
                               height=0.026, color="#FFFFFF", pos=pos)
    return caja, etiqueta


def pantalla_texto(win, texto, pie="Presioná ESPACIO para continuar",
                   titulo=None, altura=0.032):
    """Muestra un bloque de texto y espera la barra espaciadora."""
    cuerpo = visual.TextStim(
        win, text=texto, font=config.FUENTE, height=altura,
        color=config.COLOR_TEXTO, pos=(0, 0.02), wrapWidth=1.15,
        alignText="left")
    encabezado = None
    if titulo:
        encabezado = visual.TextStim(
            win, text=titulo, font=config.FUENTE, height=0.045, bold=True,
            color=config.COLOR_ACENTO, pos=(0, 0.34), wrapWidth=1.15)
    aviso = visual.TextStim(
        win, text=pie, font=config.FUENTE, height=0.024,
        color=config.COLOR_TENUE, pos=(0, -0.42))

    event.clearEvents()
    while True:
        if encabezado:
            encabezado.draw()
        cuerpo.draw()
        aviso.draw()
        win.flip()
        if event.getKeys(keyList=["space"]):
            return


def cuenta_regresiva(win, duracion, texto="Descansá. Mirá la cruz y tratá de "
                                          "quedarte quieta/o."):
    """Línea base fisiológica: cruz de fijación durante `duracion` segundos."""
    cruz = visual.TextStim(win, text="+", font=config.FUENTE, height=0.12,
                           color=config.COLOR_TEXTO, pos=(0, 0))
    leyenda = visual.TextStim(win, text=texto, font=config.FUENTE, height=0.026,
                              color=config.COLOR_TENUE, pos=(0, -0.32),
                              wrapWidth=1.0)
    fin = core.getTime() + duracion
    while core.getTime() < fin:
        cruz.draw()
        leyenda.draw()
        win.flip()


# ---------------------------------------------------------------------
def preguntar_escala(win, enunciado, ticks, etiquetas, imagenes_sam=None):
    """Escala tipo Likert / SAM. Devuelve el valor elegido."""
    texto = visual.TextStim(
        win, text=enunciado, font=config.FUENTE, height=0.034,
        color=config.COLOR_TEXTO, pos=(0, 0.28), wrapWidth=1.15)

    escala = visual.Slider(
        win, ticks=ticks, labels=etiquetas, granularity=1,
        pos=(0, -0.08), size=(1.0, 0.05), style="rating",
        font=config.FUENTE, labelHeight=0.024, labelWrapWidth=0.30,
        color=config.COLOR_TEXTO, fillColor=config.COLOR_ACENTO,
        borderColor=config.COLOR_TENUE)
    try:
        escala.marker.color = config.COLOR_ACENTO
    except Exception:
        pass

    figuras = []
    if imagenes_sam and USAR_IMAGENES_SAM:
        n = len(imagenes_sam)
        for i, nombre in enumerate(imagenes_sam):
            ruta = os.path.join(CARPETA_SAM, nombre)
            if os.path.exists(ruta):
                x = -0.44 + i * (0.88 / max(1, n - 1))
                figuras.append(visual.ImageStim(
                    win, image=ruta, pos=(x, 0.10), size=(0.11, 0.11)))

    caja, etiqueta = _boton(win, "Continuar")
    aviso = visual.TextStim(
        win, text="Elegí una opción para continuar", font=config.FUENTE,
        height=0.022, color=config.COLOR_TENUE, pos=(0, -0.30))
    raton = event.Mouse(win=win)
    event.clearEvents()

    while True:
        texto.draw()
        for f in figuras:
            f.draw()
        escala.draw()
        valor = escala.getRating()
        if valor is None:
            aviso.draw()
        else:
            caja.draw()
            etiqueta.draw()
        win.flip()

        if valor is not None and raton.isPressedIn(caja):
            while raton.getPressed()[0]:
                win.flip()
            return valor
        if valor is not None and event.getKeys(keyList=["space", "return"]):
            return valor


def preguntar_texto(win, enunciado, minimo_caracteres=0, alto=0.26):
    """Respuesta abierta en pantalla propia. Devuelve el texto escrito."""
    texto = visual.TextStim(
        win, text=enunciado, font=config.FUENTE, height=0.032,
        color=config.COLOR_TEXTO, pos=(0, 0.30), wrapWidth=1.15)

    entrada = visual.TextBox2(
        win, text="", font=config.FUENTE, pos=(0, 0.02),
        size=(1.05, alto), letterHeight=config.ALTURA_LETRA,
        color=config.COLOR_TEXTO, fillColor="#FFFFFF",
        borderColor="#D0D0D4", borderWidth=2, padding=0.016,
        anchor="center", alignment="top-left", editable=True,
        placeholder="Escribí acá…")

    caja, etiqueta = _boton(win, "Continuar", pos=(0, -0.34))
    aviso = visual.TextStim(
        win, text="", font=config.FUENTE, height=0.022,
        color=config.COLOR_TENUE, pos=(0, -0.42))

    raton = event.Mouse(win=win)
    try:
        win.currentEditable = entrada
    except Exception:
        pass
    event.clearEvents()

    while True:
        contenido = entrada.getText().strip()
        listo = len(contenido) >= minimo_caracteres
        aviso.text = ("" if listo else
                      "Escribí al menos %d caracteres (llevás %d)."
                      % (minimo_caracteres, len(contenido)))

        texto.draw()
        entrada.draw()
        aviso.draw()
        if listo:
            caja.draw()
            etiqueta.draw()
        win.flip()

        if listo and raton.isPressedIn(caja):
            while raton.getPressed()[0]:
                win.flip()
            try:
                win.removeEditable(entrada)
            except Exception:
                pass
            return contenido


# ---------------------------------------------------------------------
# Bloques de medidas
# ---------------------------------------------------------------------
SUDS_TICKS = list(range(0, 101, 10))
SUDS_ETIQUETAS = ["0\nsin malestar"] + [""] * 4 + ["50"] + [""] * 4 + \
                 ["100\nmalestar máximo"]

SAM_VALENCIA = ("En este momento, ¿cómo te sentís?",
                list(range(1, 10)),
                ["1\nmuy mal"] + [""] * 3 + ["5\nneutral"] + [""] * 3 + ["9\nmuy bien"],
                ["val_%d.png" % i for i in range(1, 10)])

SAM_AROUSAL = ("En este momento, ¿qué tan activada/o o alterada/o te sentís?",
               list(range(1, 10)),
               ["1\nmuy calma/o"] + [""] * 3 + ["5\nintermedio"] + [""] * 3 +
               ["9\nmuy activada/o"],
               ["aro_%d.png" % i for i in range(1, 10)])

# Autenticidad / empatía percibida, adaptada de Rubin et al. (2025).
# El ítem 4 es inverso: hay que recodificarlo antes de promediar.
ITEMS_AUTENTICIDAD = [
    ("aut1", "Sentí que mi interlocutor entendió genuinamente lo que le conté."),
    ("aut2", "La respuesta que recibí me pareció auténtica."),
    ("aut3", "Sentí que a mi interlocutor le importaba cómo me sentía."),
    ("aut4_inv", "La respuesta me pareció mecánica o automática."),
]
LIKERT7 = (list(range(1, 8)),
           ["1\nmuy en desacuerdo"] + [""] * 5 + ["7\nmuy de acuerdo"])




# ---------------------------------------------------------------------
# PANAS
# ---------------------------------------------------------------------
# 20 ítems (10 PA / 10 NA), en el orden canónico de Watson, Clark & Tellegen
# (1988). Versión ESTADO: se pregunta por el momento presente, no por el
# último mes. Traducción según la adaptación al español rioplatense de
# Moriondo et al. (2012) — CONVIENE COTEJAR LOS TÉRMINOS CON EL ARTÍCULO
# ORIGINAL antes de correr participantes.
#
# Se presenta en grilla de 10 ítems por pantalla, no de a uno. Con 3
# administraciones (línea base + los dos episodios) son 60 respuestas: una
# por pantalla estiraría el intervalo entre episodios lo suficiente como para
# que la activación fisiológica se disipe antes del segundo.

PANAS_TICKS = [1, 2, 3, 4, 5]
PANAS_ANCLAS = ["muy poco\no nada", "un poco", "moderada-\nmente",
                "bastante", "extremada-\nmente"]


def cargar_panas():
    ruta = os.path.join(os.path.dirname(__file__), "stim", "panas.csv")
    with open(ruta, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def preguntar_panas(win, items_por_pagina=10):
    """PANAS-estado en grilla. Devuelve {clave: 1..5} más los totales PA/NA."""
    items = cargar_panas()
    respuestas = {}
    raton = event.Mouse(win=win)

    instruccion = visual.TextStim(
        win, text="Indicá en qué medida te sentís así EN ESTE MOMENTO.",
        font=config.FUENTE, height=0.030, color=config.COLOR_TEXTO,
        pos=(0, 0.44), wrapWidth=1.15)

    x_centro, ancho = 0.12, 0.42
    x_primera = x_centro - ancho / 2.0
    paso = ancho / (len(PANAS_TICKS) - 1)
    encabezados = [
        visual.TextStim(win, text=PANAS_ANCLAS[k], font=config.FUENTE,
                        height=0.017, color=config.COLOR_TENUE,
                        pos=(x_primera + k * paso, 0.355), wrapWidth=0.115)
        for k in range(len(PANAS_TICKS))]

    for inicio in range(0, len(items), items_por_pagina):
        pagina = items[inicio:inicio + items_por_pagina]
        sliders, etiquetas = [], []
        y0, dy = 0.27, 0.062

        for j, it in enumerate(pagina):
            y = y0 - j * dy
            # OJO: style="radio" NO sirve acá. En PsychoPy, categorical es
            # True para todo slider radio, y entonces .rating devuelve
            # self.labels[...]: con labels=None crashea al primer clic y con
            # etiquetas vacías guarda '' en vez del número. style="rating"
            # deja categorical=False y devuelve el valor numérico.
            sliders.append(visual.Slider(
                win, ticks=PANAS_TICKS, labels=None, granularity=1,
                style="rating", pos=(x_centro, y), size=(ancho, 0.022),
                color=config.COLOR_TEXTO, fillColor=config.COLOR_ACENTO,
                borderColor=config.COLOR_TENUE))
            etiquetas.append(visual.TextStim(
                win, text=it["item"], font=config.FUENTE, height=0.024,
                color=config.COLOR_TEXTO, pos=(-0.13, y),
                anchorHoriz="right", alignText="right", wrapWidth=0.55))

        caja, etiqueta = _boton(win, "Continuar", pos=(0, -0.43))
        aviso = visual.TextStim(
            win, text="", font=config.FUENTE, height=0.022,
            color=config.COLOR_TENUE, pos=(0, -0.43))
        event.clearEvents()

        while True:
            instruccion.draw()
            for h in encabezados:
                h.draw()
            for sl, lb in zip(sliders, etiquetas):
                lb.draw()
                sl.draw()

            faltan = sum(1 for sl in sliders if sl.getRating() is None)
            if faltan:
                aviso.text = ("Falta 1 ítem" if faltan == 1
                              else "Faltan %d ítems" % faltan)
                aviso.draw()
            else:
                caja.draw()
                etiqueta.draw()
            win.flip()

            if not faltan and raton.isPressedIn(caja):
                while raton.getPressed()[0]:
                    win.flip()
                break

        for it, sl in zip(pagina, sliders):
            respuestas[it["clave"]] = sl.getRating()

    # totales de subescala (rango 10-50 cada una)
    for sub in ("PA", "NA"):
        respuestas[sub + "_total"] = sum(
            respuestas[it["clave"]] for it in items if it["subescala"] == sub)
    return respuestas


def bloque_medidas(win, registro, momento, incluir_autenticidad=True,
                   incluir_panas=True):
    """SUDS + SAM (+ autenticidad, sólo si ya hubo interlocutor).

    Orden: SUDS -> SAM -> autenticidad -> PANAS.

    En la LÍNEA BASE hay que llamarlo con incluir_autenticidad=False: todavía
    no existe ningún interlocutor sobre el cual opinar, así que preguntar
    "¿mi interlocutor me entendió?" no tiene referente y además adelanta la
    historia de cobertura antes de tiempo.
    """
    registro.marcar("medidas_inicio", momento)
    r = {}

    r["suds"] = preguntar_escala(
        win, "¿Cuánto malestar sentís en este momento?",
        SUDS_TICKS, SUDS_ETIQUETAS)

    enun, ticks, etiq, imgs = SAM_VALENCIA
    r["sam_valencia"] = preguntar_escala(win, enun, ticks, etiq, imgs)

    enun, ticks, etiq, imgs = SAM_AROUSAL
    r["sam_arousal"] = preguntar_escala(win, enun, ticks, etiq, imgs)

    if incluir_autenticidad:
        ticks, etiq = LIKERT7
        for clave, enunciado in ITEMS_AUTENTICIDAD:
            r[clave] = preguntar_escala(win, enunciado, ticks, etiq)

    # El PANAS va ÚLTIMO a propósito: son 20 ítems, y SUDS/SAM son las medidas
    # sensibles al tiempo (hay que tomarlas lo antes posible tras el episodio,
    # mientras la activación todavía no se disipó).
    if incluir_panas:
        registro.marcar("panas_inicio", momento)
        r.update(preguntar_panas(win))
        registro.marcar("panas_fin", momento)

    registro.marcar("medidas_fin", momento)
    return r
