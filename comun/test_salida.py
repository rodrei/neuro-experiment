# -*- coding: utf-8 -*-
"""
Tests del escritor de CSV compartido:
    python3 -m unittest comun.test_salida -v

Fijan el FORMATO de salida, que es lo que tiene que ser idéntico entre el
escritorio y la demo web: si cambia una columna, cualquier script de
análisis que ya exista se rompe en silencio.
"""

import csv
import os
import tempfile
import unittest

from comun import salida


class TestNombreBase(unittest.TestCase):

    def test_arma_el_prefijo_del_protocolo(self):
        self.assertEqual(salida.nombre_base("07", "ia", "20260906_1200"),
                         "S1_07_ia_20260906_1200")


class TestEscribirRespuestas(unittest.TestCase):

    def test_dos_columnas_con_las_claves_ordenadas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "r.csv")
            salida.escribir_respuestas(ruta, {"suds": 40, "aut1": 5})
            with open(ruta, encoding="utf-8") as f:
                filas = list(csv.reader(f))
        self.assertEqual(filas, [["aut1", "5"], ["suds", "40"]])


class TestEscribirConductual(unittest.TestCase):

    def test_une_las_claves_de_filas_distintas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "c.csv")
            salida.escribir_conductual(
                ruta, [{"episodio": 1, "tipo": "validacion"},
                       {"episodio": 2, "tipo": "rechazo", "extra": "x"}])
            with open(ruta, encoding="utf-8") as f:
                filas = list(csv.DictReader(f))
        self.assertEqual(sorted(filas[0]), ["episodio", "extra", "tipo"])
        self.assertEqual(filas[0]["extra"], "")


class TestEscribirChat(unittest.TestCase):

    def test_usa_los_campos_fijos_e_ignora_los_de_mas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "ch.csv")
            salida.escribir_chat(ruta, [
                {"autor": "agente", "texto": "hola", "origen": "guion",
                 "t_experimento_s": 1.0, "latencia_s": None, "sobra": 1}])
            with open(ruta, encoding="utf-8") as f:
                filas = list(csv.reader(f))
        self.assertEqual(filas[0], salida.CAMPOS_CHAT)


class TestEscribirEventos(unittest.TestCase):

    def test_mismo_encabezado_que_el_registro_del_escritorio(self):
        self.assertEqual(
            salida.CAMPOS_EVENTOS,
            ["t_experimento_s", "t_unix", "codigo", "etiqueta", "detalle"])

    def test_escribe_las_filas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "e.csv")
            salida.escribir_eventos(ruta, [
                {"t_experimento_s": 0.5, "t_unix": 1.0, "codigo": 1,
                 "etiqueta": "inicio_experimento", "detalle": "ia"}])
            with open(ruta, encoding="utf-8") as f:
                filas = list(csv.DictReader(f))
        self.assertEqual(filas[0]["etiqueta"], "inicio_experimento")


class TestEscribirTodo(unittest.TestCase):

    def test_devuelve_las_rutas_escritas(self):
        with tempfile.TemporaryDirectory() as carpeta:
            rutas = salida.escribir_todo(
                carpeta, "S1_x_ia_hoy",
                respuestas={"a": 1}, conductual=[{"episodio": 1}],
                chat=[{"autor": "agente", "texto": "hola"}],
                eventos=[{"t_experimento_s": 0, "t_unix": 0, "codigo": 1,
                          "etiqueta": "inicio_experimento", "detalle": ""}])
            self.assertEqual(len(rutas), 4)
            for r in rutas:
                self.assertTrue(os.path.exists(r))

    def test_sin_eventos_escribe_tres(self):
        """El escritorio escribe _eventos.csv en streaming, así que no lo pasa."""
        with tempfile.TemporaryDirectory() as carpeta:
            rutas = salida.escribir_todo(
                carpeta, "S1_x_ia_hoy",
                respuestas={"a": 1}, conductual=[{"episodio": 1}],
                chat=[{"autor": "agente", "texto": "hola"}])
        self.assertEqual(len(rutas), 3)

    def test_crea_la_carpeta_si_no_existe(self):
        with tempfile.TemporaryDirectory() as carpeta:
            destino = os.path.join(carpeta, "datos", "nuevo")
            salida.escribir_todo(destino, "S1_x_ia_hoy", respuestas={"a": 1},
                                 conductual=[{"episodio": 1}], chat=[])
            self.assertTrue(os.path.isdir(destino))


if __name__ == "__main__":
    unittest.main()
