# -*- coding: utf-8 -*-
"""
Capa de marcadores de evento.

La idea: el experimento SIEMPRE escribe un log de eventos con timestamps de
alta precisión. Además, según el equipo que tengan, puede mandar el marcador
en tiempo real por LSL, puerto serie o puerto paralelo.

Por qué el log en CSV alcanza para este estudio: las respuestas
electrodérmicas (SCR) tienen latencias de 1-4 s y se analizan en ventanas de
segundos. No hace falta precisión de milisegundos como en un ERP. Con
Empatica E4 o Shimmer3 (que graban en su propio reloj) el procedimiento
estándar es exactamente este: alinear offline por timestamp.
"""

import csv
import time
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from psychopy import core, logging

import config
from comun import protocolo


class RegistroEventos:
    """Escribe cada evento a CSV y, si corresponde, lo manda al equipo."""

    def __init__(self, ruta_csv, reloj, backend="csv"):
        self.reloj = reloj
        self.backend = backend
        self._envio = None

        carpeta = os.path.dirname(ruta_csv)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
        self._archivo = open(ruta_csv, "w", newline="", encoding="utf-8")
        self._csv = csv.writer(self._archivo)
        self._csv.writerow([
            "t_experimento_s",   # segundos desde el inicio del experimento
            "t_unix",            # timestamp absoluto, para alinear con el equipo
            "codigo",
            "etiqueta",
            "detalle",
        ])

        self._abrir_backend()

    # -----------------------------------------------------------------
    def _abrir_backend(self):
        if self.backend == "lsl":
            try:
                from pylsl import StreamInfo, StreamOutlet
                info = StreamInfo("PsychoPy_Estudio1", "Markers", 1, 0,
                                  "int32", "estudio1_markers")
                outlet = StreamOutlet(info)
                self._envio = lambda cod: outlet.push_sample([int(cod)])
                logging.info("Marcadores por LSL activos.")
            except Exception as e:
                logging.warning("No se pudo abrir LSL (%s). Sigo sólo con CSV." % e)

        elif self.backend == "serial":
            try:
                import serial
                puerto = serial.Serial(config.PUERTO_SERIAL, config.BAUDIOS_SERIAL,
                                       timeout=0)
                self._envio = lambda cod: puerto.write(bytes([int(cod) & 0xFF]))
                logging.info("Marcadores por puerto serie activos.")
            except Exception as e:
                logging.warning("No se pudo abrir el puerto serie (%s). Sigo sólo con CSV." % e)

        elif self.backend == "paralelo":
            try:
                from psychopy import parallel
                parallel.setPortAddress(config.DIRECCION_PARALELO)

                def _pulso(cod):
                    parallel.setData(int(cod) & 0xFF)
                    core.wait(0.005)
                    parallel.setData(0)

                self._envio = _pulso
                logging.info("Marcadores por puerto paralelo activos.")
            except Exception as e:
                logging.warning("No se pudo abrir el puerto paralelo (%s). Sigo sólo con CSV." % e)

    # -----------------------------------------------------------------
    def marcar(self, etiqueta, detalle=""):
        """Registra un evento. `etiqueta` debe estar en protocolo/marcadores.json."""
        codigo = protocolo.marcadores().get(etiqueta, 0)
        t_exp = self.reloj.getTime()
        t_unix = time.time()

        if self._envio is not None:
            try:
                self._envio(codigo)
            except Exception as e:
                logging.warning("Fallo al enviar marcador %s: %s" % (etiqueta, e))

        self._csv.writerow(["%.4f" % t_exp, "%.6f" % t_unix, codigo, etiqueta, detalle])
        self._archivo.flush()
        return t_exp

    def cerrar(self):
        try:
            self._archivo.close()
        except Exception:
            pass
