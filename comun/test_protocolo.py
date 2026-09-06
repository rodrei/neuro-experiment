# -*- coding: utf-8 -*-
"""
Tests del cargador del protocolo. Corren con el Python del sistema, sin red
y sin PsychoPy:  python3 -m unittest comun.test_protocolo -v

Del lado de PsychoPy no hay suite automatizada, así que estos tests son la
única red que atrapa una extracción a medio hacer: si falta una clave que el
escritorio necesita, tiene que fallar acá y no en medio de una sesión.
"""

import unittest

from comun import protocolo


class TestTextos(unittest.TestCase):

    def test_estan_todas_las_pantallas_de_prosa(self):
        t = protocolo.textos()
        for clave in ("consentimiento", "reposo", "pausa", "debriefing",
                      "cierre"):
            self.assertIn(clave, t)
            self.assertTrue(t[clave]["cuerpo"].strip(),
                            "la pantalla %s quedó sin cuerpo" % clave)

    def test_la_cobertura_tiene_las_dos_condiciones(self):
        cobertura = protocolo.textos()["cobertura"]
        self.assertEqual(set(cobertura), {"humano", "ia"})

    def test_las_dos_coberturas_son_distintas(self):
        """Es la única manipulación del factor entre-sujetos: si fueran
        iguales, el experimento no manipula nada."""
        cobertura = protocolo.textos()["cobertura"]
        self.assertNotEqual(cobertura["humano"], cobertura["ia"])

    def test_el_chequeo_tiene_las_cinco_preguntas(self):
        chequeo = protocolo.textos()["chequeo"]
        self.assertEqual(
            set(chequeo),
            {"creencia_persona_real", "sospecha_1", "sospecha_2",
             "sospecha_3", "consiente_tras_debriefing"})


class TestEscalas(unittest.TestCase):

    def test_estan_todas_las_escalas(self):
        e = protocolo.escalas()
        self.assertEqual(
            set(e),
            {"suds", "sam_valencia", "sam_arousal", "autenticidad", "panas"})

    def test_ticks_y_etiquetas_tienen_el_mismo_largo(self):
        """PsychoPy empareja ticks con labels por posición: si no coinciden,
        las anclas quedan corridas y nadie lo nota mirando la pantalla."""
        e = protocolo.escalas()
        for clave in ("suds", "sam_valencia", "sam_arousal", "autenticidad"):
            self.assertEqual(len(e[clave]["ticks"]), len(e[clave]["etiquetas"]),
                             "ticks y etiquetas no coinciden en %s" % clave)

    def test_el_panas_tiene_una_ancla_por_tick(self):
        panas = protocolo.escalas()["panas"]
        self.assertEqual(len(panas["ticks"]), len(panas["anclas"]))

    def test_autenticidad_tiene_cuatro_items_y_uno_inverso(self):
        items = protocolo.escalas()["autenticidad"]["items"]
        self.assertEqual(len(items), 4)
        inversos = [i["clave"] for i in items if i["inverso"]]
        self.assertEqual(inversos, ["aut4_inv"])


class TestParametros(unittest.TestCase):

    def test_el_modo_real_trae_los_tiempos_del_protocolo(self):
        p = protocolo.parametros("real")
        self.assertEqual(p["dur_baseline"], 300)

    def test_el_modo_demo_acorta_los_tiempos(self):
        self.assertLess(protocolo.parametros("demo")["dur_baseline"],
                        protocolo.parametros("real")["dur_baseline"])

    def test_los_parametros_comunes_estan_en_los_dos_modos(self):
        """La fórmula de latencia es el invariante 2 del diseño: no puede
        diferir entre modos ni entre plataformas."""
        for modo in ("real", "demo"):
            p = protocolo.parametros(modo)
            self.assertEqual(p["latencia_base"], 1.2)
            self.assertEqual(p["latencia_por_caracter"], 0.045)
            self.assertEqual(p["latencia_max"], 12.0)

    def test_modo_desconocido_falla(self):
        with self.assertRaises(ValueError):
            protocolo.parametros("piloto")


class TestMarcadores(unittest.TestCase):

    def test_estan_los_dieciocho_codigos(self):
        self.assertEqual(len(protocolo.marcadores()), 18)

    def test_los_codigos_no_se_repiten(self):
        """Dos eventos con el mismo código son indistinguibles al segmentar
        el EDA offline."""
        codigos = list(protocolo.marcadores().values())
        self.assertEqual(len(codigos), len(set(codigos)))

    def test_los_codigos_entran_en_un_byte(self):
        """Los backends serie y paralelo mandan el código como un byte."""
        for etiqueta, codigo in protocolo.marcadores().items():
            self.assertTrue(0 <= codigo <= 255,
                            "%s no entra en un byte: %s" % (etiqueta, codigo))


class TestGuiones(unittest.TestCase):

    def test_estan_los_dos_saludos(self):
        g = protocolo.guiones()
        self.assertIn("saludo", g)
        self.assertIn("saludo2", g)

    def test_cada_condicion_tiene_tres_turnos(self):
        g = protocolo.guiones()
        for tipo in ("validacion", "rechazo"):
            self.assertEqual(sorted(g[tipo]), [1, 2, 3],
                             "faltan turnos en %s" % tipo)

    def test_los_turnos_estan_balanceados_en_largo(self):
        """Invariante 2: la latencia del agente es función del largo, así que
        guiones desbalanceados harían esperar distinto según la condición."""
        g = protocolo.guiones()
        largo = {t: sum(len(x) for x in g[t].values())
                 for t in ("validacion", "rechazo")}
        diferencia = abs(largo["validacion"] - largo["rechazo"])
        self.assertLess(diferencia, 0.20 * max(largo.values()),
                        "los guiones difieren más de un 20%% en largo: %s"
                        % largo)


class TestPanas(unittest.TestCase):

    def test_tiene_veinte_items(self):
        self.assertEqual(len(protocolo.panas()), 20)

    def test_diez_por_subescala(self):
        items = protocolo.panas()
        for sub in ("PA", "NA"):
            self.assertEqual(
                len([i for i in items if i["subescala"] == sub]), 10,
                "la subescala %s no tiene 10 ítems" % sub)

    def test_las_claves_no_se_repiten(self):
        claves = [i["clave"] for i in protocolo.panas()]
        self.assertEqual(len(claves), len(set(claves)))


class TestTodo(unittest.TestCase):

    def test_trae_las_siete_secciones(self):
        self.assertEqual(
            set(protocolo.todo()),
            {"textos", "escalas", "marcadores", "prompts", "parametros",
             "guiones", "panas"})

    def test_es_serializable_a_json(self):
        """Lo consume el navegador por GET /api/protocolo."""
        import json
        self.assertTrue(json.dumps(protocolo.todo()))


if __name__ == "__main__":
    unittest.main()
