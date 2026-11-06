"""
01_simular.py — Genera los datos crudos simulados del estudio de AI companions.

Los datos son SIMULADOS. Este script implementa la estructura de efectos descrita
en el Anexo A5 del documento. Cada constante de PARAMS se corresponde con una fila
de la tabla A5.5: si se cambia una, hay que cambiar la otra.

Copia de trabajo del script de Elena, carpeta simulacion de Drive. Las diferencias
con el original y su motivo estan en README.md.

Produce datos deliberadamente "sucios" (artefactos, latidos ectopicos, faltantes,
fallos de chequeo de etiqueta) para que 02_limpiar.py tenga sobre que operar y las
exclusiones reportadas en la seccion 2.5 del paper tengan sustento.

Salida: datos/datos_crudos.xlsx  (hojas: participantes, episodios, rondas, parametros)
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
# Cada entrada corresponde a una fila de la tabla A5.5 del Anexo.

N_PARTICIPANTES = 150   # determinado por simulacion de potencia, ver 00_potencia.py
N_MUJERES = 81
N_EPISODIOS = 4
N_RONDAS = 3

# Supuesto central (A5.2). Fracciones del delta de estres de laboratorio.
FRAC_RECHAZO = 0.60
FRAC_VALIDACION = 0.25
# Efecto de agente como fraccion del efecto de retroalimentacion. Asimetrico (H1d).
AGENTE_EN_RECHAZO = 0.70      # calibrado: f realizado medio = 0.25 (ver A5.2)
AGENTE_EN_VALIDACION = 0.30   # mantiene la asimetria de H1d

# Correlacion intra-sujeto entre medidas repetidas (A5.3); fija el reparto de
# varianza entre el intercepto del participante y el residuo.
R_INTRA = 0.50

# Desacople autorreporte-fisiologia (A5.3): correlacion entre los interceptos de
# cada participante, con el signo de cada medida bajo estres.
R_AUTOINFORME_FISIO = 0.15

# Correlacion entre el pre-rating de la situacion y el autoinforme del episodio.
# Es la covariable del plan de analisis (A6). Supuesto, sin fuente directa.
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
    "scl_media":      dict(base=6.00, de=2.50, delta=0.00,  dist="lognormal"),
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
    "panas_n":        dict(base=15.0,  de=4.50,  delta=3.47,   dist="normal"),   # ES 0.77 x 4.50
    "suds":           dict(base=2.50,  de=1.50,  delta=1.16,   dist="normal"),   # ES 0.77 x 1.50
}

# El SCL no tiene efecto de nivel (Iffland) pero si de pendiente (Kelly):
# habituacion por ronda, atenuada bajo rechazo, y mas con un agente humano (H1b).
HABITUACION_SCL = -0.40            # microsiemens por ronda, condicion validacion
ATENUACION_RECHAZO = 0.55          # el rechazo habitua un 55% menos, en promedio de agentes

# Contaminacion deliberada (A5.1)
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
# piloto con el prompt del Anexo A2: el rechazo escribe algo menos.
LARGO_AGENTE = dict(validacion=187, rechazo=165)
LARGO_AGENTE_DE = 25
PROB_TURNO_RESPALDO = 0.01
UMBRAL_ALERTA_MALESTAR = 9

DOMINIOS = ["trabajo_estudio", "amistad", "familia_pareja", "uno_mismo"]
CONDICIONES = [("humano", "validacion"), ("humano", "rechazo"),
               ("ia", "validacion"), ("ia", "rechazo")]


# ---------------------------------------------------------------- utilidades
def cuadrado_latino(n=4):
    """Cuadrado latino ciclico n x n: cada condicion una vez en cada posicion."""
    return [[(i + j) % n for j in range(n)] for i in range(n)]


def reparto_varianza(de_total, r=None):
    """Separa el desvio total en componente entre-sujetos y residual
    de modo que la correlacion intra-sujeto sea r. Lee R_INTRA en tiempo de
    llamada, no como argumento por defecto, para poder recalibrar."""
    r = R_INTRA if r is None else r
    var = de_total ** 2
    return np.sqrt(var * r), np.sqrt(var * (1 - r))


def efecto_condicion(delta, agente, feedback):
    """Efecto de condicion en unidades de la variable, segun A5.2."""
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
    ls = cuadrado_latino(4)
    filas = []
    for i in range(N_PARTICIPANTES):
        filas.append(dict(
            id=f"P{i+1:03d}",
            edad=int(round(np.clip(rng.normal(25, 4.5), 18, 40))),
            genero=gen[i],
            secuencia=i % 4,                       # fila del cuadrado de condiciones
            secuencia_dominios=(i // 4) % 4,       # fila del cuadrado de dominios
            sospecha=bool(rng.random() < PROP_SOSPECHA),
            ucla=float(np.clip(rng.normal(42, 9), 20, 80)),
            ecr_ansiedad=float(np.clip(rng.normal(3.4, 1.1), 1, 7)),
            ecr_evitacion=float(np.clip(rng.normal(3.1, 1.0), 1, 7)),
        ))
    df = pd.DataFrame(filas)
    df.attrs["latino"] = ls
    return df, ls


# ---------------------------------------------------------------- episodios
def generar_episodios(participantes, ls, rng):
    filas = []
    for _, p in participantes.iterrows():
        orden_cond = ls[p.secuencia]
        dominio_de = ls[p.secuencia_dominios]      # condicion -> dominio, cuadrado independiente
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


# ---------------------------------------------------------------- rondas
def generar_rondas(participantes, episodios, rng):
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

    genero = dict(zip(participantes.id, participantes.genero))
    centro_ronda = (N_RONDAS + 1) / 2
    rho_pre = R_PRE_AUTOINFORME

    filas = []
    for _, ep in episodios.iterrows():
        z_pre = (ep.pre_malestar - 5.2) / 1.9
        for r in range(1, N_RONDAS + 1):
            fila = dict(id=ep.id, episodio=ep.episodio, ronda=r,
                        agente=ep.agente, feedback=ep.feedback)
            rampa = r / N_RONDAS          # el efecto se acumula a lo largo del episodio
            for v, cfg in VARIABLES.items():
                de_b, de_w = reparto_varianza(cfg["de"])
                ef = efecto_condicion(cfg["delta"], ep.agente, ep.feedback) * rampa

                # moderacion por genero, solo en medidas electrodermicas
                if v.startswith(("scl", "ns_scr", "scr_amp")) and genero[ep.id] == "mujer":
                    ef *= MOD_GENERO_EDA

                zi = z[v][ep.id]
                if cfg["dist"] == "normal":
                    # el pre-rating explica parte del residuo sin cambiar su DE
                    media = cfg["base"] + de_b * zi + ef
                    if v in ("panas_n", "suds"):
                        val = media + de_w * (rho_pre * z_pre
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
                    media = nivel * (1 + ef / cfg["base"])

                    # SCL: sin efecto de nivel, el efecto esta en la pendiente (Kelly).
                    # Centrada en la ronda media, la pendiente no mueve el promedio.
                    if v == "scl_media":
                        hab = HABITUACION_SCL * (r - centro_ronda)
                        hab *= 1 - atenuacion_habituacion(ep.agente, ep.feedback)
                        media += hab + DERIVA_SCL_POR_EPISODIO * (ep.episodio - 1)

                    media = max(media, 1e-3)
                    val = muestrear(cfg["dist"], media,
                                    media * cv_residual(cfg["de"], cfg["base"]), 1, rng)[0]
                fila[v] = float(val)

            fila["panas_n"] = float(np.clip(fila["panas_n"], 10, 50))
            fila["suds"] = float(np.clip(fila["suds"], 0, 10))
            fila["pnn50"] = float(np.clip(fila["pnn50"], 0, 100))
            fila["ns_scr_n"] = float(round(fila["ns_scr_n"]))
            filas.append(fila)
    return pd.DataFrame(filas)


# ---------------------------------------------------------------- post-episodio
def medidas_post_episodio(episodios, participantes, rng):
    """Autenticidad percibida, los cuatro items de chequeo de manipulacion, la
    naturalidad, la credibilidad del bloque final y las medidas conductuales."""
    sospecha = dict(zip(participantes.id, participantes.sospecha))
    out = []
    for _, ep in episodios.iterrows():
        humano = ep.agente == "humano"
        valida = ep.feedback == "validacion"
        # autenticidad: efecto de agente (H1c), mayor en validacion
        base = 4.6 if valida else 2.9
        aut = base + (0.8 if humano else -0.2) * (1.0 if valida else 0.45)
        # chequeo por componente: invalidacion (2 items) y retirada (2 items)
        ent = 5.6 if valida else 2.2        # "entendio lo que me pasaba"
        sent = 5.4 if valida else 2.0       # "considero que mi reaccion tenia sentido"
        interes = 5.5 if valida else 2.3    # "tenia interes en seguir"
        cortar = 2.0 if valida else 5.3     # "queria terminar la conversacion"
        rr = lambda m: float(np.clip(rng.normal(m, 0.95), 1, 7))
        # credibilidad: 0 = seguro que es una IA, 100 = seguro que es una persona
        if not humano:
            cred = CREDIBILIDAD_IA
        elif sospecha[ep.id]:
            cred = CREDIBILIDAD_HUMANO_SOSPECHA
        else:
            cred = CREDIBILIDAD_HUMANO
        largo = float(max(rng.normal(LARGO_AGENTE[ep.feedback], LARGO_AGENTE_DE), 20))
        out.append(dict(
            id=ep.id, episodio=ep.episodio,
            autenticidad=rr(aut),
            mc_entendio=rr(ent), mc_tenia_sentido=rr(sent),
            mc_interes=rr(interes), mc_queria_cortar=rr(cortar),
            naturalidad=rr(NATURALIDAD[ep.feedback]),
            credibilidad=float(np.clip(rng.normal(*cred), 0, 100)),
            largo_medio_agente=round(largo, 1),
            turnos_hasta_cierre=N_RONDAS,
            espera_acumulada_s=round(N_RONDAS * (1.2 + 0.045 * round(largo, 1)), 3),
            turnos_respaldo=int(rng.binomial(N_RONDAS, PROB_TURNO_RESPALDO)),
        ))
    return pd.DataFrame(out)


def agregar_medidas_post(episodios, participantes, rng):
    post = medidas_post_episodio(episodios, participantes, rng)
    return episodios.merge(post, on=["id", "episodio"])


# ---------------------------------------------------------------- contaminacion
def ensuciar(rondas, episodios, participantes, rng):
    """Introduce las imperfecciones descritas en A5.1."""
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
def contrastes_realizados(rondas):
    """Los tres contrastes del plan de analisis sobre el conjunto generado, en la
    metrica que corresponde a un diseno intra-sujeto. Sirve de verificacion: la
    potencia esperada de cada uno esta en 00_potencia.py y en el Anexo A6."""
    from scipy import stats
    r = rondas.copy()
    r["ln_hf"] = np.log(r["hf"].clip(lower=1))
    out = {}
    for v in ("rmssd", "rr_medio", "ln_hf", "panas_n", "suds"):
        d = r.dropna(subset=[v])
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


# ---------------------------------------------------------------- main
def main():
    participantes, ls = generar_participantes(rng)
    episodios = generar_episodios(participantes, ls, rng)
    rondas = generar_rondas(participantes, episodios, rng)
    episodios = agregar_medidas_post(episodios, participantes, rng)
    rondas, episodios = ensuciar(rondas, episodios, participantes, rng)

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
            "habituacion_scl": HABITUACION_SCL,
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
            "prob_turno_respaldo": PROB_TURNO_RESPALDO,
            "umbral_alerta_malestar": UMBRAL_ALERTA_MALESTAR,
        }.items()]
        + [dict(parametro=f"{v}.{k}", valor=str(x))
           for v, cfg in VARIABLES.items() for k, x in cfg.items()]
    )

    xlsx = SALIDA / "datos_crudos.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
        participantes.to_excel(w, sheet_name="participantes", index=False)
        episodios.to_excel(w, sheet_name="episodios", index=False)
        rondas.to_excel(w, sheet_name="rondas", index=False)
        params.to_excel(w, sheet_name="parametros", index=False)
    for nom, df in [("participantes", participantes), ("episodios", episodios),
                    ("rondas", rondas)]:
        df.to_csv(SALIDA / f"datos_crudos_{nom}.csv", index=False)

    print(f"semilla {SEMILLA}")
    print(f"participantes {len(participantes)} | episodios {len(episodios)} "
          f"| rondas {len(rondas)}")
    print(f"escrito: {xlsx}")
    print("\ncontrastes realizados en este conjunto (d de Cohen pareado y p)")
    print(f"  {'variable':<11}{'H1a agente|rechazo':<24}{'H1d interaccion':<24}{'principal'}")
    for v, r in contrastes_realizados(rondas).items():
        celdas = "".join(f"d={r[k][0]:<7} p={r[k][1]:<9.4f}" for k in ("H1a", "H1d", "principal"))
        print(f"  {v:<11}{celdas}")


if __name__ == "__main__":
    main()
