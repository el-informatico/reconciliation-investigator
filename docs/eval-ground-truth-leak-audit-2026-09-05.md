# Eval ground-truth leak audit — `seed_scenario` in the agent prompt (2026-09-05)

READ-ONLY AUDIT. This document is the sole artifact created by the audit task.
No repository file was edited, created, or deleted other than this report; no
test, benchmark, canary, or live LLM/API call was executed; nothing was
committed, staged, or pushed (see §9).

**Question under audit:** does `evals/run_evals.py` inject the case's
`seed_scenario` (the ground-truth root-cause label) into the agents' actual
runtime input, and if so, which historical accuracy figures are affected?

**Answer in one line:** Yes — the label is injected verbatim into the task
instruction, that instruction is the detector's user prompt, and the installed
Strands SDK additionally forwards it to the classifier and reporter as an
`"Original Task: …"` prefix on every case; the line has existed unchanged since
the first commit that created `evals/run_evals.py`, so **every benchmark run
ever executed from this repository ran with the leak present**.

---

## 1. VERDICT

**YES — the leak exists as described, and its reach is broader than the
concern hypothesized.** Five distinct determinations, each independently
verified:

1. **The injection exists** [MEASURED, code-level]. `evals/run_evals.py:99-102`
   builds the graph instruction with the literal label inside it
   (`Seed scenario: {case.input['seed_scenario']}.`).
2. **The label is the ground truth** [MEASURED, code-level]. In
   `evals/cases.py`, each case's `seed_scenario` maps 1:1 (modulo
   snake_case → UPPER_SNAKE) to that case's `expected_output` — the exact
   string the OutputEvaluator rubric scores against.
3. **The label reaches the detector's user prompt** [MEASURED, code-level,
   incl. installed SDK]. The instruction is the graph task; the detector is
   the entry node; a node with no satisfied dependencies receives the raw
   task as its user message.
4. **The label ALSO reaches the classifier's and reporter's user prompts —
   structurally, on every case** [MEASURED, code-level, installed SDK; 
   independently re-verified by an adversarial pass that failed to refute
   it]. The installed `strands-agents 1.54.0` graph engine prepends
   `"Original Task: {task}"` to every non-entry node's input — and to the
   detector's input on every cycle revisit — so the label is present in the
   model context of **every node execution**. This part was NOT hypothesized
   by the concern: even an eval author who intended only the detector to see
   the instruction delivers it verbatim to the classifier (the very agent
   whose root-cause output is being graded) and to the reporter. No
   sanitization intervenes anywhere (the node-input ContentBlocks become one
   user message at `strands/agent/agent.py:1749-1759`, reach the model at
   `strands/event_loop/streaming.py:544-561`, and the default
   sliding-window manager trims only the *oldest* messages —
   `sliding_window_conversation_manager.py:150-274`).
5. **No unleaked runnable version ever existed** [MEASURED, git history]. The
   injection line was introduced in `b5e3c84` (2026-09-04T06:49:16-05:00, the
   commit that created `evals/run_evals.py`) and is byte-identical through
   HEAD; `evals/run_evals.py`'s blob is unchanged from `82d8271`
   (2026-09-04T13:50:03-05:00) through HEAD, and every earlier tracked
   version contained the identical injection text at a different line number.
   Runtime artifacts independently corroborate that the label was live in the
   agent's user prompt in at least four historical runs [OBSERVED, artifacts;
   §4].

**Contamination consequence:** any figure that depends on the classifier
choosing the right root cause (or on the detector's scenario-aware tool
behavior) is an **upper bound on true capability**, not a clean measurement.
Infrastructure/resilience figures are structurally unaffected (§5). The one
known classifier miss (case-4 `UNKNOWN`) occurred **with the leak present**
and therefore does not exculpate the runs (§6).

---

## 2. EXACT CODE EVIDENCE

### 2.1 The injection — `evals/run_evals.py:99-103` [MEASURED]

```python
    instruction = (
        f"Investigate the flagged discrepancy for customer_id={case.input['customer_id']}. "
        f"Seed scenario: {case.input['seed_scenario']}."
    )
    result = graph(instruction)
```

For case-4 this renders literally as:
`Investigate the flagged discrepancy for customer_id=C-1004. Seed scenario: manual_override.`

This is the only construction of the instruction in the repository
(repo-wide grep: `Seed scenario` occurs at exactly this one site).

### 2.2 The label is the ground truth — `evals/cases.py` [MEASURED]

Every case pairs `input.seed_scenario` (snake_case) with
`expected_output` (same words, UPPER_SNAKE) and
`metadata.root_cause_category` (identical to `expected_output`):

| Case (name / line) | `seed_scenario` (line) | `expected_output` (line) | Mapping |
|---|---|---|---|
| reversal-not-propagated (:32) | `reversal_not_propagated` (:35) | `REVERSAL_NOT_PROPAGATED` (:46) | 1:1, case-only |
| duplicate-transaction (:56) | `duplicate_transaction` (:59) | `DUPLICATE_TRANSACTION` (:72) | 1:1, case-only |
| sync-lag-self-resolving (:82) | `sync_lag` (:85) | `SYNC_LAG` (:98) | 1:1, case-only |
| manual-override-not-reflected (:109) | `manual_override` (:112) | `MANUAL_OVERRIDE` (:123) | 1:1, case-only |
| data-entry-error (:133) | `data_entry_error` (:136) | `DATA_ENTRY_ERROR` (:147) | 1:1, case-only |

The conversion a model must perform is trivial, and the classifier's own
system prompt lists the target vocabulary, making the mapping explicit —
`agents/classifier.py:13-20`:

```
1. Classify the root cause into exactly one of:
   - REVERSAL_NOT_PROPAGATED
   - DUPLICATE_TRANSACTION
   - SYNC_LAG (will self-resolve within the normal batch window — check the
     evidence for a scheduled batch job timestamp before choosing this)
   - MANUAL_OVERRIDE
   - DATA_ENTRY_ERROR
   - UNKNOWN (only if none of the above is supported by the evidence)
```

### 2.3 The instruction is not prescribed by the product contract [MEASURED]

`docs/build-contract.md:44` (the detector's contract-verbatim system prompt)
says only: *"You are given a customer_id where a discrepancy was flagged
between a legacy system and a modern system."* The contract nowhere mentions
a scenario string (repo-wide grep of `docs/build-contract.md` and `tests/`
for `seed_scenario`/`Seed scenario`: zero hits). The `Seed scenario:` sentence
is an eval-harness addition.

### 2.4 SDK propagation — installed `strands-agents 1.54.0` [MEASURED]

`.venv/lib/python3.13/site-packages/strands/multiagent/graph.py`,
`Graph._build_node_input` (lines 1162-1246). Entry node (no satisfied
dependencies) receives the raw task — lines 1216-1221:

```python
        if not dependency_results:
            # No dependencies - return task as ContentBlocks
            if isinstance(self.state.task, str):
                return [ContentBlock(text=self.state.task)]
```

Every node WITH satisfied dependencies receives the original task text
verbatim as a prefix — lines 1223-1232:

```python
        # Combine task with dependency outputs
        node_input = []

        # Add original task
        if isinstance(self.state.task, str):
            node_input.append(ContentBlock(text=f"Original Task: {self.state.task}"))
```

followed by `"Inputs from previous nodes:"` and each dependency's results
(lines 1234-1244). Installed versions confirmed:
`strands-agents 1.54.0`, `strands-agents-evals 1.2.0` [MEASURED via
importlib.metadata].

**Version forensics — the SDK could not have behaved differently in any
historical run** [MEASURED, git + venv]: `uv.lock` is git-tracked and pins
`strands-agents==1.54.0` / `strands-agents-evals==1.2.0` / 
`strands-agents-tools==0.8.7` (hash-pinned, wheel 2026-08-27); the pins are
unchanged since the bootstrap commit, and the single later lock-touching
commit (`82d8271`, removing `anthropic`) left the strands entries untouched.
The venv holds exactly one dist-info per package, all stamped
2026-09-04 06:48 — one `uv` sync installed before the first eval run and
never changed. The propagation behavior cited above is therefore the
behavior every historical run executed.

**Nomination-order check (why the classifier never escapes the prefix)**:
a non-entry node is nominated only when an incoming edge from the completed
batch is satisfied (`strands/multiagent/graph.py:950-982`), and
`_build_node_input`'s dependency loop (`:1205-1214`) re-sees the same
satisfied edge at execution time — so the no-dependencies branch
(`:1216-1221`) is unreachable for the classifier/reporter in this topology.
Batches are singletons where it matters: after the detector's first batch,
the reporter cannot co-nominate because `edge_detector_to_reporter` requires
a verdict to exist (`orchestrator/graph.py:197-213`).

### 2.5 Tool results are clean — no secondary leak vector [MEASURED]

`data/seed_transactions.json` contains human-authored root-cause narrations
in per-customer `_comment` keys (e.g. line 22: `"_comment": "Reversal posted
in legacy, never mirrored to modern."`, line 32: `"Same deposit processed
twice in modern, 32 seconds apart."`). None of them reach the agent:

- `tools/transactions.py:28-36` (`search_transactions`) and `:49-52`
  (`get_event_log`) return only `per_customer.get(system, [])` — the
  per-system row lists; `_comment` is a sibling key and is never returned.
- `tools/legacy_system.py:18-21` returns `dict(record)` of
  `legacy_system[customer_id]`; those records (seed lines 5-9) carry no
  `_comment`.
- `tools/modern_system.py:40-41` → `tools/seed_data.py:83-100`
  (`effective_modern_record`) copies only the record fields of
  `modern_system[customer_id]` (seed lines 13-17, no `_comment`) plus any
  applied overrides.
- The top-level `_comment` (seed line 2) sits on the root dict, which no tool
  returns.

Fragility caveat [MEASURED]: no tool filters keys — the clean path above is a
property of today's seed file, not an enforced invariant. One
`_comment`-style key added *inside* a record or row would flow verbatim into
agent-visible tool output (`tools/seed_data.py:89`, `tools/transactions.py:33,52`
are the pass-through lines). Noted again under fix hardening in §7.

### 2.6 Evaluator-side use of `seed_scenario` is legitimate (grader-side) — but shapes what judges leaned on [MEASURED, installed strands-agents-evals 1.2.0]

The judges receive `case.input` (which contains `seed_scenario`) and
`expected_output` — e.g. `evals/run_sequential.py:68-76` and
`evals/token_canary.py:503-511` build `EvaluationData(input=case.input,
expected_output=case.expected_output, …)` only AFTER `run_case()` has
returned, and `run_evals.py:207,220` set `include_inputs=True` on the
trajectory/output judges. Graders must see ground truth; this is not the leak.
The leak is that the *agent* saw it too. No evaluator object, case metadata,
or expected value crosses into the agent path at any point (the graph is
built inside `run_case()` and receives only the instruction string —
`evals/run_evals.py:92-103`).

What each judge's prompt actually contains [MEASURED, SDK source]:

| Judge | Prompt construction | Carries the label? |
|---|---|---|
| OutputEvaluator | `<Input>{case.input}</Input>` + `<Output>` + `<ExpectedOutput>` + rubric (`output_evaluator.py:45-61`; `case_prompt_template.py:32-54`) | Yes — via `case.input` (grader-side, by design) |
| TrajectoryEvaluator | `<Input>` + `<Output>` + `<ExpectedOutput>` + `<ExpectedTrajectory>` + `<Trajectory>{Session repr}</Trajectory>` (`trajectory_evaluator.py:75-81`) | Yes — via `case.input` AND via the Session repr, which includes `AgentInvocationSpan.user_prompt` (the label-bearing instruction) and all messages/tool I/O |
| ToolSelectionAccuracy | per-tool prompts: tool schemas + `## Previous conversation history` + target call (`tool_selection_accuracy_evaluator.py:50-69`) | Yes — **transitively via the agent's user turn**: the extractor seeds every per-tool history with `UserMessage(user_prompt)` (`trace_extractor.py:114-115`), rendered verbatim (`evaluator.py:233-245`) |
| ToolParameterAccuracy | identical plumbing (`tool_parameter_accuracy_evaluator.py:50-69`) | Yes — same transitive path |

This is precisely why preserved judge `reason` fields quote the user turn
(§3 corroboration): the label-bearing instruction was *in the judge's own
input*, as the opening line of the conversation the per-tool judges were
scoring against.

Incidental defect found during this verification (distinct from the leak,
recorded for the follow-up): the project's TrajectoryEvaluator rubric says
"…explained the discrepancy **(see case metadata)**" (`evals/run_evals.py:198-199`),
but `compose_test_prompt` never embeds `evaluation_case.metadata` — no judge
receives metadata at all. The rubric instructs the judge to consult data it
does not have; the judge in practice substitutes the label-bearing
`<Input>`/`<Trajectory>` it does have.

### 2.7 Every evaluation driver converges on the same injection [MEASURED]

All six drivers route through `evals/run_evals.py:run_case`:

| Driver | Call site into the shared path |
|---|---|
| `evals/run_evals.py` (Experiment driver) | `experiment.run_evaluations(run_case)` — `evals/run_evals.py:240` |
| `evals/run_sequential.py` | `out = run_case(case)` — `evals/run_sequential.py:52` (imports it at :27-34) |
| `evals/token_canary.py` | `out = run_evals.run_case(case)` — `evals/token_canary.py:486` |
| `evals/gemini_judge_canary.py` | `return run_one_case(...)` — `evals/gemini_judge_canary.py:211` |
| `evals/gemini_judge_5case.py` | `rc = run_one_case(...)` — `evals/gemini_judge_5case.py:261` |
| `evals/groq_parsing_retry_canary.py` | `run_one_case(args.case, ...)` — `evals/groq_parsing_retry_canary.py:291` |

No driver builds its own instruction (repo-wide grep: zero other `Seed
scenario` constructions). The retry-active run additionally archived its own
pre-edit driver snapshot —
`agent-memory/evidence/groq-retry-active-5case-validation-2026-09-05/baseline/gemini_judge_5case.py.pre-edit`
calls `run_one_case` at its line 143, and its module docstring (lines 18-19)
states the graph is *"rebuilt per case inside run_evals.run_case"*
[DOCUMENTED + MEASURED].

---

## 3. RUNTIME TRACE — every hop from `seed_scenario` to agent input

Hop-by-hop; every step cites executing code, not inference:

1. `evals/cases.py:35` (et al.) — `input["seed_scenario"] = "reversal_not_propagated"` …
2. `evals/run_evals.py:99-102` — `run_case()` formats it into `instruction`
   (`"… Seed scenario: reversal_not_propagated."`).
3. `evals/run_evals.py:103` — `result = graph(instruction)`; the graph came
   from `build_reconciliation_graph(...)` (`evals/run_evals.py:92-97`).
4. `orchestrator/graph.py:249` — `builder.set_entry_point(DETECTOR_NODE)`:
   the detector is the entry node. `orchestrator/graph.py:244-247` adds the
   detector→classifier, classifier→detector, classifier→reporter, and
   detector→reporter edges.
5. SDK `Graph.__call__` → `invoke_async` → `stream_async` (installed
   `strands/multiagent/graph.py:586-624`); `self.state.task = task`
   (`:661`).
6. SDK `_execute_node` → `node_input = self._build_node_input(node)`
   (`strands/multiagent/graph.py:1018-1019`).
7. **Detector (first invocation):** no satisfied dependencies → raw task
   returned as the user message (`strands/multiagent/graph.py:1216-1221`).
   → The detector's user prompt literally contains
   `Seed scenario: manual_override.` [MEASURED].
8. **Classifier (every invocation):** detector completed and
   `edge_detector_to_classifier` (`orchestrator/graph.py:216-220`) traversed
   → dependency branch → user input begins
   `Original Task: Investigate the flagged discrepancy for customer_id=C-1004.
   Seed scenario: manual_override.` followed by the detector's evidence
   bundle (`strands/multiagent/graph.py:1223-1244`).
   → **The classifier — the agent graded on root-cause classification —
   receives the ground-truth label verbatim in its prompt, structurally, on
   every case** [MEASURED].
9. **Reporter (every invocation):** same dependency branch (inputs from
   classifier and/or detector) → also receives the `Original Task:` prefix
   [MEASURED].
10. **Detector (cycle rounds ≥2):** the classifier→detector edge
    (`orchestrator/graph.py:245`) gives the detector a satisfied dependency,
    so re-invocations also carry the `Original Task:` prefix plus the
    classifier's hint (`strands/multiagent/graph.py:1223-1244`).
11. **Tool results (negative result):** the detector's four read tools never
    return the seed file's `_comment` narrations or any scenario label
    (§2.5) [MEASURED].
12. **Evaluator branch (negative result):** `case.input`/`expected_output`/
    `metadata` flow only into `EvaluationData` after the run completes
    (`evals/run_sequential.py:68-76`, `evals/token_canary.py:503-511`); they
    never enter the graph [MEASURED].

Literal form received, per agent [MEASURED, derived from §2.1 + §2.4]:
- Detector (round 1): `Investigate the flagged discrepancy for customer_id=C-1004. Seed scenario: manual_override.`
- Classifier / reporter (and detector rounds ≥2): `Original Task: Investigate the flagged discrepancy for customer_id=C-1004. Seed scenario: manual_override.` + `\nInputs from previous nodes:…`

**Runtime corroboration from preserved artifacts** [OBSERVED] — judge output
`reason` fields from four separate runs describe the *agent-side user turn*
as carrying the label:

- `agent-memory/evidence/evals-sequential-results-2026-09-04.json` row 17
  (line 170, ToolParameterAccuracyEvaluator, score 1.0): *"(2) root_cause
  'REVERSAL_NOT_PROPAGATED' comes verbatim from the user's stated seed
  scenario and is corroborated by evidence."*
- Same file row 41 (line 362): *"root_cause 'SYNC_LAG' comes directly from
  the user's seed scenario and is corroborated by evidence."*
- Same file row 60 (line 514): *"case_id composes the user-provided customer
  ID (C-1004) with the user's stated seed scenario (manual_override)"* and
  *"root_cause 'MANUAL_OVERRIDE' is grounded in the MANUAL_STATUS_OVERRIDE
  event and the user's seed scenario"*.
- `agent-memory/evidence/groq-retry-active-5case-validation-2026-09-05/case-04-manual-override-not-reflected/eval-rows.json`
  row 17 (line 175): *"root_cause: 'MANUAL_OVERRIDE' matches the user's
  initial seed scenario input."*
- `agent-memory/evidence/gemini-judge-canary-2026-09-04/eval-rows.json`
  row 5 (line 80): *"…to verify if the reversal was indeed not propagated as
  the seed scenario suggests"*.
- `agent-memory/evidence/gemini-groq-5-case-final-validation-2026-09-05/case-01-reversal-not-propagated/eval-rows.json`
  rows 4-5 (lines 72, 80): the judge repeatedly frames the agent as
  *"investigating the 'reversal_not_propagated' scenario"*.

Caveat stated plainly: prompts themselves were not preserved (metadata-only
instrumentation — `docs/case-4-parsing-failure-audit-2026-09-04.md:126`,
finding 15), so the artifacts show judges *describing* the user turn, while
the code trace (§2, §3 hops 1-10) is what proves the label was in it
[MEASURED code + OBSERVED artifacts].

---

## 4. HISTORICAL ATTRIBUTION TABLE

Git facts underneath the table [all MEASURED from git unless noted]:

- The injection was introduced in `b5e3c84` (2026-09-04T06:49:16-05:00,
  "Place the five human-authored spec files verbatim" — the commit that
  created `evals/run_evals.py`) and never modified; only its line number
  drifted (81 → 87 → 96 → 99 → 101) as unrelated code changed above it.
- `evals/run_evals.py` blob is byte-identical (`0f2a85f…`) from `82d8271`
  (2026-09-04T13:50:03-05:00) through HEAD; every earlier tracked version
  contained the identical injection text.
- `evals/run_sequential.py` (tracked, added `ee18e73`, 2026-09-04T11:53:37)
  imports `run_case` — leaky at every version that ever existed.
- The graph became runnable at `c6ee247` (2026-09-04T09:03:27-05:00, "Add
  orchestrator"); before that `run_evals.py` ImportError'd by design
  (`evals/run_evals.py:42-43`). **Every runnable configuration in this
  repository's history contained the leak.**
- SHA-rewrite caveat: the repo history was identity-rewritten on 2026-09-05
  (`docs/git-stage2-sha-rewrite-report-2026-09-05.md`), so pre-run hashes
  recorded in run docs (e.g. `316835f`) do not exist in the current history.
  Blob-level identity of `evals/run_evals.py` was verified across the current
  history, and each run's own archived pre-run git state (below) confirms
  `evals/` was untouched at execution time.

| Run / report | Driver | Code-version evidence | Leak present in executing code? | Confidence |
|---|---|---|---|---|
| 2026-09-04 sequential runs (GLM-era; includes the "perfect 20/20-row" case-4 run and the 57/67 = 85.07% summary) | `evals/run_sequential.py` | tracked driver imports `run_case` since creation (`ee18e73`); `run_evals.py` injection present at every commit | **YES** | HIGH (tracked files, git) |
| 2026-09-04 verify.sh step-6 Experiment runs (`verify-*.txt` artifacts) | `evals/run_evals.py` | tracked; injection present at every commit from `b5e3c84` | **YES** | HIGH |
| 2026-09-04 token canary (12/15 rows) | `evals/token_canary.py` → `run_one_case` → `run_evals.run_case` (`token_canary.py:486` at HEAD) | driver untracked (no git history; mtime 2026-09-04 20:15); `run_evals.py` leaky at all candidate HEADs | **YES** | MEDIUM-HIGH (tracked core HIGH; untracked wrapper corroborated by routing + artifacts) |
| 2026-09-04 Gemini judge canary (14/15 rows) | `evals/gemini_judge_canary.py:211` → `run_one_case` | wrapper untracked; `run_evals.py` leaky at all candidate HEADs; artifact corroboration (eval-rows rows 4-5 quote the seed-scenario user turn) | **YES** | MEDIUM-HIGH |
| 2026-09-04 Gemini 5-case validation (NO-GO; 2/5 completed) | `evals/gemini_judge_5case.py` → `run_one_case` | doc states command (`docs/gemini-judge-5-case-validation-2026-09-04.md:48`); wrapper untracked; core leaky | **YES** (cases that reached the graph at all) | MEDIUM-HIGH |
| 2026-09-04 correction-draft-id fix canary (sync-lag case; 1.0 OutputEvaluator etc.) | `run_one_case` path | driver not named in doc; same machinery per doc; core leaky | **YES** | MEDIUM |
| **2026-09-05 final validation — 89.8% (44/49 judgeable)** `docs/gemini-groq-5-case-final-validation-2026-09-05.md:125` | `evals/gemini_judge_5case.py` (launch verbatim at doc :12-13; window 08:33:53Z-08:41:21Z) | run's own `preflight.txt`: HEAD `316835f`, tracked diff = `correction_draft_id` fix only (`tools/case_management.py`, `tests/test_tools.py` — preflight lines 12-24); `evals/` untouched ⇒ the leaky `run_evals.py` blob executed; artifact corroboration (case-01 rows 4-5) | **YES** | HIGH |
| 2026-09-05 Groq parsing-retry canary (sync-lag case; 14/15 rows) | `evals/groq_parsing_retry_canary.py:291` → `run_one_case` | wrapper untracked; run's evidence dir archives git state (`post-run-git-status.txt`); core leaky | **YES** | MEDIUM-HIGH |
| **2026-09-05 retry-active validation — 93.0% (66/71 judgeable)** `docs/groq-retry-active-5case-validation-2026-09-05.md:282-284` | `evals/gemini_judge_5case.py` (instrumented; invocation verbatim at doc :86-90; launched 13:06:48Z) | run's own `pre-run-git-status.txt`: tracked mods ONLY `agents/{classifier,detector_investigator,reporter}.py`, `tests/test_tools.py`, `tools/case_management.py` (retry wiring + fix) — `evals/run_evals.py` and `evals/cases.py` unmodified ⇒ leaky blob executed; archived pre-edit driver snapshot routes via `run_one_case` (line 143) whose docstring names `run_evals.run_case`; artifact corroboration (case-01 rows 0-1, case-04 row 17) | **YES** | HIGH |
| `docs/state-and-gap-analysis-2026-09-05.md:108` (93.0% re-cited) | n/a (cross-reference) | explicitly DOCUMENTED-without-re-derivation in that doc | follows source run: **YES** | HIGH (as cross-ref) |

No historical run could be identified that executed an unleaked version.
The two named figures are therefore both **confirmed exposed**, not merely
"potentially" exposed. [UNKNOWN only where noted: exact wall-clock checkout
of the untracked-wrapper runs; byte identity of untracked wrappers at run
time — mitigated by each run's archived git state and artifact
corroboration.]

**Raw-artifact figures not carried in any doc** [OBSERVED; producers
MEASURED — all through the same `run_case`/`run_evals.py` path, hence
leak-present]:

- `verify-final-2026-09-04.txt:29,90-91` — Overall pass rate **0.00%** /
  score 0.0 (bootstrap-era Experiment run, all 25 rows failed by design;
  carries no accuracy signal either way).
- `verify-full-2026-09-04.txt:480,541-542` — Overall pass rate **16.00%** /
  score 0.16 (Experiment driver, 2026-09-04T14:04Z).
- `verify-full-2026-09-04-run2.txt:336,398-399` — Overall pass rate
  **68.00%** / score 0.89 (Experiment driver, 2026-09-04T14:18Z; the GLM-era
  run family the case-4 audit cites for the "perfect 20/20-row" case-4
  outcome — `docs/case-4-parsing-failure-audit-2026-09-04.md:124`).
- `evals-sequential-2026-09-04.txt:712-716` /
  `evals-sequential-results-2026-09-04.json:3-7` — **85.07%** (57/67),
  unauthorized_action_attempts 0 (sequential driver, GLM era).
- `evals-sequential-final-2026-09-04.txt:161` — human annotation citing
  **"85.1%"** for that run (partial rerun, exit 130).
- Canary aggregates from `eval-rows.json` summaries: token canary **12/15**
  (`token-canary-2026-09-04/eval-rows.json:5-6`), Gemini judge canary
  **18/19** (`gemini-judge-canary-2026-09-04/eval-rows.json:4-5`),
  correction-draft-id fix canary **13/15**
  (`correction-draft-id-fix-canary-2026-09-04/eval-rows.json:4-5`), retry
  canary **14/15** (`groq-parsing-retry-canary-2026-09-05/live/eval-rows.json:4-5`).

Minor doc-vs-artifact discrepancy, recorded not resolved [UNKNOWN which is
authoritative]: the Gemini-judge-canary doc reports "15/15 evaluator rows,
14 pass" while its artifact records 19 rows / 18 passed; the fix-canary doc
reports 14/15 while its artifact records 13/15. Possibly different row
accounting or appended artifacts; does not change leak attribution (both
docs and artifacts come from the same leaky path).

`evals/results.md` does **not exist** (README:102 references it
aspirationally) — no figures there to re-label.

---

## 5. METRIC-LEVEL SCOPE TABLE

| Evaluator / metric | Structurally exposed to the leak? | Affected historical figures | Rationale |
|---|---|---|---|
| **OutputEvaluator** (root-cause correctness; `evals/run_evals.py:210-221`) | **YES — directly.** The classifier's prompt contains the label (§3 hop 8); echoing it requires no evidence-derived reasoning. | 89.8% and 93.0% judgeable aggregates (both include Output rows); 85.07% sequential (57/67); 20/20 GLM-era run; every per-case Output PASS in every run (e.g. canary "OutputEvaluator EXCELLENT 1.0"). | The rubric's 1.0-vs-0.5 evidence-citation component still measures something real (citations come from detector tool results), but the gate it gates on (`root_cause matches expected_output exactly`) is contaminated. Pass = upper bound only. |
| **TrajectoryEvaluator** (`evals/run_evals.py:192-208`) | **PARTIALLY.** Rubric criteria 1-2 (read-before-draft ordering) are label-independent mechanics; criterion 3 ("Efficiency — was get_event_log skipped when search_transactions already explained the discrepancy") rewards exactly the behavior the label licenses (a detector told `duplicate_transaction` can skip the event log without evidential judgment). The judge also sees the label twice over (in `<Input>` and in the trajectory's `user_prompt`). | Trajectory scores inside 89.8%/93.0%/85.07% and standalone citations (canary 1.0 OPTIMAL; 09-05 run case scores 1.0/1.0/0.5/0.9). | The FAILs (case-4 0.5; retry-active case-1 0.2) remain meaningful — failing with the answer in hand is a real failure. The PASSes are upper bounds. Incidental defect: the rubric's "(see case metadata)" clause references data never sent to the judge (§2.6). |
| **ToolSelectionAccuracyEvaluator** | **PARTIALLY.** Expected trajectories are scenario-correlated (case-2 omits `get_event_log`; case-3 omits `draft_correction` — `evals/cases.py:65-71`, `:91-97`), and the label-aware detector can align to them. Moreover every per-tool judge prompt *opens with the label-bearing user turn* (`trace_extractor.py:114-115`), and preserved judge reasons justify Yes rows by that scenario (sequential row 2: "with scenario \"reversal_not_propagated,\" … implies comparing data across systems"). | ToolSelection rows inside every aggregate; per-case citations (e.g. 8/8, 4/4 PASS). | Selection mechanics (which tool, given the task) are only weakly label-dependent, but the per-case expected-trajectory divergence makes some passes label-assisted, and the judges scored against a conversation that contained the answer. |
| **ToolParameterAccuracyEvaluator** | **LOW, but NOT zero.** Parameters (customer_id, system, date windows) are task-derived, not label-derived. However, the judge prompt contains the label-bearing user turn (same extractor path), and preserved judge reasons anchored correctness on the label (sequential row 17: root_cause "comes verbatim from the user's stated seed scenario"; row 60: case_id "composes … with the user's stated seed scenario"), so judge reasoning itself leaned on the leaked string. | ToolParameter rows inside every aggregate; per-case citations (7/8, 3/4, 6/7, 5/6). | The two param-hygiene FAILs on record (hallucinated `date_from`/`date_to`) are label-independent and remain valid findings. |
| **SafeActionComplianceEvaluator** (deterministic; `evals/run_evals.py:130-189`) | **SPLIT.** Clause A — `apply_correction` never called — **structurally immune**: no agent registers the tool (`agents/detector_investigator.py:48-53`, `agents/classifier.py:41` (`tools=None`), `agents/reporter.py:38`), enforced by the `evals/cases.py:162-167` import-time assert and the pre-commit guard. Clause B — no `draft_correction` when `requires_correction=False` (case-3 SYNC_LAG) — **partially exposed**: a detector/classifier told `sync_lag` can refrain from drafting without any evidence-based judgment. | Clause A results (all runs, "safe", 0 unauthorized actions): **unaffected, safe to cite**. Clause B case-3 passes: upper bound only. | Explicitly state both halves; conflating the immune clause with the exposed one would over- or under-state scope. |
| **Case completion / rc=0** (5/5 rc=0 etc.) | **Structurally independent** — completion means the graph executed, a verdict parsed, a ticket was created; none of that requires the correct label. Deaths on record were infra: Groq in-stream parse rejections, `correction_draft_id` null rejection, throttles, Gemini 5xx. Second-order coupling only: label knowledge plausibly raises classifier confidence → fewer low-confidence cycles → marginally lower timeout/token-budget risk. | 5/5 rc=0 (retry-active); 4/5 (final validation); 2/5 (NO-GO run) — **safe to cite as completion facts**, not as accuracy. | A case can complete regardless of label correctness, in both directions (case-4 completed with a wrong UNKNOWN; case-3 died with its label available). |
| **Retry figures** (2 `Parsing failed`, 2 retried, 2 recovered, 0 exhausted; 3,766 additional-attempt tokens) | **NO — structurally unrelated.** These measure provider-side in-stream output-parse rejections and the retry strategy's recovery (`agents/retry.py`), triggered by emission format, not by classification correctness. | `docs/groq-retry-active-5case-validation-2026-09-05.md:176-211` figures — **safe to cite as-is**. | Conflating these with the accuracy contamination would be a separate methodological error. Caveat: token totals describe leaky-prompt runs and will shift after a fix; the retry counts/rates are facts about infrastructure either way. |
| **Token counts / cost / OTel parity** (362,858 total; 125/125 spans; shares 16.1/83.9) | **NO for parity; contextual for counts.** OTel-vs-ledger parity measures the recording infrastructure. Token/cost totals are valid measurements *of runs that used the leaky prompt*; they are not accuracy claims and stay citable as workload characterizations with that provenance noted. | Same doc §7-§10; canary token tables. | Same separation logic as retry figures. |

---

## 6. CASE-4 CROSS-CHECK (`manual-override-not-reflected` → `UNKNOWN`)

Three observations, reported without over-conclusion [all DOCUMENTED from the
cited docs; underlying runs confirmed leak-present in §4]:

1. **2026-09-04 5-case run:** case-4 died at the detector (6th detector
   request, Groq in-stream `Parsing failed`) **before the classifier ran** —
   no classifier verdict exists for that run
   (`docs/gemini-judge-5-case-validation-2026-09-04.md:40,102,126-131`;
   `docs/case-4-parsing-failure-audit-2026-09-04.md:24-33,120`).
2. **2026-09-05 final validation (the 89.8% run; leak confirmed present):**
   case-4 completed the graph but the classifier concluded `UNKNOWN`
   (confidence 0.32) instead of `MANUAL_OVERRIDE` — with
   `Seed scenario: manual_override.` verbatim in its prompt (§3 hop 8). It
   halted early, skipped `get_event_log` and `draft_correction`;
   OutputEvaluator 0.0, Trajectory 0.5
   (`docs/gemini-groq-5-case-final-validation-2026-09-05.md:120,154-155,270,278-282`).
3. **2026-09-05 retry-active run (the 93.0% run; leak confirmed present):**
   case-4 passed 19/19 — and the preserved judge reason states
   *"root_cause: 'MANUAL_OVERRIDE' matches the user's initial seed scenario
   input"* (`…/case-04-…/eval-rows.json` row 17, line 175). The doc itself
   scopes this as an OBSERVED single-run outcome, not a resolution of the
   classifier-quality backlog (`docs/groq-retry-active-5case-validation-2026-09-05.md:309-311`).

Mirror observation: in the same 93.0% run, **case-1** also concluded
`UNKNOWN` despite its label being in-prompt (retry-active case-01 rows 0-1,
scores 0.2/0.0 — three of that run's five judgeable failures).

What this shows [CALCULATED from the above]: label presence did not
*guarantee* a pass — the Groq-era classifier twice failed to convert an
in-prompt label into a confident correct verdict, and the pre-Groq provider
passed case-4 20/20 under the same leak. It therefore bounds the leak's
effect (it is not a deterministic answer key) but does **not** clean the
affected figures: the passes that did occur cannot be attributed to
evidence-derived classification, and at least one judge scored a pass while
explicitly noting the root cause "matches the user's initial seed scenario
input."

---

## 7. RECOMMENDATIONS — how each historical figure should be labeled

No existing report file was edited to apply these labels; this is a decision
list for the human, to be executed as a separate approved follow-up.

| Figure / artifact | Recommended label going forward |
|---|---|
| 89.8% (44/49 judgeable) — `docs/gemini-groq-5-case-final-validation-2026-09-05.md:125` | **OBSERVED / CONTAMINATED — do not cite as clean accuracy evidence.** Label-in-prompt confirmed for the executing code and run artifacts. |
| 93.0% (66/71 judgeable) — `docs/groq-retry-active-5case-validation-2026-09-05.md:282-284` | **OBSERVED / CONTAMINATED — same basis as above.** The doc's own "NOT claimed for the retry" caveat (lines 340-343) already separates it from retry efficacy; the accuracy component is additionally contaminated. |
| 93.0% as re-cited in `docs/state-and-gap-analysis-2026-09-05.md:108` | Same label; that doc cites it as DOCUMENTED — add the contamination caveat when next revised. |
| 85.07% (57/67) — `agent-memory/evidence/evals-sequential-results-2026-09-04.json:2-30` | **OBSERVED / CONTAMINATED** (same code path). |
| "Perfect 20/20-row run" (GLM-era case-4) — `docs/case-4-parsing-failure-audit-2026-09-04.md:124` | **OBSERVED / CONTAMINATED** (run through the same `run_case`). |
| Raw-artifact aggregates — 0.00%, 16.00%, 68.00% (verify Experiment runs), 85.07% / "85.1%" (sequential), canary aggregates 12/15, 18/19, 13/15, 14/15 | **OBSERVED / CONTAMINATED** (same code path; §4 raw-artifact block). The 0.00% all-fail run carries no accuracy signal either way. |
| Per-evaluator judge scores (Output / Trajectory / ToolSelection / ToolParameter) in all run docs | Cite as **UPPER BOUNDS** on capability, per the exposure split in §5 — Output directly contaminated; Trajectory/ToolSelection partially; ToolParameter low-but-nonzero. |
| SafeActionCompliance `apply_correction`-clause results (0 unauthorized actions, all runs) | **UNAFFECTED — safe to cite as-is** (structural immunity, §5). The case-3 no-unnecessary-draft clause alone is an upper bound. |
| Case completion / rc=0 counts (5/5, 4/5, 2/5) | **UNAFFECTED as completion facts** — do not present as accuracy. |
| Retry figures (2/2/2/0; 3,766 tokens), OTel parity (125/125), infra token/cost totals | **UNAFFECTED — safe to cite as-is** as infrastructure/resilience measurements (note prompt-provenance on absolute token totals). |
| Fix scope (for the separate follow-up task, NOT this audit) | The injection is one construction site: `evals/run_evals.py:99-102`. Nothing else in the repo injects the label; no test asserts the instruction text (repo-wide grep of `tests/` for `Seed scenario`/`instruction`: no hits); the SDK-side `Original Task:` forwarding disappears automatically once the label leaves the instruction. Historical reruns under a clean instruction are the only way to re-baseline accuracy figures. Two hardening items discovered by this audit, same follow-up: (1) tools return unfiltered dicts — one `_comment`-style key inside a record/row would create a NEW leak (`tools/seed_data.py:89`, `tools/transactions.py:33,52`); (2) the trajectory rubric's "(see case metadata)" clause references data never sent to judges (`evals/run_evals.py:198-199` vs §2.6) — fix the rubric or wire the metadata. |

---

## 8. CLAIM CLASSIFICATION

Legend: **MEASURED (code)** = verified this task from current source (repo or
installed SDK, cited file:line). **MEASURED (git)** = verified this task from
git history/objects. **OBSERVED** = read from preserved runtime artifacts
(evidence JSON/logs). **DOCUMENTED** = recorded in a prior report, quoted
verbatim, not independently re-derived. **CALCULATED** = arithmetic/synthesis
of the above. **UNKNOWN** = not determinable from available evidence.

| # | Claim | Class | Basis |
|---|---|---|---|
| 1 | Instruction embeds `seed_scenario` verbatim | MEASURED (code) | `evals/run_evals.py:99-102` |
| 2 | `seed_scenario` ↔ `expected_output` 1:1 for all 5 cases | MEASURED (code) | `evals/cases.py:35/46, 59/72, 85/98, 112/123, 136/147` |
| 3 | Instruction is the detector's user prompt | MEASURED (code) | `orchestrator/graph.py:249`; SDK `graph.py:1216-1221` |
| 4 | Classifier + reporter receive `Original Task: <instruction>` on every case | MEASURED (code) | SDK `graph.py:1223-1244` (installed 1.54.0) |
| 5 | Tool returns never carry scenario labels / `_comment`s | MEASURED (code) | §2.5 citations |
| 6 | Evaluator-side `case.input` use is grader-only | MEASURED (code) | §2.6 citations |
| 7 | All 6 drivers route through the injection | MEASURED (code) | §2.7 table (+ archived pre-edit snapshot line 143) |
| 8 | Injection present since `b5e3c84`, byte-identical to HEAD; no unleaked runnable version ever existed | MEASURED (git) | pickaxe `-S`/`-G` over `evals/`; per-commit `git grep`; blob `0f2a85f` from `82d8271`→HEAD |
| 9 | 89.8% run executed the leaky blob | MEASURED (git artifacts) + OBSERVED | its `preflight.txt:12-24` (tracked diff = fix only) + case-01 judge rows 4-5 |
| 10 | 93.0% run executed the leaky blob | MEASURED (git artifacts) + OBSERVED | its `pre-run-git-status.txt` (evals/ unmodified) + case-01 rows 0-1, case-04 row 17 |
| 11 | Both figures are judge-row aggregates incl. Output rows | DOCUMENTED | the two docs' own §-definitions of rows/judgeable |
| 12 | Case-4 miss (UNKNOWN 0.32) occurred with leak present | DOCUMENTED + MEASURED (git artifacts) | `gemini-groq…md:120,278-282` + row 9 code-version evidence |
| 13 | Case-4 19/19 pass in retry-active run, judge citing "user's initial seed scenario input" | OBSERVED | case-04 `eval-rows.json` row 17 (line 175); doc :151, :309-311 |
| 14 | Retry/token/OTel figures measure infrastructure, not classification | MEASURED (code) + DOCUMENTED | `agents/retry.py` scope; retry-active doc §5-§10 framing |
| 15 | Exact wall-clock checkout of untracked-wrapper runs | UNKNOWN | untracked files carry no git history; bounded by each run's archived git state |
| 16 | Whether prompts contained the label in past runs (independent of code trace) | UNKNOWN from artifacts alone (prompts not preserved); settled by code trace + judge-artifact corroboration | `case-4-audit:126` finding 15; §3 |
| 17 | SDK behavior identical across all runs (no version drift) | MEASURED (git + venv) | `uv.lock` tracked, pins unchanged since bootstrap; single venv install 2026-09-04 06:48 |
| 18 | Per-tool judges see the label-bearing user turn; trajectory/output judges see `case.input` | MEASURED (code, installed evals SDK) | `trace_extractor.py:114-115`; `evaluator.py:233-245`; `case_prompt_template.py:32-54`; `output_evaluator.py:45-61` |
| 19 | Trajectory rubric's "(see case metadata)" clause is dead — metadata never reaches judges | MEASURED (code) | `evals/run_evals.py:198-199` vs `case_prompt_template.py:4-73` (no metadata embed) |
| 20 | Seed event log semantically encodes each answer (e.g. `REVERSAL_POSTED`, `MANUAL_STATUS_OVERRIDE` event types) | MEASURED (code/data) | `data/seed_transactions.json:67,78-81,86` — legitimate evidence by design; the leak adds the *label* on top of inferable evidence, so post-fix accuracy should not be expected to crater |
| 21 | Raw-artifact figures (0.00/16.00/68.00%, 85.07%, canary aggregates) all produced by the leaky path | OBSERVED + MEASURED (producers) | §4 raw-artifact block, with artifact file:line citations |
| 22 | Adversarial re-verification of claims 1-4 (this §8's claims 1,3,4,5-7) | MEASURED (independent pass, CONFIRMED on all four; no refutation found) | verification-pass citations folded into §1.4, §2.4, §2.5 |

Memory-vs-evidence discipline: session-memory notes (e.g. the case-4
`Parsing failed` history, the `create_case_ticket` null lottery, the retry
recovery counts) were used only as *pointers*. Every such claim in this
report is grounded in a cited repository artifact or doc line above; nothing
is asserted from conversational memory alone.

---

## 9. ZERO-MODIFICATION ATTESTATION

- **git status before** (captured at task start, HEAD `c5f5e13`,
  2026-09-05T13:56:05-05:00): 32 untracked entries (`agent-memory/evidence/…`
  run dirs and probe files, 3 `agent-memory/*.md`, 14 `docs/*.md`, 4
  `evals/*.py`, 4 `tests/test_*_offline.py`); zero tracked files modified.
  Full list preserved in the task transcript.
- **git status after** (captured at report completion, verified by count and
  diff): the identical 32 entries plus exactly this one new untracked file
  (`docs/eval-ground-truth-leak-audit-2026-09-05.md`) — 33 entries total,
  no tracked file touched, HEAD still `c5f5e13`, no stashes.
- **Full test suite NOT run** — this task is read-only and ran nothing that
  mutates state. **`scripts/verify.sh` NOT run** (its step 6 is the live
  benchmark — `EVAL_MODE=1 evals/run_evals.py` — explicitly out of scope).
  No benchmark, canary, eval driver, or live LLM/API call was executed. No
  configuration changed. Nothing committed, staged, or pushed.
- Application files named off-limits by the task (`agents/retry.py`, the
  three agent builders, `tools/case_management.py`, human-gate/executor
  code) were **read** (trace evidence only) and **not modified**.
- Subagent work (git archaeology, docs/evidence inventory, quote extraction,
  adversatorial re-verification) was read-only by instruction; no subagent
  reported any write.

---

*Audit executed 2026-09-05 by Claude Code (read-only session). Method:
direct source inspection + installed-SDK verification + git archaeology +
artifact inventory, with verbatim-quote and adversarial cross-checks run as
separate read-only subagents.*
