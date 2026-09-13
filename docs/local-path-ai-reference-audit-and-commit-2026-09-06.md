# Full local-path / AI-reference audit + commit of accumulated closed work — 2026-09-06
> AMENDED 2026-09-07: this report references the agent-memory/ directory, which was removed from repository history by the 2026-09-07 excision rewrite; those artifacts are retained only in the author's private local archive, never in this repository.

> REDACTED 2026-09-07 (privacy pass): sibling-project names and
> out-of-repo local paths in this report were replaced with neutral tokens
> ([SIBLING-A]…[SIBLING-J], ~) before publication; originals preserved in
> the author's private pre-rewrite bundle.

Task: repo-wide audit for (1) hardcoded local filesystem paths and
sibling-project references, (2) AI-authorship references in code
comments/docstrings and commit messages, (3) stale documentation claims —
followed by fixing actionable findings, documenting the no-AI-reference
rule as a visible pre-commit convention, and committing the accumulated
closed work as separate, descriptive commits.

Evidence classification used throughout: MEASURED (a test/run produced
the number) / CALCULATED (derived from measured values) / OBSERVED (raw
artifact inspected) / DOCUMENTED (a prior report asserts it; spot-checked
where cited) / PROJECTED (expectation, not evidence) / UNKNOWN.

Status: COMPLETE — final commit = §5 row 14.

## 0. Repository state at task start (MEASURED/OBSERVED)

- HEAD = `68434e6` ("P0 human gate: deterministic case identity, draft
  hygiene, approval surface"), parent `e6770b5`. OBSERVED via `git log`.
- **Task-premise correction (OBSERVED):** the task brief said "no pushed
  history (there is none yet — confirm this)". This is FALSE for the repo
  as found: remote `origin` EXISTS
  (`noreply@example.com:el-informatico/reconciliation-investigator.git`) and
  `origin/main` = `e6770b5` — i.e. history through `e6770b5` IS already
  pushed. What IS true: `68434e6` is local-only (`main` is "ahead 1").
  Consequence honored: nothing already-pushed is rewritten anywhere in
  this task; the only history modification is amending the never-pushed
  `68434e6`, which does not touch `origin/main`.
- Local branch `stage2-pre-rewrite-backup` (316835f) exists — preserved
  pre-rewrite backup history, local-only, left untouched.
- Uncommitted inventory: 17 tracked-modified files + 47 untracked paths
  (`git status --porcelain`, MEASURED). `.env` correctly absent
  (gitignored).
- Git identity: `juanz <204210901+el-informatico@users.noreply.github.com>`
  (OBSERVED via `git config`), matching the canonical identity established
  by the stage-2 history work.

## 1. Method

- Three parallel read-only audit agents (0a paths/sibling sweep; 0b+
  0c human-gate commit inspection, convention search, secret scan; AI-
  reference + stale-claim sweep). Every load-bearing hit re-verified by
  the coordinating session before any fix (this report lists only
  verified hits).
- Frozen-evidence boundary per project convention: dated audit/evidence
  records under `agent-memory/**` and `docs/*-2026-09-*` are historical
  records; findings in them are REPORTED, never edited (annotate-don't-
  erase, reaffirmed in D-2026-09-05-01).
- Live-code path findings are fixed in code (behavior), not in comments
  describing behavior — the same philosophy as the original
  `probes/probe_common.py` fix.

## 2. Phase 0 audit findings

Three parallel read-only audit agents (paths/siblings; AI-references +
stale claims; human-gate commit + conventions + secret scan); every
load-bearing hit re-verified directly by the coordinating session before
being acted on. Hit counts below are MEASURED (grep over the full tree,
including untracked files and --no-ignore passes over gitignored
artifacts; zero hits verified for `/Users/`, `C:\Users`, `C:/Users`,
`/root/`, `/Volumes/`, `D:\` everywhere).

### 2.1 AI-authorship references (Phase 0a/0b)

**Commit messages on main (all 21, subjects + full bodies, MEASURED):**

| Finding | Location | Disposition |
|---|---|---|
| `Co-Authored-By: Claude Code <test@example.com>` | `68434e6` body line 43 (the only hit on main) | **ACTIONABLE** — the commit is local-only (ahead 1 of `origin/main`); amended in place (Phase 1) |
| `CLAUDE_PROJECT_DIR` env-var mention in an evidence sentence | `f067bcd` [CORRECTED 2026-09-07 — commit pruned by the agent-memory excision rewrite; see the operative execution plan's §2.4 commit map] body line 4 ("Bootstrap close-out", already pushed) | ALLOWED — tooling reference, not attribution; pushed history is not rewritten |
| 2 trailers + 1 "GLM-5.3 via Z.AI" subject | `stage2-pre-rewrite-backup` (316835f, 8c13fc2, 3e194f1) — local-only preserved pre-rewrite backup | FROZEN — deliberate provenance record; untouched |

**Code files (*.py, *.sh, *.toml, config): ZERO attribution strings.**
All raw matches of claude/anthropic/gpt/generated patterns are allowed
subject matter, individually reviewed: credential-policy prose
(`agents/model.py:4-6,55,64` incl. a RuntimeError message string;
`tests/test_model_config.py:2-3,18-30`; `.env.example:9-12`;
`deploy/README.md:20-23`), tooling/harness references (`CLAUDE.md:41`
language policy; `.gitignore:14`; `scripts/guard-dangerous-commands.sh:5`;
`scripts/guard-no-agent-teams.sh:5`; `scripts/ares-launch.sh` — the
launcher binary it execs; `.claude/settings.json:9,20`;
`.claude/agents/*.md`; `README.md:97` file-tree entry naming CLAUDE.md),
model names (`GPT-OSS-120B` in probes/evals docstrings), Apache-2.0
boilerplate (`LICENSE:115` "generated by the Derivative Works"), and a
`.pytest_cache` node id (gitignored artifact).

**68434e6 file contents (0b): ZERO local paths, ZERO sibling names,
ZERO AI references across all 14 files** — verified twice (agent + direct
grep by the coordinating session).

### 2.2 Local paths / sibling-project references (Phase 0a)

**ACTIONABLE — live code (fix in Phase 1):**

| # | file:line | content | note |
|---|---|---|---|
| 1 | `probes/probe_groq.py:110` | `Path("~/projects/reconciliation-investigator/agent-memory/evidence")` | argparse `--evidence-stem` fallback default; behavior, not comment |
| 2 | `probes/probe_gemini.py:102` | `default="~/.../evidence/gemini-probe-2026-09-04"` | same |
| 3 | `probes/probe_cerebras.py:99` | `default="~/.../evidence/cerebras-probe-2026-09-04"` | same |
| 4 | `agents/model.py:15` | "the same validated, tool-calling-proven Groq configuration as [SIBLING-B] (see that repo's application yml and decisions D007/D010/D012)" + "its lesson L007" | sibling-repo citation in a module docstring (tracked-clean; also in pushed HEAD) |

All three probe paths were themselves flagged as a known follow-up
inside D-2026-09-05-01 ("own-repo absolute evidence-stem defaults …
NOT changed here"). The earlier sibling-`.env` defaults
(`HEAD:probes/probe_common.py` etc.) are already remediated in the
working tree — those fixes are part of the uncommitted closed work.

**INTERNAL-EXPECTED (no action):** `ares` / `AresV2` / `Ares V2`
references are this repo's own governance framework —
`scripts/ares-launch.sh` (the launcher this repo's CLAUDE.md makes the
mandatory entry point), verify.sh/guard/hook headers, `.gitignore:1,4`,
`pyproject.toml:1,11`, `tests/test_smoke.py:1`, `.claude/agents/*.md`,
`CLAUDE.md`, and provenance lines in `agent-memory/decisions.md` /
`bootstrap-report.md` / task contracts. Removing them would contradict
the repo's own enforcement wiring.

**FROZEN EVIDENCE (report-only; annotate-don't-erase):** ~2,450
`~/...` lines inside `agent-memory/evidence/**` run logs and
tracebacks (venv paths, uv cache, repo-internal frames) plus dated
audit reports quoting historical paths — full inventory in the audit
agents' reports; representative: `agent-memory/decisions.md:70,119`
(`[REDACTED]` — the only `/mnt/c/` hits in the
tree, inside 2026-09-04 decision prose recording the spec-file
provenance), `decisions.md:255,282,308,309,361,366` (sibling
citations in decision prose), `docs/final-doc-config-cleanup-2026-09-05.md:130,140-141,156,158-159`
(quoted pre-remediation code), `docs/provider-feasibility-*.md`
(tracked-clean dated reports), the `docs/git-*` audit chain,
`agent-memory/evidence/groq-probe-{[SIBLING-A],[SIBLING-B],repo-key}-2026-09-04.txt:1`
(env_file lines). These are historical records of runs/decisions that
happened on this machine; editing them is prohibited by the standing
evidence rule.

**Username `juanz` outside path strings: ZERO in live code, config, or
current-facing docs.** All occurrences are git-identity records inside
dated audit docs and frozen evidence (e.g.
`docs/git-identity-audit-stage1-2026-09-05.md`, one `ls -la` line in an
evidence log).

**Residual (no action taken, documented):** `README.md:183` "Built with
Ares v2 as the agentic build engine, driven by GLM-5.3" — a deliberate
build-engine disclosure in a current-facing doc (existed in HEAD as a
linked form; the editorial pass removed the dead `github.com` link).
README.md is held uncommitted per §6, so this line is noted, not judged.

### 2.3 Secrets (Phase 0b/0c)

**Zero real credentials found anywhere**: all 229 untracked
commit-candidate files scanned (all of `agent-memory/evidence/**` +
the named evals/tests/docs) — no `sk-`/`gsk_`/`AIza`/`ya29.`/`ghp_`/
`AKIA`/`xox` shapes, no Bearer literals, no private-key blocks, no
credential-shaped assignments. Two scanner hits resolved benign:
`orchestrator/human_gate.py:32-33` `EVAL_MODE_DEV_KEY` (committed
non-secret by design; production requires `CORRECTION_TOKEN_SECRET`,
never defaulted) and
`agent-memory/evidence/token-canary-2026-09-04/token-summary.json:92`
(a JSON key NAME, `requested_input_tokens_per_attempt`, not a value).
`.env` is properly ignored (`git check-ignore` → `.gitignore:10`),
exists mode 600, never read, never in `git status`. No file >1MB under
`agent-memory/evidence/`; the 4.2MB `*_report.json` at repo root is
gitignored by pattern.

### 2.4 Stale documentation claims (Phase 0a)

**Working tree: ZERO stale claims** across README.md,
docs/EVALUATION.md, docs/DEVPOST-DRAFT.md, docs/build-contract.md,
deploy/README.md, probes/README.md, .env.example,
docs/credential-alternatives-prompt.md, pyproject.toml, LICENSE:
- No "MIT" claim anywhere; pyproject now declares
  `license = "Apache-2.0"` (PEP 639); LICENSE copyright is filled
  ("Copyright 2026 el-informatico"); README states Apache 2.0.
- Z.AI/Anthropic path correctly described as removed/reserved-for-
  Claude-Code everywhere current; the historical prompt doc is
  quarantined with a SUPERSEDED banner (uncommitted +15 lines).
- probes `--env-file` documented as required/no-default everywhere.
- Provider facts (Groq app / Gemini Flash-Lite judge / Cerebras no-go)
  consistent in all current docs.
The stale versions live in HEAD (`deploy/README.md:21` GLM/Z.AI line,
`probes/README.md:14,46-47` sibling defaults,
`docs/credential-alternatives-prompt.md` unquarantined, pyproject
license field absent) — i.e. **the Phase 3 commits are themselves the
fix**; reverting the uncommitted work would reintroduce all four.

### 2.5 Existing no-AI-reference convention (Phase 0c)

**Visible rule in the pre-commit reading path today: NO.** No
CONTRIBUTING* anywhere, no `.github/`, no commit template
(`git config commit.template` unset; no `.gitmessage*`).
`scripts/hooks/pre-commit` execs only the segregation guard — nothing
inspects commit messages.
  [CORRECTED 2026-09-06, later commits — both halves now inverted:
  9e2339e added scripts/hooks/commit-msg (something DOES inspect
  commit messages), and cde3e6f (D-2026-09-06-03) replaced the exec
  with sequential aggregation of the segregation and sensitive-content
  guards (pre-commit no longer execs only the segregation guard).]
The convention exists as prose in
currently-UNTRACKED stage-2/3 reports (git-stage2-final-report §7,
git-stage3-pending-work-audit:275, git-stage3-final-report §6,
commit-history-audit §1.3a) and nowhere in `agent-memory/decisions.md`
(zero commit-style entries in 394 lines). README has no contributor
section. CLAUDE.md carries a language policy, not an attribution rule.
Empirical confirmation: the trailer regressed on `68434e6` with
nothing firing — the rule is documentation-only and unenforced.

### 2.6 Operational observations

- A second live session on this repo was observed during the audit
  (separate `claude` process, different shell ancestry; legal under the
  2-session concurrency cap). Working-tree content was byte-stable
  across three full captures spanning ~40 minutes (same 17
  tracked-modified files, same diffs). Drift protection adopted: git
  status re-verified immediately before every commit. OBSERVED.
- Agent A's "18 tracked-modified files" was a miscount; direct count is
  17 (verified twice). OBSERVED/MEASURED.

## 3. Phase 1 fixes applied

Architect gate (Tier C, split verdict): PROCEED-WITH-CONDITIONS on the
code fixes, the amend, CONTRIBUTING.md, the decisions append, and the
commit plan; ESCALATE-to-human on the two enforcement-surface items
(commit-msg hook, CLAUDE.md rule) — see §4.

### 3.1 Live-code fixes (before → after, all verified)

1. `probes/probe_groq.py` (post-parse fallback, was lines 109-112):
   `Path("~/projects/reconciliation-investigator/agent-memory/evidence")`
   → `Path(__file__).resolve().parent.parent / "agent-memory" / "evidence"`
   (the per-tag filename join unchanged).
2. `probes/probe_gemini.py` (argparse `--evidence-stem` default):
   absolute literal →
   `str(Path(__file__).resolve().parent.parent / "agent-memory" / "evidence" / "gemini-probe-2026-09-04")`.
3. `probes/probe_cerebras.py`: same pattern with
   `cerebras-probe-2026-09-04`.
4. `agents/model.py:12-19` (docstring only): dropped the sibling
   citation "as [SIBLING-B] (see that repo's application yml and
   decisions D007/D010/D012)" and "imported from its lesson L007";
   kept the full quota-discipline rule; the POLICY paragraph (lines
   3-12) is byte-identical.

Equivalence: CALCULATED — `__file__`.parent.parent of `probes/*.py` is
the repo root, so each default resolves to the same evidence directory
the absolute literal hardcode did, independent of where the repo is
cloned. Verification (MEASURED): `py_compile` 4/4 OK; `--help` rc=0 in
all three probes; `grep -rn '/home/<LOCAL-USER>' probes/ agents/ tools/
orchestrator/ approval/ evals/ tests/` → ZERO hits;
`pytest tests/test_model_config.py` → 4 passed.

### 3.2 Amend of 68434e6 (message-only)

Precondition (MEASURED, per architect condition): full-tree
`rg --no-ignore 68434e6` — the ONLY references are in this report
(the task's own living document); zero in frozen docs, evidence, or
tracked files, so no committed record can be orphaned by the hash
change. Mechanics per condition: empty index (`--only`), post-amend
tree-identity diff and one-line message delta. Result: see §5.

### 3.3 Findings deliberately NOT fixed (with the governing rule)

- ~2,450 `~/...` lines in `agent-memory/evidence/**` run
  logs/tracebacks and quoted paths in dated reports — frozen evidence,
  annotate-don't-erase (D-2026-09-05-01 reaffirms exactly this class).
- `agent-memory/decisions.md:70,119` `[REDACTED]` provenance lines —
  frozen append-only decision prose.
- `ares`/`AresV2` framework references — internal-expected (the repo's
  own governance wiring: launcher, guards, verify.sh, CLAUDE.md).
- `probe_groq.py --env-tag` choices `[SIBLING-A]`/`[SIBLING-B]` — kept by
  explicit human ruling D-2026-09-05-01 ("kept as evidence labels").
- `README.md:183` "Built with Ares v2 ... driven by GLM-5.3" — honest
  build-engine disclosure in a current doc; the file is held uncommitted
  (§6). Residual for the human, not a rule violation.

## 4. Phase 2 — no-AI-reference rule documentation

The architect gate escalated the two enforcement-surface items to the
human (scripts/** and CLAUDE.md are Tier C territory); the human
authorized both directly (interactive question, 2026-09-06). Chosen
locations and why each counts as "read before commits are made":

1. **`CONTRIBUTING.md` (new, repo root)** — canonical rule text. The
   standard first stop for humans preparing to commit to a public
   repo; referenced from CLAUDE.md.
2. **Project `CLAUDE.md`** — one bullet placed before "## Language
   Policy". CLAUDE.md is loaded into EVERY agent session in this repo
   before any tool runs — for AI-made commits (how this repo's commits
   are actually produced) it is literally read before every commit.
3. **`scripts/hooks/commit-msg` (new, executable, committed
   100755)** — mechanical gate, wired through the pre-existing
   `git config core.hooksPath scripts/hooks`; it executes AT commit
   time, which is the strongest form of "read". Blocks attribution
   shapes only: `Co-Authored-By:` trailers naming AI vendors,
   "generated/written/authored/assisted with|by <AI tool>" lines,
   robot-emoji signatures. Smoke-tested 6/6 before first use
   (MEASURED): trailer BLOCK, generated-with BLOCK, emoji BLOCK;
   clean PASS, human co-author trailer PASS, "remove the Anthropic
   path" subject PASS. Honest limits (in the hook's own header):
   `--no-verify` bypasses it; it sees only the message file; and it
   binds every session committing here, including concurrent ones.

Exact rule text (CONTRIBUTING.md, abridged to the normative core):
"Commit messages, code comments, and docstrings in this repository
must never carry AI-tool attribution or authorship references: no
Co-Authored-By trailers naming an AI tool or vendor; no
'Generated with ...'/'Written by ...'/'Assisted by ...' credit lines
for AI tools, and no robot-emoji signatures; no prose in a comment or
docstring claiming an AI tool authored the code it sits in.
Mentioning an AI tool as subject matter is fine and sometimes
required." CLAUDE.md carries the one-bullet summary with the same
scope. The rule deliberately does NOT ban honest tooling disclosures
(e.g. README's "Built with Ares v2 ... driven by GLM-5.3" line), per
the architect's scoping condition.

## 5. Phase 3 — commits created

`origin/main` is untouched at `e6770b5` throughout (nothing pushed;
no branches or tags created; `stage2-pre-rewrite-backup` untouched).
`68434e6` was **amended in place, message-only** (human-directed by
task §3c for exactly this finding class): new hash `7c81f61`, tree
byte-identical (`git diff 68434e6 7c81f61` — empty), message delta =
exactly the removed trailer line + its blank, history position
preserved (still first above `e6770b5`; the accumulated-work commits
stack ON TOP, so the record honestly shows the closed work was
committed after the human-gate commit, not reordered before it).
Zero references to the old hash existed anywhere outside this report
(MEASURED, §3.2).

| # | hash | subject | contents |
|---|---|---|---|
| — | `7c81f61` | P0 human gate: deterministic case identity, draft hygiene, approval surface | amended `68434e6` (trailer removed; content unchanged) |
| 1 | `9e2339e` | Make the no-AI-attribution commit rule visible and enforced | CONTRIBUTING.md, CLAUDE.md bullet, scripts/hooks/commit-msg |
| 2 | `cc6229d` | Fix eval ground-truth leak; strip seed annotations from tool returns | evals/run_evals.py, tools/{seed_data,legacy_system,modern_system,transactions}.py, tests/test_eval_ground_truth_leak.py, leak audit+fix docs |
| 3 | `ea3b7f4` | Editorial pass: license metadata, EVALUATION and DEVPOST docs | LICENSE, pyproject.toml, .env.example, docs/EVALUATION.md, docs/DEVPOST-DRAFT.md, final-doc-config-cleanup doc |
| 4 | `11488c6` | Correct Z.AI credential-path docs; quarantine historical prompt | deploy/README.md, docs/credential-alternatives-prompt.md |
| 5 | `79607f5` | Add token-workload audit and measured one-case canary | token-workload docs ×2, evals/token_canary.py, offline test, evidence dir |
| 6 | `170fb84` | Require explicit --env-file in probes; drop sibling .env default | probes ×6, remediation doc, decisions.md D-2026-09-05-01 hunk |
| 7 | `0811fbe` | Make probe evidence stems repo-relative; de-cite sibling in model doc | probes ×3 (stem hunks only), agents/model.py docstring |
| 8 | `06f49c8` | Add Gemini-judge feasibility notes, canary and 5-case harness | agent-memory notes ×2, evals ×2, offline tests ×2, validation docs ×2, evidence dirs ×2 (35 files) |
| 9 | `3f1b89d` | Add Groq parsing-retry canary and provider probe evidence | groq-preflight note, retry canary + offline test, groq probe/replay evidence ×3 |
| 10 | `1531f92` | Record leak-free 5-case validation runs and evidence | clean-5case + gemini-groq final validation docs, evidence dirs ×2 (57 files) |
| 11 | `9d06252` | Close case-4 tool-param fabrication audit chain with index | case-4 docs ×5 |
| 12 | `d7c3a90` | Document git identity audit, history rewrite, publish plan | git stage1-3 docs ×6, commit-history-audit, state-and-gap, rewrite evidence dir (12 files) |
| 13 | `97f4313` | Add human-gate task plan and e2e run evidence | human-gate-task-plan, evidence dir (4 files) |
| 14 | (this commit) | Document local-path/AI-reference audit; add decision D-2026-09-06-01 | this report + decisions.md D-2026-09-06-01 append |

**Defect and repair disclosed:** the first pass mixed this task's
evidence-stem fixes into commit 6 (the stem edits sat in the same
working-tree probe files when they were staged), leaving commit 7's
message claiming changes it did not contain. Repaired by a local
mixed reset of the three affected commits and a deterministic
re-split (stem hunks temporarily reverted, remediation committed,
stems re-applied, re-committed) — all before any push. Final tree
identical; commit 6's stats changed 542/32 -> 539/29 accordingly.
OBSERVED + MEASURED.

Per-commit drift protection: staged set verified via
`git diff --cached --name-only` before every commit (the concurrent
second session introduced no changes — working tree remained
byte-stable across the whole sequence; final status shows exactly
the two deliberate holdovers).

## 6. README.md / tools/seed_data.py entanglement disposition (3d)

- **`tools/seed_data.py`: SPLIT, committed.** Its only uncommitted
  hunk (`strip_seed_annotations`, +25 lines) is pure leak-fix content;
  the human-gate hunks (`canonical_case_id` etc., +68) were already
  committed inside `68434e6`. No entanglement remained — the hunk
  joined the leak-fix commit (`cc6229d`).
- **`README.md`: HELD UNCOMMITTED.** Its single ~107-line diff hunk
  interleaves the editorial rewrite ("What this is", "Models &
  wiring", "Running", "Evaluation") with human-gate prose written on
  top of it (scoping-decision paragraph naming the `approval/`
  package, the repo-tree `approval/` lines, the `approval.cli`/
  `approval.web` run commands, and a "Remaining work" bullet citing
  the human-gate validation doc). Splitting would require authoring
  an intermediate README that was never reviewed (the editorial pass
  predates the human-gate edits, and its own "remaining work" wording
  is unknowable without rewriting history's content). Per 3d's
  instruction this is reported explicitly and the file is left
  uncommitted rather than risk mixing unrelated work. DISPOSITION:
  human decision pending; the editorial+human-gate README delta is
  preserved in the working tree.

## 7. Test-suite counts before/after (3e)

- Before Phase 3 commits (after Phase 1 code fixes): **190 passed**
  in 6.78s, zero failures/skips (MEASURED, `uv run --locked pytest -q`).
- After all Phase 3 commits: **190 passed** in 6.60s, zero
  failures/skips (MEASURED). Counts identical — the grouping/staging
  process broke nothing.
- verify.sh was NOT run end-to-end because step 6 is the LIVE Groq
  benchmark (standing no-benchmark constraint; consistent with the
  human-gate task's "step 6 excluded by contract"). The offline steps
  were replicated individually per the architect's substitution
  condition: segregation guard PASS, `uv sync --locked` clean (84
  packages), pytest 190 passed (all MEASURED above).

## 8. Final git log (short form, e6770b5..HEAD plus anchor)

```
97f4313 Add human-gate task plan and e2e run evidence
d7c3a90 Document git identity audit, history rewrite, publish plan
9d06252 Close case-4 tool-param fabrication audit chain with index
1531f92 Record leak-free 5-case validation runs and evidence
3f1b89d Add Groq parsing-retry canary and provider probe evidence
06f49c8 Add Gemini-judge feasibility notes, canary and 5-case harness
0811fbe Make probe evidence stems repo-relative; de-cite sibling in model doc
170fb84 Require explicit --env-file in probes; drop sibling .env default
79607f5 Add token-workload audit and measured one-case canary
11488c6 Correct Z.AI credential-path docs; quarantine historical prompt
ea3b7f4 Editorial pass: license metadata, EVALUATION and DEVPOST docs
cc6229d Fix eval ground-truth leak; strip seed annotations from tool returns
9e2339e Make the no-AI-attribution commit rule visible and enforced
7c81f61 P0 human gate: deterministic case identity, draft hygiene, approval surface
e6770b5 Add bounded retry for Groq parsing failures   <- origin/main (pushed; untouched)
```

(The final audit-report commit is added on top of `97f4313`; see §5
row 14.)

## 9. Claim classification summary

- MEASURED: pytest 190/190 before and after; hook smoke matrix 6/6;
  zero-hash-reference sweep; tree-identity diff empty; per-commit
  staged-set lists; porcelain counts 66→71→(final) 2; commit
  stats; grep hit counts in §2.
- CALCULATED: evidence-stem default equivalence (repo root via
  `__file__`); the 3-line commit-6 stat delta attributability.
- OBSERVED: the second live session (PID/cwd/ancestry); agent A's
  mid-audit mtime claim (not reproduced; content stable); amend
  message delta lines 43-44.
- DOCUMENTED: stage-2 rewrite trailer purge (git-stage2-final-report
  §7); D-2026-09-05-01 rulings; human-gate report's 155→190 history.
- PROJECTED: hook prevents future attribution regressions (design
  intent; bypassable via --no-verify — stated as a limit, not a
  claim).
- UNKNOWN: what the concurrent second session is doing (idle/read-
  only as far as three content captures show); which frozen evidence
  .log files future tasks may force-add (current convention: skipped
  by *.log ignore).

## 10. Independent verification (adversarial gate + post-commit fan-out)

- **Reviewer gate: ACCEPT** — "every claim I could test held." Four
  LOW/NOTE findings, none disqualifying: (1) hook exec-bit was
  unverifiable with its read-only toolset — CLOSED by the final-state
  audit below (committed mode 100755); (2) it read the report
  mid-flight, before the §4-§9 edits landed, so its "(to be filled)"
  observation describes a superseded snapshot; (3) the /tmp evidence
  pack was stat-truncated — it compensated via direct file
  verification; (4) README's GLM-5.3 build-engine line — accepted
  residual, routed to the human (§3.3).
- **Final-state audit agent: 6/6 PASS** (MEASURED). origin/main
  untouched at e6770b5; ahead 14 (amend + 13); exactly 3 refs (no new
  branches/tags); amend diff empty + message clean + identity
  canonical; zero attribution shapes across all 14 commit messages
  (6 raw vendor-word hits, all technical/policy prose); zero
  `/home/<LOCAL-USER>` in committed *.py/*.sh/*.toml; the 4 Claude-word hits in
  *.py are the credential-policy subject-matter lines; working-tree
  delta exactly README.md + decisions.md (a pure 36-line EOF append)
  + this report; scripts/hooks/commit-msg committed at 100755; the
  old hash 68434e6 is unreachable from any branch (reflog only, never
  pushed).
- **Docs cross-reference agent: zero broken references / zero false
  claims** (OBSERVED) across the committed current-facing docs —
  including line-precision citation checks and an independent
  confirmation that the hook is live via core.hooksPath. Side
  observation: the GitHub remote is currently PRIVATE (gh repo view).
- **QA replication agent: PASS** (MEASURED) — 5/5 offline verify.sh
  steps replicated (preflight uv 0.12.9; segregation guard + both
  hooks executable; uv sync --locked clean; pytest **190 passed in
  5.90s**) plus the hook mechanical check (trailer message BLOCK rc=1;
  clean message rc=0); no live/network model calls; repo unmodified.
