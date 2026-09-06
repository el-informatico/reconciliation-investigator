# P0-C closeout — approver-kwarg fix, Windows-side default-binding validation, README resolution, final commits (2026-09-06)

Driver: human-commissioned closeout task with three recorded decisions —
(1) fix the approver-kwarg defect, (2) do NOT wait for manual
Windows-browser confirmation, validate the default `127.0.0.1` binding
with automated tooling instead, (3) commit everything locally. Result:
all three done; **6 local commits, nothing pushed; suite 217 passed
before and after** (session-start baseline 216 + 1 new regression
test); Architect gate Tier C PROCEED (conditions discharged below);
adversarial reviewer ACCEPT.

Claim tags: MEASURED (instrumented this run) / CALCULATED (derived) /
OBSERVED (seen, not instrumented) / DOCUMENTED (cited from a prior
record) / PROJECTED (prediction) / UNKNOWN (open).

---

## 1. Approver-kwarg fix — MEASURED

**Before** (`approval/web.py:347`, as documented by the loopback doc §7
and OBSERVED in that run's audit dump):

```python
executed = apply_gate_approval(case_id, outcome, draft)
```

`apply_gate_approval(case_id, gate, draft, approver: str = "human")`
(`orchestrator/graph.py:291`) fell back to its default, so a custom
`--approver` reached the `gate_approval` row (via the `GateDecision`
built at web.py:344 → `human_gate.py:252`) but the executor's
`correction_applied` row (`correction_executor.py:92`) recorded
`"human"`. Audit attribution only; no authorization effect (the
approver name is declarative, never compared — §2.4 demo scope).

**After** (one line, the entire code change):

```python
executed = apply_gate_approval(case_id, outcome, draft, approver=approver)
```

This matches the CLI path's forwarding (`graph.py:366-368`,
`approver=getattr(decision, "approver", "human")`) and the sibling
`_do_replay` call (`web.py:408`), which already passed it.

**Regression test** — `test_http_layer_approve_records_approver_in_both_audit_rows`
(`tests/test_approval_surface.py`): real HTTP POST through the real
composition (no mocks), asserting `gate_approval.approver` AND
`correction_applied.approver` both equal the non-default approver.

**Negative control** — MEASURED: written and run BEFORE the fix, it
failed on exactly the defect:

```
assert applied[0]["approver"] == approver
E   AssertionError: assert 'human' == 'http-approver-attribution'
```

(the `gate_approval` assertion passed pre-fix, isolating the failure to
the `correction_applied` row). Post-fix: 1 passed; full file 14 passed.

**Confinement** — MEASURED: `git diff --stat` over `orchestrator/`,
`agents/`, `evals/`, `tools/seed_data.py` empty; no capability-token
logic touched; `approval/` contains no `apply_correction` reference
(segregation guard PASS, verify step 2).

**Live confirmation** — MEASURED: a Windows-originated approval during
§2's validation produced BOTH audit rows carrying
`"approver": "windows-default-bind-2026-09-06"` (evidence:
`agent-memory/evidence/approval-web-windows-default-bind-2026-09-06/runtime-store-after.txt`).

## 2. Windows-side automated validation of the default binding — MEASURED

**Method that worked** (research pass, then the real run): real Windows
browser engines spawned directly from this WSL shell with
`--headless=new` plus a throwaway `--user-data-dir`, each completing in
~1 s: Edge 152.0.4191.62 `--dump-dom`, Chrome 152.0.7977.76
`--screenshot`. `powershell.exe` is conclusively unusable from this
shell (timed out in every variant, including via `cmd.exe` and with
full stdio redirection); the prior session's `chrome.exe` "hang" was a
launched persistent GUI session whose launcher never exits — not a
deadlock. Native `curl.exe` covers scripted POSTs. DOCUMENTED+MEASURED.

**Run**: fresh synthetic C-1001 case (balance 1250.00 → 1500.00, draft
`DRF-359ed2fed288`, ticket `TCK-095f5266963b`, evidence `L-TXN-90002`),
isolated `--runtime-dir`, server launched with NO `--bind` flag
(committed default `127.0.0.1`), port 8791, zero LLM/API calls. 9/9
initial-render content greps in the Edge DOM dump (case card, ticket,
root cause, correction card, values, draft id, approve form, security
footer); Chrome PNGs 1280×900 before and after approval; scripted
`POST /approve` from Windows → Execution result card (`applied`,
`AUD-da0a75f69c2d`, ticket `resolved`); scripted `POST /replay` →
refused "token already consumed (single-use)"; store chain identical to
the CLI/Playwright validations. MEASURED; full log + artifacts:
`agent-memory/evidence/approval-web-windows-default-bind-2026-09-06/`
(windows-run.txt, DOM dumps, both PNGs, responses, store dump,
verify-steps-1-5.txt).

**Honest verification level for the default binding**:
BROWSER-RENDERED + HTTP-INTERACTIVE — real Windows Edge/Chrome engines
rendered the screen (DOM content + screenshots) and a native Windows
client scripted the APPROVE form submission through the real
deterministic gate. NOT done from Windows: a headed, interactive GUI
click (headless dump/screenshot cannot click). Click-level interaction
evidence remains the prior Playwright run over `::1` (WSL side).
**Windows-GUI-headed-browser rendering of the default bind: UNKNOWN**
(not exercised; nothing observed suggests it differs — plain HTML
forms, no JS — which is PROJECTED, not evidence).

**Incident, disclosed** (MEASURED detection + remediation): the first
seeding attempt set a `RUNTIME_DIR` env var, which `tools/seed_data.py`
does not read (the store location is its `RUNTIME_DIR` module
attribute, `tools/seed_data.py:22`) — two rows appended to the repo's
own `runtime/` store. Detected immediately (no-draft render, empty
evidence runtime); both lines truncated; sha256 of all three repo
runtime files then matched the 2026-09-06T01:53Z capture
(`approval-web-loopback-2026-09-06/repo-runtime-sha256-after.txt`)
byte-identically, and were re-verified clean after the run. Nothing
executed against those rows; nothing consumed. The adversarial reviewer
independently confirmed content-level containment (zero incident
markers repo-wide). `seed_case.py` documents the attribute seam.

**Cleanup** — MEASURED: server stopped, port released, Windows temp
dir deleted (verified absent), no scheduled tasks created, no
persistent Windows state, loopback-only exposure throughout.

## 3. README entanglement resolution — CLEAN SPLIT (verified)

Outcome: **clean split achieved** — two pure-reorganization commits
plus one corrections commit. Why: a read-only analysis pass classified
every changed line (editorial vs human-gate) and found no line-level
fusion between the categories (the one MIXED region was
adjacent-but-distinct lines); the intermediate (editorial-only) state
is internally coherent; and the split was mechanically verified in
scratch repos to compose byte-identically back to the held working-tree
diff, with every intermediate line provably pre-existing in HEAD or the
working tree (zero authored content — the D-2026-09-06-01 concern).
Staged via verified patch artifacts (`/tmp/readme-split/`; HEAD and
working-tree backups cmp-verified against git truth from this seat);
no interactive hunk editing. Two follow-up facts were then corrected in
a separate one-line-each commit (the stale "no live-browser validation"
line, now stating the §2-achieved level, and the tests/ count 17→18) —
deliberately kept OUT of the pure-reorganization commits so those stay
content-neutral, per the reviewer's finding. MEASURED (git diff empty
after the split pair; commit diffs +116/−27 and +35/−13).

## 4. Commits created this session — MEASURED

| # | Hash | Subject | Contents |
|---|---|---|---|
| 1 | `ac08b36` | Add rejected-call diagnostics log and viewer | `tools/case_management.py`, `scripts/show_rejected_calls.py`, `tests/test_rejected_call_diagnostics.py`, `docs/draft-rejection-diagnostics-2026-09-06.md` |
| 2 | `6387ddd` | Restrict approval --bind to loopback; fix approver audit attribution | `approval/web.py` (bind set + approver kwarg — grouped deliberately: same component, one validation story, avoids an incoherent intermediate tree where the amended doc cites a fix not yet landed), `tests/test_approval_surface.py` (5 HTTP-layer tests + regression test), `docs/approval-web-loopback-fix-and-validation-2026-09-06.md` (with §10 + amendments), `docs/human-gate-e2e-validation-2026-09-05.md` (3 amendment blocks), `agent-memory/decisions.md` (D-2026-09-06-02 + closeout), both evidence dirs (isolated `runtime/` stores excluded by the unanchored `.gitignore` `runtime/` rule — the captured store dumps are the committable evidence) |
| 3 | `6d1af52` | README editorial pass: overview, models, tree, running docs | README.md editorial half (+116/−27, pure reorganization) |
| 4 | `95fadc8` | Document the human-gate approval surface in README | README.md human-gate half (+35/−13, pure reorganization) |
| 5 | `dbe46ed` | README: correct stale validation line and test-file count | README.md two one-line corrections |
| 6 | (this commit) | Add P0-C closeout report | `docs/p0c-closeout-2026-09-06.md` |

- **No AI attribution**: the commit-msg hook (`scripts/hooks/commit-msg`
  via `core.hooksPath=scripts/hooks`) is active and enforced at every
  commit above (wiring re-verified in the step-2 replication: hooksPath
  correct, both hooks executable — MEASURED); post-hoc inspection of
  the messages confirms none carries an AI-tool reference.
- **Nothing pushed**: local commits only; no `git push` issued this
  session. MEASURED (`git status -b`: ahead of origin/main only).
- Commit 2 was amended once pre-finalization (`7b264fb` → `6387ddd`)
  to normalize two PNG file modes copied from `/mnt/c` (100755→100644);
  message and content otherwise unchanged. OBSERVED.

## 5. Test suite — MEASURED

| Run | Command | Result |
|---|---|---|
| Session-start baseline (task brief) | `uv run --locked pytest -q` | 216 passed (DOCUMENTED from both prior tasks' docs) |
| Before any commit (Phase 4a) | `uv run --locked pytest -q` | **217 passed** in 8.08s |
| verify step-5 replication (same tree) | `uv run --locked pytest -q` | 217 passed in 7.95s |
| After all commits (Phase 4d) | `uv run --locked pytest -q` | **217 passed** |

Delta CALCULATED: 217 = 216 + 1 (the approver regression test; no other
test added this task). Zero regressions. verify.sh steps 1–5 replicated
individually, all PASS (log in the Windows evidence dir); step 6 (live
5-case benchmark) EXCLUDED per task contract and standing constraint —
no benchmark, canary, or other live LLM/API call was run this session.

## 6. Session commit sequence (git log --oneline, newest first)

```
(pending) Add P0-C closeout report
dbe46ed  README: correct stale validation line and test-file count
95fadc8  Document the human-gate approval surface in README
6d1af52  README editorial pass: overview, models, tree, running docs
6387ddd  Restrict approval --bind to loopback; fix approver audit attribution
ac08b36  Add rejected-call diagnostics log and viewer
4f81e7d  (session-start HEAD) Document local-path/AI-reference audit; ...
```

The branch remains locally ahead of origin/main (which includes the 15
pre-session commits from the earlier accumulated-work landing);
origin/main is untouched at `c5f5e13`. MEASURED.

## 7. Gates, review, and scope fences

- **Architect gate**: Tier C, PROCEED — segregation spine untouched
  (no `apply_correction` reference in `approval/`), no
  contract-mandated behavior altered (§2.5 audit fidelity improves),
  items (a)/(b) as reviewed pose no contract issue; conditions
  discharged: scope lock (1), both-rows test over the real composition
  (2), guard green (3), stale records closed via §2 + the README
  corrections commit (4), verify steps 1–5 on the final tree (5),
  local-only with hook enforcement (6). DOCUMENTED (gate output) +
  MEASURED (this doc).
- **Adversarial reviewer**: ACCEPT — "every functional and confinement
  claim survived attack". Findings disposition: MEDIUM (forward
  references to this doc + the "COMMITTED" assertion) resolved by this
  sequence completing as designed; MINOR (17→18 count) fixed in commit
  5; MINOR (deferred stale line) fixed in commit 5; INFO items
  disclosed below. DOCUMENTED (review output).
- **Untouched per contract** — MEASURED (`git diff` scope): 
  `agents/retry.py`, agent builders, `evals/`, benchmark/canary code;
  `orchestrator/human_gate.py`, `orchestrator/correction_executor.py`,
  capability-token logic; no validator weakened anywhere; no secrets
  involved (the validation used no credentials; no `.env` was read).
- **Residual/UNKNOWN carried forward**: Attempt-1 C-1004 malformed
  call shape (pre-diagnostics) stays UNKNOWN; first live
  `rejected_calls.jsonl` entry expected at the next demo/benchmark run
  (PROJECTED); Windows-headed-GUI-click of the default bind UNKNOWN
  (§2); host-side IPv4-loopback root cause UNKNOWN (Windows-side,
  admin); the offline-only status of the diagnostics wrapper on the
  live tool-rejection path (no live-model evidence by design this
  session) is disclosed per the Architect's evidence-gap note.
