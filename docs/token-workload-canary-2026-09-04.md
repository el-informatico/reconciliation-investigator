# Token-workload canary — ONE instrumented evaluation case (2026-09-04)

**Question:** replace the ESTIMATED agent/judge token split from
`docs/token-workload-audit-2026-09-04.md` with MEASURED per-request usage
from the provider's own usage metadata, for exactly ONE evaluation case.

**Method:** one case (`reversal-not-propagated`) executed ONCE through the
unmodified sequential-eval path, with a pass-through model wrapper
(`evals/token_canary.py`, new file; `git diff` on existing files empty)
recording provider-reported usage per request. Evidence labels:
**MEASURED** (read from this run's artifacts), **CALCULATED** (derived
from measured data), **PROJECTED** (scaled assumptions about the 5-case
run — NOT a measurement of it), **UNKNOWN**.

---

## 1. Executive summary

- **One case measured: agents 14,266 tokens (9 requests) vs judges
  19,115 tokens EXECUTED (13 requests) — and the TrajectoryEvaluator's
  request, at 21,214 input tokens MEASURED by Groq's own TPM meter, was
  REJECTED 6× by the free tier's 8,000 TPM per-request cap (HTTP 413)
  and never ran.** Completed-case reconstruction: judges ≈ 40.6–41.8K of
  ≈ 54.9–56.1K total → **judge share ≈ 74%**, confirming the prior
  audit's "judges are the majority" at the top of its 60–70% range.
- **TrajectoryEvaluator ≈ 39–40% of the entire case workload and ≈ 53–54%
  of the judge workload** (input exactly measured; output unknown,
  bounded) — inside the audit's 35–50% estimate.
- **The Groq free tier structurally cannot host this benchmark's judge
  stage**: the trajectory judge's single 21,214-token request exceeds the
  8,000 TPM per-request limit deterministically (not a transient
  throttle). All-Groq-free-tier is empirically NO-GO; the measured agents
  side (largest single request: 2,601 tokens) fits comfortably.
- Eval outcome of the case: 12/15 rows passed; the one judge-error row is
  the TPM-blocked TrajectoryEvaluator; SafeAction (deterministic) passed
  with 0 LLM tokens; zero unauthorized actions.
- Naive 5× projection (labeled PROJECTION, §8): ≈ 275–280K tokens —
  below the prior audit's 315–500K envelope; the audit's central ~375K
  was ~1/3 high for this case's shape (6 tool executions, R=1).
- Instrumentation integrity: wrapper captured 28 `stream()` calls; the
  independent OTel span exporter saw exactly 28 "chat" spans and agrees
  on total tokens to the token (33,381); zero existing files modified.

## 2. Execution details

- Case selected: `reversal-not-propagated` (`evals/cases.py:32`; the only
  case whose `expected_trajectory` covers the full 6-tool surface).
- Executions: **1** (single run; no retries by the operator; the 6
  trajectory-judge attempts below are the harness's own SDK-level retry
  behavior, unmodified).
- Provider: Groq, OpenAI-compatible endpoint, the app's own
  `GROQ_API_KEY` (gitignored `.env`, loaded by the app's loader; never
  read or printed). Service tier per Groq's error body: `on_demand`.
- Model: `openai/gpt-oss-120b` for agents AND judges — unchanged.
- Instrumentation: `evals/token_canary.py` — a pass-through delegating
  wrapper around the exact model objects the harness constructs
  (`get_model()` results; the four judge singletons' shared model).
  Usage read from the SDK's final streaming metadata chunk (Groq
  `prompt_tokens/completion_tokens/total_tokens` → strands
  `inputTokens/outputTokens/totalTokens`). Recorded fields are metadata
  only; system prompts are reduced to a truncated SHA-256 + length.
- Offline verification BEFORE the run: 78/78 tests green (72 existing +
  6 new hermetic instrumentation tests); `git diff` on tracked files
  empty; pre-run state snapshot taken (`/tmp/token-canary-prerun-state.txt`).
- Runtime side effects (expected app behavior, snapshotted): one draft
  appended to `runtime/drafts.jsonl`, one ticket to
  `runtime/tickets.jsonl`; `consumed_tokens.jsonl` untouched (no human
  gate on the eval path).
- Post-run incident (does not affect measurements): the driver's
  artifact-writing step crashed on `sorted()` over labels containing
  `None` AFTER all evaluators finished; `token-usage.jsonl` (flushed per
  request) and `otel-crosscheck.json` survived; `token-summary.json` was
  regenerated offline from the JSONL and `eval-rows.json` transcribed
  from `run.log`. The bug and an OTel alias double-count were fixed in
  the instrumentation file only. **The case was NOT rerun.**
- Raw evidence: `agent-memory/evidence/token-canary-2026-09-04/`
  (`token-usage.jsonl` — per-request truth; `run.log`;
  `otel-crosscheck.json`; `token-summary.json`; `eval-rows.json`).

## 3. Measured agent workload (provider-reported, this case)

| Component | Requests | Input | Output | Total |
| --- | ---: | ---: | ---: | ---: |
| Detector (incl. its 4 tool rounds) | 5 | 4,830 | 1,236 | 6,066 |
| Classifier | 1 | 1,017 | 457 | 1,474 |
| Detector loop (rounds 2+) | 0 | 0 | 0 | 0 |
| Reporter (incl. draft + ticket rounds) | 3 | 4,725 | 2,001 | 6,726 |
| Other | 0 | 0 | 0 | 0 |
| **Agents total** | **9** | **10,572** | **3,694** | **14,266** |

All MEASURED. Detector loop is 0 because the classifier's single verdict
(request #6) satisfied routing — all 5 detector requests precede it.
Attribution was exact by construction (tagged wrappers) and
cross-checkable per request (tool-spec names: the detector's 4 read
tools, the reporter's draft/ticket tools, empty for the classifier).

## 4. Measured judge workload (provider-reported, this case)

| Evaluator | Requests | Input | Output | Total |
| --- | ---: | ---: | ---: | ---: |
| Trajectory | 6 attempts, all rejected (413 TPM) | 21,214/attempt requested; 0 consumed | UNKNOWN (never processed) | 0 consumed |
| Output | 1 | 2,846 | 301 | 3,147 |
| Tool Selection | 6 (one per tool execution) | 5,487 | 1,533 | 7,020 |
| Tool Parameter | 6 (one per tool execution) | 6,369 | 2,579 | 8,948 |
| SafeActionCompliance | 0 (deterministic span walk, no model) | 0 | 0 | 0 |
| **Judges total (executed)** | **13** | **14,702** | **4,413** | **19,115** |

The 21,214 figure is MEASURED — Groq's own error body:
`Limit 8000, Requested 21214` (repeated identically on all 6 attempts,
so the request never shrank/grew between retries). Each judge call was
exactly ONE request (the structured-output tool spec rides in the same
request as the rating tools — no extra forced round occurred in this
run).

## 5. Measured token accounting

Executed (22 requests processed by Groq):

| Group | Requests | Input | Output | Total |
| --- | ---: | ---: | ---: | ---: |
| Agents | 9 | 10,572 | 3,694 | 14,266 |
| Judges | 13 | 14,702 | 4,413 | 19,115 |
| **Total executed** | **22** | **25,274** | **8,107** | **33,381** |

- input + output = 33,381 = provider-reported total (exact, per request).
- Plus 6 rejected HTTP attempts (413) for the trajectory judge — counted
  as requests ATTEMPTED (28 total `stream()` calls) but 0 tokens.
- Completed-case reconstruction (CALCULATED: executed + trajectory input
  MEASURED + trajectory output bounded 300–1,500 from the measured
  210–722 range of the other judges' outputs):

| Quantity | Low | High |
| --- | ---: | ---: |
| Agents | 14,266 | 14,266 |
| Judges | 40,629 | 41,829 |
| Grand total | 54,895 | 56,095 |
| **Judge share** | **74.0%** | **74.6%** |
| Agent share | 26.0% | 25.4% |

## 6. TrajectoryEvaluator analysis

1. **Receives the complete trajectory: CONFIRMED** from the installed
   source (unchanged from the audit's finding):
   `strands_evals/evaluators/prompt_templates/case_prompt_template.py`
   embeds `{evaluation_case.actual_trajectory}` — the pydantic `Session`
   repr — with no cap on this code path. The measured size confirms it
   empirically: 21,214 input tokens for one case vs 2,846 for the Output
   judge on the same case.
2. **Invocations for one case: 1** (one evaluate() call → one judge
   prompt; it failed 6 HTTP attempts against the TPM meter and produced
   a `judge-error` row).
3. **Input tokens: 21,214 (MEASURED, provider-side).**
4. **Output tokens: UNKNOWN** — the request was never processed; bounded
   300–1,500 by analogy to measured judge outputs on this case.
5. **Share of judge workload: ≈ 53.0–54.3% (CALCULATED).**
6. **Share of the entire case workload: ≈ 39.2–40.5% (CALCULATED)** —
   inside the audit's 35–50% band, near its 43% central.

Not modified — observation only, per the task contract.

## 7. Comparison with previous audit

| Quantity | Canary (this run) | Prior audit (5-case estimate) |
| --- | --- | --- |
| Agents / case | 14,266 MEASURED | 19.6–29.4K ESTIMATED |
| Judges / case | 40.6–41.8K (19.1K executed + 21.2K measured trajectory input + bounded output) | 43–70K ESTIMATED |
| Total / case | ≈ 54.9–56.1K | 63–100K (central ~75K) ESTIMATED |
| Judge share | ≈ 74% (executed-only: 57.3%) | 60–70% (central ~68%) |
| TrajectoryEvaluator share of case | ≈ 39–40% | 35–50% (central ~43%) |
| Requests / case | 28 attempted / 22 processed (23 in a completed case) | 27.2 average MEASURED in run 2 (136/5) |

Verdict: **PARTIALLY CONSISTENT.**
- Direction and rough magnitude confirmed: judges are the clear majority;
  TrajectoryEvaluator is the single dominant consumer (both inside or
  near the audit's bands).
- The split sits slightly OUTSIDE the audit's band (74% vs 60–70%) —
  the audit's chars→tokens conversion underestimated the trajectory
  judge's tokenizer footprint relative to the small judge calls.
- Absolute volumes run BELOW the audit's central: this case's shape
  (6 tool executions vs run-2's 8.4/case average; R=1; no detector
  cycling) plus the audit's ±20% conversion error explain most of the
  gap.
- Request count is consistent (23 successful vs 27.2 average; the delta
  is the missing 8th/9th tool-execution judge pairs of bigger cases);
  the 6 extra ATTEMPTED requests are Groq-tier retry artifacts, not
  benchmark behavior.
- Also confirmed: the audit's canary-size prediction (~21–27 requests,
  ~30–45K tokens) was close (22 processed requests; 33.4K executed +
  21.2K blocked trajectory input = 54.6K attempted workload).

## 8. 5-case projection (PROJECTION — the 5-case run was NOT measured)

Naive 5× of the completed-case reconstruction:

```text
Measured canary:        agents 14,266 | judges 40,629–41,829 | total 54,895–56,095
Naive 5× projection:    agents 71,330  | judges 203,145–209,145 | total 274,475–280,475
Previous audit:         agents 98–147K | judges 215–350K | total 315–500K (central ~375K)
```

Do not treat 5× as a measurement: case mix varies (tool executions 6 in
this case vs 8.4/case average in run 2 → tool-judge calls scale with T;
classifier confidence can dip below 0.7 and trigger detector cycling,
capacity the audit bounded at +30–60K over 5 cases; trajectory-judge
input scales with each case's trajectory size, MEASURED range in run 2:
~100–137K chars). A realistic band is the naive floor 275K up to roughly
the audit's low edge (~315K), with the central likely ~285–300K.

## 9. Provider split analysis (PROJECTION from the canary; nothing implemented)

```text
All-Groq (5-case projection):  Groq workload = agents + judges ≈ 275–315K tokens
Split (5-case projection):     Groq workload = agents ≈ 71K
                               Gemini workload = judges ≈ 203–209K (~92–96 requests)
```

- **All-Groq free tier: NO-GO — now empirically proven, not just
  budgeted.** The trajectory judge's 21,214-token single request exceeds
  the 8,000 TPM per-request cap deterministically (6/6 rejections); no
  amount of waiting fixes a per-request cap. TPD 200K would also be
  exceeded (275–315K).
- **All-Groq PAYG: viable, zero code change** — at measured sizes a 5-case
  run costs ≈ $0.06–0.13 (audit's arithmetic at $0.15/$0.60 per M
  input/output), and PAYG lifts the TPM cap (the error body itself
  advertises the tier upgrade).
- **Split (gpt-oss-120b/Groq agents + gemini-3.1-flash-lite judges):**
  agents' largest measured single request is 2,601 tokens (fits 8K TPM);
  ~71K/5-case is 36% of the 200K TPD; judges move to a 250K-TPM/500-RPD
  tier where the 21.2K trajectory call is 8.5% of one minute's budget;
  ~92–96 judge requests at 15 RPM imply a ≥6.5-minute judging phase.
- No new Gemini or Groq calls were made for this analysis; the only Groq
  calls in this task were the ONE canary case under the existing app
  configuration.

## 10. Methodological implications

Moving judges to a different model (Gemini 3.1 Flash-Lite) while agents
stay on gpt-oss-120b WOULD constitute a declared methodology change, not
a silent optimization: the measurement instrument itself changes
(lite-judge rating noise; different tokenizer → token-denominated
comparisons shift), and the run becomes mixed-provider by design. It is
distinct from the rejected mid-run fallback pattern because the
assignment is fixed and declared up front — but every result row must
carry the label (this restates the audit's condition 1, now with
measured numbers behind it). The agent side of the split keeps the
validated gpt-oss configuration byte-identical. Any such switch also
re-opens the TrajectoryEvaluator question on new grounds: its 21.2K-token
prompt is 53–54% of the judge workload, and capping or restructuring it
would be a methodology change that must NOT ride along silently with a
provider switch.

## 11. Confidence / limitations

| Number | Label |
| --- | --- |
| Agents 14,266 (9 requests, per-component rows) | MEASURED |
| Judges executed 19,115 (13 requests, per-evaluator rows) | MEASURED |
| Trajectory judge input 21,214 | MEASURED (Groq TPM meter, in the 413 error body) |
| 28 attempted / 22 processed requests; OTel 28 chat spans; totals match to the token | MEASURED |
| Completed-case totals 54.9–56.1K; judge share 74.0–74.6%; trajectory shares | CALCULATED (executed + measured trajectory input + bounded output) |
| Trajectory judge output tokens | UNKNOWN (bounded 300–1,500) |
| 5× projection and provider-split workload figures | PROJECTED |
| Reasoning-token split within outputs | UNKNOWN at this interception point — the SDK drops `reasoning_tokens` before exposure; outputs INCLUDE reasoning (e.g. detector request #5: 800 output tokens for an evidence bundle) |
| Single case, single execution, R=1, 6 tool executions | Scope limits of a canary — per-case variance is not measured |

Other limitations: one case only (by design); the driver's post-run
artifact bug means `token-summary.json`/`eval-rows.json` were regenerated
offline (from `token-usage.jsonl` / `run.log`) rather than written by the
run itself; the OTel crosscheck file's input/output sums are exactly 2×
the truth (alias double-count, documented; `total_tokens` had one key and
matches exactly).

## 12. Recommendation

**GO WITH VALIDATION** for the split strategy (gpt-oss-120b/Groq →
agents; gemini-3.1-flash-lite → judges), now on measured rather than
estimated footing, with the validation conditions tightened by this
canary:

1. Judge-model methodology disclosure on every result row (§10).
2. **New, empirically grounded:** the Groq free tier is disqualified for
   the judge stage by a per-request TPM cap (21,214 > 8,000), so the
   decision is strictly between the Gemini-judge split ($0) and all-Groq
   PAYG (~$0.06–0.13/run, zero code, zero methodology change). If
   strict-$0 is not a hard constraint, PAYG remains the lowest-complexity
   path; the split's value is the $0 constraint plus keeping the
   validated agents untouched.
3. Quota pre-checks on the day of the full run (Groq TPD/RPD headers;
   Gemini dashboard RPM/TPM/RPD + any TPD row), and expect the judging
   phase to be RPM-paced (~6.5+ min at Gemini free tier).
