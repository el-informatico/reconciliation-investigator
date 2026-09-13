# Rejected-Call Diagnostics — `runtime/rejected_calls.jsonl` (read-only observability for rejected draft/ticket calls)

Date: 2026-09-06 · Driver: human-approved remediation for the 2026-09-06 human-gate e2e
Attempt-1 gap (`docs/human-gate-e2e-validation-2026-09-05.md` §7, case C-1004) · Result:
**LANDED LOCAL, UNCOMMITTED** — suite 190 → **216 passed** (216 = 190 + 21 this
task + 5 concurrent session; §7), zero behavior change, reviewer ACCEPT.

Evidence classes used below: **MEASURED** (a test/run produced the number) ·
**CALCULATED** (derived from measured values) · **OBSERVED** (raw artifact
inspected) · **DOCUMENTED** (a prior report asserts it; spot-checked where
cited) · **PROJECTED** (expectation, not evidence) · **UNKNOWN** (no evidence
path exists). No `<<placeholder>>` is left in any claim.

---

## §1 Why this exists

DOCUMENTED + OBSERVED: human-gate e2e Attempt 1 (2026-09-06, case C-1004)
failed at the drafting stage — the reporter never completed a
`draft_correction` call that reached the gate — and the exact malformed call
shape is UNKNOWN because a rejected tool call left no trace: the validators
raise (`tools/seed_data.py:75-78,57-61,113,118-120,125`), Strands converts the
raise into an error `ToolResult` for the model, and nothing on disk records
what was rejected or why. If that recurs during a live demo there is no way to
explain it in the moment. This change records every rejected
`draft_correction`/`create_case_ticket` call — observability only.

## §2 Design

- **Where**: hooks live at the two tool call sites in `tools/case_management.py`
  ONLY. The shared validators in `tools/seed_data.py` are untouched — they are
  also on the gate path (`orchestrator/graph.py:339` calls `canonical_case_id`
  at `run_case_with_gate` entry), and per the Architect's gate condition C1 the
  diagnostics must not put writes on the Tier C spine's code path.
  **`tools/seed_data.py` has zero changes from this task** (its working-tree
  diff vs HEAD predates this session — pre-existing uncommitted work left
  intact per the P0 handoff; OBSERVED via `git status`/`git diff --stat`).
- **When**: the tool snapshots its arguments as received (`received = {...}`),
  wraps its ENTIRE body (validation + store append + return) in `try:`, and on
  any exception appends one record BEFORE the bare `raise` re-propagates the
  original exception (identity, message, traceback untouched). Reviewer
  finding 1 widened this from validation-only: a post-validation crash — e.g.
  a model-emitted `null` dying at `list(evidence_refs)`, the 2026-09-04 Groq
  null-lottery class — is exactly the "call died with no trace" shape this
  task exists to eliminate, so it is logged too (MEASURED by
  `test_post_validation_null_crash_is_logged_too` and
  `test_unserializable_argument_crash_is_logged`).
- **Fail-safe**: `_log_rejected_call` swallows every failure of its own (a
  stderr note at most) — a diagnostic can never change a rejection outcome.
- **Scope of "rejection"**: every validation raise point (13 enumerated:
  `draft_correction` — env guard, canonical id, field, 2× value,
  live-coherence, no-op; `create_case_ticket` — env guard, canonical id ×2,
  unknown draft link, cross-case draft link) plus any post-validation failure
  of the call itself, including the `require_eval_mode()` RuntimeError: an
  out-of-mode call is a rejected call whose received shape otherwise dies with
  it. Noise risk is nil in practice — every test that calls these tools runs
  under the `isolated_runtime` fixture (tmp `RUNTIME_DIR`), and in production
  `runtime/` is gitignored (`.gitignore:37`).
- **Component attribution**: static `"reporter"` — both tools belong to
  exactly one agent (`agents/reporter.py:38`, pinned by
  `tests/test_agents.py:61-64`), and neither signature declares a Strands
  `ToolContext` (strands injects one only when declared; .venv
  `strands/tools/decorator.py:178-186,410-418`), so per-caller attribution is
  not available at call time. The static value is exact, not a guess.
- **Secrets**: the tools' fixed signatures admit no credential parameters;
  model-fabricated extras are rejected by Strands binding before the function
  body runs, so they never reach the log. Defensively, any argument key
  containing key/token/secret/password/credential/authorization is masked
  (`<REDACTED:key>`), strings are clipped at 500 chars, lists capped at 20
  items, non-JSON values reduced to clipped repr — the entry is always
  JSON-serializable. No `.env` value can reach the log: the writer only ever
  sees the call's own arguments and the validator's own message.

## §3 Exact code changes

All application changes are in `tools/case_management.py`; line numbers are
before → after this change:

| What | Before | After |
|---|---|---|
| Module docstring gains the 2026-09-06 diagnostics note | L1-15 | L1-23 (new ¶ at L17-23) |
| `import sys` added | (absent) | L28 |
| `REJECTED_CALLS_LOG` + clipping/redaction constants | (absent) | L113-128 (`REJECTED_CALLS_LOG` at L120) |
| `_clip()` | (absent) | L129-135 |
| `_redact_call_args()` | (absent) | L138-164 |
| `_log_rejected_call()` | (absent) | L167-190 |
| `draft_correction`: `received` snapshot, whole body in `try`, log-then-bare-`raise` | body L154-183 | snapshot L240-246, `try` L247, `except: _log_rejected_call(...); raise` L278-284 |
| `create_case_ticket`: same treatment | body L203-236 | snapshot L304-311, `try` L312, `except: _log_rejected_call(...); raise` L347-353 |

The rejection `raise` statements themselves are byte-identical to before
(same messages, same `ValueError`s) — the wrapper only observes. New files:
`scripts/show_rejected_calls.py` (viewer), `tests/test_rejected_call_diagnostics.py`
(21 tests), this doc.

## §4 Log schema

Store: `runtime/rejected_calls.jsonl` (JSON Lines, appended via the existing
`_append_jsonl`/`runtime_path` conventions, UTF-8, one `\n`-terminated
`json.dumps` object per rejection; `runtime/` is gitignored and test-isolated
via `seed_data.RUNTIME_DIR`).

| Field | Type | Content |
|---|---|---|
| `timestamp` | string | UTC ISO-8601, `datetime.now(timezone.utc).isoformat()` (the repo's `_now()` convention) |
| `component` | string | always `"reporter"` (sole holder of these tools) |
| `tool` | string | `"draft_correction"` or `"create_case_ticket"` |
| `args` | object | the arguments AS RECEIVED (pre-canonicalization); values masked/clipped per §2 |
| `reason` | string | the validator's own message (clipped at 500 chars — messages embed the offending value) |

OBSERVED example (generated 2026-09-06 by the real code path, throwaway
runtime dir; the second line demonstrates the 500-char clip on free text):

```json
{"timestamp": "2026-09-06T06:38:40.498042+00:00", "component": "reporter", "tool": "draft_correction", "args": {"customer_id": "C-1001", "field": "balance", "current_value": "Modern balance is $250 lower", "proposed_value": "1500.00", "justification": "reversal evidence"}, "reason": "current_value for balance must be a plain number (e.g. 1500.00), got 'Modern balance is $250 lower'"}
{"timestamp": "2026-09-06T06:39:07.623824+00:00", "component": "reporter", "tool": "draft_correction", "args": {"customer_id": "C-1001", "field": "balance", "current_value": "zero zero … zero <truncated, 6000 chars total>", "proposed_value": "1500.00", "justification": "justification prose … prose <truncated, 7000 chars total>"}, "reason": "current_value for balance must be a plain number (e.g. 1500.00), got 'zero zero … zero <truncated, 6071 chars total>'"}
```

Masking (defensive only — fabricated keys cannot reach these signatures, see
§2): keys containing the secret markers log as `"<REDACTED:api_key>"`
(MEASURED by `test_redact_call_args_masks_secret_keys_and_caps_lists`).

## §5 Viewer

`scripts/show_rejected_calls.py` — read-only, pure standard library, argparse
+ `main(argv) -> int` (the probes/evals convention for small Python
diagnostics; `scripts/` itself is otherwise the shell-only enforcement
surface, so this file carries no shebang and no exec bit and is run via `uv
run --locked python`). It writes nothing, imports no application code, and is
wired into no guard/verify/hook path (Architect condition C2).

```
$ uv run --locked python scripts/show_rejected_calls.py --runtime-dir /tmp/rejected-calls-demo-6cde
2 rejected call(s) in /tmp/rejected-calls-demo-6cde/rejected_calls.jsonl

2026-09-06T06:38:40.498042+00:00  reporter  draft_correction
  reason: current_value for balance must be a plain number (e.g. 1500.00), got 'Modern balance is $250 lower'
  args:   {"customer_id": "C-1001", "field": "balance", "current_value": "Modern balance is $250 lower", "proposed_value": "1500.00", "justification": "reversal evidence"}

2026-09-06T06:38:40.498206+00:00  reporter  create_case_ticket
  reason: unknown case_id/customer_id 'CASE-C-1001': the case identity is exactly one of the seeded customers ['C-1001', 'C-1002', 'C-1003', 'C-1004', 'C-1005']
  args:   {"case_id": "CASE-C-1001", "summary": "summary", "root_cause": "SYNC_LAG", "confidence": 0.9, "evidence_refs": [], "correction_draft_id": null}
```

OBSERVED output. Flags: `--limit N` (default 20, most recent), `--all`,
`--tool {draft_correction,create_case_ticket}`, `--json` (re-serialized
objects), `--runtime-dir` (default `<repo>/runtime`). Missing/empty store →
friendly message, exit 0.

## §6 Proof the log is inert (never read by gate/executor/approval)

1. **Code citation** — the only references to `rejected_calls` in the entire
   repo are the writer (`tools/case_management.py:120,167-190`), the viewer, the
   tests, and this doc. `orchestrator/human_gate.py` reads only
   `drafts/tickets/consumed_tokens/audit_log` (L130-146, 158-199);
   `orchestrator/correction_executor.py` reads
   `audit_log/overrides/drafts/tickets` (L27-30 via `get_draft`/`get_ticket`/
   `update_*`/`effective_modern_record`). Capability tokens are built and
   validated purely from the draft's own fields + HMAC over
   `{case_id, field, new_value, exp, jti}` (`orchestrator/human_gate.py:70-87,
   90-138`) — the log is not an input to any of it.
2. **Spy test (MEASURED)** — `test_gate_and_executor_never_read_or_write_the_rejected_calls_log`
   spies on `builtins.open` and `io.open` across a full offline flow —
   `latest_pending_draft` → `run_human_gate` APPROVE (token issue) →
   `execute_correction` (token validate/consume/audit, ticket+draft
   resolution) → `validate_approval_token` replay (single-use) — and asserts
   the log file is never opened in ANY mode, is byte-identical afterwards,
   and the applied correction is the REAL one (`after == 1500.00`, not the
   canary entry's `999999.00` planted in the log). PASSED.
3. **Source tripwire (MEASURED)** — `test_no_gate_executor_or_approval_source_references_the_log`
   fails the suite if any `orchestrator/*.py` or `approval/*.py` ever grows
   the string `rejected_calls`. PASSED.
4. **No behavior change (MEASURED)** — all 11 pre-existing rejection tests in
   `tests/test_case_identity_and_hygiene.py` still pass unchanged (same
   `pytest.raises` matches, same "rejected BEFORE any append" asserts), and
   the full suite is green (§7).
5. **Independent cross-check (DOCUMENTED)** — the adversarial reviewer
   re-ran the repo-wide reference greps, the fixed-filename access audit of
   `orchestrator/` + `approval/`, and the C1/C2/C3 fence checks from its own
   seat and issued **ACCEPT**: "logging is confined to the two tool sites'
   except-paths with bare `raise` ... the log has exactly one repo-wide
   writer" (finding 1's coverage gap was then fixed, §2/§10).

## §7 Test results

| Run | Command | Result |
|---|---|---|
| Before (baseline) | `uv run --locked pytest -q` | **190 passed** in 5.67s (MEASURED) |
| New file alone (pre-review) | `uv run --locked pytest tests/test_rejected_call_diagnostics.py -v` | **19 passed** (MEASURED) |
| Full suite (pre-review) | `uv run --locked pytest -q` | **209 passed** (MEASURED; CALCULATED delta +19 = exactly the new file) |
| New file alone (post-review fix) | `uv run --locked pytest tests/test_rejected_call_diagnostics.py -q` | **21 passed** (MEASURED; +2 post-validation-crash tests, §2) |
| Full suite (final) | `uv run --locked pytest -q` | **216 passed** in 7.81s (MEASURED) |
| Segregation guard | `bash scripts/guard-segregation-of-duties.sh <repo>` | **PASS** (MEASURED) |

Final-count attribution (CALCULATED from measured values): 216 = 190 baseline
+ 21 (this task's file) + 5 (uncommitted additions to
`tests/test_approval_surface.py` — 126 insertions vs HEAD — authored by a
CONCURRENT session in this repo, not this task; HEAD moved to `8552390`
mid-session the same way. This task authored no `test_approval_surface.py`
change). All 216 pass: this change is compatible with that concurrent work.

New coverage: 7 parametrized `draft_correction` rejections + 4
`create_case_ticket` rejections (each: identical error AND exactly one entry
AND store-still-empty), cross-case link, valid-calls-write-nothing, out-of-mode
rejection logged, post-validation null crash, unserializable-argument crash,
args/reason clipping, redactor unit test (masking, list cap, JSON-safety),
log-write-failure-changes-nothing, the open-spy canary test, and the source
tripwire.

`scripts/verify.sh` was NOT run as a whole: step 6 executes the live
5-case Groq benchmark unconditionally (`scripts/verify.sh:172`), which this
task forbids. Its step 5 command was run verbatim (the pytest rows above) and
its step 2 guard standalone. Steps 1/3/4/6: not run (3 and 6 are live-network).

## §8 Scope fences (what was NOT touched)

- `agents/retry.py`, the agent builders, `evals/`, benchmark/canary code:
  untouched (DOCUMENTED by `git status`: only the three new files plus
  `tools/case_management.py` carry this task's diff).
- `orchestrator/human_gate.py`, `orchestrator/correction_executor.py`,
  `apply_correction` wiring, token logic: untouched (observed only).
- No validation accept/reject behavior changed anywhere; no new validation
  added (Architect condition C3: `confidence`/`summary`/`root_cause`/
  `evidence_refs` remain unvalidated, as before).
- No benchmark, canary, or live LLM/API call was run (all evidence is
  offline tests + offline demos).

## §9 Commit status

**Left uncommitted, unstaged, unpushed** — per the task's DO-NOT (no standing
authorization for this session) and the repo's gate-before-commit practice.
Verified from the implementing seat (OBSERVED): `git diff --cached` is empty
(0 staged paths); this task's surface is exactly `M tools/case_management.py`
+ three untracked files (`scripts/show_rejected_calls.py`,
`tests/test_rejected_call_diagnostics.py`, this doc). HEAD (`8552390` at time
of writing) advanced via a concurrent session, not this one — no commit,
stage, or push was issued from this session. The repo's commit-msg hook
rejects AI-attribution trailers; irrelevant here because nothing was
committed.

## §10 Limits / residual risk (incl. reviewer findings)

Review disposition — the adversarial reviewer ACCEPTed; finding 1 (post-
validation crashes unlogged) was FIXED by widening the `try` to the whole
call (+2 tests); finding 2 (commit/seed_data status unverifiable from the
reviewer seat) is verified in §9/§2 above; findings 3-4 are disclosed below.

- **UNKNOWN preserved**: Attempt 1's C-1004 malformed shape stays UNKNOWN —
  this log closes the gap for FUTURE rejections only; no live run was
  performed (correctly, per scope). First live entry expected at the next
  demo/benchmark run (PROJECTED).
- The open-spy covers `builtins.open`/`io.open` (every read path the repo
  uses today: `open`, `Path.read_text/open`); a hypothetical future reader
  using `os.open`/`mmap` directly would evade the spy — the source tripwire
  and review cover that residual (DOCUMENTED limitation, stated per the
  Architect's evidence-gap note).
- The store inherits the runtime/ single-writer append assumption (no
  locking) documented for all runtime stores.
- `component` is static per §2; if a second agent ever receives these tools,
  the constant must become call-time attribution (tripwire: the field would
  start lying before any test fails — flagged here deliberately).
- Reviewer finding 3 (TRIVIAL): the viewer treats `--limit 0`/negative as
  "show all" — harmless in an unwired read-only tool; left as is.
- Reviewer finding 4 (TRIVIAL): a secret VALUE pasted into free-text args
  (e.g. inside `justification`) is clipped at 500 chars but not masked — the
  contract masks secret-like KEYS only, no legitimate call carries secret
  values, and value-matching would pull credential material toward the tool
  path (against the repo's credential policy); left as designed.

## Evidence trace

| Claim | Class | Source |
|---|---|---|
| 190 → 216 passed; 216 = 190 + 21 (this task) + 5 (concurrent session's `test_approval_surface.py`) | MEASURED / CALCULATED | §7 runs + `git diff --stat HEAD -- tests/` |
| All rejection messages byte-identical; rejections still precede any append | MEASURED | `tests/test_case_identity_and_hygiene.py` green + new parametrized tests |
| Exactly one entry per rejected call; zero for valid calls | MEASURED | `tests/test_rejected_call_diagnostics.py` |
| Post-validation crashes (null `evidence_refs`, unserializable arg) also leave exactly one entry | MEASURED | `test_post_validation_null_crash_is_logged_too`, `test_unserializable_argument_crash_is_logged` |
| Clip at 500 chars; mask secret-like keys; list cap 20; always serializable | MEASURED | `test_overlong_free_text_is_clipped_in_args_and_reason`, `test_redact_call_args_…`, OBSERVED §4 lines |
| Log write failure never changes a rejection | MEASURED | `test_log_write_failure_never_changes_the_rejection` |
| Gate/executor/token paths never read (or write) the log | MEASURED | spy test §6.2 + tripwire §6.3 + citations §6.1 + reviewer cross-check §6.5 |
| `seed_data.py` validators and all spine files untouched BY THIS TASK; nothing staged/committed/pushed from this session | OBSERVED | `git status`/`git diff --stat`, §9 |
| Both tools reporter-only; no ToolContext available | DOCUMENTED | `agents/reporter.py:38`, `tests/test_agents.py:61-64`, strands decorator paths |
| verify.sh step 6 is live and unconditional | DOCUMENTED | `scripts/verify.sh:26-28,169-179` |
| Next live run writes the first real entry | PROJECTED | §10 |
| Attempt-1 C-1004 malformed shape | UNKNOWN | this task's evidence is tests-only |
