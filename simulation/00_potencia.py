"""Potencia empirica de los contrastes del plan de analisis segun N (Anexo A4).

Para cada N genera REPS conjuntos sin contaminar y cuenta en que proporcion cada
contraste da p < .05. Las tres primeras columnas promedian cinco variables
dependientes; H1b es la pendiente del SCL por epocas, humano contra IA bajo rechazo.

    python3 00_potencia.py > salida_potencia.txt
"""
import importlib.util
from pathlib import Path

import numpy as np
from scipy import stats

spec = importlib.util.spec_from_file_location("sim", Path(__file__).with_name("01_simular.py"))
sim = importlib.util.module_from_spec(spec); spec.loader.exec_module(sim)
DV = ("rmssd", "rr_medio", "ln_hf", "suds_cambio", "sam_valencia")
POR_EPISODIO = ("suds_cambio", "sam_valencia")
A = 0.70
REPS = 100


def celdas(tabla, v):
    return tabla.dropna(subset=[v]).groupby(["id", "agente", "feedback"])[v].mean().unstack([1, 2])


def p_valor(x):
    return stats.ttest_1samp(x.dropna(), 0).pvalue


def contrastes(c):
    """Efecto principal de retroalimentacion, H1a y H1d, uno por participante."""
    h1a = c[("humano", "rechazo")] - c[("ia", "rechazo")]
    h1d = h1a - (c[("humano", "validacion")] - c[("ia", "validacion")])
    fb = ((c[("humano", "rechazo")] + c[("ia", "rechazo")])
          - (c[("humano", "validacion")] + c[("ia", "validacion")])) / 2
    return fb, h1a, h1d


def correr(n, s):
    sim.N_PARTICIPANTES = n; sim.N_MUJERES = int(round(n * 0.54))
    sim.AGENTE_EN_RECHAZO = A; sim.AGENTE_EN_VALIDACION = A * 0.43; sim.R_INTRA = 0.50
    rng = np.random.default_rng(s)
    p = sim.generar_participantes(rng); e = sim.generar_episodios(p, rng)
    r, epocas = sim.generar_rondas(p, e, rng); r["ln_hf"] = np.log(r["hf"].clip(lower=1))
    e = sim.agregar_autoinforme(e, r, np.random.default_rng([s, 2]), faltantes=0)
    return r, e, epocas


print(f"efecto a={A}: la IA en el {(1-A/2)/(1+A/2)*100:.0f}% de la respuesta humana", flush=True)
print(f"potencia empirica, {REPS} simulaciones por celda, alfa=.05, datos sin contaminar", flush=True)
print(f"(error de Monte Carlo de una proporcion cercana a .80: +-{1.96*np.sqrt(.8*.2/REPS):.2f})\n", flush=True)
print(f"{'N':<7}{'H1d interaccion':<18}{'H1a agente|rechazo':<22}{'efecto principal':<18}{'H1b pendiente SCL':<18}", flush=True)
for n in (40, 50, 60, 80, 120, 150, 200, 300):
    h1d, h1a, fb, h1b = [], [], [], []
    for s in range(REPS):
        r, e, epocas = correr(n, 50000 + s)
        p = {v: [p_valor(x) < .05 for x in contrastes(celdas(e if v in POR_EPISODIO else r, v))]
             for v in DV}
        fb.append(np.mean([p[v][0] for v in DV]))
        h1a.append(np.mean([p[v][1] for v in DV]))
        h1d.append(np.mean([p[v][2] for v in DV]))
        c = celdas(sim.pendiente_kelly(epocas), "pendiente")
        h1b.append(p_valor(c[("humano", "rechazo")] - c[("ia", "rechazo")]) < .05)
    print(f"{n:<7}{np.mean(h1d):<18.2f}{np.mean(h1a):<22.2f}{np.mean(fb):<18.2f}{np.mean(h1b):<18.2f}", flush=True)
