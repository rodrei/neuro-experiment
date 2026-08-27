# Estado del trabajo — 25 de agosto de 2026

Dónde quedó todo, para retomar mañana.

---

## 1. Qué se hizo hoy

**Documento revisado (Google Docs).** Se leyeron los 18 comentarios del
`.docx` de la pre-entrega #2 (13 de Axel, 3 de Elena, 1 de Valentina) y se
produjo la versión revisada:

> **Pre-entrega #3 — Diseño experimental (revisado según comentarios de Axel)**
> https://docs.google.com/document/d/1rIoid0uvicQbELm_2pHsfYicIapo1idGbhWlVg44rS0/edit

Incluye un anexo en tabla con cada comentario y qué se hizo con él.

**Experimento en PsychoPy.** Se programó el Estudio 1 completo. Está en esta
carpeta (`psychopy_estudio1_v2`). Ver `README.md`.

---

## 2. Qué falta decidir (bloquea avanzar)

1. **Introducción duplicada** en el documento. Los párrafos 1–3 y 4–6
   desarrollan los mismos tres argumentos con distinta redacción; parecen dos
   borradores pegados. **No se tocó el texto** porque excede los comentarios de
   Axel. Decidir si se fusionan (quedaría una intro de ~4 párrafos).
2. **Afiliación de Valentina** (su propia consulta en el doc), y faltan las de
   Rodrigo y Juan.
3. **Nombre de la institución** del comité de ética: quedó como
   `[institución — completar]` en el documento y en el experimento.
4. **Qué equipo de EDA** van a usar (Empatica E4 / Shimmer3 / otro). De eso
   depende el `BACKEND_MARCADORES` en `config.py`. **No bloquea programar**:
   el default (`"csv"`) funciona con cualquiera.

---

## 3. Qué falta hacer en el experimento

Por orden de prioridad:

1. **Probar el recorrido interactivo completo.** Es lo único importante que no
   se pudo verificar: escribir en las cajas de texto, enviar con Enter, mover
   los sliders con el mouse. Todo lo demás está auditado automáticamente
   (ver "Qué está verificado" en el README). Correr en modo demo con alguien
   del equipo, de punta a punta.
2. **Cotejar los 20 ítems del PANAS** con Moriondo et al. (2012). Se
   escribieron de memoria. Términos discutibles: "upset" → *alterado/a*,
   "jittery" → *inquieto/a*, "distressed" → *angustiado/a*.
3. **Pretest de los guiones** de validación y rechazo (`stim/guiones.csv`):
   panel de jueces + muestra independiente n ≈ 30, como pide el protocolo.
4. **SAM pictórico** (opcional): poner los PNG en `stim/sam/`.
5. **Calibrar la intensidad del rechazo** con el comité de ética.
6. `MODO_DEMO = False` antes del primer participante real.

---

## 4. Decisiones ya tomadas (no volver a discutirlas)

- **PsychoPy Coder, no Builder.** Builder no tiene componente de chat.
- **Agente totalmente guionado**, sin operador Wizard-of-Oz en vivo. Es la
  única forma de garantizar contenido y latencia idénticos entre condiciones.
- **Latencia determinista** (función del largo del mensaje), no aleatoria.
- **La situación personal se cuenta dentro del chat**, no en pantallas previas.
- **EDA como medida primaria; EEG secundario y reducido a un solo índice (FAA).**
  Esto responde al comentario de Axel sin descartar el EEG del todo.
- **Orden de medidas: SUDS → SAM → autenticidad → PANAS**, porque SUDS y SAM
  son las sensibles al tiempo.
- **`style="rating"` en los sliders, nunca `"radio"`** (ver README: con radio,
  PsychoPy guarda `''` en vez del número, sin avisar).

---

## 5. Problema de entorno pendiente

Claude Code perdió el permiso de macOS para **leer** la carpeta de Google
Drive. Puede crear archivos nuevos, pero no leer, listar, sobrescribir ni
borrar los preexistentes. Por eso esta carpeta se llama `_v2` en vez de
reemplazar a la original.

Para arreglarlo: System Settings → Privacy & Security → **Full Disk Access**,
verificar que esté la app correcta (Terminal / iTerm / Claude, según desde
dónde se corre) y **reiniciar esa app** — los cambios de TCC no aplican hasta
reiniciarla.

---

## 6. La carpeta vieja `psychopy_estudio1`

Quedó desactualizada: le falta el PANAS, tiene el bug de la línea base y pide
las situaciones en pantallas previas. **Se puede borrar**, pero antes revisar
`psychopy_estudio1/datos/` por si quedaron corridas de prueba que quieran
conservar. Todo lo demás está en esta carpeta.

---

## 7. Copia de respaldo

Hay una copia idéntica en `~/Desktop/psychopy_estudio1_CORREGIDO/`, fuera de
Drive. Se puede borrar una vez confirmado que esta carpeta funciona.
