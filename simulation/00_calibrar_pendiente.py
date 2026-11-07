"""Despeja la pendiente de habituacion del SCL que reproduce el tamano de efecto de
Kelly et al. (2012), analizada como ellos la analizan.

Kelly no reporta la pendiente en uS: reporta F(1,40) = 8,25 para la interaccion
tiempo x condicion (ostracismo contra inclusion), que equivale a d_z = 0,449. Aca se
busca la pendiente en validacion (HABITUACION_SCL_EPOCA, uS por epoca) con la que el
efecto de retroalimentacion sobre la pendiente da ese mismo d_z, con N = 200.

El d_z crece en proporcion a la pendiente, asi que alcanza con medirlo una vez,
reescalar y repetir para corregir el resto. Se calibra para cada autocorrelacion
explorada: la pendiente en uS depende de ella, el d_z no.

    python3 00_calibrar_pendiente.py > salida_calibracion.txt
"""
import importlib.util
from pathlib import Path

import numpy as np
from scipy import stats

spec = importlib.util.spec_from_file_location("sim", Path(__file__).with_name("01_simular.py"))
sim = importlib.util.module_from_spec(spec); spec.loader.exec_module(sim)

N = 200
REPS_AJUSTE = 60
REPS_VERIFICACION = 200


def contrastes(semilla, habituacion, rho):
    """Efecto de retroalimentacion y H1b sobre la pendiente, uno por participante."""
    sim.N_PARTICIPANTES = N; sim.N_MUJERES = int(round(N * 0.54))
    rng = np.random.default_rng(semilla)
    p = sim.generar_participantes(rng)
    e = sim.generar_episodios(p, rng)
    z = dict(zip(p.id, rng.normal(0, 1, len(p))))
    pend = sim.pendiente_kelly(sim.generar_epocas(e, z, rng, habituacion, rho))
    c = pend.pivot_table(index="id", columns=["agente", "feedback"], values="pendiente")
    retro = ((c[("humano", "rechazo")] + c[("ia", "rechazo")])
             - (c[("humano", "validacion")] + c[("ia", "validacion")])) / 2
    h1b = c[("humano", "rechazo")] - c[("ia", "rechazo")]
    return retro.dropna(), h1b.dropna()


def dz(x):
    return float(x.mean() / x.std(ddof=1))


def calibrar(rho):
    hab = -0.10
    for vuelta in range(2):
        medido = np.mean([dz(contrastes(80000 + 1000 * vuelta + s, hab, rho)[0])
                          for s in range(REPS_AJUSTE)])
        hab *= sim.KELLY_DZ / medido
    return hab


print(f"Objetivo: d_z = {sim.KELLY_DZ} en el efecto de retroalimentacion sobre la pendiente")
print(f"N = {N}, ventana de {sim.N_EPOCAS} epocas de 10 s\n")
print(f"{'rho':<7}{'pendiente uS/epoca':<21}{'d_z retroalimentacion':<24}{'d_z H1b':<10}{'potencia H1b':<14}")
for rho in (0.80, 0.90, 0.95):
    hab = calibrar(rho)
    d_retro, d_h1b, signif = [], [], []
    for s in range(REPS_VERIFICACION):
        retro, h1b = contrastes(90000 + s, hab, rho)
        d_retro.append(dz(retro)); d_h1b.append(dz(h1b))
        signif.append(stats.ttest_1samp(h1b, 0).pvalue < .05)
    marca = "   <- RHO_EPOCA del generador" if rho == sim.RHO_EPOCA else ""
    print(f"{rho:<7.2f}{hab:<21.4f}{np.mean(d_retro):<24.3f}{np.mean(d_h1b):<10.3f}"
          f"{np.mean(signif):<14.2f}{marca}", flush=True)

# Lo que se sigue sin simular: H1b reparte la atenuacion entre agentes con
# AGENTE_EN_RECHAZO, y su contraste tiene el doble de varianza que el de
# retroalimentacion (diferencia de dos celdas contra media de dos diferencias).
a = sim.AGENTE_EN_RECHAZO
d_esperado = sim.KELLY_DZ * a / np.sqrt(2)
print(f"\nd_z de H1b que se sigue de la calibracion: {sim.KELLY_DZ} x {a} / raiz(2) = {d_esperado:.3f}")
for n in (150, 200):
    ncp, crit = d_esperado * np.sqrt(n), stats.t.ppf(.975, n - 1)
    potencia = 1 - stats.nct.cdf(crit, n - 1, ncp) + stats.nct.cdf(-crit, n - 1, ncp)
    print(f"  potencia de una t pareada con N = {n}: {potencia:.2f}")

# Cuanta incertidumbre trae el d_z de Kelly, estimado con 41 personas.
t_kelly, gl = np.sqrt(8.25), 40
bajo = next(d for d in np.arange(0, 1, 0.001)
            if stats.nct.cdf(t_kelly, gl, d * np.sqrt(41)) < 0.975)
alto = next(d for d in np.arange(0, 2, 0.001)
            if stats.nct.cdf(t_kelly, gl, d * np.sqrt(41)) < 0.025)
print(f"\nIC 95 % del d_z de Kelly (N = 41): [{bajo:.2f}, {alto:.2f}]")
