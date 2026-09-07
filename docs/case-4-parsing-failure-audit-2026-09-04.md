# Case-4 detector "Parsing failed" — read-only root-cause audit (2026-09-04)
> AMENDED 2026-09-07: this report references the agent-memory/ directory, which was removed from repository history by the 2026-09-07 excision rewrite; those artifacts are retained only in the author's private local archive, never in this repository.

**Task class:** READ-ONLY audit. No source/test/config/prompt/tool/benchmark/
instrumentation/provider changes; no live LLM, benchmark, canary, probe, or
quota consumption; nothing staged/committed/pushed. Sole intentional artifact
of this task: this file (untracked). Pre-existing working-tree modifications
(`tools/case_management.py`, `tests/test_tools.py` — the already-validated
`correction_draft_id` annotation fix) predate this task and were not touched.

**Method:** three parallel read-only investigations (code path incl. installed
SDK source; preserved evidence; cross-run comparison/determinism), followed by
independent first-hand verification of every decisive citation quoted below
against installed packages (`strands-agents 1.54.0`, `openai 3.8.0`,
`strands-agents-evals 1.2.0`, `.venv/lib/python3.13/site-packages/`) and the
primary evidence tree `agent-memory/evidence/gemini-judge-5-case-2026-09-04/`.
A secret-pattern sweep of the evidence tree was clean (the only `sk-` hit is
the substring inside the literal label `task-failure`; no keys, request ids,
or org ids appear anywhere).

---

## Executive summary

- **Exact failure:** case-4 `manual-override-not-reflected`, agent
  `detector_investigator`, provider `groq`, model `openai/gpt-oss-120b`. The
  case's **6th detector request** (2026-09-05T03:24:09Z→03:24:14Z UTC; the
  evidence dir is dated 2026-09-04 local) was accepted and streamed for
  5.134 s, then Groq terminated the stream **in-stream** with the verbatim
  error: `Parsing failed. The model generated output that could not be
  parsed. Please adjust your prompt. See 'failed_generation' for more
  details.` MEASURED (run.log:501-503, :553, :621-622;
  case-04/token-usage.jsonl row 6: `status=error`, `error_type=APIError`,
  all usage fields null).
- **Root cause:** a **provider-side (Groq) in-stream rejection of one
  nondeterministic model emission** — Groq's server failed to parse the
  model's own generated output mid-generation and surfaced it as an SSE
  `error` event inside an HTTP-200 stream. It is **not an application or
  schema defect**: the detector path carries no response schema and no
  structured output; the identical prompt (sha256 `374426cc9a3496e0`) and
  toolset succeeded on 45 of 46 instrumented Groq detector requests.
  The failure was made **terminal** by a framework policy property: Strands
  retries only `ModelThrottledException`, so this `openai.APIError` was
  raised through un-retried, wrapped as `EventLoopException`
  (`strands/event_loop/event_loop.py:405`), and the fail-fast graph killed
  the case. What the model actually emitted is **UNKNOWN** (`failed_generation`
  exists only on Groq's servers; instrumentation is metadata-only by design).
- **Confidence:** **HIGH CONFIDENCE** on the full mechanism chain (every hop
  measured in source + preserved tracebacks). Not CONFIRMED at the emission
  level because the rejected generation content is not preserved and cannot
  be re-inspected without new live calls.
- **Code defect exists?** No defect found on the failure path. The
  throttle-only retry policy is an upstream (SDK) design property that turns
  a transient single-request failure into a dead case — a resilience gap, not
  a bug in this repo.
- **Fix recommended now?** **No code change now.** The evidence supports
  "provider-side intermittent"; the smallest plausible mitigation (a
  `ModelRetryStrategy` subclass broadening `is_retryable`) is documented
  below for decision **only if recurrence materializes** — it is a behavior
  change requiring its own canary under this repo's discipline.

---

## Failure chain

```
Groq inference — openai/gpt-oss-120b, tools attached, mid tool-loop (detector request #6)
  │  ★ FAILURE POINT: Groq's server-side parse of the model's generated output FAILS
  ▼  SSE event {"error":{"message":"Parsing failed. The model generated output ..."}}
     inside the HTTP-200 chunked stream (no HTTP status involved)
openai SDK   openai/_streaming.py:198-210 → raise APIError(message=<provider text verbatim>) at :206
             (plain APIError — NOT APIStatusError → no status_code attribute)
  ▼
strands      models/openai.py:735 (async for event in response) → except :794
             classify_openai_error() (_openai_errors.py:26-46) → None
             (matches neither the rate-limit nor context-overflow patterns)
  ▼          models/openai.py:802  bare `raise`  — original APIError, message unchanged
[evals/token_canary.py:236 pass-through wrapper records error_type="APIError", re-raises]
  ▼
strands      event_loop/_retry.py:61-70  is_retryable(APIError) → False
             (retries ONLY ModelThrottledException)        ◄── AMPLIFIER: no retry
  ▼          event_loop.py:642 `raise e` → innermost cycle try#1 (:307) re-raises unwrapped
             → propagates through THREE recurse_event_loop nestings
               (event_loop.py:357 → :972 → :446, ×3 — proves a tool-nested request)
  ▼          event_loop.py:399 except Exception → :405
             raise EventLoopException(e, request_state) from e   [str() == provider text]
  ▼
strands      multiagent/graph.py:1120 "node_id=<detector_investigator> ... | node failed"
             → NodeResult FAILED → fail-fast re-raise :1147 → "graph execution failed" :706-708
  ▼          (NO application try/except anywhere: orchestrator/graph.py:318, evals/run_evals.py:103)
harness      evals/token_canary.py:487-500 → "TASK FAILED: EventLoopException: Parsing failed …"
             → 5 synthesized rows label="task-failure", score=0.0 → case exits rc=0
             (rc reflects measurement, not success — token_canary.py:575-578, index.json all_exit_zero=true)
```

**Where "Parsing failed" originates (task question A–E):** none of A/B/D/E.
It is **provider-generated error text** (origin: Groq's server) carried
verbatim through the exception chain — `openai.APIError.message` →
`EventLoopException.__str__` — and recorded verbatim by the harness via
`{exc}` interpolation. Grep-definitive: **zero occurrences** in any
executable code in this repo, strands, openai, strands_evals, or
strands_tools; the string exists only in evidence artifacts and docs. The
harness performs no error classification and never writes those words itself.
(The table label "FAILED (detector parse)" in the prior validation doc is
human shorthand, not a harness output.)

---

## Evidence

| # | Claim | Classification | Source |
|---|---|---|---|
| 1 | Fatal message text verbatim | MEASURED | run.log:502, 553, 621, 622, 672, 776; eval-rows.json:39/47/55/63/71 |
| 2 | Case-4 request ledger: 6 detector requests; #1,2,4,5 success (752/834/912/987 in); #3 `ModelThrottledException`; #6 `APIError`, no usage | MEASURED | case-04/token-usage.jsonl rows 1-6; otel-crosscheck.json (6 chat spans; spans 3 & 6 without usage) |
| 3 | Throttle at 03:24:00.575Z recovered; retry gap 4.008 s; fatal 13.838 s after throttle; two successful requests in between | MEASURED (gap) / INFERRED (attribution of the 4 s gap to `ModelRetryStrategy.initial_delay=4`) | JSONL rows 3-6; _retry.py:43 |
| 4 | Fatal request streamed 5.134 s before erroring (accepted, then terminated mid-stream) | MEASURED | otel span 6 start/end |
| 5 | Strands retries only `ModelThrottledException` | MEASURED | strands/event_loop/_retry.py:61-70 (`isinstance(exception, ModelThrottledException)`) |
| 6 | `EventLoopException` wrap at event_loop.py:405; str() = provider text | MEASURED | source :399-405; run.log:619-621 traceback matches line-for-line |
| 7 | Raise site openai/_streaming.py:206 from an SSE `error` payload; plain APIError, no status_code | MEASURED (source + traceback) / INFERRED (SSE-payload construction — constructor frames elided) | openai/_streaming.py:197-210; run.log:546-553 |
| 8 | Request was tool-nested (depth-3 `recurse_event_loop`) | RECONSTRUCTED | run.log:592-618 frame structure (identical in corroboration log:225-251) |
| 9 | Detector died before classifier; judges never ran | MEASURED | run.log:502; zero classifier/reporter rows in case-04 JSONL; eval-rows 5× task-failure |
| 10 | Instrumentation is pass-through (innocent) | MEASURED | token_canary.py:206-241; wrapper frame run.log:538-541 re-raises inner exception |
| 11 | "Parsing failed" absent from all executable code | MEASURED | repo-wide + site-packages grep (0 hits) |
| 12 | Same detector prompt/toolset/model succeeded 45/46 instrumented Groq detector requests | MEASURED | 5-case run (28), gemini canary (7), token canary (5), fix canary (6); prompt sha identical everywhere |
| 13 | Case-4 completed successfully twice under the previous provider (Z.AI GLM-5.3), incl. a perfect 20/20-row run | MEASURED | evidence/verify-full-2026-09-04-run2.txt; evals-sequential-results-2026-09-04.json |
| 14 | Second occurrence of the identical detector parse failure in the stopped verify.sh step-6 attempt (~74 min earlier); its case identity unmarked | MEASURED (occurrence) / UNKNOWN (case identity) | verify-step6-attempt-2026-09-04.log.corroboration:138-186-254 |
| 15 | Emission contents / `failed_generation` / SSE body / HTTP status / request ids / fatal request's prompt | UNKNOWN — not preserved, by design (metadata-only instrumentation) | tree-wide search; token_canary.py docstring |
| 16 | Case-4's detector inputs were the smallest of the run (752-987 vs 755-1373 case-1) | MEASURED | per-case token-usage.jsonl |
| 17 | Case-4 is the only status-mismatch case; both `search_transactions` results empty; `get_event_log` expected next but never executed | MEASURED | evals/cases.py:108-131; data/seed_transactions.json; otel all_span_names (17 spans, no get_event_log) |

---

## Case-4 reconstruction (evidence-supported sequence)

| Time (UTC 2026-09-05) | Event | Source |
|---|---|---|
| 03:23:42.325 | Case-4 chat span opens (conv `2ddf26c7…`) right after case-3 ends | otel span 1 |
| 03:23:42→03:23:51.558 | Detector req #1 SUCCESS — in 752 / out 79; TTFT 9004 ms (elevated) | JSONL row 1 |
| 03:23:51→03:23:56.680 | req #2 SUCCESS — 834/34, cache_read 512; TTFT 5073 ms | JSONL row 2 |
| 03:23:56→03:24:00.575 | req #3 THROTTLED — `ModelThrottledException`, no usage ("OpenAI threw rate limit error", run.log:491) | JSONL row 3 |
| 03:24:00.576→03:24:04.584 | SDK retry backoff 4.008 s (matches `initial_delay=4`) | otel spans 3→4 |
| 03:24:04→03:24:05.699 | req #4 SUCCESS (recovered) — 912/148 | JSONL row 4 |
| 03:24:05→03:24:09.277 | req #5 SUCCESS — 987/122, cache_read 512 | JSONL row 5 |
| 03:24:09.280→03:24:14.414 | **req #6 FATAL** — streamed 5.134 s, then in-stream SSE error; `APIError`, no usage | JSONL row 6; otel span 6 |
| at span end | `exception=<APIError> | event loop cycle failed`; `node_id=<detector_investigator>, error=<Parsing failed. …>`; `graph execution failed` | run.log:501-503 |
| — | Traceback chain A (`openai.APIError` @ _streaming.py:206) → chain B (`EventLoopException` @ event_loop.py:405, depth-3 recursion) → chain C (harness) | run.log:504-621, 623-776 |
| — | `TASK FAILED: EventLoopException: Parsing failed …`; 5 task-failure rows written; case ends rc=0 after 35.0 s | run.log:622, 778-787; eval-rows.json; token-summary.json |

Summary of the invocation: 6 requests, one throttle (recovered by the SDK's
retry — a different, benign event 13.8 s and two successful requests before
the fatal one), no retry attempted for the fatal error, request accepted and
streaming begun then terminated mid-stream, detector-only (classifier/
reporter/judges never reached), final harness classification = 5 ×
`task-failure` (score 0.0). Tools executed before death:
`read_legacy_system`, `read_modern_system`, `search_transactions` — the case's
expected next step `get_event_log` was never reached.

**Explicitly NOT preserved:** the rejected generation (`failed_generation`
lives only on Groq's servers), the SSE/response body bytes, any HTTP status
or headers, Groq request ids, the fatal request's prompt/messages and exact
input token count, the in-flight tool name at failure, and TTFT for the two
error spans. Nothing above is fabricated; where the evidence ends, it is
stated.

**Ambient context (observed, causality NOT established):** elevated TTFTs on
case-4's first two requests (9004/5073 ms vs 572-825 ms in case-1's early
requests) and the recurring Groq warning `reasoningContent is not supported
in multi-turn conversations with the Chat Completions API` (present across
ALL cases and both failing runs — gpt-oss reasoning content being dropped
multi-turn; possibly relevant to server-side output parsing, but that is
speculation and is not relied upon).

---

## Comparison with successful runs

| Execution (Groq era, all: same model, same prompt sha, same 4 tools) | Case | Detector requests | Result |
|---|---|---|---|
| token-canary 19:51 | reversal-not-propagated | 5/5 | success |
| gemini-judge canary 21:06 | reversal-not-propagated | 7/7 | success (2 classifier throttles, recovered) |
| 5-case 22:21 | case-1 reversal | 7/7 | success |
| 5-case 22:23 | case-2 duplicate | 5/5 | detector success (case died later at reporter — `correction_draft_id`) |
| 5-case 22:23 | case-3 sync-lag | 5/5 | detector success (died later at reporter — `correction_draft_id`) |
| **5-case 22:23** | **case-4 manual-override** | **4 ok + 1 throttle(recovered) + 1 fatal** | **detector parse failure** |
| 5-case 22:26 | case-5 data-entry | 5/5 | success |
| fix-canary 22:56 | sync-lag | 6/6 | success — full case completed AFTER case-4's failure, proving the detector path itself is sound |

Differences found between case-4 and the successes: **none structural** —
not prompt (identical sha), not toolset, not model/provider, not input size
(case-4's were the *smallest*), not instrumentation (pass-through, and the
same wrapper succeeded everywhere else), not quota class (the throttle was
recovered; the fatal error is a different class). The only per-case variable
is data *shape*: case-4 is the sole status-mismatch discrepancy and the sole
case whose `search_transactions` returns empty lists on both systems, pushing
the decisive evidence to `get_event_log` — a call never reached. A
data-shape contribution (an unusual continuation context after two empty
tool results inviting a malformed next emission) **cannot be excluded** but
is unproven. Additionally, the full case-4 path completed twice flawlessly
under the previous provider (Z.AI GLM-5.3), including a 20/20-row perfect
run — the failure is provider-era-specific.

**Recurrence history of this exact signature:** two occurrences in total,
both Groq/gpt-oss-120b, same evening ~74 min apart — (1) the stopped
uninstrumented verify.sh step-6 attempt (corroboration log:138-254; case
identity unmarked — see below), (2) the 5-case run's case-4. Zero occurrences
in the entire Z.AI era and in 45 other instrumented Groq detector requests.
Precedent for nondeterministic emission rejection at Groq boundaries exists
in-repo (null vs `'None'` tool-argument lottery; same case-1 detector taking
5-8 steps across executions).

**Documentation discrepancy found (does not affect the root cause):** both
prior docs attribute the corroboration log's content to being "stopped
mid-case-1". The log itself contains **two distinct node failures** — a
reporter `correction_draft_id` null rejection (:39-111) and, later, the
detector `Parsing failed` (:138-254) — with no case banners, and
detector-after-reporter is impossible within one case, so at least two
cases' agent phases executed. The parse failure there may belong to any
later case's detector; its identity is UNKNOWN.

---

## Root cause

**HIGH CONFIDENCE** (mechanism fully measured; emission-level attribution
partially UNKNOWN).

- Category **A (application/schema defect): ruled out.** No response model,
  no structured output, no Pydantic on the detector path; tool specs
  byte-identical across 46 requests of which 45 succeeded; case data and
  prompt unchanged (sha-verified).
- Category **E (harness defect): ruled out.** The harness recorded the
  exception faithfully; `rc=0` is documented measurement semantics, not
  misclassification.
- Category **D (framework/adapter defect): not a defect** — Strands/openai
  behaved as designed — but the **throttle-only retry policy
  (`_retry.py:70`) is the amplifier** that converts a transient
  single-request provider rejection into a terminal case failure with zero
  retry attempts.
- Categories **B (model-output defect) vs C (provider behavior): the
  failure event is a provider-side in-stream rejection (C) of a single
  nondeterministic model emission whose contents are unknown (B,
  unobservable).** Groq's own message attributes the fault to the model's
  generation ("The model generated output that could not be parsed");
  whether the emission was truly malformed or trips a fragile server-side
  parser cannot be determined from this repo. Primary label: **C delivered
  terminally; B unresolved.**

**Strict separation from `correction_draft_id` (maintained):** different
node (reporter vs detector), different error text ("Tool call validation
failed: … expected string, but got null" vs "Parsing failed. The model
generated output that could not be parsed"), different mechanism
(server-side validation of emitted tool *arguments* against a schema vs
server-side parse failure of the model *output itself*). The corroboration
log shows both failures occurring independently in the same attempt
(:39 vs :138), proving they are distinct failure modes. The
`correction_draft_id` annotation fix neither causes, masks, nor remediates
this failure, and this failure does not revisit that fix. No causal
relationship is claimed or found.

**Determinism:** intermittent, provider-dependent, emission-level
nondeterministic ("lottery"), with an unproven possible case-data-shape
contribution. NOT established as deterministic or purely case-data-driven
(evidence against: 45/46 identical-path successes including the same run's
other four cases and a post-failure canary; case-4 twice-clean under the
prior provider; smallest inputs of the run).

---

## Fix recommendation

**No code change should be made yet.** No defect in this repo's code is
proven; the failing step is provider-side; the observed rate is 1/46
instrumented detector requests (single occurrence); and any retry-semantics
change is a live-behavior change that, under this repo's discipline (and the
segregation/Tier-C culture), needs its own canary — spending a canary now to
mitigate a ~2%/request transient is not evidence-driven. The already-landed
`correction_draft_id` fix is independent of this path.

**Candidate minimal fix — held for decision only if recurrence materializes:**
- File/symbol: new `agents/retry.py` (or extend `agents/model.py`) with a
  subclass of `strands.event_loop._retry.ModelRetryStrategy` overriding
  `is_retryable()` to also return True for in-stream `openai.APIError`
  (optionally narrowed to parse/validation-class messages or to errors
  without `status_code`); wire it via `retry_strategy=` in the three agent
  builders (`agents/detector_investigator.py:44`,
  `agents/classifier.py`, `agents/reporter.py`). The SDK documents this
  exact extension point (_retry.py:31-32: "Subclass and override
  ``is_retryable`` … without reimplementing the rest of the retry policy").
- Why it addresses the failure: the observed failure is a single bad
  emission; a fresh attempt resamples the emission (precedent: Groq accepted
  the sibling failure's alternate emission `'None'`), and the recovery of
  case-4's own throttled request #3 shows in-loop retry preserves the
  conversation and completes.
- Regression risks: would also retry argument-validation rejections
  (masking future schema defects behind 6-attempt storms and backoff
  delay); delays genuinely terminal errors; must keep
  `ContextWindowOverflowException`/`MaxTokensReachedException` non-retried;
  changes benchmark failure economics (a "recovered" case is a different
  measurement than an unmetered clean case — must be disclosed in any run
  report).
- Offline regression test (to add if implemented): fake model whose
  `stream()` raises `openai.APIError("Parsing failed. …")` once then
  succeeds → assert agent completes, retry counter == 1; plus a
  non-retryable control (e.g. `ContextWindowOverflowException` still raises
  through) and an exhaustion case (always-raising → surfaces after
  max_attempts).
- One-case canary (if implemented): single live execution of case-4
  `manual-override-not-reflected` on the Groq detector path with the retry
  strategy active; success criteria: case completes all agents + judges,
  zero unauthorized actions, any parse-retry (if triggered) visibly
  recovered in token-usage rows. Honest limitation: because the failure is
  intermittent (~2%/request), a clean canary proves no-regression, not
  cure; the decisive statistic is the recurrence rate over the next 5-case
  run(s).

---

## Impact on next 5-case validation

**Recommendation: proceed with the next 5-case validation without waiting
for a fix or a dedicated one-case canary** (auditor's recommendation; the
GO/NO-GO and quota spend remain the human's call):

1. The only other known blocker (`correction_draft_id`) is fixed and
   separately validated; this failure mode is provider-side, intermittent,
   fail-fast (cannot corrupt results or safety properties), and already
   handled gracefully by the driver (failure recorded, loop continues).
2. Recurrence is materially likely and should be **pre-registered**: at the
   observed point rate (~1/46 agent requests; a 5-case run makes ~41-48
   at-risk agent requests), the projected chance of ≥1 such failure is
   ≈60% (point estimate), with a wide uncertainty interval (single
   occurrence; 95% band roughly 6%-90%). If it recurs, classify it
   immediately as the known provider-side intermittent issue — do not
   launch another audit; record request-level rows as this run did.
3. Escalation criterion: implement the retry-strategy fix (with its own
   offline tests + one-case canary) only if the failure recurs at a rate
   that materially blocks GO (suggested threshold: ≥2 cases lost to this
   signature in one 5-case run, or any recurrence on ≥2 consecutive runs).
4. A one-case canary for THIS failure mode alone has low statistical power
   (one sample of a ~2% event) and would consume quota better spent on the
   5-case run that doubles as the recurrence experiment.
5. Minor documentation correction to carry into the next report: the
   corroboration log ("stopped mid-case-1") contains two distinct node
   failures across ≥2 cases; the detector parse failure in it has no case
   marker. Its correct citation is "a second, unattributed occurrence of
   the same detector signature", not "case 1".
