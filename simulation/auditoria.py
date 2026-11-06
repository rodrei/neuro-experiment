"""
Audit of a simulated dataset against Annex A5 of the paper.

    python3 auditoria.py <folder with datos_crudos_*.csv>

Prints what spec section 8 asks to check: the distributions, the size of the
effects, the within-subject correlation and the deliberate contamination. It
reads only the CSVs, so it can be pointed at any version of the data.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

FOLDER = Path(sys.argv[1])
ep = pd.read_csv(FOLDER / "datos_crudos_episodios.csv")
ro = pd.read_csv(FOLDER / "datos_crudos_rondas.csv")
pa_path = FOLDER / "datos_crudos_participantes.csv"
pa = pd.read_csv(pa_path) if pa_path.exists() else None

EDA = ["scl_media", "ns_scr_n", "scr_amp_media"]
HRV = ["rr_medio", "rmssd", "sdrr", "pnn50", "hf", "lf_hf"]
SELF = ["suds_pre", "suds_post", "sam_valencia", "sam_activacion"]
ALL = EDA + HRV
SELF_SIGN = {"suds_pre": 1, "suds_post": 1, "sam_valencia": -1, "sam_activacion": 1}
# Direction of each signal under stress, to read the coupling with self-report.
STRESS_SIGN = {"scl_media": 1, "ns_scr_n": 1, "scr_amp_media": 1, "rr_medio": -1,
               "rmssd": -1, "sdrr": -1, "pnn50": -1, "hf": -1, "lf_hf": 1}


def title(text):
    print("\n" + "=" * 8 + " " + text)


def clean(df):
    """Rows without the deliberate contamination, per variable."""
    out = df.copy()
    out.loc[out.artefacto_eda, "scl_media"] = np.nan
    out.loc[out.prop_ectopicos > 0.06, ["rmssd", "sdrr", "pnn50", "hf"]] = np.nan
    return out


title("structure and counterbalancing")
print("participants", ro.id.nunique(), "| episodes", len(ep), "| rounds", len(ro))
if pa is not None:
    print("age mean %.2f (min %d, max %d) | women %d"
          % (pa.edad.mean(), pa.edad.min(), pa.edad.max(), (pa.genero == "mujer").sum()))
    print("participants per sequence", pa.secuencia.value_counts().sort_index().tolist())
pos = pd.crosstab(ep.episodio, [ep.agente, ep.feedback])
print("each condition once per position:", (pos.values == pos.values[0, 0]).mean() > 0.7,
      "\n", pos.to_string())

title("domain x condition: should be close to uniform, not confounded")
cross = pd.crosstab(ep.dominio, [ep.agente, ep.feedback])
print(cross.to_string())
chi2 = stats.chi2_contingency(cross)
print("chi2 = %.1f, p = %.3g" % (chi2[0], chi2[1]))

title("within-subject correlation (target r = 0.50), on rows without contamination")
c = clean(ro)
for v in ALL:
    d = c.dropna(subset=[v]).copy()
    d["res"] = d[v] - d.groupby(["agente", "feedback", "ronda", "episodio"])[v].transform("mean")
    groups = [g.res.values for _, g in d.groupby("id")]
    n = np.mean([len(g) for g in groups])
    msb = n * np.var([g.mean() for g in groups], ddof=1)
    msw = np.mean([g.var(ddof=1) for g in groups])
    print("  %-14s ICC = %5.2f" % (v, (msb - msw) / (msb + (n - 1) * msw)))

title("distributions, on rows without contamination")
print("  %-14s %9s %9s %9s %7s %7s %7s" % ("variable", "mean", "sd", "median", "skew", "min", "max"))
for v in ALL:
    x = c[v].dropna()
    print("  %-14s %9.2f %9.2f %9.2f %7.2f %7.2f %7.1f"
          % (v, x.mean(), x.std(), x.median(), stats.skew(x), x.min(), x.max()))
print("  values at an implausible floor:")
for v, limit in (("hf", 1), ("lf_hf", 0.05), ("rmssd", 5), ("sdrr", 10), ("pnn50", 0.01),
                 ("scr_amp_media", 0.01)):
    print("    %-14s below %-5s %5.1f%%" % (v, limit, 100 * (c[v].dropna() < limit).mean()))
print("  self-report, one value per episode:")
for v in SELF:
    x = ep[v].dropna()
    print("  %-14s %9.2f %9.2f %9.2f %7.2f %7.2f %7.1f"
          % (v, x.mean(), x.std(), x.median(), stats.skew(x), x.min(), x.max()))
print("    suds_post at 0 %.1f%%, at 10 %.1f%% | sam_valencia at 1 %.1f%%, at 9 %.1f%%"
      % (100 * (ep.suds_post.dropna() == 0).mean(), 100 * (ep.suds_post.dropna() == 10).mean(),
         100 * (ep.sam_valencia.dropna() == 1).mean(), 100 * (ep.sam_valencia.dropna() == 9).mean()))

title("effects by condition (mean over rounds, without contamination)")
cells = c.groupby(["feedback", "agente"])[ALL].mean().T
print(cells.round(2).to_string())
print("\n  AI as a share of the human response, above the validation-AI level is not")
print("  defined per variable; rejection effect relative to the variable's base:")
for v, base in (("rr_medio", 926), ("rmssd", 42), ("hf", 657)):
    h = cells.loc[v, ("rechazo", "humano")] - base
    a = cells.loc[v, ("rechazo", "ia")] - base
    print("    %-13s human %8.2f  AI %8.2f  AI/human %.2f" % (v, h, a, a / h))
self_cells = ep.groupby(["feedback", "agente"])[["suds_pre", "suds_post", "suds_cambio",
                                                 "sam_valencia", "sam_activacion"]].mean().T
print("\n  self-report by condition (per episode):")
print(self_cells.round(2).to_string())

title("SCL: drift across episodes and habituation across rounds")
print("  by episode", c.groupby("episodio").scl_media.mean().round(2).tolist())
slope = c.groupby(["feedback", "ronda"]).scl_media.mean().unstack().round(2)
print(slope.to_string())

title("gender moderation on electrodermal measures (rejection, human)")
if pa is not None:
    m = c.merge(pa[["id", "genero"]], on="id")
    sel = m[(m.feedback == "rechazo") & (m.agente == "humano")]
    print(sel.groupby("genero")[["ns_scr_n", "scr_amp_media"]].mean().round(3).to_string())

title("self-report vs physiology (target r around 0.15)")
person = c.groupby("id")[ALL].mean().join(ep.groupby("id")[SELF].mean())
print("  participant means, signed so that positive means more stress in both:")
for s in SELF:
    print("   ", s, {v: round(float((SELF_SIGN[s] * person[s]).corr(STRESS_SIGN[v] * person[v])), 2) for v in EDA + HRV})
print("  mean across pairs: %.3f" % np.mean(
    [(SELF_SIGN[s] * person[s]).corr(STRESS_SIGN[v] * person[v]) for s in SELF for v in EDA + HRV]))
print("  SUDS before with SUDS after: %.2f" % person.suds_pre.corr(person.suds_post))

title("contamination (A5.1)")
print("  missing per variable (paper: 3 to 5%):",
      {v: round(100 * ro[v].isna().mean(), 1) for v in ALL},
      {v: round(100 * ep[v].isna().mean(), 1) for v in SELF})
print("  EDA artefacts %.1f%% (parameter 5%%)" % (100 * ro.artefacto_eda.mean()))
print("  rounds with more than 6%% ectopic beats: %.1f%%" % (100 * (ro.prop_ectopicos > 0.06).mean()))
dirty_scl = ro[ro.artefacto_eda].scl_media.dropna()
print("  SCL in artefact rows: median %.1f, max %.1f (clean median %.1f)"
      % (dirty_scl.median(), dirty_scl.max(), c.scl_media.median()))
print("  rmssd median: clean %.1f, in rounds over the ectopic threshold %.1f"
      % (c.rmssd.median(), ro[ro.prop_ectopicos > 0.06].rmssd.median()))
print("  label failures %d episodes in %d participants | out of protocol %d episodes"
      % (ep.falla_etiqueta.sum(), ep[ep.falla_etiqueta].id.nunique(), ep.fuera_protocolo.sum()))

title("contrasts of the analysis plan, dirty vs without contamination (paired d)")
ro2 = ro.copy()
c2 = c.copy()
for frame in (ro2, c2):
    frame["ln_hf"] = np.log(frame.hf.clip(lower=1))
for label, frame in (("dirty", ro2), ("clean", c2)):
    print("  " + label)
    for v in ("rmssd", "rr_medio", "ln_hf", "suds_cambio", "sam_valencia"):
        source = ep if v in ("suds_cambio", "sam_valencia") else frame
        m = source.dropna(subset=[v]).groupby(["id", "agente", "feedback"])[v].mean().unstack([1, 2])
        h1a = (m[("humano", "rechazo")] - m[("ia", "rechazo")]).dropna()
        h1d = (h1a - (m[("humano", "validacion")] - m[("ia", "validacion")])).dropna()
        print("    %-13s H1a d=%6.2f p=%.4f | H1d d=%6.2f p=%.4f"
              % (v, h1a.mean() / h1a.std(), stats.ttest_1samp(h1a, 0).pvalue,
                 h1d.mean() / h1d.std(), stats.ttest_1samp(h1d, 0).pvalue))

title("episode measures")
print(ep.groupby(["feedback", "agente"])[[k for k in ep.columns if k.startswith(("autent", "mc_", "natural", "credib", "cod_"))]].mean().round(2).T.to_string())
print("  pre_malestar mean %.2f; 9 or more in %.1f%% of episodes; r with SUDS before %.3f, after %.3f"
      % (ep.pre_malestar.mean(), 100 * (ep.pre_malestar >= 9).mean(),
         ep.pre_malestar.corr(ep.suds_pre), ep.pre_malestar.corr(ep.suds_post)))
print("  columns:", list(ep.columns))
