# -*- coding: utf-8 -*-
"""
Motor de la interfaz de chat.

Es la pieza central del experimento: PsychoPy Builder no tiene un componente
de chat, así que la ventana de conversación se dibuja a mano con TextBox2
(burbujas) sobre una Window en unidades 'height'.

Lo importante para el diseño:
  - El agente está TOTALMENTE GUIONADO. No hace falta un operador en vivo.
  - La latencia del agente es DETERMINISTA (función del largo del mensaje),
    así que es idéntica entre las condiciones Humano e IA. Es exactamente el
    control que pide el diseño: lo único que varía es la fuente atribuida.
  - El participante cuenta su situación DENTRO del chat, cuando el agente se
    la pide. No se le piden por adelantado en una pantalla del software:
    eso rompía la historia de cobertura justo antes de medirla.
  - Cada mensaje deja un marcador con timestamp, para segmentar el EDA después.

Nota técnica: las burbujas se construyen UNA vez por mensaje y después sólo
se reposicionan. Construir un TextBox2 obliga a maquetar la fuente, que es
caro; hacerlo en cada frame tiraba los fps al piso.
"""

from psychopy import visual, core, event

import config

RELLENO_BURBUJA = 0.018
INTERLINEA = 1.06          # medido sobre TextBox2: paso de línea / letterHeight
SEPARACION = 0.022         # aire entre burbujas


class Chat(object):
    """Ventana de conversación."""

    def __init__(self, win, registro, etiqueta_agente):
        self.win = win
        self.registro = registro
        self.etiqueta_agente = etiqueta_agente
        self.mensajes = []          # (autor, texto, t)
        self.burbujas = []          # (TextBox2, alto) en el mismo orden
        self.transcripcion = []

        ar = win.size[0] / float(win.size[1])
        self.x_izq = -ar / 2 + 0.06
        self.x_der = ar / 2 - 0.06
        self.y_tope = 0.39
        self.y_piso = -0.30

        self.barra = visual.Rect(
            win, width=ar, height=0.10, pos=(0, 0.45),
            fillColor=config.COLOR_BARRA, lineColor=None)
        self.titulo = visual.TextStim(
            win, text=etiqueta_agente, font=config.FUENTE,
            height=0.028, color=config.COLOR_TEXTO,
            pos=(self.x_izq, 0.465), anchorHoriz="left", alignText="left")
        self.estado = visual.TextStim(
            win, text="en línea", font=config.FUENTE,
            height=0.022, color=config.COLOR_TENUE,
            pos=(self.x_izq, 0.428), anchorHoriz="left", alignText="left")

        self.caja = visual.TextBox2(
            win, text="", font=config.FUENTE,
            pos=(self.x_izq + 0.30, -0.40), size=(0.66, 0.12),
            letterHeight=config.ALTURA_LETRA, color=config.COLOR_TEXTO,
            fillColor="#FFFFFF", borderColor="#D0D0D4", borderWidth=2,
            padding=0.014, anchor="center", alignment="top-left",
            editable=True, placeholder="Escribí tu mensaje…")

        self.boton = visual.Rect(
            win, width=0.16, height=0.075, pos=(self.x_izq + 0.72, -0.40),
            fillColor=config.COLOR_ACENTO, lineColor=None)
        self.boton_txt = visual.TextStim(
            win, text="Enviar", font=config.FUENTE, height=0.026,
            color="#FFFFFF", pos=(self.x_izq + 0.72, -0.40))
        self.ayuda = visual.TextStim(
            win, text="Enter para enviar", font=config.FUENTE, height=0.019,
            color=config.COLOR_TENUE, pos=(self.x_izq + 0.72, -0.455))

        self.raton = event.Mouse(win=win)

    # -----------------------------------------------------------------
    # construcción de burbujas
    # -----------------------------------------------------------------
    def _construir_burbuja(self, autor, texto):
        """Crea la burbuja midiendo el alto real que ocupa el texto."""
        if autor == "agente":
            x, anclaje = self.x_izq, "left"
            relleno, borde = config.COLOR_BURBUJA_AG, "#E6E6EA"
        else:
            x, anclaje = self.x_der, "right"
            relleno, borde = config.COLOR_BURBUJA_PA, None

        comun = dict(
            win=self.win, text=texto, font=config.FUENTE,
            letterHeight=config.ALTURA_LETRA, color=config.COLOR_TEXTO,
            fillColor=relleno, borderColor=borde, padding=RELLENO_BURBUJA,
            anchor=anclaje, alignment="top-left", editable=False)

        # 1) maqueta provisoria, sólo para contar líneas
        provisoria = visual.TextBox2(
            pos=(0, 0), size=(config.ANCHO_BURBUJA_MAX, 0.5), **comun)
        n_lineas = max(1, len(getattr(provisoria, "_lineLenChars", [1])))

        # 2) burbuja definitiva, con el alto exacto
        alto = (n_lineas * config.ALTURA_LETRA * INTERLINEA
                + 2 * RELLENO_BURBUJA + 0.006)
        burbuja = visual.TextBox2(
            pos=(x, 0), size=(config.ANCHO_BURBUJA_MAX, alto), **comun)
        return burbuja, alto

    # -----------------------------------------------------------------
    # dibujo
    # -----------------------------------------------------------------
    def _dibujar_mensajes(self):
        """De abajo hacia arriba: el más nuevo abajo, los viejos suben."""
        y = self.y_piso
        for (burbuja, alto), (autor, _texto, _t) in zip(
                reversed(self.burbujas), reversed(self.mensajes)):
            if y > self.y_tope:
                break                      # ya se fue de pantalla
            x = self.x_izq if autor == "agente" else self.x_der
            burbuja.pos = (x, y + alto / 2.0)
            burbuja.draw()
            y += alto + SEPARACION

    def dibujar(self, mostrar_entrada=True):
        # los mensajes primero: si uno se pasa del tope, la barra lo tapa
        self._dibujar_mensajes()
        self.barra.draw()
        self.titulo.draw()
        self.estado.draw()
        if mostrar_entrada:
            self.caja.draw()
            self.boton.draw()
            self.boton_txt.draw()
            self.ayuda.draw()
        self.win.flip()

    # -----------------------------------------------------------------
    # turnos
    # -----------------------------------------------------------------
    def _agregar(self, autor, texto):
        t = self.registro.reloj.getTime()
        self.mensajes.append((autor, texto, t))
        self.burbujas.append(self._construir_burbuja(autor, texto))
        self.transcripcion.append({
            "autor": autor, "texto": texto, "t_experimento_s": round(t, 4)})

    def latencia_de(self, texto):
        """Determinista: mismo mensaje -> misma espera, en las dos condiciones."""
        t = config.LATENCIA_BASE + len(texto) * config.LATENCIA_POR_CARACTER
        return min(t, config.LATENCIA_MAX)

    def agente_dice(self, texto, etiqueta_marcador=None):
        """Muestra 'escribiendo…', espera la latencia, y publica el mensaje."""
        espera = self.latencia_de(texto)

        self.estado.text = "en línea"
        fin = core.getTime() + config.DUR_LECTURA_MIN
        while core.getTime() < fin:
            self.dibujar()

        self.estado.text = "escribiendo…"
        fin = core.getTime() + espera
        while core.getTime() < fin:
            self.dibujar()

        self.estado.text = "en línea"
        self._agregar("agente", texto)
        if etiqueta_marcador:
            self.registro.marcar(etiqueta_marcador, texto[:60])
        self.dibujar()

    def esperar_participante(self, timeout=None, minimo_caracteres=0,
                             marcador="participante_mensaje"):
        """Deja escribir al participante. Devuelve (texto, latencia_s).

        Se envía con Enter (la caja recibe un '\\n' al final) o con el botón.
        Si `minimo_caracteres` > 0, no deja enviar hasta llegar al mínimo y
        muestra cuánto le falta. Si se agota `timeout` sin texto, devuelve
        ("", None): en la ventana de respuesta libre, no contestar es un dato.
        """
        try:
            self.win.currentEditable = self.caja
        except Exception:
            pass
        self.caja.clear()
        self.caja.text = ""

        t0 = core.getTime()
        limite = None if timeout is None else t0 + timeout

        while True:
            texto = self.caja.getText()
            limpio = texto.strip()
            suficiente = len(limpio) >= minimo_caracteres

            if minimo_caracteres and not suficiente:
                self.ayuda.text = ("Al menos %d caracteres (llevás %d)"
                                   % (minimo_caracteres, len(limpio)))
            else:
                self.ayuda.text = "Enter para enviar"

            # Enter
            if texto.endswith("\n"):
                if limpio and suficiente:
                    return self._enviar(limpio, t0, marcador)
                # todavía no alcanza: saco el salto pero conservo lo escrito
                self.caja.text = texto.rstrip("\n")

            # botón Enviar
            if self.raton.isPressedIn(self.boton):
                if limpio and suficiente:
                    while self.raton.getPressed()[0]:
                        self.dibujar()
                    return self._enviar(limpio, t0, marcador)

            # se acabó el tiempo
            if limite is not None and core.getTime() > limite:
                if limpio:
                    return self._enviar(limpio, t0, marcador)
                self.registro.marcar(marcador, "sin respuesta")
                self.transcripcion.append({
                    "autor": "participante", "texto": "[sin respuesta]",
                    "t_experimento_s": round(self.registro.reloj.getTime(), 4)})
                self.ayuda.text = "Enter para enviar"
                return "", None

            self.dibujar()

    def _enviar(self, texto, t0, marcador="participante_mensaje"):
        latencia = core.getTime() - t0
        self._agregar("participante", texto)
        self.registro.marcar(marcador, "latencia=%.2f" % latencia)
        self.transcripcion[-1]["latencia_s"] = round(latencia, 3)
        self.caja.clear()
        self.caja.text = ""
        self.ayuda.text = "Enter para enviar"
        self.dibujar()
        core.wait(0.4)
        return texto, latencia

    def limpiar(self):
        self.mensajes = []
        self.burbujas = []
