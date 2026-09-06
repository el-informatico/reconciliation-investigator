# Stage 2 pre-rewrite checkpoint (2026-09-05)

**Status: ALL PRE-REWRITE INVARIANTS VERIFIED. History rewrite is authorized
to proceed ONLY after the three execution gates in §9 close green. This
report records the verified facts and every non-silent scope decision.**
Classification: MEASURED (this session, directly), OBSERVED (seen in files),
DOCUMENTED (human decision / prior report), CALCULATED, PROJECTED, UNKNOWN.

## 1. Repository state (MEASURED, independently confirmed by subagent audit 8/8)

- Branch `main` (sole), HEAD `316835fb73d66850444473c86fa33df10c4c8169`,
  **19 commits**, 0 merges, root `daedc780953416fe2a13b22fd4795256601dc2ba`,
  no tags, **no remotes** (local-only), empty stash.
- Working tree: **40 porcelain entries** — 5 tracked-modified
  (`agents/classifier.py`, `agents/detector_investigator.py`,
  `agents/reporter.py`, `tests/test_tools.py`, `tools/case_management.py`)
  + 35 untracked, ALL in known categories (1 agents/, 12 docs/, 4 evals/,
  5 tests/, 13 agent-memory/), zero unexpected files.
- Pre-rewrite offline suite: **132 passed** (6.37 s) — the A/B baseline.
- Offline pytest baseline re-verified; segregation guard passed in the prior
  session's runs (re-run post-rewrite).

## 2. Approved identity (DOCUMENTED; verified against repo + GitHub)

`juanz <204210901+el-informatico@users.noreply.github.com>` (author AND
committer, all 19 commits). Current identity on all 19:
`Ares Agent <ares-agent@local>`. GitHub account `el-informatico`
(id 204210901), gh token valid with `repo` scope; SSH transport proven
(`Hi el-informatico!`; `git ls-remote` over SSH against `[SIBLING-C]` OK);
repo name `reconciliation-investigator` **available**. (MEASURED)

## 3. Commit-message replacements (verified MEASURED)

19 message files staged in `/tmp/stage2/msgs/`; independent fidelity audit:
**19/19 EXACT MATCH** to the approved §2 table of
`docs/commit-history-audit-and-github-repo-plan-2026-09-05.md` (17 subject
rewrites + daedc78 body-only, subject = original) and `88303b7` byte-verbatim
to the original. The two `Co-Authored-By: Claude Code <test@example.com>`
trailers (316835f, 8c13fc2) exist now and are dropped by the rewrite
(replacement bodies carry no trailer).

## 4. SHA-reference inventory (corrected this session)

The Stage-1 inventory's totals were **refuted by an independent recount**
(current truth): **188 commit-SHA references** across 19 files — 148 in
docs/ + 40 in agent-memory/ (agent-memory figure confirmed exactly). The +23
delta vs Stage-1 sits entirely in
`docs/git-identity-audit-stage1-2026-09-05.md`, whose §8 addendum (added
after the Stage-1 inventory ran) lists all 19 per-SHA totals. Stage-1's
"40 refs in tracked files" is corrected to **25 refs in 7 tracked files**.
Zero ambiguous refs; zero refs outside docs/ + agent-memory/. (MEASURED)

**Design-critical fact (CONFIRMED): no tracked file references the final
commit `316835f` (rank 19)** — tracked refs point to ranks 1–16 (including
`c2803a5` rank 13 in impl-diff and `958a815` rank 16 in
provider-feasibility) but never to rank 19 — so folding the remaps into the
final commit's tree cannot create a circular self-reference.

## 5. License decision (DOCUMENTED; inputs verified MEASURED)

Apache License 2.0. `LICENSE` = canonical text verbatim
(/tmp/stage2/LICENSE.final, sha256
`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` — the
long-published digest; appendix template intact per convention). Holder line
`Copyright 2026 el-informatico` lives in the README License section.
INTERPRETATION RECORDED (per plan-audit finding 3): the approved instruction
("standard Apache License 2.0 text" + the approved holder line) is
implemented as canonical-verbatim LICENSE + holder line in README — both
halves of the instruction satisfied, canonical digest preserved. The
alternative (filling the appendix inside LICENSE) was identified and NOT
taken; if the human prefers it, that is a post-Stage-2 correction.
Repo-wide
license sweep: **exactly one normative change** — README.md line 107
`[MIT](LICENSE)` → `Copyright 2026 el-informatico. Licensed under the Apache
License, Version 2.0 — see [LICENSE](LICENSE).`; README:61/105 self-correct
once LICENSE exists; 40 HISTORICAL-KEEP lines in dated audit docs remain
untouched (they describe past state); pyproject carries no license metadata
(nothing to correct).

## 6. Scope decisions (explicit, per the no-silent-decisions rule)

- **D1 — Fold points, 19-commit invariant, no 20th commit (AMENDED after the
  coherence review).** ALL repository-document tree changes land in the
  FINAL commit (rank 19, `316835f`) only: +LICENSE (canonical Apache 2.0),
  README.md = rank-19's own blob with the single MIT→Apache line (mode
  preserved), and the three SHA remaps. Ranks 1–18 are **byte-identical to
  the original trees** — this keeps captured evidence TRUE: the 22-file
  initial-commit count recorded in task-contract-001/bootstrap-sanity, and
  the placed-README sha256 recorded in decisions.md D-05/06, both remain
  verifiable at their referenced commits (the earlier root/rank-4 fold
  placement falsified both — coherence-review findings MAJOR-2/3 — and was
  abandoned). Consequence: every adjacent patch-id except 18→19 is preserved
  exactly, a strictly stronger invariant. No new commit is created for LICENSE,
  README, reports, or any other purpose; the three Stage-2 report docs are
  created as UNTRACKED local files (a 20th commit is not approved and is not
  needed — folding is deterministic).
- **D2 — SHA-reference policy.** ALL agent-memory/ commit-SHA references are
  preserved as documented category-B provenance — this gives the
  impl-diff/decisions.md/todo-verify-resolution triple ONE consistent
  treatment (preserve). The ONLY remaps (category A): decisions.md:58
  (abac42a→new rank-3), decisions.md:68 (df44a8c→new rank-4),
  provider-feasibility-cerebras-gemini.md:455 (958a815→new rank-16) — each
  verified to occur exactly once. ALL untracked 2026-09-05 docs keep old SHAs
  (dated audit/provenance records; not pushed; the mapping is the
  translation). Non-commit hashes (blob, sha256, UUID, chatcmpl, foreign
  aresV2, orphaned a70a83c) untouched.
- **D3 — Uncommitted work stays local and UNPUSHED.** The pending application
  work product (5 modified files = retry wiring + fix, and untracked
  retry.py/docs/evals/tests/evidence) is outside the approved Stage-2 staging
  list; committing it would be an unapproved 20th commit. Consequence, stated
  plainly: **the pushed repository will show the cleaned 19-commit history
  whose latest commit predates the retry/fix work**; publishing that validated
  work is the human's next approved task (a normal commit #20 on top of the
  rewritten main, then push). This SUPERSEDES the older Stage-1 repo-plan §3
  recommendation that the pending-work commit land before the push; the
  supersession is explicit and will be acknowledged again in the final
  Stage-2 report. agent-memory remains tracked — its tracked 42 files ride
  in the 19 commits; the untracked 137 stay local like all other
  uncommitted content. Nothing is staged (`git add` is never run).
- **D4 — Recovery ref.** `refs/heads/stage2-pre-rewrite-backup` at the old
  tip, local-only, documented here; the push is explicitly
  `git push origin main` (no --tags/--all/mirror), so it cannot ship. It may
  be deleted by the human after verifying the rewrite.
- **D5 — Working-tree sync.** After the rewrite, LICENSE + corrected README +
  remapped decisions.md/provider-feasibility are written to the working tree
  to match the new HEAD trees, then `git reset --mixed main` re-syncs the
  index (which still matches the pre-rewrite tip after update-ref; mixed
  reset stages nothing and preserves the working tree — plan-audit finding
  4). `git status` must then equal the pre-existing 5 modified + untracked
  set plus the Stage-2 doc files (re-measured at execution; porcelain was 40
  at pre-rewrite measurement, 41 once this checkpoint file itself is
  counted). The pushed tree's own offline suite is verified separately in
  the rehearsal clone (its code is byte-identical to `316835f`'s, whose
  documented suite state is 94/94; the worktree suite with the uncommitted
  retry work is 132/132) — both runs are classified, not conflated
  (plan-audit finding 5).

## 7. Safety nets in place (MEASURED)

- Pre-rewrite metadata backup: `/tmp/stage2/backup/pre-rewrite-metadata.tsv`
  (old SHA | parents | author | committer | dates | subject, 19 rows) +
  `pre-rewrite-messages.txt` (verbatim bodies).
- agent-memory pre-push audit: **SAFE** — total 1.70 MiB apparent (tracked
  0.69 MiB / untracked 1.01 MiB), largest file 283 KiB, zero secret findings
  across every pattern in both the pushed set (98 tracked files) and all 179
  agent-memory files; PII clean; no `.env` under agent-memory.
- Rewrite mechanism: deterministic `git commit-tree` plumbing
  (/tmp/stage2/rebuild.sh) with precondition asserts, per-fold temp-index
  tree builds, preserved author+committer dates, guarded final
  `git update-ref` (old-value-checked). Mechanical verification:
  /tmp/stage2/verify-rebuild.sh (19 invariants incl. tree-equality outside
  folds and patch-id equality for non-boundary pairs) + `git range-diff`.

## 8. GitHub target (verified MEASURED)

Owner `el-informatico`; name `reconciliation-investigator` (available);
visibility **PRIVATE** (public only by later explicit human authorization —
never in this task); branch `main`; SSH remote URL
`noreply@example.com:el-informatico/reconciliation-investigator.git`.

## 9. Execution gates — status

1. Adversarial review of rebuild.sh + verify-rebuild.sh — **RESOLVED**: all
   three BLOCKERs were the pre-fix fold-model/patch-id/grep defects, fixed
   and hardened (old-chain pins, remap-content assertions, full fsck,
   blob-equality checks); reviewer's remaining MAJOR/MINOR findings adopted.
2. End-to-end dry-run in a /tmp clone — **GREEN**: pass 3 = 21/21 PASS exit 0
   on the hardened scripts; deterministic across two independent clone runs
   (bit-identical SHAs, expected live tip `20f296c74d1c…`); real repo
   untouched throughout.
3. Adversarial plan audit — **AMENDED**: BLOCKER/parameterization findings
   were already-covered pre-fix items; the checkpoint corrections (D1
   wording, rank range, git reset --mixed, arithmetic, holder-line
   interpretation recording, D3 supersession note) are applied in this
   revision.
4. Published-history coherence review — **RESOLVED BY AMENDMENT**: verdict was
   FIX-FIRST with 4 MAJORs; adjudication: MAJOR-2 (22-file root record) and
   MAJOR-3 (README sha256 record) ACCEPTED → fold model amended to
   rank-19-only (D1 above); MAJOR-1 (preserved old SHAs + impl-diff's
   embedded original `git log` in the tip tree) and MAJOR-4 (evidence docs
   describing the pre-rewrite `Ares Agent` identity) REJECTED as changes —
   they are the approved category-B preserve-as-provenance policy and the
   inherent consequence of the approved identity normalization; recorded as
   documented dissents with rationale. MINORs: intermediate-diff SHAs now
   eliminated by the amendment; Ares-v2 dead README link pre-existing and
   out of scope.
5. Classification oracle — **GREEN**: 188 refs in the 19-file recount
   universe = A 3 / B 185 / C 0 / D 0 / E 0, per-file and per-SHA totals
   reconciling exactly with the independent recount. Material flag adopted:
   this checkpoint doc postdates the recount and itself carries 13 B-class
   refs (201 current-tree total) — every post-rewrite sweep must state its
   count universe explicitly; Stage-2 session docs add further B refs,
   counted and disclosed, never silently ignored.

Re-validation: a fourth dry-run of the amended (rank-19-only fold) scripts
must pass before execution, establishing the new deterministic SHA
expectation. Auxiliary probes in flight: pushed-tree offline pytest and
pushed-tree secret scan (both against the rehearsal clone's tip tree, which
is identical under either fold model). Any BLOCKER ⇒ STOP (fail-safe rule);
partial progress and the exact blocker will be reported, nothing concealed.
