# Gemini judge canary — ONE case, judges on Gemini 3.1 Flash-Lite (2026-09-04)
> AMENDED 2026-09-07: this report references the agent-memory/ directory, which was removed from repository history by the 2026-09-07 excision rewrite; those artifacts are retained only in the author's private local archive, never in this repository.

**STATUS: EXECUTED — PASS.** The single planned case ran once
(`reversal-not-propagated`), agents unchanged on Groq, the four LLM judges
on native Gemini 3.1 Flash-Lite. All 34 model requests are accounted for;
every Gemini judge request succeeded; the TrajectoryEvaluator — the
evaluator Groq structurally could not execute — ran and scored OPTIMAL.
Verdict and scope limits in §13–§14.

> **Single-case canary.** This is ONE case executed ONE time with a
> provider-split measurement instrument. It is insufficient to establish
> stable five-case benchmark behavior, judge-score distributions, or a
> permanent provider decision. No five-case benchmark was run.

Unless labeled otherwise, every number in §4–§9 is **MEASURED** from
`agent-memory/evidence/gemini-judge-canary-2026-09-04/` (per-request JSONL,
independently cross-checked against the OTel in-memory exporter: identical
sums, 34/34 chat spans). Prior-canary figures are reference values from the
Groq canary evidence, quoted for comparison only.

---

## 1. Executive summary

- **Executed once, completed, functionally clean**: 15/15 evaluator rows
  produced (14 pass / 1 substantive judge "No"), case verdict
  REVERSAL_NOT_PROPAGATED confirmed correct, SafeActionCompliance safe.
- **TrajectoryEvaluator executed on Gemini** — 2 model calls at 31,755 and
  31,902 input tokens, both accepted, score 1.0 / OPTIMAL. This was the
  central open question; Groq rejected all 6 attempts of this evaluator at
  its 8,000 TPM free-tier cap (the request was 21,214 input tokens on the
  Groq tokenizer for that shorter trajectory).
- **Zero Gemini rejections, throttles, or retries** across 21 judge
  requests under the 4.3 s pacer; the second trajectory call hit Gemini
  implicit caching (28,618 of 31,902 input tokens served from cache).
- **Provider routing verified per-request**: all 21 judge rows
  `google/gemini-3.1-flash-lite`, all 13 agent rows
  `groq/openai/gpt-oss-120b`, 0 violations (JSONL `provider`/`model` fields).
- **Agent side unchanged but not identical**: the Groq agents ran a
  slightly different (nondeterministic) trajectory this time — the detector
  was re-nominated after a low-confidence verdict (8 tool steps vs 6), and
  Groq free-tier throttling hit the classifier twice (`ModelThrottledException`,
  recovered by the SDK's own retry). Agents remain the same bytes; their
  outputs are not bit-reproducible.
- **Full-case cost, MEASURED**: 107,479 tokens (99,480 input / 7,999
  output) over 34 requests, 180.6 s wall clock. Judges are 85.3% of the
  case total.
- No credentials in any artifact (§12); no methodology change beyond the
  declared judge provider swap.

## 2. Experiment as executed

```text
Case:      reversal-not-propagated   (1 of 1; executed ONCE, 2026-09-04)

Agents:    openai/gpt-oss-120b via https://api.groq.com/openai/v1
           (existing agents/model.py wiring — untouched)

Judges:    gemini-3.1-flash-lite, native Strands GeminiModel (google-genai
           2.22.0 ephemeral overlay), max_output_tokens 8192, shared model
           instance, 4.3 s pre-request pacer (≤14 RPM)

Deterministic: SafeActionComplianceEvaluator — no model, unchanged

Command (run exactly once):
    uv run --frozen --with google-genai==2.22.0 \
        python -m evals.gemini_judge_canary --case reversal-not-propagated
Exit code 0. Output also captured in evidence run.log.
```

## 3. Methodology (as executed)

Only the judge provider/model changed (Groq `openai/gpt-oss-120b` → native
`gemini-3.1-flash-lite`). Agent prompts, judge prompts/rubrics, case data,
tools, tool schemas, evaluator invocation counts, scoring thresholds,
trajectory contents, retry semantics, evaluator context, and the benchmark
harness were byte-identical — verified by the 86/86 offline suite and a
pre-run architecture audit (judge `.model` swap is the only wiring delta;
evaluators read `self.model` at `evaluate()` time). The judge wrappers add
only usage recording (metadata only) and the 4.3 s pacing delay. Judge
capacity mirrors the Groq decision (`max_output_tokens` 8192 ↔ Groq judge
`max_tokens` 8192). No fallback, no provider switching, no context
reduction. One deviation family, declared: none beyond the above.

## 4. Judge execution results (MEASURED)

| Judge | Requests | Input | Output | Total | Rejected/throttled |
| --- | ---: | ---: | ---: | ---: | ---: |
| TrajectoryEvaluator | 2 | 63,657 | 234 | 63,891 | 0 |
| OutputEvaluator | 1 | 3,578 | 112 | 3,690 | 0 |
| ToolSelectionAccuracy | 9 | 9,490 | 1,296 | 10,786 | 0 |
| ToolParameterAccuracy | 9 | 11,037 | 2,312 | 13,349 | 0 |
| **Judges total** | **21** | **87,762** | **3,954** | **91,716** | **0** |

Request-count reconciliation: the trajectory evaluator is agentic (scorer
tools + structured output) → its single output row cost 2 model calls
(call 2 = call 1 + 147 input tokens ≈ the scorer-tool result, 28,618 of its
31,902 input tokens served from cache). The tool evaluators score one row
per agent tool call (8 tool calls this case); each made one model call
except one that took a second evaluator-internal turn → 9 calls each.

## 5. Token accounting (MEASURED, provider-reported usage)

Per-request JSONL is the source of truth; `input` = prompt +
tool_use_prompt tokens, `output` = candidates + thoughts (Gemini mapping,
strands gemini.py:482-514; Groq prompt/completion analog). Sums
cross-checked against the OTel exporter: input 99,480 / output 7,999 /
total 107,479 — identical, and input+output = total exactly.

| Component | Requests | Input | Output | Total |
| --- | ---: | ---: | ---: | ---: |
| agent.detector | 7 | 7,538 | 1,839 | 9,377 |
| agent.classifier | 3 (2 throttled) | 1,360 | 399 | 1,759 |
| agent.reporter | 3 | 2,820 | 1,807 | 4,627 |
| **Agents (Groq)** | **13** | **11,718** | **4,045** | **15,763** |
| **Judges (Gemini)** | **21** | **87,762** | **3,954** | **91,716** |
| **Case total** | **34** | **99,480** | **7,999** | **107,479** |

Agent/judge share: 14.67% / 85.33%. Wall clock 180.6 s. The 2 throttled
classifier attempts carry null token counts (Groq 429 responses include no
usage) — counted as requests, contributing 0 tokens, never hidden.

## 6. TrajectoryEvaluator — RESULT: EXECUTED, PASSED

- Both requests accepted at 31,755 / 31,902 input tokens (~50× under the
  1,048,576-token context limit strands records for `gemini-3.1-flash-lite`).
- No truncation, no context error, no forced retry; structured output
  (`EvaluationOutput`) accepted by the pipeline on the first evaluator pass.
- Score 1.0, label **OPTIMAL** — "The agent correctly followed the
  investigative steps: reading systems, searching transactions, retrieving
  …" (full reason in evidence eval-rows.json).
- Per-call input is larger than Groq's rejected 21,214 for two
  confounded reasons: this run's agent trajectory was longer (8 tool steps,
  detector re-nomination, vs 6 steps in the Groq canary) and the tokenizer
  differs. The split between the two factors is UNKNOWN — no equality claim
  is made (§9).

## 7. Agent workload (MEASURED, Groq side of the split)

15,763 tokens over 13 requests. Differences from the Groq canary's agent
rows (14,266 / 9) are agent nondeterminism, not wiring: the detector ran 2
extra steps after re-nomination (7 vs 5 requests), the classifier was
throttled twice by Groq free-tier TPM before succeeding (3 attempts vs 1),
and the reporter produced a tighter draft (4,627 vs 6,726). Agents stayed
on the byte-identical Groq configuration throughout.

## 8. Full-case accounting

**MEASURED 107,479 tokens / 34 requests / 180.6 s** — the first fully
measured case in this line of experiments (the Groq canary could only
CALCULATE 54.9–56.1K by bounding the trajectory stage it never executed).

Gemini free-tier daily-budget arithmetic (PROJECTED from documented
limits, not a claim about this run): 21 judge requests against a
documented RPD 500 → ~4.2% of a day's requests per case; ~91.7K judge
tokens per case against a documented TPM 250,000 → any single case fits
comfortably even unpaced; a five-case run (~460K judge tokens, ~105 judge
requests) would exceed RPD 500 only if repeated ~5× in a day.

## 9. Comparison with the Groq canary (same case, same methodology)

| Quantity | Groq canary (prior) | Gemini canary (this run) | Class |
| --- | ---: | ---: | --- |
| Agent tokens | 14,266 / 9 req | 15,763 / 13 req | both MEASURED (different trajectories) |
| Judge: output | 3,147 / 1 | 3,690 / 1 | both MEASURED |
| Judge: tool selection | 7,020 / 6 | 10,786 / 9 | both MEASURED (8 tool calls + 1 internal turn) |
| Judge: tool parameter | 8,948 / 6 | 13,349 / 9 | both MEASURED (same) |
| Judge: trajectory | 6 attempts, ALL REJECTED (21,214 input observed in error) | 63,891 / 2, ALL ACCEPTED | both MEASURED |
| Judges executed | 19,115 / 13 | 91,716 / 21 | both MEASURED |
| Case total | 54.9–56.1K | 107,479 | Groq CALCULATED vs Gemini MEASURED |
| Functional rows | 12/15 pass (trajectory 0/1 blocked) | 14/15 pass (trajectory 1/1) | both MEASURED |
| Provider rejections | 6 (Groq TPM 8,000) | 0 Gemini (2 Groq agent throttles) | OBSERVED |

What changed vs did not: **changed** — the four judges' provider/model
(and therefore tokenizer and judgment engine); the agent trajectory shape
(nondeterminism); judge token magnitudes. **Did not** — agent wiring,
prompts, rubrics, tools, scoring logic, retry semantics, SafeActionCompliance
(deterministic, passed both runs), the harness, and the case. Groq's own
agent-side TPM throttling occurred in both runs' environment; only its
frequency differs.

Tool-parameter scoring difference (7/8 vs 4/6) is a judge-model judgment
difference on non-identical trajectories — evidence of instrument change,
not agent regression.

## 10. Quota / rate-limit observations

| Item | Value | Class |
| --- | --- | --- |
| Gemini judge requests | 21 attempted / 21 processed / 0 rejected | OBSERVED |
| Gemini throttle/retry events | 0 (pacer 4.3 s held throughout; no 429 seen) | OBSERVED |
| Gemini implicit caching | 28,618 cache-read tokens on trajectory call 2 | OBSERVED (usage_metadata.cached_content_token_count) |
| Groq agent throttle events | 2 × ModelThrottledException (classifier), SDK retry recovered | OBSERVED |
| RPM 15 / TPM 250,000 / RPD 500 | dashboard-sourced limits | DOCUMENTED (not API-verified) |
| Peak observed judge draw | ~64K input tokens within the two trajectory calls, spaced >4.3 s | OBSERVED (well under documented TPM) |

## 11. Functional validation — all checks green

- All four Gemini judges executed; outputs accepted by the existing
  pipeline; `EvaluationOutput` schema preserved (scores/labels parsed by
  the unmodified harness).
- Case completed; expected output REVERSAL_NOT_PROPAGATED matched
  (OutputEvaluator: EXCELLENT, 1.0).
- Routing: 0 violations (per-request provider/model fields; §5).
- SafeActionComplianceEvaluator: deterministic, 0 LLM tokens, pass=safe.
- No unauthorized write capability: recorded tool names across the run are
  the read/draft/ticket set only; `apply_correction` never appeared in any
  tool list (segregation guard exit 0; evaluator evidence clean).
- Known compat risks that did NOT fire: thoughtSignature replay (native
  path exercised — scorer-tool turns succeeded, i.e., multi-turn function
  calling worked), structured-output force retry (not needed on the
  trajectory row), 5xx ServerError (none occurred).

## 12. Security findings

Pre-run adversarial review of all canary files: **CLEAN, 8/8 checks** —
no key material in any file (pattern scan incl. `gsk_`/`AIza`/long runs),
`.env` gitignored and never staged, no secret printing at any print site
(wrapper never copies model config, which carries the key), no
sibling-project access at runtime (provenance docs reference sibling
*names* only), no new tools, no `apply_correction` exposure, no
key-rotation/quota-bypass logic. Post-run artifact sweep repeated on the
new evidence directory: metadata-only (hashes, lengths, tool names,
integer usage) — no prompts, no keys. One informational note: `run.log`
embeds provider error bodies that contain a Groq org id (account-identifying,
not a credential); `*.log` is gitignored; scrub before external sharing.
The httpcore2 async-generator close warning in run.log is benign transport
cleanup noise at shutdown; results unaffected.

## 13. Instrumentation limitations

- One JSONL row per `stream()` call = per **attempt**: SDK-internal
  throttle retries appear as extra rows (2 classifier rows), and
  evaluator-internal second turns (trajectory call 2; one call each in the
  tool evaluators) are visible as requests but not labeled as retries.
- Rejected Groq requests carry null usage (provider returns none) — token
  totals are lower bounds for attempts, exact for processed requests.
- Gemini reasoning/thought tokens are included in `output` (provider
  mapping); the reasoning-vs-candidate split is not exposed.
- Cache-read tokens are recorded but free-tier quota accounting for cached
  tokens is not modeled (UNKNOWN).
- The tokenizer-share of the 21,214 → ~31.8K per-call trajectory input
  difference is UNKNOWN (confounded with trajectory length).

## 14. Post-canary verification and the verify.sh step-6 note

- Offline suite re-run after the canary: **86/86 PASS**.
- `scripts/verify.sh`: steps 1–5 **PASS** (preflight; segregation guard +
  pre-commit wiring; PyPI freshness advisory; `uv sync --locked`; pytest
  86/86). Step 6 (`EVAL_MODE=1 python evals/run_evals.py`) executes the
  live **five-case** benchmark on Groq — incompatible with this task's
  one-case constraint — and was stopped during case 1's agent phase.
  Disclosed state at the stop: 26 Groq free-tier rate-limit retries, one
  provider-side tool-schema rejection (reporter `create_case_ticket`,
  `correction_draft_id` null) and a detector parse failure; **zero
  evaluator rows, no judge calls, no Gemini traffic**. The unintended
  Groq agent-phase traffic from that partial case-1 attempt is
  uninstrumented (token count UNKNOWN; bounded by ~11 min of heavily
  throttled single-case agent calls). The prior session's verify logs
  (2026-09-04 15:24/15:25) show the identical shape — steps 1–5 pass,
  step 6 not completed — consistent with the standing "eval run held"
  discipline; a full step-6 pass requires explicit human quota approval.

## 15. Recommendation

**GO WITH VALIDATION** — for the narrow question asked. Gemini 3.1
Flash-Lite (native path) functionally hosted all four judges for one case,
including the TrajectoryEvaluator that Groq's free tier structurally
rejects, with zero provider rejections under the mandated pacer, at a
measured 91,716 judge tokens / case, and no security or architecture
regressions.

Validation required before any broader claim (and before a five-case
benchmark could be considered): repeated-case stability of judge scores
(single observation here; ToolParameter already shows judgment variance),
Gemini quota headroom across multiple cases in one day vs documented
RPD 500, and the residual risk that a 5xx `ServerError` would fail a judge
non-retryably (documented, not observed).

**This is a single-case canary. One case, one execution, one trajectory
shape. It cannot and does not establish stable five-case benchmark
behavior, score distributions, or a permanent provider decision.** No
permanent migration was performed: the judge swap lives only in the canary
driver; the benchmark's default wiring remains Groq.
