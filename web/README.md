# web/ — demo en navegador

Versión del Estudio 1 que corre en el navegador, para **mostrarle el estudio al
grupo y para iterar guiones y prompts**. No reemplaza al experimento de
escritorio ni sirve para correr participantes: no hay EDA, y en modo LLM
tampoco hay control de contenido entre condiciones.

Lee el mismo `protocolo/` que `escritorio/`, a través de `comun/protocolo.py`.
Una corrección de redacción en `protocolo/` llega a las dos sin copiar nada.

## Correr local

```bash
python3 -m web.servidor.app
```

Queda en <http://localhost:8080>. Variables de entorno:

| Variable | Default | Qué hace |
| --- | --- | --- |
| `PUERTO` | `8080` | Puerto de escucha |
| `CARPETA_DATOS` | `datos/` | Dónde se escriben los CSV |
| `CODIGO_ACCESO` | vacío | Si está, `/api/turno` y `/api/datos` lo exigen |
| `OPENROUTER_API_KEY` | — | Sin ella, el modo LLM cae al guion |
| `LIMITE_POR_MINUTO` | `30` | Pedidos por IP por minuto |

Tests: `python3 -m unittest discover -s web -t . -v`

## Qué hay adentro

| Archivo | Qué hace |
| --- | --- |
| `servidor/app.py` | Sirve la página, expone `/api/protocolo`, hace de proxy al LLM y recibe los datos. Sólo stdlib |
| `index.html` | Formulario de arranque y contenedor de jsPsych |
| `js/protocolo.js` | Carga `/api/protocolo` |
| `js/chat-plugin.js` | Plugin propio: un episodio completo de chat en un trial |
| `js/escalas.js` | SUDS, SAM, autenticidad y PANAS |
| `js/experimento.js` | El timeline y el envío de datos |
| `static/vendor/` | jsPsych 8.3.0 y plugins, pineados (no CDN) |

El modo de agente (guionado / LLM) se elige **en el formulario de arranque**,
para poder alternarlo en vivo delante del grupo.

## Desplegar en fly.io

La app es `neuro-estudio1-demo`, en la organización `personal`, región `gru`
(São Paulo; fly no tiene región en Argentina).

```bash
fly deploy --app neuro-estudio1-demo
```

`Dockerfile` y `fly.toml` están en la **raíz del repo**, no acá: el contenedor
necesita `protocolo/` y `comun/` además de `web/`.

### Cuatro cosas que empiezan a facturar en silencio

La cuenta está en el plan **Hobby legacy**, que conserva la asignación gratuita
anterior: 3 VMs `shared-cpu-1x` de 256 MB, 3 GB de volumen y 100 GB de tráfico.
Esta app usa 1 máquina y 1 GB, así que entra con margen. Lo que hay que cuidar:

1. **La memoria.** `fly.toml` fija `memory = "256mb"`. Cualquier cosa más
   grande sale de la asignación.
2. **La IPv4.** Tiene que ser **compartida** (`fly ips allocate-v4 --shared`).
   Una dedicada cuesta USD 2/mes. Verificar con `fly ips list`.
3. **El volumen.** Se cobra por capacidad provisionada, no por uso: 1 GB
   alcanza para unas 65.000 sesiones a 16 KB cada una.
4. **El plan.** Salir del plan legacy es **irreversible**. Rechazar cualquier
   propuesta del panel de pasar a pago por uso.

### Bajar los datos

El volumen está atado a una máquina: **no es almacenamiento durable**. Después
de cada demo, bajar los CSV:

```bash
fly ssh console --app neuro-estudio1-demo -C "ls /datos"
fly sftp get /datos/<archivo>.csv --app neuro-estudio1-demo
```

### Cambiar el código de acceso

```bash
fly secrets set CODIGO_ACCESO=<nuevo> --app neuro-estudio1-demo
```

Es una URL pública que gasta crédito de OpenRouter: conviene que tenga código y
rotarlo después de cada demo.

## Qué NO hace

Por ser una demo descartable: no hay base de datos, ni cuentas, ni chequeos de
atención, ni SAM pictórico, ni soporte para teléfonos (un cartel manda a usar
una computadora), ni equivalente de LSL o puerto serie, ni `MODO_TEST`. Corre
siempre con los parámetros `demo` de `protocolo/parametros.json`.
