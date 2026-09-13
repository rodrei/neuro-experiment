# Phase 1 Debate Design Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the repo to English, then make the web version run the 2×2 within-subject debate design (four LLM episodes, participant-chosen topics, no deception) with visible LLM failures and centred screens, verified in a real browser and deployed to fly.io.

**Architecture:** Three layers stay as they are — `protocol/` (content as data) ← `common/` (stdlib Python: loader, LLM agent, CSV writer) ← `desktop/` (PsychoPy, unchanged behaviour) and `web/` (stdlib HTTP server + jsPsych front end). The rename is one mechanical commit before any behaviour change. New content lands in `protocol/` with loader functions and tests; the server grows `/api/health` and a richer `/api/turn`; the jsPsych timeline is rewritten around four episodes.

**Tech Stack:** Python 3.11 stdlib only (`http.server`, `urllib`, `unittest`), jsPsych 8.3 (vendored), Playwright 1.62 (global install, for manual e2e), fly.io.

**Spec:** `docs/superpowers/specs/2026-09-12-phase1-debate-design.md`

## Global Constraints

- No new Python dependencies: stdlib only, in `common/` and `web/server/`.
- Participant-facing text is Argentine Spanish (voseo); everything else — identifiers, comments, docstrings, JSON keys, CSV headers, developer docs, commit messages — is English.
- The design doc `docs/Pre-entrega #3 — Diseño experimental.md` and the existing `docs/superpowers/*` files are not touched.
- The desktop (`desktop/`) keeps its current two-episode behaviour; it must still `py_compile` with PsychoPy's Python after the rename and keep reading the protocol entries listed in spec §3.9.
- The agent latency formula (`latency_base + latency_per_char × chars`, capped at `latency_max`) is unchanged.
- Test commands: `python3 -m unittest discover -s common -t . -v`, `python3 -m unittest discover -s web -t . -v`, and for the desktop `PYTHONHOME=/Applications/PsychoPy.app/Contents/Resources PYTHONPATH=/Applications/PsychoPy.app/Contents/Resources/lib/python3.11 /Applications/PsychoPy.app/Contents/MacOS/python -m py_compile desktop/*.py`.
- Commit after every task with the attribution trailer from the session.

---

## File structure after the work

```
protocol/                 texts.json scales.json parameters.json markers.json prompts.json
                          sequences.json interlocutors.json topics.json
                          scripts.csv (desktop) fallback.csv (web) panas.csv README.md
common/                   __init__.py protocol.py llm_agent.py output.py
                          test_protocol.py test_llm_agent.py test_output.py
desktop/                  study1.py chat.py scales.py markers.py config.py
web/                      index.html README.md __init__.py test_server.py
web/server/               __init__.py app.py
web/js/                   protocol.js scales.js chat-plugin.js experiment.js
web/static/               styles.css vendor/
web/e2e/                  run_flow.mjs
data/  screenshots/  docs/  Dockerfile  fly.toml  README.md  CLAUDE.md  AGENTS.md
```

---

### Task 1: Rename `protocol/` and `common/` to English

**Files:**
- Rename: `protocolo/` → `protocol/`; `comun/` → `common/`; `protocolo/textos.json` → `protocol/texts.json`, `escalas.json` → `scales.json`, `parametros.json` → `parameters.json`, `marcadores.json` → `markers.json`, `guiones.csv` → `scripts.csv`; `comun/protocolo.py` → `common/protocol.py`, `agente_llm.py` → `llm_agent.py`, `salida.py` → `output.py`, `test_protocolo.py` → `test_protocol.py`, `test_agente_llm.py` → `test_llm_agent.py`, `test_salida.py` → `test_output.py`.
- Modify: every file above (keys, identifiers, comments, docstrings).

**Interfaces:**
- Produces `common/protocol.py`: `texts()`, `debriefing(agent)` (desktop; `agent` in `("scripted","llm")`), `scales()`, `markers()`, `prompts()`, `parameters(mode="real")`, `scripts()` → `{feedback: {turn: text}}`, `panas()`, `everything()`; constants `MODES`, `AGENTS`.
- Produces `common/llm_agent.py`: `FEEDBACK_TYPES = ("validation","rejection")`, `LLMAgent(feedback, transport=None, timeout=None)` with `.greet(text)`, `.hear(text)`, `.reply(fallback_line)` → `(text, origin)`, `.reply_in_thread(fallback_line)` → `PendingReply` (`.ready()`, `.result()`); `clean_reply(text, max_chars)`, `load_api_key(folder=ROOT)`, `NO_REPLY_MARK = "(no responde)"`, `OPENROUTER_URL`, `DEFAULT_TIMEOUT`.
- Produces `common/output.py`: `EVENT_FIELDS = ["t_experiment_s","t_unix","code","label","detail"]`, `CHAT_FIELDS = ["author","text","origin","t_experiment_s","latency_s"]`, `base_name(participant_id, tag, stamp)` → `"S1_<id>_<tag>_<stamp>"`, `write_responses`, `write_behavioral`, `write_chat`, `write_events`, `write_all(folder, base, responses, behavioral, chat, events=None)` → paths with suffixes `_responses.csv`, `_behavioral.csv`, `_chat.csv`, `_events.csv`.

Glossary for JSON keys (apply in `protocol/*.json` and everywhere they are read):

| Spanish | English |
| --- | --- |
| `nombre_agente` | `agent_name` |
| `conectando` | `connecting` |
| `etiqueta_agente.humano/ia` | `agent_label.human/ai` |
| `cobertura`, `cobertura_titulo` | `cover_story`, `cover_story_title` |
| `consentimiento.titulo/cuerpo` | `consent.title/body` |
| `reposo`, `reposo_leyenda` | `rest`, `rest_caption` |
| `pausa` | `pause` |
| `debriefing.cuerpo.guionado/llm` | `debriefing.body.scripted/llm` |
| `cierre.cuerpo/pie` | `closing.body/footer` |
| `chequeo.creencia_persona_real` | `manipulation_check.believed_real_person` |
| `chequeo.sospecha_1..3` | `manipulation_check.suspicion_1..3` |
| `chequeo.consiente_tras_debriefing` | `manipulation_check.consents_after_debriefing` |
| `enunciado`, `ticks`, `etiquetas`, `imagenes` | `prompt`, `ticks`, `labels`, `images` |
| `sam_valencia` | `sam_valence` |
| `autenticidad.items[].clave/enunciado/inverso` | `authenticity.items[].key/prompt/reverse`; keys `aut1..aut3` → `auth_1..auth_3`, `aut4_inv` → `auth_4_rev` |
| `panas.consigna/anclas/items_por_pagina` | `panas.instruction/anchors/items_per_page` |
| `parametros.real/demo/comun` | `real/demo/common` |
| `dur_baseline`, `dur_conectando`, `ventana_respuesta_libre`, `timeout_situacion` | `baseline_duration`, `connecting_duration`, `free_reply_window`, `situation_timeout` |
| `latencia_base`, `latencia_por_caracter`, `latencia_max`, `dur_lectura_min` | `latency_base`, `latency_per_char`, `latency_max`, `min_reading_time` |
| `min_caracteres_situacion`, `texto_relleno_test` | `min_situation_chars`, `test_filler_text` |
| markers | `experiment_start`, `baseline_start`, `baseline_end`, `situation_revealed`, `agent_asks_situation`, `episode_start`, `agent_message_1..3`, `participant_message`, `free_reply_start`, `episode_end`, `measures_start`, `measures_end`, `panas_start`, `panas_end`, `manipulation_check`, `experiment_end` |
| `prompts.modelo/temperatura/max_tokens/max_caracteres/rol/reglas` | `model/temperature/max_tokens/max_chars/role/rules`; role keys `validacion/rechazo` → `validation/rejection`; placeholders `{nombre}` → `{name}`, `{rol}` → `{role}`, `{maximo}` → `{max_chars}`, `{ejemplos}` → `{examples}` |
| `guiones.csv` columns `tipo,turno,texto`; rows `saludo,saludo2,validacion,rechazo` | `scripts.csv` columns `feedback,turn,text`; rows `greeting,greeting2,validation,rejection` |
| `panas.csv` columns `n,clave,item,subescala` | `n,key,item,subscale`; keys `pa_interesado`→`pa_interested`, `na_angustiado`→`na_distressed`, `pa_emocionado`→`pa_excited`, `na_alterado`→`na_upset`, and the remaining 16 translated the same way (Watson et al. item names) |

- [ ] **Step 1: Move files with git so history follows**

```bash
git mv protocolo protocol && git mv comun common
git mv protocol/textos.json protocol/texts.json
git mv protocol/escalas.json protocol/scales.json
git mv protocol/parametros.json protocol/parameters.json
git mv protocol/marcadores.json protocol/markers.json
git mv protocol/guiones.csv protocol/scripts.csv
git mv common/protocolo.py common/protocol.py
git mv common/agente_llm.py common/llm_agent.py
git mv common/salida.py common/output.py
git mv common/test_protocolo.py common/test_protocol.py
git mv common/test_agente_llm.py common/test_llm_agent.py
git mv common/test_salida.py common/test_output.py
```

- [ ] **Step 2: Rewrite the JSON/CSV files with the English keys** (values unchanged, still Spanish). Check with `python3 -c "import json,glob; [json.load(open(f)) for f in glob.glob('protocol/*.json')]"`.

- [ ] **Step 3: Translate `common/protocol.py`, `common/llm_agent.py`, `common/output.py`** — identifiers per the Interfaces block, comments and docstrings in English, folder constant `PROTOCOL_DIR = os.path.join(ROOT, "protocol")`.

- [ ] **Step 4: Translate the three test modules** (test names, fixtures, expected keys). Run: `python3 -m unittest discover -s common -t . -v` — Expected: all pass.

- [ ] **Step 5: Commit** — `git commit -m "Rename protocol/ and common/ to English"`.

---

### Task 2: Rename `desktop/` and keep it compiling

**Files:**
- Rename: `escritorio/` → `desktop/`; `estudio1.py` → `study1.py`, `escalas.py` → `scales.py`, `marcadores.py` → `markers.py`; `capturas/` → `screenshots/`; `datos/` → `data/` (gitignored; also rename the local folder).
- Modify: `desktop/*.py` (imports `from common import protocol, llm_agent, output`; all identifiers, `config.py` constants such as `MODO_DEMO` → `DEMO_MODE`, `MODO_TEST` → `TEST_MODE`, `TECLA_SALTO` → `SKIP_KEY`, `AGENTE` → `AGENT`, `TIMEOUT_LLM` → `LLM_TIMEOUT`, `BACKEND_MARCADORES` → `MARKER_BACKEND`, `FUENTE` → `FONT`, `PANTALLA_COMPLETA` → `FULLSCREEN`, `TAMANO_VENTANA` → `WINDOW_SIZE`, `COLORES` → `COLORS`); `.gitignore` (`data/`); `.dockerignore` (`desktop/`, `screenshots/`, `data/`).

**Interfaces:**
- Consumes Task 1's `common` API.
- Produces nothing other code depends on.

- [ ] **Step 1: `git mv` the directory and files; `mv datos data`; update `.gitignore` and `.dockerignore`.**
- [ ] **Step 2: Translate the five modules.** The `sys.path` insertion of the repo root stays. The four output files keep the desktop prefix `S1_<id>_<condition>_<stamp>` via `output.base_name`.
- [ ] **Step 3: Compile with PsychoPy's Python** (command in Global Constraints). Expected: no output, exit 0. Also `python3 -m py_compile desktop/*.py`.
- [ ] **Step 4: Run the common tests again** (the desktop imports nothing they don't cover, but the rename of `data/` must not break `output` tests).
- [ ] **Step 5: Commit** — `git commit -m "Rename desktop/ to English"`.

---

### Task 3: Rename `web/` to English

**Files:**
- Rename: `web/servidor/` → `web/server/`; `web/test_servidor.py` → `web/test_server.py`; `web/js/protocolo.js` → `protocol.js`, `escalas.js` → `scales.js`, `experimento.js` → `experiment.js`; `web/static/estilos.css` → `styles.css`.
- Modify: `web/server/app.py` (env vars `ACCESS_CODE`, `DATA_DIR`, `PORT`, `LLM_TIMEOUT`, `RATE_LIMIT_PER_MINUTE`; routes `/api/health`, `/api/protocol`, `/api/turn`, `/api/data`; handler names `Handler`, `Server`, `create_server(port=0, data_dir=None)`, module globals `TRANSPORT`, `ACCESS_CODE`, `DATA_DIR`), `web/index.html` (element ids `start`, `form`, `begin`, `load-status`, `skip`, `mobile-notice`; field names `participant_id`, `age`, `sex`, `agent_condition`, `order`, `agent`, `access_code`, `test_mode`; script/css paths), the four JS files (identifiers, CSS class names `screen-title`, `screen-body`, `prompt`, `fixation-cross`, `rest-caption`, `chat`, `chat-bar`, `chat-name`, `chat-status`, `chat-messages`, `bubble agent|participant`, `chat-input`, `chat-help`; `window.PROTOCOL`; jsPsych plugin `jsPsychChatEpisode` with info name `chat-episode`; data keys `episode`, `feedback`, `situation`…), `web/test_server.py`, `Dockerfile` (`COPY protocol/ common/ web/`, `ENV PORT DATA_DIR`, `CMD python -m web.server.app`), `fly.toml` (`[env] PORT DATA_DIR`, mount `source = "datos"` stays — the volume name on fly is fixed — `destination = "/data"`).

**Interfaces:**
- Produces `web/server/app.py`: `create_server(port=0, data_dir=None)`, module attributes `ACCESS_CODE`, `TRANSPORT`, `DATA_DIR`, `LLM_TIMEOUT`.
- Produces JS: `loadProtocol()`, `parameters()`, `texts()`, `scriptLine(feedback, turn)`, `textScreen(title, body, buttonLabel)`, `sliderScale(spec, key)`, `panasTrials(moment)`, `measuresBlock(moment, includeAuthenticity, mark)`, `valueOrNull(v)`, `collectMeasures(jsPsych, moment)`, `runExperiment()`, `enableTestMode(jsPsych)`, `submit(jsPsych, events)`.

- [ ] **Step 1: `git mv` files; translate `app.py` and `test_server.py`.** Run `python3 -m unittest discover -s web -t . -v` — Expected: all pass (the tests assert the new route names, env names, `S1_07_ai_` prefix, `platform,web`).
- [ ] **Step 2: Translate `index.html`, the four JS files and `styles.css`.** Behaviour identical to before (still two episodes, still cover story — that changes in Task 7).
- [ ] **Step 3: Smoke run**: `PORT=8765 python3 -m web.server.app &` then `curl -s localhost:8765/api/protocol | python3 -c "import json,sys; d=json.load(sys.stdin); print(sorted(d))"` — Expected: `['markers', 'panas', 'parameters', 'prompts', 'scales', 'scripts', 'texts']`; `curl -s localhost:8765/ | grep -c "js/experiment.js"` → 1. Kill the server.
- [ ] **Step 4: Update `Dockerfile`, `fly.toml`, `.dockerignore`.**
- [ ] **Step 5: Commit** — `git commit -m "Rename web/ to English"`.

---

### Task 4: Developer docs in English

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `AGENTS.md` (add to git; same content as CLAUDE.md with the Codex header), `protocol/README.md`, `web/README.md`.

- [ ] **Step 1: Rewrite each doc in English** describing the *current* state after Task 3 (paths, commands, env vars, routes). `CLAUDE.md`'s language rule becomes: "Code, comments, JSON keys, CSV headers, developer docs and commit messages are in English. Participant-facing text (protocol JSON values, `scripts.csv`, `fallback.csv`, `panas.csv`) is Argentine Spanish (voseo). The design doc in `docs/` is Spanish." Sections about the design (invariants, PANAS slider trap, pending items) are kept, translated.
- [ ] **Step 2: Commit** — `git commit -m "Developer docs in English"`.

---

### Task 5: Protocol content for the debate design + loader

**Files:**
- Create: `protocol/sequences.json`, `protocol/interlocutors.json`, `protocol/topics.json`, `protocol/fallback.csv`.
- Modify: `protocol/texts.json` (new screens per spec §2; `debriefing` becomes `{title, body}` single string for the web; the desktop's two versions move to `desktop_debriefing: {title, body: {scripted, llm}}`), `protocol/scales.json` (authenticity: 3 items, no reverse), `protocol/prompts.json` (`debate` and `situation` blocks), `protocol/markers.json` (+4), `protocol/parameters.json` (`min_opinion_chars: 120`, `test_filler_opinion`), `common/protocol.py`, `common/test_protocol.py`, `desktop/study1.py` and `desktop/scales.py` (read `desktop_debriefing`, `prompts.situation`, 3 authenticity items).
- Test: `common/test_protocol.py`.

**Interfaces:**
- Produces in `common/protocol.py`: `CONDITIONS = ("human_validation","human_rejection","ai_validation","ai_rejection")`, `sequences()` → `{ "1": [cond×4], … "4": […] }`, `interlocutors()` → `[{"name","type"}×4]`, `topics()` → `[{"id","category","question"}×8]`, `fallback_lines()` → `{feedback: {turn: text}}`, `split_condition(cond)` → `(agent_type, feedback)`, `desktop_debriefing(agent)`; `everything()` gains keys `sequences`, `interlocutors`, `topics`, `fallback`.

- [ ] **Step 1: Write the failing tests**

```python
class TestSequences(unittest.TestCase):
    def test_four_sequences_of_four(self):
        seqs = protocol.sequences()
        self.assertEqual(sorted(seqs), ["1", "2", "3", "4"])
        for s in seqs.values():
            self.assertEqual(sorted(s), sorted(protocol.CONDITIONS))

    def test_is_a_latin_square(self):
        seqs = protocol.sequences()
        for position in range(4):
            column = [seqs[k][position] for k in sorted(seqs)]
            self.assertEqual(sorted(column), sorted(protocol.CONDITIONS))

    def test_split_condition(self):
        self.assertEqual(protocol.split_condition("ai_rejection"), ("ai", "rejection"))
        with self.assertRaises(ValueError):
            protocol.split_condition("robot_love")


class TestInterlocutors(unittest.TestCase):
    def test_two_per_type_with_distinct_names(self):
        people = protocol.interlocutors()
        self.assertEqual(len(people), 4)
        self.assertEqual(len({p["name"] for p in people}), 4)
        self.assertEqual(sum(p["type"] == "human" for p in people), 2)
        self.assertEqual(sum(p["type"] == "ai" for p in people), 2)


class TestTopics(unittest.TestCase):
    def test_eight_topics_with_unique_ids_and_questions(self):
        topics = protocol.topics()
        self.assertEqual(len(topics), 8)
        self.assertEqual(len({t["id"] for t in topics}), 8)
        for t in topics:
            self.assertTrue(t["question"].endswith("?"))
            self.assertTrue(t["category"])


class TestFallbackLines(unittest.TestCase):
    def test_three_per_feedback(self):
        lines = protocol.fallback_lines()
        self.assertEqual(set(lines), {"validation", "rejection"})
        for feedback in lines:
            self.assertEqual(sorted(lines[feedback]), [1, 2, 3])


class TestDebatePrompts(unittest.TestCase):
    def test_debate_rules_have_the_placeholders(self):
        rules = protocol.prompts()["debate"]["rules"]
        for ph in ("{name}", "{question}", "{role}", "{max_chars}"):
            self.assertIn(ph, rules)
        self.assertEqual(set(protocol.prompts()["debate"]["role"]),
                         {"validation", "rejection"})

    def test_situation_prompts_still_there_for_the_desktop(self):
        self.assertIn("{examples}", protocol.prompts()["situation"]["rules"])


class TestWebTexts(unittest.TestCase):
    def test_new_screens_present(self):
        t = protocol.texts()
        for key in ("instructions", "interlocutor_intro", "topic_pick",
                    "topic_card", "interlocutor_label", "debriefing"):
            self.assertIn(key, t)
        self.assertIn("{name}", t["interlocutor_intro"]["human"])
        self.assertIn("{name}", t["interlocutor_label"]["ai"])
        self.assertIsInstance(t["debriefing"]["body"], str)

    def test_desktop_debriefing_keeps_both_versions(self):
        self.assertEqual(set(protocol.texts()["desktop_debriefing"]["body"]),
                         {"scripted", "llm"})
```

Also update `TestScales.test_authenticity...` to expect three items and none reversed, `TestMarkers` to expect 22 codes, and `TestEverything` to expect the eleven sections.

- [ ] **Step 2: Run** `python3 -m unittest common.test_protocol -v` — Expected: new tests FAIL (AttributeError / KeyError).

- [ ] **Step 3: Write the content files** (exact wording from spec §2 and §3) and the loader:

```python
CONDITIONS = ("human_validation", "human_rejection",
              "ai_validation", "ai_rejection")

def sequences():
    """Williams Latin square: {"1": [condition x4], ..., "4": [...]}."""
    return _read_json("sequences")

def interlocutors():
    """Four {name, type} entries, two per agent type, in assignment order."""
    return _read_json("interlocutors")

def topics():
    """Eight {id, category, question} debate topics."""
    return _read_json("topics")

def split_condition(condition):
    """'ai_rejection' -> ('ai', 'rejection')."""
    if condition not in CONDITIONS:
        raise ValueError("condition must be one of %s, not %r" % (CONDITIONS, condition))
    agent_type, feedback = condition.split("_")
    return agent_type, feedback

def fallback_lines():
    """{feedback: {turn: text}} from protocol/fallback.csv (web, LLM failures)."""
    return _read_lines_csv("fallback.csv")

def scripts():
    """{feedback: {turn: text}} from protocol/scripts.csv (desktop)."""
    return _read_lines_csv("scripts.csv")

def _read_lines_csv(filename):
    out = {}
    with open(os.path.join(PROTOCOL_DIR, filename), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.setdefault(row["feedback"], {})[int(row["turn"])] = row["text"]
    return out
```

`sequences.json`:

```json
{
  "1": ["human_validation", "human_rejection", "ai_rejection", "ai_validation"],
  "2": ["human_rejection", "ai_validation", "human_validation", "ai_rejection"],
  "3": ["ai_validation", "ai_rejection", "human_rejection", "human_validation"],
  "4": ["ai_rejection", "human_validation", "ai_validation", "human_rejection"]
}
```

`interlocutors.json`: `[{"name":"Julián","type":"human"},{"name":"Martina","type":"human"},{"name":"Nova","type":"ai"},{"name":"Kai","type":"ai"}]`.

`texts.json` additions: `instructions {title, body}`, `interlocutor_intro {title, human, ai}` (with `{name}`), `interlocutor_label {human, ai}` (with `{name}`), `topic_pick {title, lead}`, `topic_card {title, hint}` (`hint` with `{n}`), `pause.body` reworded, `consent.body` reworded, `debriefing {title, body}` single, `desktop_debriefing {title, body {scripted, llm}}` (moved). Markers: `"interlocutor_intro": 12, "topic_shown": 13, "topic_chosen": 14, "opinion_sent": 15`.

- [ ] **Step 4: Point the desktop at the moved entries** (`protocol.desktop_debriefing(config.AGENT)`, `prompts()["situation"]` inside `llm_agent` — see Task 6 — and three authenticity items). `py_compile` the desktop.
- [ ] **Step 5: Run** all common tests — Expected: PASS.
- [ ] **Step 6: Commit** — `git commit -m "Protocol content for the debate design"`.

---

### Task 6: LLM agent — debate prompt and fallback reason

**Files:**
- Modify: `common/llm_agent.py`, `common/test_llm_agent.py`.

**Interfaces:**
- Produces: `build_system_prompt(feedback, name=None, question=None)` → str (debate template when `question` is given, situation template otherwise); `LLMAgent(feedback, transport=None, timeout=None, name=None, question=None)`; `.reply(fallback_line)` → `(text, origin, reason)` where `reason` is `None` on success, else `"<ExceptionType>: <message>"` or `"empty reply from model"`; `PendingReply.result()` returns the same triple. `probe(transport=None, timeout=None)` → `(ok: bool, latency_s: float|None, error: str|None)` — sends a one-token completion `{"model": …, "messages":[{"role":"user","content":"hola"}], "max_tokens": 1}`.

- [ ] **Step 1: Write the failing tests**

```python
class TestDebatePrompt(unittest.TestCase):
    def test_contains_name_question_and_role(self):
        system = llm_agent.build_system_prompt(
            "rejection", name="Nova", question="¿Messi es el mejor de la historia?")
        self.assertIn("Nova", system)
        self.assertIn("¿Messi es el mejor de la historia?", system)
        self.assertIn("RECHAZO", system)
        self.assertNotIn("{", system)

    def test_agent_uses_debate_prompt_when_given_a_question(self):
        seen = {}
        def transport(payload):
            seen["system"] = payload["messages"][0]["content"]
            return "ok"
        agent = llm_agent.LLMAgent("validation", transport=transport,
                                   name="Julián", question="¿La religión hace bien?")
        agent.hear("Yo creo que sí.")
        agent.reply("fallback")
        self.assertIn("¿La religión hace bien?", seen["system"])
        self.assertIn("VALIDAR", seen["system"])

class TestFallbackReason(unittest.TestCase):
    def test_success_has_no_reason(self):
        agent = llm_agent.LLMAgent("validation", transport=lambda p: "hola")
        self.assertEqual(agent.reply("x"), ("hola", "llm", None))

    def test_exception_is_reported(self):
        def transport(payload):
            raise IOError("no network")
        agent = llm_agent.LLMAgent("validation", transport=transport)
        text, origin, reason = agent.reply("line")
        self.assertEqual((text, origin), ("line", "fallback"))
        self.assertEqual(reason, "OSError: no network")

    def test_empty_reply_is_reported(self):
        agent = llm_agent.LLMAgent("validation", transport=lambda p: "   ")
        self.assertEqual(agent.reply("line")[2], "empty reply from model")

class TestProbe(unittest.TestCase):
    def test_ok(self):
        ok, latency, error = llm_agent.probe(transport=lambda p: "h")
        self.assertTrue(ok); self.assertIsNone(error); self.assertGreaterEqual(latency, 0)

    def test_failure(self):
        def transport(payload):
            raise RuntimeError("401 Unauthorized")
        ok, latency, error = llm_agent.probe(transport=transport)
        self.assertFalse(ok); self.assertEqual(error, "RuntimeError: 401 Unauthorized")
```

Update existing tests that unpack `(text, origin)` to unpack three values.

- [ ] **Step 2: Run** `python3 -m unittest common.test_llm_agent -v` — Expected: FAIL.
- [ ] **Step 3: Implement.** `_openrouter_transport` turns `urllib.error.HTTPError` into `RuntimeError("HTTP %d %s: %s" % (code, reason, body[:120]))` so the reason is readable. The desktop's `reply_in_thread` consumer (`desktop/study1.py`) unpacks the triple and ignores the reason.
- [ ] **Step 4: Run** the common tests and `py_compile` the desktop — Expected: PASS.
- [ ] **Step 5: Commit** — `git commit -m "LLM agent: debate prompt, fallback reason, probe"`.

---

### Task 7: Server — health, turn with reason, seq prefix, key report

**Files:**
- Modify: `web/server/app.py`, `web/test_server.py`, `common/output.py` (`CHAT_FIELDS` += `episode, condition, interlocutor, topic, fallback_reason` — ordered `episode, condition, interlocutor, topic, author, text, origin, fallback_reason, t_experiment_s, latency_s`), `common/test_output.py`.

**Interfaces:**
- `GET /api/health` → `{"ok": true, "llm": {"key_found", "key_source", "model", "reachable", "latency_s", "error"}}`; result cached `HEALTH_CACHE_S = 60`; module attribute `PROBE_TRANSPORT = None` (tests inject a callable transport). `?refresh=1` bypasses the cache.
- `POST /api/turn` body `{feedback, name, question, history, fallback_line, access_code}` → `{text, origin, fallback_reason}`; 400 when `feedback` invalid.
- `POST /api/data` body `{info: {participant_id, sequence}, responses, behavioral, chat, events, access_code}` → files prefixed `S1_<id>_seq<sequence>_`.

- [ ] **Step 1: Write the failing tests**

```python
class TestHealth(ServerBase):
    def test_reports_reachable_when_probe_succeeds(self):
        app.PROBE_TRANSPORT = lambda payload: "h"
        code, body = request(self.port, "/api/health?refresh=1")
        self.assertEqual(code, 200)
        self.assertTrue(body["llm"]["reachable"])
        self.assertIsNone(body["llm"]["error"])
        self.assertEqual(body["llm"]["model"], protocol.prompts()["model"])

    def test_reports_the_error_when_probe_fails(self):
        def transport(payload):
            raise RuntimeError("HTTP 401 Unauthorized")
        app.PROBE_TRANSPORT = transport
        _, body = request(self.port, "/api/health?refresh=1")
        self.assertFalse(body["llm"]["reachable"])
        self.assertIn("401", body["llm"]["error"])

class TestTurn(ServerBase):
    def test_returns_text_origin_and_no_reason(self):
        code, body = request(self.port, "/api/turn", {
            "feedback": "validation", "name": "Nova",
            "question": "¿Messi es el mejor?",
            "history": [{"role": "user", "content": "Sí, obvio."}],
            "fallback_line": "fallback"})
        self.assertEqual(body, {"text": "model reply", "origin": "llm",
                                "fallback_reason": None})

    def test_failure_returns_fallback_with_reason(self):
        def transport(payload):
            raise IOError("no network")
        app.TRANSPORT = transport
        _, body = request(self.port, "/api/turn", {
            "feedback": "rejection", "history": [], "fallback_line": "Mmm."})
        self.assertEqual(body["origin"], "fallback")
        self.assertEqual(body["fallback_reason"], "OSError: no network")

    def test_question_reaches_the_system_prompt(self):
        seen = {}
        def transport(payload):
            seen["system"] = payload["messages"][0]["content"]; return "ok"
        app.TRANSPORT = transport
        request(self.port, "/api/turn", {"feedback": "rejection", "name": "Kai",
                "question": "¿El arte es cualquier cosa?", "history": [],
                "fallback_line": "x"})
        self.assertIn("¿El arte es cualquier cosa?", seen["system"])

class TestData(ServerBase):
    def test_prefix_carries_id_and_sequence(self):
        _, body = self._send()   # info: {"participant_id": "07", "sequence": 3}
        for name in body["files"]:
            self.assertTrue(name.startswith("S1_07_seq3_"))
```

- [ ] **Step 2: Run** `python3 -m unittest discover -s web -t . -v` — Expected: FAIL.
- [ ] **Step 3: Implement** `_health()` (uses `llm_agent.load_api_key()` for `key_found`/`key_source` — `"env"` if the variable is set, `"file"` if the file was read — and `llm_agent.probe(transport=PROBE_TRANSPORT or None, timeout=LLM_TIMEOUT)`; cache `(time, result)` in a module dict guarded by the existing lock), `_turn()` building `LLMAgent(feedback, transport=TRANSPORT, timeout=LLM_TIMEOUT, name=body.get("name"), question=body.get("question"))`, logging `print("LLM fallback (%s): %s" % (feedback, reason))` on fallback; `main()` prints `LLM key: found in env` / `found in openrouter_key.txt` / `NOT FOUND (every turn will fall back)`.
- [ ] **Step 4: Run** both suites — Expected: PASS.
- [ ] **Step 5: Commit** — `git commit -m "Server: health probe, turn with fallback reason, seq prefix"`.

---

### Task 8: Front end — four debate episodes, pinned topic, health line, banner, layout

**Files:**
- Modify: `web/index.html`, `web/js/protocol.js`, `web/js/scales.js`, `web/js/chat-plugin.js`, `web/js/experiment.js`, `web/static/styles.css`.

**Interfaces:**
- Consumes `/api/health`, `/api/turn`, `/api/data`, `/api/protocol` (Task 7).
- `jsPsychChatEpisode` trial parameters: `episode` (1–4), `condition`, `agent_type`, `feedback`, `interlocutor` (name), `label` (header text), `topic` (`{id, category, question}`), `access_code`, `test_mode`. Trial data: `episode, condition, agent_type, feedback, topic, interlocutor, opinion, opinion_chars, opinion_latency_s, reply_1..3, reply_1_chars..3, reply_latency_1..3, final_reply, final_latency_s, replied_at_end, replies_timed_out, fallback_turns, transcript[], events[]`.
- `jsPsychTopicPick` (new small plugin in `scales.js`? no — in `experiment.js` as a `html-button-response` trial with `choices` = remaining questions and `button_html` rendering cards) → data `{topic_id}`.

- [ ] **Step 1: Start form.** Replace the condition/order/agent selects with `<select name="sequence">` (1–4), keep id/age/sex/access code/test mode. Add `<p id="llm-health" class="health"></p>` with a `Reintentar` link. On load: `loadProtocol()`, then `checkHealth()`:

```js
async function checkHealth(refresh) {
  const el = document.getElementById("llm-health");
  el.className = "health pending";
  el.textContent = "Comprobando el LLM…";
  try {
    const resp = await fetch("/api/health" + (refresh ? "?refresh=1" : ""));
    const llm = (await resp.json()).llm;
    if (llm.reachable) {
      el.className = "health ok";
      el.textContent = `LLM listo: ${llm.model} respondió en ${llm.latency_s.toFixed(1)} s (key: ${llm.key_source})`;
    } else {
      el.className = "health error";
      el.textContent = llm.key_found
        ? `LLM no disponible: ${llm.error}`
        : "LLM no disponible: no hay API key (OPENROUTER_API_KEY u openrouter_key.txt)";
    }
  } catch (e) {
    el.className = "health error";
    el.textContent = "No se pudo consultar /api/health: " + e.message;
  }
}
```

Pre-fill sequence from the id: `((Array.from(id).reduce((a, c) => a + c.charCodeAt(0), 0)) % 4) + 1`, recomputed on `input` of the id field until the experimenter touches the select.

- [ ] **Step 2: Timeline (`experiment.js`).** Consent → rest → baseline measures (no authenticity) → instructions → for `i in 0..3`: condition = `PROTOCOL.sequences[cfg.sequence][i]`; `[agent_type, feedback] = condition.split("_")`; interlocutor = next unused of that type from `PROTOCOL.interlocutors`; intro screen (`interlocutor_intro[agent_type]` with `{name}` replaced, mark `interlocutor_intro`); topic pick trial (choices = topics not in `usedTopics`, `button_html` = `<button class="topic-card"><span class="topic-category">…</span><span class="topic-question">…</span></button>`, on_finish pushes the chosen id and marks `topic_chosen` with it; `topic_shown` marked on load); connecting; chat trial; measures (with authenticity); pause unless last. Then debriefing (single body) → close → `experiment_end`. Remove cover story, manipulation check, suspicion survey, re-consent.

- [ ] **Step 3: Chat plugin.** Render the pinned card after the bar:

```html
<div class="topic-pinned">
  <div class="topic-pinned-title">${t.topic_card.title}</div>
  <div class="topic-pinned-question">${trial.topic.question}</div>
  <div class="topic-pinned-hint">${t.topic_card.hint.replace("{n}", p.min_opinion_chars)}</div>
</div>
<div class="fallback-banner" id="fallback-banner" hidden></div>
```

Flow: `episode_start` mark (detail `${episode}_${condition}`) → `waitForParticipant({minChars: p.min_opinion_chars, timeout: p.situation_timeout, marker: "opinion_sent"})` (test-mode skip fills `p.test_filler_opinion`) → for turn 1..3: `requestTurn(fallbackLine(feedback, turn))` posting `{feedback, name, question, history, fallback_line, access_code}`; on `origin === "fallback"` increment `fallbackTurns`, and if `trial.test_mode` show the banner `Fallback (turno ${turn}): ${reason}` in red; a later `llm` turn with `fallbackTurns > 0` turns the banner amber `${fallbackTurns} turno(s) cayeron al fallback`; `agentSays(text, "agent_message_"+turn, origin, reason)` → transcript rows carry `episode, condition, interlocutor, topic, author, text, origin, fallback_reason, t_experiment_s, latency_s`; between turns the free reply (`timeout: 90`), then the final free-reply window as today. No greeting.

- [ ] **Step 4: Scales.** `measuresBlock` reads `authenticity.items` (now three). `collectMeasures` adds `auth_mean` when all three are present.

- [ ] **Step 5: Submission (`submit`).** `responses` = `participant_id, age, sex, sequence, test_mode, llm_model`, baseline measures prefixed `baseline_`, and per episode `epN_condition, epN_agent_type, epN_feedback, epN_topic, epN_interlocutor, epN_opinion` + measures prefixed `epN_` (measures are collected with moment key `ep1`…`ep4`). `behavioral` rows = the trial data minus `transcript`/`events`/jsPsych internals. `chat` = concatenated transcripts. `info = {participant_id, sequence}`.

- [ ] **Step 6: CSS.**

```css
#jspsych-target.active { display: flex; min-height: 100vh; }
.jspsych-display-element { flex: 1; display: flex; flex-direction: column; overflow-y: auto; }
.jspsych-content-wrapper { flex: 1; display: flex; align-items: center; justify-content: center; min-height: 0; }
.jspsych-content { max-width: 46rem; margin: 2rem auto; }
.chat { height: min(80vh, 44rem); }
.topic-card { display: block; width: 100%; max-width: 40rem; margin: .5rem auto; padding: 1rem 1.2rem; text-align: left; background: #fff; color: var(--text); border: 1px solid var(--border); border-radius: 10px; }
.topic-card:hover { border-color: var(--accent); }
.topic-category { display: block; font-size: .8rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
.topic-question { display: block; font-size: 1.05rem; margin-top: .2rem; }
.topic-pinned { margin: .8rem 1rem 0; padding: .7rem .9rem; background: #FFF8E6; border: 1px solid #F0DDA6; border-radius: 8px; text-align: left; }
.topic-pinned-title { font-size: .75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
.topic-pinned-question { font-size: 1rem; margin: .2rem 0; }
.topic-pinned-hint { font-size: .8rem; color: var(--muted); }
.fallback-banner { margin: .5rem 1rem 0; padding: .45rem .8rem; border-radius: 6px; font-size: .85rem; text-align: left; }
.fallback-banner.error { background: #FDECEC; color: #A32020; border: 1px solid #F3B4B4; }
.fallback-banner.warning { background: #FFF4DB; color: #7A5200; border: 1px solid #F0D48A; }
.health { font-size: .85rem; margin-top: .8rem; }
.health::before { content: "●"; margin-right: .4rem; }
.health.ok::before { color: #2E8B57; } .health.error::before { color: #C0392B; } .health.pending::before { color: var(--muted); }
```

Replace the `#jspsych-target.activo { display:block }` rule.

- [ ] **Step 7: Manual smoke** — `PORT=8765 python3 -m web.server.app`, open in a browser, run in test mode through all four episodes. Then run the unit suites (unchanged).
- [ ] **Step 8: Commit** — `git commit -m "Web: four debate episodes, pinned topic, LLM health and fallback banner, centred screens"`.

---

### Task 9: Playwright end-to-end script

**Files:**
- Create: `web/e2e/run_flow.mjs`, `web/e2e/README.md` (two lines: how to run).

**Interfaces:**
- CLI: `node web/e2e/run_flow.mjs --url http://localhost:8765 --code <access code> --shots <dir>`; exit 0 on success; prints one line per assertion.

- [ ] **Step 1: Write the script.** Uses the global Playwright (`import { chromium } from "playwright"` with `NODE_PATH` pointing at the global `node_modules`, resolved by `npm root -g`). Flow: open `--url`; wait for `#llm-health.ok, #llm-health.error`; assert its text is non-empty and record it; fill id `e2e`, tick test mode, fill code; click Empezar. Then loop: on each screen, screenshot to `<shots>/<nn>-<kind>.png` (kind from the DOM: `consent`, `rest`, `slider`, `panas`, `intro`, `topic-pick`, `chat`, `pause`, `debriefing`, `close`), assert never seeing text «otra sala» outside an intro screen, never seeing «creíste que estabas interactuando», count `.topic-card` on each topic-pick screen and assert the sequence 8, 7, 6, 5, in chat assert `.topic-pinned` exists and has no `.bubble` class and that the first `.bubble` is `.participant`; press F9 / click `#skip` to advance (for chat, click repeatedly until the chat disappears). Ends when the page shows «Se guardaron 4 archivos». Run at 1280×800 and 1440×900 (two browser contexts, same flow; the second stops after the first chat screen to keep it short).

- [ ] **Step 2: Run locally** — `PORT=8765 python3 -m web.server.app &`, `node web/e2e/run_flow.mjs --url http://localhost:8765 --shots $CLAUDE_JOB_DIR/tmp/screenshots/local`. Expected: exit 0, four CSVs appear in `data/` with the `S1_e2e_seq` prefix; look at the screenshots and check the centring.
- [ ] **Step 3: Commit** — `git commit -m "Playwright end-to-end flow check"`.

---

### Task 10: Docs for the new flow

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `AGENTS.md`, `protocol/README.md`, `web/README.md`.

- [ ] **Step 1: Update** the flow description (four episodes, topics, no cover story on the web), the protocol table (new files; desktop-only entries per spec §3.9), the output columns, `/api/health`, the test-mode banner, the e2e script, and the env/secret names on fly (`ACCESS_CODE`). Invariants section: the web follows the debate design (LLM in every episode, deterministic latency, opinion typed inside the chat, baseline without authenticity, SUDS → SAM → authenticity → PANAS, markers); the desktop still follows the original two-episode design until migrated.
- [ ] **Step 2: Commit** — `git commit -m "Docs: phase-1 debate flow"`.

---

### Task 11: Deploy and verify on fly.io

- [ ] **Step 1: Secrets.** `CODE=$(python3 -c "import secrets; print(secrets.token_urlsafe(9))")`; `fly secrets set ACCESS_CODE=$CODE --app neuro-estudio1-demo --stage`; `fly secrets unset CODIGO_ACCESO --app neuro-estudio1-demo --stage`.
- [ ] **Step 2: Deploy.** `fly deploy --app neuro-estudio1-demo` (applies staged secrets). Expected: healthy machine; `curl https://neuro-estudio1-demo.fly.dev/api/health` returns `reachable: true`.
- [ ] **Step 3: E2E against production.** `node web/e2e/run_flow.mjs --url https://neuro-estudio1-demo.fly.dev --code $CODE --shots $CLAUDE_JOB_DIR/tmp/screenshots/prod`. Expected: exit 0. `fly logs` shows the boot line about the key and no `LLM fallback` lines during the run.
- [ ] **Step 4: Fetch the produced CSVs** with `fly ssh console -C "ls /data"` to confirm four `S1_e2e_seq*` files; delete them afterwards (`rm /data/S1_e2e_*`) so the volume holds no test runs.

---

### Task 12: Merge

- [ ] **Step 1:** In the main checkout: `git -C /Users/rod/code/neuro-pre-entrega-3 merge --no-ff phase1-debate -m "Merge branch 'phase1-debate': English rename, debate design on the web, LLM visibility"`.
- [ ] **Step 2:** Report: access code, URL, what changed, how to run.
