# -*- coding: utf-8 -*-
"""
Servidor de la demo web del Estudio 1.

Cuatro responsabilidades y nada más:

  GET  /               y estáticos  -> sirve web/
  GET  /api/protocolo               -> el protocolo armado por comun.protocolo
  POST /api/turno                   -> proxy al LLM (la key nunca sale de acá)
  POST /api/datos                   -> escribe los cuatro CSV de la sesión

Es `http.server` de la biblioteca estándar a propósito: son cuatro rutas, y
así la imagen de Docker no necesita `pip install` ni hace falta preparar un
entorno para correrlo local.

El proxy es SIN ESTADO: el navegador manda el historial completo en cada
turno y el servidor reconstruye el agente. Se puede reiniciar en medio de una
demo y aguanta varias sesiones en paralelo sin trabajo extra.

Correr local:  python3 -m web.servidor.app
"""

import http.server
import json
import os
import posixpath
import socketserver
import sys
import threading
import time
import urllib.parse
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from comun import agente_llm, protocolo, salida

CARPETA_WEB = os.path.dirname(AQUI)

# Configuración por entorno. Los tests la pisan a nivel módulo.
CODIGO_ACCESO = os.environ.get("CODIGO_ACCESO", "")
CARPETA_DATOS = os.environ.get("CARPETA_DATOS", os.path.join(RAIZ, "datos"))
PUERTO = int(os.environ.get("PUERTO", "8080"))
TIMEOUT_LLM = int(os.environ.get("TIMEOUT_LLM", "20"))
LIMITE_POR_MINUTO = int(os.environ.get("LIMITE_POR_MINUTO", "30"))

# Transporte del agente. None = el real (OpenRouter). Los tests lo pisan.
TRANSPORTE = None

TIPOS_MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
}

_visitas = {}
_candado = threading.Lock()


def _permitido(ip):
    """Límite de tasa por IP: es una URL pública que gasta crédito ajeno."""
    ahora = time.time()
    with _candado:
        recientes = [t for t in _visitas.get(ip, []) if ahora - t < 60]
        if len(recientes) >= LIMITE_POR_MINUTO:
            _visitas[ip] = recientes
            return False
        recientes.append(ahora)
        _visitas[ip] = recientes
    return True


class Manejador(http.server.BaseHTTPRequestHandler):

    server_version = "Estudio1Web"

    def log_message(self, formato, *args):      # menos ruido en la consola
        pass

    # -----------------------------------------------------------------
    # helpers
    # -----------------------------------------------------------------
    def _responder(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
        if isinstance(cuerpo, str):
            cuerpo = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, codigo, obj):
        self._responder(codigo, json.dumps(obj, ensure_ascii=False))

    def _error(self, codigo, mensaje):
        self._json(codigo, {"error": mensaje})

    def _leer_json(self):
        largo = int(self.headers.get("Content-Length", "0") or 0)
        if largo <= 0:
            return {}
        return json.loads(self.rfile.read(largo).decode("utf-8"))

    def _codigo_ok(self, cuerpo):
        if not CODIGO_ACCESO:
            return True
        return cuerpo.get("codigo", "") == CODIGO_ACCESO

    # -----------------------------------------------------------------
    # GET
    # -----------------------------------------------------------------
    def do_GET(self):
        ruta = urllib.parse.urlparse(self.path).path
        if ruta == "/api/salud":
            return self._json(200, {"ok": True})
        if ruta == "/api/protocolo":
            return self._json(200, protocolo.todo())
        return self._estatico(ruta)

    def _estatico(self, ruta):
        if ruta in ("/", ""):
            ruta = "/index.html"
        # normalizar y verificar que no se escape de web/: si no, un
        # ../../openrouter_key.txt se sirve solo.
        limpio = posixpath.normpath(urllib.parse.unquote(ruta)).lstrip("/")
        destino = os.path.realpath(os.path.join(CARPETA_WEB, limpio))
        if not destino.startswith(os.path.realpath(CARPETA_WEB) + os.sep):
            return self._error(403, "ruta fuera de web/")
        if not os.path.isfile(destino):
            return self._error(404, "no encontrado")
        with open(destino, "rb") as f:
            cuerpo = f.read()
        extension = os.path.splitext(destino)[1].lower()
        self._responder(200, cuerpo,
                        TIPOS_MIME.get(extension, "application/octet-stream"))

    # -----------------------------------------------------------------
    # POST
    # -----------------------------------------------------------------
    def do_POST(self):
        ruta = urllib.parse.urlparse(self.path).path
        ip = self.client_address[0]
        if not _permitido(ip):
            return self._error(429, "demasiados pedidos")
        try:
            cuerpo = self._leer_json()
        except ValueError:
            return self._error(400, "json invalido")
        if not self._codigo_ok(cuerpo):
            return self._error(403, "codigo de acceso invalido")

        if ruta == "/api/turno":
            return self._turno(cuerpo)
        if ruta == "/api/datos":
            return self._datos(cuerpo)
        return self._error(404, "no encontrado")

    def _turno(self, cuerpo):
        """Reconstruye el agente, le replica el historial y pide un turno."""
        tipo = cuerpo.get("tipo")
        if tipo not in agente_llm.TIPOS_VALIDOS:
            return self._error(400, "tipo invalido")
        agente = agente_llm.AgenteLLM(tipo, transporte=TRANSPORTE,
                                      timeout=TIMEOUT_LLM)
        for mensaje in cuerpo.get("historial", []):
            texto = mensaje.get("content", "")
            if mensaje.get("role") == "user":
                agente.escucha(texto)
            else:
                agente.saluda(texto)
        # Si la API falla, responder() ya devuelve el guion con origen
        # "fallback": la demo nunca se cae por un turno.
        texto, origen = agente.responder(cuerpo.get("guion_fallback", ""))
        return self._json(200, {"texto": texto, "origen": origen})

    def _datos(self, cuerpo):
        """Escribe los cuatro CSV, con el mismo formato que el escritorio."""
        info = cuerpo.get("info") or {}
        respuestas = dict(cuerpo.get("respuestas") or {})
        sello = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = salida.nombre_base(info.get("id_participante") or "sin_id",
                                  info.get("condicion_agente") or "sin_cond",
                                  sello)
        respuestas["plataforma"] = "web"
        respuestas["archivo"] = base
        rutas = salida.escribir_todo(
            CARPETA_DATOS, base,
            respuestas=respuestas,
            conductual=cuerpo.get("conductual") or [],
            chat=cuerpo.get("chat") or [],
            eventos=cuerpo.get("eventos") or [])
        return self._json(200, {"ok": True,
                                "archivos": [os.path.basename(r) for r in rutas]})


class Servidor(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def crear_servidor(puerto=0, carpeta_datos=None):
    """Servidor listo para `serve_forever()`. puerto=0 elige uno libre."""
    global CARPETA_DATOS
    if carpeta_datos is not None:
        CARPETA_DATOS = carpeta_datos
    return Servidor(("0.0.0.0", puerto), Manejador)


def main():
    servidor = crear_servidor(PUERTO)
    print("Estudio 1 — demo web en http://0.0.0.0:%d" % servidor.server_address[1])
    print("Datos en %s" % CARPETA_DATOS)
    if not CODIGO_ACCESO:
        print("AVISO: sin CODIGO_ACCESO, cualquiera que tenga la URL puede "
              "gastar crédito de OpenRouter.")
    servidor.serve_forever()


if __name__ == "__main__":
    main()
