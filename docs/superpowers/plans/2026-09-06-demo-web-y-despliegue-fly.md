# Demo web en jsPsych y despliegue en fly.io — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el Estudio 1 corra en el navegador como demo para el grupo, servido desde fly.io, leyendo el mismo `protocolo/` que el experimento de escritorio.

**Architecture:** Un servidor chico de stdlib sirve la página, expone el protocolo como JSON, hace de proxy al LLM (la key nunca llega al navegador) y recibe los datos al final. El front-end es jsPsych con un plugin propio para el chat. El servidor reusa `comun/`, así que la demo y el escritorio corren el mismo protocolo y el mismo agente.

**Tech Stack:** Python 3 stdlib (`http.server`), jsPsych 8.3.0 vendorizado, Docker, fly.io.

**Spec:** `docs/superpowers/specs/2026-09-05-port-web-y-reorganizacion-design.md`

**Plan previo:** `docs/superpowers/plans/2026-09-05-protocolo-compartido-y-reorganizacion.md` (completo)

## Global Constraints

- **Todo en español** (código, comentarios, docstrings, commits).
- **Sin dependencias nuevas de Python.** El servidor es `http.server` de la stdlib, no Flask: son cuatro rutas, y así el `Dockerfile` no necesita `pip install`. Esto se aparta de la sección 9 del spec, que decía Flask; el spec se actualiza.
- **jsPsych va vendorizado y pineado** en `web/static/vendor/`, no por CDN: la demo tiene que andar aunque la sala tenga mal internet.
- **La key de OpenRouter nunca llega al navegador.** Sólo el servidor la ve, desde la variable `OPENROUTER_API_KEY`.
- **El navegador no parsea `protocolo/`**: lo recibe ya armado por `comun.protocolo.todo()`.
- **La web corre siempre con los parámetros `demo`** y no implementa el equivalente de `MODO_TEST`.
- **Los CSV de salida son idénticos a los del escritorio**, mismos nombres y mismas columnas, con `plataforma = web`.
- Tests: `python3 -m unittest discover -s comun -t . -v` y `python3 -m unittest discover -s web -t . -v`
- **Trampas de facturación de fly** (las cuatro del spec, son la checklist del despliegue): fijar 256 MB, IPv4 compartida, volumen de 1 GB, y nunca salir del plan legacy. Desplegar en la org `personal`.

Este plan es más liviano que el de la reorganización a propósito: la demo es descartable, y el spec ya fijó las decisiones de diseño. Donde el código es delicado (latencia del chat, proxy, formato de salida) va escrito; donde es maquetación rutinaria va especificado.

---

### Task 1: Salida compartida en `comun/salida.py`

El servidor tiene que escribir exactamente los mismos CSV que el escritorio. En vez de reimplementarlos, se extrae el escritor a `comun/` y lo usan los dos.

**Files:**
- Create: `comun/salida.py`
- Test: `comun/test_salida.py`
- Modify: `escritorio/estudio1.py` (usar el escritor compartido)

**Interfaces:**
- Produces:
  - `comun.salida.CAMPOS_EVENTOS` — `["t_experimento_s", "t_unix", "codigo", "etiqueta", "detalle"]`
  - `comun.salida.CAMPOS_CHAT` — `["autor", "texto", "origen", "t_experimento_s", "latencia_s"]`
  - `nombre_base(id_participante, condicion, sello) -> str` — `S1_<id>_<cond>_<sello>`
  - `escribir_respuestas(ruta, respuestas: dict)` — dos columnas clave/valor, claves ordenadas
  - `escribir_conductual(ruta, filas: list[dict])` — `DictWriter` sobre la unión ordenada de claves
  - `escribir_chat(ruta, filas: list[dict])` — `DictWriter` con `CAMPOS_CHAT`, `extrasaction="ignore"`
  - `escribir_eventos(ruta, filas: list[dict])` — `DictWriter` con `CAMPOS_EVENTOS`
  - `escribir_todo(carpeta, base, respuestas, conductual, chat, eventos=None) -> list[str]` — escribe los que correspondan y devuelve las rutas

- [ ] **Step 1: Escribir el test**

Crear `comun/test_salida.py` con casos que fijen el formato: que `escribir_respuestas` ordene las claves, que `escribir_conductual` una las claves de filas heterogéneas, que `escribir_chat` ignore campos de más y deje vacíos los que faltan, que `escribir_eventos` use el mismo encabezado que `RegistroEventos`, y que `nombre_base` arme el prefijo esperado.

```python
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `python3 -m unittest comun.test_salida -v`
Expected: FAIL — `ImportError: cannot import name 'salida'`

- [ ] **Step 3: Escribir `comun/salida.py`**

```python
# -*- coding: utf-8 -*-
"""
Escritura de los CSV de salida, compartida entre el escritorio y la web.

El formato es el contrato con los scripts de análisis: cuatro archivos por
participante, con el prefijo S1_<id>_<condición>_<fecha>. Vive acá para que
las dos plataformas no puedan divergir en las columnas.
"""

import csv
import os

CAMPOS_EVENTOS = ["t_experimento_s", "t_unix", "codigo", "etiqueta", "detalle"]
CAMPOS_CHAT = ["autor", "texto", "origen", "t_experimento_s", "latencia_s"]


def nombre_base(id_participante, condicion, sello):
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
    """Escribe los cuatro CSV y devuelve las rutas."""
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
```

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest comun.test_salida -v`
Expected: PASS

- [ ] **Step 5: Que el escritorio use el escritor compartido**

En `escritorio/estudio1.py`, reemplazar los tres bloques `with open(...)` del final de `main()` por:

```python
    salida.escribir_todo(carpeta, base,
                         respuestas=respuestas,
                         conductual=conductual,
                         chat=conv.transcripcion)
```

y el armado del nombre por `base = salida.nombre_base(info["id_participante"], info["condicion_agente"], sello)`. Agregar `from comun import salida` a los imports. El `_eventos.csv` lo sigue escribiendo `RegistroEventos` en streaming, así que no se pasa `eventos`.

Verificar: `python3 -m py_compile escritorio/estudio1.py` y que `csv` siga usándose (si no, sacar el import).

- [ ] **Step 6: Commit**

```bash
git add comun escritorio/estudio1.py
git commit -m "Escritor de CSV compartido en comun/salida.py"
```

---

### Task 2: El servidor — estáticos y protocolo

**Files:**
- Create: `web/__init__.py`, `web/servidor/__init__.py`, `web/servidor/app.py`
- Test: `web/test_servidor.py`
- Create: `web/index.html` (mínimo, para que el `GET /` sirva algo)

**Interfaces:**
- Produces:
  - `web.servidor.app.crear_servidor(puerto=0, carpeta_datos=None) -> ThreadingHTTPServer`
  - `web.servidor.app.Manejador` — `BaseHTTPRequestHandler` con las cuatro rutas
  - `CODIGO_ACCESO` desde la variable de entorno del mismo nombre (vacío = sin código)
  - Rutas: `GET /`, `GET /static/*`, `GET /js/*`, `GET /api/protocolo`, `GET /api/salud`, `POST /api/turno`, `POST /api/datos`

- [ ] **Step 1: Escribir el test de estáticos y protocolo**

`web/test_servidor.py` levanta el servidor en un puerto efímero en un hilo y le pega con `urllib`. Casos: `/api/salud` devuelve 200 y `{"ok": true}`; `/api/protocolo` trae las siete secciones y es JSON; `GET /` devuelve HTML; una ruta inexistente da 404; y `/api/protocolo` trae los guiones con las claves de turno como strings (que es como las ve el navegador).

- [ ] **Step 2: Correr y verificar que falla**

Run: `python3 -m unittest discover -s web -t . -v`
Expected: FAIL (no existe `web.servidor.app`)

- [ ] **Step 3: Escribir el servidor con las rutas de lectura**

`Manejador` con `do_GET`, un mapa de rutas, tipos MIME por extensión, y `_json(codigo, obj)` / `_error(codigo, mensaje)` como helpers. Los estáticos se sirven desde `web/` con verificación de que la ruta resuelta siga dentro de `web/` (para no servir `../../openrouter_key.txt`).

- [ ] **Step 4: Verificar que pasa**

Run: `python3 -m unittest discover -s web -t . -v`
Expected: PASS

- [ ] **Step 5: Commit**

---

### Task 3: El proxy del LLM y la recepción de datos

**Files:**
- Modify: `web/servidor/app.py` (`do_POST`)
- Modify: `web/test_servidor.py`

**Interfaces:**
- `POST /api/turno` ← `{"tipo", "historial", "guion_fallback", "codigo"}` → `{"texto", "origen"}`
- `POST /api/datos` ← `{"info", "respuestas", "conductual", "chat", "eventos", "codigo"}` → `{"ok": true, "archivos": [...]}`

- [ ] **Step 1: Escribir los tests**

Casos: sin código de acceso correcto, `/api/turno` da 403; con código, reconstruye el `AgenteLLM` del tipo pedido, le replica el historial y devuelve `{texto, origen}`; un `tipo` inválido da 400; si el transporte falla, devuelve el `guion_fallback` con `origen = "fallback"` y **200** (la demo no se cae); `/api/datos` escribe los cuatro CSV en la carpeta configurada y devuelve sus nombres; `/api/datos` con `plataforma` fuerza `"web"`.

Para no llamar a OpenRouter en los tests, el módulo expone `TRANSPORTE = None` y el test lo pisa con uno falso.

- [ ] **Step 2: Verificar que fallan**

- [ ] **Step 3: Implementar `do_POST`**

El proxy es **sin estado**: reconstruye `AgenteLLM(tipo, transporte=TRANSPORTE, timeout=TIMEOUT)`, le carga el historial recibido y llama a `responder(guion_fallback)`. Nada se guarda entre pedidos.

```python
def _turno(self, cuerpo):
    tipo = cuerpo.get("tipo")
    if tipo not in agente_llm.TIPOS_VALIDOS:
        return self._error(400, "tipo invalido")
    agente = agente_llm.AgenteLLM(tipo, transporte=TRANSPORTE,
                                  timeout=TIMEOUT_LLM)
    for mensaje in cuerpo.get("historial", []):
        if mensaje.get("role") == "user":
            agente.escucha(mensaje.get("content", ""))
        else:
            agente.saluda(mensaje.get("content", ""))
    texto, origen = agente.responder(cuerpo.get("guion_fallback", ""))
    return self._json(200, {"texto": texto, "origen": origen})
```

Límite de tasa: un diccionario `{ip: [timestamps]}` con ventana de 60 s y tope configurable por `LIMITE_POR_MINUTO` (default 30). Al pasarse, 429.

- [ ] **Step 4: Verificar que pasan**

- [ ] **Step 5: Commit**

---

### Task 4: Vendorizar jsPsych y la página de arranque

**Files:**
- Create: `web/static/vendor/` (jsPsych 8.3.0 y plugins, pineados)
- Create: `web/index.html`, `web/static/estilos.css`
- Create: `web/js/protocolo.js`

**Interfaces:**
- `window.PROTOCOLO` — el objeto de `/api/protocolo`, ya cargado
- `cargarProtocolo() -> Promise`
- `window.CONFIG_SESION` — `{id, edad, sexo, condicion, orden, agente, codigo}` del formulario

- [ ] **Step 1: Bajar y pinear jsPsych**

```bash
mkdir -p web/static/vendor
cd web/static/vendor
curl -sLO https://cdn.jsdelivr.net/npm/jspsych@8.3.0/dist/index.browser.min.js
mv index.browser.min.js jspsych.js
curl -sL https://cdn.jsdelivr.net/npm/jspsych@8.3.0/css/jspsych.css -o jspsych.css
for p in html-button-response@2.1.0 html-slider-response@2.1.0 survey-likert@2.2.0 survey-text@2.1.1 html-keyboard-response@2.2.0; do
  nombre="${p%@*}"
  curl -sL "https://cdn.jsdelivr.net/npm/@jspsych/plugin-${p}/dist/index.browser.min.js" -o "plugin-${nombre}.js"
done
```

Verificar que cada archivo pesa más de 1 KB y que ninguno es una página de error.

- [ ] **Step 2: `index.html`**

Formulario de arranque (id, edad, sexo, condición humano/ia, orden 1/2, modo de agente guionado/llm, código de acceso), un aviso para teléfonos, y el contenedor de jsPsych. Los `<script>` van en orden: vendor, `protocolo.js`, `chat-plugin.js`, `escalas.js`, `experimento.js`.

El modo de agente va en el formulario a propósito: es lo que permite alternar guionado/LLM en vivo delante del grupo.

- [ ] **Step 3: `estilos.css`** — burbujas de chat, barra del agente, caja de entrada, formulario, y el aviso de móvil por `@media (max-width: 700px)`.

- [ ] **Step 4: `protocolo.js`** — `fetch("/api/protocolo")`, guardar en `window.PROTOCOLO`, fallar con un mensaje visible si el servidor no responde.

- [ ] **Step 5: Verificar a mano** que `python3 -m web.servidor.app` levanta y la página carga el protocolo (consola sin errores).

- [ ] **Step 6: Commit**

---

### Task 5: El plugin de chat

**Files:**
- Create: `web/js/chat-plugin.js`

**Interfaces:**
- Plugin jsPsych `chat-episodio`, parámetros: `tipo`, `episodio`, `etiqueta`, `modo_agente`, `codigo`
- Devuelve en `data`: `{episodio, tipo, situacion, situacion_caracteres, latencia_situacion, respuesta_1..2, latencia_1..2, respuesta_final, latencia_final, respondio_al_final, transcripcion, eventos}`

Es la pieza no trivial: replica `escritorio/chat.py` y `correr_episodio()` de `estudio1.py` en un solo trial.

- [ ] **Step 1: La latencia determinista**

Es el invariante 2 y tiene que salir de `parametros`, no de constantes propias:

```js
function latenciaDe(texto, p) {
  const t = p.latencia_base + texto.length * p.latencia_por_caracter;
  return Math.min(t, p.latencia_max) * 1000;   // ms
}
```

- [ ] **Step 2: `agenteDice(texto, etiquetaMarcador, origen)`**

Estado "en línea" durante `dur_lectura_min`, después "escribiendo…" durante `latenciaDe(texto)`, después la burbuja y el marcador. En modo LLM la generación ocurre **antes**, mientras dice "en línea", y la latencia se aplica sobre el texto ya generado — igual que en el escritorio.

- [ ] **Step 3: `esperarParticipante({timeout, minimoCaracteres, marcador})`**

Promesa que resuelve `{texto, latencia}`. Contador de caracteres en vivo, Enter o botón para enviar, y si se agota el timeout sin texto resuelve `{texto: "", latencia: null}` y deja `[sin respuesta]` en la transcripción. No contestar es un dato.

- [ ] **Step 4: El episodio completo**

`saludo` (guionado siempre) → `esperarParticipante` con el mínimo de caracteres → 3 turnos con respuesta libre entre medio → ventana final. En modo LLM, cada turno pide `POST /api/turno` con el historial y usa `guion_fallback` del guion del tipo.

- [ ] **Step 5: Verificar a mano** el episodio entero en el navegador, en los dos modos.

- [ ] **Step 6: Commit**

---

### Task 6: Escalas y timeline

**Files:**
- Create: `web/js/escalas.js`, `web/js/experimento.js`

**Interfaces:**
- `escalas.js`: `pantallaTexto(titulo, cuerpo)`, `escalaSlider(spec)`, `bloqueMedidas(momento, incluirAutenticidad)`, `panasTrials()`, `totalesPanas(data)`
- `experimento.js`: arma el timeline y hace el `POST /api/datos`

- [ ] **Step 1: `escalaSlider` con `require_movement`**

```js
function escalaSlider(spec, clave) {
  return {
    type: jsPsychHtmlSliderResponse,
    stimulus: `<p class="enunciado">${spec.enunciado}</p>`,
    labels: spec.etiquetas.map(e => e.replace(/\n/g, "<br>")),
    min: spec.ticks[0],
    max: spec.ticks[spec.ticks.length - 1],
    step: spec.ticks[1] - spec.ticks[0],
    slider_start: spec.ticks[Math.floor(spec.ticks.length / 2)],
    require_movement: true,          // sin esto todos "contestan" el punto medio
    button_label: "Continuar",
    data: { clave: clave },
  };
}
```

`require_movement: true` es obligatorio en **todas** las escalas: un `input[type=range]` siempre tiene valor, así que sin esto se registran puntos medios falsos.

- [ ] **Step 2: PANAS en dos páginas de 10 con `survey-likert`**, y los totales con la misma regla que el escritorio: una subescala incompleta **no** tiene total.

- [ ] **Step 3: `bloqueMedidas`** en el orden fijo SUDS → SAM → autenticidad → PANAS, con `incluirAutenticidad = false` en la línea base.

- [ ] **Step 4: El timeline** — transcripción de `main()`: consentimiento → reposo (cruz, `dur_baseline`) → medidas base sin autenticidad → cobertura → episodio A + medidas → pausa → episodio B + medidas → chequeo (creencia + 3 sospechas) → debriefing **del modo usado** → reconsentimiento → cierre → envío.

El debriefing sale de `PROTOCOLO.textos.debriefing.cuerpo[modo_agente]`, igual que en el escritorio.

- [ ] **Step 5: El envío** — arma `respuestas`, `conductual`, `chat` y `eventos` y los manda a `/api/datos`. Si falla, ofrece descargar un JSON para no perder la sesión.

- [ ] **Step 6: Recorrido completo a mano en el navegador.**

- [ ] **Step 7: Commit**

---

### Task 7: Docker y despliegue en fly.io

**Files:**
- Create: `Dockerfile`, `fly.toml`, `.dockerignore` (los tres en la **raíz**: el contenedor necesita `protocolo/`, `comun/` y `web/`)
- Create: `web/README.md`

- [ ] **Step 1: `.dockerignore`**

```
escritorio/
capturas/
docs/
datos/
openrouter_key.txt
__pycache__/
*.pyc
.git/
```

- [ ] **Step 2: `Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY protocolo/ ./protocolo/
COPY comun/ ./comun/
COPY web/ ./web/

ENV PUERTO=8080 CARPETA_DATOS=/datos
EXPOSE 8080
CMD ["python", "-m", "web.servidor.app"]
```

Sin `pip install`: el servidor es stdlib.

- [ ] **Step 3: Probar la imagen local**

```bash
docker build -t estudio1-web .
docker run --rm -p 8080:8080 -e CODIGO_ACCESO=probando estudio1-web
```

Verificar `/api/salud` y `/api/protocolo`, y recorrer la demo.

- [ ] **Step 4: `fly.toml`**

```toml
app = "neuro-estudio1-demo"
primary_region = "eze"

[build]

[env]
  PUERTO = "8080"
  CARPETA_DATOS = "/datos"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 0

[[mounts]]
  source = "datos"
  destination = "/datos"

[[vm]]
  size = "shared-cpu-1x"
  memory = "256mb"
```

`memory = "256mb"` y `size = "shared-cpu-1x"` son la trampa 1: cualquier cosa más grande sale de la asignación legacy.

- [ ] **Step 5: Crear la app en la org correcta**

```bash
fly apps create neuro-estudio1-demo --org personal
fly volumes create datos --region eze --size 1 --app neuro-estudio1-demo --yes
```

`--size 1` es la trampa 3: los volúmenes se cobran por capacidad provisionada.

- [ ] **Step 6: Secretos**

```bash
fly secrets set OPENROUTER_API_KEY="$(cat openrouter_key.txt)" --app neuro-estudio1-demo
fly secrets set CODIGO_ACCESO="<código>" --app neuro-estudio1-demo
```

- [ ] **Step 7: Desplegar**

```bash
fly deploy --app neuro-estudio1-demo
```

- [ ] **Step 8: Verificar las cuatro trampas después de desplegar**

```bash
fly status --app neuro-estudio1-demo          # 1 máquina, 256 MB
fly ips list --app neuro-estudio1-demo        # v4 COMPARTIDA, no dedicada
fly volumes list --app neuro-estudio1-demo    # 1 GB
```

Si aparece una IPv4 dedicada, liberarla: `fly ips release <addr>`.

- [ ] **Step 9: Verificar la demo desplegada** — `/api/salud`, `/api/protocolo`, y un recorrido completo contra la URL pública.

- [ ] **Step 10: `web/README.md`** con cómo correrla local, cómo desplegar, y cómo bajar los datos (`fly sftp get`).

- [ ] **Step 11: Commit**
