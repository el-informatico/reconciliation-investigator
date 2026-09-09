# Evaluation & results — the honest summary
> AMENDED 2026-09-07: this report references the agent-memory/ directory, which was removed from repository history by the 2026-09-07 excision rewrite; those artifacts are retained only in the author's private local archive, never in this repository.

**As of 2026-09-06.** This document summarizes what has and has not been
measured for Reconciliation Investigator. Every figure below is quoted from
a cited source report and carries a classification tag, with one standing
exception introduced by the 2026-09-06 correction pass: §9's offline-suite
count is re-executed directly whenever the suite changes (most recently
2026-09-09). Results exist and are cited; gaps are named as gaps.
(DOCUMENTED throughout — the cited source is the authority.)

## 0. How to read this document

Claim-classification legend (same scheme as the source reports):

- **MEASURED** — directly measured in the cited report's run or task (the
  source chain's definition: verified against the run's artifacts by that
  task; not re-derived here).
- **CALCULATED** — arithmetic over measured values.
- **OBSERVED** — directly seen in repository files/artifacts.
- **DOCUMENTED** — stated in the project's own reports; accepted, not re-derived here.
- **PROJECTED** — forward-looking estimate. (None are made in this document.)
- **UNKNOWN** — not verifiable / not yet measured.

Citation rules used here (both inherited from the source chain):

- For case-4 / tool-parameter questions, the authority is
  `docs/case4-toolparam-evidence-index-2026-09-05.md` (the index), which routes
  to `docs/case4-and-toolparam-fabrication-reverification-2026-09-05.md`
  (authoritative reverification; the earlier audit
  `docs/case4-outcome-and-toolparam-fabrication-audit-2026-09-05.md` carries a
  SUPERSEDED notice routing to it). (OBSERVED)
- Evidence is cited by evidence **directory name** under
  `agent-memory/evidence/`, never by internal run-id: four directories share
  the internal run-id `gemini-judge-5-case-2026-09-04` and they are **not the
  same run** (`docs/case4-toolparam-evidence-index-2026-09-05.md` §3).
  (OBSERVED)

## 1. Headline figures

| Figure | Value | Classification | Source |
|---|---|---|---|
| Root-cause accuracy (clean run) | **4/5 = 80.0% — one OBSERVED data point, not a rate** | OBSERVED | `docs/clean-5case-validation-2026-09-05.md` §4 |
| Eval-row pass rate (raw) | 67/81 = 82.7% | CALCULATED | same, headline table |
| Eval-row pass rate (judgeable, excl. 3 judge-error rows) | 67/78 = 85.9% | CALCULATED | same, headline table |
| Judged coverage | 78/81 = 96.3% | CALCULATED | same, §14 |
| Safe-action compliance (segregation of duties) | 5/5 safe | MEASURED | same, §10 |
| Retry: clean run | 1 `Parsing failed` → retryable → retried → recovered; 0 exhausted | MEASURED | same, §3/§8 |
| Retry: retry-active run | 2/2/2/0 (events/retries/recoveries/exhausted) | MEASURED | `docs/groq-retry-active-5case-validation-2026-09-05.md` §6/§8 |
| Tool-parameter fabrication failures | 9 of 31 ToolParameterAccuracy rows | MEASURED | index §2; clean doc §10 |

## 2. Evaluation setup (what produced these numbers)

- **Cases:** 5 synthetic discrepancy scenarios, frozen in
  `data/seed_transactions.json` (served via `EVAL_MODE=1`; the tools read seed
  data, not real systems). Case definitions in `evals/cases.py`. (OBSERVED)
- **Agents:** Groq `openai/gpt-oss-120b` (detector/investigator, classifier,
  reporter), `GROQ_API_KEY` only. (DOCUMENTED, both run reports)
- **Judges:** native Strands `GeminiModel`, `gemini-3.1-flash-lite`,
  `GEMINI_API_KEY` only, 4.3 s module-global pacer; four LLM judges
  (trajectory, output/root-cause, tool-selection, tool-parameter) plus the
  deterministic `SafeActionComplianceEvaluator` (no model). (DOCUMENTED, both
  run reports)
- **Retry:** `GroqParsingFailedRetryStrategy` (`agents/retry.py`) active in all
  three agent builders in both cited runs. (DOCUMENTED, both run reports)
- **Command** (LIVE — real Groq + Gemini API calls):
  `uv run --frozen --with google-genai==2.22.0 python -m evals.gemini_judge_5case`
  (OBSERVED — the module's own blocked-path message,
  `evals/gemini_judge_5case.py:226-227`; recorded as executed — under
  `timeout 2400` and with an explicit `--out-dir` — in both source reports)
- **Evidence:** clean run → `agent-memory/evidence/clean-5case-validation-2026-09-05/`;
  retry run → `agent-memory/evidence/groq-retry-active-5case-validation-2026-09-05/`.
  (DOCUMENTED)

## 3. The clean baseline — first leak-free run

**Root-cause accuracy: 4/5 = 80.0% (one OBSERVED data point, not a rate).**
(`docs/clean-5case-validation-2026-09-05.md` §4 — the report's own words.)

- The single miss is named plainly: **case 2 (`duplicate-transaction`)**,
  expected `DUPLICATE_TRANSACTION`, produced `UNKNOWN` — the judge noted "the
  model explicitly stated that it lacked the evidence required to make an
  informed decision". (MEASURED, same §4)
- This was the first run executed after the ground-truth-leak fix (§6 below);
  the report frames it as a **new baseline, not a replication**, and its §14
  limitation is explicit: "One OBSERVED data point per metric … None of these
  is an established rate; a stable accuracy estimate requires repeated clean
  runs." (DOCUMENTED)
- Application-quality failures in the run: 11 total — 1 root-cause miss
  (case 2), 1 tool-selection failure (case 2), and 9 tool-parameter failures
  (§5 below). (MEASURED, §10)
- Also in this run: 1 Groq in-stream `Parsing failed` event (case 4,
  detector), classified retryable by the narrow matcher, retried once,
  **recovered** (+1,112 tokens for the recovery attempt); 2 throttles,
  recovered; 0 exhausted. (MEASURED, §3/§8/§10)
- 3 of 81 rows could not be judged (Gemini 503s). (MEASURED, §14)

## 4. Retry resilience — a distinct axis, unaffected by the leak

This evidence measures **infrastructure resilience**, not classification
accuracy, and the leak audit ruled it structurally unrelated: "These measure
provider-side in-stream output-parse rejections and the retry strategy's
recovery (`agents/retry.py`), triggered by emission format, not by
classification correctness … **safe to cite as-is**."
(`docs/eval-ground-truth-leak-audit-2026-09-05.md` §5) (DOCUMENTED)

- **Retry-active run** (`docs/groq-retry-active-5case-validation-2026-09-05.md`,
  evidence `agent-memory/evidence/groq-retry-active-5case-validation-2026-09-05/`):
  5/5 cases rc=0; **2** `Parsing failed` events, both classified retryable by
  the narrow matcher, both retried once, both **recovered**; **0** exhausted;
  3,766 additional-attempt tokens. (MEASURED, §5/§6/§8)
- **Clean run** (source as §3 above): **1** event, retried, recovered,
  0 exhausted. (MEASURED, §3/§8)
- Honest caveats (carried from the retry report's own §14/§15): recovery is
  live-proven only in the single-attempt form — **exhaustion and multi-attempt
  ladders remain offline-proven only**; parse-failure counts are n-of-this-run
  counts, not probabilities. Absolute token totals were measured on runs whose
  prompts still carried the leak, so totals will shift; the retry counts and
  outcomes are facts about infrastructure either way. (DOCUMENTED)

## 5. Known limitation: tool-parameter fabrication (open issue, not minimized)

**9 of 31 ToolParameterAccuracy rows failed on a recurring fabrication
pattern** (30 substantively judged: 21 pass / 9 fail; the 10th non-pass row is
case-2's Gemini-503 judge-error, no tool judged). (MEASURED — census recomputed
twice per the reports; index §2 row 2)

Composition (index §2 / reverification §2b): by tool — `create_case_ticket` 4,
`search_transactions` 3, `draft_correction` 2; by component — reporter 6,
detector 3, classifier 0 (structural — it has no tools); by parameter kind —
unsupported `confidence` values in 4 rows, invented transaction/event IDs in 4,
fabricated date windows in 3 (kinds overlap within rows). (CALCULATED —
reverification §2b aggregates over the MEASURED census)

- The recurring literal date pair
  `2026-08-06T00:00:00Z`/`2026-09-05T23:59:59Z` matches the detector's
  **instructed** "default window of the last 30 days"
  (`agents/detector_investigator.py:21-22`) — an instruction the judge cannot
  see. The reverification's own words: these facts "recontextualize
  composition (several rows are judge-visibility artifacts as much as agent
  invention); they do not change the census — the 9 verdicts are recorded as
  issued." (OBSERVED/DOCUMENTED)
- The pattern is **structurally independent of the ground-truth leak**: the
  ToolParameter judge reads only the trajectory (never `case.input` /
  `expected_output` / metadata); pre-fix, the label could reach this judge only
  transitively and only toward leniency; the 9 rows' content is disjoint from
  all label spellings; fabrication verdicts predate the fix in 7 of 8
  leak-active runs. (DOCUMENTED — reverification §2d, four-step argument;
  index §2 row 2 one-line condensation)
- Recurrence: fabrication-pattern verdicts exist in 7 of the 8 prior
  instrumented runs (the GLM sequential run is the exception). (DOCUMENTED)
- Open question, stated as such: **whether removing the leak raised the
  fabrication rate — UNKNOWN** (single clean run; heterogeneous denominators
  across runs). (UNKNOWN, per index standing-unknowns)

## 6. The ground-truth leak — discovery and fix (why older numbers are excluded)

Told as the engineering record tells it:

1. **What it was.** `evals/run_evals.py` injected the case's `seed_scenario`
   — the ground-truth root-cause label — verbatim into the task instruction;
   that instruction was the detector's user prompt, and the installed Strands
   SDK additionally forwarded it to the classifier and reporter as an
   "Original Task: …" prefix on every case. The line had existed unchanged
   since the first commit that created `evals/run_evals.py`, so **every
   benchmark run ever executed from this repository ran with the leak
   present**. (`docs/eval-ground-truth-leak-audit-2026-09-05.md` — answer and
   §2.1 quote the injection code.) (DOCUMENTED)
2. **How it was found.** A deliberate audit (direct source inspection +
   installed-SDK verification + git archaeology + artifact inventory), which
   confirmed the hypothesized detector-side injection **and found the reach
   was broader than hypothesized** (the SDK's prefix carried the label to the
   classifier and reporter too). Preserved judge `reason` fields corroborated
   it — e.g. a judge writing that the root cause "comes verbatim from the
   user's stated seed scenario". (DOCUMENTED, audit §1/§3)
3. **What was fixed** (`docs/eval-ground-truth-leak-fix-2026-09-05.md`):
   the label was removed from the instruction (`build_instruction`); a
   `strip_seed_annotations` wrapper closed the latent `_comment` channel at
   all four read tools; one rubric line stopped referencing case metadata the
   judge never received. Verified by 18 new tests; the offline suite went
   132 → 150 passed, zero regressions. The fix changes methodology
   **going forward only**. (DOCUMENTED)
4. **The ruling this document enforces.** Every root-cause-dependent accuracy
   figure produced before the fix is **MEASURED but methodologically
   contaminated — an upper bound on capability, not evidence of accuracy**,
   and is not cited as accuracy evidence anywhere in this repo's
   submission-facing documents. Historical figures may appear only in this
   clearly-labeled methodology narrative. (DOCUMENTED — the fix doc's §6
   list and the audit's §7 table are the canonical enumerations.)

The contaminated figures, each with its original context (all DOCUMENTED in
audit §4/§7 and fix doc §6):

| Figure | Original context |
|---|---|
| 89.8% (44/49) | 2026-09-05 gemini-groq final validation run (the case-4 UNKNOWN run) |
| 93.0% (66/71) | 2026-09-05 retry-active 5-case run (its retry figures remain valid — §4 above) |
| 85.07% (57/67) | 2026-09-04 sequential-driver run, GLM era |
| 68% and 16% | 2026-09-04 Experiment-driver verify.sh step-6 runs |
| 0.00% | bootstrap-era Experiment run (all rows failed by design; carries no accuracy signal either way) |
| GLM "20/20" | GLM-era case-4 run — the figure itself is wrong (actual: 19 rows / 19 passes; "20/20" is structurally impossible for the sequential driver); contaminated regardless |
| 12/15, 18/19, 13/15, 14/15 | canary aggregates (token, Gemini-judge, correction-draft-id, retry canaries) |

Explicitly **not** contaminated (audit §7): SafeActionCompliance
`apply_correction`-clause results (structural immunity — the evaluator's
other clause, "no unnecessary draft on the correction-free case", is
partially exposed and stands as an upper bound), case-completion / rc=0
counts (completion facts — not to be presented as accuracy),
retry/OTel/infrastructure-token figures.

## 7. Case-4 record (settling a recurring misstatement)

- Exactly **ONE** UNKNOWN outcome is on record for case 4 across all runs (the
  2026-09-05 08:33Z run); the "twice previously UNKNOWN" premise is refuted
  by the artifacts (the other pre-clean non-pass emitted no verdict at all —
  a detector parse-death). (DOCUMENTED — reverification §1c, index §2 row 1)
- In the clean run, case 4 **PASSED**: root cause `MANUAL_OVERRIDE` (match),
  confidence 0.95, OutputEvaluator score 1.0 ("EXEMPLARY"), 18 of 19 case
  rows —
  the first leak-free case-4 pass, and the 4th archived pass overall (5th
  counting a ticket-store-only pass). Why the earlier run's UNKNOWN flipped to
  a pass is an explicitly open question. (DOCUMENTED; UNKNOWN for the flip
  cause)

## 8. What remains unfinished (explicit, not implied)

1. **The end-to-end human-approval demo surface (P0-C): BUILT (2026-09-05/06;
   this entry originally read "NOT built").** The human gate, capability
   tokens, and correction executor are implemented and tested at the code
   level (HMAC-SHA256-signed, case/field/value-scoped, expiring (600 s
   default TTL), single-use tokens with a persisted consumption ledger and an
   audit trail), and two minimal surfaces now sit on top of the same
   deterministic gate (`orchestrator/human_gate.py`): `approval/cli.py`, a
   single-case interactive terminal flow (`python -m approval.cli`), and
   `approval/web.py`, a one-page loopback-only browser screen
   (`python -m approval.web`: default bind `127.0.0.1`, `::1` also accepted,
   every other `--bind` refused; stdlib `http.server`, no framework, no
   JavaScript, in-memory session state). Neither surface holds authority of
   its own — both render the case + proposed correction and turn
   APPROVE/REJECT into a `GateDecision` for the gate. Live validation on
   record: **CLI** — case C-1004 with a live Groq investigation through
   gate → token → executor → single-use replay refusal → 5/5 negative
   token matrix, the approval itself made in the labeled scripted
   `--non-interactive` mode (interactive prompt path unit-tested, not
   live-human-tested) (`docs/human-gate-e2e-validation-2026-09-05.md` §7/§10);
   **web** — real headless Chromium via Playwright over `[::1]:8765` with
   real form submissions (19/19 checks; deterministically seeded case, zero
   LLM calls) plus Windows-side headless Edge/Chrome rendering and a scripted
   HTTP APPROVE + replay refusal against the committed default bind
   (`docs/approval-web-loopback-fix-and-validation-2026-09-06.md` §4/§10).
   Demo scope unchanged and stated, not silent: single-case surface;
   approver identity unauthenticated by design (a free string); multi-case
   queue management and audit search out of scope per
   `docs/build-contract.md` §2.4 — which prescribes exactly this minimum
   interface, so this entry's earlier "§2.4 deferral" attribution was wrong
   (§2.4 defers auth/queue/search, not the surface); the spine is
   EVAL_MODE-only (dev signing key public by design; production requires
   `CORRECTION_TOKEN_SECRET`); headed interactive browser use untested.
   (OBSERVED — code, README approval section, and the two validation
   reports; "P0-C" is submission-roadmap nomenclature)
2. **Architecture-diagram artifact (required by the hackathon rules):
   CREATED (2026-09-06; this entry originally read "NOT created").** Lives
   at `docs/architecture-diagram-2026-09-06.md` — comprehensive diagram of
   the agent graph, human gate, capability token, and execution path, with
   an accuracy map (element → code anchor) and rendered SVG/PNG exports;
   embedded in the README and pinned byte-identical there by
   `tests/test_architecture_diagram_sync.py`. (OBSERVED)
3. **Demo video: NOT recorded.** No recording, storyboard, or demo footage
   exists (the repo's only screenshots are 2026-09-06 approval-UI validation
   artifacts under `agent-memory/evidence/`, not demo material); a text
   shot-list draft lives in `docs/DEVPOST-DRAFT.md`. (OBSERVED)
4. Accuracy is one data point per metric (§3); **repeated clean runs** are
   needed before any figure is called a rate. (DOCUMENTED)
5. Retry **exhaustion/multi-attempt** behavior is offline-proven only (§4).
   (DOCUMENTED)
6. The tool-parameter fabrication pattern (§5) is an open remediation item.
   (DOCUMENTED)
7. The repository is currently **PRIVATE** (`el-informatico/reconciliation-investigator`);
   making it public for submission is a pending human decision. (OBSERVED)

## 9. Offline test suite

Most recent count on record: **258 passed** (offline suite re-executed
2026-09-09, `uv run --locked pytest -q`).
Lineage: 132 → 150 with the leak fix's 18 new tests
(`docs/eval-ground-truth-leak-fix-2026-09-05.md` §5) → 155 (clean-run
task, `docs/clean-5case-validation-2026-09-05.md` §1d) → 190 (human-gate
task, `docs/human-gate-e2e-validation-2026-09-05.md` §8) → 216
(rejected-call diagnostics + loopback web tests,
`docs/draft-rejection-diagnostics-2026-09-06.md` §7) → 217
(approver-attribution regression test, `docs/p0c-closeout-2026-09-06.md`
§5) → 218 (+ the diagram-sync test) → 251 (+ the 33 sensitive-content
guard regression tests, `tests/test_sensitive_content_guards.py`, the
guard-hardening commit) → 257 (+ the 6 probe env-tag choice tests,
`tests/test_probe_groq_env_tag_choices.py`, the env-tag rename
commit) → 258 (+ the README offline-test-count pin test,
`tests/test_readme_test_count.py`, the README test-count drift fix —
the README's "22 offline test files" figure is now enforced by that
test). (258 MEASURED 2026-09-09; lineage DOCUMENTED per the cited
docs)

## 10. Source map

| Source | Role |
|---|---|
| `docs/case4-toolparam-evidence-index-2026-09-05.md` | authoritative index for case-4 / tool-parameter findings |
| `docs/case4-and-toolparam-fabrication-reverification-2026-09-05.md` | authoritative reverification (census, leak-independence argument, case-4 record) |
| `docs/clean-5case-validation-2026-09-05.md` | the clean baseline run (accuracy, row rates, per-evaluator census, in-run retry event) |
| `docs/groq-retry-active-5case-validation-2026-09-05.md` | retry-resilience run (2/2/2/0) |
| `docs/eval-ground-truth-leak-audit-2026-09-05.md` | leak mechanism, reach, contamination rulings |
| `docs/eval-ground-truth-leak-fix-2026-09-05.md` | the fix and its verification; contaminated-figure list |
| `agent-memory/evidence/clean-5case-validation-2026-09-05/` | clean-run evidence (cite by directory) |
| `agent-memory/evidence/groq-retry-active-5case-validation-2026-09-05/` | retry-run evidence (cite by directory) |
