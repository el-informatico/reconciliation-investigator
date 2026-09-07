# State and gap analysis — submission readiness (2026-09-05)
> AMENDED 2026-09-07: this report references the agent-memory/ directory, which was removed from repository history by the 2026-09-07 excision rewrite; those artifacts are retained only in the author's private local archive, never in this repository.

**Status: READ-ONLY AUDIT COMPLETE. Every engineering claim in the coordinating
assistant's context is CONFIRMED against the repository with zero discrepancies;
the offline suite is green at 132/132. What is missing is the submission-facing
layer: the entire validated work product since HEAD `316835f` is uncommitted,
no git remote exists, the root README is stale (7 dangling paths, zero run
commands, MIT link to a nonexistent LICENSE), and no submission artifact of any
kind (draft, video, script, team info) exists in the repo.** (MEASURED/OBSERVED)

## 0. Method, scope, and claim-classification legend

This report is the only file written by this task (per the task's OUTPUT
instruction; everything else was read-only). Two delegated read-only audits
(documentation/submission inventory; security/reproducibility sweep) plus
main-session verification are its inputs. The only executions were the offline
pytest suite and `scripts/guard-segregation-of-duties.sh` (both explicitly in
scope; the guard is a grep tripwire and wrote nothing — it exits 0 silently).
No live LLM/API call, no benchmark, no canary, no `verify.sh` (its step 6 is a
live benchmark), no git mutation, no commit/stage/push. `.env` was never
opened; no credential value appears in this report. (OBSERVED — session record)

Legend (tags appear inline on every substantive claim):

- **MEASURED** — directly measured this session by executing a command (pytest, guard, git plumbing).
- **OBSERVED** — directly seen in repository files/listings this session.
- **DOCUMENTED** — stated in the project's own docs/reports; accepted as documented, not re-derived (per task instruction).
- **CALCULATED** — arithmetic derivation from measured/observed values.
- **PROJECTED** — forward-looking estimate. (None are made in this report.)
- **UNKNOWN** — not verifiable within this task's constraints.

---

## 1. Repository state

### 1.1 Baseline and working tree

- HEAD = `316835f` ("Groq two-key feasibility…"), the last commit; stash list
  empty. (MEASURED)
- Tracked modifications vs baseline: exactly 5 files, `+42 insertions(−1
  deletion)` — `agents/classifier.py` +2, `agents/detector_investigator.py`
  +2, `agents/reporter.py` +2, `tests/test_tools.py` +35,
  `tools/case_management.py` 1 line changed. Full diff reviewed: the builder
  changes are precisely the retry wiring (one import + one
  `retry_strategy=GroqParsingFailedRetryStrategy()` line each); the
  case_management change is precisely the `correction_draft_id: str | None`
  annotation; the test change is precisely the nullability regression test.
  (MEASURED `git diff --stat`; OBSERVED full diff)
- Untracked set: `agents/retry.py`; 9 `docs/*.md` reports; 4 `evals/*` canary
  drivers; 5 `tests/test_*_offline.py` files; 5 `agent-memory/evidence/`
  directories + 3 probe-evidence files; 3 `agent-memory/*.md` notes.
  (MEASURED `git status --porcelain`)
- **Git remote: NONE configured** (`git remote -v` empty); branch `main` has no
  upstream. The repository is local-only. (MEASURED)
- No discrepancy vs the described state: the coordinating assistant's context
  ("retry implemented+wired, fix implemented, canonical report present") maps
  one-to-one onto the tree above. (OBSERVED)

### 1.2 `.env` and lockfiles

- `.env`: present at repo root, 237 B, mode `0600`; gitignored via
  `.gitignore:10`; not tracked; **never committed in any revision**
  (`git log --all --oneline -- .env` / `-- '*.env*'` empty). Contents not
  inspected, per constraints. (MEASURED/OBSERVED)
- Lockfiles: `uv.lock` is the only one (no requirements/poetry/Pipfile);
  present, **tracked**, and **unmodified** in the working tree. This matches
  the documented policy (docs/gotchas.md:35-37 — committed lock,
  `--locked` enforcement in `scripts/verify.sh` steps 4-5). (MEASURED/OBSERVED)
- Minor: `.gitignore:12` whitelists `!.env.example` but **no `.env.example`
  exists** — anticipated but never created (gap 6.6). (OBSERVED)

### 1.3 Implementation vs the described state — file-by-file confirmation

| Claimed | Actual | Verdict |
|---|---|---|
| `GroqParsingFailedRetryStrategy` in `agents/retry.py` | `agents/retry.py:112-126`; narrow verbatim-prefix matcher (`:53-55`, `:63-74`), stock bounds inherited, per-Agent fresh-instance rule stated `:35-36` | **CONFIRMED** (OBSERVED) |
| Wired into the three builders | `agents/detector_investigator.py:56`, `agents/classifier.py:44`, `agents/reporter.py:41` — all three pass `retry_strategy=GroqParsingFailedRetryStrategy()`; no other builders exist | **CONFIRMED** (OBSERVED) — line numbers also match the canonical report's own Phase-0c audit exactly |
| `correction_draft_id: str | None` fix in `tools/case_management.py` | `tools/case_management.py:114`, exactly the one-line tracked diff | **CONFIRMED** (OBSERVED) |
| Offline-tested | `tests/test_groq_parsing_retry_offline.py` + `tests/test_groq_parsing_retry_canary_offline.py` present; suite green (§2) | **CONFIRMED** (OBSERVED/MEASURED) |
| Regression test for the fix | `tests/test_tools.py:124-158` (+35 lines): schema `anyOf` string/null on both raw and normalized specs + end-to-end None/str acceptance | **CONFIRMED** (OBSERVED) |

**Discrepancy count: zero.** No item of the described implementation state
failed to match. (OBSERVED)

### 1.4 Canonical report and evidence directory

Both exist. (OBSERVED)

- Report: `docs/groq-retry-active-5case-validation-2026-09-05.md` (463 lines).
- Evidence dir top-level (17 entries, filenames only):
  `adversarial-review.md`, `analysis-digest.json`, `baseline/`,
  `case-01-reversal-not-propagated/`, `case-02-duplicate-transaction/`,
  `case-03-sync-lag-self-resolving/`, `case-04-manual-override-not-reflected/`,
  `case-05-data-entry-error/`, `index.json`, `make-analysis-digest.py`,
  `offline-suite-AFTER-instrumentation.txt`, `post-run-checks.txt`,
  `pre-run-git-status.txt`, `preflight.txt`, `retry-evidence-run.json`,
  `run.log`, `segregation-guard.txt`. (MEASURED `ls -1`)

Headline-figure confirmation (presence check only; not re-derived, per task
instruction):

| Figure (as reported) | Appears in report | Location | Verdict |
|---|---|---|---|
| 5/5 cases rc=0 | Yes | lines 3-4, §4 (`all_exit_zero: true`) | CONFIRMED (DOCUMENTED) |
| 2 `Parsing failed` events / 2 retried / 2 recovered / 0 exhausted | Yes | §5 (line 176), §6 aggregate (lines 209-211), §8 | CONFIRMED (DOCUMENTED) |
| 362,858 total tokens | Yes | §7 line 255 — labeled CALCULATED in-report from MEASURED addends 58,413 + 304,445 | CONFIRMED (DOCUMENTED) |
| 125/125 OTel parity | Yes | §9 lines 275-277 | CONFIRMED (DOCUMENTED) |
| 93.0% judgeable pass rate | Yes | §10 lines 282-283 — labeled CALCULATED in-report (66/71) | CONFIRMED (DOCUMENTED) |
| GO WITH CAVEAT | Yes | line 4 and §15 line 433 | CONFIRMED (DOCUMENTED) |

**Internal consistency: no inconsistency found.** The two cheap cross-checks
available without re-derivation both corroborate: the report's §3 claim
"132 passed" equals this session's independently measured 132 (§2 below), and
its §0c wiring line-numbers equal the actual file lines (§1.3). Nothing
required resolution, so nothing was silently resolved. (OBSERVED)

Context claims about open items also check out: the report explicitly carries
the case-4 classifier backlog as NOT resolved (case-04 passing 19/19 is scoped
to that one run, §10 lines 309-311), and records exactly one unrelated Gemini
503 in this run, unretried by design (§8 line 269) — the earlier same-day
judge-side instability (3×5xx) belongs to the *prior* baseline report, where it
is also documented. (OBSERVED)

---

## 2. Test state

- **Current: 132 passed, 0 failed/errored/skipped, 6.58 s** —
  `uv run --locked pytest -q` (the canonical `verify.sh` step-5 command, run
  standalone with pytest's cache disabled; no `EVAL_MODE`). (MEASURED)
- Last documented baseline: **130 passed** (canonical retry report §3 lines
  127-128: "baseline 130 + 2 new tests" for the driver-instrumentation tests).
  Delta **+2, fully accounted for; zero regressions** (132 pass, nothing
  fails). (DOCUMENTED baseline; CALCULATED delta; MEASURED outcome)
- Suite-count trajectory on record: 94 → 126 → 130 → 132 across the
  2026-09-04/05 sessions. (DOCUMENTED)
- Segregation-of-duties guard: **exit 0** (silent pass, no audit-log write).
  (MEASURED)
- `verify.sh` end-to-end was NOT run: its step 6 is a live benchmark — outside
  this task's constraints. Steps 2 (guard) and 5 (pytest) were run
  individually above. (OBSERVED — constraint decision)

---

## 3. Documentation inventory

Currency = describes the actual final architecture (Groq agents
`openai/gpt-oss-120b` + Gemini-native judges `gemini-3.1-flash-lite` ≤14 RPM +
`GroqParsingFailedRetryStrategy` + `correction_draft_id` fix). Limitations =
the three known items (case-4 classifier miss; Gemini 503 instability;
"2.7% sample, not a probability" caveat) where results are cited.

| Artifact | Exists | Current | Limitations | Notes |
|---|---|---|---|---|
| `README.md` (root) | Y | **N** | N/A (cites no results) | Bootstrap-era, never updated since `df44a8c`. Structure block lists 7 nonexistent paths (§6.3); zero setup/run commands; status section still says "no numbers are claimed" though measured runs exist; "Ares v2" link is a bare `https://github.com/` placeholder (README.md:94). Architecture mermaid + segregation text remain correct (README.md:21-42). (OBSERVED) |
| `docs/build-contract.md` | Y | Y (product spec; provider-agnostic) | N/A | Graph/prompts/gate contracts match the system; already specified `correction_draft_id: str | null` (lines 211-213) — the code fix conformed to it. Notes the minimum-viable demo "single-case approval screen" (lines 152-156). (OBSERVED) |
| `docs/gotchas.md` | Y | Y (profile mechanics) | N/A | Dated snapshot with explicit re-verify instruction; no provider claims. (OBSERVED) |
| `docs/groq-retry-active-5case-validation-2026-09-05.md` | Y | **Y — canonical current report** | **Y (all three)** | §1.4 above. (OBSERVED) |
| `docs/gemini-groq-5-case-final-validation-2026-09-05.md` | Y | Y (prior baseline; retry explicitly inactive, correctly framed) | Y (case-4, 3×Gemini 5xx); 2.7% caveat only PARTIAL — sample basis disclosed (lines 246-248) but the "not a probability" wording is absent from this doc | (OBSERVED) |
| `docs/groq-parsing-retry-canary-2026-09-05.md` | Y | Y (superseded by the active-validation report, by design) | Y — **origin of the 2.7% caveat** (lines 75-76, 296-298) | (OBSERVED) |
| `docs/case-4-parsing-failure-audit-2026-09-04.md` | Y | Y (dated audit, pre-retry by design) | Y (statistical caveats, lines 327-340) | (OBSERVED) |
| `docs/correction-draft-id-fix-canary-2026-09-04.md` | Y | Y | Y (scope) | Fix documented lines 5-19. (OBSERVED) |
| `docs/gemini-judge-canary-2026-09-04.md` | Y | Y (dated canary) | Y (scope) | One now-historical line: "default wiring remains Groq" (lines 283-284) — true for `evals/run_evals.py`, not the canonical driver. (OBSERVED) |
| `docs/gemini-judge-5-case-validation-2026-09-04.md` | Y | PARTIAL — accurate as a dated pre-fix NO-GO record; superseded by two 09-05 reports | Y (its own) | (OBSERVED) |
| `docs/provider-feasibility-cerebras-gemini.md`, `docs/provider-feasibility-groq-two-keys-2026-09-04.md`, `docs/token-workload-audit-2026-09-04.md`, `docs/token-workload-canary-2026-09-04.md` | Y | Y (scoped investigations/estimates, honest labels) | N/A | Provenance of the provider split. (OBSERVED) |
| `docs/credential-alternatives-prompt.md` | Y | **N — time capsule** | N/A | Describes the REMOVED Anthropic/Z.AI app path as "how the LLM is accessed today" (lines 41-68); removed same day in `958a815`. Useful provenance; not current. (OBSERVED) |
| `probes/README.md` | Y | Y | N/A | (OBSERVED) |
| `deploy/README.md` | Y | **PARTIAL** | N/A | Placeholder status still accurate ("nothing here deploys anything"), but lines 21-22 still cite the old single-Z.AI-credential rule as current. (OBSERVED) |
| `CLAUDE.md` (project) | Y | Y | N/A | Governance; no provider claims. (OBSERVED) |
| `agent-memory/*` | Y | internal session memory | — | No submission-relevant material (no Devpost draft, video script, checklist — repo-wide search zero matches). (OBSERVED) |
| Devpost/submission/pitch/demo/video/storyboard files | **N** | — | — | Zero matches repo-wide; zero media files of any kind. (OBSERVED) |
| LICENSE / CONTRIBUTING / ARCHITECTURE / SECURITY writeups | **N** | — | — | No LICENSE anywhere despite README's MIT link (README.md:105-107). The only security writeups are internal evidence records. (OBSERVED) |

Architecture explanation: exists only as README mermaid + `docs/build-contract.md`
(no standalone architecture doc). Security model: no standalone writeup (the
material lives in build-contract §s, CLAUDE.md, and validation-report §s).
Evaluation methodology: well covered by the validation docs themselves (drivers,
judges, OTel cross-check, separated failure classes). (OBSERVED)

---

## 4. Submission readiness checklist

Requirements are listed only to the extent evidenced in the repo (README.md:3,
93-94; docs/build-contract.md:4-5; docs/credential-alternatives-prompt.md:18-19):
hackathon = "Agents for Humans" (devpost.com), track = Professional Agents,
deadline = 2026-09-14, built on Strands Agents SDK. **No other requirement
(video length, description format, team size, judging criteria) is evidenced
anywhere in the repo — not inferred here.** (OBSERVED)

| Requirement | Satisfied | Evidence |
|---|---|---|
| Working, validated system (the substance behind any submission) | **Y** | 5/5 rc=0 live validation (DOCUMENTED, canonical report); 132/132 offline (MEASURED); security/segregation PASS (§5) |
| Repo link | **N** | No git remote configured; repo local-only; all validated work uncommitted (MEASURED §1.1) |
| README as judges' entry point | **N** | Stale: 7 dangling paths, zero run commands, MIT→nothing, placeholder URL (OBSERVED §3) |
| Project description (Devpost text) | **N** | No draft anywhere in repo (OBSERVED) |
| Category/track | Partial | Track known and evidenced (Professional Agents); no submission-form artifact (OBSERVED) |
| Demo video / demo assets | **N** | No script, storyboard, recording, screenshots, or GIFs anywhere (OBSERVED) |
| Team info | **N** | Nothing in repo (OBSERVED) |
| LICENSE (README claims MIT) | **N** | File absent (OBSERVED) |
| Demo interface | Partial | Build contract's minimum-viable "single-case approval screen" deferred; shipped as programmatic gate+executor (disclosed, README.md:46-54) (OBSERVED) |
| `.env` handling documented for setup | Partial | Correct in `agents/model.py:9-12` + docs; absent from README; no `.env.example` (OBSERVED) |

---

## 5. Security / reproducibility snapshot

- **Secrets: PASS.** Zero credential values in tracked files, untracked
  docs/evidence, or any git revision. The three name-suspect probe evidence
  files (`groq-probe-repo-key-*.json/.txt`, `groq-replay-probe-*.txt`) contain
  only status codes/rate-limit headers/usage counts — "repo-key" means
  "probed with the repo's key", not "stores the key". All `sk-`-pattern hits
  are the substring in `task-contract-…md` filenames; pickaxe history hits are
  the redaction helper's own detection regexes (probes/probe_common.py:26-28).
  `.env` never committed (§1.2). (OBSERVED/MEASURED — delegated sweep, spot-consistent with §1.2)
- **Credential handling documented = implemented: PASS.** env-wins loader
  (`agents/model.py:34-48`, `:47` is the env-wins line), values never printed,
  loud failure if absent (`:60-66`); Gemini resolver reuses the same loader.
  README contains no credential guidance at all (gap 6.3). (OBSERVED)
- **Segregation of duties: PASS, twice over.** Mechanical guard exit 0
  (MEASURED §2). Semantic sweep: every `apply_correction` occurrence accounted
  for — plain function (`tools/modern_system.py:44`), sole caller
  `orchestrator/correction_executor.py:71` behind HMAC single-use token
  validation (`:63-67`, keys `human_gate.py:70-138`), tests, guards, docs;
  agent tools lists are exactly detector=4 read-only / classifier=none /
  reporter=draft+ticket; the eval-side `SafeActionComplianceEvaluator`
  independently fails any trajectory touching it. The committed EVAL_MODE dev
  HMAC key is documented-by-design non-secret; outside EVAL_MODE the token
  secret is required from env with no default. (OBSERVED)
- **Anthropic-path removal: verified real** — zero `anthropic` references in
  `pyproject.toml` and `uv.lock`. (MEASURED — delegated grep)
- **Command reproducibility: operational commands MATCH; README is the drift.**
  All documented operational commands equal the actual ones (`uv run --locked
  pytest -q` = verify.sh:148; canary/validation invocations incl.
  `--frozen --with google-genai==2.22.0` match their modules). Two drifts: (a)
  README documents NO commands at all and its structure block lists files that
  do not exist; (b) one doc abbreviates verify.sh step 6 as
  "`EVAL_MODE=1 python evals/run_evals.py`" omitting the load-bearing
  `PYTHONPATH=$ROOT` and stdin `'q\n'` (docs/gemini-judge-canary-2026-09-04.md:250
  vs verify.sh:160-172). (OBSERVED)
- **Notes (authorized/disclosed, not leaks):** `probes/probe_common.py:35`
  defaults to a sibling project's `.env` path — human-authorized on record
  (agent-memory/decisions.md:308, commit 316835f), values never printed; a
  future hardening should drop the cross-project default. Root
  `*_evaluation.json`/`*_report.json` are gitignored working copies with
  all-Groq-era numbers; they will not ship. (OBSERVED)

---

## 6. Prioritized gaps (concrete; nothing already satisfied is listed)

1. **Nothing since `316835f` is committed, and no git remote exists.** The
   retry module and its wiring (tracked-but-uncommitted), the fix, all 9 result
   docs, all canary evals/tests, and the entire evidence tree (untracked) are
   invisible to any clone. A repo-link submission built from the current local
   state would show a repo whose last commit predates every validated result.
   Action: deliberate commit of the current work product, create the remote,
   push. (MEASURED)
2. **No submission artifacts exist at all** — no Devpost description draft, no
   team info, no demo video, and not even a video script/storyboard to record
   from. The only public-facing narrative artifact is the stale README.
   Action: author the description + script; record the demo (the 5-case run,
   the gate/executor approval flow, or both are the natural subject).
   (OBSERVED)
3. **README is stale and self-contradictory.** Seven dangling structure paths
   (LICENSE, requirements.txt, data/seed_legacy.json, data/seed_modern.json,
   ui/approval_gate/, deploy/agentcore.yaml, evals/results.md), an MIT badge
   pointing at a nonexistent LICENSE, zero setup/run commands (an evaluator
   cannot reproduce anything from README alone), a "no numbers claimed" status
   section long superseded, and a placeholder Ares URL. Action: rewrite to the
   final architecture + validated numbers + exact commands; add LICENSE or
   drop the MIT claim. (OBSERVED)
4. **Demo surface is programmatic only.** The build contract's minimum-viable
   demo interface (single-case approval screen) is deferred; a demo must
   either run the CLI/eval path live or the deferral must be owned explicitly
   in the submission narrative. (OBSERVED)
5. **`.env.example` missing** though `.gitignore:12` explicitly whitelists it;
   adding it (placeholders only) plus a README setup line closes the
   judge-reproducibility gap cheaply. (OBSERVED)
6. **Minor internal-doc staleness (low priority):**
   `deploy/README.md:21-22` still cites the removed Z.AI credential rule;
   `docs/credential-alternatives-prompt.md` reads as current but describes the
   removed path (fine as provenance if labeled); the step-6 command
   abbreviation (§5); the 2.7% caveat wording absent from
   `docs/gemini-groq-5-case-final-validation-2026-09-05.md` (present in the
   two later docs). (OBSERVED)

Known open items deliberately NOT listed as gaps (already owned elsewhere):
case-4 classifier quality miss and Gemini 503 instability — both documented,
carried, and out of this task's scope per its constraints. (DOCUMENTED)

---

## 7. Claim classification

Every substantive claim above carries an inline tag; this section records the
scheme's application, not a re-listing. (OBSERVED)

- **MEASURED**: git status/diff/remote/stash/log outputs; pytest 132 passed;
  guard exit 0; `.env`/`uv.lock` git-ignore and tracked-status plumbing;
  evidence-dir listing; anthropic-grep zero.
- **OBSERVED**: every file-content verification (retry implementation,
  wiring, fix, report figures' presence, README/doc staleness, segregation
  semantics, loader behavior, absence of submission artifacts).
- **DOCUMENTED**: all figures accepted from the canonical and prior reports
  without re-derivation (5/5 rc=0; 2/2/2/0; 362,858; 125/125; 93.0%; GO WITH
  CAVEAT; 130-test baseline; 94→126→130→132 trajectory).
- **CALCULATED**: test delta +2 (132 − 130); the arithmetic identities noted
  in §1.4's cross-checks.
- **PROJECTED**: none made in this report.
- **UNKNOWN**: (a) `.env` contents — never opened, by constraint; (b) any
  Devpost requirement beyond name/track/deadline/SDK — not evidenced in the
  repo and deliberately not imported from outside knowledge; (c) live-run
  behavior beyond what the (not re-run) validation reports document.

---

## Summary

**Genuinely ready (the engineering substance):** the validated system itself.
The described state is real and exactly reproduced by the tree — retry
implemented, wired at three sites, offline-tested, and live-validated per a
canonical report whose every headline figure is present and internally
consistent; the fix is in and regression-tested; 132/132 offline; secrets
clean across tree and history; segregation-of-duties holds mechanically and
semantically; every operational command is exactly documented somewhere in
docs. (MEASURED/OBSERVED/DOCUMENTED)

**Genuinely missing (the submission layer):** a committed and pushed repo (no
remote even exists), a current README, a LICENSE, any Devpost draft/team info,
and any demo asset down to a script. (OBSERVED)

**Single most submission-critical item, my own assessment:** the version-control
state. Until the work since `316835f` is committed and pushed to a real remote,
every other submission task is building on a repo link that shows none of the
validated work — it is the one gap that makes all other artifacts unreceivable,
and it is also the cheapest to close.
