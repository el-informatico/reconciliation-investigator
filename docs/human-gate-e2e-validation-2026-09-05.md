# Human Gate End-to-End Validation — 2026-09-05

Task: P0 human gate integrity + minimal demo surface (human-commissioned;
architect-gated Tier C, PROCEED-WITH-CONDITIONS C1–C9, gate evidence in
`agent-memory/human-gate-task-plan-2026-09-05.md`). This report records
what was implemented and what was actually verified. Every load-bearing
claim is tagged MEASURED (a test/run produced the number) / CALCULATED
(derived from measured values) / OBSERVED (raw artifact inspected) /
DOCUMENTED (a prior report asserts it; spot-checked where cited) /
PROJECTED (expectation, not evidence) / UNKNOWN.

Placeholder markers `<<...>>` below are filled only when the
corresponding evidence exists; they are never left in a claim.

## 1. Objective

Make the human authorization boundary a working, validated end-to-end
product experience: deterministic case identity, strict correction-draft
hygiene, an explicit human approval surface driving the EXISTING
deterministic gate, one real end-to-end approval execution on a safe
synthetic case, and a real replay attempt that is mechanically rejected.

Demo sequence demonstrated: INVESTIGATE → PROPOSE → HUMAN APPROVE →
EXECUTE → AUDIT → REPLAY ATTEMPT → REJECTED.

## 2. Implementation changes (all DELIBERATE, architect-gated C1–C9)

| File | Change |
|---|---|
| `tools/seed_data.py` | Added `canonical_case_id()`, `modern_status_values()`, `validate_correction_value()` (deterministic identity + value contract; whitelist follows the frozen seed). |
| `tools/case_management.py` | `draft_correction` and `create_case_ticket` now validate deterministically at creation time (see §3/§4); added `get_draft()`/`get_ticket()` read helpers. Tool signatures and returns unchanged (contract §3). |
| `orchestrator/human_gate.py` | (C1 scope lock) Added `ticket_for_draft()`; APPROVE of a structurally invalid draft is now an audited refusal (`gate_approval_refused`, draft → `rejected`, no token, never a crash — previously an uncaught `ValueError` at `human_gate.py:77`). |
| `orchestrator/correction_executor.py` | (C1 scope lock) `_fail` is terminal-state-aware: a replay/late failure never downgrades a `resolved`/`applied`/`rejected` record; the failure is always audited. |
| `orchestrator/graph.py` | Extracted `apply_gate_approval()` — the single APPROVE→execute composition, shared by `run_case_with_gate` and the approval surface; `run_case_with_gate` canonicalizes `case_id` at entry (invented spellings raise before any graph invocation); approver flows from the `GateDecision`. |
| `approval/` (NEW package) | `approval/cli.py` (terminal approval flow; `--non-interactive` scripted validation mode; `--demo` replay + negative matrix) and `approval/web.py` (loopback-only stdlib single-case approval screen). Zero new dependencies. The surface constructs only `GateDecision` and calls the existing spine. |
| `tests/` | New regression files (identity/hygiene, replay/linkage) + deliberate fixture updates in `tests/test_gate_executor.py` and `tests/test_tools.py` (see §8). |
| `README.md` | Approval-surface scoping note updated per §2.4 (surface exists; auth/multi-case queue/audit search explicitly out of scope). |
| NOT changed | `evals/run_evals.py` (leak fix untouched), `tests/test_eval_ground_truth_leak.py`, `agents/*` prompts (contract-verbatim), `data/seed_transactions.json`, `docs/build-contract.md`, provider config, `runtime/` historical records (preserved evidence; validation applies to new writes only). |

## 3. Case identity model (Phase 2)

One investigated customer = one case = the `customer_id` itself,
validated against the frozen seed by `canonical_case_id()` — never a
model-chosen string. MEASURED motivation (OBSERVED in `runtime/
tickets.jsonl`): 44 distinct LLM-invented `case_id` spellings across 59
live tickets made the gate's dual lookup (draft `customer_id` == ticket
`case_id`) unsatisfiable for 43/44; 11 tickets carried placeholder draft
links (`"None"`×8, `"null"`×1, `""`×2).

Enforcement: `create_case_ticket` rejects any `case_id` that is not
exactly the canonical customer id (error names the canonical value);
`correction_draft_id` must be `None` or a REAL draft of the SAME case;
`draft_correction` canonicalizes its `customer_id`;
`run_case_with_gate` canonicalizes at entry; gate/executor lookups
(`ticket_for_draft`, `latest_pending_draft`, `latest_ticket`) operate on
canonical ids only.

## 4. Correction validation model (Phase 3)

Deterministic whitelist derived from the actual domain model (modern
system of record only; the legacy system has no write path):

- Fields: exactly `balance`, `status` (`MODERN_FIELDS`, seed_data.py).
  The three observed live non-canonical names — `legacy_deposit_amount`,
  `transaction_amount (L-TXN-90301)`,
  `deposit_amount (transaction MTXN-20230901-002)` — are
  invalid-and-must-be-rejected (verdict per task Phase 3); NO aliases
  are mapped (OBSERVED: those were the live artifacts; the canonical
  schema has no such fields).
- Values: `balance` = JSON number or a string that is exactly a plain
  decimal number → canonicalized to float (the live reporter emits
  strings — "1500.00" style — so strict-numeric strings are mapped
  deterministically; prose and booleans are REJECTED);
  `status` = the seed's closed enum (`ACTIVE`, `SUSPENDED`),
  case-insensitive → canonicalized to upper.
- Coherence: `current_value` must equal the LIVE modern-system value
  (read-your-writes overlay included); `proposed == current` (no-op) is
  rejected.
- Rejection is always a deterministic `ValueError` naming the problem —
  never silent coercion into an executable mutation. Defense-in-depth:
  the gate refuses (audited) any structurally invalid draft that
  predates these creation-time checks.

Reporter-behavior note (C8): the reporter now receives deterministic
errors for malformed drafts/tickets instead of silent acceptance. This
is product-level strictness commissioned by the task; it does not touch
`evals/run_evals.py`, judges, or methodology. Any future benchmark run
must be compared with this change in mind. The historically measured
4/5 clean-run result predates this change (DOCUMENTED,
`docs/clean-5case-validation-2026-09-05.md`).

## 5. Phase 1 determination: "invalid field names" vs the 9/31 rows

PARTIALLY OVERLAPPING — two distinct defect classes (HIGH confidence,
forensic agent evidence, spot-verified by the architect):

- X = invalid draft field NAMES (schema membership). Reporter-only;
  judge-INVISIBLE — X's instances PASSED ToolParameterAccuracy in their
  own runs (no judge row scores field-name canonicity).
- Y = the clean run's 9/31 ToolParameterAccuracy failures = fabricated
  VALUES (traceability): reporter 6 rows + detector 3 rows; occurs with
  canonical field keys too.
- Intersection: reporter component + C-1005 family + exactly ONE shared
  artifact (clean-run draft `DRF-29a27ee0a64f` = `runtime/drafts.jsonl`
  line 36 = judge row c5-14 — a non-canonical field name carrying the
  fabricated `MTXN-20230901-002` id).
- The fabricated DATE-parameter pattern is DETECTOR-side (instructed
  30-day default window) → NOT the same issue; out of Phase 3 scope.
  A date FORMAT whitelist would not fix well-formed-but-wrong dates and
  would alter detector behavior measured by evals — boundary respected,
  not changed here.

Implication applied: draft hygiene (this task) fixes X at creation time;
Y's case_id portion is fixed by deterministic identity (§3); Y's
fabricated evidence-ID-in-prose portion (justification/summary/evidence
_refs) is deterministically checkable against seed ids in principle but
is NOT implemented here — it changes eval-measured reporter behavior
beyond the commissioned scope and is recorded as a candidate next step.

## 6. Approval flow (Phase 4) and capability-token properties

Flow: INVESTIGATE (graph) → PROPOSE (validated draft + linked ticket) →
HUMAN SEES (CLI renders case file + draft; web screen renders the case
card: case id, ticket summary/root cause/confidence/evidence refs,
field, current → proposed, justification, status) → HUMAN DECIDES
(APPROVE/REJECT forms/keys → `GateDecision`) → GATE
(`run_human_gate`: audits every decision; on APPROVE issues the token) →
EXECUTOR (`apply_gate_approval` → `execute_correction`: validates
authorization BEFORE mutation) → `apply_correction` (plain function,
modern-system override store) → AUDIT → REPLAY REJECTED (single-use
JTI). The surface holds zero authority: no token issuance/validation
logic, no import of the write tool, loopback-only web server, no
authentication (§2.4 demo scope — explicit README note).

Token properties (unchanged spine, MEASURED by the existing matrix +
new tests): HMAC-SHA256 over canonical JSON `{case_id, field,
new_value, exp, jti}`; scoped to exact case + field + exact typed value;
TTL 600 s default (expiry enforced); single-use via `jti` in
`runtime/consumed_tokens.jsonl`; constant-time signature comparison;
malformed/forged/tampered/expired/wrong-scope/consumed all rejected
deterministically. EVAL_MODE signs with a committed, deliberately
non-secret dev key; production requires `CORRECTION_TOKEN_SECRET`
(never defaulted, never committed).

## 7. End-to-end validation (Phase 5) — SAFE SYNTHETIC ONLY

Setup: single seeded case, isolated `--runtime-dir` store, EVAL_MODE=1,
live Groq investigation via `run_case_with_gate` (NOT the 5-case
benchmark; NOT the retry canary — both closed). Approval in the scripted
`--non-interactive` validation mode (explicitly labeled scripted
approval by the authorized validation run; the interactive path is
unit-tested with faked stdin). Replay and the negative matrix
(wrong-case / wrong-field / wrong-value / expired / malformed tokens)
attempted after execution, without weakening any check.

Evidence: `agent-memory/evidence/human-gate-e2e-2026-09-06/` (task
started 2026-09-05; the live run crossed local midnight and executed
2026-09-06T05:11–05:16Z — the report filename keeps the task date).

### Attempt 1 (2026-09-06T05:11Z) — FAILED at the drafting stage (kept, unhidden)

Command: `uv run --locked python -m approval.cli --customer C-1004 --demo
--non-interactive --decision approve --approver validation-run-2026-09-06
--runtime-dir agent-memory/evidence/human-gate-e2e-2026-09-06/runtime`.
OBSERVED: the graph completed and the reporter ticketed correctly —
ticket `TCK-acb8c6f96e35`, case_id `C-1004` (CANONICAL — no invented
spelling), root_cause MANUAL_OVERRIDE @ 0.94, `correction_draft_id: null`
(proper JSON null) — but NO draft reached the gate
(`drafts.jsonl` never created): the CLI exited with
"the gate refused the flow: cannot approve: no pending correction draft".
Rejected draft attempts leave no record (validation precedes the append),
so WHICH malformed call the reporter made is UNKNOWN; one Groq
"Parsing failed" event occurred and was recovered by the closed retry
strategy (OBSERVED in the console log — the canary itself was NOT rerun).
Attempt 1's ticket remains `open` in the store — correct behavior.

### Attempt 2 (2026-09-06T05:15Z, after adding gate-input visibility to the scripted decider) — FULL SUCCESS (MEASURED)

Same command, `--approver validation-run-2026-09-06-attempt2`; console:
`live-run-attempt2-console.txt`. Zero "Parsing failed" events.

1. INVESTIGATE (live Groq): verdict `MANUAL_OVERRIDE` confidence 0.92 —
   the third consecutive correct live classification of C-1004
   (0.95 clean run, 0.94 attempt 1, 0.92 attempt 2; DOCUMENTED + OBSERVED).
2. PROPOSE: draft `DRF-8b0699623aab` — canonical and coherent:
   `{customer_id: "C-1004", field: "status", current_value: "ACTIVE",
   proposed_value: "SUSPENDED"}` with a justification citing the REAL
   seed event `EVT-L-40041` (manual override, suspected fraud).
   Ticket `TCK-e3fbdea87443` links the draft; case_id canonical.
3. HUMAN APPROVE (scripted, labeled): gate issued the capability.
4. EXECUTE (deterministic): `status=applied`, `before=ACTIVE`,
   `after=SUSPENDED`, `no_op=False`, audit `AUD-3413b18b91d3`.
5. AUDIT (MEASURED, `runtime/audit_log.jsonl` in the evidence dir):
   `gate_approval` (approver recorded) → `correction_applied`
   (case/field/before/after/ticket/draft linked) → `correction_failed`
   for the replay with the exact error below. `consumed_tokens.jsonl`
   holds exactly ONE jti (the replay did not double-append). Ticket
   `resolved` + `audit_entry_id`; draft `applied`; attempt 1's older
   null-linked ticket left `open` — live proof of linked-vs-latest
   ticket resolution. `overrides.json`: modern C-1004 status SUSPENDED;
   `data/seed_transactions.json` byte-identical (git diff empty).
6. REPLAY ATTEMPT: same token, same arguments through the executor →
   `status=failed`, exact error
   `token validation failed: token already consumed (single-use)`;
   post-replay integrity: ticket still `resolved`, draft still
   `applied` (terminal-state-aware `_fail`).
7. NEGATIVE MATRIX (validate, consume=False — the spine's own answers):
   different-case REJECTED (token scoped to case 'C-1001') /
   wrong-field REJECTED (token scoped to field 'balance') /
   wrong-value REJECTED (different correction value) /
   expired REJECTED (token expired) / malformed REJECTED (malformed token).

Runtime isolation CONFIRMED: all writes landed in the evidence
`--runtime-dir`; the repo's own `runtime/` store was untouched
(its 36 drafts / 59 tickets / 2 jtis unchanged).

## 8. Tests (Phase 6)

Baseline before this task: 155 passed (MEASURED, Phase 0, and again
after the core edits with fixture updates: 155 passed).

Final (MEASURED): **190 passed** (155 baseline + 27 + 8; zero failures,
zero skips). New files: `tests/test_case_identity_and_hygiene.py` (17
tests: canonical identity round-trip/rejection incl. invented spellings;
draft value canonicalization incl. strict numeric strings; rejection of
the three live non-canonical field names, prose, booleans, out-of-enum
status, incoherent current_value, no-op; ticket identity/linkage
enforcement incl. garbage and cross-case draft links; get_draft/
get_ticket; legacy runtime records preserved as evidence),
`tests/test_gate_replay_and_linkage.py` (10 tests: exact-link ticket
resolution vs later unlinked; documented fallback for unknown ids; gate
refusal of an invalid legacy draft — audited, draft rejected, NO token,
no crash; executor replay-after-success without clobbering terminal
ticket/draft state; failed execute after REJECT never flips the rejected
ticket; wrong-case token at executor level leaves the target untouched;
status-correction end-to-end with overlay; apply_gate_approval resolves
the linked ticket; run_case_with_gate rejects non-canonical case_id
before any graph invocation), `tests/test_approval_surface.py` (8
socket-free tests: web render with/without draft, XSS escaping,
execution/replay cards; CLI unknown-customer exit 2; scripted-decider
honest labeling; interactive decider approve/quit via faked stdin;
result block reads back real store state).

verify.sh steps 1–5 (MEASURED, exact step commands, log in the evidence
dir; step 6 — the live benchmark — contractually EXCLUDED and not run):
preflight PASS (uv 0.12.9 / Python / git), segregation guard PASS +
pre-commit wiring OK (core.hooksPath=scripts/hooks, exec bit),
uv sync --locked clean, pytest 190 passed, PyPI freshness: all three
pins current (no drift).

Deliberate existing-test edits (C5, narrowing-to-honest, no assertion
deletions): `tests/test_gate_executor.py` `_draft_and_ticket` values
1500→1250 / 1250→1500 (the old pair asserted the legacy/modern swap the
coherence rule eliminates; live modern C-1001 balance is 1250.00) and
one `validate_approval_token` value 1250.00→1500.00 (the draft now
proposes the real correction); `tests/test_tools.py` draft values
aligned the same way, and the null-schema regression test's string
draft id now points at a REAL same-case draft (intent — required-but-
nullable schema, None accepted — unchanged).

## 9. Security invariants (status after this task)

| Invariant | Status | Evidence |
|---|---|---|
| No LLM tool may call `apply_correction` | HOLDS | unchanged tool lists (`tests/test_agents.py`); `approval/` contains zero references (grep); segregation guard PASS; `tests/test_tools.py` plain-function pin |
| `apply_correction` stays a plain deterministic Python function | HOLDS | untouched (C1); single non-test import site unchanged (executor) |
| Reporter may draft but never execute | HOLDS | reporter tools unchanged; drafts now validated harder at creation |
| Human approval mandatory before execution | HOLDS | unchanged spine; MEASURED live (execution only after the gate issued the token); no-token path still fails closed |
| Tokens cryptographically authenticated, scoped to case/field/value, expiring, single-use via JTI | HOLDS | unchanged spine; MEASURED live (replay refused; negative matrix 5/5 rejected) |
| Constant-time signature comparison | HOLDS | unchanged `hmac.compare_digest` |
| Executor validates authorization before mutation | HOLDS | unchanged order; replay attempt audited and refused with no second mutation |
| Mutation audit logged | HOLDS | MEASURED live: gate_approval → correction_applied → correction_failed (replay) chain in the evidence audit log |
| No frontend/UI bypass around the executor | HOLDS | surface constructs only `GateDecision`; single composition point `apply_gate_approval`; web screen loopback-only, no auth (stated demo scope) |
| No LLM-chosen capability scope or manufactured approval | HOLDS (strengthened) | capability is minted ONLY by the gate from the validated draft's own field/proposed_value; case identity canonical (this task) |
| No secret committed or exposed | HOLDS | `.env` never printed; EVAL_MODE key is a committed non-secret by design; production key never defaulted |

Deviations/notes: none of the above was weakened to make the demo pass;
the only spine behavior changes (audited approval refusal; terminal-
state-aware failure marking; draft/ticket creation-time validation)
tighten the boundary.

## 10. Limitations / not tested

- Human approval is EXPLICIT but UNAUTHENTICATED (demo scope, §2.4):
  `approver` is a free string; EVAL_MODE's signing key is public by
  design. Production strength requires `CORRECTION_TOKEN_SECRET` and an
  authenticated approver identity — both out of scope.
- The JTI store is an append-only file: single-use holds under
  single-writer conditions; concurrent multi-process replay races are
  UNKNOWN (demo conditions are single-writer).
- The web screen binds 127.0.0.1, has no auth/session/CSRF protection,
  and is for demo presentation only (per contract §2.4 minimum viable
  interface; multi-case queue, auth, audit search explicitly deferred).
  > AMENDED 2026-09-06: the screen also accepts `--bind ::1` (IPv6
  > loopback; committed default unchanged at 127.0.0.1) — same
  > loopback-only scope. See
  > docs/approval-web-loopback-fix-and-validation-2026-09-06.md.
- No real financial system exists in this stack (EVAL_MODE mock stores
  only); nothing here warrants a "financially safe" claim in any
  absolute sense.
- Not tested (deliberately, with reasons):
  - The web screen's HTTP layer in a real browser: this dev environment
    cannot reach loopback listeners from the shell (OBSERVED: a bare
    `python -m http.server` also times out), so `approval/web.py` is
    verified by socket-free render/delegation unit tests and code
    review only. Live-browser validation is a remaining step for the
    human on the demo machine.
    > SUPERSEDED 2026-09-06: the gap is closed — the root cause was
    > IPv4-loopback-only (WSL2 mirrored host; ::1 is healthy), and the
    > screen is now live-browser-validated (real Chromium over [::1],
    > 19/19 checks) with its HTTP layer test-covered. See
    > docs/approval-web-loopback-fix-and-validation-2026-09-06.md.
    > The Windows-side GUI-browser check of the default 127.0.0.1 bind
    > (curl-evidenced 200 OK) remains a human step.
    > AMENDED 2026-09-06 (P0-C closeout): automated Windows-side
    > validation of the default bind completed — real Windows Edge and
    > Chrome headless engines rendered the screen (DOM dumps + PNG
    > screenshots) and a native Windows client scripted the APPROVE
    > through the real deterministic gate (both audit rows carry the
    > custom approver). Only a headed interactive GUI click was not
    > exercised. See docs/approval-web-loopback-fix-and-validation-
    > 2026-09-06.md §10 and docs/p0c-closeout-2026-09-06.md.
  - The interactive CLI prompt against a live human (unit-tested with
    faked stdin; the live run used the labeled scripted mode).
  - Attempt 1's reporter-side draft failure is not diagnosable beyond
    "no draft call succeeded" (rejected attempts leave no record —
    validation precedes the append). UNKNOWN which call shape failed.
  - Concurrency: multi-process/multi-thread replay races on the JTI
    store (single-writer demo conditions only).
  - Production (non-EVAL_MODE) signing: `CORRECTION_TOKEN_SECRET`
    requirement is unit-tested; no production deployment exists.
  - The 5-case benchmark and the retry canary were NOT rerun (closed
    experiments; boundary respected). Any future benchmark comparison
    must account for the stricter tool acceptance (§4 reporter-behavior
    note).
