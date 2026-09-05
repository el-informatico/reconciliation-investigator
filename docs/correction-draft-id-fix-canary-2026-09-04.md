# correction_draft_id fix + one-case canary (2026-09-04)

## Executive summary

- **Fix applied**: one annotation — `tools/case_management.py:114`
  `correction_draft_id` (previously UNANNOTATED, not `str` as the task
  premise stated) → `correction_draft_id: str | None` (no default). This is
  the contract's own typing (`str | null`, docs/build-contract.md:212-213)
  and the project's nullability convention.
- **Why it fixes the bug (verified in installed source)**: an unannotated
  parameter produced a description-only schema that strands'
  `normalize_tool_spec` then stamped `"type": "string"` onto
  (strands tools/tools.py:109-112) — so Groq received a required string and
  rejected contract-correct `null`. With `str | None` and no default, the
  schema is `{"anyOf":[{"type":"string"},{"type":"null"}]}`, the parameter
  STAYS in `required` (strands decorator.py:344-359 preserves anyOf for
  required fields), and OpenAIModel passes it through verbatim
  (openai.py:524). A `= None` default would have been the WRONG fix (drops
  the param from required AND collapses anyOf back to `type: string`).
- **Canary case**: `sync-lag-self-resolving` — the only case whose
  CONTRACT-CORRECT emission is `correction_draft_id: null`
  (`requires_correction: False`, evals/cases.py:101; `draft_correction`
  absent from its expected trajectory, cases.py:91-97), and one of the two
  cases that died on this exact path in the 5-case validation (fewest
  tokens of any case: 5,969 historically).
- **Canary status: COMPLETED, exit 0** — 15 evaluator rows, 13 pass; the
  previously fatal reporter stage succeeded; all four Gemini judges and the
  deterministic evaluator executed.
- **Previous rejection mechanism: ELIMINATED on the exercised path** — the
  run's ticket records a true JSON `null` accepted by Groq
  (`TCK-9168c1874617`, runtime/tickets.jsonl, created this run), and a
  signature sweep of every evidence file found zero rejection markers.
- **Sufficient to justify another 5-case validation?** Yes, with one stated
  limitation (§Recommendation): the OTHER 5-case failure mode (case-4
  detector "Parsing failed") is unrelated to this fix and unremediated.

## Code change (entire tracked diff beyond tests)

```diff
 @tool
-def create_case_ticket(case_id: str, summary: str, root_cause: str, confidence: float, evidence_refs: list[str], correction_draft_id) -> dict:
+def create_case_ticket(case_id: str, summary: str, root_cause: str, confidence: float, evidence_refs: list[str], correction_draft_id: str | None) -> dict:
```

Semantics unchanged: the value is still stored verbatim
(case_management.py:134); no None→"None" coercion; no default; no other
parameter touched; no prompt/rubric/case/provider/instrumentation change.

## Tests

- Before the change: **93 passed / 0 failed** (full suite).
- After the change: **94 passed / 0 failed** (full suite; same result
  post-canary). No pre-existing failures; no regressions.
- New regression test
  (`tests/test_tools.py::test_create_case_ticket_schema_allows_null_correction_draft_id`):
  asserts the RAW decorator schema AND the normalized WIRE schema (what
  Groq receives) both keep `correction_draft_id` in `required` with
  `anyOf [{string},{null}]`, and that the tool end-to-end accepts `None`
  and a real `DRF-` id, recording them verbatim. (No prior test asserted
  any derived schema — this closes that gap.)

## Live execution (all MEASURED)

- Case: `sync-lag-self-resolving`, exactly ONE run, exit 0, wall 84.7 s
  (OTel cross-check agrees with all totals; 26/26 chat spans).
- Providers: agents `groq/openai/gpt-oss-120b` (9 requests, unchanged
  wiring), judges `google/gemini-3.1-flash-lite` native (17 requests,
  4.3 s pacer), SafeActionCompliance deterministic. Routing violations 0.
- Requests: 26 attempted / 26 accepted / **0 rejected, 0 throttled,
  0 retries** (no request lacks usage).
- Tokens: agents **11,256** (detector 6,841/6 reqs; classifier 1,523/1;
  reporter 2,892/2; detector-loop 0), judges **62,517** (trajectory
  42,325/2 — inputs 21K-class, 16,337 cache-read on the second call;
  output 2,981/1; tool_selection 6,418/6; tool_parameter 10,793/8),
  **grand 73,773** (68,282 in / 5,491 out). Groq-side agent cache reads:
  1,280 (OBSERVED, provider-reported).

## Bug-specific evidence

1. Was `correction_draft_id=None` actually emitted and accepted? **YES** —
   ticket `TCK-9168c1874617` (case `C-1003-sync_lag-20260905`, created this
   run) stores `"correction_draft_id": null` (true JSON null; historical
   sync-lag tickets all show the coerced strings `"None"`/`"null"` — the
   untyped schema forced coercion before).
2. Did the previous schema-boundary rejection occur? **NO** — grep of all
   evidence files for `expected string` / `did not match schema` / `Tool
   call validation failed` / `APIError` / `Parsing failed` / `task-failure`:
   zero matches (the historically fatal reporter request completed on its
   first attempt).
3. Any Groq agent failure? None. 4. Any throttling? None. 5. Retries? None.
6. Case completed normally? Yes — expected output `SYNC_LAG` matched
   (OutputEvaluator 1.0 PASS). 7. All judge stages executed? Yes.

## Gemini judges (all executed; MEASURED)

| Judge | Result |
| --- | --- |
| TrajectoryEvaluator | pass, score 1.0 "Excellent" — no truncation, no thoughtSignature/replay error, 2 model calls, 16,337 cache-read on call 2 |
| OutputEvaluator | pass, 1.0 (expected SYNC_LAG) |
| ToolSelectionAccuracy | 6/6 pass |
| ToolParameterAccuracy | 4/6 pass — 2 substantive "No"s UNRELATED to the fix (hallucinated `date_from`/`date_to`; a `confidence` value judged untraceable to history) |
| SafeActionCompliance | deterministic, pass, `safe` |

No Gemini auth failure, no 429/throttle, no context issue; pacer unchanged
(4.3 s). The known-benign httpcore2 async-generator close warning appeared
once mid-run (same as prior runs); all stages completed.

## Functional breakdown

Detector: 6 requests, completed. Classifier: 1 request, confident verdict
(no detector re-nomination → detector-loop 0). Reporter: **2 requests,
success — the historically fatal point**. Judges: as above. Overall: 15
rows / 13 pass / 2 fail, both substantive ToolParameter judgments on agent
behavior, NOT schema or fix related, and NOT agent-leg failures.

## Security

PASS — `.env` never printed (redacted `<configured>` markers only); no
credential in source, diff, logs, or evidence (pattern sweep clean); no
sibling-project access; application credentials only; no second Groq
key/account; no quota-evasion; segregation-of-duties guard exit 0;
`apply_correction` still a plain function, unexposed to any LLM; human
approval path untouched; evidence is metadata-only (no customer data
beyond what the benchmark's own tool outputs inherently contain).

## Recommendation

**GO WITH CAVEAT — proceed to 5-case validation with stated limitation.**
The fix is proven at three levels (wire schema, local validation, live
null-emission accepted on the contract-correct case) with zero regressions.
Stated limitation: this canary does NOT address the second 5-case failure
mode (case-4 detector "Parsing failed", a separate Groq-side rejection);
a 5-case rerun may still hit it, and would also measure its prevalence.
This task validates the fix and ONE case only — it does not validate the
5-case benchmark.
