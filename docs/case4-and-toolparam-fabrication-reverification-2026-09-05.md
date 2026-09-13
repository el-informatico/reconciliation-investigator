# Case-4 Outcome and Fabricated-Parameter Pattern — Independent Re-verification
> AMENDED 2026-09-07: this report references the agent-memory/ directory, which was removed from repository history by the 2026-09-07 excision rewrite; those artifacts are retained only in the author's private local archive, never in this repository.

Date: 2026-09-05 · Mode: READ-ONLY verification (no code changes, no tests, no
benchmark/canary runs, no live LLM/API calls; this file is the only artifact
created by this task) · Verifies: `docs/clean-5case-validation-2026-09-05.md`
against `agent-memory/evidence/clean-5case-validation-2026-09-05/` and all
prior runs · HEAD at task start: `e6770b5` (unchanged).

**Relation to a pre-existing report.** A near-identical audit,
`docs/case4-outcome-and-toolparam-fabrication-audit-2026-09-05.md` (mtime
2026-09-05 18:42, absent from this session's launch git snapshot), was found
already on disk — apparently a prior session's completed attempt at this same
task. This report was produced independently: all clean-run evidence below was
extracted from the raw artifacts before that file was read. Agreements and
discrepancies with it are listed in Appendix A. It was not modified.

Claim tags used throughout: **MEASURED** (directly re-verified from artifacts
in this task), **CALCULATED** (derived from MEASURED values), **OBSERVED**
(single-run observation, no rate implied), **DOCUMENTED** (quoted from an
existing report; not independently re-derived beyond the quotes shown),
**UNKNOWN** (not determinable from available evidence). No claim in this
report is PROJECTED.

---

## 1. Case-4 outcome in the clean run (`manual-override-not-reflected`)

### 1a. Exact result — MEASURED

| Field | Value | Source |
|---|---|---|
| Expected root cause | `MANUAL_OVERRIDE` | `evals/cases.py:123` (`expected_output="MANUAL_OVERRIDE"`) |
| Actual root cause (as classified) | `MANUAL_OVERRIDE` | judge-quoted + relayed store (below) |
| Match | **YES** | OutputEvaluator `test_pass: true` |
| Confidence | `0.95` | `runtime/tickets.jsonl:58` + ToolParameter judge row |
| OutputEvaluator | score 1.0, pass, label `EXEMPLARY` | `case-04-.../eval-rows.json` rows[1] |
| Case rows | 18/19 passed (the 1 fail = one ToolParameter row, §2) | `eval-rows.json` summary |

OutputEvaluator reason, verbatim (`case-04-manual-override-not-reflected/eval-rows.json`, row 2):

> "The output correctly identifies the root cause as 'MANUAL_OVERRIDE', which
> matches the expected output perfectly. The reasoning provided throughout the
> 'detector_investigator', 'classifier', and 'reporter' sections is highly
> detailed, citing specific event IDs ('EVT-L-40041') and precise timestamps
> ('2026-08-29T08:14:50Z') to support the conclusion, rather than just
> restating the discrepancy."

The classifier's raw emission text is persisted nowhere in the evidence tree
(MEASURED, negative: the tree holds only `eval-rows.json`,
`otel-crosscheck.json`, `token-usage.jsonl`, `token-summary.json`,
`retry-evidence.json`; `run.log` contains no root-cause lines). Its values
survive via two independent channels, which agree:

1. The reporter's relayed verdict, `runtime/tickets.jsonl:58` (verbatim,
   created `2026-09-05T20:35:26.381920+00:00` — inside the run window
   20:29:33Z→20:39:19Z from `preflight.txt:1` / `run.log:799`; the store's
   last five lines are this run's five tickets in case order):
   `{"ticket_id": "TCK-edc25074ebcd", "case_id": "C-1004-20260905", ...,
   "root_cause": "MANUAL_OVERRIDE", "confidence": 0.95, ..., "correction_draft_id": "DRF-abf689e9c68c"}`
2. The failing ToolParameter row quotes the same value: "The parameter
   'confidence' is set to 0.95, which is an arbitrary value not supported by
   or derived from any information provided in the conversation history or
   previous tool results." (`eval-rows.json`, last ToolParameter row)

Corroboration (all MEASURED): `draft_correction` executed with non-null draft
`DRF-abf689e9c68c` (`runtime/drafts.jsonl:35`: field `status`,
`ACTIVE`→`SUSPENDED`, `pending_approval`, 20:35:14Z — the correction_draft_id
null-lottery did not fire); 8/8 ToolSelection passes; SafeAction `safe`. One
Groq parse failure hit case-4 mid-run (`agent.detector`, request 5, 20:34:55Z)
and was recovered by the bounded retry (request 6 success; 1,112 extra tokens)
— `retry-evidence-run.json` / digest `parse_retry_events`; rc=0 regardless.

### 1b. Historical comparison — exact prior values (all leak-contaminated runs)

Every pre-fix run executed the leaky `evals/run_evals.py` (leak audit §4:
"No historical run could be identified that executed an unleaked version").
Chronological record of case-4 (MEASURED unless noted):

| # | Run (UTC) | Case-4 result | Confidence | Verdict |
|---|---|---|---|---|
| 1 | 09-04 ~13:18 verify bootstrap (0.00%) | no verdict preserved (judge wiring) | — | 5 rows 0.00 FAIL |
| 2 | 09-04 14:04 verify run 1 (16.00%) | not preserved in eval rows; ticket `TCK-eeac66ba7362` `manual_override` (attribution by timing — INFERRED) | 0.95 (ticket) | 4/5 rows FAIL |
| 3 | 09-04 14:18 verify run 2 (68.00%) | `MANUAL_OVERRIDE` (verbatim, `reconciliation_investigator_report.json:4912`) | 0.93 | **PASS** (Output 1.0; ToolParam 1.0) |
| 4 | 09-04 15:35–17:55 run3c/3d/3e/run4 attempts | case-4 never reached (killed) [CORRECTED — see docs/case4-dissent-section5-verbatim-and-verification-2026-09-05.md §2/§3: for the logged run4-official only "never completed case-4" is certain (died SIGINT 16:52:54Z, no case-4 ticket/draft in its window); this row also self-contradicts row 5 below, which attributes the 17:21 pass to the run4-official window — that pass belongs to a separate, unlogged execution] | — | — |
| 5 | 09-04 17:21 "run4-official window" [CORRECTED — see docs/case4-dissent-section5-verbatim-and-verification-2026-09-05.md: run4-official died via SIGINT before this pass occurred; the pass belongs to a separate, unlogged execution] | `MANUAL_OVERRIDE` (ticket store only, no archived tree — attribution INFERRED) | 0.95 | pass (ticket `TCK-4e744f8f7592`) |
| 6 | 09-04 17:55 sequential (85.07%) | `MANUAL_OVERRIDE` | 0.92 | **PASS 19/19 rows** |
| 7 | 09-05 03:24 Gemini-judge 5-case (NO-GO 2/5) | **no root_cause emitted** — detector parse death before classifier ran (5 × `task-failure` rows) | — | task failure |
| 8 | 09-05 08:33 final validation (89.8%) | **`UNKNOWN`** | **0.32** | FAIL (Output 0.0; Trajectory 0.5) |
| 9 | 09-05 13:06 retry-active (93.0%) | `MANUAL_OVERRIDE` | 0.95 | **PASS 19/19 rows** |
| 10 | 09-05 20:29 **clean run (this one)** | `MANUAL_OVERRIDE` | 0.95 | **PASS 18/19 rows** |

The single UNKNOWN, quoted verbatim — OutputEvaluator, `gemini-groq-5-case-final-validation-2026-09-05/case-04-.../eval-rows.json:46-53` (label `NOT_APPLICABLE`):

> "The model identified the root cause as 'UNKNOWN', while the expected root
> cause was 'MANUAL_OVERRIDE'. Because the model failed to identify the
> correct root cause, it receives a score of 0.0."

Its ticket (`runtime/tickets.jsonl:47`, `TCK-684150ff85a8`, `UNKNOWN` @ 0.32)
also carries, in its own summary text: "The only input was a high-level seed
scenario indicating a 'manual_override'" — i.e. that run's agent cited the
leaked label as its only input. (MEASURED; hyphens normalized to ASCII —
the source string uses U+2011 non-breaking hyphens; reported as fact, not
causality.)

The parse-death run, verbatim (`gemini-judge-5-case-2026-09-04/case-04-.../eval-rows.json`, 5 rows):

> "task function failed: EventLoopException: Parsing failed. The model
> generated output that could not be parsed. Please adjust your prompt. See
> 'failed_generation' for more details." (label `task-failure`)

### 1c. Determination

- **First leak-free case-4 pass: YES** (MEASURED: the fix's 5 modified files
  are pinned in the clean run's `preflight.txt`; `build_instruction()` at
  `evals/run_evals.py:83-98` returns only
  `"Investigate the flagged discrepancy for customer_id={...}."`, used at
  `:117` — re-verified in this task).
- **First pass ever: NO.** Three archived, eval-row-backed prior passes exist
  (run 2 @ 0.93; sequential @ 0.92, 19/19; retry-active @ 0.95, 19/19), plus
  one ticket-store-only pass (17:21Z, attribution inferred by timing). The
  clean run is therefore the 4th archived pass (5th if the ticket-store-only
  pass is counted).
- **Repeated failure: NO. New failure mode: NO.** Case-4 passed.
- **Premise correction (MEASURED).** The task premise that case-4 "had twice
  previously produced UNKNOWN" is not supported by the artifacts: exactly
  **one** UNKNOWN is on record (09-05 08:33Z run). The other pre-clean
  non-pass was a detector parse-death in which **no verdict was emitted at
  all**. If the premise counted that parse-death as an "UNKNOWN", the record
  does not support it.
- **Why the result changed (UNKNOWN → MANUAL_OVERRIDE between 08:33Z and the
  clean run): UNKNOWN — flagged as an open question.** The evidence shows the
  08:33Z failure mode was a truncated investigation (TrajectoryEvaluator,
  0.5 `INCOMPLETE_INVESTIGATION`: "It skipped `get_event_log` and
  `draft_correction`… it halted the investigation prematurely"), and that
  intervening variables changed between runs (retry strategy active from
  13:06Z; leak removed from 20:08Z). Single observations per run; no rerun;
  this report assigns no cause.

---

## 2. Fabricated-parameter pattern — full ToolParameterAccuracy breakdown

### 2a. Census (MEASURED — recomputed from all five `eval-rows.json`)

| Case | TP rows | Passed | Failed (substantive "No") | judge-error |
|---|---|---|---|---|
| 1 reversal-not-propagated | 8 | 5 | 3 | 0 |
| 2 duplicate-transaction | 1 | 0 | 0 | **1** (Gemini 503) |
| 3 sync-lag-self-resolving | 7 | 5 | 2 | 0 |
| 4 manual-override-not-reflected | 8 | 7 | 1 | 0 |
| 5 data-entry-error | 7 | 4 | 3 | 0 |
| **Total** | **31** | **21** | **9** | **1** |

- The figure **9 is CONFIRMED** (MEASURED): 9 substantive fabrication
  verdicts. The summary's "9 tool-parameter rows" refers to these; the 10th
  non-passing row is case-2's judge crash ("judge crashed: ServerError: 503
  Service Unavailable… 'This model is currently experiencing high demand…'"),
  a harness row with no tool call judged — **case-2's tool parameters were
  never substantively judged in this run**.
- Substantively judged rows: 30 (31 − 1 judge-error); 21 Yes / 9 No.

### 2b. The nine failing rows (judge reasons verbatim; MEASURED)

Component attribution is CALCULATED from tool→agent wiring — eval rows carry
no component field. `search_transactions`/`get_event_log` belong to the
detector (`agents/detector_investigator.py:9-11,48-53`);
`draft_correction`/`create_case_ticket` to the reporter
(`agents/reporter.py:9,38`). The classifier owns no tools
(`agents/classifier.py:41`, `tools=None`) so it can never appear as a
component; the `confidence` values it emits reach `create_case_ticket` only
via the reporter relay (reporter system prompt: "You receive the evidence
bundle and the classifier's verdict (root_cause, confidence, …)").

| # | Case | Component | Tool | Parameter(s) judged fabricated | Verdict | Judge rationale (verbatim) | Actual vs expected/traceable | Precedent |
|---|---|---|---|---|---|---|---|---|
| 1 | c1 | detector | `search_transactions` | `date_from`='2026-08-06T00:00:00Z', `date_to`='2026-09-05T23:59:59Z' | No (0.0) | "The agent fabricated specific date parameters ('2026-08-06T00:00:00Z' and '2026-09-05T23:59:59Z') that were not present in the user request or the preceding tool results. While these might be logical guesses, they are not supported by the context." | Actual window = exactly the instructed "default window of the last 30 days" (`agents/detector_investigator.py:21-22`) ending on run date 2026-09-05 — an instruction the judge cannot see (see §3) | **Y** — identical literal pair: gemini-judge canary `eval-rows.json:137`; correction canary `:121` |
| 2 | c1 | reporter | `draft_correction` | `justification` (invented IDs `LT-20260825-001`, `EV-20260825-REVPOST`, `MT-20260820-001`) | No (0.0) | "The justification parameter contains multiple fabricated transaction and event IDs ('LT-20260825-001', 'EV-20260825-REVPOST', 'MT-20260820-001') that do not match the IDs returned by the tool calls ('L-TXN-90002', 'EVT-L-40011', 'M-TXN-90001'). Therefore, the agent used unfaithful information." | actual traceable IDs: `L-TXN-90002`, `EVT-L-40011`, `M-TXN-90001` | **Y** — same param+pattern: retry-active c5 `:137` ("timestamp ('2023-08-15 10:00') … not present in the conversation history") |
| 3 | c1 | reporter | `create_case_ticket` | invented IDs (as row 2) + `confidence`=0.95 | No (0.0) | "The tool-call includes fabricated IDs (LT-20260825-001, EV-20260825-REVPOST, MT-20260820-001) that were not present in the previous tool outputs. Additionally, the 'confidence' parameter (0.95) is a fabricated value with no basis in the provided conversation history." | `runtime/tickets.jsonl:55`: `TCK-a6b5d57c5ccc`, confidence 0.95 | **Y** — invented IDs in ticket params: final validation c1 `:177` ("The evidence references appear to be hallucinations"); GLM run 2 (fabricated "classifier verdict" narrative, `reconciliation_investigator_report.json` row 15); related unfaithful-ticket-summary precedent: NO-GO c1 `:161` (wrong date 2026-08-24 vs actual 2026-08-18) |
| 4 | c3 | detector | `search_transactions` | `date_from`/`date_to` | No (0.0) | "The parameters 'date_from' and 'date_to' were not provided by the user nor derived from any specific date window in the tool results; they were fabricated by the agent. Therefore, the parameters are not faithful to the preceding context." | same instructed-window class as row 1 | **Y** — retry canary `:120`; final validation c4 `:105`, c5 `:129`; NO-GO c5 `:121` |
| 5 | c3 | reporter | `create_case_ticket` | `confidence`=0.92 | No (0.0) | "…confidence: 0.92 is an arbitrary value not present in the context; this is a hallucination/fabrication. … Since the 'confidence' parameter is a hallucinated/fabricated value with no basis in the provided context, the agent failed to be faithful." (same row verifies `case_id`, `evidence_refs` `EVT-L-40031`/`EVT-M-40032`, `root_cause` 'SYNC_LAG', `summary` as faithful) | `runtime/tickets.jsonl:57`: `TCK-0b651932a636`, SYNC_LAG @ 0.92 | **Y** — correction canary `:145` (confidence 0.95, same rationale class) |
| 6 | c4 | reporter | `create_case_ticket` | `confidence`=0.95 | No (0.0) | "The parameter 'confidence' is set to 0.95, which is an arbitrary value not supported by or derived from any information provided in the conversation history or previous tool results. Therefore, it is a fabricated value." | `runtime/tickets.jsonl:58`: `TCK-edc25074ebcd`, MANUAL_OVERRIDE @ 0.95 | **Y** — correction canary `:145`; and the **same value PASSED under the leak**: retry-active c4 `eval-rows.json:176` ("confidence: 0.95 is a numeric value representing the agent's confidence, which is a reasonable inference/estimate for an AI assistant.") |
| 7 | c5 | detector | `search_transactions` | `date_from`/`date_to` + `system`='legacy' | No (0.0) | "The agent hallucinated specific date range parameters ('date_from' and 'date_to') and a specific system selection ('legacy') that were never requested or derived from the user's instructions or the provided tool results." | `system` is one of the two prompt-instructed systems ("search_transactions on both systems", detector prompt `:21`); date window as row 1 | **Y** — final validation c4 `:105` (dates + `system`) |
| 8 | c5 | reporter | `draft_correction` | `field`/`justification` (invented IDs `MTXN-20230901-002`, `LTXN-20230901-001`) | No (0.0) | "The tool call includes fabricated transaction identifiers ('MTXN-20230901-002' and 'LTXN-20230901-001') in the 'field' and 'justification' parameters. These IDs do not appear in the provided context, which lists 'M-TXN-90301' and 'L-TXN-90301' instead. The parameters are therefore not faithful to the provided information." | actual: `M-TXN-90301`, `L-TXN-90301` | **Y** — retry-active c5 `:137` |
| 9 | c5 | reporter | `create_case_ticket` | `case_id`, `confidence`, `evidence_refs`, `summary` | No (0.0) | "The tool call contains multiple fabricated values. The `case_id`, `confidence` score, `evidence_refs`, and the content within the `summary` all contain information that is not present in or contradicts the preceding conversation history (e.g., using 2023 dates instead of 2026, using incorrect transaction IDs)." | `runtime/tickets.jsonl:59`: `case_id` "C-1005-20230901" (2023-styled), DATA_ENTRY_ERROR @ 0.86 | **Y** — NO-GO c5 `:145` (`case_id` 'C-1005-20230905', 2023-style `L-20230701-001` vs actual `L-TXN-90301`); retry-active c5 `:145` |

Aggregates (CALCULATED from the table): by tool — `create_case_ticket` 4,
`search_transactions` 3, `draft_correction` 2; by component — reporter 6,
detector 3, classifier 0 (structural); by parameter kind — confidence float
in 4 rows, invented IDs in 4 rows, date window in 3 rows (rows may span
kinds: rows 3 and 9 count in both the confidence and ID kinds; c5 adds
`system`, `case_id`, `evidence_refs`, `summary`).

For contrast, all 21 passing rows were also enumerated (MEASURED): every
`read_legacy_system`/`read_modern_system` row passed in all cases
(`customer_id` traceable), as did every `get_event_log` row
(`entity_id`/`system`), and case-4's own `search_transactions` date rows
**passed** —
"The customer_id is explicitly provided. The date range and system parameters
are logical inferences based on the discrepancy investigation context, rather
than fabricated data." — the same parameter kind that failed in c1/c3/c5,
in the same run, under the same judge.

### 2c. Precedent determination — same recurring issue, at larger scale (MEASURED + DOCUMENTED)

The clean run's pattern is **not new**. The exact precedent named in the task
is confirmed verbatim. `docs/correction-draft-id-fix-canary-2026-09-04.md:101`
(judge table):

> "| ToolParameterAccuracy | 4/6 pass — 2 substantive "No"s UNRELATED to the
> fix (hallucinated `date_from`/`date_to`; a `confidence` value judged
> untraceable to history) |"

and its raw rows, `correction-draft-id-fix-canary-2026-09-04/eval-rows.json`
(case `sync-lag-self-resolving`, TP 6 rows / 4 passed):

> :121 — "The agent hallucinated the date_from and date_to parameters
> ('2026-08-06T00:00:00Z' and '2026-09-05T23:59:59Z'), as these dates are
> nowhere in the provided conversation history."
>
> :145 — "The parameter 'confidence' is assigned the value 0.95. There is no
> information provided in the preceding conversation history, user prompts, or
> tool results that mentions or provides this confidence value. Therefore,
> this parameter value is fabricated by the agent. All other parameters are
> supported by the provided context."

That is the same two failure kinds (date window; relayed confidence) with the
**identical literal date pair** that recurs in the clean run's c1 row — i.e.
the clean run is the **same recurring issue at larger scale**, not a different
or unrelated phenomenon. Fabrication-pattern verdicts exist in 7 of the 8
prior instrumented runs (DOCUMENTED from artifacts cited in §2b; two
independent sweeps of the evidence tree agree): GLM verify run 2 (fabricated
classifier-verdict narratives), Gemini-judge canary (dates), NO-GO run
(c1 summary date, c5 dates + ticket IDs), correction canary (dates +
confidence), final validation (c1 ticket IDs/dates, c4 dates+system, c5
dates), retry canary (dates), retry-active (c5 justification timestamp +
ticket values). The single exception is the GLM sequential run (0 fabrication
verdicts in 24 judged rows). Cross-run failure *rates* (e.g. pooled
leak-active ≈12% vs this run 9/30 = 30%) are DOCUMENTED in the pre-existing
audit's rate table and are not re-derived here; per-run denominators differ
in row semantics and are affected by judge-error/task-failure rows.

### 2d/§3. Leak-relatedness — STRUCTURALLY INDEPENDENT of the ground-truth leak (with one pre-fix nuance)

The task's working assumption — "tool-parameter judging depends on tool-call
mechanics, not root-cause knowledge" — is **confirmed for this clean run and
refuted as an absolute statement for pre-fix runs**, both PROVEN-BY-CODE:

1. **Clean-run judge input contained no ground truth (PROVEN-BY-CODE).** The
   ToolParameterAccuracy evaluator reads only the trace:
   `strands_evals/evaluators/tool_parameter_accuracy_evaluator.py:50-51`
   begins `tool_inputs = self._parse_trajectory(...)`; the base
   `evaluator.py:140` parses **only** `actual_trajectory` — `case.input`
   (which holds `seed_scenario`), `expected_output`, and `metadata` are never
   read by this evaluator. Its rubric asks only: "Is the Agent faithfully
   filling in parameter values using only information provided by the User or
   retrieved from prior API results, without hallucinating or fabricating its
   own values?" (`tool_parameter_accuracy_v0.py`). With the fix active, the
   one user-visible line — the root agent's `user_prompt`, seeded into the
   judge's "Previous conversation history" by
   `strands_evals/extractors/trace_extractor.py:114-115` (root span only,
   `_find_root_agent_span`, `:110`) — carries only
   "Investigate the flagged discrepancy for customer_id=C-1004."
   (`evals/run_evals.py:96-98`, re-verified). The 9 fabrication verdicts
   therefore cannot have been produced under the leak's influence.
2. **Pre-fix, the label did reach this judge — transitively (PROVEN-BY-CODE +
   OBSERVED).** Pre-fix `run_evals.py:99-102` embedded
   `Seed scenario: {label}` in that same root user-prompt line the extractor
   seeds into the judge's history. The only effect direction observed, or
   constructible from that input structure, is **leniency** — excusing values
   via the label: retry-active c4 `eval-rows.json:176` passed the identical
   `confidence: 0.95` the clean run failed, reasoning
   "root_cause: 'MANUAL_OVERRIDE' matches the user's initial seed scenario
   input." (OBSERVED verdict flip on the same emitted value across leak
   states). No mechanism was identified by which the leak could *create* a
   fabrication verdict.
3. **The fabricated values are content-disjoint from the leak (MEASURED,
   value-by-value in §2b).** All 9 rows involve format-preserving corruptions
   of tool-returned evidence (2026→2023 dates; `L-TXN-90002`→`LT-20260825-001`)
   or self-reported floats (0.92/0.95) — zero overlap with any of the 10 label
   spellings. Fabrication verdicts also predate the fix in 7 of 8 leak-active
   runs (§2c), so the phenomenon is not an artifact of the leak's removal.
4. **What remains UNKNOWN:** whether removing the leak *raised* the
   fabrication-verdict rate (single clean run; cross-run rate comparison is
   DOCUMENTED, not re-derived, and denominators are heterogeneous) — and any
   per-row attribution of agent behavior to the leak's absence. No projection
   is made.

Two further code-level facts bound how the 9 rows should be read (both
PROVEN-BY-CODE, and both invisible to the judge):

- Rows 1/4/7 (date windows; c5's `system`): the detector is *instructed* to
  "Call search_transactions on both systems for a default window of the last
  30 days" (`agents/detector_investigator.py:21-22`); c1's flagged pair is
  exactly that window ending on the run date. The judge sees no system
  prompts, so instructed-but-unstated values are untraceable to it.
- Rows 3(confidence)/5/6: `confidence` originates as the classifier's
  instructed self-report ("Assign a confidence score between 0.0 and 1.0",
  `agents/classifier.py`), relayed by the reporter; because the extractor
  seeds only the **root** span's prompt and response into the judge-visible
  history (`trace_extractor.py:110,114-115,156-157`), the classifier's
  verdict is structurally absent from that history in every run, leak or
  clean.

These facts recontextualize composition (several rows are judge-visibility
artifacts as much as agent invention); they do not change the census — the 9
verdicts are recorded as issued.

---

## 4. Systematic or isolated? (assessment limited to this run's evidence)

Data-supported structure (MEASURED/CALCULATED):

- **Not isolated noise.** 9 substantive failures across 4 of 5 judged cases,
  recurring parameter kinds (confidence ×4 rows, invented IDs ×4, date
  windows ×3), concentrated in `create_case_ticket` (4/9) and the reporter
  (6/9). Values recur literally across runs and cases: `0.95` twice in this
  run and in two prior runs; the date pair `2026-08-06T00:00:00Z`/
  `2026-09-05T23:59:59Z` identical in two prior canaries and this run's c1;
  2023-styled fabricated IDs/dates recur across runs and cases — case-5
  specifically in the NO-GO (`:145`), retry-active (`:137`/`:145`) and clean
  runs, case-1 in the final validation (`:177`). Not per-run-universal: in
  the final validation case-5's ticket was 2026-styled (`C-1005-20260905`)
  with only its date window flagged (`:129`); the sequential run's case-5
  died mid-case (task-failure, no ticket); GLM verify-run-2's case-5 judge
  rows are unpreserved.
- **Not a single-tool or single-case artifact either.** Three tools and both
  tool-owning components are involved; the only case with zero substantive
  TP failures (c3 has 2) is c2 — which was never substantively judged.
- **Judge-side strictness is itself measured-variable within this run:**
  c4's date parameters passed as "logical inferences" while c1/c3/c5's
  same-kind values failed; c4's `case_id` "C-1004-20260905" (an
  agent-composed value of the same family as c5's flagged "C-1005-20230901")
  was not flagged.
- One c1 fabrication event propagated across two calls (the same invented IDs
  in `draft_correction` and `create_case_ticket`).

**Assessment (OBSERVED, single run):** a recurring, structured pattern
spanning cases and runs — a mixture of genuine invented-value findings
(2023-dated IDs/dates contradicting tool results) and judge-visibility
artifacts on instructed or relayed values (default date window; classifier
confidence). No rate, trend, or cause is asserted beyond this run's evidence.

---

## 5. Claim classification and verification provenance

| # | Claim | Class | Provenance |
|---|---|---|---|
| 1 | Case-4 clean-run root_cause `MANUAL_OVERRIDE`, match, EXEMPLARY | MEASURED | Re-verified: `eval-rows.json` row 2 (raw JSON read in this task) |
| 2 | Case-4 confidence 0.95 | MEASURED | Re-verified: `runtime/tickets.jsonl:58` (raw read) + judge row quoting 0.95 |
| 3 | Classifier raw emission not persisted | MEASURED (negative) | Exhaustive check of evidence tree + `run.log` grep (0 hits) |
| 4 | Expected label `MANUAL_OVERRIDE` | MEASURED | `evals/cases.py:123` (read in this task) |
| 5 | Case-4 historical timeline incl. single UNKNOWN @ 0.32, parse-death, 3 archived passes | MEASURED/DOCUMENTED | Delegate sweep of raw artifacts (eval-rows/report.json/tickets per row); key rows re-verified verbatim by a second independent pass (§1b quotes) |
| 6 | "Twice previously UNKNOWN" premise unsupported | MEASURED | Follows from row 5 enumeration |
| 7 | Cause of 08:33Z→clean change | UNKNOWN | Stated as open question |
| 8 | TP census 31/21/9+1; figure 9 confirmed | MEASURED/CALCULATED | Recomputed from all five `eval-rows.json` + `analysis-digest.json` in this task |
| 9 | 9-row breakdown incl. tools/components/rationales | MEASURED + CALCULATED (component/tool mapping via code wiring; params via tool signatures `tools/transactions.py:17,40`, `tools/case_management.py:88,114`) | This task |
| 10 | Actual values (tickets/drafts IDs, confidences, case_ids) | MEASURED | `runtime/tickets.jsonl:55-59`, `runtime/drafts.jsonl:35` (raw reads) |
| 11 | Correction-canary precedent (dates + confidence) | MEASURED | Raw `eval-rows.json:121/:145` + report `:101` — verbatim re-verified in this task |
| 12 | 7-of-8 leak-active recurrence; cross-run rates (~12.4% pooled vs 30%) | DOCUMENTED | Prior-run artifacts (paths in §2b/§2c, two sweeps agree); rate table quoted from pre-existing audit, not re-derived |
| 13 | Leak mechanism, fix boundary, judge-input anatomy | MEASURED/PROVEN-BY-CODE | `evals/run_evals.py:83-98,117`, `trace_extractor.py:110-157`, evaluator/rubric files (read in this task); leak-audit quotes DOCUMENTED |
| 14 | Verdict flip on confidence 0.95 (leak PASS → clean FAIL) | OBSERVED | Both rows verbatim (retry-active `:176`; clean c4) |
| 15 | Leak's only judge-side effect direction = leniency | DOCUMENTED + OBSERVED | Mechanism quotes §3.2; no counter-example found in any sweep |
| 16 | Whether leak removal raised the fabrication rate | UNKNOWN | Single run |
| 17 | Instructed-window / relayed-confidence judge-visibility artifacts | MEASURED (code) + OBSERVED (verdicts) | Detector prompt `:21-22`; classifier prompt; extractor root-span mechanics |

Distinguishing re-verification from quotation: items 1–4, 6–11, 13–14, 17
were re-verified against raw artifacts in this task (directly or via verbatim
quote re-verification with exact line numbers); items 5 (per-run details
beyond the quoted rows), 12 and 15 are quoted from existing reports/sweeps
with citations, as tagged.

---

## 6. Zero-modification confirmation

- `git status --porcelain` before vs after this task: **identical**, with the
  single sanctioned exception of this new untracked file
  (`docs/case4-and-toolparam-fabrication-reverification-2026-09-05.md`).
  Before-snapshot captured at task start (HEAD `e6770b5`, 5 modified tracked
  files, untracked set as found); after-snapshot diffed against it.
- No test, benchmark, canary, or eval executed; no live LLM/API call made; no
  configuration change; nothing committed, staged, or pushed (verified:
  `git diff --cached` empty, HEAD unchanged).
- Files read include gitignored runtime stores (`runtime/tickets.jsonl`,
  `runtime/drafts.jsonl`) — read-only; their mtimes/contents unchanged by
  this task. No secrets were printed or copied; evidence handled is
  metadata/judge text only.

---

## Appendix A. Relation to the pre-existing audit (`docs/case4-outcome-and-toolparam-fabrication-audit-2026-09-05.md`)

This task's independent extraction **agrees** with that file on every core
fact re-derived here: case-4 `MANUAL_OVERRIDE` @ 0.95 EXEMPLARY 18/19
(first leak-free pass; 3 archived prior passes + 1 ticket-store-only); the
"twice UNKNOWN" premise unsupported; TP census 31/21/9 substantive + 1
judge-error; the 9-row composition (tools 4/3/2, components 6/3); the
correction-canary precedent; structural leak-independence with the
leniency-only pre-fix channel.

Discrepancies found in that file (flagged, not fixed — it was not modified):

1. Internal contradiction on pass count: §1c "at least the FIFTH pass on
   record overall" vs §5 "4th pass overall" (reconcilable only by silently
   toggling the timing-inferred ticket-store pass in/out of the count).
   This report states both counts explicitly instead (§1c).
2. Off-by-one row references inside its §1c ("row 5"/"row 4" vs its own §1b
   table's row 6/row 5).
3. Header says "this file is the only artifact created" while §6 discloses a
   second write (`\/tmp\/git-status-before-followup.txt`).
4. Its quote of the retry-active judge's "a reasonable inference/estimate"
   (audit `:192-194`) carries no inline citation at the quote site; the
   underlying artifact line is
   `groq-retry-active-5case-validation-2026-09-05/case-04-.../eval-rows.json:176`
   (a path that file does cite elsewhere, e.g. `:168`, including the
   root_cause-excused-via-"seed scenario" observation this report's §3.2
   quotes).

An earlier draft of this appendix additionally claimed the audit "does not
note that the same row also excused root_cause via the leaked label"; that
claim was wrong (its §2b row 6 notes exactly that) and was removed during
this report's adversarial review pass.

END OF REPORT
