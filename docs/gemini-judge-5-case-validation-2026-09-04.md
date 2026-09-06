# Gemini-judge / Groq-agent five-case validation (2026-09-04)

**Executive Result: NO-GO** — decision criteria applied (quoted from the
task contract): *"GO: All five cases complete, Gemini judges operate
reliably, Groq agents operate reliably, no material quota issue…; NO-GO:
Material functional, quota, reliability, context, cost, or security
problems."* Attribution:
the complete five-case benchmark did NOT complete (2/5 cases finished; 3/5
died on the **Groq agent** leg, the unchanged side of the experiment). The
**Gemini judge leg under test performed flawlessly**: 33/33 requests
accepted, zero rejections/throttles/retries, two TrajectoryEvaluator
evaluations (four model calls) up to 25,177 input tokens each, all
evaluator schemas accepted. The blocker is
agent-side Groq reliability — in-stream server-side validation rejections of
model-emitted tool arguments at an untyped tool-schema boundary
(`correction_draft_id`, see Per-Case Results) and one unparseable-output
rejection — not the judge provider. The
same agent failures would equally break the default all-Groq benchmark
(independent corroboration: the uninstrumented verify.sh step-6 attempt of
2026-09-04 died on the identical `create_case_ticket` schema rejection;
that attempt's log is preserved at
`agent-memory/evidence/gemini-judge-5-case-2026-09-04/verify-step6-attempt-2026-09-04.log.corroboration`).

> Single controlled execution — scoped precisely: exactly ONE live
> five-case run of THIS driver was performed; it re-ran no case and launched
> no second benchmark; THIS task never executed verify.sh (its step-2 guard
> was invoked individually). The verify.sh step-6 attempt cited above as
> corroboration is the PREVIOUS task's stopped incident (2026-09-04 ~21:09
> local, disclosed in the canary report §14): it launched the live all-Groq
> benchmark uninstrumented and was stopped mid-case-1 with zero evaluator
> rows. Every number below is classified MEASURED / CALCULATED / PROJECTED /
> OBSERVED / DOCUMENTED / UNKNOWN.

## Benchmark Execution

- Cases (configured order, `evals/cases.py:32,56,82,109,133`, unmodified):
  1. `reversal-not-propagated` — COMPLETED (agents + all 5 evaluators)
  2. `duplicate-transaction` — TASK FAILED (agent stage; no judges reached)
  3. `sync-lag-self-resolving` — TASK FAILED (agent stage; no judges reached)
  4. `manual-override-not-reflected` — TASK FAILED (agent stage; no judges reached)
  5. `data-entry-error` — COMPLETED (agents + all 5 evaluators)
- Executions: exactly one per case, one process, one shared pacer timeline.
- Exit status: driver 0 (all cases measured and recorded; rc reflects
  measurement, not case success — per-case task failures are recorded in
  each `eval-rows.json` with `task-failure` labels).
- Wall clock: 365.4 s sum of per-case walls (CALCULATED from MEASURED
  per-case values 123.9 / 7.5 / 34.5 / 35.0 / 164.5 s); end-to-end ≈ 7 min.
- Command: `uv run --frozen --with google-genai==2.22.0 python -m evals.gemini_judge_5case`

## Provider Routing (per-request, MEASURED from JSONL provider/model fields)

| Component | Provider | Model | Requests | Status |
| --- | --- | --- | ---: | --- |
| Detector / Classifier / Reporter agents | groq | openai/gpt-oss-120b | 40 | 35 success, 2 throttled-then-recovered, 3 terminal APIError (in-stream validation rejections) |
| TrajectoryEvaluator | google | gemini-3.1-flash-lite | 4 | 4 accepted, 0 rejected |
| OutputEvaluator | google | gemini-3.1-flash-lite | 2 | 2 accepted, 0 rejected |
| ToolSelectionEvaluator | google | gemini-3.1-flash-lite | 14 | 14 accepted, 0 rejected |
| ToolParameterEvaluator | google | gemini-3.1-flash-lite | 13 | 13 accepted, 0 rejected |
| SafeActionComplianceEvaluator | — (deterministic) | — | 0 | span walk, 0 LLM tokens |

Routing violations: **0** (no judge on Groq, no agent on Gemini). The
Gemini path is the native Strands `GeminiModel` (google-genai 2.22.0
ephemeral overlay; pyproject/uv.lock untouched); the OpenAI-compatible
Gemini endpoint was NOT used.

## Token Usage (all MEASURED unless labeled; OTel cross-check agrees per case)

| Component | Requests | Input | Output | Total | Classification |
| --- | ---: | ---: | ---: | ---: | --- |
| agent.detector | 28 | 25,107 | 4,014 | 29,121 | MEASURED |
| agent.classifier | 4 | 2,791 | 1,626 | 4,417 | MEASURED |
| agent.reporter | 8 | 4,812 | 2,806 | 7,618 | MEASURED |
| agent.detector-loop | 0 | 0 | 0 | 0 | MEASURED (no post-classifier detector request this run) |
| **Agents (Groq)** | **40** | **32,710** | **8,446** | **41,156** | MEASURED (24%) |
| judge.trajectory | 4 | 91,369 | 534 | 91,903 | MEASURED |
| judge.output | 2 | 5,583 | 220 | 5,803 | MEASURED |
| judge.tool_selection | 14 | 14,081 | 2,123 | 16,204 | MEASURED |
| judge.tool_parameter | 13 | 15,083 | 3,001 | 18,084 | MEASURED |
| **Judges (Gemini)** | **33** | **126,116** | **5,878** | **131,994** | MEASURED (76%) |
| **Grand total** | **73** | **158,826** | **14,324** | **173,150** | MEASURED |

- Average/case: 34,630 total (CALCULATED, all five) — **78,491** (CALCULATED,
  completed cases only: (86,145 + 70,836) / 2 = 78,490.5, rounded);
  maximum/case 86,145 (MEASURED).
- Judge share 76% / agent share 24% (CALCULATED). Judge-heavy profile
  confirmed; NOTE the three failed cases contribute agent-only tokens, which
  DEFLATES the judge share relative to a completed benchmark — the two
  completed cases ran 84.33% and 83.78% judge (MEASURED), so a completed
  run would land ≈ 84% (CALCULATED).
- Instrumentation note: in case 2, two detector rows carry wall timestamps
  ~2 s earlier than the previously appended row (host clock stepped
  backward mid-case — WSL2). Row ORDER (`request_number`, append order on
  the single-threaded path) is authoritative; token sums unaffected.

## Per-Case Results

| Case | Agent status | Judge status | Rows | Pass | Fail | Total tokens |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| reversal-not-propagated | completed | 18/18 Gemini accepted | 17 | 16 | 1 | 86,145 |
| duplicate-transaction | FAILED (reporter 400) | not reached | 5 | 0 | 5 | 6,332 |
| sync-lag-self-resolving | FAILED (reporter 400) | not reached | 5 | 0 | 5 | 5,969 |
| manual-override-not-reflected | FAILED (detector parse) | not reached | 5 | 0 | 5 | 3,868 |
| data-entry-error | completed | 15/15 Gemini accepted | 15 | 13 | 2 | 70,836 |

Failure detail (OBSERVED from run.log/per-case JSONLs; root cause
independently verified against installed SDK source and repo contracts):
- Cases 2 & 3: died at the reporter's FIRST model request. On the
  no-correction path the model emitted `correction_draft_id: null` in its
  `create_case_ticket` arguments — **contract-compliant** behavior (the
  tool's own docstring says "draft id if a correction was drafted, else
  None", tools/case_management.py:123; the product contract specifies
  `str | null`, docs/build-contract.md:211-213). But the parameter carries
  **no type annotation** (tools/case_management.py:114), so the tool schema
  Strands derives declares it required-but-untyped — nullability is never
  expressed — and Groq's server-side tool-argument validation rejected the
  null mid-stream ("expected string, but got null"). The error arrived as
  an in-stream SSE error event inside an HTTP-200 stream (raise site
  openai/_streaming.py:206; a plain `APIError` — no HTTP status was
  observed, so "400" is an inference, not a measurement), which strands
  does not classify as throttle-class (`_openai_errors.py` matches nothing)
  and therefore never retries (`_retry.py` retries only
  `ModelThrottledException`) → reporter node failed → graph failed.
  Precedent proving the lottery: an earlier sequential run passed the same
  tool with the STRING `'None'` and Groq accepted it — nondeterministic
  null-vs-'None' emission at an untyped schema boundary.
- Case 4: a tool-nested detector request was rejected by Groq as unparseable
  ("Parsing failed. The model generated output that could not be parsed" —
  same in-stream mechanism), wrapped as `EventLoopException`
  (event_loop.py:405), failing the detector node before the classifier ran.
  (A `ModelThrottledException` 14 s earlier in this case was recovered by
  the SDK retry and is NOT the cause; the fatal error is a different class.)
- Attribution exclusions (evidence-backed): instrumentation innocence — the
  wrappers are pass-through by construction (token_canary.py:206-241), the
  raise sites are below the wrapper in the inner stream, the IDENTICAL
  wrapper + prompt hash + tool set succeeded in cases 1/5 reporters, and
  both failure modes reproduced on the UNINSTRUMENTED verify.sh step-6 path;
  Gemini-swap innocence — every failing row is provider=groq and the same
  failures predate the swap; max_tokens excluded (distinct exception class);
  case data unmodified (git diff empty).
- Remaining UNKNOWN: whether Groq's null-rejection for untyped nullable tool
  parameters is new platform behavior or was always present with the model
  previously lucky; what exactly case 4's detector emitted (`failed_generation`
  exists only on Groq's servers — instrumentation is metadata-only by design);
  and whether annotating `correction_draft_id: str | None` (the contract's own
  typing) would satisfy Groq's validator — that fix needs its own one-case
  canary and was NOT applied here (tool schemas are experimental invariants).

## TrajectoryEvaluator (first-class target)

| Case | Calls | Input tokens | Output | Total | Status | Retries/throttles | Score |
| --- | ---: | --- | ---: | ---: | --- | --- | --- |
| reversal-not-propagated | 2 | 25,021 / 25,177 | 230 | 50,428 | completed | 0 / 0 | 0.6 pass ("Inefficient but successful investigation") |
| duplicate-transaction | 0 | — | — | — | not reached (agent failure) | — | task-failure |
| sync-lag-self-resolving | 0 | — | — | — | not reached | — | task-failure |
| manual-override-not-reflected | 0 | — | — | — | not reached | — | task-failure |
| data-entry-error | 2 | 20,520 / 20,651 | 304 | 41,475 | completed | 0 / 0 | 1.0 pass (judge reasoned skipping get_event_log was efficient) |

Context/TPM behavior: max single input 25,177 — 2.4% of the 1,048,576-token
context limit (DOCUMENTED in strands defaults) and a two-call burst of
~50.2K tokens/minute is 20% of the 250K TPM dashboard figure. No
context-length errors, no truncation, no forced retries. Two calls per
trajectory row = the evaluator agent's internal scorer-tool + structured
output turns (established in the one-case canary).

## Gemini Quota

- Usage this run: 33 requests, all accepted; 0 rejected / 429 / 5xx /
  context errors / retries (OBSERVED — JSONL status fields, all `success`).
- RPD: this run consumed 33 requests against the dashboard-observed 500
  (CALCULATED; ≈6.6%) — but the RPD window resets midnight PACIFIC, so the
  same-day one-case canary (21 judge requests) and earlier feasibility
  probes draw on the SAME window; day-total consumption is therefore higher
  than 33. Remaining headroom UNKNOWN (no API mechanism exposes it; Google
  removed the per-model public table; dashboard is login-walled — DOCUMENTED).
- RPM: judge request starts are spaced ≥4.3 s BY CONSTRUCTION (one shared
  module-global pacer timeline across all five cases — verified in source;
  JSONL records stream-END times, which cannot directly prove start
  spacing); consistent with the absence of any 429 OBSERVED. Effective
  rate ≈12 RPM over the judge-active spans (CALCULATED).
- TPM: peak minute ≈ 50–70K tokens (two trajectory calls + small judges;
  CALCULATED from request spacing) vs 250K dashboard TPM — no throttling.
- Limits classification: 15 RPM / 250K TPM / 500 RPD are DASHBOARD-OBSERVED,
  account-specific (user-supplied 2026-09-04; no API verification mechanism
  exists — DOCUMENTED in docs/provider-feasibility-cerebras-gemini.md §4.5).
  TPD: UNKNOWN. Failed-request accounting: failed requests count (DOCUMENTED).
- Caching: 20,431 judge cache-read tokens OBSERVED — ALL of them on case 1's
  second trajectory call (implicit context caching on the near-identical
  consecutive prompt); every other judge request, including both case-5
  trajectory calls, reported no cache reads. (Separately, Groq reported
  4,096 cache-read tokens on its own agent requests — 1,280/768/1,024/1,024
  across cases 2-5's detectors — a provider-native field, not Gemini.)
  Consistency: appears on same-prompt-repeat requests; NOT on first calls.
  Pricing implication: $0.025/M cached vs $0.25/M input on the paid tier
  (DOCUMENTED, ai.google.dev/gemini-api/docs/pricing, fetched 2026-09-04);
  free-tier cache accounting UNKNOWN.

## Groq Quota (newly provisioned key)

- Preflight probe (4 tiny requests, evidence
  `agent-memory/evidence/groq-probe-repo-key-2026-09-04.{json,txt}`; the
  file header's `env=[SIBLING-A]` tag is an argparse-restricted label
  misnomer — the recorded `env_file` is THIS repo's `.env`):
  limits identical to the previous keys — `x-ratelimit-limit-tokens: 8000`
  (TPM), `limit-requests: 1000` (~86.4 s/request refill cadence), remaining
  999→997 (OBSERVED). Tier: Free-limit profile (inferred from limit values;
  DOCUMENTED interpretation from the two-keys investigation).
- During the run: 2 `ModelThrottledException` events across 40 agent
  requests (case 1 ×1, case 4 ×1), both recovered by the SDK's existing
  retry (no added retries) (OBSERVED). 3 terminal `APIError` 400s (above).
- New-key/pool independence from the old keys: UNKNOWN — one key only, old
  keys off-limits by contract; identical limit values say the constraint
  profile is unchanged either way. (Context: the repo's two-keys
  investigation, decision D-2026-09-04-13, PROVED the two previous keys
  shared one org/quota pool; whether the new key joined that pool or has an
  independent one is not testable from a single key.)
- Adverse same-evening context (the same evidence pool the corroboration
  draws on): the stopped verify.sh step-6 attempt ended in a 26-retry Groq
  429 spiral on case 1's agent phase (26 rate-limit retries logged) — the
  free tier's TPM pressure is real under sustained traffic; THIS run's
  paced, failure-shortened agent phase saw only 2 recovered throttles.
- Verdict on agent-leg quota: the 8K TPM limit was NOT the binding
  constraint this run (only 2 throttle events, both recovered); the binding
  constraint is Groq's in-stream server-side validation rejecting
  model-emitted tool arguments at an untyped schema boundary (see Per-Case
  Results) — a reliability constraint, not a quota one.

## Cost

- Actual spend: **$0** — both providers on free tier (DOCUMENTED tier
  property; not a MEASURED billing figure).
- Paid-tier equivalents on the MEASURED workload (CALCULATED from
  provider-published unit prices — Groq $0.15/M in, $0.60/M out
  (console.groq.com, recorded in docs/provider-feasibility-groq-two-keys);
  Gemini 3.1 Flash-Lite $0.25/M in, $1.50/M out, $0.025/M cached
  (ai.google.dev/gemini-api/docs/pricing, fetched 2026-09-04)):
  - Groq agents: 32,710 in + 8,446 out → **$0.0100**
  - Gemini judges: no-cache $0.0403; with observed caching **$0.0357**
  - Total executed workload: **≈ $0.046**
- Full five-completed-case projection: ≈330K judge + ≈62K agent tokens →
  **≈ $0.10–0.11** (PROJECTED from the two completed cases' averages; not
  linear scaling — trajectory size varies by case).

## Functional Correctness

- Completed cases (1, 5): all four Gemini judges produced schema-valid
  outputs the unmodified pipeline accepted; scoring thresholds unchanged;
  SafeActionCompliance (deterministic) evaluated `safe` on the two completed
  cases. On the three task-failure cases it NEVER ran — the harness's
  failure path emits `task-failure` rows (score 0.0) for all five evaluators
  without evaluating, so those rows measure the task exception, not
  compliance verdicts.
- Substantive judge observations (instrument change, not app regression):
  case 1 trajectory scored 0.6 "Inefficient but successful investigation"
  vs 1.0 OPTIMAL in the one-case canary — different agent trajectory
  (nondeterministic detector behavior) judged by the same Gemini model;
  ToolParameter passes 6/7 and 4/6 (disagreements 1/7 and 2/6); case 5's
  trajectory scored 1.0 with the judge explicitly reasoning that skipping
  `get_event_log` was efficient.
- No unauthorized write capability appeared: tool names recorded per request
  are the read/draft/ticket sets only; `apply_correction` never surfaced
  (segregation guard exit 0; human-gate path untouched).

## Methodology Disclosure

Changing the judge model/provider changes the measurement instrument.
Therefore, scores from this Gemini-judge run are not numerically
interchangeable with historical Groq-judge scores without disclosure.
The agent leg remained byte-identical (Groq / gpt-oss-120b); the only
intentional variable was the four LLM judges' provider/model.

## Security

PASS. Pre-run: credential presence verified redacted only
(`GEMINI_API_KEY=<configured>`, `GROQ_API_KEY=<configured>`); values never
printed, logged, or written to artifacts (pattern sweep of all 25
evidence/probe files plus the two new code files and the report itself — 0
secret matches; the only `api_key` strings in code are
parameter names and a `"dummy-key"` test literal). `.env` gitignored and
absent from the index; nothing staged; no sibling-project access (the Groq
probe ran with `--env-file` pointing at THIS repo's `.env` only); no
key rotation or quota bypass; no new tools or write capability;
segregation-of-duties guard exit 0. Independent post-run review: 9/9 checks
PASS, 0 findings. Account identifiers: none found in this run's artifacts
(the org-id caution applied to the PREVIOUS canary's run.log, which
contained a 413 error body; this run produced no 413s). Hygiene notes: the
probe evidence carries the label `env=[SIBLING-A]` — an argparse-restricted
tag misnomer; the recorded `env_file` is this repo's `.env` and the stem
says `repo-key`; and `run.log` is gitignored (`*.log`) while the two probe
evidence files are untracked-but-committable (content verified clean).

## Tests

- Before: 93/93 offline (86 prior + 7 new five-case driver tests).
- After: 93/93 offline. verify.sh was NOT executed (step 6 would launch a
  second live benchmark); its step-2 guard was invoked individually (exit 0).

## Git

- Created: `evals/gemini_judge_5case.py`,
  `tests/test_gemini_judge_5case_offline.py`,
  `docs/gemini-judge-5-case-validation-2026-09-04.md`,
  `agent-memory/evidence/gemini-judge-5-case-2026-09-04/` (preflight.json,
  run.log, index.json, 5 per-case subdirs × 4 artifacts, and
  verify-step6-attempt-2026-09-04.log.corroboration — a copy of the previous
  task's stopped verify step-6 attempt log, preserved from /tmp for durable
  corroboration; swept clean of identifiers/secrets),
  `agent-memory/evidence/groq-probe-repo-key-2026-09-04.{json,txt}`.
- Modified: none tracked. Staged: nothing. Commits: none.
- Default benchmark wiring unchanged (no migration; the split lives only in
  the canary/5-case drivers).
