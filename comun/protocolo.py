# -*- coding: utf-8 -*-
"""
Lector de protocolo/: el contenido del experimento como datos.

Es el único módulo que sabe cómo está guardado el protocolo. El experimento
de escritorio y el servidor web lo leen por acá, así que una corrección de
redacción en protocolo/ llega a las dos implementaciones sin copiar nada.

Sólo biblioteca estándar: lo importa tanto el Python embebido de PsychoPy
como el del servidor.
"""

import csv
import json
import os

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
CARPETA = os.path.join(RAIZ, "protocolo")

MODOS = ("real", "demo")
AGENTES = ("guionado", "llm")

_cache = {}


def _leer_json(nombre):
    """Lee protocolo/<nombre>.json una sola vez y lo cachea."""
    if nombre not in _cache:
        ruta = os.path.join(CARPETA, nombre + ".json")
        with open(ruta, encoding="utf-8") as f:
            _cache[nombre] = json.load(f)
    return _cache[nombre]


def textos():
    """Prosa de las pantallas, historia de cobertura y chequeo final."""
    return _leer_json("textos")


def debriefing(agente):
    """El debriefing que corresponde al modo de agente que se usó.

    Hay dos versiones porque lo que pasó fue distinto. Con el agente
    guionado, todos los mensajes estaban escritos de antemano y eran
    idénticos entre participantes. Con el agente por LLM no: los generó un
    modelo a partir de lo que contó la persona, y decírselo de la otra
    manera sería mentirle justo en la pantalla donde se le deja de mentir.
    """
    if agente not in AGENTES:
        raise ValueError("agente debe ser uno de %s, no %r" % (AGENTES, agente))
    bloque = textos()["debriefing"]
    return {"titulo": bloque["titulo"], "cuerpo": bloque["cuerpo"][agente]}


def escalas():
    """SUDS, SAM, autenticidad y PANAS: enunciados, ticks y anclas."""
    return _leer_json("escalas")


def marcadores():
    """{etiqueta: codigo} para el log de eventos y el equipo de EDA."""
    return _leer_json("marcadores")


def prompts():
    """Rol por condición, plantilla de reglas y parámetros del modelo."""
    return _leer_json("prompts")


def parametros(modo="real"):
    """Tiempos del modo pedido, con los parámetros comunes mezclados.

    Los comunes (la fórmula de latencia, sobre todo) valen en los dos modos:
    es el invariante 2 del diseño y no puede depender de cómo se corra.
    """
    if modo not in MODOS:
        raise ValueError("modo debe ser uno de %s, no %r" % (MODOS, modo))
    crudo = _leer_json("parametros")
    combinado = dict(crudo["comun"])
    combinado.update(crudo[modo])
    return combinado


def guiones():
    """{tipo: {turno: texto}} desde protocolo/guiones.csv."""
    salida = {}
    with open(os.path.join(CARPETA, "guiones.csv"), encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            salida.setdefault(fila["tipo"], {})[int(fila["turno"])] = fila["texto"]
    return salida


def panas():
    """Los 20 ítems del PANAS, en orden, desde protocolo/panas.csv."""
    with open(os.path.join(CARPETA, "panas.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def todo():
    """El protocolo entero en un dict, para servirlo por HTTP al navegador.

    Ojo: al pasar por json.dumps, las claves enteras de guiones() salen como
    strings ("1", "2", "3"). El lado del navegador las lee así.
    """
    return {
        "textos": textos(),
        "escalas": escalas(),
        "marcadores": marcadores(),
        "prompts": prompts(),
        "parametros": {modo: parametros(modo) for modo in MODOS},
        "guiones": guiones(),
        "panas": panas(),
    }
