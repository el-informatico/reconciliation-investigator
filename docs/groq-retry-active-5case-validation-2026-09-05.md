# Groq parse-retry ACTIVE — 5-case validation (2026-09-05)

**Status: COMPLETE — 5/5 cases rc=0; the `GroqParsingFailedRetryStrategy` fired LIVE twice
and recovered twice; No retry-related regressions were observed on any other axis → GO WITH CAVEAT.** (MEASURED)

- Run: `groq-retry-active-5case-validation-2026-09-05`, exactly ONE execution
  (MEASURED: `index.json executions: 1`, all case dirs created once).
- Launched 2026-09-05T13:06:48Z, ended 13:16:37Z — **589 s end-to-end wall**
  (MEASURED from run.log `LAUNCH_UTC`/`END_UTC`); per-case walls sum to 586.9 s
  (MEASURED), consistent with the envelope.
- Evidence: `agent-memory/evidence/groq-retry-active-5case-validation-2026-09-05/`
  (this report's every figure is derived from that tree; the reproducible
  derivation is `make-analysis-digest.py` → `analysis-digest.json`).
- Headline distinction this run exists to make: **2 of the 5 cases were NOT clean.**
  `duplicate-transaction` and `data-entry-error` each hit the provider's in-stream
  `Parsing failed` rejection, were classified retryable by the narrow matcher,
  retried once, and RECOVERED. They are resilience successes, not clean cases
  (§5, §6). The other three cases were clean.

---

## 1. Phase 0 — self-verification record (0a–0f, all CONFIRMED, no material conflict)

Four independent read-only audits run before any live call (their exact commands
and outputs are preserved in this session's working record; findings summarized):

- **0a** `docs/groq-parsing-retry-canary-2026-09-05.md` exists (676 lines) and
  matches the documented record on all eight claims: GO WITH CAVEAT; one live
  canary on `sync-lag-self-resolving` (rc=0, 101.0 s, 26/26 requests success);
  `Parsing failed` did not recur (grep-verified across run.log / token-usage /
  eval-rows / otel-crosscheck); the retry did NOT fire (ledger
  `classification_count: 0`); offline 94→126→130 cumulative, zero regressions;
  security PASS 11/11; fix pair byte-identical (blob hashes equal in both
  patches). Non-material phrasing notes: "94→130" is cumulative across two
  sessions; the doc carries three already-disclosed inline self-corrections.
  (DOCUMENTED, verified against the file)
- **0b** Evidence dir `agent-memory/evidence/groq-parsing-retry-canary-2026-09-05/`
  exists; ledger format confirmed: `get_retry_evidence()` →
  `{strategy_class, signature_prefix, classification_count, events[{timestamp,
  exception_type, message_head(≤200 chars), classified_retryable}], note}`;
  known semantics respected in this run's reporting (classification_count counts
  classifications, not retries performed; the JSONL adjacency derivation is the
  independent cross-check). (DOCUMENTED, verified)
- **0c** `agents/retry.py` present (127 lines, untracked); wired at exactly 3
  production sites (`detector_investigator.py:56`, `classifier.py:44`,
  `reporter.py:41`); the working-tree diff was byte-identical to the canary's
  `post-implementation-tracked-diff.patch` — no drift since the canary.
  (DOCUMENTED, verified)
- **0d** `tools/case_management.py:114` carries `correction_draft_id: str | None`;
  diff vs HEAD is exactly that one line (blob `a1cfc39` → `aa952d6`). Not
  modified in this task (sha256 before == after, §12). (DOCUMENTED, verified)
- **0e** Canonical driver confirmed: `evals/gemini_judge_5case.py`; prior baseline
  report `docs/gemini-groq-5-case-final-validation-2026-09-05.md`; naming
  convention `<topic-slug>-YYYY-MM-DD.md` with mirrored evidence stem. The
  driver did NOT surface the retry ledger → instrumentation gap (§3).
  (DOCUMENTED, verified)
- **0f** No material conflict; one identity limitation disclosed: `agents/retry.py`
  has no canary-era hash (post-gate docstring edit), so its "unchanged during
  THIS task" proof is this task's own before/after sha256 pair (§12) plus the
  offline suite — canary-era byte identity is UNKNOWN and not claimed.

## 2. Benchmark configuration and case order (required item 1)

Provider architecture preserved exactly (MEASURED from run.log banner and
index.json; no deviations):

| Leg | Provider / model | Credential | Notes |
|---|---|---|---|
| Agents (detector, classifier, reporter) | Groq `openai/gpt-oss-120b` | `GROQ_API_KEY` only | unpaced; **retry strategy ACTIVE in all three builders** |
| Judges (4 evaluators) | native Strands `GeminiModel`, `gemini-3.1-flash-lite` | `GEMINI_API_KEY` only | module-global 4.3 s pacer across all 5 cases; **no Gemini retries** (none configured; 503 ServerError structurally unretryable) |

- SafeActionCompliance: deterministic, no model. (DOCUMENTED)
- No provider switching, no credential rotation, no extra keys/accounts, no
  quota bypass. The Z.AI / Claude Code coding-plan credential was never used
  for any application call. (OBSERVED — the only credentials read are the two
  above, via the app's own `.env` loader; values never printed)
- **Case order confirmed identical to the specified order** (MEASURED, run.log
  line 3 and `evals/cases.py`): `reversal-not-propagated`, `duplicate-transaction`,
  `sync-lag-self-resolving`, `manual-override-not-reflected`, `data-entry-error`.
  Each executed exactly once; no reruns, no canaries before or after, no
  individual-case retries outside the single execution. (MEASURED: per-case
  token-usage.jsonl row counts monotonic per component, `executions: 1`)

Exact invocation (MEASURED, from preflight.txt and run.log):

```
timeout 2400 uv run --frozen --with google-genai==2.22.0 \
    python -m evals.gemini_judge_5case \
    --out-dir agent-memory/evidence/groq-retry-active-5case-validation-2026-09-05
```

`--frozen`/`--with` overlay leaves `uv.lock` and `pyproject.toml` untouched
(sha256-verified, §12). The 40-min `timeout` was a safety net only; not hit.

`verify.sh` was NOT executed (its step 6 would launch a second live benchmark;
established convention — steps 2 and 5 equivalents were run individually, §12).

## 3. Observation-only instrumentation added before the run (and nothing else)

The 5-case driver did not surface `agents.retry`'s ledger (Phase 0e). Added to
`evals/gemini_judge_5case.py`, reusing the canary's validated helpers
(`read_ledger_rows`, `derive_ledger_summary`, `RETRY_STRATEGY_NAME` from
`evals/groq_parsing_retry_canary.py`):

- per-case `retry-evidence.json`: snapshot-diff of the module-global cumulative
  classification registry (count before vs after each case — the registry is
  never reset during the run; no state mutation) + `ledger_derived` from that
  case's `token-usage.jsonl`;
- run-root `retry-evidence-run.json` (cumulative registry + per-case deltas);
  `index.json` gains `retry_strategy` and `retry_evidence` keys;
- both writes are best-effort and MUST NEVER raise (canary `_write_evidence_tail`
  pattern).

No evaluated path changed: prompts, tools, evaluators, scoring, routing, cases,
pacer, retry semantics, `run_one_case` — untouched. The driver diff is purely
additive evidence writes (docstring note, imports, three evidence functions,
snapshot/write calls, two index.json keys; the `run_one_case` invocation itself
unchanged) — MEASURED against the preserved pre-edit copy
`evidence/.../baseline/gemini_judge_5case.py.pre-edit`, sha256 `b0230941…` →
`37868fa5…`. The reused helper modules (`evals/token_canary.py`,
`evals/gemini_judge_canary.py`, `evals/groq_parsing_retry_canary.py`) were NOT
in this task's hash set: no edits were made to them in this task (OBSERVED,
operator record), corroborated indirectly by the 132-test suite, exact OTel
parity, and artifact-schema parity — but their run-window byte identity is not
independently hash-proven (adversarial-review finding 3).

Offline suite after instrumentation: **132 passed in 5.14 s** (baseline 130 + 2
new tests; **zero regressions**) — `evidence/.../offline-suite-AFTER-instrumentation.txt`. (MEASURED)

One test-authoring iteration is disclosed: the first version of
`test_main_writes_retry_evidence_per_case_and_run_root` asserted each case's
captured after-count against the FINAL registry count (wrong — the registry
legitimately advances past earlier snapshots); fixed to assert internal
consistency (`after == before + delta`) plus the cumulative trajectory
`[0,1,1,1,1]`. The driver was never wrong; the test was. (OBSERVED)

## 4. Execution outcome — case-by-case (required item 2)

All five cases completed with **rc=0**; `all_exit_zero: true` (MEASURED,
index.json). Ambient noise in run.log is exactly the documented known-benign set
(`reasoningContent is not supported…` warnings; the httpcore2 async-generator
`RuntimeError: generator didn't stop after athrow()` traceback, appearing
6× — roughly once per case window, same documented-benign kind as the
canary's occurrence). (OBSERVED)

| # | Case | rc | Parse-retry classification (§6 taxonomy) | Wall s | Attempts (agent/judge) | Eval rows/passed |
|---|---|---|---|---|---|---|
| 1 | reversal-not-propagated | 0 | **CLEAN** — no `Parsing failed` at any point | 75.4 | 24 (8/16), 0 errors | 13/10 |
| 2 | duplicate-transaction | 0 | **Parsing failed → retryable → retry attempted → recovery SUCCEEDED** | 111.1 | 20 (10/10), 2 errors (1 agent APIError, 1 judge 503) | 10/9 |
| 3 | sync-lag-self-resolving | 0 | **CLEAN** | 131.3 | 25 (9/16), 0 errors | 15/15 |
| 4 | manual-override-not-reflected | 0 | **CLEAN** | 166.2 | 31 (11/20), 0 errors | 19/19 |
| 5 | data-entry-error | 0 | **Parsing failed → retryable → retry attempted → recovery SUCCEEDED** | 102.9 | 25 (10/15), 1 error (agent APIError) | 15/13 |

All MEASURED (per-case token-summary.json / eval-rows.json / retry-evidence.json).

Attribution cross-check for the two parse events — three independent channels
agree (OBSERVED): (a) the `agents.retry` WARNING lines in run.log sit between
the case-N and case-N+1 `artifacts in:` banners, which print at case END →
during case-02 and case-05; (b) the registry snapshot-diff attributes
`delta_classifications = 1` to exactly case-02 and case-05; (c) the APIError
rows live in case-02's and case-05's token-usage.jsonl with a following
same-component success row. No non-retryable (`new-signature`) parse error
occurred in this run: the only `Parsing failed` texts anywhere in the evidence
tree are the two matched-and-recovered events (text scan: run.log WARNING lines
×2, the two per-case retry-evidence.json `message_head`s, and the run-root
ledger copies — `analysis-digest.json parsing_failed_text_scan`). (MEASURED)

## 5. Parse-retry disclosure — explicit clean-vs-recovered distinction (required item 7)

- **Clean cases (3):** reversal-not-propagated, sync-lag-self-resolving,
  manual-override-not-reflected. No `Parsing failed` observed at any point.
- **Recovered-by-retry cases (2 — NOT clean):** duplicate-transaction,
  data-entry-error. Each would be misreported as "clean" if the retry were
  invisible; this report classifies them as resilience successes with an
  infrastructure event inside them.
- **New-signature (non-retryable) events: 0. Exhausted retries: 0.**

## 6. Parse-retry event records (required item 6 — mandated fields)

**Event 1 — case `duplicate-transaction`, component `agent.detector`**
- Request/attempt within component: **request #5** (of 6 detector requests that
  case), error row timestamp 2026-09-05T13:08:09.382Z. (MEASURED)
- Observed provider error (verbatim, ≤200-char ledger head): `Parsing failed.
  The model generated output that could not be parsed. Please adjust your
  prompt. See 'failed_generation' for more details.` — `openai.APIError`
  (in-stream, no status code). (MEASURED)
- Narrow matcher (`is_groq_parsing_failed_error`) classified retryable: **YES** —
  ledger event at 13:08:09.385Z, 3 ms after the request-ledger error row.
  (MEASURED)
- Retry attempt occurred: **YES** (detector request #6 follows; the
  classification-driven re-execution is the only mechanism that produces a
  next attempt — the stock strategy retries ONLY `ModelThrottledException`,
  verified against the installed SDK). (MEASURED + DOCUMENTED)
- Recovery: **SUCCEEDED** — request #6 `status=success`; case completed rc=0,
  correction flow judged `SUCCESS`/`Yes` by the judges. (MEASURED)
- Additional attempts consumed: **1**. (MEASURED)
- Tokens of the additional attempt: input 1,215 / output 732 / total 1,947;
  the failed attempt itself reported no usage (`had_usage=false` — the in-stream
  rejection precedes usage). (MEASURED)

**Event 2 — case `data-entry-error`, component `agent.detector`**
- Request #5 (of 6), 2026-09-05T13:14:57.748Z; identical verbatim error text and
  class. (MEASURED)
- Classified retryable: **YES** (ledger event 13:14:57.750Z). Retry attempted:
  **YES** (request #6). Recovery: **SUCCEEDED**. Additional attempts: **1**.
  Additional-attempt tokens: 1,163 / 656 / **1,819** (failed attempt no usage).
  Case completed rc=0. (MEASURED)

Aggregate: parse-failure classifications **2**; parse retries attempted **2**;
successful parse recoveries **2**; exhausted parse retries **0**; total
additional-attempt tokens **3,766** (CALCULATED 1,947+1,819). Both events hit
`agent.detector` request #5 — noted as an OBSERVED positional coincidence; no
causal claim. Numbering note (adversarial-review finding 4): `request_number`
is the case-wide JSONL row ordinal (it resets each case and is shared across
components — case-02's lone `judge.tool_selection` row is ordinal #14 of that
case), not a per-component counter; for `agent.detector`, the case's leading
component, ordinal coincides with the within-component attempt index, so
#5→#6 is correct in both readings. The 2-events/48-agent-requests figure for
this run is a raw count of one run, **not an established probability** (§14).

## 7. Token accounting (required items 3–5)

All figures MEASURED from per-case token-summary.json (recorder) and identical
to the OTel sums (§9). `input + output == total_reported` holds on every row
set. Usage-less rows: exactly **3** — the two parse-error rows (in-stream
rejection precedes usage; `had_usage=false`) and case-02's judge 503
ServerError row (`judge.tool_selection` `missing_usage: 1`; case-02
`requests.without_usage: 2`). No total is affected (null rows contribute 0).
Cache-read grand total: 32,672.

**Agents (Groq openai/gpt-oss-120b) — 48 attempts (46 success / 2 parse-error):**

| Component | Requests | Input | Output | Total |
|---|---|---|---|---|
| agent.detector | 30 | 27,082 | 4,951 | 32,033 |
| agent.classifier | 5 | 4,208 | 1,972 | 6,180 |
| agent.reporter | 13 | 13,792 | 6,408 | 20,200 |
| **Agents total** | **48** | **45,082** | **13,331** | **58,413** |

Per case (agents in/out/total): case-1 7,122/1,623/8,745 · case-2
10,360/3,411/13,771 · case-3 8,723/2,467/11,190 · case-4 10,593/2,791/13,384 ·
case-5 8,284/3,039/11,323. (Cases 2 and 5 totals INCLUDE their additional
recovery attempts — 1,947 and 1,819 respectively, already inside these sums.)

**Judges (gemini-3.1-flash-lite) — 77 attempts (76 success / 1 ServerError):**

| Evaluator | Requests | Input | Output | Total |
|---|---|---|---|---|
| judge.trajectory | 10 | 214,993 | 1,159 | 216,152 |
| judge.tool_parameter | 35 | 38,082 | 8,179 | 46,261 |
| judge.tool_selection | 27 | 24,097 | 4,148 | 28,245 |
| judge.output | 5 | 13,248 | 539 | 13,787 |
| **Judges total** | **77** | **290,420** | **14,025** | **304,445** |

**Grand total: 362,858** (CALCULATED = 58,413 + 304,445; both addends MEASURED).
Agents 16.1% / judges 83.9% of total (CALCULATED) — judge-heavy as in all prior
Gemini-judge runs.

## 8. Request accounting (required item 6)

| Quantity | Count | Note |
|---|---|---|
| Attempts | **125** (48 agent + 77 judge) | MEASURED (JSONL rows) |
| Accepted/succeeded | **122** (46 + 76) | MEASURED |
| Schema-rejected | 0 | MEASURED (no such error class in any row) |
| Throttled (`ModelThrottledException`) | **0** | MEASURED (prior run: 2, both stock-recovered) |
| Stock throttle retries fired | 0 | MEASURED (nothing to recover) |
| Provider errors — agent Groq in-stream `APIError` (`Parsing failed`) | **2** | both classified retryable, both recovered by `GroqParsingFailedRetryStrategy` (§6) |
| Provider errors — judge Gemini 503 `ServerError` | **1** | case-02 `judge.tool_selection`, 13:09:29.696Z; not retried (by design — no Gemini retries); recorded as a `judge-error` eval row |
| Parse-failure classifications / parse retries / successful recoveries / exhausted | 2 / 2 / 2 / 0 | MEASURED |

## 9. OTel cross-check vs recorder (required item 8)

Per case, the in-memory OTel exporter's `chat` spans were summed (alias-deduped)
and compared to the recorder: **125/125 spans overall; delta = 0 on every case;
`spans_equal_row_count = true` on every case.** (MEASURED,
per-case otel-crosscheck.json; aggregate in analysis-digest.json). Exact match,
same as the prior validation's 98/98.

## 10. Evaluator results, with failure separation (required item 9)

**72 rows, 66 passed — 91.7% raw (CALCULATED); judgeable rows 71 (72 minus the
one judge-error row), 66 passed — 93.0% judgeable (CALCULATED).** SafeActionCompliance
(`safe`) passed in all five cases (MEASURED — no `safe` row among failures).

**Application-quality failures (5):** case-01 ×3 — TrajectoryEvaluator
`NOT_APPLICABLE` 0.2 (agent stopped at UNKNOWN despite search results the judge
reads as showing charge+reversal in legacy vs charge-only in modern);
OutputEvaluator `NOT_APPLICABLE` 0.0 (root cause UNKNOWN → 0 per rubric);
ToolSelectionAccuracy `No` 0.0 (proposed no-correction on UNKNOWN). case-05 ×2 —
ToolParameterAccuracy `No` ×2 (hallucinated `2023-08-15` timestamps and
unsupported `case_id`/`confidence` values vs actual 2026-08-24 data). All five
are agent-judgment issues, NOT infrastructure. (MEASURED, judge reasons quoted
in analysis-digest.json)

**Provider/infrastructure failures (1):** case-02 ToolSelectionAccuracy
`judge-error` — Gemini 503 "high demand" ServerError (§8); that evaluator
contributed no judgment for case-02 (its only request crashed).

**Retry behavior (2 events):** disclosed in §5–§6; neither affected any eval row
(both cases completed their full evaluation; rows/passed above are post-recovery
outcomes, and the affected requests' outputs were produced by the recovery
attempt).

**Evaluator-mechanism issues (0):** no mislabeled, missing, or double-counted
rows; `NOT_APPLICABLE` labels are rubric outcomes, not mechanism faults.
(OBSERVED)

The case-4 `UNKNOWN` vs `MANUAL_OVERRIDE` classifier-quality backlog item was
NOT touched (case-04 passed 19/19 this run; that is an OBSERVED outcome of this
run only, not a resolution of the backlog item).

## 11. Comparison against the prior 5-case validation (required item 14)

Baseline: `docs/gemini-groq-5-case-final-validation-2026-09-05.md` (retry
INACTIVE — the builder wiring landed after that run). This run has **exactly one
additional variable: the active retry strategy**, plus ordinary run-to-run
variance (agent trajectories and judge demand are nondeterministic).

| Axis | Prior (retry inactive) | This run (retry active) |
|---|---|---|
| Cases completed rc=0 | 4/5 (case-3 died) | **5/5** |
| Attempts (agent/judge) | 98 (45/53) | 125 (48/77) |
| Accepted | 92 | 122 |
| Throttles (stock-recovered) | 2 | 0 |
| In-stream `Parsing failed` | **1 → case-3 terminal death** (detector req#5) | **2 → both recovered** (detector req#5, both cases rc=0) |
| Gemini ServerError | 3 (503×2, 500×1) | 1 (503) |
| Eval rows / passed | 57 / 44 (77.2%; 44/49 judgeable = 89.8%) | 72 / 66 (91.7%; 66/71 = 93.0%) |
| Tokens (agents/judges/grand) | 55,037 / 240,988 / 296,025 | 58,413 / 304,445 / 362,858 |
| Wall | 448 s | 589 s |

- **Completion 4/5 → 5/5 is directly retry-attributable for this run's two
  events**: absent the strategy, an in-stream `APIError` is terminal (the stock
  SDK strategy retries only `ModelThrottledException` — DOCUMENTED code path,
  verified against installed SDK source), which is exactly how prior case-3
  died on the identical error class, same component, same request position.
  (DOCUMENTED + MEASURED; the counterfactual for THESE two events is inferred
  from that documented mechanism, not from a rerun — reruns are forbidden and
  none were performed.)
- **The eval-rate improvement is NOT claimed for the retry.** The prior run's
  dead case contributed 5 task-failure rows that depress its raw rate; the
  judgeable-rate change (89.8% → 93.0%) is within run-to-run variance. The
  retry fixes infrastructure resilience, not agent judgment — this run still
  shows 5 application-quality failures (§10), including case-01 scoring 10/13
  vs the prior run's 18/19 (different agent trajectory, no retry involvement —
  case-01 was clean this run). (OBSERVED; no causality claimed)
- Token growth (+22.6% grand) tracks the larger completed workload (77 vs 53
  judge requests — every judge request paced ≥4.3 s, a ≥103 s CALCULATED
  pacing-floor increase) plus the two recovery attempts (3,766 tokens) and
  their backoff delays. Wall 589 s vs 448 s is consistent with that.
  (CALCULATED decomposition; MEASURED components)

## 12. Security and segregation-of-duties (required item 10) — ALL PASS

From `evidence/.../post-run-checks.txt` (every line reproducible):

1. No secrets in code/logs/evidence: pattern scan (`gsk_…`, `AIza…`, `Bearer …`,
   `authorization`) over the entire evidence tree + instrumented driver →
   **0 hits**. (MEASURED)
2. `.env` never read into any artifact; only its sha256 appears (value-free).
   `.env` byte-identical to task start: `874a40f8…` before == after. (MEASURED)
3. `uv.lock` (`a3b4ac54…`) and `pyproject.toml` (`ad9b302d…`) byte-identical to
   task start. (MEASURED)
4. No sibling-project access: all reads/writes confined to this repo's tree.
   (OBSERVED)
5. No credential rotation; only `GROQ_API_KEY` + `GEMINI_API_KEY` used, via the
   app's own loader, env-wins order. (OBSERVED; presence checked as booleans)
6. Segregation-of-duties guard (`scripts/guard-segregation-of-duties.sh`):
   **exit 0** pre-run and post-run. `apply_correction` appears only in
   `tools/modern_system.py` (plain function), `orchestrator/correction_executor.py`
   (not an LLM node; imports it explicitly as a non-tool), and docstrings —
   **never in any agent builder or tools list**. (MEASURED)
7. Constrained files untouched this task — sha256 before == after (preflight vs
   post-run): `agents/retry.py` `ab0ed6af…`, `agents/detector_investigator.py`
   `fe2d7042…`, `agents/classifier.py` `9a6df5e2…`, `agents/reporter.py`
   `1866711d…`, `tools/case_management.py` `99a441dd…`. (MEASURED)
8. Instrumented files stable across the run window: `evals/gemini_judge_5case.py`
   `37868fa5…`, test file `29aaf22d…` — same before launch and after completion.
   (MEASURED)

## 13. Git baseline vs final state; no commit/stage/push (required items 11–13)

- HEAD before == after: `316835fb73d66850444473c86fa33df10c4c8169`; stash list
  empty both times; **no commit, no stage, no push occurred** (MEASURED —
  `git rev-parse`, `git stash list`, porcelain output; no index-side entries).
- Tracked working-tree diff identical before == after: the pre-existing
  5-file diff (`agents/{classifier,detector_investigator,reporter}.py` +2 lines
  each = the retry wiring; `tools/case_management.py` 1 line = the
  `correction_draft_id` annotation; `tests/test_tools.py` +35 = its regression
  test) — `5 files changed, 42 insertions(+), 1 deletion(-)` both snapshots.
  (MEASURED)
- Untracked set: task-start set unchanged, plus exactly two additions from this
  task: `agent-memory/evidence/groq-retry-active-5case-validation-2026-09-05/`
  and this report `docs/groq-retry-active-5case-validation-2026-09-05.md`. The
  two instrumented files (`evals/gemini_judge_5case.py`,
  `tests/test_gemini_judge_5case_offline.py`) were already untracked before the
  task, so their modification adds no new git entry. (MEASURED)

## 14. Limitations (required item 15)

1. **n=1 run.** Every rate here describes one execution. The 2 parse events in
   48 agent requests (this run) and the historical ~2.5–2.7% small-sample
   figures are raw counts, **not established probabilities** — no probability
   claim is made anywhere in this report.
2. **Live recovery demonstrated in exactly one form:** single additional
   attempt per event, first backoff step only (~4 s), both on `agent.detector`
   request #5. Multi-attempt backoff ladders and retry exhaustion remain
   exercised only offline (DOCUMENTED via the 132-test suite); their live
   behavior is UNKNOWN.
3. **Throttle+parse interaction unexercised live** (0 throttles this run); the
   shared 6-attempt budget under a mixed failure pattern is untested live.
4. Judge-side 503s remain unretried by design; one evaluator's judgment is
   missing for case-02 (judgeable-rate denominators account for it, but the
   score gap is real variance).
5. `request_number` semantics: it is a case-wide JSONL row ordinal (resets per
   case, shared across components — case-02's lone `judge.tool_selection` row
   is ordinal #14 of that case), NOT a per-component counter. §6's #5→#6
   adjacency is valid because both rows sit in one case's JSONL, and for the
   detector (leading component) ordinal == within-component index. Cross-case
   request numbering is not comparable. (MEASURED; corrected per adversarial
   review finding 4)
6. Comparability: results are NOT numerically interchangeable with historical
   all-Groq runs (different judge model); comparison is made only against the
   2026-09-05 Gemini-judge baseline, which itself differs by the one intended
   variable plus natural variance.
7. `agents/retry.py` canary-era byte identity is UNKNOWN (no canary-era hash
   exists); this task proves only that it was not modified during THIS task.
8. The wall-clock/token comparison in §11 is a decomposition, not a controlled
   experiment — workload size differed (eval rows 72 vs 57).

## 15. Recommendation (required item 16)

**GO WITH CAVEAT.**

Justification tied to evidence:

- **The specific resilience gap that motivated the retry is now demonstrated
  as recovered in live execution** (MEASURED): the exact production failure
  that killed prior case-3 occurred twice in this run and was recovered twice,
  with both cases completing rc=0 and full evaluations. First live
  demonstration of the strategy's recovery path (the canary could not exercise
  it).
- **No retry-related regressions were observed on any other axis** (MEASURED):
  5/5 completion (first run achieving it), OTel exact match 125/125, offline
  suite 132/132, security/segregation PASS, constrained files and
  `.env`/lockfiles byte-identical, no VCS operations.
- **Not NO-GO** — and not because of absence of the failure mode: the failure
  mode DID occur and was handled. NO-GO would require evidence the retry harms
  correctness, exceeds its budget, or masks new signatures; none appeared (0
  new-signature events, 0 exhausted retries).

The caveats (all carried from §14): recovery is live-proven only in the
single-attempt form — exhaustion and multi-attempt ladders remain offline-only;
the parse-failure rate remains an n-of-this-run count, not a probability; and
the retry does not address the 5 application-quality failures this run exposed
(including case-01's UNKNOWN outcome), which stay on the quality backlog —
explicitly including the untouched case-4 classifier item.

**Next evidence that would change this recommendation:** a run exhibiting an
exhausted retry ladder (would trigger the NO-GO criteria in the disclosure
taxonomy), or a new-signature parse error (fresh investigation trigger —
preserve the exact text; do NOT broaden the matcher without a dedicated
canary).
