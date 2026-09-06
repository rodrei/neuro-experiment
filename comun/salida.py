# -*- coding: utf-8 -*-
"""
Escritura de los CSV de salida, compartida entre el escritorio y la web.

El formato es el contrato con los scripts de análisis: cuatro archivos por
participante, con el prefijo S1_<id>_<condición>_<fecha>. Vive acá para que
las dos plataformas no puedan divergir en las columnas.

Sólo biblioteca estándar.
"""

import csv
import os

CAMPOS_EVENTOS = ["t_experimento_s", "t_unix", "codigo", "etiqueta", "detalle"]
CAMPOS_CHAT = ["autor", "texto", "origen", "t_experimento_s", "latencia_s"]


def nombre_base(id_participante, condicion, sello):
    """El prefijo común a los cuatro archivos de una sesión."""
    return "S1_%s_%s_%s" % (id_participante, condicion, sello)


def _abrir(ruta):
    carpeta = os.path.dirname(ruta)
    if carpeta:
        os.makedirs(carpeta, exist_ok=True)
    return open(ruta, "w", newline="", encoding="utf-8")


def escribir_respuestas(ruta, respuestas):
    """Dos columnas, clave y valor, con las claves ordenadas."""
    with _abrir(ruta) as f:
        w = csv.writer(f)
        for clave in sorted(respuestas):
            w.writerow([clave, respuestas[clave]])


def escribir_conductual(ruta, filas):
    """Una fila por episodio. Las columnas son la unión de todas las claves."""
    campos = sorted({k for fila in filas for k in fila})
    with _abrir(ruta) as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for fila in filas:
            w.writerow(fila)


def escribir_chat(ruta, filas):
    """Transcripción completa, con el origen de cada mensaje del agente."""
    with _abrir(ruta) as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_CHAT, extrasaction="ignore")
        w.writeheader()
        for fila in filas:
            w.writerow(fila)


def escribir_eventos(ruta, filas):
    """Mismo esquema que el log que escribe RegistroEventos en el escritorio."""
    with _abrir(ruta) as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_EVENTOS, extrasaction="ignore")
        w.writeheader()
        for fila in filas:
            w.writerow(fila)


def escribir_todo(carpeta, base, respuestas, conductual, chat, eventos=None):
    """Escribe los CSV de una sesión y devuelve las rutas.

    `eventos` es opcional porque el escritorio ya lo escribe en streaming
    mientras corre (ver marcadores.RegistroEventos); la web, en cambio, junta
    el log en memoria y lo manda al final.
    """
    os.makedirs(carpeta, exist_ok=True)
    rutas = []
    pares = [("_respuestas.csv", escribir_respuestas, respuestas),
             ("_conductual.csv", escribir_conductual, conductual),
             ("_chat.csv", escribir_chat, chat)]
    if eventos is not None:
        pares.append(("_eventos.csv", escribir_eventos, eventos))
    for sufijo, escritor, datos in pares:
        ruta = os.path.join(carpeta, base + sufijo)
        escritor(ruta, datos)
        rutas.append(ruta)
    return rutas
