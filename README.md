# Estudio 1 en PsychoPy — Validación y rechazo: IA vs. agente humano

Neurodiplo, Grupo 3 · AI companions · pre-entrega #3

Implementación del **Estudio 1**: 2 × 2 mixto, Tipo de agente (Humano vs. IA)
entre-sujetos y Retroalimentación (Validación vs. Rechazo) intra-sujeto
contrabalanceada.

> **Esta carpeta (`psychopy_estudio1_v2`) es la versión vigente.**
> Reemplaza a `psychopy_estudio1`, que quedó desactualizada. Ver `LEEME_cambios.txt`.

---

## Cómo correrlo

Abrir **PsychoPy Coder** (no Builder — ver más abajo), abrir `estudio1.py`, Run.

Desde terminal:

```bash
cd "psychopy_estudio1_v2" && PYTHONHOME=/Applications/PsychoPy.app/Contents/Resources PYTHONPATH=/Applications/PsychoPy.app/Contents/Resources/lib/python3.11 /Applications/PsychoPy.app/Contents/MacOS/python estudio1.py
```

Salir en cualquier momento: **Ctrl + Q**.

Por defecto arranca en **modo demo** (`MODO_DEMO = True` en `config.py`):
ventana chica y tiempos cortos. Para correr participantes, ponerlo en `False`.

---

## Los archivos

| Archivo | Qué hace |
|---|---|
| `estudio1.py` | Script principal: el flujo completo |
| `chat.py` | Motor de la interfaz de chat (burbujas, "escribiendo…", turnos) |
| `escalas.py` | Instrucciones, SUDS, SAM, autenticidad, PANAS, texto libre |
| `marcadores.py` | Marcadores de evento y sincronización con el equipo fisiológico |
| `config.py` | **Todos los parámetros ajustables viven acá** |
| `stim/guiones.csv` | Banco de mensajes del agente |
| `stim/panas.csv` | Los 20 ítems del PANAS con su subescala |
| `datos/` | Salida (se crea sola) |

---

## Flujo del experimento

1. Diálogo inicial (ID, edad, sexo, condición de agente, orden, si registra EEG)
2. Consentimiento e instrucciones
3. **Línea base** 5 min con cruz de fijación → marcadores 10/11
4. Bloque de medidas de línea base: SUDS → SAM → **PANAS** *(sin ítems de autenticidad: todavía no hay interlocutor)*
5. **Historia de cobertura** — acá se manipula el factor entre-sujetos
6. **Episodio 1** → bloque de medidas completo
7. **Episodio 2** (la otra retroalimentación) → bloque de medidas completo
8. Chequeo de manipulación + funnel debriefing (3 preguntas abiertas)
9. **Debriefing completo** y reconsentimiento para usar los datos

Cada episodio: el agente saluda y **pide una situación personal** → el
participante la cuenta **dentro del chat** (mínimo 120 caracteres, con contador)
→ tres turnos del agente con respuesta libre entre medio → ventana final de
respuesta libre (puede no responder; la latencia se registra igual).

Orden dentro de cada bloque de medidas: **SUDS → SAM → autenticidad → PANAS.**
SUDS y SAM son las medidas sensibles al tiempo y van primero; el PANAS, que es
largo, va último.

---

## Cuatro decisiones de implementación (y por qué)

**1. Coder, no Builder.** El 80 % de esto es una interfaz de chat, y Builder no
tiene componente de chat. La conversación está dibujada a mano con `TextBox2`
sobre una `Window` en unidades `height`.

**2. El agente está totalmente guionado: no hace falta operador
Wizard-of-Oz en vivo.** El diseño exige contenido y latencia idénticos entre las
condiciones Humano e IA. Un operador humano no puede garantizarlo; un script sí.
Además hace el procedimiento exactamente replicable.

**3. La latencia del agente es determinista, no aleatoria.**
`latencia = 1.2 s + 0.045 s × caracteres` (tope 12 s). Mismo mensaje ⇒ misma
espera. Los guiones están **balanceados en extensión** (validación 340
caracteres, rechazo 349), así que las dos ramas quedan parejas en tiempo total
de espera: 18,9 s vs. 19,3 s.

**4. La situación personal se cuenta dentro del chat.** No se piden por
adelantado en pantallas del software. La historia de cobertura *es* la
manipulación: pedirlas antes y después "pegarlas" en el chat rompía la ilusión
justo antes de medirla.

> *Contrapartida a declarar en limitaciones:* si la segunda situación se elige
> después de haber recibido el rechazo, el rechazo puede contaminar qué decide
> contar. Como el orden de retroalimentación está contrabalanceado, ese arrastre
> queda repartido entre condiciones y no sesga el contraste principal.

---

## Sincronización con el EDA

`config.BACKEND_MARCADORES` elige cómo se marcan los eventos:

- `"csv"` (por defecto) — sólo el log con timestamps. **Sirve para Empatica E4
  y Shimmer3**, que graban en su propio reloj: se alinea offline por `t_unix`.
- `"lsl"` — además publica marcadores por Lab Streaming Layer (`pylsl` ya viene
  con PsychoPy). Recomendado si el equipo lo soporta.
- `"serial"` — byte TTL por puerto serie (configurar `PUERTO_SERIAL`).
- `"paralelo"` — **no existe en Mac**; sólo en una PC de laboratorio.

Si el backend falla al abrir, el experimento **no se cae**: avisa y sigue en CSV.

Las SCR tienen latencias de 1–4 s y se analizan en ventanas de segundos, así que
**no hace falta precisión de milisegundos** como en un ERP. El log por timestamps
alcanza. Esto es lo que más de-riesga el montaje: no dependen de tener hardware
de trigger.

Códigos: 1 inicio · 10/11 baseline · 20 episodio_inicio · **19 agente_pide_situacion** ·
**18 situacion_revelada** · 21/22/23 mensajes del agente · 30 mensaje del participante ·
35 ventana de respuesta libre · 40 episodio_fin · 50/51 bloque de medidas ·
**52/53 PANAS** · 60 chequeo de manipulación · 99 fin.

---

## Qué sale al terminar

Cuatro CSV por participante en `datos/`, prefijo `S1_<id>_<condición>_<fecha>`:

| Archivo | Contenido |
|---|---|
| `_eventos.csv` | Cada evento con `t_experimento_s` y `t_unix`. **Es el que se cruza con el EDA.** |
| `_respuestas.csv` | SUDS, SAM, autenticidad, PANAS (20 ítems + PA_total + NA_total), chequeo de manipulación, funnel debriefing |
| `_conductual.csv` | Situación contada, largo, y latencias de respuesta; si respondió o no al rechazo |
| `_chat.csv` | Transcripción completa con timestamps |

---

## Trampa de PsychoPy: no usar `style="radio"`

La grilla del PANAS usa `style="rating"`. **No cambiar a `"radio"`.**
En PsychoPy `Slider.categorical` es `True` para todo slider de estilo radio, y
en ese caso `.rating` devuelve `self.labels[...]` en vez del número:

- con `labels=None` → `TypeError` al primer clic del participante;
- con `labels=[""]*5` → guarda `''` en vez del valor, **sin avisar**.

Con `style="rating"` queda `categorical=False` y devuelve el número.

---

## Pendientes antes de correr participantes

- [ ] **Poner `MODO_DEMO = False`** en `config.py`.
- [ ] **Cotejar los 20 ítems del PANAS** con Moriondo et al. (2012). La
      traducción actual se escribió de memoria; términos discutibles:
      "upset" → *alterado/a*, "jittery" → *inquieto/a*, "distressed" → *angustiado/a*.
- [ ] **SAM pictórico.** Hoy son escalas numéricas de 9 puntos con anclas
      verbales. Para los monigotes originales: poner los PNG en `stim/sam/`
      como `val_1.png`…`val_9.png` y `aro_1.png`…`aro_9.png`; el código los
      detecta y los dibuja solo.
- [ ] **Pretest de los guiones.** Los mensajes de `stim/guiones.csv` están
      balanceados en extensión pero **no validados**. El protocolo pide panel
      de jueces + pretest independiente (n ≈ 30).
- [ ] **Intensidad del rechazo.** Los guiones son deliberadamente suaves; la
      calibración final es decisión del comité de ética.
- [ ] **Elegir el backend de marcadores** según el equipo que consigan.
- [ ] **Probar el recorrido interactivo completo** con alguien del equipo.

---

## Qué está verificado

- Los cinco módulos compilan con el Python de PsychoPy 2026.2.2.
- El chat renderiza correctamente a ~116 fps; las burbujas se miden (no se
  estiman) y se cachean, no se reconstruyen por frame.
- La latencia del agente es determinista y está balanceada entre ramas.
- Recorrido completo del flujo auditado sin interacción: 48 pantallas en el
  orden correcto, cero preguntas sobre el interlocutor antes del primer chat,
  PANAS en los 3 momentos, la situación pedida 2 veces dentro del chat.
- El log de eventos escribe la secuencia completa con timestamps monótonos y
  `t_unix` válido.
- Los sliders devuelven los valores numéricos correctos (probado poniendo y
  leyendo valores).

**No verificado:** el recorrido interactivo real — escribir en las cajas, enviar
con Enter, mover los sliders con el mouse. Requiere una persona frente a la
pantalla. Es lo primero que hay que probar.
