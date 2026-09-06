# Final documentation/config cleanup — 2026-09-05

Closes the four follow-ups flagged by the editorial pass
(`docs/EVALUATION.md`, README repair, `docs/DEVPOST-DRAFT.md`).
Documentation and config only — no application code. LICENSE holder
decision is final: `Copyright 2026 el-informatico` stays as applied; the
LICENSE file was not touched by this task (its working-tree
modification predates this session — prior editorial pass).

## Summary

| # | Item | Outcome |
|---|------|---------|
| 1 | `pyproject.toml` license field | DONE — `license = "Apache-2.0"` (PEP 639 SPDX string); `uv lock --check` exit 0 (MEASURED) |
| 2 | `deploy/README.md` stale Z.AI rule | DONE — corrected to current policy (minimal in-place fix) |
| 3 | `docs/credential-alternatives-prompt.md` | DONE — HISTORICAL/SUPERSEDED header note; artifact below `---` untouched |
| 4 | `probes/README.md` sibling-`.env` refs | **STOP branch taken** — code-behavior confirmed; security finding escalated for human ruling; NO code and NO README change (per task instruction) |
| 5 | `.env.example` | DONE — created from grep-confirmed inventory, placeholders only; `.gitignore` already excludes `.env` but not `.env.example` (MEASURED, no `.gitignore` change needed); README known-gap line updated |

Nothing staged, committed, or pushed. No application/eval/retry/
human-gate code touched. No benchmarks, canaries, or live LLM/API calls.

## Method

Direct reads/edits for the tightly coupled single-file fixes (items
1–3, 5); five delegated read-only investigations:

1. env-var inventory (repo-wide grep) — item 5 input;
2. `probes/` sibling-`.env` audit — item 4 verdict;
3. Architect gate (OCM) — tier + escalation ruling;
4. documentation-consistency sweep for residual Z.AI-as-current claims — COMPLETE (§ Governance record);
5. PEP 639 / uv packaging research — COMPLETE (§ Governance record);
plus a final adversarial diff review — spawned after all edits landed
(verdict in § Governance record).

## Item 1 — pyproject.toml license field

Before/after (exact diff hunk, `git diff pyproject.toml`):

```diff
 description = "Reconciliation investigator agent system built on the Strands Agents SDK"
+# PEP 639 SPDX expression — matches the LICENSE file. Bare-string form,
+# not the legacy {text=...} table: this is a virtual project with no
+# build backend, so uv (>=0.12 here) is the only metadata consumer.
+license = "Apache-2.0"
 requires-python = ">=3.13"
```

Form rationale: the project is a VIRTUAL uv project — `[project]` with
deliberately NO `[build-system]` (stated in the file header) — so there
is no build backend; uv itself (0.12.9, MEASURED via `uv --version`) is
the sole metadata consumer, and the PEP 639 bare SPDX string is the
current canonical form. Validity is verified empirically, not by
convention:

```
$ uv lock --check
Resolved 89 packages in 1ms
lock_check_exit=0            # MEASURED
```

`uv.lock` was not modified (license metadata is lock-neutral; the
lockfile remains byte-unchanged — OBSERVED via `git status`: uv.lock
not in the modified list).

## Item 2 — deploy/README.md Z.AI rule

Before/after (exact; the stale text is old lines 21–23, in the AWS
credentials bullet):

```diff
 - AWS credentials and region setup — human-provided and human-run; an
   Ares session never invents or stores cloud credentials. Note the
-  standing single-MODEL-credential rule (GLM-5.3 via the one Z.AI
-  credential) is about model access and is unaffected by infrastructure
-  credentials, which remain a human decision.
+  standing model-credential policy (2026-09-04, `agents/model.py`): the
+  Z.AI credential is reserved exclusively for Claude Code — never for
+  this application — and the application itself uses GROQ_API_KEY only.
+  That policy governs model access and is unaffected by infrastructure
+  credentials, which remain a human decision.
```

Section retained (it serves the deployment-credential-inventory
purpose); only the stale claim corrected. Matches `agents/model.py`
docstring policy verbatim in substance (DOCUMENTED + directly verified).

## Item 3 — docs/credential-alternatives-prompt.md

**Approach: historical-annotation header** (the document's primary
purpose was exploring the now-removed option; annotate, don't erase).

A dated `> **HISTORICAL / SUPERSEDED …**` blockquote was inserted
between the title and the "Copy everything below the line" paragraph.
Everything below the `---` separator is preserved byte-identical —
MEASURED: `git diff docs/credential-alternatives-prompt.md` shows a
single +15-line hunk strictly above the artifact (the file was
tracked-clean at session start, so the diff isolates this session's
edit exactly).

Passages identified as describing the removed path as current (original
line numbers, pre-annotation):

- L4 — "exactly how the non-compliant usage works **today**";
- L41 — section heading "The problem — how the LLM is accessed
  **today** (non-compliant)";
- L51–62 — "The violation: our application's eval harness ALSO points
  at that same key/endpoint. In code, `agents/model.py` does:" followed
  by an `AnthropicModel` snippet that no longer exists in
  `agents/model.py`;
- L44–49 — Z.AI env config described as the current dev setup (the
  Claude-Code half of this remains true; the app half does not);
- partial counterweight already present: L67–68 "we already stopped it".

The header enumerates these explicitly so the annotation is traceable
to the passages it covers, and states the current policy + pointer
(`agents/model.py` docstring: Z.AI = Claude Code only; app reads
`GROQ_API_KEY` only, Groq `openai/gpt-oss-120b`).

## Item 4 — probes/README.md sibling-.env: SECURITY FINDING (STOP branch)

**Verdict: the README is accurate, not stale.** `probes/` code actually
reads sibling-project `.env` files BY DEFAULT. Per the task's explicit
STOP instruction: no code fix, no README fix — reported here for a
dedicated follow-up.

Code evidence (OBSERVED, code text):

- `probes/probe_common.py:35` —
  `DEFAULT_ENV_FILE = Path("~/projects/[SIBLING-A]/.env")`
  (comment at :33–34 documents the sibling choice);
- `load_credentials()` really opens/reads it (`:41` exists-check,
  `:44` `read_text`);
- that default is the argparse `--env-file` default in every probe
  (`probe_cerebras.py:93`, `probe_gemini.py:97`, `probe_groq.py:96–97`,
  `probe_strands.py:82`) — so the README's bare invocations
  (`probes/README.md:44–50`) read the sibling file with no flag given;
- `probe_groq.py` additionally takes explicit sibling paths
  (`probes/README.md:46–47` shows `--env-file
  ~/projects/[SIBLING-A]/.env` and
  `.../[SIBLING-B]/.env`).

README passages that would have been "corrected" (they are instead
accurate descriptions of code behavior): lines 12–19 (credentials
bullet), 38 (probe_groq row), 44–50 (invocation examples).

Mitigations present in code (OBSERVED): names-only extraction (only the
requested variable names are parsed); values masked in all stdout and
evidence output by a redactor (`probe_common.py:61–72`); values used
in-process only; all evidence writes land inside this repo
(`agent-memory/evidence/`); request headers never recorded.

Authorization provenance (DOCUMENTED, `agent-memory/decisions.md`, read
directly): D-2026-09-04-12 records the feasibility investigation as
"Authorized", credentials "loaded ONLY by name from the sibling
[SIBLING-A] .env", with an adversarial post-investigation
scan CLEAN incl. exact-value equality vs both `.env`s; D-2026-09-04-13
records the "Authorized two-key re-validation" ([SIBLING-A]
AND [SIBLING-B]), "neither sibling modified", scan CLEAN vs all
three `.env`s. D-12 also rules `probes/` to be controlling-session
territory (like `scripts/`).

Tension requiring the human ruling (escalated by the Architect gate):

- This task's standing constraint: "no sibling-project access".
- Task contract standing constraint
  (`agent-memory/task-contract-001-bootstrap-scaffold.md:122`): "Never
  modify aresV2 or any sibling project" — a modification prohibition;
  the recorded authorization covers name-only READS during the
  investigation.
- `evals/groq_parsing_retry_canary.py:252–253` asserts "no
  sibling-project credential is read or copied" — true of the canary,
  contradicted by the probes' default.
- The feasibility investigation is now CLOSED (D-12/D-13 concluded),
  yet the sibling-default remains the code's silent default.

**Question for the human:** does the sibling-`.env` arrangement remain
accepted now the investigation is closed (in which case item 4 should
be re-scoped to document it WITH its authorization provenance), or
should the probe code be remediated (default to this repo's `.env`, or
require an explicit `--env-file` with no default) — remediation being
controlling-session territory per D-12, explicitly out of scope here.

Unverified by design: whether the sibling paths currently exist on
disk (never checked — no sibling access from this session); whether
probes were ever executed (only `probes/__pycache__/` residue OBSERVED,
indicating at least one past import).

## Item 5 — .env.example

Full variable list discovered by direct grep (delegated, exhaustive;
file:line citations), NOT assumed from memory:

| Variable | Read at | Purpose | In .env.example |
|---|---|---|---|
| `GROQ_API_KEY` | `agents/model.py:59` | app's only model credential (required; RuntimeError if absent) | yes — active placeholder |
| `EVAL_MODE` | `tools/seed_data.py:30`, `orchestrator/human_gate.py:51` | runtime switch; auto-set by entry points (`evals/run_evals.py:78`, `evals/run_sequential.py:36`, `scripts/verify.sh:172`) | documented as do-not-set (not an active entry) |
| `CORRECTION_TOKEN_SECRET` | `orchestrator/human_gate.py:53` | HMAC signing key; required only when EVAL_MODE != "1" | yes — commented entry |
| `GEMINI_API_KEY` | `evals/gemini_judge_canary.py:120` (+ consumers `gemini_judge_5case.py:195`, `groq_parsing_retry_canary.py:247`) | Gemini judge harness (exits if absent) | yes — active placeholder |
| `GEMINI_MIN_INTERVAL_S` | `evals/gemini_judge_canary.py:78` | judge pacer; default "4.3", clamped [0, 3600] | documented with caveat: read at import time, BEFORE the .env loader — must be a real env var; a .env line is inert |
| `CEREBRAS_API_KEY` | `probes/probe_cerebras.py:102`, `probes/probe_strands.py:86` | probes only; read from explicit `--env-file`, never this repo's `.env`; Cerebras ruled no-go (commit d9c6f97) | documented as not-a-.env-var |
| `CLAUDE_PROJECT_DIR` | `scripts/guard-dangerous-commands.sh:54,77`, `guard-no-agent-teams.sh:17` | Claude Code harness-provided | noted (do not set) |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | `scripts/ares-launch.sh:24,66,127` | FORBIDDEN — launcher refuses if set | noted (do not set) |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL` / any `ZAI_*` | — NO code reads anywhere (grep-verified) | forbidden for the app (Claude Code only, per policy) | explicit never-put-here warning |

`GROQ_API_KEY`/`GEMINI_API_KEY` probes read via `--env-file` are the
same names (probes never read this repo's `.env`). Tests set dummy
values only (hermetic). No `.env.example` existed anywhere before
(confirmed by search; `README.md:139` even recorded the gap).

**Post-review correction (claim-by-claim verification):** the first
draft presented `GEMINI_MIN_INTERVAL_S` as an uncomment-into-`.env`
knob; verification showed its sole reader executes at import time of
`evals/gemini_judge_canary.py:78`, BEFORE the `.env` loader runs in
those drivers — a `.env` line would silently do nothing. `.env.example`
now documents it as a real-environment-variable knob with that caveat
(the commented assignment affordance was removed). All other claims
CONFIRMED with file:line evidence, including: loader semantics
(`agents/model.py:34-48`, env-wins), the GEMINI gate's exit-if-absent
behavior in all three judge scripts, `CORRECTION_TOKEN_SECRET`'s
EVAL_MODE-conditional requirement with the committed non-secret dev
key, EVAL_MODE auto-set ordering (a `.env` EVAL_MODE could never
reliably take effect — the do-not-put-in-.env advice is correct), and
zero ANTHROPIC_*/ZAI_* code reads (independent grep).

Created: repo-root `.env.example` — placeholders only
(`your-groq-api-key-here`, `your-gemini-api-key-here`,
`generate-with-openssl-rand-hex-32`); NO real values anywhere in the
file (OBSERVED; also checked by the final review).

`.gitignore` verification (MEASURED, outputs verbatim):

```
$ git check-ignore -v .env
.gitignore:10:.env	.env
$ git check-ignore -v .env.example
.gitignore:12:!.env.example	.env.example
$ git status --porcelain --untracked-files=all | grep -i env
?? .env.example
```

`.env` is ignored; `.env.example` is matched by the negation and shows
as untracked-but-visible — i.e. NOT gitignored. No `.gitignore` change
was needed (the `!.env.example` exception already existed).

Consistency ripple fixed: `README.md` "No `.env.example` exists yet — a
known gap." → "See `.env.example` for a placeholder-only template."
(This session's ONLY README change; all other README working-tree
modifications predate this session.)

## Governance record

- **Architect gate** (delegated): verdict `NO-MAPPING / escalate`. It
  confirmed independently: no Tier-C surface touched (no build-contract
  change, no `apply_correction`/`correction_executor`/`human_gate`,
  frozen files untouched, LICENSE respected), and it re-verified the
  item-4 STOP branch against the probe code itself. Its escalation
  grounds: (a) item-4 needs a human ruling (preserved above), (b) its
  invocation lacked the OCM rule table. Its evidence gaps are closed
  here: diff hunks embedded (items 1–2), `uv lock --check` and
  `git check-ignore` outputs pasted verbatim, report sections
  completed. One stale mark corrected: it recorded `.env.example` as
  absent — it launched before the file was written; on-disk +
  porcelain state above is authoritative. Process disclosure it made:
  same model/credential as the implementing session — a process check,
  not a cross-model review.
- **OCM rule table located**: `agent-memory/task-contract-001-bootstrap-scaffold.md:94–108`.
  Applied by the implementing session (the Architect seat never saw
  it): every executed change is Tier A ("Routine: comments/docs only,
  zero behavior"). Provenance caveat: this mapping is recorded here,
  not re-issued by the Architect seat. Any future item-4 remediation
  would be at least Tier C territory (crossing repo boundaries;
  controlling-session files).
- **Documentation-consistency sweep — COMPLETE.** Verdict: the repo is
  consistent in everything submission-facing (README, CLAUDE.md,
  `docs/EVALUATION.md`, `docs/DEVPOST-DRAFT.md`, build-contract,
  `.env.example`, code, tests, pyproject/uv.lock): every Z.AI/GLM
  mention outside `agent-memory/` is explicitly era-labeled or
  Claude-Code-scoped; zero presented-as-current violations found.
  Today's item-2/item-3 fixes are therefore complete — no sibling
  stale claims remain in scope. (Its README:139 side observation was
  overtaken mid-sweep by this session's edit — the sweep read the
  pre-edit text; the hunk in § Item 5 shows the fix.)
- **PEP 639 / uv packaging research — COMPLETE.** Confirms the chosen
  form with cited sources (PEP 639; docs.astral.sh/uv;
  packaging.python.org pyproject-toml guide; uv changelog): the bare
  SPDX string is the current canonical form; uv's virtual-project
  `[project]` parser accepts-and-ignores the field (it structurally
  cannot error or warn on it); `uv.lock` contains zero license
  references — license metadata is lock-neutral (`uv lock --check`
  exit 0 independently re-confirmed `--offline` by the researcher on
  this repo); the legacy `license = {text = ...}` table is formally
  deprecated (PEP 639) and warning-producing under setuptools ≥77 /
  hatchling ≥1.27. DOCUMENTED (cited) + MEASURED (repo-empirical).
- **Final adversarial review — three lenses, all returned:**
  - **Reviewer gate: ACCEPT.** "Every reproducible factual claim
    (code citations, policy text, probe behavior, D-12/-13 record,
    .gitignore semantics, env-var coverage) verified true on disk."
    Its falsification attempts (repo-wide env-var coverage sweep,
    sibling-.env finding vs probe code/argparse/README/decisions.md,
    report citation hunt) all failed to break the change set. Its one
    citation note is reconciled: `gemini_judge_5case.py:195` is the
    `resolve_gemini_api_key()` call (the consumption point cited);
    `:198` is the refusal string — both correct, no discrepancy. It
    cannot run git/uv (read-only seat): staging/lock claims remain
    covered by this session's MEASURED outputs above. Disclosed
    same-model limitation (process check, not cross-model).
  - **Secrets-leak scan: CLEAN.** Placeholders only; no key-shaped
    strings anywhere (sole regex hits were "task-contract" filename
    substrings); no exposure-inducing instructions; the policy note
    strengthens rather than weakens the Claude-Code-only rule. One
    non-actioned observation: active placeholders are truthy, so an
    unedited copy would later surface as a provider 401 rather than
    the missing-key RuntimeError — rejecting literal placeholder
    strings would be an application-code change (out of scope;
    recorded as optional hardening).
  - **`.env.example` claim verification: 10/10 claims checked; one
    real inaccuracy found and FIXED** (GEMINI_MIN_INTERVAL_S
    import-time read — see Item 5's post-review correction). The
    EVAL_MODE advice was vindicated by loader-ordering analysis;
    ANTHROPIC/ZAI zero-reads independently re-confirmed.

### Residual follow-ups found by the sweep — OUT OF TASK SCOPE (not
### edited here; controlling-session territory)

1. `agent-memory/task-board.json:6` — live, undated state file (read
   by `ares-launch.sh` at every launch) carries the unscoped absolute
   "no second credential anywhere", now false for the app
   (`GROQ_API_KEY`) and judges (`GEMINI_API_KEY`). Needs scoping to
   the build seats by the controlling session.
2. `agent-memory/task-contract-002-implementation.md:80-83` — pinned
   design constraint 6 still states single GLM-5.3 via
   `ANTHROPIC_BASE_URL`/`ANTHROPIC_API_KEY` with no historical
   annotation (unlike the item-3 file). Same
   annotate-don't-erase header indicated.
3. `agent-memory/decisions.md` — no superseding decision entry records
   the Z.AI-path removal / Groq switch (D-2026-09-04-09 stands as the
   latest model-wiring entry; the switch lives only in commit 82d8271,
   the `agents/model.py` docstring, and dated docs). The ledger is
   append-only and controlling-session-owned.

## Git state

Before-state (session start, `git status --porcelain`, tracked mods):
`M LICENSE`, `M README.md`, `M evals/run_evals.py`, `M tools/legacy_system.py`,
`M tools/modern_system.py`, `M tools/seed_data.py`, `M tools/transactions.py`
+ 45 untracked entries — ALL predate this session.

This session changed:

| File | Change | Type |
|---|---|---|
| `pyproject.toml` | license field + comment (hunk above) | modified, tracked |
| `deploy/README.md` | credential-policy wording (hunk above) | modified, tracked |
| `README.md` | ONE sentence (.env.example pointer) | modified, tracked (file already carried prior-pass mods) |
| `docs/credential-alternatives-prompt.md` | header annotation only | modified, tracked (was tracked-clean at session start — hence absent from the before-state porcelain; single +15-line insertion hunk, see Item 3) |
| `.env.example` | NEW | untracked |
| `docs/final-doc-config-cleanup-2026-09-05.md` | NEW (this report) | untracked |

Not touched by this session: LICENSE, all application/eval/tools/test
code, scripts/, probes/, uv.lock, .gitignore. Nothing staged
(MEASURED: `git diff --cached --stat` empty), nothing committed,
nothing pushed.

## Claim classification

- `uv lock --check` exit 0; check-ignore outputs; `?? .env.example` in
  porcelain; empty staged diff; uv 0.12.9; the insertion-only diff
  hunk for `docs/credential-alternatives-prompt.md` → **MEASURED**
- File contents/edits, diff hunks, `.env.example` placeholders-only,
  verbatim-preservation below `---` → **OBSERVED**
- Policy (Z.AI = Claude Code only; app = GROQ only), probe
  authorization record (D-12/D-13), OCM table, "no sibling
  modification" constraint, Cerebras no-go → **DOCUMENTED** (primary
  sources read directly this session)
- Env-var inventory + probe code behavior → **OBSERVED** (exhaustive
  delegated grep with file:line; independently corroborated by the
  Architect for item 4)
- Tier A mapping (rule table applied) → **CALCULATED**
- Sibling paths' current on-disk existence; whether probes ever ran →
  **UNKNOWN** (deliberately unverified — no sibling access)
- No claims in this report are PROJECTED.
