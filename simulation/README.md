# simulation/

The simulated data behind the paper's Results, generated from the effect structure of
Annex A3 and sized by the power analysis of Annex A4. Independent of the rest of the
repo, with its own dependencies. The scripts keep Spanish names and comments, as in
the group's original scripts on Drive.

**For the team, in Spanish and without assuming Python or methodology: [LEEME.md](LEEME.md).**

```bash
python3 -m venv venv && venv/bin/pip install numpy pandas scipy openpyxl
venv/bin/python 01_simular.py                              # writes datos/, seed 20261103
venv/bin/python -m unittest test_simular                   # what the data must satisfy (~90 s)
venv/bin/python auditoria.py datos                         # descriptive audit of the CSVs
venv/bin/python 00_calibrar_pendiente.py > salida_calibracion.txt   # SCL slope vs Kelly et al.
venv/bin/python 00_potencia.py > salida_potencia.txt       # power table (~10 min)
```

| File | What it does |
|---|---|
| `01_simular.py` | The generator. Parameters at the top, one per row of table A3.5 |
| `00_calibrar_pendiente.py` | Solves for `HABITUACION_SCL_EPOCA`, the slope that reproduces Kelly et al.'s d_z = .449 |
| `00_potencia.py` | Empirical power by N for the feedback main effect, H1a, H1d and H1b |
| `auditoria.py` | Reads only the CSVs and prints distributions, effects and contamination |
| `test_simular.py` | Checks the generator against the paper, including that both Latin squares match `protocol/` |

Output in `datos/`: `datos_crudos_{participantes,episodios,rondas,epocas}.csv` and
the same tables plus the parameters in `datos_crudos.xlsx`.

The group's analysis notebook (`entrega final/simulacion/AI_companions_analisis.ipynb`
on Drive) downloads `01_simular.py` from GitHub pinned to a commit and reads the
columns by name. Renaming a column or changing a public function's signature
(`generar_participantes`, `generar_episodios`, `generar_rondas`, `ensuciar`,
`ensuciar_epocas`, `agregar_medidas_post`, `agregar_autoinforme`, `pendiente_kelly`)
breaks it; after a change, the commit it pins has to move.

Changing `RHO_EPOCA`, `N_EPOCAS`, `ELEVACION_TAREA` or the SCL noise requires running
`00_calibrar_pendiente.py` again and copying its value into `HABITUACION_SCL_EPOCA`.
