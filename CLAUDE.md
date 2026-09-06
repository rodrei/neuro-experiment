# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es esto

Implementación en **PsychoPy** (Coder, no Builder) del Estudio 1 de un diseño experimental de una diplomatura en neurociencias: "Validación y rechazo: IA vs. agente humano" (Grupo 3, AI companions). Diseño 2×2 mixto: Tipo de agente (humano vs. IA, entre-sujetos, manipulado sólo por la historia de cobertura) × Retroalimentación (validación vs. rechazo, intra-sujeto, contrabalanceada). El protocolo completo está en `Pre-entrega #3 — Diseño experimental.md`.

**Todo el proyecto está en español** (código, comentarios, docs, commits): mantenerlo así.

## Cómo se corre

No hay entorno virtual propio: se usa el Python embebido en PsychoPy (3.11).

```bash
PYTHONHOME=/Applications/PsychoPy.app/Contents/Resources \
PYTHONPATH=/Applications/PsychoPy.app/Contents/Resources/lib/python3.11 \
/Applications/PsychoPy.app/Contents/MacOS/python escritorio/estudio1.py
```

O abrir `escritorio/estudio1.py` en PsychoPy Coder y Run. Salir en cualquier momento: **Ctrl+Q**.

- `MODO_DEMO = True` en `escritorio/config.py` (default): ventana chica y tiempos cortos, el flujo entero se prueba en ~3 min. Ponerlo en `False` para participantes reales.
- `MODO_TEST = True` en `escritorio/config.py` (default `False`): botón **Saltar** en cada pantalla y tecla `F9` para lo mismo. Recorre el flujo sin contestar nada. Lo salteado queda vacío en los CSV (una subescala incompleta del PANAS no lleva total) y la corrida queda marcada con `modo_test` en `_respuestas.csv`. Los helpers (`boton_salto`, `dibujar_salto`, `salto_pedido`, `soltar_raton`) viven en `escritorio/escalas.py` y los usan también `chat.py` y `estudio1.py`. `salto_pedido` consulta la tecla siempre con `keyList`, para no vaciar el buffer que necesitan las pantallas con `TextBox2` editable.
- Tests (Python puro, sin red ni PsychoPy): `python3 -m unittest discover -s comun -t . -v`. Cubren el cargador del protocolo y el agente LLM. Para el resto no hay suite: se compilan los módulos con el Python de PsychoPy (`py_compile`) y el recorrido interactivo (tipear, Enter, sliders con mouse) se prueba a mano.
- Chat de consola para iterar los prompts del LLM: `python3 -m comun.agente_llm`.

## Arquitectura

Tres capas, con la dependencia siempre en la misma dirección
(`escritorio/ → comun/ → protocolo/`, nunca al revés):

**`protocolo/`** — el contenido del experimento como datos, no como código:
prosa de las pantallas (`textos.json`), escalas (`escalas.json`), tiempos y
fórmula de latencia (`parametros.json`), códigos de marcador
(`marcadores.json`), prompts del agente LLM (`prompts.json`), y los estímulos
`guiones.csv` (saludo/saludo2 + 3 turnos de validación + 3 de rechazo) y
`panas.csv` (20 ítems con subescala).

**`comun/`** — Python compartido, sólo stdlib, sin PsychoPy.

- `protocolo.py` — único lector de `protocolo/`. Lo usan las dos plataformas, así que una corrección de redacción llega a las dos sin copiar nada.
- `agente_llm.py` — agente por LLM vía OpenRouter (opt-in con `config.AGENTE = "llm"`; default `"guionado"`). Un `AgenteLLM` nuevo por episodio; el saludo sigue guionado; si la API falla el turno cae al guion (`origen` queda en `_chat.csv`). El transporte HTTP se inyecta, por eso es testeable sin red (`test_agente_llm.py`). Sólo stdlib (`urllib`): no agregar dependencias.

**`escritorio/`** — el experimento en PsychoPy.

- `estudio1.py` — orquestador: diálogo inicial → consentimiento → línea base → historia de cobertura → 2 episodios de chat (cada uno seguido de su bloque de medidas) → chequeo de manipulación → debriefing → guardado de CSVs.
- `chat.py` — clase `Chat`: interfaz de conversación dibujada a mano con `TextBox2` (burbujas, "escribiendo…", caja de entrada). Las burbujas se construyen una sola vez por mensaje y se cachean (construirlas por frame tira los fps al piso).
- `escalas.py` — pantallas de texto y autoinforme: SUDS, SAM, autenticidad, PANAS (grilla), texto libre. `bloque_medidas()` arma el bloque completo en orden fijo SUDS → SAM → autenticidad → PANAS.
- `marcadores.py` — `RegistroEventos`: siempre loguea a CSV (`t_experimento_s` + `t_unix`); opcionalmente reenvía cada marcador por LSL / serie / paralelo según `config.BACKEND_MARCADORES`. Si el backend falla, avisa y sigue sólo con CSV (nunca voltea el experimento).
- `config.py` — sólo lo específico de PsychoPy: modo demo/test, ventana, apariencia, backend de marcadores y puertos.

**Dónde se edita qué:** el contenido del experimento (prosa, escalas, guiones,
marcadores, prompts) se edita en `protocolo/`, nunca en el código. Después de
tocar `protocolo/`, correr `python3 -m unittest discover -s comun -t . -v`.

Como PsychoPy Coder corre el archivo directo y no hay paquete instalado, los
módulos de `escritorio/` agregan la raíz del repo a `sys.path` para poder
importar `comun`.

Salida en `datos/`: cuatro CSVs por participante (`_eventos`, `_respuestas`, `_conductual`, `_chat`) con prefijo `S1_<id>_<condición>_<fecha>`.

## Invariantes del diseño experimental (no romper)

Son decisiones metodológicas, no de código; cambiarlas altera el experimento. Valen para el modo default `"guionado"`; el modo `"llm"` rompe deliberadamente los invariantes 1 y 2 y por eso es opt-in, sólo para pilotos/demos hasta que el grupo y el comité de ética lo evalúen (ver README, "Modo LLM").

1. **El agente está totalmente guionado** y el contenido es idéntico entre condiciones Humano/IA; lo único que varía es la fuente atribuida (historia de cobertura + etiqueta en la barra del chat).
2. **La latencia del agente es determinista**: `1.2 s + 0.045 s × caracteres` (tope 12 s). Los guiones están balanceados en extensión entre validación y rechazo para que la espera total quede pareja. Si se editan los guiones, re-balancear largos.
3. **La situación personal se cuenta dentro del chat** (el agente la pide; mínimo 120 caracteres). No agregar pantallas previas que la pidan: rompe la historia de cobertura.
4. **La línea base no incluye los ítems de autenticidad** (`incluir_autenticidad=False`): todavía no existe interlocutor.
5. **Orden del bloque de medidas: SUDS → SAM → autenticidad → PANAS** (las sensibles al tiempo primero; el PANAS largo al final).
6. Cada evento relevante deja marcador con timestamp (códigos en `config.MARCADORES`) para segmentar el EDA offline.

## Trampa de PsychoPy: sliders

La grilla del PANAS usa `style="rating"`. **Nunca cambiarlo a `"radio"`**: todo slider de estilo radio queda `categorical=True` y `.rating` devuelve labels en vez del número — con `labels=None` da `TypeError` al primer clic; con `labels=[""]*5` guarda `''` silenciosamente.

## Pendientes conocidos

Ver la lista completa en `README.md` ("Pendientes antes de correr participantes"): probar el recorrido interactivo a mano, cotejar la traducción del PANAS con Moriondo et al. (2012), pretest de los guiones, SAM pictórico opcional (PNGs en `protocolo/sam/`, se autodetectan), elegir backend de marcadores según el equipo de EDA.
