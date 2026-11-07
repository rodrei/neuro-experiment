# La simulación de datos del Estudio 1

Esta carpeta produce los **datos simulados** sobre los que se escribieron los
Resultados del paper. No hay participantes reales: los números salen de un programa
que imita cómo se verían los datos si el estudio se hubiera hecho y los efectos
fueran del tamaño que sugiere la literatura. Este documento explica qué hace ese
programa, cómo correrlo y qué supuestos tiene, sin dar por sabido Python ni
estadística.

> **Lo más importante.** Los datos simulados **no son evidencia** a favor ni en
> contra de las hipótesis. Sirven para dos cosas: mostrar que el análisis completo
> funciona de punta a punta, y calcular cuántos participantes harían falta para
> detectar los efectos si existieran (Anexo A3.4 del paper).

## Índice

1. [La idea en una página](#1-la-idea-en-una-página)
2. [Cómo correrlo](#2-cómo-correrlo)
3. [Qué archivos hay](#3-qué-archivos-hay)
4. [Qué produce: las cuatro tablas](#4-qué-produce-las-cuatro-tablas)
5. [Cómo se generan los datos, paso a paso](#5-cómo-se-generan-los-datos-paso-a-paso)
6. [La conductancia por épocas y la hipótesis H1b](#6-la-conductancia-por-épocas-y-la-hipótesis-h1b)
7. [La potencia: cuántos participantes hacen falta](#7-la-potencia-cuántos-participantes-hacen-falta)
8. [La semilla: por qué los resultados no cambian](#8-la-semilla-por-qué-los-resultados-no-cambian)
9. [Supuestos sin fuente directa](#9-supuestos-sin-fuente-directa)
10. [Cómo cambiar un parámetro sin romper nada](#10-cómo-cambiar-un-parámetro-sin-romper-nada)
11. [Glosario](#11-glosario)

---

## 1. La idea en una página

El estudio tiene un diseño **2 × 2 intra-sujeto**: cada participante pasa por las
cuatro combinaciones de **agente** (persona o IA) y **retroalimentación** (validación
o rechazo), en cuatro episodios de tres rondas de chat cada uno. En cada episodio
cuenta una situación personal de un dominio distinto (trabajo o estudio, amistad,
familia o pareja, uno mismo).

El programa fabrica, para 200 participantes, todo lo que el estudio mediría:

- **Fisiología por ronda:** conductancia de la piel (SCL, SCR) y variabilidad
  cardíaca (RR, RMSSD, SDRR, pNN50, HF, LF/HF).
- **Conductancia por época de 10 segundos**, que es lo que analiza H1b.
- **Autoinforme por episodio:** SUDS antes y después, y SAM (valencia y activación)
  al final.
- **Medidas de cada episodio:** autenticidad percibida, los seis ítems del chequeo de
  manipulación, naturalidad, credibilidad (0 a 100), la codificación de las
  transcripciones, el largo de los mensajes del agente y la espera acumulada.
- **Datos de cada participante:** edad, género, UCLA, ECR, y si expresó sospecha.

Cada número sale de una regla simple: **un valor de base + un efecto según la
condición + la forma de ser de esa persona + ruido.** El valor de base y el tamaño
del efecto vienen de la literatura (tabla A3.5 del paper); la forma de ser de cada
persona hace que sus cuatro episodios se parezcan entre sí, como pasa con gente
real; el ruido es la variación que no se explica por nada de lo anterior.

Además, el programa **ensucia** los datos a propósito: agrega artefactos de
movimiento, latidos ectópicos, valores perdidos y algunos participantes que no
registran bien la etiqueta del agente. Si los datos salieran perfectos, los pasos de
limpieza del análisis no tendrían nada que hacer y las exclusiones que reporta el
paper no tendrían de dónde salir.

El análisis estadístico **no está acá**: está en el notebook del grupo
(`entrega final/simulacion/AI_companions_analisis.ipynb`, en el Drive), que baja
`01_simular.py` de GitHub, genera los datos con él y corre todos los contrastes.

---

## 2. Cómo correrlo

Hace falta Python 3 (en una Mac ya viene instalado; se prueba con `python3 --version`
en la Terminal) y cuatro librerías: **numpy** (cálculo numérico), **pandas**
(tablas), **scipy** (estadística) y **openpyxl** (escribir Excel).

Desde la Terminal, parado en esta carpeta (`simulation/`):

```bash
# 1. Una sola vez: crear un entorno propio e instalar las librerías.
#    "venv" es una carpeta con un Python aparte, para no tocar el del sistema.
python3 -m venv venv
venv/bin/pip install numpy pandas scipy openpyxl

# 2. Generar los datos. Tarda unos segundos y escribe en datos/.
venv/bin/python 01_simular.py

# 3. Verificar que los datos cumplen lo que dice el paper. Tarda un minuto y medio;
#    al final tiene que decir "OK".
venv/bin/python -m unittest test_simular

# 4. Opcional: un informe descriptivo de los datos generados.
venv/bin/python auditoria.py datos

# 5. Opcional: recalcular la calibración de H1b (segundos) y la tabla de potencia
#    (unos diez minutos). Las salidas ya están guardadas en los .txt.
venv/bin/python 00_calibrar_pendiente.py > salida_calibracion.txt
venv/bin/python 00_potencia.py > salida_potencia.txt
```

Lo que imprime el paso 2 es un resumen de los contrastes en este conjunto de datos:

```
semilla 20261103
participantes 200 | episodios 800 | rondas 2400 | epocas 14400
...
H1b, humano - IA bajo rechazo (d de Cohen pareado y p)
  pendiente del SCL   d=0.141   p=0.0491
  nivel medio del SCL d=0.078   p=0.2739   (nulo declarado)
```

Si se corre dos veces da exactamente lo mismo (ver la [sección 8](#8-la-semilla-por-qué-los-resultados-no-cambian)).
Las cifras del paper son las del notebook, que aplica la limpieza completa; este
resumen es una verificación rápida.

---

## 3. Qué archivos hay

| Archivo | Qué es |
|---|---|
| `01_simular.py` | **El generador.** Arriba de todo están los parámetros, cada uno con un comentario que dice de dónde sale. Cada parámetro corresponde a una fila de la tabla A3.5 del paper. |
| `00_calibrar_pendiente.py` | Calcula la pendiente de habituación de la conductancia que reproduce el tamaño de efecto de Kelly et al. (2012). Ver la [sección 6](#6-la-conductancia-por-épocas-y-la-hipótesis-h1b). |
| `salida_calibracion.txt` | Lo que imprimió la última calibración. |
| `00_potencia.py` | Genera muchos conjuntos de datos para cada tamaño de muestra y cuenta en cuántos sale cada contraste significativo. Es la tabla del Anexo A4. |
| `salida_potencia.txt` | Lo que imprimió la última corrida de potencia. |
| `test_simular.py` | Las pruebas automáticas: unas cincuenta afirmaciones del paper que los datos tienen que cumplir (por ejemplo, «la conductancia no tiene efecto de nivel», «el orden de las condiciones es el mismo que usa la web»). |
| `auditoria.py` | Lee los CSV generados e imprime distribuciones, correlaciones, efectos por condición y cuánta suciedad hay. No depende del generador: sirve para revisar cualquier versión de los datos. |
| `datos/` | Los datos generados (siguiente sección). |
| `README.md` | Lo mismo que este documento, en corto y en inglés, para quien programa. |

---

## 4. Qué produce: las cuatro tablas

Todo queda en `datos/`, en cuatro CSV (se abren con Excel o Google Sheets) y en un
único `datos_crudos.xlsx` con una hoja por tabla más una hoja `parametros` con todos
los valores usados.

Las tablas están **anidadas**: cada participante tiene 4 episodios, cada episodio 3
rondas y 18 épocas. Se cruzan por `id` (participante) y `episodio` (1 a 4, en el
orden en que los vivió).

**`datos_crudos_participantes.csv`** — una fila por persona (200).
`edad`, `genero`, `secuencia` y `secuencia_dominios` (las filas de los cuadrados
latinos que le tocaron, de 0 a 3), `sospecha` (si dudó del interlocutor en la
pregunta abierta), `ucla`, `ecr_ansiedad`, `ecr_evitacion`.

**`datos_crudos_episodios.csv`** — una fila por episodio (800).
`agente` y `feedback` (la condición), `dominio`, `pre_malestar` (0 a 10, elicitado
al inicio) y `alerta_malestar` (9 o más), el autoinforme (`suds_pre`, `suds_post`,
`suds_cambio`, `sam_valencia`, `sam_activacion`), `autenticidad`, los seis ítems de
manipulación (`mc_entendio`, `mc_tenia_sentido`, `mc_problema_era_yo`,
`mc_atribuyo_culpa`, `mc_interes`, `mc_queria_cortar`), la codificación de la
transcripción (`cod_validacion`, `cod_invalidacion`, `cod_atribucion`,
`cod_retirada`), `naturalidad`, `credibilidad`, `largo_medio_agente`,
`turnos_hasta_cierre`, `espera_acumulada_s`, `turnos_respaldo`, y las marcas
`falla_etiqueta` y `fuera_protocolo`.

**`datos_crudos_rondas.csv`** — una fila por ronda (2.400).
La fisiología promediada en la ronda: `scl_media`, `ns_scr_n`, `scr_amp_media`,
`rr_medio`, `rmssd`, `sdrr`, `pnn50`, `hf`, `lf_hf`. Más `artefacto_eda` (la
conductancia de esa ronda tiene un artefacto de movimiento) y `prop_ectopicos` (qué
proporción de latidos hubo que corregir).

**`datos_crudos_epocas.csv`** — una fila por época de 10 segundos (14.400).
`ronda` (a qué tercio de la ventana pertenece), `epoca` (1 a 18), `scl` (la
conductancia en esa época, en microsiemens), `scl_basal` (la línea base en reposo de
ese episodio) y `artefacto_eda`.

> El notebook de análisis lee estas columnas **por nombre**. Si se renombra alguna,
> el análisis se rompe.

---

## 5. Cómo se generan los datos, paso a paso

El generador hace siempre lo mismo, en este orden.

### 5.1 Los participantes y el orden de los episodios

Se crean 200 personas, 108 mujeres y 92 varones, con edad media de 25 años.

A cada una le toca un **orden de las cuatro condiciones** y una **asignación de
dominios a condiciones**, cada uno de un cuadrado latino de 4 × 4 (una tabla de
cuatro filas donde cada condición aparece una vez en cada posición):

- El orden de las condiciones usa un **cuadrado de Williams**: además de que cada
  condición aparezca una vez en cada posición, cada condición viene inmediatamente
  después de cada otra exactamente una vez. Así, si un episodio deja un «arrastre» al
  siguiente, ese arrastre queda repartido por igual entre las condiciones.
- Los dominios usan otro cuadrado, independiente del primero, para que el contenido
  de lo relatado no quede pegado a una condición.

La fila de cada cuadrado sale del número de participante, igual que la sugiere la
web: el orden cambia con cada participante y el dominio cada cuatro. **Los dos
cuadrados son los mismos que usa el experimento** (`protocol/sequences.json` y
`protocol/domain_sequences.json`), y una prueba automática lo verifica.

### 5.2 El tamaño de los efectos

Esta es la decisión central, y está explicada en el Anexo A3.2. La literatura da
cuánto cambia cada medida bajo **estrés de laboratorio comparado con reposo** (por
ejemplo, el intervalo RR baja 142 ms). Pero en este estudio no hay reposo: incluso
la validación es activante, porque la persona cuenta algo que la hizo sentir mal.
Por eso los efectos son **fracciones** de ese cambio publicado:

| Condición | Fracción del cambio de estrés |
|---|---|
| Rechazo, persona | 0,60 × 1,35 = **0,81** |
| Rechazo, IA | 0,60 × 0,65 = **0,39** |
| Validación, persona | 0,25 × 1,15 = **0,29** |
| Validación, IA | 0,25 × 0,85 = **0,21** |

El 0,60 y el 0,25 son el rechazo y la validación. El agente agrega o quita la mitad
de 0,70 en el rechazo y la mitad de 0,30 en la validación. Dicho en palabras: **el
rechazo de una IA produce aproximadamente la mitad (48 %) de la respuesta que el
mismo rechazo de una persona**, y en la validación la diferencia entre agentes es
mucho menor. Esa asimetría es exactamente lo que predice H1d. El 0,70 no tiene una
fuente empírica (nadie midió esto antes); es un criterio sustantivo del grupo.

El efecto **crece a lo largo del episodio**: en la ronda 1 vale un tercio, en la 2
dos tercios y en la 3 completo. Así se acumula en el estudio de Shenk y Fruzzetti
(2011). Consecuencia: el efecto promedio de las tres rondas es dos tercios del valor
de la tabla.

### 5.3 Cada persona es distinta, pero se parece a sí misma

Si una persona tiene el corazón más lento que el promedio, lo tiene en los cuatro
episodios. El generador lo imita dándole a cada participante su propio nivel en cada
medida. El reparto es mitad y mitad: **la mitad de la variación total viene de
diferencias entre personas y la otra mitad de variación dentro de cada persona**
(correlación intra-sujeto de 0,50, Anexo A3.3).

Otros dos vínculos:

- El autoinforme y la fisiología de una persona se relacionan **poco** (correlación
  alrededor de 0,15), como se ve siempre en la literatura: lo que alguien dice sentir
  y lo que marca su cuerpo van bastante por separado.
- El malestar que la persona le asignó a la situación al principio (0 a 10) predice
  un poco su autoinforme en ese episodio (correlación 0,30). Por eso funciona como
  covariable en el análisis.

### 5.4 Las distribuciones

Cada medida tiene la forma que tiene en la realidad, no una campana simétrica:

- Las que no pueden ser negativas (conductancia, amplitud de SCR, índices de
  variabilidad cardíaca) son **log-normales**: muchos valores moderados y unos pocos
  muy altos. Sus efectos son proporcionales al nivel de cada persona.
- La cantidad de respuestas de conductancia por minuto es un **conteo** (Poisson).
- Solo el autoinforme y el intervalo RR son normales.

### 5.5 El autoinforme

El SUDS se mide antes y después de cada episodio; el SAM, al final. Dentro del
episodio el generador lleva un «estado» por ronda, pero lo que se guarda es solo lo
que el protocolo mide: el estado al final de la última ronda. El SUDS de antes no
sabe qué condición viene.

### 5.6 Las medidas de cada episodio

- **Autenticidad percibida:** más alta con una persona, sobre todo en la validación
  (H1c).
- **Chequeos de manipulación:** los seis ítems separan bien el rechazo de la
  validación.
- **Codificación de las transcripciones:** las cuatro dimensiones (1 a 7) difieren
  mucho entre validación y rechazo y **no** difieren entre agentes. Ese es el
  supuesto que el análisis de invariancia de la dosis pone a prueba.
- **Naturalidad y credibilidad:** la naturalidad no difiere entre agentes; la
  credibilidad sigue la etiqueta, salvo en quienes sospechan.
- **Largo de los mensajes:** 196 caracteres en validación y 137 en rechazo (medido en
  180 respuestas del prompt actual). Una persona varía más que el modelo.
- **Espera:** en la IA sale de la regla del indicador de escritura (1,2 s + 0,045 s
  por carácter); en la persona, del tiempo de leer (5 s) y tipear (4 caracteres por
  segundo). Resultado: unos 26 s por episodio con la IA y unos 140 s con una persona.
- **Turnos de respaldo:** solo en la IA (uno de cada cien turnos), porque una persona
  no tiene líneas de respaldo.

### 5.7 La suciedad

Después de generar todo, se agrega a propósito:

| Imperfección | Cuánta |
|---|---|
| Valores perdidos en cada medida | 4 % |
| Rondas con artefacto de movimiento en la conductancia (el valor se multiplica entre 2,5 y 6) | 5 % |
| Rondas con más de 6 % de latidos corregidos (la variabilidad cardíaca queda inflada) | 6 % |
| Participantes que no registran la etiqueta del agente (su convicción sale invertida) | 3 |
| Episodios en que el agente se sale del protocolo | 2 |

Las épocas reciben la suciedad de su ronda: si la conductancia de la ronda tiene un
artefacto, sus seis épocas también; si se perdió, se pierden.

---

## 6. La conductancia por épocas y la hipótesis H1b

H1b dice que el rechazo de una persona produce **menos habituación** de la
conductancia que el de una IA: a lo largo del episodio la conductancia baja, y baja
menos cuando rechaza una persona. Y que **no hay diferencia de nivel medio** entre
agentes. Es la parte más técnica de la simulación, así que va con detalle.

### Qué se genera

Para cada episodio, una **ventana fija de 3 minutos** contada desde el primer mensaje
del agente, partida en **18 épocas de 10 segundos**, como hacen Kelly et al. (2012)
con 16. La ventana es fija, y no la duración real del episodio, a propósito: los
episodios con una persona duran bastante más, y una ventana de largo variable
metería esa diferencia de exposición dentro de la medida.

En cada época, la conductancia es:

> **nivel de reposo** de la persona en ese episodio (sube un poco de episodio en
> episodio, como observaron Kelly et al.)
> **+ elevación por la tarea** (1,5 µS)
> **+ pendiente de habituación × tiempo**
> con un **ruido** que se parece mucho de una época a la siguiente.

- La **pendiente** vale −0,145 µS por época en la validación. Bajo rechazo se
  atenúa: 74 % menos con una persona y 36 % menos con la IA. La diferencia entre esas
  dos atenuaciones es H1b. El tiempo se cuenta desde el centro de la ventana, así que
  la pendiente no mueve el promedio: no hay efecto de nivel.
- El **ruido** es «autorregresivo» (AR(1), con correlación 0,90 entre épocas
  seguidas): el nivel tónico de la piel cambia despacio, y si las épocas se generaran
  independientes la pendiente sería artificialmente fácil de estimar. Además es
  multiplicativo, así que **la conductancia nunca es negativa**.
- El **SCL de cada ronda** es el promedio de las seis épocas de su tercio de la
  ventana. Las épocas y las rondas son la misma señal, no dos sorteos distintos.

### Cómo se analiza

Igual que Kelly et al.: para cada episodio se calcula el logaritmo de la conductancia
más uno, se le resta el de la línea base del episodio, y se ajusta una recta por
mínimos cuadrados sobre las 18 épocas. La pendiente de esa recta es la habituación
del episodio. Restar la línea base cambia el nivel, no la pendiente. Las épocas con
artefacto o perdidas quedan afuera, y si un episodio se queda con menos de dos de sus
tres rondas, no tiene pendiente. La función es `pendiente_kelly()` y el notebook usa
esa misma.

H1b compara, dentro de cada participante, la pendiente del rechazo humano con la del
rechazo de la IA.

### De dónde sale el −0,145: la calibración

Kelly et al. no publican cuánto baja la conductancia en microsiemens. Publican un
estadístico, F(1,40) = 8,25, para la diferencia de pendientes entre ostracismo e
inclusión. Eso equivale a un **tamaño de efecto d_z = 0,449**: la diferencia de
pendientes es casi media desviación estándar.

`00_calibrar_pendiente.py` busca la pendiente que, analizada como la analizan ellos,
reproduce ese 0,449 en el efecto de retroalimentación (rechazo contra validación).
El resultado es **−0,145 µS por época**. La pendiente no se eligió para que H1b diera
significativo: se despejó para que el tamaño de efecto coincida con el de la fuente.

Una consecuencia importante, que conviene entender bien: **una vez fijado ese tamaño
de efecto, la potencia de H1b queda determinada por cuentas, sin importar los
detalles de la ventana.** H1b es la diferencia entre agentes dentro del rechazo, que
es el 0,70 del efecto de retroalimentación, y su contraste tiene el doble de varianza.
Entonces su tamaño de efecto es 0,449 × 0,70 / √2 ≈ **0,22**, y con 200 personas eso
da una potencia de **0,88**. Por eso cambiar la autocorrelación entre 0,80 y 0,95 no
cambia la potencia (ver `salida_calibracion.txt`): no es que el resultado sea robusto
a ese supuesto, es que la calibración lo absorbe por construcción.

Lo que de verdad sostiene a H1b son dos cosas: el **0,449 de Kelly**, estimado con
solo 41 personas (su intervalo de confianza del 95 % va de 0,12 a 0,77), y el
**0,70** del reparto entre agentes, que no tiene fuente. Las épocas importan por
otra razón: un tamaño de efecto se puede trasladar de un estudio a otro solo si la
pendiente se estima de la misma manera, y Kelly la estima sobre épocas de 10 s.

### En este conjunto de datos

La pendiente humano contra IA bajo rechazo da **p = 0,049** (d = 0,14), y el nivel
medio **p = 0,27**, como predice H1b. Que salga justo en el borde es azar (ver la
[sección 8](#8-la-semilla-por-qué-los-resultados-no-cambian)).

### Lo que requiere del experimento

Las épocas se cortan del registro continuo de la conductancia, así que el experimento
solo tiene que marcar cuándo aparece en pantalla el primer mensaje del agente. La web
ya lo hace (el marcador `agent_message_1`, que se registra cuando el mensaje llega a
la pantalla). Lo que falta en un laboratorio real es sincronizar el reloj de la web
con el del equipo que registra la conductancia.

Hay un punto abierto de método: la ventana de 3 minutos tiene que caber dentro de
los episodios con IA, que son los más cortos. Después del primer mensaje quedan dos
respuestas del participante, dos esperas de la IA (unos 9 s cada una) y 8 s con el
último mensaje en pantalla. Para que entren 3 minutos, el participante tiene que
tardar al menos unos 77 s en escribir cada respuesta. El pretest de calibración
(sección 2.3 del paper) sirve para comprobarlo.

---

## 7. La potencia: cuántos participantes hacen falta

La **potencia** de un contraste es la probabilidad de que dé significativo si el
efecto existe del tamaño supuesto. Lo convencional es pedir al menos 0,80.

Como el diseño es complicado (rondas dentro de episodios dentro de personas), no hay
una fórmula: se estima simulando. `00_potencia.py` genera **100 conjuntos de datos
para cada tamaño de muestra**, aplica los contrastes y cuenta en qué proporción dan
p < 0,05. Las tres primeras columnas promedian cinco variables (RMSSD, RR medio,
logaritmo de HF, cambio de SUDS y valencia del SAM).

| N | H1d interacción | H1a agente en rechazo | Efecto principal | H1b pendiente |
|---|---|---|---|---|
| 40 | .37 | .67 | .75 | .30 |
| 50 | .42 | .76 | .83 | .38 |
| 60 | .49 | .79 | .86 | .51 |
| 80 | .53 | .86 | .94 | .63 |
| 120 | .69 | .93 | .97 | .74 |
| 150 | .76 | .95 | .99 | .84 |
| **200** | **.83** | **.99** | **1.00** | **.88** |
| 300 | .91 | 1.00 | 1.00 | .98 |

Cómo leerla:

- **H1d decide el N.** Es la interacción, una diferencia de diferencias, y por eso el
  contraste más difícil de detectar. Pasa 0,80 recién con 200 personas.
- Con 100 conjuntos, cada valor tiene un margen de error de unos ±0,08 para H1b, que
  es un solo contraste, y algo menor para las columnas que promedian cinco variables.
  Por eso para H1b conviene mirar también la cuenta exacta de la sección 6: 0,77 con
  150 y 0,88 con 200.
- La estimación es **conservadora**: no usa covariables ni los modelos jerárquicos
  del plan de análisis, que en un análisis real ganan potencia.

---

## 8. La semilla: por qué los resultados no cambian

Una computadora no genera azar verdadero: genera números que parecen al azar a
partir de un número inicial, la **semilla**. Con la misma semilla, la secuencia es
siempre la misma, y por eso los datos salen idénticos cada vez que se corre el
programa. La semilla es **20261103** y está fija.

**No se cambia la semilla para que un resultado dé.** Si se probaran semillas hasta
que H1b saliera significativa, el resultado reportado sería elegido y no azaroso. Por
el mismo motivo, nada en la simulación se ajustó mirando si un contraste daba
significativo: los efectos salen de la literatura, la pendiente de la calibración
contra Kelly y el N de la tabla de potencia.

Un conjunto concreto puede dar no significativo aunque la potencia sea alta: con
potencia 0,88, eso pasa más o menos una vez de cada ocho. El paper reporta lo que da
este conjunto y se apoya en la potencia para interpretarlo.

Algunas partes del generador usan su propia secuencia de azar (las épocas, la espera
humana, la codificación, el autoinforme), para que cambiar algo en una de ellas no
mueva todos los demás valores.

---

## 9. Supuestos sin fuente directa

Todo lo que no viene de la literatura es un supuesto, y el paper lo declara. Los
principales:

| Supuesto | Valor | Dónde importa |
|---|---|---|
| Fracción del rechazo | 0,60 del cambio de estrés | Todos los efectos |
| Efecto del agente | 0,70 en rechazo, 0,30 en validación | H1a, H1b, H1d |
| Correlación intra-sujeto | 0,50 | Ruido de todas las medidas |
| Acople autoinforme-fisiología | 0,15 | Correlaciones entre medidas |
| Pre-rating y autoinforme | 0,30 | Covariable |
| Moderación por género | ×1,45 sobre el efecto en SCR, mujeres | Solo frecuencia y amplitud de SCR |
| Autocorrelación entre épocas | 0,90 (explorada 0,80 a 0,95) | Pendiente en µS, no la potencia |
| Elevación por la tarea | 1,5 µS | Nivel del SCL durante el episodio |
| Ventana | 18 épocas de 10 s | H1b |
| Tiempos de la persona | 5 s de lectura, 4 caracteres por segundo | Espera en la condición humana |
| Naturalidad, credibilidad, codificación | Sin diferencia entre agentes | Chequeos de la sección 2.5 |

La moderación por género tiene un alcance menor de lo que su nombre sugiere: actúa
sobre el efecto de condición, y la conductancia tónica no tiene efecto de condición
(es el nulo de H1b), así que solo alcanza a las respuestas fásicas. El género entra
en el análisis como covariable, no como moderador contrastado.

---

## 10. Cómo cambiar un parámetro sin romper nada

1. Cambiar el valor en `01_simular.py`, en la sección de parámetros de arriba.
2. **Cambiar la misma fila en la tabla A3.5 del paper.** El script y la tabla tienen
   que coincidir.
3. Si el cambio toca la conductancia por épocas (`RHO_EPOCA`, `N_EPOCAS`,
   `ELEVACION_TAREA` o el ruido), correr `00_calibrar_pendiente.py` y copiar en
   `HABITUACION_SCL_EPOCA` el valor de la fila marcada.
4. Correr las pruebas (`venv/bin/python -m unittest test_simular`). Si alguna falla,
   el cambio contradice algo que el paper afirma, y hay que decidir cuál de los dos
   corregir.
5. Si el cambio afecta los tamaños de efecto o el N, volver a correr `00_potencia.py`
   y actualizar la tabla del Anexo A4.
6. Subir el cambio a GitHub y **actualizar en el notebook el commit del que baja el
   generador**. Si no, el notebook sigue usando la versión anterior. Después, correr
   el notebook de nuevo y revisar las cifras de Resultados (están entre corchetes
   justamente para eso).

---

## 11. Glosario

- **Intra-sujeto:** cada participante pasa por todas las condiciones, y se lo compara
  consigo mismo.
- **Cuadrado latino / de Williams:** una tabla de órdenes en la que cada condición
  aparece una vez en cada posición; el de Williams además equilibra qué condición
  viene después de cuál.
- **SCL:** nivel tónico de conductancia de la piel, en microsiemens (µS). Sube con la
  activación simpática y cambia despacio.
- **SCR:** respuestas fásicas de la conductancia: subidas breves ante un estímulo. Se
  cuentan (frecuencia) y se miden (amplitud).
- **Habituación:** la respuesta baja a medida que la situación se repite o se
  prolonga.
- **Época:** un tramo fijo de la señal, acá de 10 segundos.
- **RR, RMSSD, SDRR, pNN50, HF, LF/HF:** índices cardíacos. El RR es el tiempo entre
  latidos; los demás miden cuánto varía, y bajan con el estrés (salvo LF/HF, que
  sube).
- **SUDS:** malestar subjetivo de 0 a 10. **SAM:** escala pictórica de valencia y
  activación, de 1 a 9.
- **d de Cohen pareado (d_z):** tamaño de un efecto intra-sujeto, en desviaciones
  estándar de la diferencia. 0,2 es chico, 0,5 mediano, 0,8 grande.
- **p:** probabilidad de ver una diferencia así de grande si no hubiera efecto. Por
  convención, p < 0,05 es «significativo».
- **Potencia:** probabilidad de obtener p < 0,05 si el efecto existe del tamaño
  supuesto.
- **Log-normal:** una distribución de valores positivos, con la mayoría moderados y
  una cola de valores altos.
- **AR(1):** un ruido en el que cada valor se parece al anterior; el 0,90 dice cuánto.
- **Semilla:** el número inicial del que sale todo el azar del programa.
- **Monte Carlo:** estimar algo repitiendo una simulación muchas veces.
