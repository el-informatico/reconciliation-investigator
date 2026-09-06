# Stage 3 pending-work audit (2026-09-05)

**Status: PRE-COMMIT AUDIT COMPLETE. Identity corrected; pending work fully
audited and classified; the Groq parsing-retry/fix work verified (security,
implementation, tests, docs, secrets); commit #20 contents proposed —
NOT YET CREATED. Awaiting explicit human approval at the mandatory
pre-commit stop.** (Classification tags as in prior stage reports:
MEASURED / OBSERVED / DOCUMENTED / CALCULATED / UNKNOWN.)

Verification method: direct measurement in this session plus eight
independent delegated reviews (adversarial invariant review; retry
implementation review against installed SDK source; docs/evidence
consistency review; secret/artifact scan; committed-tree simulation;
architect gate; staged-diff dry-run in a sandbox clone; adversarial
commit-readiness challenge). No live LLM call, no benchmark, no provider
capacity consumed; `scripts/verify.sh` was NOT executed (its step 6 is the
live 5-case benchmark — steps 2 and 5 equivalents were run individually).

---

## 1. Remote baseline (full SHA) — MEASURED

- Remote: `origin` = `noreply@example.com:el-informatico/reconciliation-investigator.git`
- Remote HEAD: `refs/heads/main` = **`8eb545f757fdacbaf043a9d67221738667282bdb`**
  (verified three ways: `git ls-remote` SSH, `gh api .../branches/main`, and the
  tracking ref). No other refs, **0 tags**, 1 branch.
- Remote commit count: **19** (GitHub API + `git rev-list --count origin/main`).
- Visibility: **PRIVATE** (`gh api` → `private: true`). Owner `el-informatico`.

## 2. Local baseline (full SHA) — MEASURED

- Branch: `main` (sole branch). Local HEAD = **`8eb545f757fdacbaf043a9d67221738667282bdb`**.
- Local commit count: **19**. Identity on all 19 commits (author AND committer,
  unanimous by `git log --format | sort -u`): `juanz <204210901+el-informatico@users.noreply.github.com>`.
- Local-only ref: `refs/heads/stage2-pre-rewrite-backup` = `316835fb73d66850444473c86fa33df10c4c8169`
  (Stage-2 recovery; **stays local — will not be pushed**). No tags, no stashes,
  no extra worktrees.

## 3. Ahead/behind state — MEASURED

`git rev-list --left-right --count origin/main...HEAD` → **0 / 0**.
Merge-base = `8eb545f…` (= both tips). Index empty (`git diff --cached` = 0 lines).
Commit-range diff `origin/main..HEAD` = empty. All pending work therefore lives
in the working tree and untracked files only.

## 4. Working-tree state before Stage 3 — MEASURED

5 tracked-modified files + 39 untracked top-level paths (44 porcelain entries;
the untracked evidence directories hold ~140 files on disk):

- Modified: `agents/classifier.py`, `agents/detector_investigator.py`,
  `agents/reporter.py`, `tests/test_tools.py`, `tools/case_management.py`
  — collectively `5 files changed, 42 insertions(+), 1 deletion(-)`, byte-for-byte
  the diff the live validation recorded as its baseline (§13 of the validation
  report; re-derived this session).
- Byte-drift check vs the validation's §12 sha256 records — all identical:
  `agents/retry.py` `ab0ed6af…`, `agents/detector_investigator.py` `fe2d7042…`,
  `agents/classifier.py` `9a6df5e2…`, `agents/reporter.py` `1866711d…`,
  `tools/case_management.py` `99a441dd…`; `.env` `874a40f8…`, `uv.lock`
  `a3b4ac54…`, `pyproject.toml` `ad9b302d…` (unchanged since the validated run).

## 5. Repo-local identity — before / after — MEASURED

| Scope | Before | After |
|---|---|---|
| `--local` user.name | `Ares Agent` | **`juanz`** |
| `--local` user.email | `ares-agent@local` | **`204210901+el-informatico@users.noreply.github.com`** |

Set via `git config --local user.name/email` (only `.git/config` written).
Verified with `git config --show-origin --get-all`: both values resolve solely
to `file:.git/config`.

## 6. Global identity — before / after (unmodified) — MEASURED

`git config --global --get user.name` / `user.email` = **(unset) both before and
after** (matches the Stage-1 finding that the human maintains identity
repo-locally only). System scope also unset. No `--global`/`--system` write was
performed at any point. Sibling repositories under `~/projects/` re-snapshotted
read-only after the change: all unchanged ([SIBLING-B], [SIBLING-G], aresV2,
[SIBLING-H], [SIBLING-I], [SIBLING-J],
[SIBLING-E] still `Ares Agent <ares-agent@local>`; [SIBLING-C] and
[SIBLING-A] still `juanz <juanz@local>`); only this repo carries the
new identity. No Stage-3 command wrote outside this repository (sandbox work
confined to `/tmp/stage3/`).

## 7. Exact files of the retry/fix work (proposed commit #20) — MEASURED

The pending work is one closed Groq-resilience work product ("retry/fix",
the same 5-file tracked diff Stage 1 §1 and Stage 2 §17.1 classified), plus its
tests and documentation/evidence:

**Code + tests (7 paths):**
| Path | Change | Content |
|---|---|---|
| `agents/retry.py` | new (126 lines) | `GroqParsingFailedRetryStrategy` — see §11 |
| `agents/detector_investigator.py` | +2 lines | import + `retry_strategy=GroqParsingFailedRetryStrategy()` |
| `agents/classifier.py` | +2 lines | same wiring |
| `agents/reporter.py` | +2 lines | same wiring |
| `tools/case_management.py` | 1 line | `correction_draft_id` → `correction_draft_id: str \| None` (implements `docs/build-contract.md:213` `str \| null`; the untyped parameter made strands stamp `type:string` onto the wire schema so Groq rejected contract-correct `null`) |
| `tests/test_tools.py` | +35 lines | regression test `test_create_case_ticket_schema_allows_null_correction_draft_id` (raw + normalized wire schema stay required-yet-nullable; tool accepts `None` and a real draft id verbatim) |
| `tests/test_groq_parsing_retry_offline.py` | new (21 tests) | hermetic retry tests — self-contained (imports only `agents.retry`, strands, openai, httpx2) |

**Documentation + evidence (4 docs + 3 evidence trees, 67 files):**
`docs/case-4-parsing-failure-audit-2026-09-04.md` (root-cause audit of the
exact failure; cited by `agents/retry.py`'s docstring),
`docs/correction-draft-id-fix-canary-2026-09-04.md` (typing-fix canary),
`docs/groq-parsing-retry-canary-2026-09-05.md` (retry canary report),
`docs/groq-retry-active-5case-validation-2026-09-05.md` (canonical live
validation), and the mirrored evidence trees
`agent-memory/evidence/{correction-draft-id-fix-canary-2026-09-04 (4 files),
groq-parsing-retry-canary-2026-09-05 (25), groq-retry-active-5case-validation-2026-09-05 (38)}`.

**Structural-coupling finding (decisive for scope):** the retry *canary driver*
(`evals/groq_parsing_retry_canary.py`) and its offline test
(`tests/test_groq_parsing_retry_canary_offline.py`) are retry-specific but
import `evals.gemini_judge_canary` and `evals.token_canary` — the untracked,
separately-validated evals workstream. Committing them would drag that entire
layer into #20; omitting their imports breaks the committed tree. They are
therefore EXCLUDED and remain local with the rest of the evals layer (future
commit of that layer). The included test file has no such coupling — proven by
simulation (§9).

## 8. Exact files EXCLUDED from commit #20, and why — MEASURED

| Category (Stage-3 taxonomy) | Paths | Why excluded |
|---|---|---|
| B→G: retry-specific but coupled | `evals/groq_parsing_retry_canary.py`, `tests/test_groq_parsing_retry_canary_offline.py` | import the excluded evals workstream; belong with that layer's future commit |
| D: unrelated workstreams (Gemini-judge evaluation) | `evals/gemini_judge_canary.py`, `evals/gemini_judge_5case.py`, `tests/test_gemini_judge_canary_offline.py`, `tests/test_gemini_judge_5case_offline.py`, `docs/gemini-judge-canary-2026-09-04.md`, `docs/gemini-judge-5-case-validation-2026-09-04.md`, `docs/gemini-groq-5-case-final-validation-2026-09-05.md`, `agent-memory/evidence/gemini-judge-*` (2 dirs), `agent-memory/evidence/gemini-groq-5-case-final-validation-2026-09-05/`, `agent-memory/gemini-feasibility-2026-09-04.md`, `agent-memory/gemini-quota-provenance-2026-09-04.md` | separate, previously completed bodies of work with their own validations; not the retry/fix work |
| D: unrelated workstream (token audit) | `evals/token_canary.py`, `tests/test_token_canary_offline.py`, `docs/token-workload-audit-2026-09-04.md`, `docs/token-workload-canary-2026-09-04.md`, `agent-memory/evidence/token-canary-2026-09-04/` | same |
| D: Stage-1/2 git-publication session artifacts | `docs/git-identity-audit-stage1-2026-09-05.md`, `docs/git-stage2-final-report-2026-09-05.md`, `docs/git-stage2-sha-rewrite-report-2026-09-05.md`, `docs/git-stage2-pre-rewrite-checkpoint-2026-09-05.md`, `agent-memory/evidence/git-stage2-rewrite-2026-09-05/`, `docs/commit-history-audit-and-github-repo-plan-2026-09-05.md`, `docs/state-and-gap-analysis-2026-09-05.md` | Stage-2/3 process records, not application work; their disposition is a separate human decision |
| D: provider notes | `agent-memory/groq-preflight-2026-09-04.md` | provider-feasibility workstream |
| G: probe artifacts (stay local; hygiene-checked) | `agent-memory/evidence/groq-probe-repo-key-2026-09-04.json`, `…groq-probe-repo-key-2026-09-04.txt`, `…groq-replay-probe-2026-09-04.txt` | probe tooling output; secret-scan CLEAN (see §10) but not evidence for this work |
| G: credentials/config | `.env` (237 B) | gitignored (`.gitignore:10`), untracked, never staged |
| G: runtime/ | `runtime/**` (gitignored) | generated runtime store |

## 9. Tests executed and results — MEASURED

| Command (cwd = repo) | Result |
|---|---|
| `uv run --locked pytest -q` (verify.sh step-5 form; full working tree) | **132 passed** in 5.31 s (collect count 132 re-verified; matches Stage-2's record) |
| `uv run --locked pytest tests/test_groq_parsing_retry_offline.py tests/test_tools.py tests/test_gate_executor.py -q` (retry + tool + security/gate/executor) | **59 passed** (21 + 15 + 23) |
| `bash scripts/guard-segregation-of-duties.sh <repo>` (verify.sh step-2 form) | **exit 0** |
| Committed-tree simulation (sandbox clone of `8eb545f` + exactly the proposed file set; `GROQ_API_KEY=dummy uv run --locked pytest -q`) | **94 passed** in 7.26 s — exactly the predicted 72 baseline + 1 regression + 21 retry; zero collection errors; guard exit 0 |

Test-count reconciliation: 132 = 72 (committed at `8eb545f`) + 1 (`test_tools`) + 21 (retry offline) + 38 excluded-workstream tests (gemini-judge 15, token 8, retry-canary-driver 15). No failures anywhere; nothing to classify.

## 10. Secret / artifact scan — MEASURED (delegated, independent)

- Pattern classes (Groq `gsk_`, Gemini `AIza`, OpenAI `sk-`, GitHub `ghp_`/`github_pat_`, AWS `AKIA`, private-key headers, Bearer/authorization values, Z.AI markers, generic secret assignments, 40+hex blobs) over all 14 intended paths, the three evidence trees (74 files), and the 42 added diff lines: **zero credential material**. Only hits: one known-benign offline test fixture token and digest-legit sha256/commit-id records (34 hex-40 tokens, all file digests; one digest *of* `.env` — value-free).
- `.gitignore` protection confirmed: `.env`, `runtime/`, `*_evaluation.json` ignored; no intended path ignored except the `run.log` completeness item below.
- Evidence trees: nothing >200 KB (max 37.5 KB), no binaries, no exec bits, one zero-byte `segregation-guard.txt` (by design); the two `baseline/*.pre-edit` files are deliberate pre-edit snapshots (digest-verified), not foreign workstream content.
- Excluded probe artifacts (local hygiene only): **CLEAN** — no credential-shaped material.
- **Completeness caveat (the one open decision):** `.gitignore:7 *.log` silently
  skips three intended evidence files — `correction-draft-id-fix-canary-2026-09-04/run.log`
  (4,776 B), `groq-retry-active-5case-validation-2026-09-05/run.log` (37,514 B),
  `groq-parsing-retry-canary-2026-09-05/live/run.log` (5,243 B). The canonical
  report derives its figures from `run.log` (cited 8×). **Recommendation: force-add
  these three (`git add -f`) — evidence stays verbatim, one-shot, no policy-file
  change; renaming would falsify the reports' own derivations, and a `.gitignore`
  negation would be a repo-policy edit outside Stage-3 scope.** Fallback if
  disapproved: commit without them and accept a disclosed evidence gap. No
  tracked `.log` exists today (no precedent either way); `agent-memory` is
  intended to be tracked per the owner's Stage-1 decision.

## 11. Architecture / security invariant review — MEASURED (delegated, adversarial)

**15/15 PASS** (verdict ACCEPT), with file:line evidence: detector = exactly the
4 read-only tools; classifier `tools=None`; reporter = draft+ticket only;
`apply_correction` a plain function whose sole caller is
`orchestrator/correction_executor.py:71`; human gate deterministic (stdlib +
HMAC, `orchestrator/human_gate.py:86,103-106`), payload scoped
`{case_id, field, new_value, exp, jti}`, TTL 600 s + single-use jti consumption;
audit logging intact; `agents/retry.py` imports nothing from tools/orchestrator
(no write path); retry classification narrow; `agents/model.py` untouched (Groq
wiring intact; only `GROQ_API_KEY`/`GEMINI_API_KEY`/`CORRECTION_TOKEN_SECRET`/`EVAL_MODE`
read — **no Z.AI credential anywhere in application code**); the tracked diff
touches **no file under `orchestrator/` or `scripts/`**.

**Retry implementation review — 11/11 PASS against installed SDK source**
(strands-agents 1.54.0, openai 3.8.0): prefix-exact 68-char case-sensitive match
(`str.startswith`; lowered/reworded/prefixed/truncated all fail); every
`APIStatusError` subclass (401/403/429/400/500) excluded even with the audited
text; stock throttle path inherited unchanged (6 attempts / 4 s initial / 240 s
cap; worst-case sleep 124 s; subclass adds no loop); **exhaustion re-raises the
original `openai.APIError` unswerved** (`event_loop.py:641-642`; the
`EventLoopException` wrap belongs to the tool-execution block, not the model
path); exactly 3 production `retry_strategy=` sites; `strands_evals` and all
Gemini/judge paths contain zero retry references (type gate also categorically
excludes non-openai exceptions); **no mutation duplication** — retry re-entry
re-invokes only the model stream (`event_loop.py:632-636`), tools execute only
after a completed stream, partial toolUse is never appended; evidence ledger
metadata-only + lock-guarded; fresh instance per Agent.

**Architect gate:** Tier B (no Tier-C surface touched; the annotation *implements*
`docs/build-contract.md:213` rather than changing contract), ACTION
gate-with-conditions → conditions (1) scope = audited set only and (2) 94/94
tree-simulation green are **satisfied** (the simulation landed PASS after the
gate ran); condition (3) is carried forward, not a commit blocker: disclose
parse-retries in all future benchmark reports, and record the strands-1.54.0
private-API subclassing (`_retry.py` internals, `_max_attempts`/`_initial_delay`/
`_max_delay` attributes) plus the `httpx2` transitive test import
(openai==3.8.0 dep; pinned in `uv.lock:613`) as upgrade hazards while versions
stay pinned.

## 12. Documentation / evidence review — MEASURED (delegated)

Canonical report `docs/groq-retry-active-5case-validation-2026-09-05.md`:
**every checkable claim reconciles exactly** against the evidence tree —
executions:1; 589 s wall (13:06:48Z→13:16:37Z); 5/5 rc=0 (`all_exit_zero`);
2 ledger classifications attributed to case-02/case-05 with 3 ms/2 ms lag;
token tables identical to per-case summaries (agents 48/45,082/13,331/58,413;
judges 77/290,420/14,025/304,445; grand 362,858); 72 rows/66 passed; exactly one
`judge-error` row (Gemini 503); OTel 125/125 delta-0; "132 passed in 5.14s"
artifact; **corrected wording present verbatim** ("No retry-related regressions
were observed on any other axis", status line + §15); n=1 explicit; 2/48 framed
as raw count, **not** a probability; exhaustion/multi-attempt stated
offline-only; Gemini 503 documented as **not retried by design**; §12
post-run-checks (guard exit 0 + constrained-file sha256s) present. Canary and
typing-fix docs likewise confirmed (rc=0, 101.0 s, 26/26, `classification_count:0`;
15 rows/13 pass; null ticket `TCK-9168c1874617` in `runtime/tickets.jsonl` as the
doc itself cites). Cross-doc: the case-4 audit's verbatim error text is
byte-identical to `agents/retry.py`'s prefix. Two benign evidentiary notes (the
typing-fix canary's 93→94 suite figures have no artifact inside its own tree;
null-ticket proof lives in gitignored `runtime/`), and two advisory items from
the adversarial challenge (below) — **no objective factual inconsistency found;
per Phase 7 no report edits were made.**

Advisory (disclosed, no action taken): the committed docs reference not-yet-
committed files — the reproduce command `python -m evals.gemini_judge_5case`
and the canary driver/tests (excluded evals layer), and the case-4 audit's
primary evidence tree (gemini-judge workstream). These become followable when
that layer is committed; reports are historical records and were not edited.
Also noted: two provenance references to pre-rewrite SHAs (`316835f…`) resolve
only on the local `stage2-pre-rewrite-backup` ref — consistent with the
human-approved Stage-2 preserve-as-provenance policy (22 such occurrences
already exist in the pushed tree).

## 13. Proposed commit #20 contents — MEASURED (staged-diff dry-run in sandbox clone)

- **78 files, 9,790 insertions(+), 1 deletion(-)**: 5 modified tracked
  (classifier, detector_investigator, reporter, test_tools, case_management —
  the 1 deletion is the single-line typing change) + 73 new
  (`agents/retry.py`, 4 docs, 1 test, 67 evidence files). Zero deletions of
  files; nothing outside the approved set; nothing ignored accidentally staged.
- Optional (recommended, §10): +3 force-added `run.log` files → **81 files**.
- Proposed message (subject per the Stage-3 preference):

```
Add bounded retry for Groq parsing failures

Groq intermittently rejects one nondeterministic gpt-oss-120b emission
and terminates the HTTP-200 SSE stream ("Parsing failed. The model
generated output that could not be parsed."), raised by the openai SDK
as a plain APIError that stock Strands treats as terminal; it killed
benchmark cases on 2026-09-04 and 2026-09-05. agents/retry.py adds
GroqParsingFailedRetryStrategy: exactly that one verbatim-prefix
signature (never APIStatusError, never any other message) layered on
the stock throttle-only policy with stock bounds (6 attempts, 4s..240s
exponential backoff) and the original exception preserved on
exhaustion. Wired into the detector, classifier, and reporter builders
only; judges and Gemini paths are untouched.

Also type create_case_ticket's correction_draft_id as str | None per
docs/build-contract.md (str | null): untyped, strands stamped
type:string onto the wire schema, so Groq rejected contract-correct
null emissions and killed the reporter node.

Offline: 21 new hermetic retry tests; suite passes 132 locally and 94
in this tree. Live (2026-09-05, 5-case validation): 5/5 rc=0, the retry
fired twice and recovered twice, zero new-signature or exhausted
events. Includes the root-cause audit, both canary reports, the active
5-case validation report, and their evidence trees.
```

- Author/committer will be `juanz <204210901+el-informatico@users.noreply.github.com>` (repo-local config now set); no Claude Code mention, no co-author trailers. The `scripts/hooks/pre-commit` segregation guard will run at commit time (currently exit 0).
- Push plan (after approval + post-commit checks): `git push origin main` only — no tags, no `stage2-pre-rewrite-backup`, no force. Remote pre-verified: PRIVATE, 1 branch, HEAD `8eb545f…`, 19 commits, 0 tags.

## 14. Safety statement

**Commit #20 is SAFE TO CREATE**, as a normal descendant of `8eb545f`
(ahead/behind 0/0; fast-forward push), with one ratification decision: whether
to force-add the three `run.log` evidence files (recommended yes — §10) or
commit the 78-file set without them (fallback, gap disclosed). Residual notes,
none blocking: dangling references to the excluded evals layer (§12); two
pre-rewrite-SHA provenance references (§12); carried-forward upgrade hazards
(strands private-API subclassing; httpx2 transitive import — optional future
hardening: pin `httpx2==2.12.0` in pyproject); first-ever evidence
subdirectories in `agent-memory` (cosmetic extension of the tracked-evidence
convention). No architecture/security invariant is violated; tests pass in
both scopes; secrets absent; identity corrected and verified.

**STOP: no commit, no push, no branch, no visibility change has been made.
Awaiting explicit human approval.**
