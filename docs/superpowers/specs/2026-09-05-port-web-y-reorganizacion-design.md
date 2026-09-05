# Port a navegador + reorganización del repo

**Fecha:** 2026-09-05
**Estado:** diseño aprobado, pendiente de plan de implementación

## 1. Contexto y objetivo

El Estudio 1 existe hoy como una aplicación de escritorio en PsychoPy Coder que
corre en la máquina del laboratorio, con registro de actividad electrodérmica
(EDA) sincronizado por marcadores. Se quiere además una versión que corra en el
navegador, para **mostrarle el estudio al grupo y a la cátedra, y para iterar
guiones y prompts con conocidos**.

La versión web **no reemplaza** al experimento de escritorio ni sirve para
correr participantes reales: no hay EDA, y en modo LLM tampoco hay control de
contenido entre condiciones.

El objetivo secundario, y el que deja valor permanente, es **separar las dos
implementaciones sin duplicar el contenido del experimento**.

## 2. Decisiones tomadas

| Decisión | Elección |
| --- | --- |
| Propósito de la web | Demo / piloto del grupo |
| Horizonte | Descartable: mostrarlo y listo |
| Agente soportado | Los dos (guionado y LLM) |
| Stack front-end | jsPsych |
| Estructura del repo | `protocolo/` compartido |

Del cruce entre "descartable" y "`protocolo/` compartido" se desprende el
principio que ordena todo el diseño:

> **La reorganización es permanente; la aplicación web es descartable.**

`protocolo/` se justifica por sí solo, aunque la demo se tire a la basura
después de la presentación: hace auditable el contenido del experimento de
escritorio, que hoy está desparramado como literales de Python en tres archivos.
El front-end web, en cambio, se diseña para la velocidad y se acepta deuda
técnica a sabiendas.

## 3. Invariantes del diseño experimental

`CLAUDE.md` enumera seis invariantes metodológicos. La versión web no puede
sostener tres de ellos, y eso tiene que quedar escrito en la documentación en
vez de descubrirse después:

| Invariante | En la web |
| --- | --- |
| 1. Agente totalmente guionado | **Roto en modo LLM** (ya era opt-in en escritorio) |
| 2. Latencia determinista | **Se conserva**: misma fórmula, leída de `parametros.json` |
| 3. La situación se cuenta dentro del chat | **Se conserva** |
| 4. Línea base sin ítems de autenticidad | **Se conserva** |
| 5. Orden SUDS → SAM → autenticidad → PANAS | **Se conserva** |
| 6. Un marcador con timestamp por evento | **Roto**: no hay EDA que segmentar. El log se escribe igual, con el mismo esquema |

El comportamiento del experimento de escritorio **no cambia en nada**. Su
contenido se muda a `protocolo/` y lo vuelve a leer de ahí: mismas pantallas,
mismo orden, mismos CSV, mismos marcadores.

## 4. Estructura de archivos

```
protocolo/            # el experimento como DATOS. Fuente de verdad única.
  textos.json
  escalas.json
  parametros.json
  marcadores.json
  prompts.json
  guiones.csv         # git mv desde stim/
  panas.csv           # git mv desde stim/
  sam/                # PNGs opcionales del SAM pictórico, si algún día existen
  README.md

comun/                # Python compartido. Sólo stdlib, sin PsychoPy.
  __init__.py
  protocolo.py
  agente_llm.py       # git mv, sin cambios de lógica
  test_protocolo.py
  test_agente_llm.py  # git mv

escritorio/           # PsychoPy. Comportamiento idéntico al actual.
  estudio1.py
  chat.py
  escalas.py
  marcadores.py
  config.py

web/                  # jsPsych. Descartable.
  index.html
  js/
    protocolo.js
    chat-plugin.js
    escalas.js
    experimento.js
  static/
    estilos.css
    vendor/           # jsPsych 8.x pineado, no CDN
  servidor/
    app.py
    requisitos.txt
  README.md

datos/                # sin cambios, sigue gitignoreado
docs/
  Pre-entrega #3 — Diseño experimental.md    # git mv desde la raíz
  superpowers/specs/
capturas/
```

Los movimientos se hacen con `git mv` para no perder el historial.

## 5. `protocolo/` — la fuente de verdad

El riesgo real de tener dos implementaciones no es el port: es la **divergencia
silenciosa**. Hoy los textos de cobertura, el consentimiento, el debriefing, los
ítems de autenticidad, las anclas de SUDS y SAM, los códigos de marcador y las
constantes de latencia viven como literales de Python repartidos entre
`config.py`, `escalas.py` y `estudio1.py`. Si la web copia todo eso a JavaScript,
la próxima corrección de redacción deja dos experimentos distintos y nadie puede
decir después cuál vio cada participante.

### `textos.json`

Prosa que hoy está incrustada en `estudio1.py` y `config.py`:

```json
{
  "consentimiento": {"titulo": "Antes de empezar", "cuerpo": "..."},
  "reposo": {"titulo": "Registro en reposo", "cuerpo": "..."},
  "pausa": {"titulo": "Pausa", "cuerpo": "..."},
  "debriefing": {"titulo": "Sobre lo que acabás de hacer", "cuerpo": "..."},
  "cierre": {"cuerpo": "...", "pie": "Presioná ESPACIO para terminar"},
  "conectando": "Conectando…",
  "nombre_agente": "Alex",
  "etiqueta_agente": {"humano": "...", "ia": "..."},
  "cobertura": {"humano": "...", "ia": "..."},
  "chequeo": {
    "creencia_persona_real": {"enunciado": "...", "anclas": ["..."]},
    "sospecha_1": "...",
    "sospecha_2": "...",
    "sospecha_3": "...",
    "consiente_tras_debriefing": {"enunciado": "...", "anclas": ["...", "..."]}
  }
}
```

### `escalas.json`

SUDS, SAM (valencia y arousal, con los nombres de los PNG opcionales), los
cuatro ítems de autenticidad marcando cuál es inverso, las anclas Likert de 7
puntos, y las anclas y la consigna del PANAS.

```json
{
  "suds": {"enunciado": "...", "ticks": [0, 10, "…", 100], "etiquetas": ["..."]},
  "sam_valencia": {"enunciado": "...", "ticks": [1, "…", 9], "etiquetas": ["..."], "imagenes": ["val_1.png", "…"]},
  "sam_arousal":  {"...": "…"},
  "autenticidad": {
    "items": [
      {"clave": "aut1", "enunciado": "...", "inverso": false},
      {"clave": "aut4_inv", "enunciado": "...", "inverso": true}
    ],
    "ticks": [1, "…", 7],
    "etiquetas": ["..."]
  },
  "panas": {"consigna": "...", "ticks": [1, 2, 3, 4, 5], "anclas": ["..."], "items_por_pagina": 10}
}
```

`aut4_inv` hoy se marca sólo por convención en el nombre y un comentario. Pasa a
ser un campo (`"inverso": true`), que es donde tiene que estar antes de que
alguien promedie la subescala.

### `parametros.json`

Con las dos variantes que hoy resuelve el ternario `if MODO_DEMO`:

```json
{
  "real": {"dur_baseline": 300, "dur_conectando": 8, "ventana_respuesta_libre": 120, "timeout_situacion": 300},
  "demo": {"dur_baseline": 15,  "dur_conectando": 3, "ventana_respuesta_libre": 20,  "timeout_situacion": 60},
  "comun": {
    "latencia_base": 1.2,
    "latencia_por_caracter": 0.045,
    "latencia_max": 12.0,
    "dur_lectura_min": 1.0,
    "min_caracteres_situacion": 120,
    "texto_relleno_test": "..."
  }
}
```

La fórmula de latencia queda en `comun` a propósito: es el invariante 2, y no
debe poder diferir entre plataformas ni entre modos.

### `marcadores.json`

Los 18 códigos de `config.MARCADORES`, tal cual.

### `prompts.json`

`ROL` por tipo, la plantilla `REGLAS`, y los parámetros del modelo que afectan lo
que el agente dice:

```json
{
  "reglas": "plantilla con {nombre} {rol} {maximo} {ejemplos}",
  "rol": {"validacion": "...", "rechazo": "..."},
  "modelo": "anthropic/claude-haiku-4.5",
  "temperatura": 0.7,
  "max_tokens": 300,
  "max_caracteres": 350
}
```

`modelo` y `temperatura` van acá, no en la config de cada plataforma: si la demo
corriera con otro modelo que el escritorio, sería exactamente la divergencia que
se quiere evitar. `timeout_llm` sí es operativo y queda en cada plataforma.

### `guiones.csv` y `panas.csv`

Se mueven sin cambios desde `stim/`.

## 6. `comun/` — código Python compartido

### `protocolo.py`

Carga y valida `protocolo/`. Expone funciones (`textos()`, `escalas()`,
`parametros(modo)`, `marcadores()`, `prompts()`, `guiones()`, `panas()`) con
caché en memoria. Sólo stdlib: `json`, `csv`, `os`.

Es la pieza que hace que **las dos plataformas lean el protocolo con el mismo
código Python**. El navegador no parsea los CSV: el servidor expone
`GET /api/protocolo` con un JSON armado por este mismo cargador.

Consecuencia a tener presente: **la versión web siempre necesita el servidor**,
incluso en modo guionado.

### `test_protocolo.py`

Afirma que existen todas las claves que necesita el escritorio, que los ticks y
las etiquetas de cada escala tienen largos compatibles, que los 18 marcadores
están, que `guiones.csv` tiene saludo, saludo2 y tres turnos de cada tipo, y que
`panas.csv` tiene 20 ítems, 10 por subescala.

Importa porque del lado de PsychoPy no hay suite automatizada: es la única red
que atrapa una extracción a medio hacer.

### `agente_llm.py`

Se mueve sin cambios de lógica. Los únicos ajustes son leer `ROL`/`REGLAS`/modelo
desde `protocolo.prompts()` en vez de tener las constantes adentro, y que
`_ejemplos_de_guion()` lea `protocolo/guiones.csv`.

El transporte ya es inyectable, así que sigue siendo testeable sin red.

## 7. `escritorio/` — qué cambia

Cambio mecánico: cada literal se reemplaza por una lectura de `comun.protocolo`.

- `estudio1.py`: los cinco bloques de prosa y las cuatro preguntas del chequeo.
- `escalas.py`: `SUDS_*`, `SAM_*`, `ITEMS_AUTENTICIDAD`, `LIKERT7`, `PANAS_*`.
- `config.py`: se van `COBERTURA`, `ETIQUETA_AGENTE`, `NOMBRE_AGENTE`,
  `MARCADORES`, tiempos, latencias y parámetros del LLM.
- `marcadores.py`: lee los códigos de `protocolo.marcadores()`.
- `escalas.py`: `CARPETA_SAM` pasa a apuntar a `protocolo/sam/`, para que la
  autodetección de los PNG opcionales siga funcionando después del movimiento.
- `estudio1.py`: `_respuestas.csv` suma el campo `plataforma` con el valor
  `escritorio`.

`config.py` conserva sólo lo específico de la plataforma: `MODO_DEMO`,
`MODO_TEST`, `TECLA_SALTO`, `PANTALLA_COMPLETA`, `TAMANO_VENTANA`, colores,
`FUENTE`, `ALTURA_LETRA`, `ANCHO_BURBUJA_MAX`, `BACKEND_MARCADORES`, puertos
serie y paralelo, `TIMEOUT_LLM`, `AGENTE`.

Como PsychoPy Coder corre el archivo directo y no hay entorno virtual ni paquete
instalado, `estudio1.py` agrega al inicio la raíz del repo a `sys.path` para
poder importar `comun`.

## 8. `web/` — front-end jsPsych

### `experimento.js`

El timeline es una transcripción directa de `main()` en `estudio1.py`:

formulario de inicio → pantalla completa → consentimiento → reposo (cruz de
fijación) → bloque de medidas de línea base (sin autenticidad) → cobertura →
episodio A + bloque de medidas → pausa → episodio B + bloque de medidas →
chequeo de manipulación → debriefing → consentimiento posterior → envío.

El formulario de inicio reemplaza a `gui.DlgFromDict`: id, edad, sexo, condición
(humano/ia), orden (1/2), **modo de agente** (guionado/llm) y código de acceso.
El modo de agente va en el formulario, y no en un archivo de configuración, para
poder alternarlo en vivo delante del grupo.

### `chat-plugin.js`

Plugin propio de jsPsych. Es la única pieza no trivial: hace todo lo que hace
`chat.py` menos la maquetación manual.

- Burbujas en una columna flex, la más nueva abajo. El `_construir_burbuja` de
  PsychoPy (maqueta provisoria para contar líneas, alto exacto, reposicionado
  por frame) desaparece: lo hace CSS.
- Barra superior con `etiqueta_agente` y estado "en línea" / "escribiendo…".
- Latencia determinista: `latencia_base + largo × latencia_por_caracter`, con
  tope, precedida por `dur_lectura_min`. En modo LLM la generación ocurre
  mientras el estado dice "en línea", y **la latencia se aplica después, en
  función del largo del texto ya generado**, igual que en `agente_dice()`.
- Caja de entrada con mínimo de caracteres y contador en vivo, envío con Enter o
  con el botón.
- Timeout: si se agota sin texto, registra `[sin respuesta]`. No contestar es un
  dato del diseño, no un error.
- Mide la latencia de cada respuesta del participante.

Estimado: ~250 líneas, contra las 277 de `chat.py`.

### `escalas.js`

Usa plugins de stock:

- SUDS, SAM y autenticidad: `html-slider-response` con **`require_movement: true`**.
- PANAS: dos trials de `survey-likert` de 10 ítems cada uno.

`require_movement` es crítico. Un `input[type=range]` de HTML siempre tiene un
valor; sin esa opción, todo participante que no toque el control "contesta" el
punto medio en silencio. Es el equivalente en navegador de la trampa de
`style="radio"` que ya está documentada para PsychoPy.

Los totales PA/NA se calculan con la misma regla que hoy: **una subescala
incompleta no tiene total** (`None`), para que un total parcial no se lea después
como un dato válido.

### Tiempos y modo test

La web corre siempre con los parámetros `demo` de `parametros.json`: la línea
base de 5 minutos no tiene sentido delante de una clase, y sin EDA tampoco tiene
función. **No se implementa el equivalente del `MODO_TEST`** (botón Saltar y
tecla F9): con los tiempos cortos ya se recorre el flujo entero en pocos minutos,
y sostener dos mecanismos de salteo en la demo no se paga.

### Registro de eventos

Sin LSL ni puerto serie. Se acumula en memoria un log con el mismo esquema que
`_eventos.csv` (`t_experimento_s`, `t_unix`, `codigo`, `etiqueta`, `detalle`) y
se manda al final junto con el resto.

## 9. `web/servidor/app.py`

Una aplicación Flask chica con cuatro responsabilidades:

| Ruta | Qué hace |
| --- | --- |
| `GET /` y estáticos | Sirve `web/` |
| `GET /api/protocolo` | JSON armado por `comun.protocolo`, con los CSV ya parseados |
| `POST /api/turno` | Proxy al LLM |
| `POST /api/datos` | Recibe la sesión y escribe los CSV |

### Por qué hace falta un proxy

La key de OpenRouter no puede viajar al navegador: lo que la página puede leer,
el participante también. La llamada tiene que hacerla algo que el participante no
controle.

### El proxy es sin estado

El navegador manda `{tipo, historial, codigo}`; el servidor reconstruye
`AgenteLLM(tipo)`, le replica el historial y llama a `responder()`. Devuelve
`{texto, origen}`.

Sin almacén de sesiones: el servidor se puede reiniciar en medio de la demo y
soporta varios participantes en paralelo sin trabajo extra. Y como reusa
`AgenteLLM` en vez de reimplementarlo, la demo usa **demostrablemente los mismos
prompts** que el escritorio, y el camino de caída al guion cuando la API falla
viene de arriba: una API caída degrada en el navegador igual que en el escritorio.

### Control de abuso

Es una URL pública que gasta crédito de OpenRouter. Alcanza con un código de
acceso compartido, verificado del lado del servidor, y un límite de tasa por IP.

## 10. Datos

`POST /api/datos` escribe **los mismos cuatro CSV, con los mismos nombres** que
el escritorio:

```
S1_<id>_<condicion>_<fecha>_eventos.csv
S1_<id>_<condicion>_<fecha>_respuestas.csv
S1_<id>_<condicion>_<fecha>_conductual.csv
S1_<id>_<condicion>_<fecha>_chat.csv
```

Cualquier script de análisis funciona sobre las dos plataformas sin saber cuál
generó el archivo. `_respuestas.csv` incluye `plataforma` (`escritorio` / `web`)
además de los campos actuales `agente`, `modo_test` y `modelo_llm`.

## 11. Hospedaje: fly.io vs. Vercel vs. VPS

El VPS de 2 vCPU / 4 GB / 40 GB está sobrado: una sesión completa produce unos
16 KB de CSV, y las llamadas al LLM salen hacia afuera. El recurso nunca fue el
problema. La pregunta es cuál da **menos trabajo de operación** para una demo.

### Vercel — no simplifica

Es lo más simple para la mitad estática, y rompe la otra mitad:

- **No hay filesystem persistente.** Las funciones sólo escriben en `/tmp`, que
  es efímero por invocación. `POST /api/datos` escribiendo CSV **no funciona**:
  habría que reescribir la persistencia contra Vercel Blob, S3 o Postgres. Es un
  cambio al diseño de datos, no un detalle de despliegue.
- El límite de duración de función aprieta contra `TIMEOUT_LLM = 20`, según el
  plan.
- El runtime de Python es de segunda respecto del de Node.

Sólo es viable si se abandona la persistencia del lado del servidor (ver la
variante más abajo).

### fly.io — **recomendado**

- Contenedor de verdad: la app Flask corre tal cual, sin reescribir nada.
- **Volumen persistente** montado donde hoy está `datos/`: el diseño de CSV
  sobrevive intacto.
- TLS automático en `*.fly.dev`. Sin Caddy, sin systemd, sin renovar
  certificados, sin parchear el sistema operativo.
- `fly secrets set OPENROUTER_API_KEY=…` alcanza: `cargar_api_key()` **ya** lee
  esa variable de entorno antes de buscar el archivo. Cero cambios de código.
- `auto_stop_machines` deja el costo cerca de cero entre demos.
- Toda la configuración son un `Dockerfile` y un `fly.toml`; el despliegue es
  `fly deploy`.

Contras: una cuenta y una relación de facturación más; el volumen está atado a
una máquina, así que hay que bajar los CSV con `fly sftp get` después de cada
demo y no confiar en que queden ahí. Verificar el precio vigente antes de
comprometerse: el esquema de planes de fly cambió más de una vez.

### VPS — la alternativa sin cuentas nuevas

Ya está pago y ya existe, así que el costo marginal es cero. El costo es de
operación: usuario, firewall, Caddy o nginx, unidad de systemd, script de
despliegue y actualizaciones del sistema. A cambio da acceso SSH para depurar en
vivo durante la presentación, que no es poco cuando estás mostrando algo delante
de la cátedra.

**Tiene además un argumento de privacidad propio.** En modo guionado sobre el
VPS, el texto libre del participante —situaciones personales que lo movilizaron—
nunca sale de infraestructura propia. En fly.io sí. En modo LLM el punto se
diluye, porque ese texto ya viaja a OpenRouter y al proveedor del modelo. Para
una demo con voluntarios es una nota al pie, no un bloqueo, pero conviene
decirlo en el debriefing.

### Variante: sin persistencia del lado del servidor

Como la demo es descartable, una tercera opción es que jsPsych le ofrezca al
participante descargar sus propios CSV al terminar, y que el operador los junte.
El servidor queda reducido al proxy del LLM, y Vercel pasa a ser viable y
trivial. Se pierde la recolección centralizada y se depende de que nadie cierre
la pestaña antes de tiempo.

### Decisión

**fly.io**, con el VPS como alternativa si no se quiere abrir otra cuenta. El
despliegue queda detrás de una interfaz chica (`Dockerfile` + `fly.toml` + un
`README`), así que cambiar de opinión después cuesta poco.

## 12. Riesgos

**El riesgo principal**: el paso de extracción toca `estudio1.py`, `escalas.py`,
`config.py` y `marcadores.py` —código que funciona y que corre participantes
reales— en beneficio de una demo descartable.

Mitigación: el cambio es mecánico (literal → lectura de diccionario),
`test_protocolo.py` atrapa las claves faltantes, y el paso termina con una
corrida manual completa en `MODO_TEST` antes de seguir con la web. Los
movimientos van con `git mv` y en un commit separado de los cambios de
contenido, para que el diff sea legible.

**Alternativa más barata**, si el riesgo no se quiere correr: mover sólo `stim/`
a `protocolo/`, que la web lea `guiones.csv` y `panas.csv`, y duplicar la prosa
en JavaScript. No toca el escritorio, al precio de la divergencia que se quería
evitar.

**Riesgos menores**: que el plugin de chat quede pesado en navegadores viejos
(se prueba en Chrome y Firefox actuales, nada más); que `require_movement` se
olvide en alguna escala y se registren puntos medios falsos (lo cubre una
revisión de `escalas.js` contra `escalas.json`); que la key quede en el
repositorio al preparar el despliegue (`openrouter_key.txt` ya está
gitignoreado y en fly se usa `fly secrets`).

## 13. Fuera de alcance

Por ser una demo descartable, **no** se hace: base de datos, cuentas de
participante, chequeos de atención, SAM pictórico, soporte para teléfonos (un
cartel que mande a usar una computadora), equivalente de LSL o puerto serie,
internacionalización, panel de administración, ni Docker más allá de lo que
fly.io necesita.

## 14. Esfuerzo estimado

| Paso | Estimado |
| --- | --- |
| `protocolo/` + `comun/protocolo.py` + tests | 1 sesión |
| Reconectar el escritorio y verificarlo a mano | 1 sesión |
| Front-end jsPsych (chat, escalas, timeline) | 2–3 sesiones |
| Servidor (proxy, datos, estáticos) | 1 sesión |
| Despliegue | ½ sesión |

Total: **5 a 7 sesiones de trabajo enfocado**.

## 15. Documentación a actualizar

Todas las rutas cambian, así que entran en el alcance `README.md`, `CLAUDE.md` y
`AGENTS.md` (comandos de corrida, arquitectura, ubicación de los tests), más el
`git mv` de `Pre-entrega #3 — Diseño experimental.md` a `docs/`. `CLAUDE.md`
suma además qué invariantes rompe la versión web, y `protocolo/README.md` explica
que ese directorio es la fuente de verdad y que ambas implementaciones lo leen.
