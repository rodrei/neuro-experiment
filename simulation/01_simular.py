"""
01_simular.py — Genera los datos crudos simulados del estudio de AI companions.

Los datos son SIMULADOS. Este script implementa la estructura de efectos descrita
en el Anexo A3 del documento. Cada constante de esta seccion de parametros se
corresponde con una fila de la tabla A3.5: si se cambia una, hay que cambiar la otra.
Que hace y como, explicado para el equipo: LEEME.md.

Produce datos deliberadamente "sucios" (artefactos, latidos ectopicos, faltantes,
fallos de chequeo de etiqueta) para que la limpieza del notebook de analisis tenga
sobre que operar y las exclusiones reportadas en la seccion 2.5 del paper tengan
sustento.

El autoinforme se mide por episodio (seccion 3 del paper): SUDS antes y despues,
SAM al final. Dentro de un episodio se genera por ronda solo como estado subyacente,
del que sale el valor final; la hoja de rondas no lo incluye porque nadie lo mide.

El SCL se genera por epoca de 10 s (seccion 4 y Anexo A4): es lo que analiza H1b.
El SCL de cada ronda es la media de las epocas de su tercio de la ventana.

Salida: datos/datos_crudos.xlsx  (hojas: participantes, episodios, rondas, epocas,
                                  parametros)
        datos/datos_crudos_*.csv

Uso:  python3 01_simular.py
"""

import numpy as np
import pandas as pd
from pathlib import Path

SEMILLA = 20261103
rng = np.random.default_rng(SEMILLA)

AQUI = Path(__file__).resolve().parent
SALIDA = AQUI / "datos"
SALIDA.mkdir(exist_ok=True)

# ---------------------------------------------------------------- parametros
# Cada entrada corresponde a una fila de la tabla A3.5 del Anexo.

N_PARTICIPANTES = 200   # determinado por simulacion de potencia, ver 00_potencia.py y A4
N_MUJERES = 108
N_EPISODIOS = 4
N_RONDAS = 3

# Supuesto central (A3.2). Fracciones del delta de estres de laboratorio.
FRAC_RECHAZO = 0.60
FRAC_VALIDACION = 0.25
# Efecto de agente como fraccion del efecto de retroalimentacion. Asimetrico (H1d).
AGENTE_EN_RECHAZO = 0.70      # calibrado: f realizado medio = 0.25 (ver A3.2)
AGENTE_EN_VALIDACION = 0.30   # mantiene la asimetria de H1d

# Correlacion intra-sujeto entre medidas repetidas (A3.3); fija el reparto de
# varianza entre el intercepto del participante y el residuo.
R_INTRA = 0.50

# Desacople autorreporte-fisiologia (A3.3): correlacion entre los interceptos de
# cada participante, con el signo de cada medida bajo estres.
R_AUTOINFORME_FISIO = 0.15

# Correlacion entre el pre-rating de la situacion y el autoinforme del episodio.
# Es la covariable del plan de analisis (A4). Supuesto, sin fuente directa.
R_PRE_AUTOINFORME = 0.30

# Moderacion por genero en la respuesta electrodermica (Iffland et al., 2014).
# Multiplicador del efecto de condicion sobre EDA en mujeres.
MOD_GENERO_EDA = 1.45

# Deriva de la linea base entre episodios (Kelly et al., 2012): el SCL basal
# asciende de un episodio al siguiente.
DERIVA_SCL_POR_EPISODIO = 0.45     # microsiemens

# Variables: (basal_media, basal_de, delta_estres, distribucion)
# "delta_estres" es el cambio estres-vs-reposo publicado; los efectos de condicion
# son fracciones de este valor.
VARIABLES = {
    # --- electrodermicas (Dawson, Schell y Filion, Tabla 7.1)
    "scl_media":      dict(base=6.00, de=2.50, delta=0.00,  dist="lognormal"),   # en reposo; sale de las epocas
    "ns_scr_n":       dict(base=2.00, de=0.90, delta=0.60,  dist="poisson"),   # la varianza la fija lambda y R_INTRA
    "scr_amp_media":  dict(base=0.35, de=0.18, delta=0.15,  dist="lognormal"),
    # --- cardiacas (Castaldo et al., 2015, diferencias de medias agrupadas)
    "rr_medio":       dict(base=926.0, de=90.0,  delta=-142.0, dist="normal"),      # basal: Nunan 2010
    "rmssd":          dict(base=42.0,  de=15.0,  delta=-12.0,  dist="asimetrica"),  # basal: Nunan 2010
    "sdrr":           dict(base=50.0,  de=16.0,  delta=-7.6,   dist="asimetrica"),  # basal: Nunan 2010 (SDNN)
    "pnn50":          dict(base=32.0,  de=19.0,  delta=-8.0,   dist="asimetrica"),  # Nunan no reporta pNN50; basal de Castaldo
    "hf":             dict(base=657.0, de=777.0, delta=-360.0, dist="asimetrica"),  # basal: Nunan 2010
    "lf_hf":          dict(base=2.80,  de=2.60,  delta=0.61,   dist="asimetrica"),  # basal: Nunan 2010
    # --- autoinforme (Shenk y Fruzzetti, 2011)
    "sam_valencia":   dict(base=6.00,  de=1.50,  delta=-1.16,  dist="normal"),   # ES 0.77 x 1.50; base y DE: supuesto
    "suds":           dict(base=2.50,  de=1.50,  delta=1.16,   dist="normal"),   # ES 0.77 x 1.50
}
AUTOINFORME = ("sam_valencia", "suds")     # estado subyacente por ronda, ver arriba
RANGO = dict(sam_valencia=(1, 9), suds=(0, 10))
# La activacion del SAM se mide solo al final del episodio. Mismo ES; base y DE: supuesto.
SAM_ACTIVACION = dict(base=4.00, de=1.60, delta=1.23)

# El SCL no tiene efecto de nivel (Iffland) pero si de pendiente (Kelly): habitua a
# lo largo del episodio, menos bajo rechazo, y menos aun con un agente humano (H1b).
# Se genera por epoca de 10 s dentro de una ventana fija, igual para los dos agentes,
# contada desde el primer mensaje del agente. Kelly et al. (2012) usan 16 epocas.
N_EPOCAS = 18                      # 3 minutos; 6 epocas por ronda
RHO_EPOCA = 0.90                   # autocorrelacion del SCL tonico entre epocas seguidas. Supuesto
ELEVACION_TAREA = 1.50             # uS sobre el reposo durante el episodio. Supuesto
ATENUACION_RECHAZO = 0.55          # el rechazo habitua un 55% menos, en promedio de agentes
# Kelly et al.: interaccion tiempo x condicion F(1,40) = 8,25 -> eta2p = .171 -> d_z = .449.
# Es el efecto de RETROALIMENTACION sobre la pendiente (ostracismo contra inclusion).
KELLY_DZ = 0.449
# Pendiente en validacion, uS por epoca. No se elige: es la que reproduce KELLY_DZ
# en el efecto de retroalimentacion, analizado como Kelly. La despeja
# 00_calibrar_pendiente.py; si cambia RHO_EPOCA, el ruido o la ventana, hay que
# volver a correrlo y copiar aca el valor.
HABITUACION_SCL_EPOCA = -0.1449

# Contaminacion deliberada (A3.1)
PROP_FALTANTES = 0.04
PROP_ARTEFACTO_EDA = 0.05
PROP_ECTOPICOS = 0.06              # umbral de latidos ectopicos y proporcion de rondas que lo superan
BETA_ECTOPICOS = (1.3, 54)         # Beta tal que P(prop_ectopicos > PROP_ECTOPICOS) = 0.06
N_FALLA_ETIQUETA = 3               # participantes con la conviccion invertida
PROB_FALLA_POR_EPISODIO = 0.6
N_FUERA_PROTOCOLO = 2              # episodios en que el agente se sale del guion

# Credibilidad de la identidad declarada (seccion 2.5). Supuestos, sin fuente directa.
PROP_SOSPECHA = 11 / 41            # Kelly et al. (2012): 11 de 41 con dudas
CREDIBILIDAD_HUMANO = (78, 14)     # conviccion 0-100, media y DE, etiqueta humana
CREDIBILIDAD_HUMANO_SOSPECHA = (55, 18)
CREDIBILIDAD_IA = (12, 10)
NATURALIDAD = dict(validacion=5.0, rechazo=4.0)   # 1-7; sin diferencia entre agentes

# Medidas conductuales de la retirada (seccion 2.5). Medias de conversaciones
# piloto con el prompt del Anexo A2: el rechazo escribe algo menos. En la condicion
# humana responde una persona del equipo con el mismo protocolo: supuesto, misma
# media que el modelo y mas variabilidad.
LARGO_AGENTE = dict(validacion=196, rechazo=137)
LARGO_AGENTE_DE = 25
LARGO_HUMANO_DE = 40
# Espera de la condicion humana: leer y tipear cada respuesta. Supuestos, sin fuente
# directa. La de la IA sale de la latencia determinista del protocolo.
TIEMPO_LECTURA_S = 5
TIPEO_CARACTERES_S = 4
VARIACION_ESPERA_HUMANO = 0.15     # DE del logaritmo, por episodio
PROB_TURNO_RESPALDO = 0.01         # solo IA: una persona no tiene lineas de respaldo
UMBRAL_ALERTA_MALESTAR = 9

# Items de la atribucion disposicional (Pendientes). Supuesto: entre la validacion y
# la retirada, porque el protocolo pide dos de cinco componentes por mensaje y este
# no aparece en todos.
ATRIBUCION = dict(validacion=1.9, rechazo=4.8)
# Codificacion de las transcripciones en la escala 1-7 del VIBCS (seccion 2.5), media
# de las tres pasadas del codificador automatico. Supuesto: la dosis no difiere entre
# agentes, y una persona varia mas que el modelo.
CODIFICACION = dict(
    cod_validacion=dict(validacion=5.6, rechazo=1.7),
    cod_invalidacion=dict(validacion=1.6, rechazo=5.4),
    cod_atribucion=dict(validacion=1.3, rechazo=3.8),
    cod_retirada=dict(validacion=1.6, rechazo=5.2),
)
CODIFICACION_DE = dict(humano=0.9, ia=0.7)

DOMINIOS = ["trabajo_estudio", "amistad", "familia_pareja", "uno_mismo"]
CONDICIONES = [("humano", "validacion"), ("humano", "rechazo"),
               ("ia", "validacion"), ("ia", "rechazo")]

# Los dos cuadrados de la web (protocol/sequences.json y domain_sequences.json); un
# test verifica que coincidan. Indices sobre CONDICIONES y DOMINIOS.
# Orden de las condiciones, una fila por secuencia: cuadrado de Williams. Cada
# condicion aparece una vez en cada posicion y precede a cada otra una sola vez,
# lo que equilibra el arrastre de un episodio al siguiente.
CUADRADO_CONDICIONES = [[0, 1, 3, 2], [1, 2, 0, 3], [2, 3, 1, 0], [3, 0, 2, 1]]
# Dominio de cada condicion, una fila por secuencia de dominios: cuadrado latino
# ciclico, independiente del anterior.
CUADRADO_DOMINIOS = [[(i + j) % 4 for j in range(4)] for i in range(4)]


# ---------------------------------------------------------------- utilidades


def reparto_varianza(de_total, r=None):
    """Separa el desvio total en componente entre-sujetos y residual
    de modo que la correlacion intra-sujeto sea r. Lee R_INTRA en tiempo de
    llamada, no como argumento por defecto, para poder recalibrar."""
    r = R_INTRA if r is None else r
    var = de_total ** 2
    return np.sqrt(var * r), np.sqrt(var * (1 - r))


def efecto_condicion(delta, agente, feedback):
    """Efecto de condicion en unidades de la variable, segun A3.2."""
    frac = FRAC_RECHAZO if feedback == "rechazo" else FRAC_VALIDACION
    agente_frac = AGENTE_EN_RECHAZO if feedback == "rechazo" else AGENTE_EN_VALIDACION
    signo = +1 if agente == "humano" else -1
    return delta * frac * (1 + signo * agente_frac / 2)


def atenuacion_habituacion(agente, feedback):
    """Cuanto se atenua la habituacion del SCL: nada en validacion y, bajo
    rechazo, con el mismo reparto entre agentes que el resto de los efectos."""
    if feedback != "rechazo":
        return 0.0
    signo = +1 if agente == "humano" else -1
    return ATENUACION_RECHAZO * (1 + signo * AGENTE_EN_RECHAZO / 2)


def factor_persona(z, cv):
    """Multiplicador log-normal de media 1 y coeficiente de variacion cv, para las
    medidas que no pueden ser negativas. Un intercepto aditivo con estas DE
    dejaria medias negativas en una parte de los participantes."""
    s2 = np.log1p(cv ** 2)
    return np.exp(np.sqrt(s2) * z - s2 / 2)


def cv_residual(de, base):
    """Coeficiente de variacion del residuo de una medida positiva. Como el residuo
    escala con el nivel de cada persona, este reparto es el que da a la vez la DE
    de la tabla y la correlacion intra-sujeto R_INTRA."""
    t2 = (de / base) ** 2
    return np.sqrt((1 - R_INTRA) * t2 / (1 + R_INTRA * t2))


def muestrear(dist, media, de, size, rng):
    """Genera valores respetando la forma de la distribucion de cada medida."""
    if dist == "normal":
        return rng.normal(media, de, size)
    if dist == "poisson":
        return rng.poisson(max(media, 0.05), size).astype(float)
    if dist in ("lognormal", "asimetrica"):
        media = max(media, 1e-6)
        sigma = np.sqrt(np.log1p((de / media) ** 2))
        mu = np.log(media) - sigma ** 2 / 2
        return rng.lognormal(mu, sigma, size)
    raise ValueError(dist)


# ---------------------------------------------------------------- participantes
def generar_participantes(rng):
    gen = np.array(["mujer"] * N_MUJERES + ["varon"] * (N_PARTICIPANTES - N_MUJERES))
    rng.shuffle(gen)
    filas = []
    for i in range(N_PARTICIPANTES):
        filas.append(dict(
            id=f"P{i+1:03d}",
            edad=int(round(np.clip(rng.normal(25, 4.5), 18, 40))),
            genero=gen[i],
            # filas de los dos cuadrados, como las sugiere la web a partir del numero
            secuencia=i % 4,                       # fila de CUADRADO_CONDICIONES
            secuencia_dominios=(i // 4) % 4,       # fila de CUADRADO_DOMINIOS
            sospecha=bool(rng.random() < PROP_SOSPECHA),
            ucla=float(np.clip(rng.normal(42, 9), 20, 80)),
            ecr_ansiedad=float(np.clip(rng.normal(3.4, 1.1), 1, 7)),
            ecr_evitacion=float(np.clip(rng.normal(3.1, 1.0), 1, 7)),
        ))
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- episodios
def generar_episodios(participantes, rng):
    filas = []
    for _, p in participantes.iterrows():
        orden_cond = CUADRADO_CONDICIONES[p.secuencia]
        dominio_de = CUADRADO_DOMINIOS[p.secuencia_dominios]   # condicion -> dominio
        for pos in range(N_EPISODIOS):
            condicion = orden_cond[pos]
            agente, feedback = CONDICIONES[condicion]
            # pre-rating de malestar de la situacion (0-10), elicitado al inicio
            pre = round(float(np.clip(rng.normal(5.2, 1.9), 0, 10)), 1)
            filas.append(dict(
                id=p.id, episodio=pos + 1, agente=agente, feedback=feedback,
                dominio=DOMINIOS[dominio_de[condicion]],
                pre_malestar=pre,
                alerta_malestar=pre >= UMBRAL_ALERTA_MALESTAR,
            ))
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- epocas de SCL
def generar_epocas(episodios, z_scl, rng, habituacion=None, rho=None):
    """SCL tonico en uS por epoca de 10 s, dentro de la ventana fija de cada episodio.

    Cada episodio tiene su nivel de reposo (el de la persona mas la deriva de Kelly
    entre episodios), al que se suma la elevacion de la tarea y una pendiente de
    habituacion. El residuo es AR(1) entre epocas, porque el SCL tonico cambia
    despacio, y multiplicativo, como el resto de las medidas positivas: el SCL nunca
    es negativo. Su desvio es el de una ronda, de modo que la correlacion
    intra-sujeto del SCL sigue en R_INTRA. scl_basal es la linea base en reposo del
    episodio. z_scl: puntaje de cada participante para el SCL, {id: z}.
    """
    habituacion = HABITUACION_SCL_EPOCA if habituacion is None else habituacion
    rho = RHO_EPOCA if rho is None else rho
    cfg = VARIABLES["scl_media"]
    de_b, _ = reparto_varianza(cfg["de"])
    s = np.sqrt(np.log1p(cv_residual(cfg["de"], cfg["base"]) ** 2))   # DE del log
    n = len(episodios)

    escala = np.array([factor_persona(z_scl[i], de_b / cfg["base"]) for i in episodios.id])
    reposo = cfg["base"] * escala + DERIVA_SCL_POR_EPISODIO * (episodios.episodio.to_numpy() - 1)
    atenuacion = np.array([atenuacion_habituacion(a, f)
                           for a, f in zip(episodios.agente, episodios.feedback)])
    t = np.arange(1, N_EPOCAS + 1) - (N_EPOCAS + 1) / 2     # centrada: sin efecto de nivel
    tendencia = (reposo + ELEVACION_TAREA * escala)[:, None] \
        + (habituacion * (1 - atenuacion))[:, None] * t

    res = np.empty((n, N_EPOCAS))
    res[:, 0] = rng.normal(0, s, n)
    for k in range(1, N_EPOCAS):
        res[:, k] = rho * res[:, k - 1] + rng.normal(0, s * np.sqrt(1 - rho ** 2), n)
    scl = tendencia * np.exp(res - s ** 2 / 2)
    basal = reposo * np.exp(rng.normal(0, s, n) - s ** 2 / 2)

    epoca = np.tile(np.arange(1, N_EPOCAS + 1), n)
    return pd.DataFrame(dict(
        id=np.repeat(episodios.id.to_numpy(), N_EPOCAS),
        episodio=np.repeat(episodios.episodio.to_numpy(), N_EPOCAS),
        agente=np.repeat(episodios.agente.to_numpy(), N_EPOCAS),
        feedback=np.repeat(episodios.feedback.to_numpy(), N_EPOCAS),
        ronda=(epoca - 1) // (N_EPOCAS // N_RONDAS) + 1,
        epoca=epoca,
        scl=scl.ravel(),
        scl_basal=np.repeat(basal, N_EPOCAS),
    ))


def pendiente_kelly(epocas):
    """Pendiente de habituacion de cada episodio, como la estiman Kelly et al.:
    minimos cuadrados de log(SCL + 1) - log(SCL_basal + 1) sobre las epocas, en
    unidades de log por epoca. Restar la linea base cambia el nivel y no la
    pendiente. Deja afuera las epocas con artefacto o faltantes, y da NaN si quedan
    menos de dos de las tres rondas."""
    e = epocas.sort_values(["id", "episodio", "epoca"])
    if len(e) % N_EPOCAS:
        raise ValueError("cada episodio tiene que tener sus N_EPOCAS epocas")
    y = (np.log1p(e.scl) - np.log1p(e.scl_basal)).to_numpy()
    if "artefacto_eda" in e:
        y = np.where(e.artefacto_eda.to_numpy(dtype=bool), np.nan, y)
    y = y.reshape(-1, N_EPOCAS)
    valido = ~np.isnan(y)
    t = np.where(valido, np.arange(1, N_EPOCAS + 1, dtype=float), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        tc = t - np.nanmean(t, axis=1, keepdims=True)
        yc = y - np.nanmean(y, axis=1, keepdims=True)
        pendiente = np.nansum(tc * yc, axis=1) / np.nansum(tc ** 2, axis=1)
    rondas_con_datos = valido.reshape(len(y), N_RONDAS, -1).any(axis=2).sum(axis=1)
    pendiente[rondas_con_datos < 2] = np.nan
    out = e.iloc[::N_EPOCAS][["id", "episodio", "agente", "feedback"]].reset_index(drop=True)
    out["pendiente"] = pendiente
    return out


def ensuciar_epocas(epocas, rondas):
    """Lleva a las epocas la contaminacion que ensuciar() puso en su ronda: si el SCL
    de la ronda tiene un artefacto, sus epocas tienen el mismo; si se perdio, se
    pierden. Antes de ensuciar, el SCL de la ronda es la media de sus epocas."""
    e = epocas.copy()
    claves = ["id", "episodio", "ronda"]
    ronda = e[claves].merge(rondas[claves + ["scl_media", "artefacto_eda"]],
                            on=claves, how="left")
    limpia = e.groupby(claves).scl.transform("mean").to_numpy()
    artefacto = ronda.artefacto_eda.to_numpy(dtype=bool)
    factor = np.where(artefacto, ronda.scl_media.to_numpy() / limpia, 1.0)
    e["scl"] = np.where(ronda.scl_media.isna(), np.nan, e.scl.to_numpy() * factor)
    e["artefacto_eda"] = artefacto
    return e


# ---------------------------------------------------------------- rondas
def generar_rondas(participantes, episodios, rng):
    """Una fila por ronda con las medidas fisiologicas y el autoinforme subyacente.
    Devuelve (rondas, epocas): el SCL de cada ronda es la media de sus epocas."""
    # factor comun participante-nivel para el acople debil autoinforme-fisiologia
    comun = rng.normal(0, 1, N_PARTICIPANTES)
    carga = np.sqrt(R_AUTOINFORME_FISIO)

    # z de cada participante para cada variable (correlacion intra-sujeto)
    z = {}
    for v, cfg in VARIABLES.items():
        propio = rng.normal(0, 1, N_PARTICIPANTES)
        signo = -1 if cfg["delta"] < 0 else 1      # mas estres, valores mas bajos
        z[v] = dict(zip(participantes.id,
                        signo * carga * comun + np.sqrt(1 - carga ** 2) * propio))

    # Flujo de azar propio: cambiar la ventana o el ruido del SCL no mueve el resto.
    epocas = generar_epocas(episodios, z["scl_media"], rng.spawn(1)[0])
    scl_ronda = epocas.groupby(["id", "episodio", "ronda"]).scl.mean().to_dict()

    genero = dict(zip(participantes.id, participantes.genero))
    rho_pre = R_PRE_AUTOINFORME

    filas = []
    for _, ep in episodios.iterrows():
        z_pre = (ep.pre_malestar - 5.2) / 1.9
        for r in range(1, N_RONDAS + 1):
            fila = dict(id=ep.id, episodio=ep.episodio, ronda=r,
                        agente=ep.agente, feedback=ep.feedback)
            rampa = r / N_RONDAS          # el efecto se acumula a lo largo del episodio
            for v, cfg in VARIABLES.items():
                if v == "scl_media":
                    fila[v] = float(scl_ronda[(ep.id, ep.episodio, r)])
                    continue
                de_b, de_w = reparto_varianza(cfg["de"])
                ef = efecto_condicion(cfg["delta"], ep.agente, ep.feedback) * rampa

                # moderacion por genero, solo en medidas electrodermicas con efecto
                # de condicion: la frecuencia y la amplitud de las SCR
                if v.startswith(("ns_scr", "scr_amp")) and genero[ep.id] == "mujer":
                    ef *= MOD_GENERO_EDA

                zi = z[v][ep.id]
                if cfg["dist"] == "normal":
                    # el pre-rating explica parte del residuo sin cambiar su DE
                    media = cfg["base"] + de_b * zi + ef
                    if v in AUTOINFORME:
                        signo = -1 if cfg["delta"] < 0 else 1
                        val = media + de_w * (signo * rho_pre * z_pre
                                              + np.sqrt(1 - rho_pre ** 2) * rng.normal())
                    else:
                        val = rng.normal(media, de_w)
                elif cfg["dist"] == "poisson":
                    # la varianza residual es lambda: el factor de persona aporta
                    # lo que falta para llegar a R_INTRA
                    cv = np.sqrt(R_INTRA / (1 - R_INTRA) / cfg["base"])
                    media = cfg["base"] * factor_persona(zi, cv) + ef
                    val = muestrear("poisson", media, None, 1, rng)[0]
                else:
                    # medidas positivas: nivel y efecto proporcionales, residuo con
                    # coeficiente de variacion constante
                    nivel = cfg["base"] * factor_persona(zi, de_b / cfg["base"])
                    media = max(nivel * (1 + ef / cfg["base"]), 1e-3)
                    val = muestrear(cfg["dist"], media,
                                    media * cv_residual(cfg["de"], cfg["base"]), 1, rng)[0]
                fila[v] = float(val)

            for v in AUTOINFORME:
                fila[v] = float(np.clip(fila[v], *RANGO[v]))
            fila["pnn50"] = float(np.clip(fila["pnn50"], 0, 100))
            fila["ns_scr_n"] = float(round(fila["ns_scr_n"]))
            filas.append(fila)
    rondas = pd.DataFrame(filas)
    # agregar_autoinforme necesita a la misma persona para lo que se mide fuera de las rondas
    rondas.attrs["z"] = z
    rondas.attrs["comun"] = dict(zip(participantes.id, comun))
    return rondas, epocas


# ---------------------------------------------------------------- autoinforme
def agregar_autoinforme(episodios, rondas, rng, faltantes=PROP_FALTANTES):
    """El autoinforme tal como se mide: SUDS antes y despues del episodio, y SAM al
    final. Lo que se mide al final es el estado subyacente de la ultima ronda, donde
    el efecto ya se acumulo por completo. Usa su propio flujo de azar."""
    z, comun = rondas.attrs["z"], rondas.attrs["comun"]
    carga = np.sqrt(R_AUTOINFORME_FISIO)
    finales = (rondas[rondas.ronda == N_RONDAS]
               .set_index(["id", "episodio"])[list(AUTOINFORME)])
    propio = {i: rng.normal() for i in comun}
    filas = []
    for _, ep in episodios.iterrows():
        rho, z_pre = R_PRE_AUTOINFORME, (ep.pre_malestar - 5.2) / 1.9
        cfg = VARIABLES["suds"]
        de_b, de_w = reparto_varianza(cfg["de"])
        pre = (cfg["base"] + de_b * z["suds"][ep.id]
               + de_w * (rho * z_pre + np.sqrt(1 - rho ** 2) * rng.normal()))
        de_b, de_w = reparto_varianza(SAM_ACTIVACION["de"])
        z_activacion = carga * comun[ep.id] + np.sqrt(1 - carga ** 2) * propio[ep.id]
        activacion = (SAM_ACTIVACION["base"] + de_b * z_activacion
                      + efecto_condicion(SAM_ACTIVACION["delta"], ep.agente, ep.feedback)
                      + de_w * rng.normal())
        final = finales.loc[(ep.id, ep.episodio)]
        filas.append(dict(
            id=ep.id, episodio=ep.episodio,
            suds_pre=float(np.clip(pre, *RANGO["suds"])),
            suds_post=final.suds,
            sam_valencia=final.sam_valencia,
            sam_activacion=float(np.clip(activacion, *RANGO["sam_valencia"])),
        ))
    medidas = pd.DataFrame(filas)
    for v in ("suds_pre", "sam_activacion"):
        medidas.loc[rng.random(len(medidas)) < faltantes, v] = np.nan
    medidas["suds_cambio"] = medidas.suds_post - medidas.suds_pre
    return episodios.merge(medidas, on=["id", "episodio"])


# ---------------------------------------------------------------- post-episodio
def medidas_post_episodio(episodios, participantes, rng):
    """Autenticidad percibida, los seis items de chequeo de manipulacion, la
    naturalidad, la credibilidad del bloque final, la codificacion de la transcripcion
    y las medidas conductuales."""
    sospecha = dict(zip(participantes.id, participantes.sospecha))
    # Flujo propio: la variacion de la espera humana no corre los sorteos de ensuciar().
    rng_espera = np.random.default_rng([SEMILLA, 1])
    # Tambien propio para la atribucion y la codificacion, por el mismo motivo.
    rng_codigo = np.random.default_rng([SEMILLA, 3])
    out = []
    for _, ep in episodios.iterrows():
        humano = ep.agente == "humano"
        valida = ep.feedback == "validacion"
        # autenticidad: efecto de agente (H1c), mayor en validacion
        base = 4.6 if valida else 2.9
        aut = base + (0.8 if humano else -0.2) * (1.0 if valida else 0.45)
        # chequeo por componente: invalidacion, atribucion y retirada (2 items cada uno)
        ent = 5.6 if valida else 2.2        # "entendio lo que me pasaba"
        sent = 5.4 if valida else 2.0       # "considero que mi reaccion tenia sentido"
        interes = 5.5 if valida else 2.3    # "tenia interes en seguir"
        cortar = 2.0 if valida else 5.3     # "queria terminar la conversacion"
        rr = lambda m: float(np.clip(rng.normal(m, 0.95), 1, 7))
        rr_atribucion = lambda: float(np.clip(rng_codigo.normal(ATRIBUCION[ep.feedback], 0.95), 1, 7))
        codigos = {c: float(np.clip(rng_codigo.normal(m[ep.feedback], CODIFICACION_DE[ep.agente]), 1, 7))
                   for c, m in CODIFICACION.items()}
        # credibilidad: 0 = seguro que es una IA, 100 = seguro que es una persona
        if not humano:
            cred = CREDIBILIDAD_IA
        elif sospecha[ep.id]:
            cred = CREDIBILIDAD_HUMANO_SOSPECHA
        else:
            cred = CREDIBILIDAD_HUMANO
        largo_de = LARGO_HUMANO_DE if humano else LARGO_AGENTE_DE
        largo = round(float(max(rng.normal(LARGO_AGENTE[ep.feedback], largo_de), 20)), 1)
        if humano:
            espera = (N_RONDAS * (TIEMPO_LECTURA_S + largo / TIPEO_CARACTERES_S)
                      * rng_espera.lognormal(0, VARIACION_ESPERA_HUMANO))
        else:
            espera = N_RONDAS * (1.2 + 0.045 * largo)
        out.append(dict(
            id=ep.id, episodio=ep.episodio,
            autenticidad=rr(aut),
            mc_entendio=rr(ent), mc_tenia_sentido=rr(sent),
            mc_problema_era_yo=rr_atribucion(), mc_atribuyo_culpa=rr_atribucion(),
            mc_interes=rr(interes), mc_queria_cortar=rr(cortar),
            **codigos,
            naturalidad=rr(NATURALIDAD[ep.feedback]),
            credibilidad=float(np.clip(rng.normal(*cred), 0, 100)),
            largo_medio_agente=largo,
            turnos_hasta_cierre=N_RONDAS,
            espera_acumulada_s=round(espera, 3),
            # Se sortea tambien en la condicion humana, y en este lugar, para no
            # correr los sorteos de ensuciar().
            turnos_respaldo=int(rng.binomial(N_RONDAS, PROB_TURNO_RESPALDO)) * (not humano),
        ))
    return pd.DataFrame(out)


def agregar_medidas_post(episodios, participantes, rng):
    post = medidas_post_episodio(episodios, participantes, rng)
    return episodios.merge(post, on=["id", "episodio"])


# ---------------------------------------------------------------- contaminacion
def ensuciar(rondas, episodios, participantes, rng):
    """Introduce las imperfecciones descritas en A3.1. Las epocas las reciben despues,
    con ensuciar_epocas()."""
    rondas = rondas.copy()
    episodios = episodios.copy()
    n = len(rondas)

    rondas["artefacto_eda"] = rng.random(n) < PROP_ARTEFACTO_EDA
    rondas.loc[rondas.artefacto_eda, "scl_media"] *= rng.uniform(2.5, 6.0,
                                                                 rondas.artefacto_eda.sum())
    rondas["prop_ectopicos"] = np.clip(rng.beta(*BETA_ECTOPICOS, n), 0, 1)
    graves = rondas.prop_ectopicos > PROP_ECTOPICOS
    for v in ("rmssd", "sdrr", "pnn50", "hf"):
        rondas.loc[graves, v] *= rng.uniform(1.6, 3.2, graves.sum())

    for v in VARIABLES:
        perdidos = rng.random(n) < PROP_FALTANTES
        rondas.loc[perdidos, v] = np.nan

    # participantes que no registran la etiqueta del agente: conviccion invertida
    fallan = rng.choice(participantes.id, N_FALLA_ETIQUETA, replace=False)
    invertir = episodios.id.isin(fallan) & (rng.random(len(episodios)) < PROB_FALLA_POR_EPISODIO)
    episodios.loc[invertir, "credibilidad"] = 100 - episodios.loc[invertir, "credibilidad"]

    # criterio de marcado de la seccion 2.5: conviccion del lado opuesto a la etiqueta
    episodios["falla_etiqueta"] = (((episodios.agente == "humano") & (episodios.credibilidad < 50))
                                   | ((episodios.agente == "ia") & (episodios.credibilidad > 50)))

    # episodios en que el agente se sale del protocolo
    idx = rng.choice(len(episodios), N_FUERA_PROTOCOLO, replace=False)
    episodios["fuera_protocolo"] = False
    episodios.iloc[idx, episodios.columns.get_loc("fuera_protocolo")] = True
    return rondas, episodios


# ---------------------------------------------------------------- verificacion
def contrastes_realizados(rondas, episodios):
    """Los tres contrastes del plan de analisis sobre el conjunto generado, en la
    metrica que corresponde a un diseno intra-sujeto. Sirve de verificacion: la
    potencia esperada de cada uno esta en 00_potencia.py y en el Anexo A4."""
    from scipy import stats
    r = rondas.copy()
    r["ln_hf"] = np.log(r["hf"].clip(lower=1))
    out = {}
    for v in ("rmssd", "rr_medio", "ln_hf", "suds_cambio", "sam_valencia"):
        d = (episodios if v in ("suds_cambio", "sam_valencia") else r).dropna(subset=[v])
        c = d.groupby(["id", "agente", "feedback"])[v].mean().unstack([1, 2])
        h1a = (c[("humano", "rechazo")] - c[("ia", "rechazo")]).dropna()
        h1d = ((c[("humano", "rechazo")] - c[("ia", "rechazo")])
               - (c[("humano", "validacion")] - c[("ia", "validacion")])).dropna()
        fb = (((c[("humano", "rechazo")] + c[("ia", "rechazo")])
               - (c[("humano", "validacion")] + c[("ia", "validacion")])) / 2).dropna()
        out[v] = {nom: (round(float(x.mean() / x.std(ddof=1)), 3),
                        float(stats.ttest_1samp(x, 0).pvalue))
                  for nom, x in (("H1a", h1a), ("H1d", h1d), ("principal", fb))}
    return out


def contraste_h1b(epocas, rondas):
    """H1b sobre el conjunto generado: la pendiente, humano menos IA bajo rechazo, y el
    nivel medio del SCL, que H1b declara nulo. Sin las rondas con artefacto."""
    from scipy import stats
    def agente_en_rechazo(tabla, v):
        c = tabla.dropna(subset=[v]).groupby(["id", "agente", "feedback"])[v].mean().unstack([1, 2])
        return (c[("humano", "rechazo")] - c[("ia", "rechazo")]).dropna()
    limpias = rondas[~rondas.artefacto_eda]
    out = {}
    for nombre, x in (("pendiente", agente_en_rechazo(pendiente_kelly(epocas), "pendiente")),
                      ("nivel", agente_en_rechazo(limpias, "scl_media"))):
        out[nombre] = (round(float(x.mean() / x.std(ddof=1)), 3),
                       float(stats.ttest_1samp(x, 0).pvalue))
    return out


# ---------------------------------------------------------------- main
def main():
    participantes = generar_participantes(rng)
    episodios = generar_episodios(participantes, rng)
    rondas, epocas = generar_rondas(participantes, episodios, rng)
    episodios = agregar_medidas_post(episodios, participantes, rng)
    rondas, episodios = ensuciar(rondas, episodios, participantes, rng)
    epocas = ensuciar_epocas(epocas, rondas)
    episodios = agregar_autoinforme(episodios, rondas, np.random.default_rng([SEMILLA, 2]))
    rondas_medidas = rondas.drop(columns=list(AUTOINFORME))

    params = pd.DataFrame(
        [dict(parametro=k, valor=str(v)) for k, v in {
            "semilla": SEMILLA, "n_participantes": N_PARTICIPANTES,
            "n_mujeres": N_MUJERES, "n_episodios": N_EPISODIOS, "n_rondas": N_RONDAS,
            "frac_rechazo": FRAC_RECHAZO, "frac_validacion": FRAC_VALIDACION,
            "agente_en_rechazo": AGENTE_EN_RECHAZO,
            "agente_en_validacion": AGENTE_EN_VALIDACION,
            "r_intra": R_INTRA, "r_autoinforme_fisio": R_AUTOINFORME_FISIO,
            "r_pre_autoinforme": R_PRE_AUTOINFORME,
            "mod_genero_eda": MOD_GENERO_EDA,
            "deriva_scl_por_episodio": DERIVA_SCL_POR_EPISODIO,
            "n_epocas": N_EPOCAS,
            "rho_epoca": RHO_EPOCA,
            "elevacion_tarea": ELEVACION_TAREA,
            "kelly_dz": KELLY_DZ,
            "habituacion_scl_epoca": HABITUACION_SCL_EPOCA,
            "atenuacion_rechazo": ATENUACION_RECHAZO,
            "prop_faltantes": PROP_FALTANTES,
            "prop_artefacto_eda": PROP_ARTEFACTO_EDA,
            "prop_ectopicos": PROP_ECTOPICOS,
            "beta_ectopicos": BETA_ECTOPICOS,
            "n_falla_etiqueta": N_FALLA_ETIQUETA,
            "prob_falla_por_episodio": PROB_FALLA_POR_EPISODIO,
            "n_fuera_protocolo": N_FUERA_PROTOCOLO,
            "prop_sospecha": PROP_SOSPECHA,
            "credibilidad_humano": CREDIBILIDAD_HUMANO,
            "credibilidad_humano_sospecha": CREDIBILIDAD_HUMANO_SOSPECHA,
            "credibilidad_ia": CREDIBILIDAD_IA,
            "naturalidad": NATURALIDAD,
            "largo_agente": LARGO_AGENTE,
            "largo_agente_de": LARGO_AGENTE_DE,
            "largo_humano_de": LARGO_HUMANO_DE,
            "tiempo_lectura_s": TIEMPO_LECTURA_S,
            "tipeo_caracteres_s": TIPEO_CARACTERES_S,
            "variacion_espera_humano": VARIACION_ESPERA_HUMANO,
            "prob_turno_respaldo": PROB_TURNO_RESPALDO,
            "umbral_alerta_malestar": UMBRAL_ALERTA_MALESTAR,
            "sam_activacion": SAM_ACTIVACION,
            "atribucion": ATRIBUCION,
            "codificacion": CODIFICACION,
            "codificacion_de": CODIFICACION_DE,
        }.items()]
        + [dict(parametro=f"{v}.{k}", valor=str(x))
           for v, cfg in VARIABLES.items() for k, x in cfg.items()]
    )

    xlsx = SALIDA / "datos_crudos.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
        participantes.to_excel(w, sheet_name="participantes", index=False)
        episodios.to_excel(w, sheet_name="episodios", index=False)
        rondas_medidas.to_excel(w, sheet_name="rondas", index=False)
        epocas.to_excel(w, sheet_name="epocas", index=False)
        params.to_excel(w, sheet_name="parametros", index=False)
    for nom, df in [("participantes", participantes), ("episodios", episodios),
                    ("rondas", rondas_medidas), ("epocas", epocas)]:
        df.to_csv(SALIDA / f"datos_crudos_{nom}.csv", index=False)

    print(f"semilla {SEMILLA}")
    print(f"participantes {len(participantes)} | episodios {len(episodios)} "
          f"| rondas {len(rondas)} | epocas {len(epocas)}")
    print(f"escrito: {xlsx}")
    print("\ncontrastes realizados en este conjunto (d de Cohen pareado y p)")
    print(f"  {'variable':<13}{'H1a agente|rechazo':<24}{'H1d interaccion':<24}{'principal'}")
    for v, r in contrastes_realizados(rondas, episodios).items():
        celdas = "".join(f"d={r[k][0]:<7} p={r[k][1]:<9.4f}" for k in ("H1a", "H1d", "principal"))
        print(f"  {v:<13}{celdas}")
    h1b = contraste_h1b(epocas, rondas)
    print("\nH1b, humano - IA bajo rechazo (d de Cohen pareado y p)")
    print(f"  pendiente del SCL   d={h1b['pendiente'][0]:<7} p={h1b['pendiente'][1]:.4f}")
    print(f"  nivel medio del SCL d={h1b['nivel'][0]:<7} p={h1b['nivel'][1]:.4f}   (nulo declarado)")


if __name__ == "__main__":
    main()
