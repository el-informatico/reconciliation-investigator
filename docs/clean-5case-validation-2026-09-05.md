# P0-B — First Clean Five-Case Validation (post ground-truth-leak fix)
> AMENDED 2026-09-07: this report references the agent-memory/ directory, which was removed from repository history by the 2026-09-07 excision rewrite; those artifacts are retained only in the author's private local archive, never in this repository.

Date: 2026-09-05 · Driver: `evals/gemini_judge_5case.py` · Result: **GO WITH CAVEAT**

Purpose: produce the FIRST methodologically clean accuracy number for the
reconciliation-investigator agents after the P0-A ground-truth-leak fix
(`docs/eval-ground-truth-leak-fix-2026-09-05.md`). Every historical figure
(89.8%, 93.0%, 85.07%, 68%, 16%, GLM 20/20) is MEASURED but contaminated —
this run is a NEW BASELINE, not a replication.

Evidence tree: `agent-memory/evidence/clean-5case-validation-2026-09-05/`
(`preflight.txt`, `run.log`, 5 case dirs, `index.json`,
`retry-evidence-run.json`, `make-analysis-digest.py`, `analysis-digest.json`).

**Headline (all MEASURED/CALCULATED from this single run):**

| Metric | Value |
|---|---|
| Cases completed (rc=0) | 5/5 |
| Eval rows: raw pass rate | **67/81 = 82.7%** |
| Eval rows: judgeable pass rate (excl. 3 Gemini-503 judge-error rows) | **67/78 = 85.9%** |
| Root-cause classification | **4/5 = 80.0%** (case 2 → `UNKNOWN`) |
| Segregation-of-duties (SafeAction) | 5/5 safe |
| Total tokens (agents + judges) | 313,842 |
| End-to-end wall clock | 586 s (20:29:33Z → 20:39:19Z) |

---

## 1. Phase 0 findings (pre-live gate — all completed BEFORE any live call)

### 1a. The six evaluation drivers (0a)

All drivers live under `evals/`; none anywhere else (probes/ make raw provider
calls with no graph/cases; verified by repo-wide grep — DOCUMENTED).

| # | Driver file | Purpose | Uses `build_instruction()`? | Live? | Judges | Last used for |
|---|---|---|---|---|---|---|
| 1 | `evals/run_evals.py` | Original Experiment driver: 5 frozen cases through the real Strands Graph, 5 evaluators; `__main__` `:254-265`; verify.sh step 6 | **Defines it** (`:83-98`), calls it at `:117` | Live (Groq + Groq) | 4 LLM judges on shared Groq model + SafeAction | verify.sh step-6 runs; GLM-era "20/20" |
| 2 | `evals/run_sequential.py` | Same cases/evaluators via SDK per-row API | Indirectly — `run_case` at `:52` | Live (Groq + Groq) | Same 4 Groq judges | 2026-09-04: 85.07% (57/67), case-4 20/20 |
| 3 | `evals/token_canary.py` | One-case token canary; hosts shared engine `run_one_case()` (`:436-578`) | Indirectly — `:486` | Live (Groq + Groq) | Wrapped Groq | `docs/token-workload-canary-2026-09-04.md` |
| 4 | `evals/gemini_judge_canary.py` | One-case judge-split canary; exports Gemini machinery + pacer | Indirectly — `:211-216` | Live (Groq + Gemini) | **Native Gemini** 4.3 s pacer | `docs/gemini-judge-canary-2026-09-04.md`, `docs/correction-draft-id-fix-canary-2026-09-04.md` |
| 5 | `evals/gemini_judge_5case.py` | **The "5-case validation" driver** | Indirectly — `:261-266` | Live (Groq + Gemini) | **Native Gemini** | **All three 5-case reports** |
| 6 | `evals/groq_parsing_retry_canary.py` | ONE-SHOT single-case retry canary | Indirectly — `:291` | Live (Groq + Gemini) | Native Gemini | `docs/groq-parsing-retry-canary-2026-09-05.md` |

Funnel (verified by direct read, MEASURED): every driver terminates at
`run_evals.run_case` (`evals/run_evals.py:101-124`) — the ONLY production call
site of `build_instruction()` (`:117`), passed verbatim to `graph(...)`
(`:118`). `token_canary.run_one_case` passes the case object through with zero
string handling (`evals/token_canary.py:486`). No other task-string
constructor exists in `evals/`, `agents/`, `orchestrator/`, `scripts/`,
`probes/`.

### 1b. Test-coverage determination (0b)

`tests/test_eval_ground_truth_leak.py` (pre-P0-B): 6 functions / 18 instances:

| Test (file:line) | Instances | Level |
|---|---|---|
| `test_instruction_carries_no_ground_truth_label` (`:109-118`) | 5 | Direct-shared: asserts on `build_instruction()` output |
| `test_sdk_original_task_propagation_carries_no_label` (`:123-137`) | 5 | Direct-shared + hand-assembled SDK propagation (literals verified vs installed strands-agents 1.54.0 `graph.py:1228-1244`) |
| `test_read_tool_returns_are_annotation_free` (`:142-160`) | 5 | Tool-return: real tools, real seed |
| `test_key_filter_survives_a_poisoned_seed` (`:165-191`) | 1 | Tool-return, adversarial `_comment` planting |
| `test_trajectory_rubric_references_no_unsent_data` (`:196-203`) | 1 | Rubric: `(see case metadata)` absent |
| `test_frozen_answer_key_is_byte_identical` (`:208-215`) | 1 | Anti-drift pin on the 5 identity tuples |

Leak signal: the 10 exact label spellings (`LEAK_STRINGS` `:47-50`), cross-case,
plus `"Seed scenario"`/`"seed_scenario"`.

**Determination:** FULL STRUCTURAL COVERAGE at the shared-function level (all
six drivers covered by inheritance — none has its own construction site), BUT
no test exercised any driver's invocation path: nothing proved `run_case`'s
body cannot mutate the instruction between construction and `graph(...)`.
Under the task's 0d rule this is a coverage gap at the selected driver's call
site.

### 1c. Driver selection (0c)

**Selected: `evals/gemini_judge_5case.py`** (DOCUMENTED/MEASURED):
1. Routes through the fixed path — `main()` `:251-266` →
   `token_canary.run_one_case` (`:436`, untouched pass-through at `:486`) →
   `run_evals.run_case` → `build_instruction()` (`run_evals.py:117`).
2. Historical 5-case convention — all three prior reports name it verbatim
   (`docs/gemini-judge-5-case-validation-2026-09-04.md:48`,
   `docs/gemini-groq-5-case-final-validation-2026-09-05.md:10-13`,
   `docs/groq-retry-active-5case-validation-2026-09-05.md:52,86-90`).
3. Provider architecture preserved — Groq `openai/gpt-oss-120b` agents
   (`GROQ_API_KEY` only) + native `GeminiModel` `gemini-3.1-flash-lite` judges
   (`GEMINI_API_KEY` only), 4.3 s module-global pacer, no Gemini retries,
   `GroqParsingFailedRetryStrategy` active unmodified.

### 1d. Gap closure (0d)

Per 0d(i), one narrow test appended to `tests/test_eval_ground_truth_leak.py`:
`test_run_case_hands_the_clean_instruction_to_the_graph` (5 parametrized
instances) — monkeypatches `orchestrator.graph.build_reconciliation_graph`,
`run_evals.telemetry`, `run_evals.StrandsInMemorySessionMapper` with offline
fakes, executes `run_evals.run_case(case)` (the choke point every driver
passes through) and asserts on the string captured at the `graph(...)` call
site: customer pointer present, all 10 label spellings absent (cross-case),
`"Seed scenario"`/`"seed_scenario"` absent, graph invoked exactly once,
packaging contract intact. `run_case`'s function-local import
(`evals/run_evals.py:106`) resolves the patched module attribute at call time,
so the patches bind to the real production path (Architect-verified).

Suite results (MEASURED): module 23 passed (18 + 5 new) in 0.94 s; full suite
**155 passed** (P0-A baseline 150), 5.41 s / 5.33 s — zero regressions;
`scripts/guard-segregation-of-duties.sh .` → exit 0.

### 1e. Git baseline (0e)

MEASURED before any live call: `main` in sync with `origin/main`, HEAD
`e6770b5` [CORRECTED 2026-09-07 — hash typo in the original; refers to pre-rewrite c5f5e13] (`e6770b5`, "Add bounded retry for
Groq parsing failures"); nothing staged; 5 modified tracked files =
exactly P0-A's uncommitted fix set (`evals/run_evals.py`,
`tools/legacy_system.py`, `tools/modern_system.py`, `tools/seed_data.py`,
`tools/transactions.py`); `.env`/`uv.lock` unmodified; no discrepancy vs the
P0-A post-fix state.

### 1f. Additional Phase 0 gates

- **Security/reliability review** (delegated, cited): PASS on all gates — no
  secrets in diff/evidence (patterns scanned; dummies/false positives only);
  guard exit 0 + manual multi-line check of all three `Agent(` builders;
  diff = exactly the three intended P0-A changes; `evals/cases.py` +
  `data/seed_transactions.json` byte-identical to HEAD; `agents/retry.py`,
  agent builders, `tools/case_management.py` untouched uncommitted. Advisory
  (WARN-1): canaries read `GEMINI_API_KEY` from repo `.env` via the app's
  authorized loader (`agents/model.py:34-48`); values never printed.
- **Architect gate**: **Tier B, PROCEED with conditions** — test verified as
  binding to the real production path, hermetic, below every Tier C boundary;
  conditions (offline suite green before spend; exactly one invocation; no
  provider/methodology swaps on failure; scope firewall; no commit/stage/push;
  report records HEAD + dirty files) — all adopted and met.
- **Adversarial pre-flight verification** (delegated, independent): CONDITIONAL
  GO — command form identical to both successful 2026-09-05 runs; fresh
  out-dir; both key NAMES in `.env`; overlay fully cached; `GEMINI_MIN_INTERVAL_S`
  unset → default 4.3 s; retry strategy sha256-identical to the last historical
  run; no import-time requests; case order pinned by code + offline test.
  Corrections adopted: `runtime/consumed_tokens.jsonl` NOT on this path
  (gate-only write site; confirmed untouched post-run, mtime 2026-09-04);
  `drafts.jsonl`/`tickets.jsonl` appended and gitignored (`.gitignore:37`);
  `index.json` carries the driver's hardcoded label `"gemini-judge-5-case-2026-09-04"`
  (`gemini_judge_5case.py:287`), as in both prior Sep-5 runs.

---

## 2. Benchmark configuration and case order (confirmed as specified)

- Command (executed EXACTLY ONCE, from repo root — MEASURED, `preflight.txt`/`run.log`):
  ```
  timeout 2400 uv run --frozen --with google-genai==2.22.0 \
      python -m evals.gemini_judge_5case \
      --out-dir agent-memory/evidence/clean-5case-validation-2026-09-05
  ```
- Agents: Groq `openai/gpt-oss-120b`, `GROQ_API_KEY` only (confirmed in
  `index.json`: agent_provider=groq).
- Judges: native `GeminiModel` `gemini-3.1-flash-lite`, `GEMINI_API_KEY` only
  (index.json: judge_provider=google); pacer 4.3 s, module-global, no Gemini
  retries; deterministic SafeAction untouched.
- Retry: `GroqParsingFailedRetryStrategy` active, unmodified (index.json
  records it; sha256-pinned in `preflight.txt`).
- Case order — literal `evals/cases.py` order (`:32,56,82,109,133`), no
  sort/shuffle, each exactly once, no rerun path; OBSERVED identical in
  `index.json` and `run.log` line 3:
  1. `reversal-not-propagated` 2. `duplicate-transaction`
  3. `sync-lag-self-resolving` 4. `manual-override-not-reflected`
  5. `data-entry-error`
- Methodology deltas vs historical runs (the intended ones only, DOCUMENTED):
  instruction = customer pointer only; tool returns strip `_`-prefixed keys;
  trajectory rubric references no unsent metadata.
- Timing: LAUNCH_UTC 2026-09-05T20:29:33Z → END_UTC 20:39:19Z = **586 s**
  end-to-end (MEASURED). Per-case `wall_clock_seconds` as recorded: 157.0 /
  73.0 / 113.9 / 138.6 / 152.8 s (sum 635.3 s — the summary field's sum
  exceeds the end-to-end window by 49.3 s; cause UNKNOWN, an accounting
  artifact of the field; token counts are unaffected and cross-check to OTel
  at delta=0).

---

## 3. Case-by-case completion status (incl. parse-retry disclosure)

All 5 cases completed rc=0; driver exit 0; single execution (MEASURED).

| # | Case | rc | Wall (s) | Requests (succ/err) | Parse-retry classification |
|---|---|---|---|---|---|
| 1 | reversal-not-propagated | 0 | 157.0 | 32 (29/3) | **clean** — no `Parsing failed` event (2 Groq throttles recovered by stock retry; 1 Gemini 503 judge-error — infra, not parse) |
| 2 | duplicate-transaction | 0 | 73.0 | 20 (18/2) | **clean** — no parse event (2 Gemini 503 judge-errors — infra) |
| 3 | sync-lag-self-resolving | 0 | 113.9 | 28 (28/0) | **clean** — zero errors of any kind |
| 4 | manual-override-not-reflected | 0 | 138.6 | 32 (31/1) | **classified retryable → retried → recovered — NOT clean** (see below) |
| 5 | data-entry-error | 0 | 152.8 | 28 (28/0) | **clean** — zero errors of any kind |

**Parse-retry event record (the single event; MEASURED from
`retry-evidence-run.json`, case-4 `retry-evidence.json`, token-usage.jsonl,
run.log WARNING):**
- Case: 4 (`manual-override-not-reflected`); component: `agent.detector`;
  attempt: request_number 5 (2026-09-05T20:34:55.356Z).
- Observed error text (verbatim head): `"Parsing failed. The model generated
  output that could not be parsed. Please adjust your prompt. See
  'failed_generation' for more details."` — exception type `APIError`.
- Classification: retryable (exact known signature; matcher not broadened);
  ledger `classification_count: 1`.
- Retry outcome: retried (next same-component request_number 6) → **recovered**
  (`status=success`); additional tokens consumed by the recovery attempt:
  1,112 (input 1,056 / output 56); the failed attempt contributed 0 (no usage).
- Case completion: rc=0, all evaluators ran (18/19 rows passed).
- Exhaustions: 0. New-signature (unclassified) parse events: 0 — the digest's
  5 "Parsing failed" text hits are all records of this same single event
  (run.log WARNING + retry-evidence copies), not additional events.

No case was rerun. No infra failure triggered any rerun (none needed: the 3
Gemini 503s are judge-side, recorded as `judge-error` rows per design).

---

## 4. Root-cause classification results (the number this task exists for)

Source: OutputEvaluator rows in each case's `eval-rows.json` (MEASURED).
"Actual" is the root cause the judge quotes from the run's output.

| # | Case | Expected | Actual | Match |
|---|---|---|---|---|
| 1 | reversal-not-propagated | `REVERSAL_NOT_PROPAGATED` | `REVERSAL_NOT_PROPAGATED` (judge: "correctly identifies… clear, specific evidence citations", label EXCELLENT) | **Y** |
| 2 | duplicate-transaction | `DUPLICATE_TRANSACTION` | `UNKNOWN` (judge: "the model explicitly stated that it lacked the evidence required to make an informed decision") | **N** |
| 3 | sync-lag-self-resolving | `SYNC_LAG` | `SYNC_LAG` (specific txn/event IDs cited, label SUCCESS) | **Y** |
| 4 | manual-override-not-reflected | `MANUAL_OVERRIDE` | `MANUAL_OVERRIDE` (specific event IDs/timestamps cited, label EXEMPLARY) | **Y** |
| 5 | data-entry-error | `DATA_ENTRY_ERROR` | `DATA_ENTRY_ERROR` (judge notes reporter-section ID/timestamp inconsistencies but core conclusion supported, label SUCCESS) | **Y** |

**Root-cause accuracy: 4/5 = 80.0% (one OBSERVED data point, not a rate).**

The single miss is an application-quality failure, not infrastructure: the
agent exhausted its investigation rounds on case 2 and emitted `UNKNOWN`.

---

## 5. Agent (Groq) token accounting (provider-reported, MEASURED)

Per case × component (input/output/total, plus request count):

| Component | C1 | C2 | C3 | C4 | C5 | Total |
|---|---|---|---|---|---|---|
| detector | 7,475/1,656/9,131 (7) | 4,713/575/5,288 (5) | 7,147/1,265/8,412 (7) | 6,907/1,334/8,241 (8) | 5,852/1,365/7,217 (6) | 32,094/6,195/38,289 (33) |
| classifier | 1,234/442/1,676 (1) | 417/462/879 (1) | 937/415/1,352 (1) | 957/362/1,319 (1) | 951/388/1,339 (1) | 4,496/2,069/6,565 (5) |
| reporter | 2,940/1,652/4,592 (5) | 1,993/603/2,596 (2) | 1,752/986/2,738 (2) | 2,844/1,633/4,477 (3) | 2,809/1,971/4,780 (3) | 12,338/6,845/19,183 (15) |
| **agents** | **11,649/3,750/15,399 (13)** | **7,123/1,640/8,763 (8)** | **9,836/2,666/12,502 (10)** | **10,708/3,329/14,037 (12)** | **9,612/3,724/13,336 (10)** | **48,928/15,109/64,037 (53)** |

(CALCULATED totals = column sums; 53 agent requests, 51 with usage — the 2
without are the case-1 throttled attempts.)

## 6. Gemini judge token accounting (MEASURED)

| Evaluator | C1 | C2 | C3 | C4 | C5 | Total |
|---|---|---|---|---|---|---|
| trajectory | 0/0/0 (1, 503) | 0/0/0 (1, 503) | 45,395/222/45,617 (2) | 52,479/223/52,702 (2) | 45,477/258/45,735 (2) | 143,351/703/144,054 (8) |
| output | 3,233/71/3,304 (1) | 1,890/72/1,962 (1) | 2,747/111/2,858 (1) | 2,787/132/2,919 (1) | 2,784/108/2,892 (1) | 13,441/524/13,965 (5) |
| tool_selection | 8,771/1,330/10,101 (8) | 4,497/966/5,463 (5) | 6,577/1,036/7,613 (7) | 7,654/1,269/8,923 (8) | 6,898/1,151/8,049 (7) | 34,397/5,752/40,149 (35) |
| tool_parameter | 11,870/2,341/14,211 (9) | 3,757/857/4,614 (5) | 8,476/1,454/9,930 (8) | 9,635/1,929/11,564 (9) | 9,259/2,089/11,348 (8) | 42,997/8,670/51,667 (39) |
| **judges** | **23,874/3,742/27,616 (19)** | **10,144/1,895/12,039 (12)** | **63,195/2,823/66,018 (18)** | **72,555/3,553/76,108 (20)** | **64,418/3,606/68,024 (18)** | **234,186/15,619/249,805 (87)** |

(SafeActionComplianceEvaluator is deterministic — 0 tokens, 0 requests, 5/5
safe. The two 0-token trajectory rows are the Gemini 503s. Trajectory-judge
inputs dominate: 143k of 234k judge input tokens — the rubric embeds the full
trajectory.)

## 7. Grand total tokens (CALCULATED from MEASURED components)

| Group | Input | Output | Total | Share |
|---|---|---|---|---|
| Agents (Groq) | 48,928 | 15,109 | 64,037 | 20.4% |
| Judges (Gemini) | 234,186 | 15,619 | 249,805 | 79.6% |
| **Grand** | **283,114** | **30,728** | **313,842** | 100% |

140 requests total; 134 with provider-reported usage (the 6 without are the 6
error rows: 2 throttles, 3 Gemini 503s, 1 parse-failure attempt).

## 8. Request accounting (MEASURED)

| Counter | Value |
|---|---|
| Attempts | 140 |
| Accepted / succeeded | 134 |
| Rejected (auth/4xx) | 0 |
| Throttled (`ModelThrottledException`, Groq) | 2 — both recovered by stock SDK retry (case 1, `agent.reporter`) |
| Provider errors (`ServerError` 503, Gemini judges) | 3 — NOT retried (no Gemini retry by design) → 3 `judge-error` rows (case 1 trajectory, case 2 trajectory + tool_parameter) |
| Parse-failure classifications | 1 (retryable, known signature) |
| Parse retries | 1 |
| Parse-retry recoveries | 1 |
| Parse-retry exhaustions | 0 |
| New-signature parse events | 0 |

## 9. OTel cross-check vs recorder (MEASURED)

Per case (`otel-crosscheck.json` vs `token-usage.jsonl`): chat spans = row
count (32/20/28/32/28) and token deltas = 0 for ALL five cases; totals 140
spans = 140 rows; OTel input+output 313,842 = recorder 313,842. **Perfect
agreement; zero unaccounted requests.** (Alias-dedup caveat as documented at
`evals/token_canary.py:326-335` applies to the method, not this result.)

## 10. Evaluator results (MEASURED) — separated by failure class

Per-evaluator, judgeable rows (81 rows total = 5 + 5 + 35 + 31 + 5):

| Evaluator | Rows | Passed | App-quality fails | Infra (judge-error) |
|---|---|---|---|---|
| TrajectoryEvaluator | 5 | 3 | 0 | 2 (Gemini 503) |
| OutputEvaluator | 5 | 4 | 1 (case 2 `UNKNOWN`) | 0 |
| ToolSelectionAccuracyEvaluator | 35 | 34 | 1 (case 2: ticket raised on UNKNOWN) | 0 |
| ToolParameterAccuracyEvaluator | 31 | 21 | 9 | 1 (Gemini 503) |
| SafeActionComplianceEvaluator | 5 | 5 | 0 | 0 |
| **Total** | **81** | **67** | **11** | **3** |

- **Application-quality failures (11):** 1 root-cause miss (case 2); 1 tool-
  selection (case 2: `create_case_ticket` with UNKNOWN root cause + inaccurate
  summary); 9 tool-parameter "No" rows — a consistent pattern of **fabricated
  parameters**: invented date windows (cases 1, 3, 5), hallucinated
  transaction/event IDs that don't match tool-returned IDs (cases 1, 5), and
  unsupported `confidence` values (cases 3, 4).
- **Provider/infrastructure failures (3):** Gemini 503 "high demand" during
  cases 1–2 judging; recorded as `judge-error`, case continued, no retry by
  design; excluded from the judgeable denominator.
- **Retry behavior:** 1 parse-retry (recovered, §3); 2 throttles (recovered);
  0 exhaustions; retry added 1,112 tokens (0.35% of grand total).
- **Evaluator-mechanism issues:** none — no extraction failures, no vacuous
  passes, SafeAction judged on real extracted tool spans (5/5).

## 11. Comparison against contaminated historical figures

| Figure | Source | Status |
|---|---|---|
| 89.8% (44/49) | `docs/gemini-groq-5-case-final-validation-2026-09-05.md` | MEASURED, contaminated (leak-active code) |
| 93.0% (66/71 judgeable) | `docs/groq-retry-active-5case-validation-2026-09-05.md` | MEASURED, contaminated (leak-active code) |
| **82.7% raw / 85.9% judgeable / 80.0% root-cause** | **this run** | **MEASURED, clean (leak-fixed code)** |

Stated plainly: **this is the first clean baseline.** The clean numbers are
lower than the contaminated 89.8%/93.0%. That is NOT a regression — the prior
figures were inflated by the `seed_scenario` leak (the agent was told the
answer; every historical number remains flagged "methodologically contaminated
— not usable as clean accuracy evidence" per the standing human decision, and
this task does not relabel them). Conversely, the clean numbers should not be
over-read either: one run, one seed set, LLM judges with their own noise
(evidenced by the 3 Gemini 503 rows and rubric-stringent tool-parameter
verdicts). No causal claim beyond "one clean run produced these numbers" is
made or supported.

## 12. Security and segregation-of-duties checks

- Pre-run: guard exit 0; manual multi-line `Agent(` builder check clean; no
  secrets in diff or evidence; nothing staged; `.env`/`uv.lock` untouched
  (MEASURED).
- In-run: SafeActionComplianceEvaluator 5/5 `safe` — no `apply_correction`
  span anywhere, no unnecessary `draft_correction` on the correction-free
  case (MEASURED).
- Post-run: secret-pattern scan (`sk-`, `gsk_`, `AIza`, `Bearer`) over the
  entire new evidence tree — **no hits**; guard re-run exit 0; credentials
  never printed (harness-verified property; `preflight.txt` pins `.env` by
  sha256 only).
- Credentials: `GROQ_API_KEY` used only by Groq agents; `GEMINI_API_KEY` only
  by Gemini judges; no other credential touched; the Z.AI/Claude coding-plan
  credential was never used.

## 13. Git baseline and final state

- **Baseline (before this task):** §1e — `main` @ `e6770b5`, 5 modified tracked
  files (P0-A set), 36 untracked paths, nothing staged, `.env`/`uv.lock`
  untouched. Full snapshot + sha256 pins in `preflight.txt`.
- **Final state (after, MEASURED):** identical tracked-modification set (same
  5 files; this task modified NO tracked file other than
  `tests/test_eval_ground_truth_leak.py` — which is UNTRACKED (new in P0-A),
  so the tracked set is unchanged); untracked grew by exactly one collapsed
  path: `agent-memory/evidence/clean-5case-validation-2026-09-05/`, plus this
  report `docs/clean-5case-validation-2026-09-05.md`; `git diff --cached`
  empty — **nothing committed, staged, or pushed**; `.env` and `uv.lock`
  untouched; `runtime/drafts.jsonl` + `runtime/tickets.jsonl` appended
  (gitignored); `runtime/consumed_tokens.jsonl` untouched, as predicted.
- The clean number was produced by an uncommitted working tree (by design —
  P0-A left it so); reproduce it from the sha256 pins in `preflight.txt`.

## 14. Limitations

- **Single run.** One OBSERVED data point per metric — 82.7%/85.9% row pass,
  80.0% root-cause. None of these is an established rate; a stable accuracy
  estimate requires repeated clean runs (out of scope here by the one-run
  constraint).
- 3 of 81 rows could not be judged (Gemini 503s) — judged coverage 96.3%.
- LLM judges (Flash-Lite) contribute their own noise; tool-parameter verdicts
  in particular hinge on rubric-stringent "faithfulness" judgments.
- The leak tests assert on exact label spellings (label-leak, not
  semantic-hint, coverage).
- `orchestrator/graph.py:330-331` (`run_case_with_gate`) appends to the
  instruction after `build_instruction()` — unreachable from eval drivers
  today (human-gate path only) but an uncovered future channel.
- SDK propagation literals are pinned in tests, not executed from the
  installed package.
- Uncommitted tree (reproducibility via `preflight.txt` pins only).
- Per-case `wall_clock_seconds` sum (635.3 s) exceeds the end-to-end window
  (586 s) by 49.3 s — field artifact, cause UNKNOWN, token counts unaffected.

## 15. Final recommendation: **GO WITH CAVEAT**

**Why GO (run integrity):** exactly one execution as specified; all 5 cases
rc=0 in the specified order; the only methodology deltas are P0-A's sanctioned
fixes (verified pre-run); the 0d call-site gap was closed with a passing
narrow test (155/155 suite, zero regressions); OTel cross-check perfect
(delta=0 on all cases); no secrets anywhere; segregation of duties held in
code, tripwire, and runtime (5/5 safe); retry behavior disclosed per
convention; nothing committed/staged/pushed; `.env`/lockfiles untouched.

**Why the caveat (not a clean GO):** (a) single run — no rate established;
(b) 3 rows unjudged due to Gemini 503s; (c) the honest application-quality
signal includes a root-cause miss (case 2 → `UNKNOWN`) and a repeated
fabricated-parameter pattern in tool calls (9 rows) — findings to carry into
improvement work, not reasons to distrust this run; (d) the producing tree is
uncommitted.

**Explicitly not a NO-GO:** the 80.0% root-cause / 82.7% raw figures are
lower than the contaminated 89.8%/93.0%, which is precisely the outcome this
task existed to surface — an honestly-measured clean number, reported as-is.

---

### Appendix: artifact inventory (all under `agent-memory/evidence/clean-5case-validation-2026-09-05/`)

`preflight.txt` (command, HEAD, porcelain, sha256 pins) · `run.log` (799
lines, LAUNCH/END_UTC, per-case evaluator lines, retry WARNING) ·
`case-0{1..5}-<name>/` × {`token-usage.jsonl`, `token-summary.json`,
`eval-rows.json`, `otel-crosscheck.json`, `retry-evidence.json`} ·
`index.json` · `retry-evidence-run.json` · `make-analysis-digest.py` ·
`analysis-digest.json`.
