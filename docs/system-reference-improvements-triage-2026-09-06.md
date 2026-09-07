# SYSTEM-REFERENCE §7 — Independent Triage (2026-09-06)

**A re-verified, prioritized action plan for the 2026-09-14 submission.**
Produced from `docs/SYSTEM-REFERENCE.md` §7 (17 items: 7.a.1–7.a.6
deadline-facing, 7.b.1–7.b.11 long-term) by independent re-assessment
against current source — not a restatement of §7. Fifteen of the 17
items' observations were re-verified directly (7.a.5 and 7.b.11 are
relayed — nothing in them is re-verifiable offline); four findings were
re-scoped,
one item was split with one half recommended against, and one long-term
item was **promoted** to pre-submission (7.b.6, on public-flip exposure
evidence §7 did not have).

**Basis**: git HEAD `cac9a80` (= `origin/main`, MEASURED `git rev-parse`,
in sync), working tree clean of modifications to tracked files at the
verification snapshot (19:29:55 UTC 2026-09-06, MEASURED). The offline
suite was **not** executed by this task; "218 passed" is relayed as
DOCUMENTED (SYSTEM-REFERENCE §8.1, MEASURED at this HEAD by that task).
No live LLM/API call, benchmark, canary, or test was run. No existing
file was modified; this file is the task's only output.

**Concurrent-task context (load-bearing for this plan)**: a parallel
session is fixing the five doc-accuracy findings whose fix targets are
`README.md`, `docs/human-gate-e2e-validation-2026-09-05.md`, and
`docs/p0c-closeout-2026-09-06.md` (README ×3 + e2e `:30` + p0c §4 —
the "five findings" recorded when SYSTEM-REFERENCE was drafted). That
session was OBSERVED running (session registry, ~19:26 UTC); **nothing
had landed in the working tree at the snapshot time** (MEASURED
`git status --porcelain`, 19:29:55 UTC). This plan therefore treats
those five items as *in flight, owned elsewhere* and converts them into
a post-merge verification checklist instead of re-recommending the edits.

**Interim status (added 19:37:01 UTC, post-snapshot)**: that task's
edits have since landed **uncommitted** in the working tree — all five
findings visibly addressed (the README NOTE/judges/runtime-tree
rewrites, a bracketed correction at e2e `:30`, dated CORRECTED blocks
at p0c §4, and the diagram mermaid/SVG/PNG re-synced to match), while
the e2e §6 wording (T8) is not touched. HEAD remains `cac9a80`. The
§4.1 checklist therefore converts from pre-merge to
verify-at-commit-time.

**Update (post-commit, same day)**: the five fixes were then committed
and pushed — `fbe3be4` (README: judge defaults, enforcement note,
runtime store list) and `7e3eed2` (e2e `:30` + p0c §4/§6 bracketed
CORRECTED annotations, insertion-only); `origin/main` now sits at
`7e3eed2`, two commits past this document's `cac9a80` anchor basis —
the citations above remain scoped to `cac9a80`, which is what the §4.1
checklist verifies. T8 (e2e §6 wording) remains untouched and open
(MEASURED: `git show 7e3eed2` touches the e2e doc at `:30` only).

---

## 0. Method, and what was re-verified vs relayed

Four parallel read-only verification passes (control-path code;
judge-facing docs snapshot; test inventory; evals wiring + agent-memory
residuals + git tracking), plus direct first-hand reads of the
load-bearing token-validation code (`orchestrator/human_gate.py:100-138`),
the judge wiring (`evals/run_evals.py:63-75`), the p0c §2 headed-click
passage, and local git refs. Verification classification per item:

| §7 item | Observation re-verified? | How |
|---|---|---|
| 7.a.1 judges wiring | YES | README + EVALUATION current text quoted; `evals/run_evals.py:75` + `agents/model.py:29-31,71-74` read |
| 7.a.2 diagram NOTE | YES | README:84-85 vs README:111-117 quoted |
| 7.a.3 e2e `:30` / §6 wording | YES | e2e `:30`, `:131-133` quoted; `seed_data.py:82` + grep over `*.py` (0 hits); `approval/cli.py:36-43, 282, 289-295` read |
| 7.a.4 p0c §4 staleness | YES | p0c `:162-163, :195-197` quoted; `git rev-parse origin/main` = `cac9a80`; `ac1ba3a..cac9a80` = 23 commits (CALCULATED); amendment-note grep = 0 |
| 7.a.5 blockers | RELAYED + grounded | EVALUATION §8.3 (`:266-269`) and §8.7 (`:276-277`) quoted; `docs/DEVPOST-DRAFT.md:131` shot-list heading confirmed |
| 7.a.6 headed click | YES | p0c §2 `:98-107` read directly ("NOT done… UNKNOWN… PROJECTED, not evidence") |
| 7.b.1 constant-time | YES | `human_gate.py:105` vs `:117/:123/:125/:133` read; greps over tests/ = 0 hits (3 patterns) |
| 7.b.2 spent-token | YES | consume-order read; re-execution-coverage grep = 0 hits; apply-failure sim test found (`test_gate_executor.py:246-262`) |
| 7.b.3 `exp` edge | YES | `:115` verified between the two try-blocks; executor body has zero try/except; `grep '"exp"' tests/` = 0 |
| 7.b.4 concurrency | YES | no `fcntl`/`filelock` imports; read-then-append `:131-137`; web lock scope `:260/:305/:319/:426` |
| 7.b.5 form cap | YES | `web.py:292-295` read; size/limit greps over tests/ = 0 hits |
| 7.b.6 residuals | YES + extended | all three files quoted; `git ls-files` tracking checked (the new evidence) |
| 7.b.7 README:200 | YES | line quoted; `runtime/` on-disk contents listed |
| 7.b.8 rejected-calls | YES | `--limit` code path read (mechanism corrected); component constant quoted |
| 7.b.9 drift automation | YES | EVALUATION §9 quoted; existing pin tests inventoried; §7's own citation accuracy sampled |
| 7.b.10 RUNTIME_DIR | YES | `seed_data.py:21-22`; repo-wide env-read grep = 0 hits; incident passage read (p0c §2) |
| 7.b.11 repeated runs | RELAYED | policy-gated live item; nothing to re-verify offline |

Taxonomy (senses pinned as in SYSTEM-REFERENCE §0.2, plus PROJECTED,
which this document does use): **MEASURED** = a command was executed and
its output recorded during this task (by this session or its subagents);
**OBSERVED** = directly seen in repository files at HEAD `cac9a80`;
**DOCUMENTED** = relayed from a cited project report; **CALCULATED** =
arithmetic over MEASURED/OBSERVED values; **PROJECTED** = this document's
forward-looking judgment (effort/impact estimates); **UNKNOWN** = not
determinable from available evidence.

---

## 1. The four triage buckets

### 1.1 Do before submission — high confidence this matters to judges

**T1. 7.a.5 — the two process blockers: demo video, then public flip.**
Not code; they gate the submission more than anything else in §7
(DOCUMENTED, EVALUATION §8.3 `:266-269`, §8.7 `:276-277`;
`docs/DEVPOST-DRAFT.md:131` shot-list draft exists, no footage —
OBSERVED). Everything else in this bucket sequences around them.
Effort: video = the long pole (recording + editing); flip = minutes plus
a final read-through. Dependency: T2 and T3 below should land before
their respective gates.

**T2. 7.a.6 — headed GUI click, before the video session.** The one
unexercised browser step in the human-approval chain. Grounding
re-verified first-hand: p0c §2 states a headed, interactive click was
NOT done and equivalence is "PROJECTED, not evidence"
(`docs/p0c-closeout-2026-09-06.md:98-107`, OBSERVED; also `:224`).
Sequencing premise, corrected on review: the current DEVPOST shot list
(`docs/DEVPOST-DRAFT.md:131-162`) contains **no browser-APPROVE shot**
(shot 4 shows the gate source + offline tests; shot 5 the produced case
file), and the draft itself lists "headed-browser interaction untested"
as a bound — so the click is not a hard recording prerequisite. It is
still best done before any recording or live Q&A: it closes the last
"projected, not evidenced" step that EVALUATION §8.3 discloses, and any
approval moment that does reach camera or judge questions is then
pre-proven. Effort: small/low-risk — one headed Edge/Chrome session
against the default bind (Windows-side per the validated technique, or
`[::1]` per the WSL2 workaround), one APPROVE click, one artifact note;
the headless=new mechanics are already proven on this host (DOCUMENTED,
loopback-validation §10). Fallback if it truly cannot happen: one
honest scoped-out line in EVALUATION §8.3 — but then update §8.3/§5.10
language to match whichever path was taken (do not leave both the
claim and the gap standing).

**T3. 7.b.6 — PROMOTED from long-term: clear the three agent-memory
residuals BEFORE the public flip.** New evidence §7 did not have: all
three files are **git-tracked** (MEASURED `git ls-files agent-memory` —
245 files; `task-board.json`, `task-contract-002-implementation.md`,
`decisions.md` all tracked), so at flip they publish, and they describe
a world the public repo contradicts:
- `agent-memory/task-board.json:6` — "GLM-5.3 via the single Z.AI
  credential for every seat … no second credential anywhere" (OBSERVED;
  false since the Groq + Gemini-judge split).
- `agent-memory/task-contract-002-implementation.md:80-83` — "single
  GLM-5.3 via the existing Z.AI … env; No second credential, ever" with
  **no** supersession banner (MEASURED grep for
  SUPERSEDED/STALE/OBSOLETE = 0 hits).
- `agent-memory/decisions.md` — the latest model-wiring entry is
  `D-2026-09-04-09` (GLM-5.3/Z.AI, `:174`); no later entry records the
  Z.AI→Groq switch, and the ledger itself admits the gap is open
  (`:393-394`, OBSERVED).

Effort: small/low-risk — one appended decision entry recording the
switch (the item §7 itself calls most likely to mislead a future agent
session) + two one-line annotations. Impact: judge-facing consistency
at flip (a reader comparing README's Groq+Gemini wiring against
"no second credential anywhere" sees a contradiction) and agent-session
hygiene. Dependency: must precede the flip; independent of the video.
(`guard-audit.log` is gitignored (`*.log`) and would NOT publish —
MEASURED; no action needed there.)

**T4. [IN FLIGHT — owned by the concurrent five-findings task; do not
duplicate] 7.a.1, 7.a.2, 7.a.3(a), 7.a.4, 7.b.7.** All five underlying
observations re-verified still true at the 19:29:55 UTC snapshot
(OBSERVED, §2 below for per-item evidence). This plan's action for them
is the post-merge checklist in §4.1 — they only count as done when that
task's edits have landed and the checklist passes. If that task stalls
or its scope excludes one, the excluded item becomes a small bucket-2
fix (each is a one-clause-to-one-line annotate-don't-erase edit).

### 1.2 Do before submission if time allows, lower urgency

**T5. 7.b.1 — pin constant-time comparison mechanically (test half
only).** Re-verified: `hmac.compare_digest` at the signature site
(`human_gate.py:105`) and plain comparisons everywhere else
(`:117/:123/:125/:133`, OBSERVED); **zero** test coverage of the
property (MEASURED greps: `compare_digest`, `constant.time|timing|side.channel`,
`hmac|compare` over tests/ → 0, 0, 0 hits). Effort: small/low-risk —
one source-scan test in the rejected-calls-tripwire style (assert the
signature comparator remains `compare_digest`; assert no secret-derived
value is compared with `==`). Offline, no live dependency. Impact:
converts the e2e §9 "Constant-time signature comparison — HOLDS" row
(e2e `:270`, OBSERVED) from a documented claim into an enforced one.
Note: the *other* half of §7.b.1 (qualify the e2e §9 row) targets the
concurrent task's file — fold it into the §4.1 checklist instead of
editing that file now.

**T6. 7.b.10 — RUNTIME_DIR startup warning.** Re-verified: the seam is
a module attribute (`seed_data.py:22`, with the `:21` comment), and a
repo-wide grep finds **zero** reads of a `RUNTIME_DIR` env var
(MEASURED). This is not hypothetical: the p0c Windows validation had a
disclosed incident where setting the env var silently appended two rows
to the repo's own `runtime/` store (DOCUMENTED, p0c §2
"Incident, disclosed"; detection MEASURED there). Effort: small — an
import-time or call-time stderr warning when the env var is present
(`tools/seed_data.py` is not on CLAUDE.md's Tier-C list). Impact:
demo-prep safety (the exact failure mode — clean runtime dir assumed,
writes landing in the repo store — is what a pre-video rehearsal could
hit) plus future-agent hygiene.

**T7. 7.b.9(i) — EVALUATION §9 suite-count sync, CONDITIONAL.** Only if
any test lands before submission (T5 would): the "218 passed" line is
hand-cited with lineage (EVALUATION §9 `:281-291`, OBSERVED) and is
accurate today (DOCUMENTED as MEASURED 2026-09-06 at this HEAD; not
re-run by this task). Trigger: any tests/ change ⇒ refresh or drop the
absolute number. `docs/EVALUATION.md` is not the concurrent task's
file, so this edit has no conflict exposure.

**T8. 7.a.3(b) — e2e §6 surface-wording amendment, AFTER the concurrent
task lands.** The observation is verified (e2e `:131-133` "no token
issance/validation logic" vs `approval/cli.py:36-43` importing the token
functions for the `--demo` negative matrix, `consume=False` at `:282` —
OBSERVED). Whether the concurrent five-findings task includes this
sixth wording fix is UNKNOWN (its named scope is the five findings);
sequencing it after that task lands avoids editing the same file
concurrently. Tiny annotate-don't-erase edit.

### 1.3 Explicitly defer past submission (one-line reason each)

- **7.b.2 (spent-token-on-apply-failure, GAP-4)** — Tier C
  (`correction_executor`) plus a genuine security-semantics redesign
  (defer-consumption trades a replay window against spendability);
  key-holder-reachable only and demo-invisible, 8 days out.
- **7.b.3 (non-numeric `exp` hardening, GAP-5)** — Tier C
  (`human_gate`) for an edge no surface can produce (the gate itself
  mints `exp` as a number); unreachable in any demo path.
- **7.b.4 (concurrency/locking for runtime stores, GAP-7)** — real but
  large (file locking, temp+rename, or protocol redesign); the demo is
  single-operator and the web server already serializes its own
  handlers (`web.py:426`, `:305/:319` — OBSERVED).
- **7.b.5 (bound the web form read, GAP-9)** — defense-in-depth on a
  loopback-only, unauthenticated-by-design demo surface; churn on a
  surface that carries a 19/19 live validation for zero judge-visible
  benefit.
- **7.b.8 (rejected-calls follow-ups)** — `component` becomes call-time
  only if a second agent ever holds the tools (unplanned); the viewer
  `--limit 0` quirk (verified: the chained comparison at
  `show_rejected_calls.py:88` makes any limit ≤ 0 mean unlimited —
  OBSERVED) is cosmetic; the first live entry needs an authorized live
  run. Opportunistic note: demo-video rehearsals ARE live runs — if a
  draft rejection ever occurs during one, capture the entry then.
- **7.b.11 (repeated clean runs)** — live-authorization-gated, and
  pre-deadline repeats are high-variance with a binding downside: this
  repo's own accuracy-figure policy would oblige reporting whatever a
  second run shows. The honest n=1 framing already on record is
  submission-grade; a rate is a post-submission program.

### 1.4 Recommend NOT doing, or reconsidering

- **7.b.9(ii) — a file:line drift-check test for SYSTEM-REFERENCE's
  anchors: recommend against.** Three reasons, in decreasing weight:
  (1) this task's re-verification found SYSTEM-REFERENCE's own
  citations already contain imprecisions (§3, meta-findings M1-M3) — a
  mechanical anchor-pinner would either fail on arrival or, worse,
  freeze prose errors as "passing"; (2) the load-bearing constants it
  would protect are already behavior-pinned by tests (TTL
  `test_gate_executor.py:88-91`, bind set `test_approval_surface.py:
  214-221`, threshold/caps via `test_graph_routing.py`, typed values
  `:230-234` — OBSERVED), so the test would duplicate existing pins in
  a more brittle form; (3) SYSTEM-REFERENCE §8.3 already declares its
  own freshness policy (± diff after any commit). The 7.b.9(i) half
  (suite-count line) survives as T7.
- **7.a.6 fallback — reconsider doing both halves loosely.** If the
  headed click happens, EVALUATION §8.3/§5.10 should say so; if it is
  scoped out, they should say that. The item's two outcomes are
  alternatives, not a menu to leave half-updated.
- **7.b.11 as a pre-submission idea at all — reconsider** (cross-listed
  from §1.3, where the defer itself lives). §7 files it
  under long-term; this triage agrees and sharpens the reason: chasing
  a better number inside 8 days, with a mandatory-disclosure policy on
  the outcome, is motivated-reasoning territory. Post-submission, run
  it properly.

---

## 2. Re-verification result per §7 item (step 2a evidence)

All 15 re-verifiable observations **verified still accurate** at HEAD
`cac9a80` / snapshot 19:29:55 UTC, and neither relayed item (7.a.5,
7.b.11) is contradicted by anything observed — none excluded for
staleness (§5). Detail beyond
§0's table:

- **7.a.1** — README:124-127 says judges are Gemini "(evaluation only)";
  no README line states that `verify.sh` step 6's base harness wires its
  judges to Groq (`evals/run_evals.py:75` `judge_model =
  get_model(max_tokens=8192)` → `agents/model.py:71-74` Groq
  `OpenAIModel`, `api.groq.com/openai/v1` — OBSERVED). Nuance vs §7's
  framing: §7 says "EVALUATION §2 is already correct — README alone is
  unqualified"; re-verification found EVALUATION §2 (`:57-61`) correct
  *for the reported runs* but **equally silent** on the base-harness
  Groq default (OBSERVED). The README clause remains the right fix; the
  parenthetical overstates EVALUATION's coverage.
- **7.a.2** — README:84-85 (inside the mermaid NOTE) credits
  `guard-segregation-of-duties.sh` as "mechanically enforced by";
  README:111-117 states tool registration as the mechanism (OBSERVED).
  Both quoted verbatim by the docs-verification pass.
- **7.a.3(a)** — e2e `:30` still names `modern_status_values()`;
  `tools/seed_data.py:82` defines `status_values()`; a grep for the old
  name over `*.py` = 0 hits (MEASURED — the only mentions anywhere are
  the e2e line itself and SYSTEM-REFERENCE's citations of it).
- **7.a.3(b)** — e2e `:131-133` "no token issuance/validation logic";
  `approval/cli.py:36-43` imports `issue_approval_token` /
  `validate_approval_token`, used by `--demo`'s negative matrix
  (`:272-295`, `consume=False` at `:282`) and replay leg (`:322-330`)
  (OBSERVED). The §6 sentence is imprecise about authority vs imports.
- **7.a.4** — p0c `:162-163` "Nothing pushed … MEASURED" and `:195-197`
  "origin/main is untouched at `ac1ba3a`. MEASURED." vs local
  `origin/main = cac9a80` (MEASURED `git rev-parse`), which is
  CALCULATED as 23 commits past `ac1ba3a`; no amendment note exists
  (MEASURED grep).
- **7.a.5** — video NOT recorded (EVALUATION §8.3, `:266-269`,
  DOCUMENTED; shot-list heading at `docs/DEVPOST-DRAFT.md:131`,
  OBSERVED); repo PRIVATE, flip pending human decision (EVALUATION
  §8.7 `:276-277`, DOCUMENTED).
- **7.a.6** — p0c §2 `:98-107`: headed interactive click NOT done,
  click-level evidence limited to the prior Playwright run over `::1`,
  Windows-headed equivalence "PROJECTED, not evidence" (OBSERVED).
- **7.b.1** — see T5. Signature site constant-time; scope/jti sites
  plain; no test coverage (OBSERVED + MEASURED greps).
- **7.b.2** — consumption inside validation (default `consume=True`,
  `human_gate.py:96`, `:135-137`) strictly precedes the apply
  (`correction_executor.py:73-75` → `:81`); apply-failure simulation
  test exists (`test_gate_executor.py:246-262`) but **no** test
  re-executes afterward (MEASURED grep over three gate/executor test
  files = 0 hits) (OBSERVED + MEASURED).
- **7.b.3** — `float(payload.get("exp", 0))` at `:115` sits between the
  signature try (`:104-110`) and the field try (`:119-124`);
  `execute_correction` contains no try/except, so the ValueError
  bypasses `_fail` and no `correction_failed` row is written (OBSERVED;
  `grep '"exp"' tests/` = 0 hits, MEASURED).
- **7.b.4** — no `fcntl`/`filelock`/`msvcrt` imports in human_gate;
  jti check-then-append is an unlocked read-then-append (`:131-137`);
  the web lock is per-server (`build_server` `:426`) serializing
  do_GET/do_POST (`:305/:319`) — CLI+web or two processes unprotected
  (OBSERVED).
- **7.b.5** — `_form` reads exactly `Content-Length` bytes with no cap
  (`web.py:292-295`); no test bounds it (MEASURED greps = 0 hits)
  (OBSERVED + MEASURED).
- **7.b.6** — see T3 (extended beyond §7 with the tracking check).
- **7.b.7** — README:200 "gitignored gate state: audit log, consumed
  tokens" (OBSERVED); on disk `runtime/` currently holds
  `drafts.jsonl`, `tickets.jsonl`, `consumed_tokens.jsonl` and **no**
  `audit_log.jsonl` (OBSERVED directory listing) — the line names a
  file that need not exist and omits the two dominant stores.
- **7.b.8** — component constant at `case_management.py:121`
  (`_TOOL_COMPONENT = "reporter"`, OBSERVED); viewer quirk mechanism
  corrected by re-verification: it is the chained comparison
  `0 < args.limit < len(entries)` at `show_rejected_calls.py:88`
  (default 20 at `:63`) — any limit ≤ 0 means unlimited, not just 0
  (OBSERVED; §7's "quirk" label was right, the usual truthiness
  explanation would be wrong).
- **7.b.9** — EVALUATION §9 `:281-291` hand-cites 218 with lineage
  (OBSERVED); the only doc-sync test in the repo is
  `tests/test_architecture_diagram_sync.py` (mermaid-block identity;
  MEASURED grep — no suite-count or prose test exists).
- **7.b.10** — see T6. Eight `require_eval_mode` call sites across four
  tool modules (OBSERVED) confirm the EVAL_MODE-only spine breadth that
  makes the attribute seam the single runtime-location control.
- **7.b.11** — relayed (DOCUMENTED, §5.1): 80.0% is one clean-run data
  point; nothing offline to re-verify.

---

## 3. Meta-findings on SYSTEM-REFERENCE itself (byproducts, not §7 items)

Recorded because they fed the 7.b.9(ii) recommendation:

- **M1**: GAP-8 cites "README:141" for "production requires
  `CORRECTION_TOKEN_SECRET`" — README contains no such phrasing
  anywhere (MEASURED grep, exit 1); the phrasing lives in EVALUATION
  §8.1 (`:257` area) and the e2e doc (`:142-143`, `:286`). GAP-8's
  substance (EVAL_MODE-only spine) is code-true (OBSERVED,
  `require_eval_mode` census + `_token_key` `:50-59`), but the README
  anchor is a phantom.
- **M2**: §4 row 11 cites `tests/test_gate_executor.py:246-266` for
  replay-without-clobbering; that test lives at
  `tests/test_gate_replay_and_linkage.py:146-173` (the
  `test_gate_executor.py:246-262` range is the apply-failure test)
  (OBSERVED).
- **M3**: §4 row 5's `test_gate_executor.py:203` asserts the
  failed+audited outcome and ticket/draft statuses; the
  store-value-untouched assertion lives at
  `test_gate_replay_and_linkage.py:198-206` (OBSERVED). Behavior
  pinned, citation split across files.
- **M4** (minor, adjacent to 7.b.2): `_fail`'s draft-status guard
  covers `applied/rejected/correction_failed` but not `approved` — an
  approved-but-unapplied draft would be downgraded to
  `correction_failed` on a later failure (`correction_executor.py:69`,
  OBSERVED). Not a §7 item; belongs in the 7.b.2 redesign discussion
  whenever that happens.

None of these invalidate a §7 item; they are drift in the *document*,
which is precisely the failure mode a mechanical anchor test would
amplify rather than fix.

---

## 4. Interaction flags: demo video and public flip (step 4)

### 4.1 Demo video (pending per 7.a.5)

1. **T2 (headed click) before the recording session** — not a hard
   prerequisite (the current shot list has no browser-APPROVE shot), but
   do it first if doing it at all: it closes the §5.10 gap EVALUATION
   §8.3 discloses, and any approval moment that ends up on camera or in
   Q&A is pre-proven.
2. **T4 (five doc fixes) landed before recording** — weak coupling
   (docs aren't in frame) but the submission package the video points
   at should be coherent when judges follow up. Post-merge checklist:
   (a) README states verify.sh step-6 judges are Groq / Gemini is the
   reported-run split; (b) README NOTE names tool registration as the
   mechanism and the guard as tripwire; (c) e2e `:30` reads
   `status_values()`; (d) p0c §4 carries a dated pushed-later amendment;
   (e) README:200 lists drafts/tickets. (f) optional sixth: e2e §6
   wording per T8; (g) optional: qualify the e2e §9 constant-time row
   (7.b.1's doc half — see T5) while that file is open.
3. **Demo-prep runtime hygiene** — the RUNTIME_DIR incident precedent
   (T6): use the documented `--runtime-dir` flag, never the env var;
   verify the store location before recording.

### 4.2 Public flip (pending per 7.a.5)

1. **T4 merged** — the five doc fixes are the judge-facing accuracy
   layer; flip only after the §4.1 checklist passes.
2. **T3 (agent-memory residuals) BEFORE flipping** — tracked files
   publish stale model-wiring claims that contradict README/EVALUATION
   (MEASURED tracking; OBSERVED text).
3. **Untracked-docs decision (human)** — `docs/SYSTEM-REFERENCE.md`,
   this triage file, and the two `agent-memory/*-2026-09-06.md` session
   reports are untracked (MEASURED `git status`). Commit-or-leave is a
   human call at flip time. If SYSTEM-REFERENCE is committed, add
   closure notes for the §7 items fixed by then, or it ships stale —
   the same staleness class this plan exists to prevent. Note (from the
   independent cross-check, §8): the p0c §4 CORRECTED block cites
   push-confirmations living in untracked agent-memory files —
   committing that amendment without committing (or de-referencing)
   them leaves the correction dangling.
4. **Branch hygiene (verified clean)** — the remote has only
   `origin/main` (MEASURED `git for-each-ref refs/remotes`); the local
   `stage2-pre-rewrite-backup` branch (pre-identity-rewrite history) is
   local-only. Keep it unpushed through the flip.
5. **T7 trigger** — if any test landed since EVALUATION §9 was written,
   sync the count before flipping.

---

## 5. Items excluded for staleness (step 5)

**None.** All 15 re-verifiable §7 observations held at HEAD `cac9a80`
(§2); the two relayed items (7.a.5, 7.b.11) rest on their cited
reports, contradicted by nothing observed; no post-SYSTEM-REFERENCE
task has changed the code (MEASURED: HEAD unchanged, tracked files
unmodified at snapshot). Two caveat
classes, neither an exclusion:

- Five items' **fix targets** are being edited concurrently (T4) — the
  observations stand; the *fixes* are re-routed to the post-merge
  checklist to guarantee zero conflict.
- §7-item-1's parenthetical ("EVALUATION §2 is already correct")
  overstates EVALUATION's coverage (§2, 7.a.1 nuance) — the item's
  README fix survives intact; the parenthetical should not be relayed
  as-is.

---

## 6. Top-3 recommendation (immediately after this task)

1. **Do the headed GUI click (T2 / 7.a.6), then record the demo video
   (T1).** The video is the submission's long pole; the click is small
   and closes the chain's one unevidenced step — doing it first means
   any approval moment that reaches camera or Q&A is pre-proven (the
   current shot list does not require it, which is also why T2's
   scoped-out fallback remains respectable if time forces the choice).
   Operationally the two can merge: recording the video through the
   browser approval surface with a real human APPROVE click closes T2
   and T1's centerpiece in one shot (the cross-check's variant, §8).
2. **Run the flip gate: verify the concurrent five-findings merge
   against the §4.1 checklist, land T3 (agent-memory residuals:
   decisions.md entry + two annotations), decide the untracked-docs
   question, final README+EVALUATION read-through — then flip** (branch
   hygiene §4.2.4 is already clean: the remote holds only `origin/main`).
   All small, all judge-facing, all offline.
3. **If any coding time remains: T5 (constant-time source-scan test),
   then T7 (sync EVALUATION §9, since T5 adds a test).** Offline,
   small, converts a claimed invariant into an enforced one; stop
   there — T6/T8 (§1.2) remain available as fill-ins if more time
   appears, and everything beyond them is correctly deferred (§1.3).

Ordering rationale (PROJECTED): with 8 days left, the video dominates;
the flip items are minutes each but must be sequenced after the
concurrent task lands; T5/T6 are the only code-adjacent items whose
cost/benefit still clears the bar before 2026-09-14.

---

## 7. Claim classification summary

- **MEASURED** (command executed, output recorded, this task):
  `git rev-parse HEAD`/`origin/main` = `cac9a80`; `git status` snapshot
  (3 untracked files, zero modifications) at 19:29:55 UTC; all test
  greps cited in §2 (constant-time 0 hits, re-execution 0 hits,
  `"exp"` 0 hits, size-limit 0 hits, `modern_status_values` 0 hits
  over `*.py`, RUNTIME_DIR env reads 0 hits, supersession banners 0 hits,
  p0c amendment-note 0 hits, README `CORRECTION_TOKEN_SECRET` 0 hits);
  `git ls-files agent-memory` tracking results; `git for-each-ref
  refs/remotes` (origin/main only); 23 commits `ac1ba3a..cac9a80`;
  runtime/ directory listing (via verification pass).
- **OBSERVED** (in repo files at HEAD): every quoted code/doc line in
  §1-§3 with its `file:line` anchor (human_gate, correction_executor,
  web, cli, seed_data, case_management, show_rejected_calls,
  run_evals/model wiring, README/e2e/p0c/EVALUATION/DEVPOST-DRAFT/
  task-board/contract-002/decisions.md passages).
- **CALCULATED**: 23 commits between `ac1ba3a` and `cac9a80`
  (`git rev-list --count`).
- **DOCUMENTED** (relayed from cited reports): 218 passed at this HEAD
  (SYSTEM-REFERENCE §8.1); 80.0% single-point accuracy and §5.1
  limitations; headed-click status (p0c §2); RUNTIME_DIR incident
  (p0c §2); video/visibility blockers (EVALUATION §8.3/§8.7).
- **PROJECTED**: all effort/impact/sequencing judgments in §1 and §6;
  the concurrency conflict avoided by re-routing T4/T8; the flip-time
  exposure of stale tracked files (the tracking itself is MEASURED; the
  exposure is a projection of the human's pending flip decision).
- **UNKNOWN**: whether a headed click will in fact succeed on this host
  (technique proven headless, headed click never attempted — p0c §2).

---

## 8. Independent-assessor cross-check (blind, post-draft)

A second assessor re-triaged §7 blind to this document (same
environmental facts, independent re-verification of the code bases).
Convergence: 14 of 17 bucket placements identical; all five in-flight
findings characterized the same way (they "reduce to 'commit'"); the
same single recommend-against sub-item (7.b.9's mechanical
citation-drift test); no stale items found. Splits and adoptions:

- **7.b.6** — the blind pass deferred it ("internal notes; not
  judge-visible"), not having weighed the tracking evidence: the three
  agent-memory files are git-TRACKED (MEASURED) and the flip publishes
  them, so "internal" ceases to be true at flip. This document's
  promotion (T3) stands.
- **7.b.5** — the blind pass ranked it bucket-B ("3 lines in
  non-Tier-C web.py"). Correct that web.py is not Tier C, but the
  surface carries a 19/19 live validation against a loopback-only
  threat model; pre-deadline churn buys nothing judge-visible. Recorded
  as the one open judgment split.
- **7.b.9(i)** — the blind pass deferred the whole item; T7's
  conditional trigger (refresh only if tests land) is equivalent when
  none do.
- **Adopted from the cross-check**: the p0c §4 CORRECTED block cites
  untracked agent-memory push-confirmations (dangling-reference risk —
  folded into §4.2 item 3); the observation that EVALUATION §8 already
  discloses "headed interactive browser use untested" (making T2's
  scoped-out fallback near-moot); and the operational variant of
  recording the video through a real human APPROVE click (folded into
  §6 item 1).

Classification: the cross-check's relayed outputs are DOCUMENTED; the
facts it independently re-verified (Groq judge default, gate/executor
code paths, web form read, RUNTIME_DIR seam, runtime/ contents,
agent-memory residuals, viewer quirk, 218 citations, 19 test files)
corroborate this document's MEASURED/OBSERVED basis.
