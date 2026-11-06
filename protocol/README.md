# protocol/

The content of Study 1 as data: screen prose, scales, domains, condition
sequences, marker codes, the prompt and the fallback lines.

**This folder is the source of truth.** `common/protocol.py` reads it, and the
web (`web/`) consumes it through there. Values are Argentine Spanish; keys are
English.

| File | What it holds |
| --- | --- |
| `texts.json` | Consent, rest, elicitation, distress alert, instructions, agent announcements and header labels, chat lines, pause, final block, debriefing, data use, closing, demo notice |
| `scales.json` | SUDS, SAM (valence, arousal), authenticity (3 items), manipulation checks (4 items), naturalness, the 0–10 situation rating, the 0–100 credibility scale, the AI companion use items and the PANAS anchors |
| `instruments.json` | UCLA-3 and ECR. `items` stays empty until the wording of the validated Spanish versions is available, and then needs `n_items` entries of `{key, item}` plus `instruction`, `ticks` and `anchors` |
| `parameters.json` | Real and demo timings, the latency formula, rounds per episode, the distress threshold, the test filler |
| `markers.json` | The event codes |
| `prompts.json` | Model parameters, the rules template and one task paragraph per feedback type (Annex A2 of the paper) |
| `domains.json` | The four situation domains, in elicitation order |
| `sequences.json` | The 4×4 Williams Latin square over the four conditions |
| `domain_sequences.json` | The 4×4 Latin square assigning a domain to each condition, independent of `sequences.json` |
| `fallback.csv` | Three lines per feedback type, shown when an LLM turn fails. They are also the prompt's style examples |
| `panas.csv` | The 20 PANAS items with their subscale |

## When editing

- **Run the tests afterwards:** `python3 -m unittest discover -s common -t . -v`.
  They check both squares, the wording the specification fixes, that ticks and
  labels match, that the prompt mentions nothing about how the agent is
  presented, and that the fallback lines stay balanced in length.
- The prompt template uses `{role}`, `{max_chars}` and `{examples}`. The texts
  that mention a domain use `{domain}`, and the label fits after «relacionada
  con», «que tiene que ver con» and «sobre». `instrument_pending` uses `{title}`
  and `{n}`.
- **Never put the agent type in the prompt.** In this app the model answers both
  agent conditions, and its content has to be the same in each.
- The debriefing describes the study as designed, with a person in the human
  condition. Only the `demo` notes say that the model answers every conversation,
  or, for a demo started without a valid access code, that the replies are fixed.
