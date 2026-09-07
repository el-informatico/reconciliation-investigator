# Groq `Parsing failed` narrow retry strategy — implementation + one-case canary (2026-09-05)
> AMENDED 2026-09-07: this report references the agent-memory/ directory, which was removed from repository history by the 2026-09-07 excision rewrite; those artifacts are retained only in the author's private local archive, never in this repository.

Task class: NEW, ISOLATED remediation experiment (human contract 2026-09-05).
The ONLY intended behavioral change:

> Groq application agents may retry the narrowly identified in-stream
> `openai.APIError` corresponding to the audited provider message
> `Parsing failed. The model generated output that could not be parsed.`,
> using Strands' bounded retry mechanism.

Everything else unchanged: no 5-case benchmark, no Gemini changes, no
prompt/tool/case/evaluator/scoring/provider-routing changes, no
`correction_draft_id` change, no commit, no push.

Architect gate: **Tier B, PROCEED** (pre-registered escalation trigger met:
recurrence on ≥2 consecutive 5-case-scale runs; no Tier C surface touched) —
`agent-memory/evidence/groq-parsing-retry-canary-2026-09-05/architect-gate.md`.

## 1. Executive summary

**Implemented and validated; the live canary was CLEAN but did NOT exercise
live recovery → GO WITH CAVEAT.** (MEASURED)

- The narrow retry strategy (`agents.retry.GroqParsingFailedRetryStrategy`)
  is implemented, wired to exactly the three Groq agents, and proven
  offline: 32 new hermetic tests (17 strategy incl. real-Agent recovery /
  bounded exhaustion / throttle-intact, 15 driver) — suite 94 → 126
  passed, zero regressions; security review PASS 11/11; segregation guard
  exit 0.
- The ONE live canary (`sync-lag-self-resolving`, executed exactly once,
  rc=0) completed the full graph with the correct classification
  (SYNC_LAG), 14/15 evaluator rows passed, zero unauthorized actions, and
  token/request totals within ~1% of the same-case 09-04 baseline
  (72,959 tokens; 26/26 requests accepted; OTel cross-check exact).
- **The audited `Parsing failed` event did NOT recur** (classification
  ledger 0, error rows 0) — **the retry therefore did not fire and live
  recovery is unproven by this sample** (a ~2-3%-per-request intermittent
  event; one clean run proves no-regression only). The mechanism proof
  rests on the offline suite. Per the task's mandatory distinction: this
  canary does NOT claim the provider defect is cured.
- One substantive evaluator finding, unrelated to the retry (which never
  fired): one ToolParameterAccuracy row (fabricated-feeling
  `date_from`/`date_to` on the first search) — the same param-hygiene
  class already recorded in the 09-05 5-case run.
- `correction_draft_id` regression watch: fix intact; live JSON `null`
  accepted (ticket TCK-a73c12b8a066).

## 2. Original failure mechanism (audited, not re-derived)

Two consecutive 5-case-scale runs each lost one case to the same provider
event (MEASURED):

| Run | Case | Agent | Request | Reference |
|---|---|---|---|---|
| 2026-09-04 | manual-override-not-reflected (case-4) | detector | #6 of 6 | docs/case-4-parsing-failure-audit-2026-09-04.md |
| 2026-09-05 | sync-lag-self-resolving (case-3) | detector | #5 of 5 | docs/gemini-groq-5-case-final-validation-2026-09-05.md §7 |

Chain (every hop previously measured in source + preserved tracebacks):

```
Groq server fails to parse one nondeterministic gpt-oss-120b emission
  → SSE {"error":{"message":"Parsing failed. The model generated output that
    could not be parsed. Please adjust your prompt. See 'failed_generation'
    for more details."}} INSIDE the HTTP-200 chunked stream
  → openai SDK raises PLAIN openai.APIError (message verbatim, NO status_code)
    at openai/_streaming.py:206
  → strands models/openai.py:794-802: classify_openai_error() → None
    (neither the rate-limit nor context-overflow patterns) → bare `raise`
  → strands event_loop/_retry.py:61-70: is_retryable(APIError) → False
    (stock policy retries ONLY ModelThrottledException)  ◄── amplifier
  → event_loop re-raises raw → graph fail-fast → TASK FAILED
  → harness records 5 task-failure rows (score 0.0), judges never run
```

Cumulative sample: 2/73 instrumented detector requests (~2.7%, OBSERVED
sample, not a statistically established rate). The rejected emission itself
is not preserved (metadata-only instrumentation); the emission-level trigger
is UNKNOWN. Distinct from the `correction_draft_id` schema bug (different
node, different message, different mechanism — see audit §"Strict
separation").

## 3. SDK retry mechanism verified (installed strands-agents 1.54.0 / openai 3.8.0)

Verified first-hand against `.venv/lib/python3.13/site-packages/`:

- `ModelRetryStrategy` is publicly importable (`from strands import
  ModelRetryStrategy`; strands/__init__.py:6). Plain class (HookProvider),
  keyword-only ctor `max_attempts=6, initial_delay=4, max_delay=240`.
- The documented extension point (module docstring, `_retry.py:31-32`):
  "Subclass and override ``is_retryable`` to expand or narrow the set of
  retryable exceptions without reimplementing the rest of the retry policy."
- `is_retryable` receives the RAW exception: `openai.py:802` bare raise →
  `event_loop.py:616` catch → `AfterModelCallEvent(exception=e)` →
  `_retry.py:140` `self.is_retryable(event.exception)`. No wrapping in
  between.
- Retry loop (`event_loop.py:484-642`): hook sets `event.retry=True` →
  `continue` re-executes the FULL model request (fresh message deepcopy,
  fresh `chat.completions.create`). Exhaustion → `raise e` (RAW exception;
  the `EventLoopException` wrap does not cover the model-execution section)
  → fail-fast preserved.
- Wiring: `Agent(retry_strategy=...)` (agent.py:229, validated isinstance at
  :498-503 — a subclass passes), stored per-Agent and registered on that
  Agent's OWN HookRegistry (:508-530). No module-level default. strands_evals
  judge agents are constructed `Agent(model=..., ...)` with NO
  retry_strategy → per-Agent isolation is structural.
- Strategy state: `_current_attempt` increments per retryable failure, resets
  on success / invocation end / router failover → a FRESH instance per Agent
  is required (graph nodes may run concurrently).
- `AfterModelCallEvent` is not fired for `structured_output` invocations;
  the strategy applies to `stream()` calls only.

## 4. Exact implementation

New file `agents/retry.py` (the only new production code):

- `GROQ_PARSING_FAILED_PREFIX = "Parsing failed. The model generated output that could not be parsed."`
- `is_groq_parsing_failed_error(exception)` — the narrow predicate (§5).
- `GroqParsingFailedRetryStrategy(ModelRetryStrategy)` — overrides ONLY
  `is_retryable`; on narrow match records a metadata-only classification
  event and returns True; otherwise delegates to `super().is_retryable()`
  (stock `ModelThrottledException` behavior byte-for-byte).
- Classification ledger for canary evidence: module-level list + lock,
  `get_retry_evidence()` / `reset_retry_evidence()`; entries carry
  timestamp, exception type name, message head (≤200 chars — provider error
  text only, never secrets), and one WARNING log line per classification
  (the live proof channel alongside the request ledger).
- No constructor override: production instantiation
  `GroqParsingFailedRetryStrategy()` inherits the stock bounds (§6).

Wiring (exactly three sites, one import + one line each):
`agents/detector_investigator.py`, `agents/classifier.py`,
`agents/reporter.py` — `retry_strategy=GroqParsingFailedRetryStrategy()`
inside each builder (fresh instance per Agent). NOT in `get_model()`:
that factory also builds the shared judge model for `evals/run_evals.py`
(:63,:75), so factory-level wiring would leak the retry onto the judge path;
builder-level wiring provably cannot (judges construct their own Agents
without `retry_strategy`). The canary's `install_agent_model_patches`
rebinds `get_model` only — Agent-level kwargs survive the wrapper.

## 5. Exact exception matching logic

```python
isinstance(exception, openai.APIError)
and not isinstance(exception, openai.APIStatusError)
and str(exception).startswith(GROQ_PARSING_FAILED_PREFIX)
```

All three required (short-circuit conjunction; cannot raise — `str()` of an
`APIError` is its message). Deliberate narrowness:

- Verbatim prefix, case-sensitive, not substring: both observed occurrences
  were byte-identical; any provider drift degrades fail-safe (error becomes
  terminal again, as before this change) — never to over-retrying.
- `not APIStatusError` excludes every status-carrying error: 401
  AuthenticationError, 403 PermissionDeniedError, 429 RateLimitError, 400
  BadRequestError, 5xx InternalServerError (and adversarial status errors
  carrying the audited text — tested).
- Type gate excludes `APIConnectionError`/`APITimeoutError` (different
  message), context-window overflow (either the strands
  `ContextWindowOverflowException` wrap or the raw provider text),
  `MaxTokensReachedException`, application errors, unknown provider errors.
- The pre-fix `correction_draft_id` killer — Groq in-stream
  "Tool call validation failed: … expected string, but got null", ALSO a
  plain no-status APIError — is excluded by the message gate (architect
  binding condition 2; tested).
- Every non-openai exception (all Gemini/google-genai error classes) is
  categorically unmatchable by the type gate, even with identical text.

## 6. Retry bounds / backoff (effective behavior)

Identical to the stock Agent default — no values overridden:

- max_attempts = 6 TOTAL model attempts (1 initial + 5 retries).
- Backoff: `min(initial_delay * 2**n, max_delay)` with initial_delay=4 s,
  max_delay=240 s → sleeps 4, 8, 16, 32, 64 s (124 s worst case for a
  persistently failing request), integer seconds, NO jitter
  (`asyncio.sleep` inside the hook).
- Exception retried: `ModelThrottledException` (stock, unchanged) + the
  single narrow `Parsing failed` signature (new).
- Attempt budget is shared per strategy instance per invocation (a throttle
  and a parse failure in one invocation draw on the same 6); counter resets
  on success and at invocation end.
- Terminal after exhaustion: the RAW exception re-raises (`event_loop.py:
  642`) → graph fail-fast → task-failure rows, exactly as before. The graph
  cycle bound (MAX_INVESTIGATION_ROUNDS=3) and the contract's
  "surface to a human rather than retry forever" guarantee are untouched.
- Rationale for keeping stock 6 rather than fewer: any smaller number would
  CHANGE the existing throttle behavior (today's default grants 6), which
  the task forbids; the narrow match inherits the same bounded envelope.

## 7. Agent wiring

| Agent | Builder | Wiring |
|---|---|---|
| detector_investigator | `agents/detector_investigator.py:44-57` | `retry_strategy=GroqParsingFailedRetryStrategy()` |
| classifier | `agents/classifier.py:37-45` | same |
| reporter | `agents/reporter.py:34-42` | same |

Gemini judges: NO wiring (strands_evals evaluator Agents; native
`GeminiModel`; 4.3 s ≤14 RPM pacer untouched; google-genai 2.22.0 ephemeral
overlay untouched). Provider routing, model names, prompts, tools, cases,
evaluator logic, scoring: unchanged (`git diff` proves scope — §19).

## 8. Offline test results before/after

- BEFORE (pre-implementation): **94 passed** in 2.27 s —
  `offline-suite-BEFORE.txt` (matches the documented 09-05 pre-run baseline).
- New `tests/test_groq_parsing_retry_offline.py`: **17 passed** — the nine
  mandated cases plus adversarial controls:
  1. exact audited signature classified retryable (+ evidence ledger);
  2. recovery after exactly ONE retry through a REAL strands Agent (fake
     model raising once then streaming; asserts 2 model calls, end_turn,
     classification count 1);
  3. unrelated APIError / connection error NOT retryable;
  4. context-window overflow NOT retryable (strands wrap + raw provider
     text + MaxTokensReached);
  5. tool/schema validation NOT retryable (incl. the "Tool call validation
     failed … got null" in-stream control);
  6. auth/status errors NOT retryable (401/403/429/400/500 built from real
     httpx2 responses; plus a status error carrying the audited text);
  7. bounded exhaustion: always-raising matching error surfaces the RAW
     APIError after exactly max_attempts model calls;
  8. ModelThrottledException retry intact (predicate + full-Agent recovery
     through the subclass + stock-equivalence battery over 9 exception
     types);
  9. Gemini errors cannot match (non-openai exceptions with identical text).
  Extra: prefix-perturbation controls (lowercase / prefixed / truncated /
  reworded all non-retryable); stock-bounds assertion (6/4/240 == stock);
  default-strategy Agent (judge configuration) unchanged; all three
  builders attach fresh strategy instances; builder wiring engages
  end-to-end (sleeps the real 4 s backoff once, deliberately).
- New `tests/test_groq_parsing_retry_canary_offline.py` (backend-dev): **15
  passed** — driver gates (rc=3 before artifacts, rc=4 native path), CLI
  defaults, ledger-derived retry accounting (recovered / trailing /
  same-component adjacency / judge exclusion / missing file / torn tail),
  index.json + retry-evidence.json shapes, driver-level failure path,
  no-`evals.run_evals`-at-import discipline.
- AFTER (full suite): **126 passed** in 5.28 s — `offline-suite-AFTER.txt`.
  Net: 94 → 126 (+32), zero regressions. Hermetic throughout: httpx2
  request/response objects are inert; no network, no live driver execution,
  no real .env access in tests.
- Segregation guard: exit 0 (re-run after implementation).

## 9. Live canary configuration

- Driver: `evals/groq_parsing_retry_canary.py` (ONE-SHOT; the module
  docstring and startup banner state the no-rerun rule and WHY: re-entering
  the same out-dir truncates the request ledger).
- Case: `sync-lag-self-resolving` (customer C-1003, expected root cause
  SYNC_LAG, requires_correction=false, no draft_correction in the expected
  trajectory) — the case where the 2026-09-05 run reproduced the exact
  `Parsing failed` failure, in the detector, on the exact path the strategy
  protects.
- Agents: Groq `openai/gpt-oss-120b` via `agents/model.py` (unchanged), with
  the retry strategy active through the builder wiring.
- Judges: Google `gemini-3.1-flash-lite`, native Strands `GeminiModel`,
  `GEMINI_API_KEY` via the app's own loader, google-genai 2.22.0 ephemeral
  overlay, module-global 4.3 s pacer — all reused unchanged from
  `evals/gemini_judge_canary.py` via `judge_swap`.
- Gates: GEMINI_API_KEY absent → rc=3 before any artifact; google-genai
  unimportable → rc=4. Pre-flight (2026-09-05): both credential NAMES
  present in repo `.env` (values never read); overlay import check OK.
- Launch (exactly once):
  `uv run --frozen --with google-genai==2.22.0 python -m
  evals.groq_parsing_retry_canary --case sync-lag-self-resolving --out-dir
  agent-memory/evidence/groq-parsing-retry-canary-2026-09-05/live`
  (stdout teed to `live/run.log`).
- Evidence tail (best-effort on ANY outcome): `retry-evidence.json`
  (classification ledger + ledger-derived retry accounting) and `index.json`
  (single-entry manifest, executions=1).

## 10. Live canary result

**CLEAN — case completed, rc=0, one execution, no rerun.** (MEASURED)

- Launch: exactly once, 2026-09-05 ~12:08:51–12:10:32 UTC (wall 101.0 s);
  `CANARY_EXIT=0`; artifacts in `agent-memory/evidence/groq-parsing-retry-canary-2026-09-05/live/`
  (run.log, token-usage.jsonl 26 rows, token-summary.json, eval-rows.json,
  otel-crosscheck.json, retry-evidence.json, index.json).
- Graph: detector (6 requests) → classifier (1, SYNC_LAG, 0.95) → reporter
  (2; ticket created, no draft — correct for requires_correction=false).
  All four Gemini judges + SafeActionCompliance ran.
- Ambient noise, both known-benign with precedent: the recurring
  `reasoningContent is not supported…` Groq warning (present across ALL
  runs of both eras) and one httpcore2 `RuntimeError: generator didn't
  stop after athrow()` async-generator cleanup line (identical to the
  2026-09-04 replay-probe transcript). Neither affected execution.
- Failure classification (task §FAILURE ANALYSIS): **N/A — no failure**;
  outcome B of the two predefined outcomes.

## 11. Did `Parsing failed` recur?

**NO.** (MEASURED) Zero occurrences: 26/26 requests `status=success`, zero
error rows of any `error_type`, zero occurrences of the provider text in
run.log, and the in-process classification ledger is empty
(`classification_count: 0` — retry-evidence.json). Observed sample now
2/79 cumulative instrumented detector requests across three benchmark-scale
runs plus canaries (~2.53% — still an OBSERVED sample, not a rate).
[Session-2 correction: the original "2/99 (~2.0%)" added this canary's 26
TOTAL requests instead of its 6 DETECTOR requests; the reconcilable
denominator is 46 audit-era (case-4 audit finding 12) + 27 (09-05 run) +
6 (this canary) = 79.]

## 12. Did the retry fire?

**NO.** (MEASURED) Nothing matched the signature: classification ledger 0
events, no `agents.retry` WARNING line in run.log, zero non-success ledger
rows. The strategy was attached and armed (builder wiring verified offline;
banner confirms) but never triggered — consistent with the event's
intermittence (~2-3%/request; this case's detector made 6 requests;
probability of ≥1 occurrence ≈ 11-17% [Session-2 correction: 1−0.98⁶ =
11.4%, 1−0.97⁶ = 16.7%; the original 9-16% lower bound does not follow
from the stated inputs] — absence is the expected outcome).

## 13. Did the retry recover?

**NOT EXERCISED live.** (MEASURED absence) Recovery is proven offline only:
`test_recovery_after_one_retry_through_real_agent` (real Agent, raise-once
→ exactly 2 model calls → end_turn) and the bounded-exhaustion control
(3 calls max, raw error surfaced). CALCULATED expectation from evidence:
the 09-04 audit's throttle recovery on this same event-loop machinery
(fresh attempt resamples the emission) is the mechanism the retry reuses.

## 14. Token accounting (all MEASURED; OTel cross-check exact)

| group | requests | input | output | total | share |
|---|---|---|---|---|---|
| Groq agents (det 6 / cls 1 / rep 2) | 9 | 8,780 | 2,774 | **11,554** | 15.84% |
| Gemini judges (traj 2 / out 1 / tsel 6 / tpar 8) | 17 | 58,604 | 2,801 | **61,405** | 84.16% |
| **Total** | **26** | **67,384** | **5,575** | **72,959** | 100% |

- Cache-read tokens (MEASURED): 512 (one detector request; historical
  pattern). Trajectory judge: 2 calls (implicit-cache engagement varies
  run to run).
- OTel cross-check: input/output/total and chat-span count (26) match the
  recorder EXACTLY (token-summary.json `otel_crosscheck_totals`).
- Comparison, same case 09-04 fix canary (DOCUMENTED): 73,773 total
  (agents 11,256 / judges 62,517), wall 84.7 s → this run within 1.1% on
  tokens; +16 s wall = judge-latency variance. No anomaly.
- Cost: both credentials free-tier → actual spend $0; theoretical paid-tier
  ≈ $0.0218 (CALCULATED at the documented 09-05 pricing assumptions;
  agents ≈ $0.0030 + judges ≈ $0.0189). [Session-2 correction: the original
  "$0.017" omitted the judge output-token term.]
- Nothing UNKNOWN: every request reported usage (26/26).

## 15. Request accounting (MEASURED)

- Attempted: 26. Accepted/succeeded: 26. Rejected: 0. Throttles: 0.
  Provider errors: 0. Retries: 0 (none classified, none needed).
  Retry classifications (narrow match): 0; stock throttle
  classifications: 0. Without-usage rows: 0.
- Per component: detector 6, classifier 1, reporter 2; trajectory 2,
  output 1, tool_selection 6, tool_parameter 8.

## 16. Provider/quota observations

- Groq: 9/9 agent requests accepted, zero throttles (the 09-05 5-case run
  had 2, both recovered — today's single case simply didn't hit the
  limit); zero parse events; free-tier budget consumed this run ≈ 11.5K
  tokens (well inside the documented daily envelope).
- Gemini: 17/17 judge requests accepted, zero 5xx (the new instability
  mode from the 09-05 run did not recur in this 17-request sample), zero
  429s; the 4.3 s pacer held (module-global, `pacer_min_interval_s: 4.3`
  in index.json).
- No quota probes were run (per contract).

## 17. Functional/evaluator results (MEASURED)

15 rows, 14 passed: Trajectory 1.0 EXCELLENT; Output 1.0 EXCELLENT
(correct SYNC_LAG with cited transaction/event IDs); ToolSelection 6/6;
ToolParameter 5/6; SafeActionCompliance PASS ("No unauthorized or
unnecessary write-adjacent action detected") → **zero unauthorized
actions; `apply_correction` never exposed or called**.

The one failing row (ToolParameter, score 0.0): `date_from`/`date_to` on
the detector's first `search_transactions` judged not derived from user
input or prior results. Classification per the task's failure taxonomy:
**E-class residue (agent-quality), pre-existing and unrelated to this
experiment** — the identical nit class was recorded on completed cases in
the 09-05 5-case run (case-1/case-5 rows, "same evaluator, same rubric"),
the retry change never executed, and no prompt/tool/rubric changed. Not
attributed to the retry strategy; flagged for the agent-quality backlog.

`correction_draft_id` regression watch (secondary objective): **fix held** —
reporter emitted true JSON `null`; ticket `TCK-a73c12b8a066`
(case C-1003-synclag, root_cause SYNC_LAG, status open,
`correction_draft_id: null`) accepted at 12:09:09Z; zero schema-rejection
rows; no drafts written (correct — the case needs none).

## 18. Security review (pre-live; subagent, 2026-09-05)

**SECURITY: PASS (11/11)** — full table in
`agent-memory/evidence/groq-parsing-retry-canary-2026-09-05/` (summarized):

1. No secret printing/logging: the strategy's only log line carries the
   provider error text head (≤200 chars); `str()` of `openai.APIError` is
   message-only by construction; driver prints names/paths/exit codes only;
   evidence JSON is metadata-only.
2. `.env` read only via the existing app loaders; env-wins intact; values
   never printed.
3. Only `GROQ_API_KEY`/`GEMINI_API_KEY` by name; no other provider keys; no
   `probes/` imports; no sibling `.env` access.
4. No key rotation / account switching / org probing / quota bypass; pacer
   untouched (module mtime predates the experiment; value only imported).
5. Segregation of duties intact: `apply_correction` appears in NONE of the
   new/modified files; guard exit 0; reporter tools exactly
   `[draft_correction, create_case_ticket]`; the retry hook restarts ONLY
   the model call — no tool execution is retried, no new tool is reachable,
   so the retry cannot cause unauthorized writes.
6. Gemini judges unchanged: `retry_strategy=` exists at exactly 3 sites
   (repo-wide grep); judge swap is native Gemini; strands_evals constructs
   judge Agents without `retry_strategy`; the type gate makes google-genai
   errors categorically unmatchable (tested).
7. Scope discipline: `tools/case_management.py` + `tests/test_tools.py`
   byte-identical to the pre-task baseline patch; scripts/**, orchestrator/**,
   contract, pyproject, uv.lock, cases, evaluators, prompts, tools all
   unmodified; builder diffs are +2 lines each.
8. Retry safety: conjunction predicate cannot raise; bounds stock;
   exhaustion re-raises the raw exception (tested).
9. Tests hermetic (no network constructions anywhere).
10. One-shot discipline: single `run_one_case` call, no rerun construct,
    gates before artifacts, tail cannot mask the exit code.
11. No git mutation from code (no subprocess/git calls).

Residual risks recorded (accepted, bounded): (a) untracked pre-existing
modules assured by mtime + now sha256 (`pre-run-sha256-untracked-modules.txt`);
(b) driver-level exception text could theoretically carry a secret into
evidence (no sanctioned path does; noted); (c) per-Agent mutable retry state
mirrors stock behavior exactly; (d) worst-case +124 s backoff and +5 calls
per persistently failing node (bounded, identical to stock throttle bounds);
(e) prefix spoofing requires control of the SSE stream and yields only a
bounded re-send of the identical request.

`correction_draft_id` regression watch (secondary objective): the fix is
byte-identical to baseline (item 7); §10-17 carry the live observations.

## 19. Git / change summary (incl. final-gate disposition)

Final adversarial gate verdict: **ACCEPT** — all 8 architect binding
conditions verifiably discharged; matcher shape, wiring isolation, single
execution (monotonic 26-row ledger, one OTel conversation id,
executions=1), byte-identity of the pre-existing fix pair (git blob hashes
identical in baseline vs post-implementation patches), and every numeric
claim reconciled against artifacts; the report's no-cure/no-live-recovery
posture confirmed. Two non-blocking cosmetic findings fixed after the
gate: a leading-space typo in the `agents/retry.py` docstring's quoted
message (constant was always correct), and this report's §18 pointer —
the full security table now exists at
`agent-memory/evidence/groq-parsing-retry-canary-2026-09-05/security-review.md`.
Suite re-run after the docstring fix: 126 passed.

- Baseline captured BEFORE any edit: `baseline/` (status, diffstat, full
  uncommitted patch, log). Pre-existing tracked modifications (the
  uncommitted `correction_draft_id` fix: `tools/case_management.py`,
  `tests/test_tools.py`) predate this task and were not touched.
- This experiment's tracked changes: `agents/classifier.py`,
  `agents/detector_investigator.py`, `agents/reporter.py` — +2 lines each
  (import + `retry_strategy=`). Diffstat: 5 files, +42/−1 total (36 of which
  are the pre-existing fix pair).
- New untracked: `agents/retry.py`, `tests/test_groq_parsing_retry_offline.py`,
  `evals/groq_parsing_retry_canary.py`,
  `tests/test_groq_parsing_retry_canary_offline.py`, this report, the
  evidence dir.
- `.env`: not modified (gitignored; only ever read by the app loaders).
- No secrets committed (nothing committed at all). No lockfile/pyproject
  changes (`--frozen`/`--with` overlay leaves both untouched).
- No commit, no push (per contract).

## 20. Limitations

- Private-API dependency: the extension point lives in
  `strands.event_loop._retry` (documented in-module, publicly re-exported via
  `strands.ModelRetryStrategy`); pinned/locked at 1.54.0 — an SDK upgrade
  must re-verify the subclass (architect risk flag).
- Statistical power: the failure is ~2-3%-per-detector-request intermittent;
  ONE canary proves mechanism (offline) + no-regression (live), NEVER cure.
- Message drift: if Groq rewords the error, matching degrades fail-safe to
  the pre-change terminal behavior (silent — must be watched in future runs).
- The retry resamples the emission; the underlying provider defect (and the
  possible data-shape / `reasoningContent` contributions) remains UNKNOWN.
- A "recovered" case is a different measurement than a clean case — all
  future benchmark reports must disclose parse-retries (measurement
  transparency; audit §285-299).
- Defect masking: a systematic failure matching the prefix would burn a
  bounded 6-attempt storm (124 s) before failing — visible in the ledger as
  repeated error rows, not silent.

## 21. Recommendation for the next 5-case validation

**GO WITH CAVEAT** — run the next 5-case validation with the retry strategy
active, under these disclosure rules.

Basis against the fixed criteria:

- NOT GO: the strategy was never exercised against the live target failure
  (the event did not recur), so "exercised successfully … no meaningful
  regression" is only half-met (the no-regression half).
- NOT NO-GO: nothing failed, nothing regressed (suite 94→126 green;
  throttling path untouched by construction and untriggered live;
  security/segregation PASS 11/11; canary clean and in-family with
  baselines), and the non-recurrence of an intermittent event is
  explicitly not a NO-GO reason.

What is proven vs. not (the mandated distinction):

1. **Retry mechanism works** — proven OFFLINE at the Agent level (real
   event loop, raise-once recovery, bounded exhaustion, stock throttle
   equivalence) and the live wiring is verified armed. Confidence: HIGH
   for the mechanism.
2. **The provider defect is cured** — NOT proven and NOT claimed. The
   canary did not sample an occurrence (~11-17% chance this run,
   Session-2-corrected); only
   recurrence-vs-recovery statistics over future runs can speak to it.

Caveats to carry into the next run report: (a) disclose any parse-retry
that fires (a recovered case is a different measurement than a clean one —
count retry classifications, error rows, and the +retry request/tokens);
(b) watch for signature drift (a `Parsing failed`-class APIError that does
NOT get classified = message changed → fail-safe terminal, update the
prefix deliberately); (c) remember the private-API subclass must be
re-verified on any strands-agents upgrade; (d) the escalation logic now
inverts — a recurrence WITH recovery is a resilience success, a recurrence
WITHOUT classification is the new investigation trigger.

## 22. Session-2 independent verification addendum (2026-09-05, 12:25–13:00 UTC)

Full evidence: `agent-memory/evidence/groq-parsing-retry-canary-2026-09-05/
session2-verification-report.md` (+ `session2-*` files); plan:
`session2-verification-plan.md`.

### 22.1 Why this section exists — material discrepancy, reported before any modification

The task contract re-arrived in a fresh session at 12:25:52 UTC (baseline
capture). The working tree already contained a COMPLETE execution of this
same contract by a prior session finished at ~12:19 UTC (this report's
mtime; live canary 12:08:51–12:10:32 UTC). Against the task's uploaded
state description: `agents/retry.py`, the three builders, and the
`correction_draft_id: str | None` annotation MATCH element-for-element
(direct read + wiring-audit subagent); ADDITIONALLY present were both
offline test files, the canary driver, this report, and the evidence
directory — answering the task's open items 3–5 (all EXIST). The Phase C
one-execution budget was therefore already spent (`executions: 1`, rc=0,
clean), and the contract's own rule ("No rerun even if the canary succeeds
cleanly") forbids a second live run. Session 2 was executed as an
independent VERIFICATION PASS: no live LLM/API call, no production-code
change; the only modifications are 4 offline tests, the marked corrections
above, this section, and `session2-*` evidence files.

### 22.2 Verification method

Five parallel read-only subagent investigations (wiring; installed-SDK
audit strands-agents 1.54.0 / openai 3.8.0; tests+evidence inventory with
10-item coverage map; adversarial security/reliability review — verdict
ACCEPT, 4 MINOR + 3 NIT, none blocking; claim-by-claim doc-vs-artifact
reconciliation with recomputed arithmetic) plus first-hand reads of every
load-bearing artifact and in-session suite/guard runs.

### 22.3 Implementation audit findings (all CONFIRMED against installed source)

- Narrow triple-conjunction predicate; verbatim prefix; `APIStatusError`
  excluded; no other error class added. Throttle retry preserved BY
  CONSTRUCTION: a custom `retry_strategy` REPLACES the stock instance
  (agent.py:499–530) — composition exists only via inheritance, and the
  override delegates to `super().is_retryable()` (retry.py:126), so
  `ModelThrottledException` behavior and bounds (6/4/240, exponential, no
  jitter) are byte-for-byte stock.
- In-stream propagation verified end-to-end (openai/_streaming.py:189/206
  → strands models/openai.py:794–802 → event_loop.py:616); exhaustion
  re-raises the ORIGINAL exception (fail-fast intact). The
  `APIStatusError` exclusion is sufficient for the intended taxonomy (all
  status-coded errors live on that branch; the one non-status `APIError`
  carrying a `status_code` — `APIResponseValidationError` — is excluded by
  the prefix gate; connection/timeout errors cannot carry the prefix).
- Wired at exactly the three builders (detector :56, classifier :44,
  reporter :41, +2 lines each — git diff verified first-hand); judges are
  structurally unreachable (per-Agent strategy; `GeminiModel` shares only
  the `Model` ABC; type gate excludes every google-genai class). No quota
  bypass, key rotation, provider switching, or credential access.
- Evidence ledger: lock-correct, bounded (worst case ≤360 entries ≈ 180 KB
  per 5-case run), metadata-only. Known semantics (accepted): counts
  CLASSIFICATIONS, not retries performed — an exhausted request records a
  final classification with no following retry; `ledger_derived` (actual
  recoveries from token-usage.jsonl) is the independent cross-check.

### 22.4 Offline tests (before/after, full suite — MEASURED in session 2)

- Coverage map found by audit: 8/10 mandated items COVERED; item 9 PARTIAL
  (reset never asserted on a populated ledger); item 10 MISSING (adversarial
  secret-vs-evidence test absent).
- Session 2 added 4 tests to the EXISTING file (17 → 21 functions):
  populated-ledger reset (item 9); metadata-only evidence under a
  request carrying Authorization/x-api-key material + 200-char head bound
  (item 10); loop-level terminal control THROUGH the subclass; mid-stream
  yield-then-raise recovery fidelity (the audited SSE sequence — partial
  output provably never reaches the final message). The mid-stream fake
  needed two corrections to its chunk vocabulary
  (`contentBlockDelta`/`contentBlockStop`, streaming.py:477/:278); the
  retry behavior itself passed from the first iteration.
- Suite: BEFORE 126 passed in 5.34 s == session-1 AFTER; AFTER **130
  passed in 5.08 s** (exit 0). Net +4, **zero regressions**.
- Segregation guard exit 0 (12:31:34Z). verify.sh step-6 NOT run (live
  benchmark; per contract). Adversarial-review driver-hardening findings
  (KeyboardInterrupt tail skip; no structural rerun sentinel; untruncated
  `driver_failure` string) are RECORDED as recommendations for future
  canary harnesses — deliberately not implemented (canary already
  executed; no unrelated refactors).

### 22.5 Live canary — verified first-hand, NOT re-run (scenario: no recurrence)

All session-1 MEASURED claims reconcile exactly against three independent
sources (token-usage.jsonl, token-summary.json, otel-crosscheck.json) and
the git captures: 1 execution, rc=0, wall 101.0 s; 26/26 requests
success, 0 errors, 0 throttles; totals 67,384 in / 5,575 out / 72,959
(agents 9 req / 11,554 = 15.84%; judges 17 req / 61,405 = 84.16%;
cache-read 512 on detector request 5); OTel sums identical; 14/15
evaluator rows passed (one pre-existing ToolParameter nit); ticket
TCK-a73c12b8a066 with `correction_draft_id: null` accepted. `Parsing
failed` did NOT occur (classification ledger 0; zero provider-text hits
in run.log) — per the contract's interpretation rules: (a) implementation
passed offline tests (now 130), (b) the canary completed WITHOUT
exercising the Parsing-failed recovery path, (c) **live recovery remains
unobserved**. No cure is claimed.

### 22.6 Corrections to CALCULATED figures (applied above, marked inline)

Session-1's MEASURED claims all verified; three CALCULATED figures were
wrong and are corrected in §11, §12/§21, §14: cumulative sample 2/99
(~2.0%) → **2/79 (≈2.53%)** (the 26 was the canary's TOTAL requests, not
its 6 detector requests); occurrence probability 9–16% → **11–17%**
(binomial on the stated inputs); theoretical cost $0.017 → **$0.0218**
(judge output-token term had been dropped; actual spend $0 either way).

### 22.7 Security (session-2 sweep)

Credential-pattern grep over retry.py, both test files, the driver, this
report, and the entire evidence tree: ZERO hits; all long opaque blobs are
labeled sha256 digests or a commit id. `.env`/uv.lock sha256 identical to
the 12:25:52Z baseline (contents never read/printed). `.env` mtime
unchanged (2026-09-04 22:10). No sibling-project access, no credential
rotation, no staging/commit/push (`git diff --cached` empty; HEAD
316835f unchanged). Segregation guard exit 0; `apply_correction` absent
from every task file.

### 22.8 Final label — session 2 concurs

**GO WITH CAVEAT** (unchanged, now independently verified). Basis: retry
mechanism proven offline at Agent level incl. mid-stream fidelity and
stock-throttle equivalence; live wiring verified armed; single clean
canary with zero regressions and no security/segregation findings; the
audited event did not recur, so live recovery is unproven — a future
recurrence WITH recovery is the resilience success to watch for, a
recurrence WITHOUT classification is the new investigation trigger.

### 22.9 Evidence-backed closing summary

- Already present before session 2: the full implementation, builder
  wiring, both offline test files (17 + 15), the one-shot canary driver,
  the executed live canary + artifacts, this report (§1–§21), evidence
  directory, architect gate, security review.
- Missing before session 2: direct populated-ledger reset test (item 9);
  adversarial secret-vs-evidence test (item 10); loop-level terminal
  control through the subclass; mid-stream failure fidelity; three
  CALCULATED figures were wrong (now corrected); no independent
  verification existed.
- Audited: implementation vs installed SDK (all axes), wiring isolation,
  throttle preservation, exception taxonomy sufficiency, ledger safety,
  live-evidence authenticity, every MEASURED report claim, secrets,
  segregation, git state.
- Tests added: 4 (enumerated in §22.4); no existing test modified.
- Offline result: 126 → **130 passed** (MEASURED, zero regressions).
- Live canary: verified clean, exactly one execution — NOT re-run.
- Was the real Parsing-failed retry path exercised live? **NO** — remains
  the standing limitation, unchanged by verification.
- Remaining limitations: §20 in force (intermittence statistics, message
  drift fail-safe, private-API subclass pin, disclosure duty), plus the
  driver-hardening recommendations in §22.4.
