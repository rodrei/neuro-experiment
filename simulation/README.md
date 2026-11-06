# simulation/

Working copy of the simulated data for the paper's Results. **Elena's originals in
the Drive folder `entrega final/simulacion` are untouched.** Before any change,
this copy reproduced her `datos_crudos_episodios.csv` and `datos_crudos_rondas.csv`
exactly (600 and 1,800 rows, every column), so every difference below comes from
the changes listed here.

The scripts keep Elena's Spanish names and comments, so they can be diffed against
hers and audited against Annex A5.

```bash
python3 -m venv venv && venv/bin/pip install numpy pandas scipy openpyxl
venv/bin/python 01_simular.py            # writes datos/, seed 20261103, reproducible
venv/bin/python -m unittest test_simular # what the data must satisfy
venv/bin/python auditoria.py datos       # the checks of spec section 8
venv/bin/python 00_potencia.py           # the power table; output in salida_potencia.txt
```

## What was wrong and what changed

| # | Problem in the original | Measured | Fix | Now |
|---|---|---|---|---|
| 1 | **H1b had no effect to find.** Attenuated habituation applied to all rejection, whatever the agent, so human and AI rejection had the same slope | Slope −0.17 vs −0.17, p = .59 | Attenuation splits between agents like the other effects (A5.2): 0.74 human, 0.36 AI | Effect in the generator (see power below) |
| 2 | **Domain fully confounded with condition.** Both squares used the same row offset, so each condition always got the same domain | χ² = 1800: every domain in one condition | Independent square, crossed by `(i // 4) % 4`, same as the web | χ² = 1.2, p = .999 |
| 3 | **Impossible HRV values.** Normal intercepts pushed means below zero, then clamped to 1e-6 | HF under 1 ms² in 15.8% of rows; LF/HF up to 374; LF/HF ICC .02 | Positive measures use a log-normal person factor, proportional effects and a constant coefficient of variation; same means and SDs as A5.5 | 0%; LF/HF max 30; ICC .49 |
| 4 | **Within-subject correlation missing on SCR count**, because a Poisson's variance is fixed by λ | ICC .10 (target .50) | Person factor sized for R_INTRA given λ | ICC .36 |
| 5 | **Self-report/physiology coupling not implemented.** The common factor only reached PANAS and SUDS | Mean r = .03 (target about .15) | Correlated person intercepts, signed by each measure's direction under stress | Mean r = .13 |
| 6 | **SCL had a level effect** by construction, against the paper's slope-only claim: the slope was anchored at round 1 | Rejection vs validation +0.33 µS, p = .0009 | Slope centred on the middle round | +0.04 µS, p = .70 |
| 7 | **A quarter of the rounds counted as ectopic.** `PROP_ECTOPICOS = 0.06` was a threshold on a Beta with mean 4.4% | 25.2% of rounds, with HRV × 1.6–3.2 | Beta(1.3, 54): 6% of rounds exceed the 6% threshold | 5.9% |
| 8 | **The covariate predicted nothing**, though A6 counts on it to reduce residual variance | r(pre-rating, SUDS) = .01 | New `R_PRE_AUTOINFORME = 0.30`, inside the residual so the SDs do not change | r = .31 |
| 9 | **Section 2.5's measures were missing:** naturalness, 0–100 credibility, suspicion, message length, accumulated wait, fallback turns. `etiqueta_reportada` belonged to the old check | Not in the data | Added. `falla_etiqueta` now applies the paper's criterion: conviction on the opposite side of the label | 46 episodes in 35 participants flagged; 43 report suspicion |
| 10 | Mean age truncated by `int()` against the reported 25 | 24.44 | Rounded | 24.61 |

Values changed throughout, because several fixes change how many random draws are
used. The seed is the same. **Nothing was tuned to make a contrast significant:**
no seed was tried other than Elena's.

## Power at the design's N = 150

`salida_potencia.txt`, same 100 runs per cell and seeds as Annex A6, plus an H1b column.

| N | H1d interaction | H1a | Main effect | H1b SCL slope |
|---|---|---|---|---|
| 40 | .41 | .75 | .80 | .08 |
| 50 | .42 | .82 | .88 | .08 |
| 60 | .53 | .86 | .94 | .10 |
| 80 | .59 | .95 | .97 | .11 |
| 120 | .76 | .98 | 1.00 | .15 |
| **150** | **.83** | **.99** | **1.00** | **.19** |
| 200 | .88 | 1.00 | 1.00 | .24 |
| 300 | .97 | 1.00 | 1.00 | .27 |

## What the paper has to change

Annex A5.5 says its middle column must match the script.

- **A5.5, SUDS:** the table says effect +1,8; the script has always used +1,16 (ES 0,77 × 1,50). Use +1,16.
- **A5.5, SCL slope:** the table says −0,04 µS per epoch; the script uses −0,40 µS per round. Use the latter.
- **A5.5, SCR amplitude:** the table says median 0,35; it is the mean.
- **A5.5, new rows:** `R_PRE_AUTOINFORME`, the credibility and naturalness means, the suspicion rate and the agent message length. All are assumptions; the suspicion rate comes from Kelly et al. and the message length from a handful of pilot conversations with the Annex A2 prompt.
- **A5.2:** say that effects grow across the episode (`rampa = r / 3`), so the mean over rounds is two thirds of the stated fraction. This was never documented.
- **A6 table and §1:** replace with the table above. H1d goes from .86 to .83 and H1a from 1.00 to .99. The .80 threshold is now reached between 120 and 150, not at 120.
- **§1:** delete the second of the two power paragraphs stuck together in that section.
- **Pendientes §4:** it says the calibration ran on dirty data and effects will rise after cleaning. `00_potencia.py` never calls `ensuciar`, so the power table is already on clean data and will not rise.

## Decisions that are Elena's

1. **H1b is badly underpowered: .19 at N = 150.** Round-to-round SCL noise (within-person SD about 1.8 µS, from R_INTRA = .50 and SD 2.5) swamps a slope difference of 0.15 µS per round. As generated, H1b will usually not reach significance, and in this dataset it does not (p = .30). A tonic signal is far more stable within a session than R_INTRA = .50 implies, so a higher within-subject correlation for SCL could be argued, but that is a new assumption and I did not make it. Either way, A6 should stop being silent on H1b.
2. **Self-report is generated per round, but the experiment measures it per episode.** The procedure (2.4) gives PANAS and SUDS after each episode, yet the data, the trajectory figure planned for PANAS and §5 treat them as per round. Either the procedure gains per-round items or the self-report data becomes per episode.
3. **By chance, this dataset shows a level difference H1b predicts against:** human vs AI SCL under rejection, +0.32 µS, p = .035, though the generator has no such effect. It is about the false-positive rate to expect and is reported here rather than removed by changing the seed.
4. **The experiment's condition square differs from the simulation's.** The web uses a Williams square, which balances carryover; the simulation keeps Elena's cyclic one. Both satisfy what the paper states.
