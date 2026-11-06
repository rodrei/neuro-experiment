"""Potencia empirica con el efecto en -50% (a=0.70): despeja el N para H1a, H1b y H1d."""
import importlib.util, sys
import numpy as np
from scipy import stats
spec = importlib.util.spec_from_file_location("sim", "01_simular.py")
sim = importlib.util.module_from_spec(spec); spec.loader.exec_module(sim)
DV = ("rmssd", "rr_medio", "ln_hf", "panas_n", "suds")
A = 0.70

def celdas(r, v):
    d = r.dropna(subset=[v])
    return d.groupby(["id","agente","feedback"])[v].mean().unstack([1,2])
def p_h1a(r, v):
    c = celdas(r, v)
    return stats.ttest_1samp((c[("humano","rechazo")]-c[("ia","rechazo")]).dropna(), 0).pvalue
def p_h1d(r, v):
    c = celdas(r, v)
    x = ((c[("humano","rechazo")]-c[("ia","rechazo")])
         - (c[("humano","validacion")]-c[("ia","validacion")])).dropna()
    return stats.ttest_1samp(x, 0).pvalue
def p_fb(r, v):
    c = celdas(r, v)
    x = (((c[("humano","rechazo")]+c[("ia","rechazo")])
          -(c[("humano","validacion")]+c[("ia","validacion")]))/2).dropna()
    return stats.ttest_1samp(x, 0).pvalue
def p_h1b(r):
    """Pendiente del SCL, ronda 3 menos ronda 1, humano contra IA bajo rechazo."""
    d = r[r.feedback == "rechazo"].pivot_table(
        index=["id","agente"], columns="ronda", values="scl_media")
    pendiente = ((d[3]-d[1])/2).unstack("agente")
    return stats.ttest_1samp((pendiente["humano"]-pendiente["ia"]).dropna(), 0).pvalue
def correr(n, s):
    sim.N_PARTICIPANTES=n; sim.N_MUJERES=int(round(n*0.54))
    sim.AGENTE_EN_RECHAZO=A; sim.AGENTE_EN_VALIDACION=A*0.43; sim.R_INTRA=0.50
    sim.rng=np.random.default_rng(s)
    p,ls=sim.generar_participantes(sim.rng); e=sim.generar_episodios(p,ls,sim.rng)
    r=sim.generar_rondas(p,e,sim.rng); r["ln_hf"]=np.log(r["hf"].clip(lower=1)); return r

REPS=100
print(f"efecto a={A}: la IA en el {(1-A/2)/(1+A/2)*100:.0f}% de la respuesta humana", flush=True)
print(f"potencia empirica, {REPS} simulaciones por celda, alfa=.05, datos sin contaminar\n", flush=True)
print(f"{'N':<7}{'H1d interaccion':<18}{'H1a agente|rechazo':<22}{'efecto principal':<18}{'H1b pendiente SCL':<18}", flush=True)
for n in (40,50,60,80,120,150,200,300):
    h1d=[];h1a=[];fb=[];h1b=[]
    for s in range(REPS):
        r=correr(n,50000+s)
        h1d.append(np.mean([p_h1d(r,v)<.05 for v in DV]))
        h1a.append(np.mean([p_h1a(r,v)<.05 for v in DV]))
        fb.append(np.mean([p_fb(r,v)<.05 for v in DV]))
        h1b.append(p_h1b(r)<.05)
    print(f"{n:<7}{np.mean(h1d):<18.2f}{np.mean(h1a):<22.2f}{np.mean(fb):<18.2f}{np.mean(h1b):<18.2f}", flush=True)
