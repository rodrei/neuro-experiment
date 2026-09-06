# -*- coding: utf-8 -*-
"""
Pantallas de instrucciones y escalas de autoinforme.

SAM: por ahora se presenta como escala numérica de 9 puntos con anclas
verbales. Si quieren la versión pictórica original (los monigotes), hay que
poner los PNG en protocolo/sam/ y el código ya los dibuja arriba de la escala.
Ver el README.
"""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from psychopy import visual, core, event

import config
from comun import protocolo

CARPETA_SAM = os.path.join(RAIZ, "protocolo", "sam")
USAR_IMAGENES_SAM = os.path.isdir(CARPETA_SAM)


# ---------------------------------------------------------------------
def _boton(win, texto, pos=(0, -0.40), tamano=(0.24, 0.075), altura=0.026,
           color=None):
    caja = visual.Rect(win, width=tamano[0], height=tamano[1], pos=pos,
                       fillColor=color or config.COLOR_ACENTO, lineColor=None)
    etiqueta = visual.TextStim(win, text=texto, font=config.FUENTE,
                               height=altura, color="#FFFFFF", pos=pos)
    return caja, etiqueta


# ---------------------------------------------------------------------
# Modo test: saltear pantallas
# ---------------------------------------------------------------------
# Las usan también chat.py y estudio1.py, para que el botón esté en el mismo
# lugar en todas las pantallas. Abajo a la derecha: ahí no hay nada en
# ninguna pantalla, ni siquiera en la relación de aspecto más angosta.
POS_SALTO = (0.52, -0.455)


def boton_salto(win):
    """Botón 'Saltar' del modo test. Fuera del modo test, (None, None)."""
    if not config.MODO_TEST:
        return None, None
    return _boton(win, "Saltar (%s)" % config.TECLA_SALTO.upper(),
                  pos=POS_SALTO, tamano=(0.22, 0.055), altura=0.021,
                  color=config.COLOR_TENUE)


def dibujar_salto(boton):
    """Dibuja el botón de salto, si lo hay."""
    if boton[0] is not None:
        boton[0].draw()
        boton[1].draw()


def salto_pedido(boton=(None, None), raton=None):
    """True si el modo test está activo y se pidió saltear la pantalla.

    La tecla se consulta SIEMPRE con keyList: así event.getKeys() deja el
    resto del buffer intacto, que es lo que necesitan las pantallas con un
    TextBox2 editable para seguir recibiendo lo que se tipea.
    """
    if not config.MODO_TEST:
        return False
    if event.getKeys(keyList=[config.TECLA_SALTO]):
        return True
    return bool(boton[0] is not None and raton is not None
                and raton.isPressedIn(boton[0]))


def soltar_raton(win, raton):
    """Espera a que se suelte el botón: un clic no tiene que saltear dos."""
    while raton.getPressed()[0]:
        win.flip()


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

    salto = boton_salto(win)
    raton = event.Mouse(win=win)
    event.clearEvents()
    while True:
        if encabezado:
            encabezado.draw()
        cuerpo.draw()
        aviso.draw()
        dibujar_salto(salto)
        win.flip()
        if event.getKeys(keyList=["space"]):
            return
        if salto_pedido(salto, raton):
            soltar_raton(win, raton)
            return


def cuenta_regresiva(win, duracion, texto=None):
    """Línea base fisiológica: cruz de fijación durante `duracion` segundos."""
    if texto is None:
        texto = protocolo.textos()["reposo_leyenda"]
    cruz = visual.TextStim(win, text="+", font=config.FUENTE, height=0.12,
                           color=config.COLOR_TEXTO, pos=(0, 0))
    leyenda = visual.TextStim(win, text=texto, font=config.FUENTE, height=0.026,
                              color=config.COLOR_TENUE, pos=(0, -0.32),
                              wrapWidth=1.0)
    salto = boton_salto(win)
    raton = event.Mouse(win=win)
    fin = core.getTime() + duracion
    while core.getTime() < fin:
        cruz.draw()
        leyenda.draw()
        dibujar_salto(salto)
        win.flip()
        if salto_pedido(salto, raton):
            soltar_raton(win, raton)
            return


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
    salto = boton_salto(win)
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
        dibujar_salto(salto)
        win.flip()

        if salto_pedido(salto, raton):
            soltar_raton(win, raton)
            return valor
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

    salto = boton_salto(win)
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
        dibujar_salto(salto)
        win.flip()

        if salto_pedido(salto, raton):
            soltar_raton(win, raton)
            try:
                win.removeEditable(entrada)
            except Exception:
                pass
            return contenido
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
# Los enunciados, ticks y anclas de todas las escalas viven en
# protocolo/escalas.json.
#
# Los ítems de autenticidad / empatía percibida están adaptados de Rubin et
# al. (2025). El cuarto es INVERSO (queda marcado con "inverso": true en el
# protocolo): hay que recodificarlo antes de promediar la subescala.




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

def preguntar_panas(win, items_por_pagina=None):
    """PANAS-estado en grilla. Devuelve {clave: 1..5} más los totales PA/NA."""
    cfg = protocolo.escalas()["panas"]
    items = protocolo.panas()
    if items_por_pagina is None:
        items_por_pagina = cfg["items_por_pagina"]
    ticks, anclas = cfg["ticks"], cfg["anclas"]
    respuestas = {}
    raton = event.Mouse(win=win)

    instruccion = visual.TextStim(
        win, text=cfg["consigna"],
        font=config.FUENTE, height=0.030, color=config.COLOR_TEXTO,
        pos=(0, 0.44), wrapWidth=1.15)

    x_centro, ancho = 0.12, 0.42
    x_primera = x_centro - ancho / 2.0
    paso = ancho / (len(ticks) - 1)
    encabezados = [
        visual.TextStim(win, text=anclas[k], font=config.FUENTE,
                        height=0.017, color=config.COLOR_TENUE,
                        pos=(x_primera + k * paso, 0.355), wrapWidth=0.115)
        for k in range(len(ticks))]

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
                win, ticks=ticks, labels=None, granularity=1,
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
        salto = boton_salto(win)
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
            dibujar_salto(salto)
            win.flip()

            if salto_pedido(salto, raton):
                soltar_raton(win, raton)
                break
            if not faltan and raton.isPressedIn(caja):
                while raton.getPressed()[0]:
                    win.flip()
                break

        for it, sl in zip(pagina, sliders):
            respuestas[it["clave"]] = sl.getRating()

    # totales de subescala (rango 10-50 cada una). Una subescala incompleta
    # no tiene total: pasa sólo si se salteó la grilla en modo test, y un
    # total parcial ahí adentro se leería después como un dato válido.
    for sub in ("PA", "NA"):
        valores = [respuestas[it["clave"]] for it in items
                   if it["subescala"] == sub]
        respuestas[sub + "_total"] = (
            None if any(v is None for v in valores) else sum(valores))
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
    esc = protocolo.escalas()
    r = {}

    suds = esc["suds"]
    r["suds"] = preguntar_escala(win, suds["enunciado"], suds["ticks"],
                                 suds["etiquetas"])

    for clave in ("sam_valencia", "sam_arousal"):
        sam = esc[clave]
        r[clave] = preguntar_escala(win, sam["enunciado"], sam["ticks"],
                                    sam["etiquetas"], sam["imagenes"])

    if incluir_autenticidad:
        aut = esc["autenticidad"]
        for item in aut["items"]:
            r[item["clave"]] = preguntar_escala(
                win, item["enunciado"], aut["ticks"], aut["etiquetas"])

    # El PANAS va ÚLTIMO a propósito: son 20 ítems, y SUDS/SAM son las medidas
    # sensibles al tiempo (hay que tomarlas lo antes posible tras el episodio,
    # mientras la activación todavía no se disipó).
    if incluir_panas:
        registro.marcar("panas_inicio", momento)
        r.update(preguntar_panas(win))
        registro.marcar("panas_fin", momento)

    registro.marcar("medidas_fin", momento)
    return r
