# protocol/

The content of Study 1 as data: screen prose, scales, debate topics,
interlocutors, condition sequences, marker codes, prompts and fallback lines.

**This folder is the source of truth.** `common/protocol.py` reads it, and
through it both implementations consume it: the web (`web/`) and the desktop
(`desktop/`). A wording fix here reaches both without copying anything.
Values are Argentine Spanish; keys are English.

| File | What it holds | Used by |
| --- | --- | --- |
| `texts.json` | Consent, rest, instructions, interlocutor intros and labels, topic pick, pinned card, pause, debriefing, closing | web (desktop reads the `desktop_*` entries, `cover_story*`, `agent_name`, `agent_label`, `manipulation_check`, `connecting`, `rest*`, `closing`) |
| `scales.json` | SUDS, SAM (valence, arousal), authenticity (3 items) and the PANAS anchors | both |
| `parameters.json` | Real and demo timings, the latency formula, `min_opinion_chars` (web), `min_situation_chars` (desktop), test fillers | both |
| `markers.json` | The 22 event codes | both (`situation_revealed`, `agent_asks_situation`, `manipulation_check` are desktop-only) |
| `prompts.json` | Model parameters; `debate` rules and roles (web); `situation` rules and roles (desktop) | both |
| `topics.json` | The eight debate questions: `id`, `category`, `question` | web |
| `interlocutors.json` | Four names with `type` `human` or `ai`, in assignment order | web |
| `sequences.json` | The 4×4 Williams Latin square over the four conditions | web |
| `fallback.csv` | Three generic lines per feedback type, shown when an LLM turn fails | web |
| `scripts.csv` | Greeting, greeting2 and three scripted turns per feedback type | desktop |
| `panas.csv` | The 20 PANAS items with their subscale | both |
| `sam/` | Optional PNGs for the pictorial SAM (auto-detected by the desktop) | desktop |

## When editing

- **Run the tests afterwards:** `python3 -m unittest discover -s common -t . -v`.
  They check the sequences are a Latin square, ids are unique, every
  placeholder the code fills is present, ticks and labels match, and the
  desktop scripts stay balanced in length.
- Prompt templates use `{name}`, `{question}`, `{role}`, `{max_chars}`
  (`debate`) and `{name}`, `{role}`, `{max_chars}`, `{examples}`
  (`situation`); intros and labels use `{name}`; the pinned card hint uses
  `{n}`.
- Topics should be questions people hold strong views on; the participant
  picks one per episode from the ones not yet used, so keep at least eight.
- The desktop-only entries go away when the desktop is migrated to the
  debate design.
