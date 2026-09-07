# Case-4 / Tool-Parameter Documentation Chain — Consolidated Evidence Index
> AMENDED 2026-09-07: this report references the agent-memory/ directory, which was removed from repository history by the 2026-09-07 excision rewrite; those artifacts are retained only in the author's private local archive, never in this repository.

Date: 2026-09-05 · Mode: closure/consolidation task. This file is the only NEW
artifact; reports A and B received only (i) the human-approved §6 notice
amendment to A and (ii) inline run4 correction markers in both — both proven
amendment/insertion-only by byte-level diff (§4). Nothing staged, committed,
or pushed; no tests, benchmarks, or live LLM/API calls; no evidence directory
modified (§3 is a read-only disambiguation); no application/eval code touched.

**This index introduces NO new findings.** It only consolidates and points to
the existing four-report chain. Claims carry the chain's classification tags
(MEASURED / CALCULATED / OBSERVED / DOCUMENTED / PROJECTED / UNKNOWN), with an
explicit boundary between what THIS task re-verified first-hand and what it
relays without independent re-verification (§5).

**Line-number convention.** A's notice amendment (this task) added two lines,
so every `A:NNN` citation in the earlier chain documents (pre-amendment
numbering) is +2 in the current file: A:93→A:95, A:111–114→A:113–116,
A:393→A:395. A repo-wide sweep by this task's lane measured the affected
set: 36 `A:NNN` sites in the §5 follow-up and 15 in the dissent review (all
translate +2), plus two whole-notice references "A:1–15" (the notice text now
spans 1–17). Two PRE-EXISTING dissent-review citations predate that doc's own
convention and resolve against the notice-free original — translate +20, not
+2: DR:82 ("A:193" → current 213–214) and DR:97 ("A:85–86" → current
105–106). No document other than the dissent review, the §5 follow-up, and
this index cites A or B by line number. `B:NNN` and `DR:NNN` citations are
unchanged (B's markers were inline-only; spot-checked on disk).

## 1. The report chain (chronological — why four documents exist)

Four 2026-09-05 documents cover one topic because each was produced by a
different session with a different mandate: original audit → independent
re-verification → adjudication of the annotation inserted between them →
verification of that adjudication's findings. Suggested read order for a
newcomer: **this index → report B (authoritative core) → §5 follow-up (run4
ground truth + materiality) → dissent review (process record, 19/19
settlement) → report A (A-only content)**.

1. **Report A** — `docs/case4-outcome-and-toolparam-fabrication-audit-2026-09-05.md`
   (earliest; earlier/parallel session). Case-4 outcome + fabricated-parameter
   audit of the clean 5-case run. Carries a SUPERSEDED notice (lines 1–20;
   original content resumes at line 21) routing authority to B; the notice's second sentence was amended by this
   task per dissent review §6. Still the sole record of A-only content: the
   §1d 20/20-vs-19/19 erratum, the §5 P0-B errata + headline-figure
   verification, the clean-run case-2 UNKNOWN note, and the §3 cross-run rate
   table (which B itself cites as provenance).
2. **Report B** — `docs/case4-and-toolparam-fabrication-reverification-2026-09-05.md`
   (independent re-derivation). Agrees with A on every core fact it re-derives
   (its Appendix A). **Authoritative for case-4's outcome and the
   tool-parameter fabrication findings**, per A's (amended) notice. Carries
   run4 correction markers at B:84–85 (this task).
3. **Dissent review** — `docs/case4-annotation-dissent-review-2026-09-05.md`.
   Adjudicated the prior session's decision to insert A's notice over a fired
   STOP condition: override "substantively defensible but procedurally wrong";
   remedy = amendment, not removal (§6 proposal — applied to A by this task).
   Also settled 20/20→19/19 (§4) and first surfaced the run4 erratum and the
   §5a run-1 disagreement (§5).
4. **§5 follow-up** —
   `docs/case4-dissent-section5-verbatim-and-verification-2026-09-05.md`.
   Evidence-traced verification of the dissent review's §5: run4 erratum
   CONFIRMED (CALCULATED from 8 MEASURED premises) and rated LOW MATERIALITY
   (§2); §5a adjudicated — B matches the artifact (§4); §5b B:84
   inference-as-fact caveat (§3); evidence-dir run-id sharing found (§6.5);
   per-item fold-in recommendations (§6) implemented by this task/index.

## 2. Authoritative findings at a glance

| # | Question | Authoritative answer | Proven in (primary) | Full detail | Class | Re-verified this task? |
|---|---|---|---|---|---|---|
| 1 | Case-4 outcome (clean run) | **PASS**: root_cause `MANUAL_OVERRIDE` (match), confidence 0.95 (ticket-store channel), OutputEvaluator 1.0 `EXEMPLARY`, 18/19 case rows; **first leak-free case-4 pass**; NOT first pass ever — 3 archived prior passes + 1 ticket-store-only ⇒ 4th archived / 5th overall; **exactly ONE historical UNKNOWN on record** (09-05 08:33Z @ 0.32) — the "twice previously UNKNOWN" premise is REFUTED | Report B §1a–§1c | A §1 corroborates; §5 follow-up §4 re-verified the run-1 row (B:82 matches `tickets.jsonl:7`; A:91 "NOT preserved" wrong — negligible materiality) | MEASURED (independently, twice, per B) | No — relayed (DOCUMENTED) |
| 2 | Tool-parameter fabrication | **9 fabrication-pattern failures of 31 ToolParameter rows** (30 substantively judged: 21 pass / 9 fail; the 10th non-pass is case-2's Gemini-503 judge-error, no tool judged); same literal date-pair (`2026-08-06T00:00:00Z`/`2026-09-05T23:59:59Z`) and confidence-value pattern as the earlier correction-draft-id canary (`correction-draft-id-fix-canary-2026-09-04/eval-rows.json:121,:145`); recurring and structured, not isolated; **structurally independent of the ground-truth leak** (the leak's only observed/constructible judge-side effect direction was leniency) | Report B §2 | A §2b agrees (byte-identical rationales); B §2d proves the judge-input anatomy by code | MEASURED (census recomputed twice per report) | No — relayed (DOCUMENTED) |
| 3 | "20/20" vs "19/19" GLM-run figure | **19 rows / 19 passes** (`evals-sequential-results-2026-09-04.json`, sha256-pinned; counted twice incl. one count-blind lane; 20/20 is structurally impossible for the sequential driver). **Every "20/20" mention in the repo is wrong.** Known occurrences (four docs; deliberately NOT fixed in this task — future pass): `docs/case-4-parsing-failure-audit-2026-09-04.md:124,198-199`; `docs/eval-ground-truth-leak-audit-2026-09-05.md:371,400-401,430,472,492`; `docs/clean-5case-validation-2026-09-05.md:8,38-39`; `docs/eval-ground-truth-leak-fix-2026-09-05.md:363` | Dissent review §4 | A §1d first recorded it (naming three of the four docs) | MEASURED (two lanes, one count-blind) | No — relayed (DOCUMENTED); flagged for a future pass |
| 4 | run4-attribution erratum | The 09-04 17:21:17Z case-4 pass (`TCK-4e744f8f7592`, ticket-store DIRECT) belongs to a **subsequent, unlogged execution — not run4-official**, which died via SIGINT at 16:52:54Z (EXIT=130, death already on record in `impl-diff-2026-09-04.txt:724` at 17:12:19Z), 2m19s before the first ticket of the c1→c4 progression. Both A and B originally mis-attributed it identically; **now annotated in place** (this task) at A:95, A:113–116, A:395 (= chain numbering A:93/111–114/393) and B:84–85. **LOW MATERIALITY**: no public/citable figure depends on run4 (README figureless; no index/pitch/submission docs; nothing pushed — main = origin/main = ac1ba3a) | §5 follow-up §2 | Dissent review §5b first found it (tagged INFERRED); B's row-4/row-5 self-contradiction annotated at B:84 | CALCULATED from MEASURED premises | Marker placement + diffs yes; ground truth relayed |
| 5 | Evidence-directory id collision | Four directories internally carry run-id `gemini-judge-5-case-2026-09-04`; disambiguated in §3 below | §5 follow-up §6.5 (three) + this task's delegated lane (four, on disk) | §3 table | MEASURED | Yes — directory facts re-verified by a delegated read-only lane in this task |

Standing UNKNOWN items in the chain (relayed): cause of the 08:33Z
UNKNOWN→clean PASS change (B §1c); whether leak removal raised the fabrication
rate (B §2d/§4 — single run); per-attempt interior case placement of the
run3c/3d/3e kills (§5 follow-up §3). PROJECTED: none — no claim in this chain
is projected, and this index adds none.

## 3. Evidence-directory run-id collision — disambiguation (READ-ONLY)

The internal run-id `gemini-judge-5-case-2026-09-04` is carried as the
`"run"` label in `index.json:2` by **FOUR** evidence directories — root cause:
the hardcoded label at `evals/gemini_judge_5case.py:287`, inherited by every
later 5-case driver invocation. **They are NOT the same run. Never
disambiguate by that internal id — use the directory name plus its launch
envelope.** No directory or file was renamed, moved, or modified.

| Directory (under `agent-memory/evidence/`) | Physical run (launch envelope, all disjoint) | Report it evidences | Distinguishing markers |
|---|---|---|---|
| `gemini-judge-5-case-2026-09-04/` (namesake) | file mtimes 2026-09-05 03:16–03:42 UTC (no LAUNCH marker; chain timeline row "09-05 03:24") | `docs/gemini-judge-5-case-validation-2026-09-04.md` (NO-GO 2/5); primary tree of `docs/case-4-parsing-failure-audit-2026-09-04.md:15` | 24 files / 280K; unique `preflight.json` (JSON form) + `verify-step6-attempt-2026-09-04.log.corroboration`; no `retry_strategy` keys; case-4 = detector parse death, no verdict |
| `gemini-groq-5-case-final-validation-2026-09-05/` | `LAUNCH_UTC=2026-09-05T08:33:53Z`, END 08:41:21Z | `docs/gemini-groq-5-case-final-validation-2026-09-05.md` (4/5, 89.8%) | 26 files / 328K; unique `special-validation.md`; its `post-run-checks.txt` (not unique — the retry-active dir also has one) flags the label reuse at `:37–41`); no `retry_strategy` keys; **the case-4 UNKNOWN run** |
| `groq-retry-active-5case-validation-2026-09-05/` | `LAUNCH_UTC=2026-09-05T13:06:48Z` | `docs/groq-retry-active-5case-validation-2026-09-05.md` (5/5 rc=0, 93.0%) | 39 files / 416K; unique `adversarial-review.md`; `baseline/` unique among these four (one also exists in `groq-parsing-retry-canary-2026-09-05/`); `retry-evidence-run.json` shared with the clean dir; HAS `retry_strategy`/`retry_evidence` keys; case-4 PASS @ 0.95, 19/19 |
| `clean-5case-validation-2026-09-05/` | `LAUNCH_UTC=2026-09-05T20:29:33Z` | `docs/clean-5case-validation-2026-09-05.md` (leak-free baseline; subject of reports A and B) | 31 files / 420K; no unique top-level artifact — distinguish by the 20:29:33Z envelope (latest of the four) plus the 31-file/420K inventory (`make-analysis-digest.py` is shared with the retry-active dir); HAS `retry_strategy` keys; **case-4 EXEMPLARY pass — the run this whole chain is about** |

Premise note (OBSERVED): the closure task's framing said "two directories";
the §5 follow-up §6.5 measured three (naming the three 2026-09-05 dirs);
on-disk verification by this task's delegated lane found four — the namesake
directory also self-carries the label (its `index.json:2` and
`preflight.json:2`), which the §5 list omitted. The collision was already
documented pre-existing in `docs/clean-5case-validation-2026-09-05.md:141–144`
and in the gemini-groq dir's own `post-run-checks.txt:37–41`.

## 4. Corrections applied by this task (2026-09-05; byte-verified)

1. **A's notice §6 amendment** (dissent review §6, recorded there as
   human-approved; applied verbatim, both the replacement and the appended
   clause): the notice's second sentence now reads "…which agrees with it on
   every core fact **it re-derives** and grounds those against the raw
   evidence; findings unique to this report (e.g. its §1d and §5 errata and
   its cross-run rate table) are not restated there." Diff proof: exactly one
   hunk, lines 5–11, confined to the notice; A below the notice byte-identical
   (pre line 19+ == amended line 21+).
2. **Run4 correction markers** (inline, adjacent to each claim; original
   sentences preserved — nothing deleted or rewritten):
   - A:95 (§1b timeline row 3, Run cell) — standard marker.
   - A:116 (end of the "run4-official, by contrast, DID reach case-4 …"
     sentence) — standard marker.
   - A:395 (§5 provenance table, class cell) — standard marker.
   - B:85 (§1b row 5, after `"run4-official window"`) — standard marker.
   - B:84 (§1b row 4, after "case-4 never reached (killed)") — variant marker
     additionally noting that only "never completed case-4" is certain for the
     logged run4 (died SIGINT 16:52:54Z, no case-4 ticket/draft in its
     window) and that the row self-contradicts row 5.
   Standard marker text (used verbatim at all standard sites):
   `[CORRECTED — see docs/case4-dissent-section5-verbatim-and-verification-2026-09-05.md: run4-official died via SIGINT before this pass occurred; the pass belongs to a separate, unlogged execution]`
3. **Byte-level proof**: removing the three markers from A reproduces the
   post-amendment snapshot exactly; removing the two markers from B reproduces
   B's pre-task state exactly (python string-removal + `cmp`, byte-exact).
   sha256 ledger (full values, so this file is self-contained): A pre
   `792a6b5dfd149cc56b4430d12b1f320e43c56c9b6295b9ae03f0b5940bdbfe57` → A post
   `ae0a46774076bf8a1bac1351260b43bb9bbb6dcbb08d8998843822e5d4a03959`; B pre
   `0b1f0b895e8214aafbd9c0655093d49173a37214cd26aed75543bce32147419c` → B post
   `ec352fb9d8f5302cc75dfec5af66a8e4496abe07aa8445022413ffbef0c25ed7` (the
   pre values match the hashes pinned at DR:662–664). Session snapshots under
   `/tmp/case4-chain-snapshots/` are ephemeral and outside the repo.
4. **Deliberately NOT done** (out of scope by instruction): fixing the "20/20"
   occurrences in the four docs of §2 row 3 (flagged there for a future
   pass); annotating B:118–122, which repeats the 17:21 timing inference
   ("attribution inferred by timing") without mis-citing run4 by name — task
   scoped B's annotations to B:84–85, and no count there is affected; any edit
   to the dissent review or §5 follow-up; any change to any evidence
   directory.

## 5. Classification legend and re-verification boundary

Tags follow the chain's convention (definitions in B's header): MEASURED =
directly verified against artifacts by the named task; CALCULATED = derived
from MEASURED values; OBSERVED = single-run observation; DOCUMENTED = relayed
from an existing document without independent re-derivation; PROJECTED /
UNKNOWN as labeled. **PROJECTED: none.**

- **Re-verified first-hand in THIS task (MEASURED here)**: the full text of
  the four chain reports (read directly); the pre/post byte states of A and B
  (sha256 + marker-removal equivalence + diffs in §4); the evidence-directory
  inventory in §3 (paths, file counts, sizes, mtimes/launch envelopes,
  `index.json:2` run labels, artifact inventories, citing reports —
  delegated read-only lanes; the hardcoded label at
  `evals/gemini_judge_5case.py:287` verified on disk (pre-documented at
  `docs/clean-5case-validation-2026-09-05.md:141–144`); git status
  before/after; absence of any write to evidence directories.
- **Relayed WITHOUT independent re-verification (DOCUMENTED from the chain)**:
  every substantive figure and verdict in §2 rows 1–4 — the case-4 outcome
  values and pass counts, the 9/31 census, the 19/19 artifact count, the run4
  ground truth (SIGINT 16:52:54Z, ticket progression timestamps), the
  materiality rulings, and the UNKNOWN items listed under §2.

## 6. Zero-side-effect confirmation

- `git status --porcelain=v1` before this task (46 lines, snapshot
  `/tmp/case4-git-status-before.txt`) vs after: the identical set plus this
  one new untracked file. Reports A and B are untracked, so their
  annotation-only modification is proven by the §4 byte-level snapshots, not
  by git. `git diff --cached` empty; HEAD unchanged (`ac1ba3a`); nothing
  staged, committed, or pushed.
- No write issued by this task anywhere under `agent-memory/` (§3 is
  read-only; lane-verified: zero evidence-tree mtimes after 21:25 local).
  One environmental side effect, not a task write: the harness command guard
  appended to `agent-memory/guard-audit.log` at session start (21:27:41
  local), before this task's first action. No tests, benchmarks, canaries,
  or live LLM/API calls; no application/eval code touched.
- Secrets: none encountered or reproduced; the namesake dir's
  `preflight.json` records key presence only (values never logged).

END OF INDEX
