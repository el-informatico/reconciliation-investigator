# Eval ground-truth leak FIX — P0-A (2026-09-05)

Task: remove the ground-truth leak channels from the evaluation methodology
(code going forward only). Established facts come from
`docs/eval-ground-truth-leak-audit-2026-09-05.md`; nothing here re-litigates
them. No live LLM/API call, no benchmark, no canary was run for this fix; no
commit, stage, or push was performed.

Execution date: 2026-09-05. Baseline HEAD at task start: `e6770b5`.

---

## 1. PHASE 0 PROPOSAL (verbatim — the human's review artifact; not edited after implementation began)

### 1a. Current state re-confirmed (HEAD `e6770b5`, re-read in full this task)

**Item A — the injection.** `evals/run_evals.py:99-102`:

```python
    instruction = (
        f"Investigate the flagged discrepancy for customer_id={case.input['customer_id']}. "
        f"Seed scenario: {case.input['seed_scenario']}."
    )
```

This is the repo's ONLY instruction construction site (repo-wide grep:
`Seed scenario` occurs exactly here; every eval driver — `run_sequential.py:52`,
`token_canary.py:486`, `gemini_judge_canary.py:211`, `gemini_judge_5case.py:261`,
`groq_parsing_retry_canary.py:291` — routes through `run_evals.run_case`).
The label maps 1:1 to `expected_output` (`evals/cases.py:35/46, 59/72, 85/98,
112/123, 136/147`) and reaches the detector's user prompt verbatim, plus the
classifier's and reporter's via the SDK's `Original Task:` prefix
(`strands-agents 1.54.0`, `Graph._build_node_input`,
`.venv/.../strands/multiagent/graph.py:1216-1221` entry, `:1228` prefix).

**Item B — the unfiltered tool returns.** Four pass-through sites:

- `tools/legacy_system.py:21` — `return dict(record)`
- `tools/seed_data.py:89` — `record = dict(seed)` inside `effective_modern_record()`, returned to agents by `read_modern_system` (`tools/modern_system.py:41`)
- `tools/transactions.py:32-36` — `return [dict(row) for row in rows if …]` (`search_transactions`)
- `tools/transactions.py:52` — `return [dict(row) for row in per_entity.get(system, [])]` (`get_event_log`)

Precision statement (MEASURED two ways this task: static key-placement analysis
by two subagents, and a runtime enumeration of every key reachable through the
four read tools for all five customers): **no `_comment` key reaches an agent
today.** The seven `_comment` keys (`data/seed_transactions.json:2,22,32,42,49,
54,72`) sit as siblings of the returned sub-objects, and no returned record/row
currently contains one. Item B is therefore a LATENT channel — no key filter
exists anywhere, so a `_comment`-style key added *inside* a record or row would
flow verbatim into agent-visible tool output. This matches the audit's §2.5
fragility caveat / §7 hardening item 1. The task context's phrase "exposes a
seed-file key" is accurate about the channel (unfiltered) and must not be read
as "an agent saw a key at HEAD" — no agent did.

**Item C — the rubric defect.** `evals/run_evals.py:194-206`, the
`TrajectoryEvaluator` rubric; the defective clause at `:198-199`:

```
    3. Efficiency — was get_event_log skipped when search_transactions already
       explained the discrepancy (see case metadata)?
```

Installed `strands-agents-evals 1.2.0` `compose_test_prompt`
(`case_prompt_template.py:28-66`) embeds only `<Input>`, `<Output>`,
`<ExpectedOutput>`, `<Trajectory>`, `<ExpectedTrajectory>`,
`<TrajectoryDescription>`, environment state, and `<Rubric>` — `case.metadata`
is NEVER embedded in any judge prompt. The rubric directs the judge to consult
data it cannot see.

### 1b. Phase 0c sweep result — no additional channel (two independent read-only sweeps)

An eval-surface sweep (all six drivers, judge-prompt construction, cases,
tools, agents, orchestrator) and an adversarial product-path hunt (system
prompts, tool docstrings/specs, seed rows actually returned, gate/executor,
probes, runtime stores, SDK decorator output) **both concluded: beyond items
A–C, no other channel delivers ground-truth/answer-naming information to agent
input, and no judge receives answer-key data its scoring role does not require.**
Two reviewed, deliberately-NOT-changed observations:

1. **Judges see `case.input` — including `seed_scenario` — via `<Input>`
   (`include_inputs=True`, `run_evals.py:207,220`).** Grader-side by design:
   `OutputEvaluator` must compare against `expected_output` and
   `TrajectoryEvaluator` against `expected_trajectory`; the judge holding the
   answer key is what scoring IS (audit §2.6 ruling). Not equivalent in kind to
   A (the measurement-corrupting direction was agent-seees-key, not
   scorer-sees-key). Changing it would alter judge methodology — out of scope.
2. **Detector system-prompt example "look for a reversal specifically"**
   (`agents/detector_investigator.py:34`). Uniform across all five cases (a
   static module constant — zero per-case information), the classifier (the
   answer-producer) never sees the detector's prompt, and the file is
   contract-verbatim + on the task's do-not-touch list. Recorded as a
   limitation (§8), not changed.

Ruled out by the sweeps (non-exhaustive list): per-case prompt asymmetry (none
— prompts are static constants); tool specs leaking module/source (SDK sends
name+description+parameters only, `decorator.py:284-313`, `openai.py:518-525`);
`_comment` reaching agents today (structurally impossible — `.get(system)`
picks only row-list siblings); docstrings naming labels (none do);
gate/hint path at eval time (unused — `run_case` calls the graph directly);
runtime-store feedback loops (tickets/drafts are never read back into agent
input; the observed `runtime/tickets.jsonl` case_id
`"C-1001-reversal-not-propagated"` is a fossil of the OLD leak, not a channel);
a second instruction site (none).

### 1c. Proposed changes (file | current | proposed | rationale)

**Fix A — strip the label from the agent task string, keep the legitimate task.**

| File | Current | Proposed |
|---|---|---|
| `evals/run_evals.py:99-102` | the two-sentence f-string assigned to local `instruction` inside `run_case` (quoted in §1a) | new module-level function (placed after the `telemetry = …` line, before `run_case`), with `run_case` body reduced to calling it: |

```python
def build_instruction(case: Case) -> str:
    """The agent-visible task string — the customer pointer ONLY.

    This must never embed case.input['seed_scenario'] (or any other
    answer-naming field): that value maps 1:1 to expected_output, the
    entry node receives the task verbatim as its user prompt, and the
    installed SDK's "Original Task:" prefix (strands-agents 1.54.0,
    multiagent/graph.py Graph._build_node_input) forwards it into every
    downstream node's context — the ground-truth leak fixed 2026-09-05
    (docs/eval-ground-truth-leak-fix-2026-09-05.md, Phase 0 §1c Fix A).
    Hoisted to module level for the same reason as tools_called_in:
    tests/test_eval_ground_truth_leak.py asserts on THIS exact string.
    """
    return (
        f"Investigate the flagged discrepancy for customer_id={case.input['customer_id']}."
    )
```

```python
    instruction = build_instruction(case)
    result = graph(instruction)
```

Rationale: (i) Leak-free — `seed_scenario` is no longer rendered into the task
string anywhere; because this is the single construction site and the SDK
prefix forwards only the task itself, removing it here removes it from the
detector's, classifier's, and reporter's contexts simultaneously (no other
driver or file constructs an instruction — verified §1a). (ii) Preserves the
legitimate function — the customer pointer is the only case-specific datum the
detector needs; `docs/build-contract.md:44` prescribes only "You are given a
customer_id where a discrepancy was flagged"; the engine test harness already
drives the graph with exactly this label-free form
(`tests/test_graph_engine.py:88`), confirming the product never needed the
scenario sentence. `flagged_discrepancy` is deliberately NOT added to the
instruction (it was never agent-visible before; adding it would be a
methodology change beyond this task's scope).

**Fix B — enforce an annotation-proof agent boundary on all four read tools.**

| File | Current | Proposed |
|---|---|---|
| `tools/seed_data.py` (new helper, after `effective_modern_record`) | — | `strip_seed_annotations(obj)` (below) |
| `tools/legacy_system.py:21` | `return dict(record)` | `return strip_seed_annotations(record)` |
| `tools/modern_system.py:41` | `return effective_modern_record(customer_id)` | `return strip_seed_annotations(effective_modern_record(customer_id))` |
| `tools/transactions.py:32-36` | `return [dict(row) for row in rows if …]` | wrap the comprehension's result in `strip_seed_annotations(…)` |
| `tools/transactions.py:52` | `return [dict(row) for row in per_entity.get(system, [])]` | wrap in `strip_seed_annotations(…)` |

```python
def strip_seed_annotations(obj):
    """Recursively copy obj with every '_'-prefixed dict key removed.

    Seed-file annotation keys (_comment today, any _-prefixed author
    note later) are provenance for humans, never evidence for agents.
    Every read tool routes its return through this, so an annotation
    placed inside a record or row can never reach agent context,
    whatever the seed file looks like — previously clean returns were
    an accident of key placement, not an enforced invariant (audit
    §2.5 fragility caveat; fix doc Phase 0 §1c Fix B). Returns a new
    structure; the lru_cache'd seed is never mutated. No legitimate
    field in data/seed_transactions.json starts with '_' (pinned by
    tests/test_eval_ground_truth_leak.py).
    """
    if isinstance(obj, dict):
        return {
            key: strip_seed_annotations(value)
            for key, value in obj.items()
            if not str(key).startswith("_")
        }
    if isinstance(obj, list):
        return [strip_seed_annotations(item) for item in obj]
    return obj
```

Rationale: (i) Leak-free — the class of seed-file annotation keys
(`_`-prefixed by the file's own convention) can never appear in any dict a
tool returns to an agent, including nested ones (event `payload`), regardless
of future seed edits; enforced exactly at the agent boundary ("what a tool
returns"), not inside the data layer. (ii) Preserves function — every
legitimate field passes through untouched: runtime enumeration this task
shows the reachable key set is exactly {CUSTOMER_ID, BALANCE, STATUS,
LAST_UPDATED} ∪ {customerId, balance, status, lastUpdated} ∪ {transaction_id,
type, amount, timestamp, related_transaction_id} ∪ {event_id, event_type,
timestamp, payload + payload.*} — none starts with `_`; the sanitizer copies
rather than mutates, so the cached seed is safe; the runtime override overlay
(`_applied_at` bookkeeping in `effective_modern_record`) is internal and never
copied into records, and `read_modern_system`'s return is sanitized after the
overlay, preserving read-your-writes semantics. `tools/case_management.py`
constructs its returns from agent-supplied arguments only (no seed data
flows through it) and is on the do-not-touch list — unchanged.

**Fix C — make the trajectory rubric reference only data the judge receives.**

| File | Current | Proposed |
|---|---|---|
| `evals/run_evals.py:198-199` | `3. Efficiency — was get_event_log skipped when search_transactions already\n       explained the discrepancy (see case metadata)?` | `3. Efficiency — was get_event_log skipped when search_transactions already\n       explained the discrepancy?` |

Rationale: (i) the parenthetical is removed entirely — the judge never
receives `case.metadata` (installed `compose_test_prompt` embeds no metadata),
so the rubric no longer instructs it to consult unavailable data; (ii) the
criterion itself survives unchanged and is fully judgeable from what the judge
DOES receive — the `<Trajectory>` block contains the tool calls and their
results, which is exactly what "did search_transactions already explain the
discrepancy" asks about. (Choosing removal over "wire metadata in": wiring
metadata into judge prompts would ADD answer-bearing data (`notes`,
`root_cause_category`) to judge input — the opposite of this task's direction.)

**Fix D (Phase 0c findings) — none required.** §1b documents the two
reviewed non-changes and the ruled-out list; no code change proposed beyond
A, B, C.

**Non-changes guaranteed by this proposal:** `evals/cases.py` untouched
(the answer key — `seed_scenario` values, `expected_output`, metadata, order —
stays byte-identical); agents/*, tools/case_management.py, orchestrator/*,
human-gate/executor/capability-token code untouched; provider architecture,
model selection, judge separation, `agents/retry.py` untouched; no historical
report edited.

### 1d. Phase 2 test plan (preview; details in §5)

New module `tests/test_eval_ground_truth_leak.py` (offline; hermetic dummy
`GROQ_API_KEY` set before importing `evals.run_evals` — the provider client
is constructed lazily per request, so no live call is possible):

1. For each of the five cases: `build_instruction(case)` contains the
   customer_id, and contains NONE of the ten label spellings (all five
   `seed_scenario` + all five `expected_output` values — cross-case), nor
   `Seed scenario` / `seed_scenario`.
2. The SDK-propagated form (`"Original Task: {task}"` + the exact block
   sequence `graph.py:1228-1244` assembles) carries no label.
3. All four read tools, all five customers, both systems: returns contain
   only legitimate fields (allowlist), no `_`-prefixed key anywhere
   (recursive), no label string in the serialized returns.
4. Poisoned-seed variant: `_comment` planted INSIDE a legacy record, a modern
   record, a transaction row, and an event payload — tools still return
   annotation-free data (proves the FILTER is the invariant, not today's key
   placement).
5. `run_evals.trajectory_evaluator.rubric` contains neither "(see case
   metadata)" nor the word "metadata", and still carries the efficiency
   criterion (get_event_log/search_transactions).
6. The answer key is pinned byte-for-byte: the five (name, customer_id,
   seed_scenario, expected_output) tuples and `metadata.root_cause_category`
   must equal literal constants — any drift fails loudly.

Full suite (`uv run --locked pytest -q`) run before (132 passed, captured
before any edit) and after; zero regressions expected outside the new tests.

---

## 2. PHASE 1 vs PHASE 0 PROPOSAL — conformance

**Matched exactly; zero deviations.** The applied diff (§3) is code-for-code
the §1c proposal: same `build_instruction` text (docstring included), same
`run_case` reduction, same rubric deletion, same `strip_seed_annotations`
helper, same four tool-boundary applications, same files and no others.
§1d was labeled a preview; the implemented test module (§5) covers all six
previewed items plus two strictly-stronger assertions (`"seed_scenario"`
absent from the instruction; the planted note's text absent from poisoned
returns). No proposal revision was needed mid-implementation.

## 3. EXACT DIFFS APPLIED (tracked files; `git diff` verbatim at completion)

5 files changed, 53 insertions(+), 12 deletions(-):

| File | Change (new line numbers) |
|---|---|
| `evals/run_evals.py` | + `build_instruction(case)` at `:83-100` (module level, after `telemetry`); `run_case` instruction block `:99-102` (old) → `instruction = build_instruction(case)` at `:117`; rubric `:198-199` (old) → `:213-214` — ` (see case metadata)` deleted |
| `tools/seed_data.py` | + `strip_seed_annotations(obj)` at `:103-127` (recursive `_`-prefix key stripper; copies, never mutates the cached seed) |
| `tools/legacy_system.py` | `:21` `return dict(record)` → `return strip_seed_annotations(record)`; import extended `:5` |
| `tools/modern_system.py` | `:42` `return effective_modern_record(customer_id)` → `return strip_seed_annotations(effective_modern_record(customer_id))`; import extended `:26` |
| `tools/transactions.py` | `:32-36` and `:52` — both list comprehensions wrapped in `strip_seed_annotations(…)`; import extended `:5` |

Before/after for the three substantive sites:

```diff
--- evals/run_evals.py (run_case)
-    instruction = (
-        f"Investigate the flagged discrepancy for customer_id={case.input['customer_id']}. "
-        f"Seed scenario: {case.input['seed_scenario']}."
-    )
+    instruction = build_instruction(case)
     result = graph(instruction)

--- evals/run_evals.py (TrajectoryEvaluator rubric)
     3. Efficiency — was get_event_log skipped when search_transactions already
-       explained the discrepancy (see case metadata)?
+       explained the discrepancy?

--- tools/legacy_system.py
-    return dict(record)
+    return strip_seed_annotations(record)
```

(`build_instruction` and `strip_seed_annotations` bodies are quoted in full
in §1c and landed verbatim.)

## 4. ANSWER KEY BYTE-IDENTITY

`git diff --exit-code evals/cases.py` → **empty** (byte-identical to HEAD
`e6770b5`, which is also the pre-task state: zero tracked modifications
existed at task start). The five cases' `seed_scenario` values,
`expected_output` values, order, and metadata are untouched. Enforced
permanently by `test_frozen_answer_key_is_byte_identical`
(`tests/test_eval_ground_truth_leak.py`), which pins all five
(name, customer_id, seed_scenario, expected_output) tuples and
`metadata.root_cause_category` as literals.

## 5. REGRESSION TESTS AND SUITE COUNTS

New module: `tests/test_eval_ground_truth_leak.py` — 18 tests:

| # | Test | Proves |
|---|---|---|
| 1-5 | `test_instruction_carries_no_ground_truth_label[case]` | Fix A: for each case, `build_instruction` keeps the customer_id, carries none of the TEN label spellings (all five cases' snake + UPPER forms — cross-contamination proof), no `Seed scenario`, no `seed_scenario` |
| 6-10 | `test_sdk_original_task_propagation_carries_no_label[case]` | Fix A propagation: the exact block sequence the installed SDK assembles (`"Original Task: {task}"` + `"Inputs from previous nodes:"` + dep blocks, `graph.py:1228-1244`) carries no label |
| 11-15 | `test_read_tool_returns_are_annotation_free[case]` | Fix B on the real seed: all four read tools, all five customers, both systems — returns within the legitimate-field allowlist, no `_`-prefixed key at ANY nesting depth, no label string in serialized returns |
| 16 | `test_key_filter_survives_a_poisoned_seed` | Fix B substance: `_comment` planted inside a legacy record, modern record, transaction row, AND event payload — tools still return annotation-free data (the pre-fix pass-throughs would have forwarded it verbatim) |
| 17 | `test_trajectory_rubric_references_no_unsent_data` | Fix C: rubric has neither "(see case metadata)" nor the word "metadata"; the efficiency criterion (get_event_log/search_transactions) survives |
| 18 | `test_frozen_answer_key_is_byte_identical` | §4, as a permanent pin |

**Full-suite counts** (`uv run --locked pytest -q`, = verify.sh step 5; all
offline, no live calls):

- **Before any edit: 132 passed** (exit 0, 5.83s) — captured prior to the
  first code change.
- **After the fix: 150 passed** (exit 0, 5.31s) = 132 + 18 new.
  **Zero regressions** (no pre-existing test failed or changed).
- `scripts/guard-segregation-of-duties.sh` → PASS (the diff touches
  `tools/`; no `apply_correction` adjacency).
- Driver-import sanity: `evals.run_sequential` (all six imported names) and
  the new `build_instruction` import cleanly offline.

**Negative control (proof the tests detect the leak):** the Phase 1 source
changes were temporarily stashed (`git stash push -- <5 files>`; untracked
files and `evals/cases.py` never stashed; popped immediately; stash count 0
before and after) and the new module was run against the pre-fix code:
**12 failed, 6 passed**, with exactly the expected modes — 10 ×
`AttributeError: module 'evals.run_evals' has no attribute 'build_instruction'`
(the pre-fix module offers no label-free construction path at all),
1 × `annotation key '_comment' reached a tool return` (Fix B detector fires),
1 × `'(see case metadata)' not in rubric` failed (Fix C detector fires).
The 6 pre-fix passes are the 5 real-seed tool tests (today's seed really is
clean — the LATENT characterization of item B, §1a) and the frozen-key test
(correct both ways by design).

## 6. SCOPE STATEMENT — GOING FORWARD ONLY

This fix changes evaluation methodology **going forward only**. It does NOT
retroactively validate or invalidate any historical figure. The figures
**89.8%** (44/49), **93.0%** (66/71), **85.07%** (57/67), **68%**, **16%**,
the "20/20" GLM run, and every other root-cause-dependent accuracy figure in
`docs/` remain flagged per `docs/eval-ground-truth-leak-audit-2026-09-05.md`
as **MEASURED but methodologically contaminated — not usable as clean
accuracy evidence**, pending a separate clean rerun (**P0-B**, explicitly
not part of this task). No existing historical report was edited, relabeled,
or disclaimed in this task (deliberately deferred, as instructed).

## 7. ADDITIONAL CHANNELS (Phase 0c / Phase 1 item 4)

**None found; none fixed beyond A, B, C.** Two independent read-only sweeps
(eval-surface + adversarial product-path; §1b) found no further agent-input
channel and no judge input that its scoring role does not require. The two
reviewed non-changes (judges' grader-side `<Input>` access to
`case.input`/`seed_scenario`; the detector prompt's uniform "look for a
reversal specifically" example) are documented with rationale in §1b and
remain unchanged. Evidence standard for these conclusions: direct source
quotes at file:line from the repo and the installed SDK packages
(strands-agents 1.54.0, strands-agents-evals 1.2.0), plus a runtime
enumeration of every key reachable through the four read tools for all five
customers (zero `_`-prefixed keys reachable at HEAD).

## 8. LIMITATIONS — stated as UNKNOWN, not assumed clean

1. **No post-fix live run exists yet** (by task constraint). That the fixed
   harness produces label-free trajectories at runtime is established
   code-path-wise (instruction is the sole agent-input carrier of the task;
   SDK forwards only it), but an OTel-observed run has not been executed —
   the first clean benchmark (P0-B) is the empirical confirmation. UNKNOWN:
   how agent behavior changes without the label (more cycles, different tool
   patterns, lower completion) — that is the measurement P0-B exists to take.
2. **Judges remain label-sighted** (`<Input>` carries `case.input` incl.
   `seed_scenario`; `<ExpectedOutput>`/`<ExpectedTrajectory>` by design).
   Ruled grader-legitimate (§1b, audit §2.6); a label-blind judging design
   would be a separate methodology decision, not a leak fix.
3. **The `_`-prefix convention is the enforced boundary**, not a full
   field allowlist in production code: a future seed annotation key that
   does NOT start with `_` inside a record would still pass through. The
   allowlist ASSERTION in the tests catches it for the four known shapes;
   the sanitizer alone would not. (Audit §7 hardening item 1 is satisfied
   for the annotation convention the seed file actually uses.)
4. **The detector prompt's reversal example** (`agents/detector_investigator.py:34`)
   stays: byte-verbatim contract prompt, uniform across all five cases (no
   per-case information), and on the task's do-not-touch list. Assessed
   BENIGN by the adversarial pass; not zero-influence in principle.
5. **C-1004's `MANUAL_STATUS_OVERRIDE` event type** remains the
   nearest-to-literal label echo inside returned evidence — standing ruling
   (audit claim 20): designed discriminative evidence, not a leak. If that
   ruling is ever re-litigated, that row is the deciding case.
6. **Historical run prompts were never preserved** (audit §3 caveat), so
   pre-fix contamination is proven by code trace + judge-artifact
   corroboration, not by stored prompts — unchanged by this task.
7. **The `trajectory_description` dead parameter** observed in the installed
   TrajectoryEvaluator (accepted but never sent) is an SDK quirk noted
   during research; it plays no role in this fix and was left untouched.

## 9. CLAIM CLASSIFICATION

| # | Claim | Class | Basis |
|---|---|---|---|
| 1 | Injection existed at `run_evals.py:99-102`; now removed | MEASURED | §1a quote; §3 diff; post-fix grep: `Seed scenario` occurs in no repo code — only the regression test's negative assertions and the audit/fix reports quoting the old line |
| 2 | `seed_scenario` ↔ `expected_output` 1:1, all five cases | MEASURED | `evals/cases.py:35/46, 59/72, 85/98, 112/123, 136/147` (re-read this task) |
| 3 | One instruction site serves all six drivers | MEASURED | repo-wide greps + driver import graph (two subagents, this task) |
| 4 | SDK forwards `Original Task: {task}` to every non-entry node (1.54.0) | MEASURED | installed `graph.py:1216-1221, 1228-1244`, re-verified this task |
| 5 | Judge prompts never embed `case.metadata` | MEASURED | installed `case_prompt_template.py:28-66` |
| 6 | Item B was LATENT at HEAD (no `_comment` reached agents) | MEASURED | runtime enumeration of all reachable keys (this task) + two independent static analyses |
| 7 | Filter now enforces annotation-free returns | MEASURED | poisoned-seed test passes post-fix, fails pre-fix (§5) |
| 8 | Rubric no longer references unsent data | MEASURED | rubric test passes post-fix, fails pre-fix (§5) |
| 9 | Answer key byte-identical pre/post | MEASURED | empty `git diff` on `evals/cases.py` + pinned test 18 |
| 10 | Suite 132 → 150, zero regressions | MEASURED | both runs executed this task, exit 0 |
| 11 | Negative control: 12 fail / 6 pass pre-fix, with stated modes | MEASURED | stash-cycle run (§5); stash count 0 after restore |
| 12 | No additional agent-input channel exists | CALCULATED (from exhaustive sweeps) | two independent read-only sweeps, no refutation found; residual risk per §8 |
| 13 | All live drivers converge on the fixed `run_case` | MEASURED | §1a; driver import sanity run |
| 14 | Future-run trajectories will be label-free at runtime | PROJECTED | follows from 1+3+4 code-wise; not yet OTel-observed (§8.1) |
| 15 | Historical figures remain contaminated/not clean evidence | DOCUMENTED | audit §7 table; unchanged by this task |
| 16 | Post-fix accuracy/completion outcomes | UNKNOWN | P0-B's job; nothing measured here predicts them |

## 10. GIT STATUS — before / after

- **Before** (task start): HEAD `e6770b5c497a4abf9620e76497ec7c14cadc51da`;
  0 tracked files modified; 0 staged; 0 stashes; 33 untracked entries
  (pre-existing evidence/report/driver/test files).
- **After** (completion): HEAD unchanged `e6770b5`; **5 tracked files
  modified** (`evals/run_evals.py`, `tools/legacy_system.py`,
  `tools/modern_system.py`, `tools/seed_data.py`, `tools/transactions.py` —
  exactly the §1c/§3 fix set); **35 untracked** = the same 33 + this report
  (`docs/eval-ground-truth-leak-fix-2026-09-05.md`) +
  `tests/test_eval_ground_truth_leak.py`; **0 staged; 0 stashes**
  (negative-control stash pushed and popped in full, verified count 0).
- **Nothing committed, staged, or pushed.** No live LLM/API call, no
  benchmark, no canary, no verify.sh step 6 was executed at any point
  (offline gates run: pytest = step 5; segregation guard = step 2).

---

*Fix executed 2026-09-05 by Claude Code. Method: first-hand re-reading of
the full affected surface + four delegated read-only investigations
(eval-surface leak sweep; installed-SDK propagation/judge-prompt mechanics;
test-strategy/offline-import feasibility; adversarial product-path hunt),
synthesized into the frozen §1 proposal, implemented exactly, and verified
by a 18-test offline regression module including a pre-fix negative control.*
