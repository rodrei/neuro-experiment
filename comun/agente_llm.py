# -*- coding: utf-8 -*-
"""
Agente conversacional por LLM (OpenRouter), alternativa al agente guionado.

Se activa con AGENTE = "llm" en config.py. El flujo del experimento, los
marcadores y los CSVs no cambian: sólo cambia quién escribe los mensajes.

Decisiones importantes:
  - El saludo que pide la situación sigue SIEMPRE guionado (tiene que pedirla
    sí o sí, y es idéntico entre condiciones). El LLM toma la conversación
    a partir de la situación revelada.
  - Si la API falla o devuelve vacío, el turno cae al guion fijo de
    protocolo/guiones.csv y el experimento sigue (mismo espíritu que los backends
    de marcadores: nunca se cae). El origen queda registrado.
  - La key se lee de OPENROUTER_API_KEY o de openrouter_key.txt (gitignoreado),
    porque al lanzar desde PsychoPy Coder no hay variables de entorno.
  - Sin dependencias nuevas: sólo urllib de la librería estándar.

Para iterar los prompts sin abrir PsychoPy:  python3 agente_llm.py
"""

import json
import os
import ssl
import threading
import urllib.request

from comun import protocolo

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
URL_OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"

TIPOS_VALIDOS = ("validacion", "rechazo")

# El timeout es operativo, no metodológico: cada plataforma lo pasa al
# construir el agente. Este es el valor que usa si nadie dice otra cosa.
TIMEOUT_POR_DEFECTO = 20


def _ejemplos_de_guion(tipo):
    """Los mensajes guionados del tipo, como anclas de estilo del prompt."""
    try:
        return list(protocolo.guiones()[tipo].values())
    except (OSError, KeyError):
        return []


def limpiar_respuesta(texto, maximo):
    """Deja el texto listo para una burbuja de chat: una sola línea y, si se
    pasa del máximo, recortado en el último cierre de oración que entre."""
    texto = " ".join(texto.split())
    if len(texto) <= maximo:
        return texto
    corte = texto[:maximo]
    ultimo = max(corte.rfind("."), corte.rfind("!"), corte.rfind("?"))
    if ultimo > 0:
        return corte[:ultimo + 1]
    return corte


def cargar_api_key(carpeta=RAIZ):
    """OPENROUTER_API_KEY del entorno, o openrouter_key.txt en `carpeta`."""
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    ruta = os.path.join(carpeta, "openrouter_key.txt")
    try:
        with open(ruta, encoding="utf-8") as f:
            key = f.read().strip()
    except OSError:
        return None
    return key or None


def _contexto_ssl():
    """Contexto TLS armado con una autoridad certificante que exista en este
    intérprete.

    El Python embebido de PsychoPy no tiene el bundle de certificados en la
    ruta donde lo busca OpenSSL, así que el contexto por defecto no puede
    validar a OpenRouter. certifi viene adentro de PsychoPy; si no está, se
    usa el bundle del sistema. La verificación no se desactiva nunca: por
    este canal viaja lo que escribe el participante.
    """
    candidatos = []
    try:
        import certifi
    except ImportError:
        pass
    else:
        candidatos.append(certifi.where())
    candidatos.append("/etc/ssl/cert.pem")
    for ruta in candidatos:
        if os.path.exists(ruta):
            return ssl.create_default_context(cafile=ruta)
    return ssl.create_default_context()


def _transporte_openrouter(payload, timeout=TIMEOUT_POR_DEFECTO):
    """Transporte real: manda el payload y devuelve el texto de la respuesta.

    Cualquier problema (sin key, sin red, HTTP != 200, JSON raro) se deja
    subir como excepción: el que llama decide caer al guion.
    """
    key = cargar_api_key()
    if not key:
        raise RuntimeError(
            "No hay API key: definí OPENROUTER_API_KEY o creá openrouter_key.txt")
    pedido = urllib.request.Request(
        URL_OPENROUTER,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(pedido, timeout=timeout,
                                context=_contexto_ssl()) as resp:
        datos = json.loads(resp.read().decode("utf-8"))
    return datos["choices"][0]["message"]["content"]


class AgenteLLM(object):
    """Un episodio de conversación. Crear uno nuevo por episodio."""

    def __init__(self, tipo, transporte=None, timeout=None):
        if tipo not in TIPOS_VALIDOS:
            raise ValueError("tipo debe ser uno de %s" % (TIPOS_VALIDOS,))
        self.tipo = tipo
        self.timeout = TIMEOUT_POR_DEFECTO if timeout is None else timeout
        # El transporte inyectado recibe sólo el payload: el timeout se ata
        # acá para no cambiarle la firma a los tests.
        if transporte is None:
            transporte = lambda payload: _transporte_openrouter(
                payload, self.timeout)
        self.transporte = transporte
        self.historial = []     # [{"role": ..., "content": ...}]

        cfg = protocolo.prompts()
        self.system = cfg["reglas"].format(
            nombre=protocolo.textos()["nombre_agente"],
            rol=cfg["rol"][tipo],
            maximo=cfg["max_caracteres"],
            ejemplos="\n".join("- " + e for e in _ejemplos_de_guion(tipo))
                     or "(sin ejemplos)")

    # -----------------------------------------------------------------
    def saluda(self, texto):
        """Registra un mensaje guionado del agente (p. ej. el saludo)."""
        self.historial.append({"role": "assistant", "content": texto})

    def escucha(self, texto):
        """Registra lo que escribió el participante."""
        self.historial.append({"role": "user", "content": texto})

    def responder(self, guion_fallback):
        """Genera el próximo turno. Devuelve (texto, origen) con origen
        "llm" o "fallback". Si algo falla, el turno sale del guion y el
        historial queda coherente con lo que se mostró en pantalla."""
        cfg = protocolo.prompts()
        payload = {
            "model": cfg["modelo"],
            "messages": [{"role": "system", "content": self.system}]
                        + list(self.historial),
            "max_tokens": cfg["max_tokens"],
            "temperature": cfg["temperatura"],
        }
        motivo = None
        try:
            crudo = self.transporte(payload)
            texto = limpiar_respuesta(crudo, cfg["max_caracteres"])
        except Exception as error:
            texto = ""
            motivo = "%s: %s" % (type(error).__name__, error)
        origen = "llm"
        if not texto.strip():
            # Sin este aviso, una key vencida, una caída de red y un problema
            # de certificados se ven todos igual desde la pantalla: como un
            # experimento guionado.
            print("AVISO: turno %s al guion (%s)."
                  % (self.tipo, motivo or "el modelo devolvió texto vacío"))
            texto, origen = guion_fallback, "fallback"
        self.historial.append({"role": "assistant", "content": texto})
        return texto, origen

    def responder_en_hilo(self, guion_fallback):
        """Como responder(), pero en un hilo: permite seguir dibujando la
        pantalla mientras se espera la API. Devuelve un PedidoEnCurso."""
        return PedidoEnCurso(self, guion_fallback)


class PedidoEnCurso(object):
    """Un responder() corriendo en segundo plano."""

    def __init__(self, agente, guion_fallback):
        self._resultado = None
        self._hilo = threading.Thread(
            target=self._correr, args=(agente, guion_fallback), daemon=True)
        self._hilo.start()

    def _correr(self, agente, guion_fallback):
        self._resultado = agente.responder(guion_fallback)

    def listo(self):
        return not self._hilo.is_alive()

    def resultado(self):
        """Bloquea hasta tener el (texto, origen)."""
        self._hilo.join()
        return self._resultado


# =====================================================================
# Chat de consola para probar los prompts sin abrir PsychoPy
# =====================================================================
if __name__ == "__main__":
    tipo = ""
    while tipo not in TIPOS_VALIDOS:
        tipo = input("¿Tipo de episodio? (validacion/rechazo): ").strip()
    agente = AgenteLLM(tipo)
    saludo = ("Hola. Me dijeron que vamos a charlar un rato. Contame algo "
              "que te haya pasado últimamente y que te haya movilizado.")
    agente.saluda(saludo)
    print("\n[%s] %s" % (protocolo.textos()["nombre_agente"], saludo))
    while True:
        try:
            entrada = input("\n[vos] ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not entrada:
            break
        agente.escucha(entrada)
        texto, origen = agente.responder(
            guion_fallback="(fallback: acá iría el guion)")
        print("\n[%s · %s] %s"
              % (protocolo.textos()["nombre_agente"], origen, texto))
