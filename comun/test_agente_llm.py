# -*- coding: utf-8 -*-
"""
Tests de comun/agente_llm.py. Corren con el Python del sistema, sin red y sin
PsychoPy:  python3 -m unittest comun.test_agente_llm -v

El transporte (la llamada HTTP a OpenRouter) se inyecta, así que acá se
prueba todo lo demás: armado del historial, rol por condición, fallback
al guion, y limpieza del texto.
"""

import os
import ssl
import tempfile
import threading
import unittest

from comun.agente_llm import (AgenteLLM, _contexto_ssl, cargar_api_key,
                              limpiar_respuesta)


def transporte_fijo(respuesta):
    """Transporte falso: siempre devuelve `respuesta` y anota qué recibió."""
    llamadas = []

    def transporte(payload):
        llamadas.append(payload)
        return respuesta

    transporte.llamadas = llamadas
    return transporte


class TestResponder(unittest.TestCase):

    def test_devuelve_el_texto_del_modelo_con_origen_llm(self):
        transporte = transporte_fijo("Te entiendo, debe haber sido difícil.")
        agente = AgenteLLM("validacion", transporte=transporte)
        agente.escucha("Me peleé con mi hermana y quedé muy mal.")

        texto, origen = agente.responder(guion_fallback="guion de respaldo")

        self.assertEqual(texto, "Te entiendo, debe haber sido difícil.")
        self.assertEqual(origen, "llm")

    def test_manda_el_historial_completo_en_orden(self):
        transporte = transporte_fijo("ok")
        agente = AgenteLLM("validacion", transporte=transporte)
        agente.saluda("Hola, contame algo que te haya pasado.")
        agente.escucha("Perdí el trabajo.")
        agente.responder(guion_fallback="respaldo")
        agente.escucha("Gracias por escucharme.")
        agente.responder(guion_fallback="respaldo")

        mensajes = transporte.llamadas[-1]["messages"]
        self.assertEqual(mensajes[0]["role"], "system")
        self.assertEqual(
            [(m["role"], m["content"]) for m in mensajes[1:]],
            [("assistant", "Hola, contame algo que te haya pasado."),
             ("user", "Perdí el trabajo."),
             ("assistant", "ok"),
             ("user", "Gracias por escucharme.")])

    def test_el_rol_de_la_condicion_esta_en_el_system_prompt(self):
        for tipo, palabra in [("validacion", "valid"), ("rechazo", "rechaz")]:
            transporte = transporte_fijo("ok")
            agente = AgenteLLM(tipo, transporte=transporte)
            agente.escucha("hola")
            agente.responder(guion_fallback="respaldo")
            system = transporte.llamadas[0]["messages"][0]["content"]
            self.assertIn(palabra, system.lower(),
                          "el system prompt de %s no menciona su rol" % tipo)

    def test_tipo_desconocido_falla_al_construir(self):
        with self.assertRaises(ValueError):
            AgenteLLM("neutral")


class TestFallback(unittest.TestCase):

    def test_si_el_transporte_falla_devuelve_el_guion(self):
        def transporte(payload):
            raise IOError("sin red")

        agente = AgenteLLM("rechazo", transporte=transporte)
        agente.escucha("hola")

        texto, origen = agente.responder(guion_fallback="Mmm, no sé.")

        self.assertEqual(texto, "Mmm, no sé.")
        self.assertEqual(origen, "fallback")

    def test_si_el_modelo_devuelve_vacio_usa_el_guion(self):
        agente = AgenteLLM("validacion", transporte=transporte_fijo("   "))
        agente.escucha("hola")

        texto, origen = agente.responder(guion_fallback="respaldo")

        self.assertEqual(texto, "respaldo")
        self.assertEqual(origen, "fallback")

    def test_tras_fallback_el_historial_guarda_el_guion(self):
        """La conversación tiene que seguir coherente con lo que se mostró
        en pantalla: si un turno salió del guion, el turno siguiente del
        modelo tiene que recibir ese guion como si lo hubiera dicho él."""
        transporte = transporte_fijo("ok")

        def transporte_que_falla_primero(payload):
            if not transporte.llamadas:
                transporte.llamadas.append(payload)
                raise IOError("sin red")
            return transporte(payload)

        agente = AgenteLLM("validacion",
                           transporte=transporte_que_falla_primero)
        agente.escucha("hola")
        agente.responder(guion_fallback="respaldo")
        agente.escucha("sigo acá")
        agente.responder(guion_fallback="respaldo 2")

        mensajes = transporte.llamadas[-1]["messages"]
        self.assertIn(("assistant", "respaldo"),
                      [(m["role"], m["content"]) for m in mensajes])


class TestLimpieza(unittest.TestCase):

    def test_texto_corto_queda_igual(self):
        self.assertEqual(limpiar_respuesta("Todo bien.", maximo=100),
                         "Todo bien.")

    def test_colapsa_saltos_de_linea(self):
        """Un solo globo de chat: nada de párrafos ni listas."""
        self.assertEqual(
            limpiar_respuesta("Primero.\n\nSegundo.\n- item", maximo=100),
            "Primero. Segundo. - item")

    def test_recorta_largo_en_limite_de_oracion(self):
        texto = "Una oración corta. " * 30
        recortado = limpiar_respuesta(texto, maximo=100)
        self.assertLessEqual(len(recortado), 100)
        self.assertTrue(recortado.endswith("."))

    def test_recorta_duro_si_no_hay_puntuacion(self):
        recortado = limpiar_respuesta("x" * 500, maximo=100)
        self.assertEqual(len(recortado), 100)


class TestResponderEnHilo(unittest.TestCase):
    """El pedido corre en segundo plano para poder seguir dibujando la
    pantalla ("en línea") mientras se espera la API."""

    def test_no_bloquea_y_entrega_el_mismo_resultado(self):
        arranco = threading.Event()
        soltar = threading.Event()

        def transporte_lento(payload):
            arranco.set()
            soltar.wait(timeout=5)
            return "respuesta lenta"

        agente = AgenteLLM("validacion", transporte=transporte_lento)
        agente.escucha("hola")

        pedido = agente.responder_en_hilo(guion_fallback="respaldo")
        self.assertTrue(arranco.wait(timeout=5))
        self.assertFalse(pedido.listo())   # el transporte sigue colgado

        soltar.set()
        self.assertEqual(pedido.resultado(), ("respuesta lenta", "llm"))
        self.assertTrue(pedido.listo())
        self.assertEqual(agente.historial[-1]["content"], "respuesta lenta")



class TestContextoSSL(unittest.TestCase):
    """El Python embebido de PsychoPy no encuentra el bundle de CAs en la
    ruta que busca OpenSSL: sin contexto propio, toda llamada a OpenRouter
    muere en CERTIFICATE_VERIFY_FAILED y el turno cae al guion. Estos tests
    fallan con el contexto por defecto si se corren con el Python de
    PsychoPy, que es donde importa."""

    def test_el_contexto_trae_autoridades_cargadas(self):
        self.assertTrue(_contexto_ssl().get_ca_certs())

    def test_el_contexto_verifica_el_certificado(self):
        contexto = _contexto_ssl()
        self.assertEqual(contexto.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(contexto.check_hostname)

class TestApiKey(unittest.TestCase):

    def setUp(self):
        self._previa = os.environ.pop("OPENROUTER_API_KEY", None)

    def tearDown(self):
        if self._previa is not None:
            os.environ["OPENROUTER_API_KEY"] = self._previa

    def test_lee_la_variable_de_entorno(self):
        os.environ["OPENROUTER_API_KEY"] = "sk-or-de-entorno"
        self.assertEqual(cargar_api_key(), "sk-or-de-entorno")

    def test_lee_el_archivo_si_no_hay_variable(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "openrouter_key.txt")
            with open(ruta, "w") as f:
                f.write("sk-or-de-archivo\n")
            self.assertEqual(cargar_api_key(carpeta=carpeta),
                             "sk-or-de-archivo")

    def test_sin_key_devuelve_none(self):
        with tempfile.TemporaryDirectory() as carpeta:
            self.assertIsNone(cargar_api_key(carpeta=carpeta))


if __name__ == "__main__":
    unittest.main()
