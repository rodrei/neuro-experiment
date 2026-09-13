# protocolo/

El contenido del Estudio 1 como datos: prosa de las pantallas, escalas,
guiones del agente, códigos de marcador y prompts del modo LLM.

**Esta carpeta es la fuente de verdad.** La lee `comun/protocolo.py`, y por
ahí la consumen las dos implementaciones: el experimento de escritorio en
PsychoPy (`escritorio/`) y la demo web (`web/`). Una corrección de redacción
acá llega a las dos sin copiar nada.

| Archivo | Qué tiene |
| --- | --- |
| `textos.json` | Consentimiento, reposo, cobertura, pausa, debriefing, cierre y chequeo final |
| `escalas.json` | SUDS, SAM (valencia y arousal), autenticidad y anclas del PANAS |
| `parametros.json` | Tiempos reales y de demo, y la fórmula de latencia del agente |
| `marcadores.json` | Los 18 códigos de evento |
| `prompts.json` | Rol por condición, reglas del agente LLM y parámetros del modelo |
| `guiones.csv` | Mensajes guionados: saludo, saludo2 y 3 turnos por condición |
| `panas.csv` | Los 20 ítems del PANAS con su subescala |
| `sam/` | PNGs opcionales del SAM pictórico (si existen, se autodetectan) |

## Al editar

- **Los guiones se re-balancean en largo.** La latencia del agente es función
  del largo del mensaje, así que validación y rechazo tienen que sumar
  parecido o la espera difiere entre condiciones. Lo verifica
  `comun/test_protocolo.py`.
- **Correr los tests después de tocar cualquier cosa acá:**
  `python3 -m unittest discover -s comun -t . -v`
