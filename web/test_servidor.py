# -*- coding: utf-8 -*-
"""
Tests del servidor de la demo:
    python3 -m unittest discover -s web -t . -v

Levantan el servidor de verdad en un puerto efímero y le pegan por HTTP, sin
red hacia afuera: el transporte del LLM se pisa con uno falso.
"""

import json
import os
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from web.servidor import app


def pedir(puerto, ruta, cuerpo=None):
    """Devuelve (codigo, objeto_json_o_texto)."""
    url = "http://127.0.0.1:%d%s" % (puerto, ruta)
    datos = None
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf-8")
    pedido = urllib.request.Request(
        url, data=datos, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=10) as resp:
            crudo = resp.read().decode("utf-8")
            codigo = resp.status
    except urllib.error.HTTPError as e:
        with e:
            crudo = e.read().decode("utf-8")
            codigo = e.code
    try:
        return codigo, json.loads(crudo)
    except ValueError:
        return codigo, crudo


class BaseServidor(unittest.TestCase):

    def setUp(self):
        self.carpeta = tempfile.mkdtemp()
        self.servidor = app.crear_servidor(0, carpeta_datos=self.carpeta)
        self.puerto = self.servidor.server_address[1]
        self.hilo = threading.Thread(target=self.servidor.serve_forever,
                                     daemon=True)
        self.hilo.start()
        self._codigo_previo = app.CODIGO_ACCESO
        self._transporte_previo = app.TRANSPORTE

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        shutil.rmtree(self.carpeta, ignore_errors=True)
        app.CODIGO_ACCESO = self._codigo_previo
        app.TRANSPORTE = self._transporte_previo


class TestLectura(BaseServidor):

    def test_salud(self):
        codigo, cuerpo = pedir(self.puerto, "/api/salud")
        self.assertEqual(codigo, 200)
        self.assertTrue(cuerpo["ok"])

    def test_protocolo_trae_las_siete_secciones(self):
        codigo, cuerpo = pedir(self.puerto, "/api/protocolo")
        self.assertEqual(codigo, 200)
        self.assertEqual(
            set(cuerpo),
            {"textos", "escalas", "marcadores", "prompts", "parametros",
             "guiones", "panas"})

    def test_los_turnos_de_guion_llegan_con_clave_string(self):
        """Al pasar por JSON las claves enteras se vuelven strings: el lado
        del navegador tiene que leerlas así."""
        _, cuerpo = pedir(self.puerto, "/api/protocolo")
        self.assertIn("1", cuerpo["guiones"]["validacion"])

    def test_el_debriefing_viene_con_las_dos_versiones(self):
        _, cuerpo = pedir(self.puerto, "/api/protocolo")
        self.assertEqual(set(cuerpo["textos"]["debriefing"]["cuerpo"]),
                         {"guionado", "llm"})

    def test_ruta_inexistente_da_404(self):
        codigo, _ = pedir(self.puerto, "/no-existe.js")
        self.assertEqual(codigo, 404)

    def test_no_sirve_archivos_fuera_de_web(self):
        """Un traversal no puede llegar a openrouter_key.txt."""
        codigo, _ = pedir(self.puerto, "/../../openrouter_key.txt")
        self.assertIn(codigo, (403, 404))


class TestTurno(BaseServidor):

    def setUp(self):
        super().setUp()
        app.CODIGO_ACCESO = ""
        app.TRANSPORTE = lambda payload: "respuesta del modelo"

    def test_devuelve_el_texto_con_origen_llm(self):
        codigo, cuerpo = pedir(self.puerto, "/api/turno", {
            "tipo": "validacion",
            "historial": [{"role": "user", "content": "me peleé con mi hermana"}],
            "guion_fallback": "respaldo"})
        self.assertEqual(codigo, 200)
        self.assertEqual(cuerpo, {"texto": "respuesta del modelo",
                                  "origen": "llm"})

    def test_replica_el_historial_en_el_payload(self):
        visto = {}

        def transporte(payload):
            visto["messages"] = payload["messages"]
            return "ok"

        app.TRANSPORTE = transporte
        pedir(self.puerto, "/api/turno", {
            "tipo": "rechazo",
            "historial": [{"role": "assistant", "content": "hola"},
                          {"role": "user", "content": "perdí el trabajo"}],
            "guion_fallback": "respaldo"})
        roles = [(m["role"], m["content"]) for m in visto["messages"][1:]]
        self.assertEqual(roles, [("assistant", "hola"),
                                 ("user", "perdí el trabajo")])

    def test_tipo_invalido_da_400(self):
        codigo, _ = pedir(self.puerto, "/api/turno", {"tipo": "neutral"})
        self.assertEqual(codigo, 400)

    def test_si_el_transporte_falla_devuelve_el_guion_con_200(self):
        """La demo no se cae por un turno: cae al guion, como el escritorio."""
        def transporte(payload):
            raise IOError("sin red")

        app.TRANSPORTE = transporte
        codigo, cuerpo = pedir(self.puerto, "/api/turno", {
            "tipo": "rechazo", "historial": [],
            "guion_fallback": "Mmm, no sé."})
        self.assertEqual(codigo, 200)
        self.assertEqual(cuerpo, {"texto": "Mmm, no sé.", "origen": "fallback"})


class TestCodigoDeAcceso(BaseServidor):

    def setUp(self):
        super().setUp()
        app.CODIGO_ACCESO = "secreto"
        app.TRANSPORTE = lambda payload: "ok"

    def test_sin_codigo_da_403(self):
        codigo, _ = pedir(self.puerto, "/api/turno",
                          {"tipo": "validacion", "historial": []})
        self.assertEqual(codigo, 403)

    def test_con_codigo_pasa(self):
        codigo, _ = pedir(self.puerto, "/api/turno",
                          {"tipo": "validacion", "historial": [],
                           "codigo": "secreto"})
        self.assertEqual(codigo, 200)

    def test_el_protocolo_no_pide_codigo(self):
        """La página tiene que poder cargar antes de que se tipee el código."""
        codigo, _ = pedir(self.puerto, "/api/protocolo")
        self.assertEqual(codigo, 200)


class TestDatos(BaseServidor):

    def setUp(self):
        super().setUp()
        app.CODIGO_ACCESO = ""

    def _mandar(self):
        return pedir(self.puerto, "/api/datos", {
            "info": {"id_participante": "07", "condicion_agente": "ia"},
            "respuestas": {"suds": 40},
            "conductual": [{"episodio": 1, "tipo": "validacion"}],
            "chat": [{"autor": "agente", "texto": "hola", "origen": "guion"}],
            "eventos": [{"t_experimento_s": 0, "t_unix": 0, "codigo": 1,
                         "etiqueta": "inicio_experimento", "detalle": "ia"}]})

    def test_escribe_los_cuatro_csv(self):
        codigo, cuerpo = self._mandar()
        self.assertEqual(codigo, 200)
        self.assertEqual(len(cuerpo["archivos"]), 4)
        for nombre in cuerpo["archivos"]:
            self.assertTrue(os.path.exists(os.path.join(self.carpeta, nombre)))

    def test_el_prefijo_lleva_id_y_condicion(self):
        _, cuerpo = self._mandar()
        for nombre in cuerpo["archivos"]:
            self.assertTrue(nombre.startswith("S1_07_ia_"))

    def test_marca_la_plataforma_como_web(self):
        _, cuerpo = self._mandar()
        respuestas = [n for n in cuerpo["archivos"] if "_respuestas" in n][0]
        with open(os.path.join(self.carpeta, respuestas), encoding="utf-8") as f:
            contenido = f.read()
        self.assertIn("plataforma,web", contenido)


if __name__ == "__main__":
    unittest.main()
