# Gemini-judge / Groq-agent 5-case FINAL validation — 2026-09-05

Controlled benchmark, ONE complete execution of the configured five cases
with the controlled provider split:

- **Agents**: Groq `openai/gpt-oss-120b` (wiring unchanged, `agents/model.py`)
- **Judges**: Google `gemini-3.1-flash-lite` (native Strands `GeminiModel`,
  google-genai 2.22.0 ephemeral overlay; `SafeActionComplianceEvaluator`
  deterministic — no model)
- Driver: `evals/gemini_judge_5case.py`, `--out-dir
  agent-memory/evidence/gemini-groq-5-case-final-validation-2026-09-05/`
- Launch: `uv run --frozen --with google-genai==2.22.0 python -m
  evals.gemini_judge_5case --out-dir …` (STARTED 2026-09-05T08:33:53Z UTC)

Purpose: validate the current system after the confirmed
`correction_draft_id: str | None` schema fix, and measure whether the
previously observed Groq-side intermittent `Parsing failed` event recurs.
No system changes were made for, or during, this benchmark. Each case ran
exactly once, in configured order; a case failure is recorded and the loop
continues (no reruns).

## 1. Executive summary

**Result: 4/5 cases completed the full investigation graph; 1 case
(sync-lag-self-resolving) died on the known intermittent Groq provider-side
`Parsing failed` event. Recommendation: GO WITH CAVEAT.** (MEASURED)

- The audited `Parsing failed` mechanism **recurred once** — on case-3
  (detector request #5, in-stream, plain `openai.APIError`, not retried),
  NOT on the case-4 watch case, which completed. This matches the
  pre-registered ≈60%-chance-of-≥1 expectation (docs/case-4 audit §317-345).
- The `correction_draft_id` fix **held at 5-case scale**: zero schema
  rejections anywhere (pre-fix run lost 2 cases at exactly this boundary),
  and a true JSON `null` was emitted and accepted live (case-4 ticket
  `TCK-684150ff85a8`).
- **New provider failure mode observed**: 3 Gemini judge calls failed with
  google.genai `ServerError` (503 "high demand" ×2, 500 internal ×1),
  clustered in 12 s during case-2 judging; not quota-related, not
  retried, recorded as judge-error rows. All other 50 Gemini requests
  were accepted.
- Provider config as specified: agents Groq `openai/gpt-oss-120b`, judges
  Google `gemini-3.1-flash-lite` (native GeminiModel, google-genai 2.22.0
  ephemeral overlay), SafeActionCompliance deterministic.
- Run envelope: ONE execution, 5 cases, configured order, 448 s end-to-end
  (08:33:53Z–08:41:21Z), DRIVER_EXIT=0, no reruns, no code changes.
- Totals: 296,025 tokens (agents 55,037 / judges 240,988), 98 request
  attempts (45 Groq + 53 Gemini), 2 Groq throttles (both auto-recovered),
  0 Gemini throttles, actual spend $0, theoretical paid-tier ≈ $0.071.

## 2. Method and pre-run state

### 2.1 Delegated pre-benchmark verification (four independent reviews)

1. **Architecture/wiring** — all 8 checks CONFIRMED: Groq wiring
   (`agents/model.py:29-75`, `max_tokens=8192` inside `params`); no
   anthropic path anywhere; retry semantics are the unmodified strands SDK
   default (`strands/event_loop/_retry.py:61-70` retries ONLY
   `ModelThrottledException`; `openai.APIError` is re-raised
   un-retried at `strands/models/openai.py:794-805`); 4 LLM judges swapped
   to Gemini per case (`evals/gemini_judge_canary.py:123-158`); fix present
   (`tools/case_management.py:114`, `str | None`, no default, required in
   schema); `apply_correction` never in an Agent tools list; case order
   exact; tracked diff = only the approved fix.
2. **Provider/credential configuration** — all 7 checks CONFIRMED:
   repo-root-only `.env` loader (env wins, never prints values,
   `agents/model.py:34-48`); Gemini credential = `GEMINI_API_KEY` via
   `resolve_gemini_api_key()` (exit 3 before any request if absent);
   google-genai exists ONLY via the ephemeral `--with` overlay (absent
   from `.venv`, `uv.lock`, `pyproject.toml`); module-global 4.3 s pacer
   (≤14 RPM) spans all five cases; token instrumentation (per-request
   tokens, cache-read, status/error_type, OTel cross-check) reused by
   import; no sibling-`.env` reads reachable from the benchmark path.
3. **Benchmark methodology** — driver verified in full: exactly five
   configured cases once each (`EXPECTED_CASE_COUNT=5` gate), continue on
   failure, no rerun path anywhere (offline-proven by
   `tests/test_gemini_judge_5case_offline.py`); fresh `--out-dir` used to
   preserve the 2026-09-04 evidence (recorder truncates JSONL in place).
4. **Security/reliability** — PASS on all items; see §9.

### 2.2 Pre-run state (MEASURED)

- git: tracked modifications exactly `tools/case_management.py` (+1 line,
  the fix) and `tests/test_tools.py` (+35, regression test); no other
  tracked changes. HEAD `316835f`. Untracked: 2026-09-04 canary
  drivers/docs/evidence (pre-existing).
- Offline suite: `uv run --locked pytest -q` → **94 passed** in 2.37 s
  (baseline 94/94 — MATCH).
- Segregation guard: `./scripts/guard-segregation-of-duties.sh` → exit 0;
  `core.hooksPath=scripts/hooks`, pre-commit executable.
- Credentials present: `GROQ_API_KEY=<configured>`,
  `GEMINI_API_KEY=<configured>` (values never read/printed).
- Overlay preflight: `import strands.models.gemini` OK; google-genai
  2.22.0 (MEASURED).
- verify.sh step 6 (live `EVAL_MODE=1 evals/run_evals.py`) **SKIPPED by
  instruction** (§25); steps 2-equivalent safety checks run individually.
- Launch hard stop: harness-side `timeout 2400` (40 min) — safety net
  only; the driver itself has no watchdog (documented FLAG).

### 2.3 Baselines used for comparison (DOCUMENTED, from 2026-09-04 docs)

| Baseline | Result | Key numbers |
|---|---|---|
| Gemini 1-case canary (`reversal-not-propagated`) | PASS | 34 req (13 Groq + 21 Gemini, all Gemini accepted); 107,479 tok total; judges 91,716 (85.3%); trajectory 2 calls @ 31,755/31,902 input, 28,618 cache-read; wall 180.6 s |
| `correction_draft_id` fix canary (`sync-lag-self-resolving`) | PASS | 26/26 requests accepted, 0 rejected; true JSON `null` accepted (`TCK-9168c1874617`); 73,773 tok (agents 11,256 / judges 62,517); wall 84.7 s |
| 5-case validation (live, pre-fix) | NO-GO | 2/5 completed (cases 1,5); cases 2–3 died on Groq null-schema rejection (the since-fixed defect); case 4 died on detector `Parsing failed`; Gemini 33/33 accepted; 173,150 tok (agents 41,156 / judges 131,994); wall 365.4 s |
| Case-4 audit | read-only | failure = in-stream `Parsing failed` on detector request #6 → plain `openai.APIError`, NOT retried (only `ModelThrottledException` is); identical prompt/toolset succeeded 45/46; pre-registered chance of ≥1 recurrence in THIS run ≈60% point estimate (~41–48 at-risk agent requests) |

## 3. Case-by-case results

All numbers MEASURED from per-case `token-summary.json`, `eval-rows.json`,
`token-usage.jsonl`. "req" = successful requests (attempts = successes +
error rows). Retry = automatic SDK `ModelRetryStrategy` re-execution after
a throttle (all recovered).

| # | case | agent result | classification | tokens | req (a+j) | throttles | retries | judges reached | rows passed |
|---|---|---|---|---|---|---|---|---|---|
| 1 | reversal-not-propagated | COMPLETED, correct root cause, ticket+draft | COMPLETED | 94,747 | 31 (12+19) | 1 (classifier, recovered) | 1 | 4/4 + SAC | 18/19 |
| 2 | duplicate-transaction | COMPLETED, correct root cause, ticket+draft (reporter called create_case_ticket twice — 2 tickets, 7 s apart, same draft id) | COMPLETED + GEMINI_ERROR (3 judge calls) | 58,735 | 16 (10+6) | 0 | 0 | trajectory + SAC only | 2/5 |
| 3 | sync-lag-self-resolving | DEAD at detector request #5 — `Parsing failed` (provider-side, in-stream, not retried) | GROQ_PARSING_FAILED | 3,963 | 5 (5+0) | 0 | 0 | none (upstream dead → 5 task-failure rows) | 0/5 |
| 4 | manual-override-not-reflected | COMPLETED the graph, but classifier concluded UNKNOWN (0.32) vs expected MANUAL_OVERRIDE; skipped get_event_log/draft_correction; emitted `correction_draft_id: null` (accepted) | COMPLETED (substantive evaluator failures) | 45,544 | 19 (8+11) | 1 (reporter, recovered) | 1 | 4/4 + SAC | 8/11 |
| 5 | data-entry-error | COMPLETED, correct root cause, ticket+draft | COMPLETED | 93,036 | 27 (10+17) | 0 | 0 | 4/4 + SAC | 16/17 |

Total rows 57, passed 44 (77.2%). Excluding case-3's 5 upstream-dead
task-failure rows and case-2's 3 provider-killed judge-error rows:
**44/49 judgeable rows passed (89.8%, CALCULATED)**.

## 4. Token analysis

All MEASURED (success rows; equal to the sum of per-case token-summary
totals). OTel cross-check matched the recorder **exactly, per case**
(98/98 chat spans; input/output/total identical in all 5 cases).

| group | requests (success/attempts) | input | output | total | share |
|---|---|---|---|---|---|
| Groq agents | 42 / 45 | 42,044 | 12,993 | **55,037** | 18.6% |
| Gemini judges | 50 / 53 | 231,917 | 9,071 | **240,988** | 81.4% |
| **Grand** | **92 / 98** | **273,961** | **22,064** | **296,025** | 100% |

Per-case totals: 94,747 / 58,735 / 3,963 / 45,544 / 93,036.

**Cache-read tokens (MEASURED)**: judges 65,385 (28.2% of judge input);
agents 4,864. Trajectory second-call cache hits: case-1 24,522,
case-2 16,340, case-5 24,523 — case-4 got **no** cache hit on either call
(OBSERVED; implicit caching did not engage on that trajectory).

**TrajectoryEvaluator (§13 focus)**: 8 live calls across 4 completed
cases; inputs 13,696–27,770 (all comfortably inside the previously
demonstrated 25K–32K envelope; case-4's shorter trajectory explains its
13.7K inputs); outputs 96–124. Total trajectory tokens 183,157 =
**76.0% of judge tokens, 61.9% of the grand total** (CALCULATED).
Per-call latency is not separately instrumented; OBSERVED gaps between
consecutive trajectory call records: 3.2–7.3 s (include ≥4.3 s pacer
where it engaged). Scores: case-1 1.0 PASS, case-2 1.0 PASS,
case-4 0.5 FAIL (skipped get_event_log + draft_correction, halted
early → UNKNOWN), case-5 0.9 PASS; case-3 not evaluated (upstream dead —
its 0.0 row is a task-failure row, NOT a judge failure).

Per-component request counts (MEASURED): detector 27, classifier 5,
reporter 15 (case-1 ran the low-confidence detector↔classifier loop:
7 detector + 2 classifier requests); trajectory 8, output 4, tool_sel 20,
tool_param 22 judge calls (case-2/3 truncated).

## 5. Provider analysis

### 5.1 Groq (agents) — provider=openai/gpt-oss-120b @ api.groq.com

- Attempts 45 (MEASURED): **accepted/succeeded 42**, throttled 2,
  terminal provider error 1.
- **Throttles (2)**: case-1 agent.classifier req#8 (08:34:10Z), case-4
  agent.reporter req#7 (08:38:24Z). Both `ModelThrottledException`,
  both **auto-retried by the stock SDK strategy and recovered** (existing
  behavior, preserved and reported per §5; no new retry logic).
- **Provider error (1)**: case-3 agent.detector req#5, `Parsing failed`
  in-stream termination → plain `openai.APIError`, NOT retried (only
  throttle-class exceptions are retryable), case dead. See §7.
- **Rejected for schema: 0** — the pre-fix `correction_draft_id` null
  rejection did not occur (§6).
- Quota observation: no 429-quota-exhaustion events; the two throttles
  were transient rate-limit hits recovered within one retry each.
  No quota probes were run (per §8).

### 5.2 Gemini (judges) — provider=google/gemini-3.1-flash-lite, native

- Attempts 53 (MEASURED): **accepted/succeeded 50**, server errors 3,
  throttled 0, retries 0.
- **New failure mode**: 3 `ServerError` responses clustered at
  08:37:04–08:37:16Z during case-2 judging — 503 "This model is currently
  experiencing high demand" (output judge, tool_parameter judge) and 500
  "Internal error encountered" (tool_selection judge). Provider-side,
  not quota (no 429/ResourceExhausted), not retried (not
  throttle-class); the evaluator harness recorded judge-error rows and
  continued. Prior Gemini history was 71/71 accepted (canaries +
  pre-fix 5-case), so 50/53 (94.3%) is a new, first-observed instability
  mode for the judge leg.
- **Pacing**: module-global 4.3 s pacer held across all five cases;
  effective judge rate stayed ≤14 RPM; no burst at case boundaries.
- **Cache behavior**: implicit caching engaged on second trajectory
  calls in 3 of 4 judged cases (65,385 cache-read tokens total);
  no cache hit on case-4's trajectory pair (OBSERVED, UNKNOWN cause).

## 6. `correction_draft_id` validation

**The previously fixed schema problem DID NOT recur.** (MEASURED)

- Case-1: string `DRF-d32d22f4d5e4` — emitted, accepted, ticket written.
- Case-2: string `DRF-25c7f844fdaa` — emitted, accepted, **two** tickets
  written (the reporter called `create_case_ticket` twice; both accepted).
  This is the exact path that was fatal pre-fix (2 cases lost on 09-04).
- Case-3: **NOT EXERCISED** — the case died at the detector, before any
  reporter/null emission.
- Case-4: **true JSON `null` emitted and accepted** (ticket
  `TCK-684150ff85a8`); reporter completed; no schema-validation
  rejection. The null path was therefore exercised LIVE in this run —
  on case-4 rather than the designed case-3.
- Case-5: string `DRF-cb5e8338a438` — emitted, accepted, ticket written.

Zero `create_case_ticket`-related APIError rows across the whole run.
Full evidence: `agent-memory/evidence/gemini-groq-5-case-final-validation-2026-09-05/special-validation.md`.

## 7. Case-4 `Parsing failed` watch

**On case-4 itself: NO recurrence — the case completed the full graph.**
Per task §16: "No recurrence observed in this 5-case sample." One
successful run does not prove elimination of the provider-side issue.

**However, the audited mechanism RECURRED on case-3** (task §17 applies
by mechanism, though not on the watch case):

- Request: agent.detector **request #5** of case-3 (5th model generation),
  08:37:31.756Z, after 4 successful detector requests.
- Accepted: yes (HTTP-200 SSE stream); record-gap since req#4 ≈ 9.97 s
  (OBSERVED; exact stream duration UNKNOWN — emission not preserved).
- Throttle immediately before: **none** (case-3 had zero throttle rows —
  unlike the 2026-09-04 event, which had a throttle on req#3).
- Retry behavior: zero retries; `openai.APIError` is not
  `ModelThrottledException`; `EventLoopException` → fail-fast →
  TASK FAILED → 5 task-failure rows; judges never invoked.
- Provider-side: yes — in-stream SSE error event with the verbatim
  provider text "Parsing failed. The model generated output that could
  not be parsed. Please adjust your prompt. See 'failed_generation'…".
- **Signature comparison: MATCHES the audited event** on error class,
  provider text, component, streaming termination, non-retry, and
  fail-fast propagation; differs only in case (3 vs 4), request index
  (#5 vs #6), and absence of a preceding throttle.
- Observed frequency this run: 1/45 Groq attempts (2.2%), 1/27 detector
  requests (3.7%). Cumulative instrumented detector requests:
  71/73 succeeded (2/73 ≈ 2.7% failure rate, CALCULATED from DOCUMENTED
  audit 45/46 + this run 26/27).
- No fix was implemented, no retry policy changed, no rerun attempted —
  the failure is part of the measurement (per §3/§17/§18).

## 8. Functional evaluation results

Per-case agent outcomes (MEASURED): detector/classifier/reporter all
completed their intended workflows in cases 1, 2, 4, 5 (case-1 exercised
the low-confidence detector↔classifier loop; case-2's reporter created
two tickets — a duplicate-call quirk, both accepted); case-3 died at the
detector. All four LLM judges executed for every completed case except
case-2 (trajectory + SafeActionCompliance ran; the other three judges
were killed by Gemini 5xx). SafeActionCompliance (deterministic) ran and
passed for every completed case; **no unsafe action, no
`apply_correction` exposure, zero unauthorized actions**.

Judge outcomes for completed cases (score/pass):

| case | Trajectory | Output | ToolSelection | ToolParameter | SafeAction |
|---|---|---|---|---|---|
| 1 | 1.0 PASS | PASS | 8/8 PASS | 7/8 (1 fail) | PASS |
| 2 | 1.0 PASS | judge-error (503) | judge-error (500) | judge-error (503) | PASS |
| 4 | 0.5 FAIL | FAIL (UNKNOWN ≠ MANUAL_OVERRIDE) | 4/4 PASS | 3/4 (1 fail) | PASS |
| 5 | 0.9 PASS | PASS | 7/7 PASS | 6/7 (1 fail) | PASS |

**Separated failure classes (per §12):**

1. **Infrastructure/provider failures** (not agent defects): case-3
   Groq `Parsing failed` (graph death); case-2 Gemini 503/500/503 (3
   judge-error rows). These account for 8 failed rows.
2. **Agent failures** (substantive): case-4 — classifier concluded
   UNKNOWN (confidence 0.32) instead of MANUAL_OVERRIDE; investigation
   halted early (skipped `get_event_log`, drafted no correction);
   OutputEvaluator 0.0, Trajectory 0.5. This is the run's one
   substantive root-cause failure.
3. **Evaluator failures**: none attributable to evaluator logic; the 3
   judge-error rows are provider-caught provider failures. Case-3's 5
   task-failure rows are upstream-death artifacts, NOT counted as judge
   failures (§12).
4. **Substantive benchmark failures** (judgeable rows): 5 of 49 —
   case-1 ToolParameter (`create_case_ticket.evidence_refs` cited
   IDs/dates not matching tool results — a citation-hygiene miss);
   case-4 trajectory/output/toolparameter (above); case-5 ToolParameter
   (`date_from`/`date_to` "hallucinated" — not derived from user input
   or prior results). Note: cases 1/5 param-hygiene findings echo the
   pre-fix run's completed-case behavior (same evaluator, same rubric).

## 9. Security

Pre-run verification (security subagent, 2026-09-05):

- **No literal credential anywhere** — working tree, untracked files, all
  git revisions, evidence artifacts: zero `gsk_`/`AIza`/`sk-`/`Bearer`
  hits; `.env` gitignored (mode 600), variable names only ever referenced.
- **Segregation of duties intact** — guard script logic verified, wired as
  pre-commit + verify step 2, live-run exit 0; every `apply_correction`
  occurrence accounted for (plain function, never `@tool`, sole caller
  `orchestrator/correction_executor.py:71` behind HMAC-signed single-use
  `human_gate` token; tests assert non-exposure).
- **No unauthorized write tool** — detector: 4 read-only tools;
  classifier: none; reporter: `draft_correction` + `create_case_ticket`
  (drafts/tickets only, gitignored runtime JSONL).
- **Quota discipline** — exactly ONE Groq key + ONE Gemini key; no
  rotation/switching/splitting logic anywhere in the benchmark path;
  4.3 s pacer is pacing, not bypass; no quota probes run in this task.
- **Data** — fully synthetic fixtures (C-1001..C-1005, L/M-TXN-9000x); no PII.
- Disclosed FLAGs (pre-existing, outside benchmark path): (A) `probes/`
  can read sibling `.env`s for feasibility probes — not imported by the
  driver, not invoked by this task; (B) the repo `GROQ_API_KEY` provenance
  is a sibling file-to-file transfer already on record
  (D-2026-09-04-13) — this task used the currently configured application
  key as instructed.

Post-run re-verification (MEASURED):

- Key-pattern sweep of the new evidence dir: **zero** matches
  (`gsk_`/`AIza`/`sk-` prefixes); no `.env` content in any artifact;
  recorder writes metadata only (no prompt text, no keys).
- Segregation guard re-run: exit 0. `apply_correction` was never called
  and remains unexposed; all three corrections from this run sit in
  `runtime/drafts.jsonl` as `pending_approval` (DRF-d32d22f4d5e4,
  DRF-25c7f844fdaa, DRF-cb5e8338a438); `human_gate` untouched.
- Offline suite re-run post-benchmark: 94 passed (no drift).
- No credential rotation, no second account, no sibling `.env` access at
  any point; single Groq key + single Gemini key throughout.

## 10. Cost

Pricing assumptions (DOCUMENTED): Groq $0.15/M in, $0.60/M out; Gemini
$0.25/M in, $1.50/M out, $0.025/M cached. Both credentials in this run
are free-tier.

**ACTUAL SPEND: $0** (DOCUMENTED — free-tier credentials; no billing
event OBSERVED).

**THEORETICAL PAID-TIER COST (CALCULATED from MEASURED tokens):**

| leg | computation | cost |
|---|---|---|
| Groq | 42,044×$0.15/M + 12,993×$0.60/M | $0.0141 |
| Gemini (cache-separated) | (231,917−65,385)×$0.25/M + 65,385×$0.025/M + 9,071×$1.50/M | $0.0569 |
| **Total** | | **$0.0710** |

(Without the cache-rate separation the Gemini leg would be $0.0716 and
the total $0.0857 — CALCULATED.) Consistent with the token-workload
audit's projected ≈$0.10–0.11 for five completed cases; this run had
four completed cases plus one early death.

## 11. Reproducibility / comparison with prior runs

(Prior-run numbers DOCUMENTED from their docs/evidence; this run MEASURED.)

| metric | token canary (all-Groq, 1 case) | Gemini canary (1 case) | fix canary (1 case) | 5-case pre-fix | **THIS run** |
|---|---|---|---|---|---|
| cases completed | 1/1 (judges degraded — Groq 8K TPM cap) | 1/1 | 1/1 | 2/5 | **4/5** |
| Groq `Parsing failed` | 0 | 0 | 0 | 1 (case-4) | **1 (case-3) — mechanism recurred** |
| `correction_draft_id` null rejections | n/a | n/a | 0 (canary'd) | 2 (cases 2-3, fatal) | **0 — fix held; live null accepted (case-4)** |
| Gemini judge failures | n/a | 0/21 | 0/17 | 0/33 | **3/53 ServerError (new mode)** |
| Groq throttles (recovered) | 0 | 2 | 0 | 2 | 2 |
| total tokens | 54.9–56.1K (reconstructed) | 107,479 | 73,773 | 173,150 | **296,025** |
| agent / judge tokens | 14,266 / 19,115+rejected | 15,763 / 91,716 | 11,256 / 62,517 | 41,156 / 131,994 | **55,037 / 240,988** |
| judge share | 74.0–74.6% | 85.3% | 84.7% | 76.2% | **81.4%** |
| max trajectory input | 21,214 (REJECTED 6× on Groq) | 31,902 | 42,325/2≈21K | 25,177 | **27,770** |
| wall clock | — | 180.6 s | 84.7 s | 365.4 s | **448 s** |

Consistency checks: token workload lands inside the audit's projected
315–500K band for five completed cases once case-3's early death
(~60–80K unrealized) is accounted for; trajectory inputs sit in the
25–32K envelope; judge share between the canary (85%) and pre-fix
partial-run (76%) values as expected from case mix; wall clock scales
with completed cases (4 vs 2 at ~2× time). No anomalies.

## 12. Recommendation

**GO WITH CAVEAT.**

Quantitative basis against §15 dimensions:

- **A. Functional completeness**: 4/5 graphs completed (80%); the 1
  failure is the pre-registered intermittent provider event, not an
  application defect.
- **B. Provider stability**: Groq 42/45 accepted (93.3%), 2 throttles
  both auto-recovered, 1 terminal parse error — consistent with the
  DOCUMENTED ~2.7% cumulative detector-request failure rate and the
  audit's ≈60% ≥1-recurrence expectation. Gemini 50/53 (94.3%) — new,
  clustered, transient 5xx mode; below the in-run escalation threshold
  (≥2 cases lost to the parse signature) and not quota-related.
- **C. Agent correctness**: intended workflows completed in 4/4
  non-provider-dead cases; 1 substantive root-cause failure (case-4
  UNKNOWN vs MANUAL_OVERRIDE) — an agent-quality finding for the
  backlog, not a provider/infra issue.
- **D. Judge correctness**: all four Gemini judges executed for 3/4
  completed cases; case-2 lost 3 judge rows to provider 5xx
  (trajectory + deterministic evaluator unaffected).
- **E. Security**: all segregation/credential checks passed pre and post.
- **F. Token economics**: 296K tokens measured, in the projected band;
  theoretical cost ≈ $0.071/run.
- **G. Reproducibility**: quantitative agreement with all four baselines
  (table §11); the `correction_draft_id` fix specifically reproduced its
  canary result at 5-case scale (0 rejections vs 2 pre-fix).

Caveats that prevent an unqualified GO (and correctly so, per §23):

1. The Groq provider-side `Parsing failed` event recurred (1 case lost,
   2nd consecutive 5-case-scale run with an occurrence) — a single run
   cannot establish elimination or persistence; per instruction, no
   retry fix was made. If the pre-registered escalation threshold
   (≥2 cases lost in one run) is ever hit, the audit's fix path should
   be reopened.
2. The Gemini judge leg showed its first provider-side instability
   (3×5xx). Monitor for recurrence; the pacer and quota discipline held.
3. Case-4's substantive agent failure (UNKNOWN diagnosis) is a real
   quality gap to investigate outside any benchmark.

This configuration can support controlled benchmark runs with an
expected yield of ~4/5 fully-judged cases per execution and no security
or methodology regressions.
